"""Qdrant 向量库:单 collection,repo_id 作 payload 过滤,按 point id 级联删除。"""
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings

COLLECTION = "codelens_chunks"


@lru_cache
def client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(dim: int) -> None:
    c = client()
    existing = {col.name for col in c.get_collections().collections}
    if COLLECTION not in existing:
        c.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        c.create_payload_index(COLLECTION, "repo_id", qm.PayloadSchemaType.KEYWORD)


def upsert_chunks(points: list[dict]) -> None:
    """points: [{id, vector, payload}]"""
    if not points:
        return
    client().upsert(
        collection_name=COLLECTION,
        points=[qm.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points],
    )


def delete_points(ids: list[str]) -> None:
    if not ids:
        return
    client().delete(
        collection_name=COLLECTION,
        points_selector=qm.PointIdsList(points=ids),
    )


def delete_repo(repo_id: str) -> None:
    client().delete(
        collection_name=COLLECTION,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(must=[qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))])
        ),
    )


def search(repo_id: str, query_vector: list[float], limit: int) -> list[dict]:
    res = client().query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=limit,
        query_filter=qm.Filter(
            must=[qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))]
        ),
        with_payload=True,
    ).points
    return [{"id": str(p.id), "score": p.score, "payload": p.payload} for p in res]
