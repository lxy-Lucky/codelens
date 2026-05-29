"""图谱增强:
  1. API 路由桥接 —— Spring 路由(@*Mapping)与前端 HTTP 调用(axios/fetch)按归一化 URL 连 CALLS_API 边
  2. MyBatis —— mapper XML 的 statement 连到同名接口方法(MAPS_TO 边),并为 SQL statement 建节点

边均带 confidence,低于精确直连。跨语言只在 URL/名字能对上时才连,不硬连。
"""
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.services import fileio
from app.services.chunker import _extract_script_from_vue
from app.services.languages import LANG_TO_TS_GRAMMAR, detect_language

MAPPING_RE = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping")
FIRST_STR_RE = re.compile(r'"([^"]*)"')
HTTP_VERBS = {"get", "post", "put", "delete", "patch", "request"}


def _parser(lang: str):
    grammar = LANG_TO_TS_GRAMMAR.get(lang)
    if not grammar:
        return None
    from app.services.ts import get_parser
    return get_parser(grammar)


def normalize_url(url: str) -> str:
    """归一化:去协议/host、去 query、路径参数统一为 *、去尾斜杠。"""
    if not url:
        return ""
    url = url.split("?")[0].strip()
    url = re.sub(r"^https?://[^/]+", "", url)
    # JS ${...} 必须先于 Spring {id} 处理,否则 ${id} 会被错切成 $*
    url = re.sub(r"\$\{[^}]*\}", "*", url)
    url = re.sub(r"\{[^}]*\}", "*", url)
    url = re.sub(r":[A-Za-z_][A-Za-z0-9_]*", "*", url)
    if not url.startswith("/"):
        url = "/" + url
    if len(url) > 1 and url.endswith("/"):
        url = url[:-1]
    return url


# ─── Java Spring routes ───
def _modifiers_text(node, src: bytes) -> str:
    for ch in node.children:
        if ch.type == "modifiers":
            return src[ch.start_byte:ch.end_byte].decode("utf-8", "ignore")
    return ""


def _name_of(node, src: bytes) -> str | None:
    n = node.child_by_field_name("name")
    return src[n.start_byte:n.end_byte].decode("utf-8", "ignore") if n else None


def extract_routes(root: Path, files: list[Path]) -> dict[str, str]:
    """归一化路由 -> handler 方法 symbol key。"""
    routes: dict[str, str] = {}
    for f in files:
        if detect_language(str(f)) != "java":
            continue
        parser = _parser("java")
        if not parser:
            return routes
        rel = str(f.relative_to(root)).replace("\\", "/")
        src = fileio.read_utf8_bytes(f)
        tree = parser.parse(src)

        def visit(node, class_prefix: str):
            if node.type == "class_declaration":
                mods = _modifiers_text(node, src)
                prefix = class_prefix
                if MAPPING_RE.search(mods):
                    m = FIRST_STR_RE.search(mods)
                    if m:
                        prefix = class_prefix + m.group(1)
                for ch in node.children:
                    visit(ch, prefix)
                return
            if node.type == "method_declaration":
                mods = _modifiers_text(node, src)
                if MAPPING_RE.search(mods):
                    m = FIRST_STR_RE.search(mods)
                    path = m.group(1) if m else ""
                    full = normalize_url(class_prefix + path)
                    name = _name_of(node, src)
                    if name and full:
                        routes[full] = f"{rel}::{name}"
                return
            for ch in node.children:
                visit(ch, class_prefix)

        visit(tree.root_node, "")
    return routes


# ─── Frontend HTTP calls ───
def _callee_http_verb(node, src: bytes) -> str | None:
    fn = node.child_by_field_name("function")
    if fn is None:
        return None
    if fn.type == "identifier":
        name = src[fn.start_byte:fn.end_byte].decode("utf-8", "ignore")
        return "request" if name == "fetch" else None
    if fn.type in ("member_expression", "member_access_expression"):
        prop = fn.child_by_field_name("property")
        if prop:
            v = src[prop.start_byte:prop.end_byte].decode("utf-8", "ignore").lower()
            return v if v in HTTP_VERBS else None
    return None


def _first_url_arg(node, src: bytes) -> str | None:
    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    for ch in args.children:
        if ch.type in ("string", "string_fragment"):
            return src[ch.start_byte:ch.end_byte].decode("utf-8", "ignore").strip("'\"`")
        if ch.type == "template_string":
            return src[ch.start_byte:ch.end_byte].decode("utf-8", "ignore").strip("`")
    return None


def extract_frontend_calls(root: Path, files: list[Path]) -> list[tuple[str, str]]:
    """返回 [(调用方 symbol key, 归一化 URL)]。"""
    calls: list[tuple[str, str]] = []
    def_types = {"function_declaration", "method_definition", "class_declaration", "arrow_function"}
    for f in files:
        lang = detect_language(str(f))
        if lang not in ("javascript", "typescript", "tsx", "vue"):
            continue
        rel = str(f.relative_to(root)).replace("\\", "/")
        raw = fileio.read_text(f)
        if lang == "vue":
            script, script_lang, _ = _extract_script_from_vue(raw)
            if not script.strip():
                continue
            parse_lang, source = script_lang, script
        else:
            parse_lang, source = ("typescript" if lang in ("typescript", "tsx") else "javascript"), raw
        parser = _parser(parse_lang)
        if not parser:
            continue
        src = source.encode("utf-8")
        tree = parser.parse(src)

        def visit(node, enclosing: str):
            cur = enclosing
            if node.type in def_types:
                n = node.child_by_field_name("name")
                if n:
                    cur = src[n.start_byte:n.end_byte].decode("utf-8", "ignore")
            if node.type == "call_expression" and _callee_http_verb(node, src):
                url = _first_url_arg(node, src)
                if url:
                    nurl = normalize_url(url)
                    if nurl.startswith("/"):
                        calls.append((f"{rel}::{cur or 'module'}", nurl))
            for ch in node.children:
                visit(ch, cur)

        visit(tree.root_node, "")
    return calls


