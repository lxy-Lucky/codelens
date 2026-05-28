import asyncio

from fastapi import APIRouter, HTTPException

from app.models.schemas import SearchRequest, SearchResponse
from app.services import retriever, state

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def semantic_search(req: SearchRequest):
    repo = await asyncio.to_thread(state.get_repo, req.repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    hits = await retriever.search(req.repo_id, req.query, req.top_n, req.languages)
    return SearchResponse(query=req.query, hits=hits)
