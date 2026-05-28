import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.services import graph_builder, neo4j_store, state

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.post("/{repo_id}/build")
async def build(repo_id: str):
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    try:
        return await graph_builder.build_graph(repo_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"图构建失败(Neo4j 是否启动?): {e}")


@router.get("/{repo_id}/subgraph")
async def subgraph(repo_id: str, symbol_key: str = Query(...), hops: int = 1):
    try:
        return await asyncio.to_thread(neo4j_store.subgraph, repo_id, symbol_key, min(hops, 3))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"查询失败: {e}")


@router.get("/{repo_id}/mermaid")
async def mermaid(repo_id: str, symbol_key: str = Query(...), hops: int = 1):
    """返回 Mermaid flowchart 文本,供前端直接渲染。"""
    g = await asyncio.to_thread(neo4j_store.subgraph, repo_id, symbol_key, min(hops, 3))
    lines = ["graph LR"]

    def nid(key: str) -> str:
        return "n" + str(abs(hash(key)) % (10**8))

    for n in g["nodes"]:
        label = (n.get("name") or n["key"]).replace('"', "'")
        lines.append(f'  {nid(n["key"])}["{label}"]')
    for e in g["edges"]:
        style = "-->" if (e.get("confidence") or 1) >= 0.8 else "-.->"
        lines.append(f'  {nid(e["src"])} {style} {nid(e["dst"])}')
    return {"mermaid": "\n".join(lines), "node_count": len(g["nodes"])}
