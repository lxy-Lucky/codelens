"""bge-m3 embedding + bge-reranker。延迟加载,默认跑 CPU 以给 14B 腾显存。"""
import os
from functools import lru_cache

# 必须在 transformers/tokenizers/torch 导入前设置:
# - TOKENIZERS_PARALLELISM:子线程调用 fast tokenizer 的 Rust 线程会死锁
# - OMP/MKL=1:embedding 跑在工作线程(非主线程),OpenMP 并行区在非主线程会死锁;
#   压到单线程规避(CPU embedding 会慢些,后续上 GPU 再放开)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from app.config import settings

MAX_EMBED_CHARS = 8000  # 单 chunk 送入 encode 的字符上限,防止超长块拖死


@lru_cache
def _embedder():
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)  # 关键:避免非主线程 OpenMP 并行死锁
    return SentenceTransformer(settings.embedding_model, device=settings.embedding_device)


@lru_cache
def _reranker():
    from FlagEmbedding import FlagReranker

    return FlagReranker(settings.reranker_model, use_fp16=False)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    capped = [t[:MAX_EMBED_CHARS] for t in texts]
    vecs = _embedder().encode(
        capped, normalize_embeddings=True, batch_size=16, show_progress_bar=False
    )
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_dim() -> int:
    return _embedder().get_embedding_dimension()


def rerank(query: str, docs: list[str]) -> list[float]:
    """返回每个 doc 与 query 的相关性分数。"""
    if not docs:
        return []
    pairs = [[query, d] for d in docs]
    scores = _reranker().compute_score(pairs, normalize=True)
    return scores if isinstance(scores, list) else [scores]
