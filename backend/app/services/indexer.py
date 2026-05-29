"""索引流水线:遍历 → 增量(文件 hash)→ tree-sitter 切块 → embedding → Qdrant 入库。

以「单文件」为事务单位:删旧向量 → 切块 → 嵌入 → 写新向量 → 更新映射。
失败的文件单独记录、跳过,不阻断整库。提供进度事件供 SSE。
"""
import asyncio
import hashlib
import time
import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch
from pathlib import Path

from app.services import bm25_store, embedding, fileio, qdrant_store, state
from app.services.chunker import chunk_source
from app.services.languages import SUPPORTED_EXTS, detect_language
from app.services.ts import executor as ts_executor

MAX_FILE_BYTES = 1_000_000  # 跳过超大文件

# 嵌入+入库专用线程,与解析(ts_executor / tree-sitter 线程)分离,实现 CPU 解析与 GPU 嵌入重叠
embed_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="codelens-embed")


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


def _log(msg: str) -> None:
    print(f"[index] {msg}", flush=True)


# 每批文件数:一批文件的所有 chunk 一次性喂 GPU(大批量才高效)
BATCH_FILES = 60


def _parse_file(repo_id: str, root: Path, file: Path, raw: bytes) -> dict:
    """只解析切块(CPU,tree-sitter),不嵌入不入库。返回 {rel_path, language, chunks, old_ids}。"""
    rel_path = str(file.relative_to(root)).replace("\\", "/")
    language = detect_language(rel_path)
    old_ids = state.get_chunk_ids_for_file(repo_id, rel_path)
    if len(raw) > MAX_FILE_BYTES:
        return {"rel_path": rel_path, "language": language, "chunks": [], "old_ids": old_ids}
    source = fileio.decode_bytes(raw)  # 自动检测编码(cp932/gb2312…),避免乱码
    chunks = chunk_source(source, language) if language else []
    return {"rel_path": rel_path, "language": language, "chunks": chunks, "old_ids": old_ids}


def _embed_and_store(repo_id: str, items: list[dict]) -> None:
    """对一批文件的所有 chunk 一次性嵌入(大批量,GPU 高效),再按文件入库。"""
    all_texts = [c.text for it in items for c in it["chunks"]]
    t0 = time.perf_counter()
    vectors = embedding.embed_texts(all_texts) if all_texts else []
    if all_texts:
        _log(f"embedded batch: {len(all_texts)} chunks / {len(items)} files in "
             f"{time.perf_counter() - t0:.2f}s")

    vi = 0
    for it in items:
        rel_path, language, chunks, old_ids = (
            it["rel_path"], it["language"], it["chunks"], it["old_ids"])
        if old_ids:
            qdrant_store.delete_points(old_ids)
        if not chunks:
            state.replace_file_chunks(repo_id, rel_path, [])
            continue
        points, chunk_ids = [], []
        for c in chunks:
            vec = vectors[vi]; vi += 1
            cid = str(uuid.uuid4())
            chunk_ids.append(cid)
            points.append({
                "id": cid,
                "vector": vec,
                "payload": {
                    "repo_id": repo_id, "rel_path": rel_path,
                    "symbol": c.symbol, "kind": c.kind,
                    "start_line": c.start_line, "end_line": c.end_line,
                    "language": language, "text": c.text,
                },
            })
        qdrant_store.upsert_chunks(points)
        state.replace_file_chunks(repo_id, rel_path, chunk_ids)


async def index_repo(repo_id: str, root_path: str, excludes: list[str]) -> AsyncIterator[dict]:
    """异步生成进度事件:{stage, current, total, file, ...}"""
    root = Path(root_path)
    if not root.is_dir():
        yield {"stage": "error", "message": f"路径不存在或不是目录: {root_path}"}
        return

    loop = asyncio.get_running_loop()
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
    processed = 0

    file_batches = [files[i:i + BATCH_FILES] for i in range(0, total, BATCH_FILES)]

    async def parse_batch(batch_files: list[Path]) -> list[dict]:
        """读取+哈希+增量判断+tree-sitter 解析(在 ts 线程),不嵌入。返回每文件结果。"""
        out: list[dict] = []
        for file in batch_files:
            rel = str(file.relative_to(root)).replace("\\", "/")
            seen.add(rel)
            try:
                raw = await asyncio.to_thread(file.read_bytes)
                fhash = hashlib.sha256(raw).hexdigest()  # 直接哈希原始字节,稳定且与编码无关
                if prev_hashes.get(rel) == fhash:
                    out.append({"status": "skip", "rel": rel})
                    continue
                parsed = await loop.run_in_executor(ts_executor, _parse_file, repo_id, root, file, raw)
                out.append({"status": "parse", "rel": rel, "parsed": parsed, "fhash": fhash})
            except Exception as e:  # noqa: BLE001
                out.append({"status": "error", "rel": rel, "msg": str(e)})
        return out

    # 预取一批:在 embed 线程嵌入当前批(GPU)的同时,后台并行解析下一批(CPU)→ 重叠
    prefetch = asyncio.create_task(parse_batch(file_batches[0])) if file_batches else None
    for k in range(len(file_batches)):
        results = await prefetch
        if k + 1 < len(file_batches):
            prefetch = asyncio.create_task(parse_batch(file_batches[k + 1]))

        for r in results:
            if r["status"] == "skip":
                lang = detect_language(r["rel"])
                if lang:
                    lang_stats[lang] = lang_stats.get(lang, 0) + 1
                processed += 1
                yield {"stage": "skip", "current": processed, "total": total, "file": r["rel"]}
            elif r["status"] == "error":
                errors += 1
                processed += 1
                yield {"stage": "file_error", "current": processed, "total": total,
                       "file": r["rel"], "message": r["msg"]}

        parsed_items = [r for r in results if r["status"] == "parse"]
        if not parsed_items:
            continue
        try:
            await loop.run_in_executor(
                embed_executor, _embed_and_store, repo_id, [r["parsed"] for r in parsed_items])
            for r in parsed_items:
                p = r["parsed"]
                await asyncio.to_thread(
                    state.upsert_file, repo_id, p["rel_path"], r["fhash"], p["language"])
                if p["language"]:
                    lang_stats[p["language"]] = lang_stats.get(p["language"], 0) + 1
                processed += 1
            yield {"stage": "indexed", "current": processed, "total": total,
                   "file": parsed_items[-1]["rel"]}
        except Exception as e:  # noqa: BLE001 整批失败不阻断,这批下次重试
            import traceback
            _log("batch error:\n" + traceback.format_exc())  # 打到 uvicorn 控制台
            errors += len(parsed_items)
            processed += len(parsed_items)
            yield {"stage": "file_error", "current": processed, "total": total,
                   "file": "(batch)", "message": f"{type(e).__name__}: {e}"}

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
