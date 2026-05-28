"""bge-m3 embedding + bge-reranker。延迟加载,默认跑 CPU 以给 14B 腾显存。"""
from functools import lru_cache

from app.config import settings


@lru_cache
def _embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model, device=settings.embedding_device)


@lru_cache
def _reranker():
    from FlagEmbedding import FlagReranker

    return FlagReranker(settings.reranker_model, use_fp16=False)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vecs = _embedder().encode(texts, normalize_embeddings=True, batch_size=32)
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
