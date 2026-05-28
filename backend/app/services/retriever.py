"""检索:向量召回 top_k → bge-reranker 精排 → top_n。符号名精确命中加权。

(BM25 全文混合检索为后续增强,当前用向量召回 + 符号名加权覆盖精确符号场景。)
"""
import asyncio
import re

from app.config import settings
from app.models.schemas import CodeChunkHit
from app.services import embedding, qdrant_store


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


def _search_sync(repo_id: str, query: str, top_n: int) -> list[CodeChunkHit]:
    qvec = embedding.embed_query(query)
    raw = qdrant_store.search(repo_id, qvec, settings.retrieval_top_k)
    if not raw:
        return []

    docs = [r["payload"].get("text", "") for r in raw]
    rerank_scores = embedding.rerank(query, docs)

    qtokens = _tokens(query)
    scored: list[tuple[float, dict]] = []
    for r, rs in zip(raw, rerank_scores):
        payload = dict(r["payload"])
        payload["_chunk_id"] = r["id"]
        symbol = (payload.get("symbol") or "").lower()
        boost = 0.15 if symbol and symbol in qtokens else 0.0
        scored.append((rs + boost, payload))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_to_hit(p, s) for s, p in scored[:top_n]]


async def search(repo_id: str, query: str, top_n: int | None = None) -> list[CodeChunkHit]:
    n = top_n or settings.rerank_top_n
    return await asyncio.to_thread(_search_sync, repo_id, query, n)
