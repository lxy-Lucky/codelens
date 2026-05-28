"""索引流水线:遍历 → 增量(文件 hash)→ tree-sitter 切块 → embedding → Qdrant 入库。

以「单文件」为事务单位:删旧向量 → 切块 → 嵌入 → 写新向量 → 更新映射。
失败的文件单独记录、跳过,不阻断整库。提供进度事件供 SSE。
"""
import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from fnmatch import fnmatch
from pathlib import Path

from app.services import bm25_store, embedding, qdrant_store, state
from app.services.chunker import chunk_source
from app.services.languages import SUPPORTED_EXTS, detect_language

MAX_FILE_BYTES = 1_000_000  # 跳过超大文件


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _is_excluded(rel_parts: tuple[str, ...], excludes: list[str]) -> bool:
    for part in rel_parts:
        for pat in excludes:
            if part == pat or fnmatch(part, pat):
                return True
    return False


def _walk_files(root: Path, excludes: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_excluded(rel.parts, excludes):
            continue
        if p.suffix not in SUPPORTED_EXTS:
            continue
        out.append(p)
    return out


def _index_one_file(repo_id: str, root: Path, file: Path) -> tuple[int, str | None]:
    """处理单个文件,返回 (chunk 数, 语言)。"""
    rel_path = str(file.relative_to(root)).replace("\\", "/")
    language = detect_language(rel_path)
    raw = file.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        return 0, language
    source = raw.decode("utf-8", "ignore")

    chunks = chunk_source(source, language) if language else []

    # 删旧向量(级联),再写新的
    old_ids = state.get_chunk_ids_for_file(repo_id, rel_path)
    if old_ids:
        qdrant_store.delete_points(old_ids)

    if not chunks:
        state.replace_file_chunks(repo_id, rel_path, [])
        return 0, language

    texts = [c.text for c in chunks]
    vectors = embedding.embed_texts(texts)
    points = []
    chunk_ids = []
    for c, vec in zip(chunks, vectors):
        cid = str(uuid.uuid4())
        chunk_ids.append(cid)
        points.append({
            "id": cid,
            "vector": vec,
            "payload": {
                "repo_id": repo_id,
                "rel_path": rel_path,
                "symbol": c.symbol,
                "kind": c.kind,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "language": language,
                "text": c.text,
            },
        })
    qdrant_store.upsert_chunks(points)
    state.replace_file_chunks(repo_id, rel_path, chunk_ids)
    return len(chunks), language


async def index_repo(repo_id: str, root_path: str, excludes: list[str]) -> AsyncIterator[dict]:
    """异步生成进度事件:{stage, current, total, file, ...}"""
    root = Path(root_path)
    if not root.is_dir():
        yield {"stage": "error", "message": f"路径不存在或不是目录: {root_path}"}
        return

    qdrant_store.ensure_collection(embedding.embedding_dim())
    state.set_repo_status(repo_id, "indexing")

    yield {"stage": "scanning"}
    files = await asyncio.to_thread(_walk_files, root, excludes)
    total = len(files)
    yield {"stage": "scanned", "total": total}

    prev_hashes = await asyncio.to_thread(state.get_file_hashes, repo_id)
    seen: set[str] = set()
    lang_stats: dict[str, int] = {}
    errors = 0

    for i, file in enumerate(files):
        rel_path = str(file.relative_to(root)).replace("\\", "/")
        seen.add(rel_path)
        try:
            raw = await asyncio.to_thread(file.read_bytes)
            fhash = _hash(raw.decode("utf-8", "ignore"))
            if prev_hashes.get(rel_path) == fhash:
                lang = detect_language(rel_path)
                if lang:
                    lang_stats[lang] = lang_stats.get(lang, 0) + 1
                yield {"stage": "skip", "current": i + 1, "total": total, "file": rel_path}
                continue
            _, lang = await asyncio.to_thread(_index_one_file, repo_id, root, file)
            await asyncio.to_thread(state.upsert_file, repo_id, rel_path, fhash, lang)
            if lang:
                lang_stats[lang] = lang_stats.get(lang, 0) + 1
            yield {"stage": "indexed", "current": i + 1, "total": total, "file": rel_path}
        except Exception as e:  # noqa: BLE001 单文件失败不阻断
            errors += 1
            yield {"stage": "file_error", "current": i + 1, "total": total,
                   "file": rel_path, "message": str(e)}

    # 清理已删除的文件(上次有、这次没见到)
    for stale in set(prev_hashes) - seen:
        old_ids = await asyncio.to_thread(state.get_chunk_ids_for_file, repo_id, stale)
        await asyncio.to_thread(qdrant_store.delete_points, old_ids)
        await asyncio.to_thread(state.delete_file_record, repo_id, stale)
        yield {"stage": "removed", "file": stale}

    bm25_store.invalidate(repo_id)  # 内容可能变但 chunk 数不变,显式失效
    chunk_count = await asyncio.to_thread(state.count_chunks, repo_id)
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if repo:
        repo.update({"status": "ready", "file_count": len(seen),
                     "chunk_count": chunk_count, "language_stats": lang_stats, "error": None})
        await asyncio.to_thread(state.upsert_repo, repo)
    yield {"stage": "done", "total": total, "chunks": chunk_count, "errors": errors}
