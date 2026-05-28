import asyncio
from fnmatch import fnmatch
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import TreeNode
from app.services import state
from app.services.languages import detect_language

router = APIRouter(prefix="/api/files", tags=["files"])


def _excluded(name: str, excludes: list[str]) -> bool:
    return any(name == p or fnmatch(name, p) for p in excludes)


def _build_tree(root: Path, excludes: list[str]) -> list[TreeNode]:
    def walk(d: Path) -> list[TreeNode]:
        nodes: list[TreeNode] = []
        try:
            entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return nodes
        for p in entries:
            if _excluded(p.name, excludes):
                continue
            rel = str(p.relative_to(root)).replace("\\", "/")
            if p.is_dir():
                children = walk(p)
                if children:  # 跳过空目录
                    nodes.append(TreeNode(name=p.name, path=rel, type="dir", children=children))
            else:
                lang = detect_language(p.name)
                if lang:  # 只展示支持的代码文件
                    nodes.append(TreeNode(name=p.name, path=rel, type="file", language=lang))
        return nodes

    return walk(root)


def _safe_resolve(root: Path, rel_path: str) -> Path:
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise HTTPException(400, "非法路径")
    return target


@router.get("/{repo_id}/tree", response_model=list[TreeNode])
async def file_tree(repo_id: str):
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    root = Path(repo["path"])
    return await asyncio.to_thread(_build_tree, root, repo["excludes"])


@router.get("/{repo_id}/content")
async def file_content(repo_id: str, path: str = Query(...)):
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise HTTPException(404, "仓库不存在")
    root = Path(repo["path"])
    target = _safe_resolve(root, path)
    if not target.is_file():
        raise HTTPException(404, "文件不存在")
    content = await asyncio.to_thread(target.read_text, "utf-8", "ignore")
    return {"path": path, "language": detect_language(path), "content": content}
