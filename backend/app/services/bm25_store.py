"""每仓 BM25 索引:从 Qdrant 拉全量 chunk 构建,按 chunk 数签名缓存,失效自动重建。

语料用「符号名 + 代码文本」分词,对精确符号检索友好。
"""
import threading

from app.services import qdrant_store, state
from app.services.tokenize import tokenize

_lock = threading.Lock()
# repo_id -> {signature, bm25, ids, payloads}
_cache: dict[str, dict] = {}


def _build(repo_id: str) -> dict:
    from rank_bm25 import BM25Okapi

    rows = qdrant_store.scroll_repo(repo_id)
    ids = [r["id"] for r in rows]
    payloads = [r["payload"] for r in rows]
    corpus = []
    for p in payloads:
        text = (p.get("symbol") or "") + " " + (p.get("text") or "")
        corpus.append(tokenize(text))
    bm25 = BM25Okapi(corpus) if corpus else None
    return {"bm25": bm25, "ids": ids, "payloads": payloads}


def _get(repo_id: str) -> dict | None:
    signature = state.count_chunks(repo_id)
    with _lock:
        cached = _cache.get(repo_id)
        if cached and cached["signature"] == signature:
            return cached
        built = _build(repo_id)
        built["signature"] = signature
        _cache[repo_id] = built
        return built


def invalidate(repo_id: str) -> None:
    with _lock:
        _cache.pop(repo_id, None)


def search(repo_id: str, query: str, limit: int, languages: list[str] | None = None) -> list[dict]:
    """返回 [{id, score, payload}],按 BM25 分降序。languages 非空时按语言过滤。"""
    entry = _get(repo_id)
    if not entry or entry["bm25"] is None:
        return []
    tokens = tokenize(query)
    if not tokens:
        return []
    lang_set = set(languages) if languages else None
    scores = entry["bm25"].get_scores(tokens)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out = []
    for i in ranked:
        if scores[i] <= 0:
            continue
        payload = entry["payloads"][i]
        if lang_set and payload.get("language") not in lang_set:
            continue
        p = dict(payload)
        p["_chunk_id"] = entry["ids"][i]
        out.append({"id": entry["ids"][i], "score": float(scores[i]), "payload": p})
        if len(out) >= limit:
            break
    return out
