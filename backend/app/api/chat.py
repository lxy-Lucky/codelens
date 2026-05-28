import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest
from app.services import prompts, retriever, state
from app.services.ollama_client import ollama

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(req: ChatRequest):
    repo = await asyncio.to_thread(state.get_repo, req.repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")

    # 有选中代码:围绕选中片段(仍补充检索结果);无选中:全库检索
    hits = await retriever.search(req.repo_id, req.message)

    messages = prompts.build_messages(
        question=req.message,
        hits=hits,
        history=[m.model_dump() for m in req.history],
        selected_code=req.selected_code,
        selected_file=req.selected_file,
    )

    async def event_gen():
        # 先把引用片段(grounding 来源)发给前端,便于渲染可点链接
        refs = [
            {"file": h.file_path, "start_line": h.start_line, "end_line": h.end_line,
             "symbol": h.symbol, "kind": h.kind}
            for h in hits
        ]
        yield f"data: {json.dumps({'type': 'refs', 'refs': refs}, ensure_ascii=False)}\n\n"
        try:
            async for token in ollama.chat_stream(messages):
                yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
