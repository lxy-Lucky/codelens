import asyncio
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import fileio, prompts, state
from app.services.languages import detect_language
from app.services.ollama_client import ollama

router = APIRouter(prefix="/api/docs", tags=["docs"])


class DocRequest(BaseModel):
    repo_id: str
    path: str  # 相对路径
    locale: Literal["zh", "ja", "en"] = "zh"


def _safe(root: Path, rel: str) -> Path:
    t = (root / rel).resolve()
    if not str(t).startswith(str(root.resolve())):
        raise HTTPException(400, "非法路径")
    return t


@router.post("")
async def generate_docs(req: DocRequest):
    repo = await asyncio.to_thread(state.get_repo, req.repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    target = _safe(Path(repo["path"]), req.path)
    if not target.is_file():
        raise HTTPException(404, "文件不存在")
    source = await asyncio.to_thread(fileio.read_text, target)
    lang = detect_language(req.path)

    messages = prompts.build_docs_messages(req.path, lang, source, locale=req.locale)

    async def gen():
        try:
            async for token in ollama.chat_stream(messages, temperature=0.3):
                yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