def build_api_edges(routes: dict[str, str], calls: list[tuple[str, str]]) -> list[dict]:
    edges: list[dict] = []
    for caller_key, url in calls:
        target = routes.get(url)
        if target:
            edges.append({"src": caller_key, "dst": target, "type": "CALLS_API", "confidence": 0.6})
    return edges


# ─── 文件级依赖(DEPENDS_ON) ───
_JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".vue")
_JAVA_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(\.\*)?\s*;", re.M)
_JS_FROM = re.compile(r"""from\s*['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")


def _resolve_js(importer_rel: str, spec: str, fileset: set[str]) -> str | None:
    if not spec.startswith("."):  # 裸包 / 别名(@/…)无法可靠解析,跳过
        return None
    base = posixpath.normpath(posixpath.join(posixpath.dirname(importer_rel), spec))
    cands: list[str] = []
    if any(base.endswith(e) for e in _JS_EXTS):
        cands.append(base)
    cands += [base + e for e in _JS_EXTS]
    cands += [base + "/index" + e for e in _JS_EXTS]
    for c in cands:
        if c in fileset:
            return c
    return None


def extract_file_deps(root: Path, files: list[Path]):
    """返回 (file 节点列表, DEPENDS_ON 边列表)。Java 按 FQN 解析,JS/TS/Vue 按相对路径解析。"""
    file_text: dict[str, tuple[str, str]] = {}
    java_fqn: dict[str, str] = {}
    fileset: set[str] = set()

    for f in files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        lang = detect_language(rel)
        if lang not in ("java", "javascript", "typescript", "tsx", "vue"):
            continue
        try:
            txt = fileio.read_text(f)
        except OSError:
            continue
        fileset.add(rel)
        file_text[rel] = (lang, txt)
        if lang == "java":
            m = _JAVA_PKG.search(txt)
            pkg = m.group(1) if m else ""
            stem = rel.rsplit("/", 1)[-1][:-5]  # 去掉 .java
            java_fqn[f"{pkg}.{stem}" if pkg else stem] = rel

    edges: dict[tuple, float] = {}
    nodes: set[str] = set()

    def add(src: str, dst: str, conf: float) -> None:
        if src == dst or dst not in fileset:
            return
        nodes.update((src, dst))
        k = (src, dst)
        if k not in edges or conf > edges[k]:
            edges[k] = conf

    for rel, (lang, txt) in file_text.items():
        if lang == "java":
            for m in _JAVA_IMPORT.finditer(txt):
                fqn, wild = m.group(1), m.group(2)
                if wild:  # import x.y.*; 通配,逐个连该包下已知类
                    prefix = fqn + "."
                    for ofqn, orel in java_fqn.items():
                        if ofqn.startswith(prefix) and "." not in ofqn[len(prefix):]:
                            add(rel, orel, 0.8)
                    continue
                tgt = java_fqn.get(fqn)
                if tgt:
                    add(rel, tgt, 0.9)
        else:
            for m in _JS_FROM.finditer(txt):
                tgt = _resolve_js(rel, m.group(1), fileset)
                if tgt:
                    add(rel, tgt, 0.85)
            for m in _JS_REQUIRE.finditer(txt):
                tgt = _resolve_js(rel, m.group(1), fileset)
                if tgt:
                    add(rel, tgt, 0.85)

    file_symbols = [
        {"key": r, "name": r.rsplit("/", 1)[-1], "kind": "file", "file": r, "line": 1}
        for r in nodes
    ]
    dep_edges = [
        {"src": s, "dst": d, "type": "DEPENDS_ON", "confidence": c} for (s, d), c in edges.items()
    ]
    return file_symbols, dep_edges


# ─── MyBatis mapper XML ───
def extract_mybatis(root: Path, files: list[Path], name_to_keys: dict[str, list[str]]):
    """返回 (xml statement 节点列表, 边列表)。
    namespace 末段类名 + 接口方法名 匹配到已有方法 symbol。
    """
    symbols: list[dict] = []
    edges: list[dict] = []
    for f in files:
        if detect_language(str(f)) != "xml":
            continue
        rel = str(f.relative_to(root)).replace("\\", "/")
        try:
            txt = fileio.read_text(f)
        except OSError:
            continue
        if "<mapper" not in txt or "namespace" not in txt:
            continue  # 非 MyBatis mapper
        try:
            xroot = ET.fromstring(txt)
        except ET.ParseError:
            continue
        namespace = xroot.attrib.get("namespace", "")
        if not namespace:
            continue
        iface_simple = namespace.split(".")[-1]
        for stmt in xroot:
            tag = stmt.tag.lower()
            if tag not in ("select", "insert", "update", "delete"):
                continue
            sid = stmt.attrib.get("id")
            if not sid:
                continue
            sql_key = f"{rel}::{sid}"
            symbols.append({"key": sql_key, "name": sid, "kind": "sql",
                            "file": rel, "line": 1})
            # 连到接口方法:名字匹配 sid 且其 key 文件名含接口简单名
            for cand in name_to_keys.get(sid, []):
                if iface_simple in cand:
                    edges.append({"src": cand, "dst": sql_key,
                                  "type": "MAPS_TO", "confidence": 0.7})
    return symbols, edges
