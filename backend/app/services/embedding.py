"""bge-m3 embedding + bge-reranker。延迟加载,默认跑 CPU 以给 14B 腾显存。"""
import os
from functools import lru_cache

from app.config import settings

# 必须在 transformers/tokenizers/torch 导入前设置:
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # 子线程调用 fast tokenizer 会死锁
# OMP/MKL=1:只要 embedding 或 reranker 任一在 CPU 跑,其在工作线程里的 OpenMP 并行区就会死锁,
# 必须压到单线程规避。GPU 前向在显卡上无此问题。
if "cpu" in (settings.embedding_device, settings.reranker_device):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

MAX_EMBED_CHARS = 8000  # 单 chunk 送入 encode 的字符上限,防止超长块拖死


def _is_cuda() -> bool:
    return settings.embedding_device.startswith("cuda")


def _batch_size() -> int:
    return 64 if _is_cuda() else 16


@lru_cache
def _embedder():
    import torch
    from sentence_transformers import SentenceTransformer

    if settings.embedding_device == "cpu":
        torch.set_num_threads(1)  # CPU 下避免非主线程 OpenMP 并行死锁
    model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
    if _is_cuda():
        model = model.half()  # fp16:显著提速、省一半显存(便于与 LLM 共存)
    return model


@lru_cache
def _reranker():
    import torch
    from sentence_transformers import CrossEncoder

    dev = settings.reranker_device
    if dev == "cpu":
        torch.set_num_threads(1)  # CPU 下避免非主线程 OpenMP 并行死锁
    ce = CrossEncoder(settings.reranker_model, device=dev, max_length=512)
    if dev.startswith("cuda"):
        ce.model.half()
    return ce


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    capped = [t[:MAX_EMBED_CHARS] for t in texts]
    vecs = _embedder().encode(
        capped, normalize_embeddings=True, batch_size=_batch_size(), show_progress_bar=False
    )
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def embedding_dim() -> int:
    return _embedder().get_embedding_dimension()


def rerank(query: str, docs: list[str]) -> list[float]:
    """返回每个 doc 与 query 的相关性分数(min-max 归一到 [0,1])。"""
    if not docs:
        return []
    import numpy as np

    pairs = [[query, d[:MAX_EMBED_CHARS]] for d in docs]
    raw = np.asarray(_reranker().predict(pairs, convert_to_numpy=True), dtype=float).ravel()
    # 不依赖 predict 是否已 sigmoid:在候选集内 min-max 归一,保证排序单调且与加权可比
    if raw.size > 1 and raw.max() > raw.min():
        raw = (raw - raw.min()) / (raw.max() - raw.min())
    return raw.tolist()
