"""SQLite 状态库:仓库注册 + 文件 hash(增量) + 文件→chunk/node 映射(级联删除)。

同步实现,异步上下文用 asyncio.to_thread 调用。
"""
import json
import sqlite3
import threading
from contextlib import contextmanager

from app.config import settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    excludes TEXT NOT NULL DEFAULT '[]',
    language_stats TEXT NOT NULL DEFAULT '{}',
    file_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS files (
    repo_id TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    language TEXT,
    PRIMARY KEY (repo_id, rel_path)
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    rel_path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(repo_id, rel_path);
"""


@contextmanager
def _conn():
    with _lock:
        conn = sqlite3.connect(settings.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


# ─── repos ───
def upsert_repo(repo: dict) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO repos (id, name, path, status, excludes, language_stats, file_count, chunk_count, error)
               VALUES (:id, :name, :path, :status, :excludes, :language_stats, :file_count, :chunk_count, :error)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, path=excluded.path, status=excluded.status,
                 excludes=excluded.excludes, language_stats=excluded.language_stats,
                 file_count=excluded.file_count, chunk_count=excluded.chunk_count, error=excluded.error""",
            {
                **repo,
                "excludes": json.dumps(repo.get("excludes", [])),
                "language_stats": json.dumps(repo.get("language_stats", {})),
            },
        )


def set_repo_status(repo_id: str, status: str, error: str | None = None) -> None:
    with _conn() as c:
        c.execute("UPDATE repos SET status=?, error=? WHERE id=?", (status, error, repo_id))


def get_repo(repo_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone()
    return _row_to_repo(row) if row else None


def list_repos() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM repos ORDER BY name").fetchall()
    return [_row_to_repo(r) for r in rows]


def delete_repo(repo_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM repos WHERE id=?", (repo_id,))
        c.execute("DELETE FROM files WHERE repo_id=?", (repo_id,))
        c.execute("DELETE FROM chunks WHERE repo_id=?", (repo_id,))


def _row_to_repo(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["excludes"] = json.loads(d.get("excludes") or "[]")
    d["language_stats"] = json.loads(d.get("language_stats") or "{}")
    return d


# ─── files (增量) ───
def get_file_hashes(repo_id: str) -> dict[str, str]:
    with _conn() as c:
        rows = c.execute("SELECT rel_path, hash FROM files WHERE repo_id=?", (repo_id,)).fetchall()
    return {r["rel_path"]: r["hash"] for r in rows}


def upsert_file(repo_id: str, rel_path: str, file_hash: str, language: str | None) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO files (repo_id, rel_path, hash, language) VALUES (?, ?, ?, ?)
               ON CONFLICT(repo_id, rel_path) DO UPDATE SET hash=excluded.hash, language=excluded.language""",
            (repo_id, rel_path, file_hash, language),
        )


def delete_file_record(repo_id: str, rel_path: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM files WHERE repo_id=? AND rel_path=?", (repo_id, rel_path))


# ─── chunks (级联删除映射) ───
def get_chunk_ids_for_file(repo_id: str, rel_path: str) -> list[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT chunk_id FROM chunks WHERE repo_id=? AND rel_path=?", (repo_id, rel_path)
        ).fetchall()
    return [r["chunk_id"] for r in rows]


def replace_file_chunks(repo_id: str, rel_path: str, chunk_ids: list[str]) -> None:
    with _conn() as c:
        c.execute("DELETE FROM chunks WHERE repo_id=? AND rel_path=?", (repo_id, rel_path))
        c.executemany(
            "INSERT OR REPLACE INTO chunks (chunk_id, repo_id, rel_path) VALUES (?, ?, ?)",
            [(cid, repo_id, rel_path) for cid in chunk_ids],
        )


def count_chunks(repo_id: str) -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM chunks WHERE repo_id=?", (repo_id,)).fetchone()[0]
