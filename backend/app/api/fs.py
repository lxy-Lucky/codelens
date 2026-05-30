"""文件系统浏览:仅供本地路径补全。只列目录,不返回文件内容。"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/fs", tags=["fs"])


@router.get("/list")
def list_dir(path: str = ""):
    """列出给定路径下的子目录(用于路径自动补全)。

    - path 为空 → 返回 home 目录 + 常见根盘(Windows)/根目录(POSIX)入口
    - path 不存在 → 当作"在父目录里按前缀过滤"处理,便于输入到一半就提示
    """
    p = Path(path) if path else Path.home()

    # 输入了不存在的路径:按父目录前缀过滤
    if path and not p.exists():
        parent = p.parent
        prefix = p.name.lower()
        if not parent.exists() or not parent.is_dir():
            return {"path": str(p), "exists": False, "entries": []}
        try:
            subs = sorted(
                (d for d in parent.iterdir() if d.is_dir() and d.name.lower().startswith(prefix)),
                key=lambda d: d.name.lower(),
            )
        except PermissionError:
            return {"path": str(parent), "exists": True, "entries": []}
        return {
            "path": str(parent),
            "exists": True,
            "entries": [{"name": d.name, "path": str(d)} for d in subs[:200]],
        }

    if not p.exists() or not p.is_dir():
        raise HTTPException(400, f"不是目录: {p}")

    try:
        subs = sorted(
            (d for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")),
            key=lambda d: d.name.lower(),
        )
    except PermissionError:
        return {"path": str(p), "exists": True, "entries": []}

    return {
        "path": str(p),
        "exists": True,
        "entries": [{"name": d.name, "path": str(d)} for d in subs[:500]],
    }
