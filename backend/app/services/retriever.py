"""混合检索:向量召回 + BM25 召回 → RRF 融合 → bge-reranker 精排 → top_n。

- 向量:语义相近
- BM25:精确符号 / 关键字命中(代码感知分词)
- RRF 融合两路排名,再对融合候选 rerank,符号名精确命中额外加权
"""
import asyncio
import re

from app.config import settings
from app.models.schemas import CodeChunkHit
from app.services import bm25_store, embedding, qdrant_store

RRF_K = 60
FUSION_CANDIDATES = 30  # 融合后送入 reranker 的候选数


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text)}


def _to_hit(payload: dict, score: float) -> CodeChunkHit:
    return CodeChunkHit(
        chunk_id=payload.get("_chunk_id", ""),
        file_path=payload["rel_path"],
        symbol=payload.get("symbol"),
        kind=payload.get("kind"),
        start_line=payload.get("start_line", 0),
        end_line=payload.get("end_line", 0),
        score=score,
        snippet=payload.get("text", ""),
        language=payload.get("language"),
    )


def _rrf_fuse(vector_hits: list[dict], bm25_hits: list[dict]) -> list[dict]:
    """按 RRF 融合两路结果,返回去重后的 payload 列表(含 _rrf 分)。"""
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    for ranklist in (vector_hits, bm25_hits):
        for rank, hit in enumerate(ranklist):
            cid = hit["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            if cid not in payloads:
                p = dict(hit["payload"])
                p["_chunk_id"] = cid
                payloads[cid] = p
    order = sorted(scores, key=lambda c: scores[c], reverse=True)
    return [payloads[c] for c in order[:FUSION_CANDIDATES]]


def _search_sync(repo_id: str, query: str, top_n: int) -> list[CodeChunkHit]:
    qvec = embedding.embed_query(query)
    vector_hits = qdrant_store.search(repo_id, qvec, settings.retrieval_top_k)
    bm25_hits = bm25_store.search(repo_id, query, settings.retrieval_top_k)

    fused = _rrf_fuse(vector_hits, bm25_hits)
    if not fused:
        return []

    docs = [p.get("text", "") for p in fused]
    rerank_scores = embedding.rerank(query, docs)

    qtokens = _tokens(query)
    scored: list[tuple[float, dict]] = []
    for payload, rs in zip(fused, rerank_scores):
        symbol = (payload.get("symbol") or "").lower()
        boost = 0.15 if symbol and symbol in qtokens else 0.0
        scored.append((rs + boost, payload))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_to_hit(p, s) for s, p in scored[:top_n]]


async def search(repo_id: str, query: str, top_n: int | None = None) -> list[CodeChunkHit]:
    n = top_n or settings.rerank_top_n
    return await asyncio.to_thread(_search_sync, repo_id, query, n)
