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

from app.services import fileio, graph_enrich, neo4j_store, state
from app.services.ts import executor as ts_executor
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

# 极通用/JDK 内置方法名:几乎总是库调用,连进图里只是噪声
CALL_STOPWORDS = {
    "tostring", "equals", "hashcode", "getclass", "clone", "wait", "notify",
    "notifyall", "valueof", "compareto", "name", "ordinal", "values",
    "println", "print", "format", "log", "info", "debug", "warn", "error",
}


def _parser(lang: str):
    grammar = LANG_TO_TS_GRAMMAR.get(lang)
    if not grammar:
        return None
    from app.services.ts import get_parser
    return get_parser(grammar)


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
        src = fileio.read_utf8_bytes(f)
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

    def _resolve(callee: str, src_file: str) -> tuple[str, float] | None:
        """名字解析为调用目标。降噪:停用词跳过;优先同文件;仓库内唯一才连;跨文件多义跳过。"""
        if callee.lower() in CALL_STOPWORDS:
            return None
        cands = name_to_keys.get(callee)
        if not cands:
            return None
        same = [k for k in cands if k.rsplit("::", 1)[0] == src_file]
        if same:
            return same[0], 0.9                # 同文件:高置信
        if len(cands) == 1:
            return cands[0], 0.75              # 全库唯一:中置信
        return None                            # 跨文件多义(JDK 同名碰撞等)→ 跳过

    edge_map: dict[tuple, dict] = {}  # (src,dst,type) 去重,保留最高置信

    def _add_edge(s: str, d: str, t: str, conf: float) -> None:
        if s == d:
            return
        k = (s, d, t)
        if k not in edge_map or conf > edge_map[k]["confidence"]:
            edge_map[k] = {"src": s, "dst": d, "type": t, "confidence": conf}

    for sym in symbols:
        node = sym["_node"]
        lang = detect_language(sym["file"])
        call_types = CALL_TYPES.get(lang, set())
        src = fileio.read_utf8_bytes(root / sym["file"])

        def walk_calls(n):
            if n.type in call_types:
                callee = _callee_name(n, src, lang)
                if callee:
                    r = _resolve(callee, sym["file"])
                    if r:
                        _add_edge(sym["key"], r[0], "CALLS", r[1])
            for ch in n.children:
                walk_calls(ch)

        walk_calls(node)

    edges = list(edge_map.values())

    clean_symbols = [{k: v for k, v in s.items() if k != "_node"} for s in symbols]

    # ─── 增强:API 路由桥接 + MyBatis XML ───
    routes = graph_enrich.extract_routes(root, files)
    fe_calls = graph_enrich.extract_frontend_calls(root, files)
    api_edges = graph_enrich.build_api_edges(routes, fe_calls)
    xml_symbols, xml_edges = graph_enrich.extract_mybatis(root, files, name_to_keys)
    dep_symbols, dep_edges = graph_enrich.extract_file_deps(root, files)

    all_symbols = clean_symbols + xml_symbols + dep_symbols
    all_edges = edges + api_edges + xml_edges + dep_edges

    neo4j_store.delete_repo(repo_id)
    neo4j_store.upsert_symbols_and_edges(repo_id, all_symbols, all_edges)
    return {
        "symbols": len(all_symbols),
        "edges": len(all_edges),
        "routes": len(routes),
        "api_edges": len(api_edges),
        "mybatis_edges": len(xml_edges),
        "dep_edges": len(dep_edges),
    }


async def build_graph(repo_id: str) -> dict:
    repo = await asyncio.to_thread(state.get_repo, repo_id)
    if not repo:
        raise ValueError("仓库不存在")
    # 跑在唯一的解析线程上,与索引共用,确保 tree-sitter Parser 不跨线程
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        ts_executor, _build_sync, repo_id, repo["path"], repo["excludes"]
    )
