from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Repo ───
class RepoStatus(str, Enum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    error = "error"


class IndexRepoRequest(BaseModel):
    path: str = Field(..., description="本地仓库绝对路径")
    name: Optional[str] = None
    excludes: list[str] = Field(
        default_factory=lambda: ["node_modules", ".git", "dist", "build", "target", "vendor"]
    )


class RepoInfo(BaseModel):
    id: str
    name: str
    path: str
    status: RepoStatus
    language_stats: dict[str, int] = Field(default_factory=dict)
    file_count: int = 0
    chunk_count: int = 0
    error: Optional[str] = None


# ─── File tree ───
class TreeNode(BaseModel):
    name: str
    path: str  # relative to repo root
    type: Literal["dir", "file"]
    language: Optional[str] = None
    children: Optional[list["TreeNode"]] = None


# ─── Search ───
class SearchRequest(BaseModel):
    repo_id: str
    query: str
    top_n: Optional[int] = None


class CodeChunkHit(BaseModel):
    chunk_id: str
    file_path: str        # relative path
    symbol: Optional[str]  # function/class name
    kind: Optional[str]    # function | method | class | block
    start_line: int
    end_line: int
    score: float
    snippet: str
    language: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    hits: list[CodeChunkHit]


# ─── Chat ───
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    # 选中代码上下文(可空)。非空时问答围绕这段代码,空则全库检索。
    selected_code: Optional[str] = None
    selected_file: Optional[str] = None
    selected_range: Optional[tuple[int, int]] = None


TreeNode.model_rebuild()
