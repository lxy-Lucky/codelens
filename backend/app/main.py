import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, docs, files, graph, repos, search
from app.services import neo4j_store, state
from app.services.ollama_client import ollama


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(state.init_db)
    try:
        await asyncio.to_thread(neo4j_store.ensure_constraints)
    except Exception:
        pass  # Neo4j 未启动不阻断 MVP 检索功能
    # 后台预热 LLM(避免首问冷启动)
    asyncio.create_task(ollama.warmup())
    yield


app = FastAPI(title="CodeLens", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repos.router)
app.include_router(search.router)
app.include_router(files.router)
app.include_router(chat.router)
app.include_router(graph.router)
app.include_router(docs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
