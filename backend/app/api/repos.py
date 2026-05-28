import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import IndexRepoRequest, RepoInfo
from app.services import bm25_store, indexer, neo4j_store, qdrant_store, state

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.get("", response_model=list[RepoInfo])
async def list_repos():
    return await asyncio.to_thread(state.list_repos)


@router.post("", response_model=RepoInfo)
async def create_repo(req: IndexRepoRequest):
    root = Path(req.path)
    if not root.is_dir():
        raise HTTPException(400, f"路径不存在或不是目录: {req.path}")
    repo_id = str(uuid.uuid4())
    repo = {
        "id": repo_id,
        "name": req.name or root.name,
        "path": str(root.resolve()),
        "status": "pending",
        "excludes": req.excludes,
        "language_stats": {},
        "file_count": 0,
        "chunk_count": 0,
        "error": None,
    }
    await asyncio.to_thread(state.upsert_repo, repo)
    return repo


@router.get("/{repo_id}/index")
async def index_repo_stream(repo_id: str):
    """SSE 流式索引进度。"""
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")

    async def event_gen():
        try:
            async for ev in indexer.index_repo(repo_id, repo["path"], repo["excludes"]):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            await asyncio.to_thread(state.set_repo_status, repo_id, "error", str(e))
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.delete("/{repo_id}")
async def delete_repo(repo_id: str):
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    # 级联删除:Qdrant 向量 + Neo4j 图 + SQLite 记录
    await asyncio.to_thread(qdrant_store.delete_repo, repo_id)
    try:
        await asyncio.to_thread(neo4j_store.delete_repo, repo_id)
    except Exception:
        pass
    await asyncio.to_thread(state.delete_repo, repo_id)
    bm25_store.invalidate(repo_id)
    return {"ok": True}
