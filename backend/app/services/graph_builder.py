"""调用图/依赖图提取(tree-sitter,名字解析,标注置信度)。

两遍:
  1. 收集全仓符号定义 → 符号表(name -> [keys])
  2. 对每个定义,遍历其子树找调用,按名字解析为边(同名唯一=高,多义=中,跨语言不连)

注意:这是语法级近似。接口/多态、依赖注入、动态调用无法精确解析,故每条边带 confidence。
Java 图与 JS/TS 图天然不相连(前后端),不强行桥接。
"""
import asyncio
from fnmatch import fnmatch
from pathlib import Path

from app.services import graph_enrich, neo4j_store, state
from app.services.languages import LANG_TO_TS_GRAMMAR, SUPPORTED_EXTS, detect_language

DEF_TYPES = {
    "java": {"method_declaration", "constructor_declaration", "class_declaration", "interface_declaration"},
    "javascript": {"function_declaration", "method_definition", "class_declaration"},
    "typescript": {"function_declaration", "method_definition", "class_declaration", "interface_declaration"},
    "tsx": {"function_declaration", "method_definition", "class_declaration", "interface_declaration"},
}
CALL_TYPES = {
    "java": {"method_invocation"},
    "javascript": {"call_expression"},
    "typescript": {"call_expression"},
    "tsx": {"call_expression"},
}


def _parser(lang: str):
    grammar = LANG_TO_TS_GRAMMAR.get(lang)
    if not grammar:
        return None
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser(grammar)
    except Exception:
        return None


def _def_name(node, src: bytes) -> str | None:
    n = node.child_by_field_name("name")
    if n:
        return src[n.start_byte:n.end_byte].decode("utf-8", "ignore")
    for ch in node.children:
        if "identifier" in ch.type:
            return src[ch.start_byte:ch.end_byte].decode("utf-8", "ignore")
    return None


def _callee_name(node, src: bytes, lang: str) -> str | None:
    if lang == "java":
        n = node.child_by_field_name("name")
        if n:
            return src[n.start_byte:n.end_byte].decode("utf-8", "ignore")
    else:
        fn = node.child_by_field_name("function")
        if fn is None:
            return None
        if fn.type == "identifier":
            return src[fn.start_byte:fn.end_byte].decode("utf-8", "ignore")
        if fn.type in ("member_expression", "member_access_expression"):
            prop = fn.child_by_field_name("property")
            if prop:
                return src[prop.start_byte:prop.end_byte].decode("utf-8", "ignore")
    return None


def _collect_defs(root: Path, files: list[Path]) -> tuple[list[dict], dict[str, list[str]], dict]:
    symbols: list[dict] = []
    name_to_keys: dict[str, list[str]] = {}
    file_trees: dict = {}  # rel_path -> (lang, tree, src, parser)
    for f in files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        lang = detect_language(rel)
        parser = _parser(lang) if lang else None
        if not parser:
            continue
        src = f.read_bytes()
        tree = parser.parse(src)
        file_trees[rel] = (lang, tree, src)
        targets = DEF_TYPES.get(lang, set())

        def visit(node):
            if node.type in targets:
                name = _def_name(node, src)
                if name:
                    key = f"{rel}::{name}"
                    kind = "class" if "class" in node.type or "interface" in node.type else (
                        "method" if "method" in node.type or "constructor" in node.type else "function")
                    symbols.append({"key": key, "name": name, "kind": kind,
                                    "file": rel, "line": node.start_point[0] + 1,
                                    "_node": node})
                    name_to_keys.setdefault(name, []).append(key)
            for ch in node.children:
                visit(ch)

        visit(tree.root_node)
    return symbols, name_to_keys, file_trees


def _build_sync(repo_id: str, root_path: str, excludes: list[str]) -> dict:
    root = Path(root_path)
    files = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix in SUPPORTED_EXTS
        and not any(part == e or fnmatch(part, e) for part in p.relative_to(root).parts for e in excludes)
    ]
    symbols, name_to_keys, _ = _collect_defs(root, files)

    edges: list[dict] = []
    for sym in symbols:
        node = sym["_node"]
        lang = detect_language(sym["file"])
        call_types = CALL_TYPES.get(lang, set())
        src = None
        # 找该符号所在文件 src:从 symbols 同 file 复用较繁,直接重读
        src = (root / sym["file"]).read_bytes()

        def walk_calls(n):
            if n.type in call_types:
                callee = _callee_name(n, src, lang)
                if callee and callee in name_to_keys:
                    targets = name_to_keys[callee]
                    conf = 0.9 if len(targets) == 1 else 0.5
                    for tkey in targets:
                        if tkey != sym["key"]:
                            edges.append({"src": sym["key"], "dst": tkey,
                                          "type": "CALLS", "confidence": conf})
            for ch in n.children:
                walk_calls(ch)

        walk_calls(node)

    clean_symbols = [{k: v for k, v in s.items() if k != "_node"} for s in symbols]

    # ─── 增强:API 路由桥接 + MyBatis XML ───
    routes = graph_enrich.extract_routes(root, files)
    fe_calls = graph_enrich.extract_frontend_calls(root, files)
    api_edges = graph_enrich.build_api_edges(routes, fe_calls)
    xml_symbols, xml_edges = graph_enrich.extract_mybatis(root, files, name_to_keys)

    all_symbols = clean_symbols + xml_symbols
    all_edges = edges + api_edges + xml_edges

    neo4j_store.delete_repo(repo_id)
    neo4j_store.upsert_symbols_and_edges(repo_id, all_symbols, all_edges)
    return {
        "symbols": len(all_symbols),
        "edges": len(all_edges),
        "routes": len(routes),
        "api_edges": len(api_edges),
        "mybatis_edges": len(xml_edges),
    }


async def build_graph(repo_id: str) -> dict:
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise ValueError("仓库不存在")
    return await asyncio.to_thread(_build_sync, repo_id, repo["path"], repo["excludes"])
