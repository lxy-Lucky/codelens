"""Neo4j 图库:符号节点 + CALLS / DEPENDS_ON 边,带置信度,按 repo_id 隔离。"""
from functools import lru_cache

from neo4j import GraphDatabase

from app.config import settings


@lru_cache
def driver():
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


def ensure_constraints() -> None:
    with driver().session() as s:
        s.run(
            "CREATE CONSTRAINT symbol_key IF NOT EXISTS "
            "FOR (n:Symbol) REQUIRE (n.repo_id, n.key) IS UNIQUE"
        )


def delete_repo(repo_id: str) -> None:
    with driver().session() as s:
        s.run("MATCH (n:Symbol {repo_id:$r}) DETACH DELETE n", r=repo_id)


def delete_file(repo_id: str, rel_path: str) -> None:
    with driver().session() as s:
        s.run(
            "MATCH (n:Symbol {repo_id:$r, file:$f}) DETACH DELETE n",
            r=repo_id, f=rel_path,
        )


def upsert_symbols_and_edges(repo_id: str, symbols: list[dict], edges: list[dict]) -> None:
    """symbols: [{key, name, kind, file, line}]
    edges: [{src, dst, type, confidence}]  (src/dst 为 symbol key)
    """
    with driver().session() as s:
        if symbols:
            s.run(
                """UNWIND $rows AS row
                   MERGE (n:Symbol {repo_id:$r, key:row.key})
                   SET n.name=row.name, n.kind=row.kind, n.file=row.file, n.line=row.line""",
                rows=symbols, r=repo_id,
            )
        if edges:
            s.run(
                """UNWIND $rows AS row
                   MATCH (a:Symbol {repo_id:$r, key:row.src})
                   MATCH (b:Symbol {repo_id:$r, key:row.dst})
                   MERGE (a)-[e:REL {type:row.type}]->(b)
                   SET e.confidence=row.confidence""",
                rows=edges, r=repo_id,
            )


def file_deps(repo_id: str, file_key: str) -> dict:
    """某文件的依赖(它 import 的)与被依赖(import 它的),基于 DEPENDS_ON 边。"""
    with driver().session() as s:
        imp = s.run(
            """MATCH (f:Symbol {repo_id:$r, key:$k})-[e:REL]->(t:Symbol)
               WHERE e.type='DEPENDS_ON'
               RETURN t.key AS key, t.name AS name, t.file AS file""",
            r=repo_id, k=file_key,
        )
        imports = [{"key": x["key"], "name": x["name"], "file": x["file"]} for x in imp]
        by = s.run(
            """MATCH (sx:Symbol)-[e:REL]->(f:Symbol {repo_id:$r, key:$k})
               WHERE e.type='DEPENDS_ON'
               RETURN sx.key AS key, sx.name AS name, sx.file AS file""",
            r=repo_id, k=file_key,
        )
        imported_by = [{"key": x["key"], "name": x["name"], "file": x["file"]} for x in by]
    return {"imports": imports, "imported_by": imported_by}


def subgraph(repo_id: str, symbol_key: str, hops: int = 1) -> dict:
    """返回某节点 ±hops 跳的子图,供 Mermaid 渲染。"""
    with driver().session() as s:
        result = s.run(
            f"""MATCH (center:Symbol {{repo_id:$r, key:$k}})
                CALL {{
                  WITH center
                  MATCH path=(center)-[*1..{hops}]-(m:Symbol)
                  RETURN path LIMIT 400
                }}
                WITH collect(path) AS paths
                RETURN paths""",
            r=repo_id, k=symbol_key,
        )
        record = result.single()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    if record and record["paths"]:
        for path in record["paths"]:
            for node in path.nodes:
                nodes[node["key"]] = {
                    "key": node["key"], "name": node.get("name"),
                    "kind": node.get("kind"), "file": node.get("file"), "line": node.get("line"),
                }
            for rel in path.relationships:
                edges.append({
                    "src": rel.start_node["key"], "dst": rel.end_node["key"],
                    "type": rel.get("type"), "confidence": rel.get("confidence"),
                })
    return {"nodes": list(nodes.values()), "edges": edges}
