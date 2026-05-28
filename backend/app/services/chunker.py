"""tree-sitter 语法感知切块:按函数/方法/类边界切,保留符号名与行号。

- Java / JS / TS / TSX:用 tree-sitter 提取定义节点
- Vue:抽取 <script> 块后按 ts/js 解析
- XML:整文件作一块(MyBatis/Spring 配置,后续可按 <select>/<mapper> 细分)
- 解析失败或无语法:退化为按行滑窗
"""
import re
from dataclasses import dataclass

from app.services.languages import LANG_TO_TS_GRAMMAR

# 各语言要捕获为独立 chunk 的定义节点类型
DEF_NODE_TYPES: dict[str, set[str]] = {
    "java": {
        "method_declaration",
        "constructor_declaration",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
    },
    "javascript": {
        "function_declaration",
        "method_definition",
        "class_declaration",
    },
    "typescript": {
        "function_declaration",
        "method_definition",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    },
    "tsx": {
        "function_declaration",
        "method_definition",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    },
}

MAX_CHUNK_LINES = 200  # 超大定义二次切
WINDOW_LINES = 60      # 退化滑窗大小
WINDOW_OVERLAP = 10

# 各语言的注释节点类型(java: line_comment/block_comment;js/ts: comment)
COMMENT_TYPES = {"comment", "line_comment", "block_comment"}


def _leading_comment_start(node) -> tuple[int, int]:
    """向上吞并紧邻的注释兄弟节点,返回 (起始字节, 起始行)。

    允许多条连续注释堆叠(每条与下一块相隔不超过 1 行)。
    """
    start_byte = node.start_byte
    start_row = node.start_point[0]
    cur = node
    while True:
        prev = cur.prev_sibling
        if prev is None or prev.type not in COMMENT_TYPES:
            break
        if start_row - prev.end_point[0] > 1:  # 中间空行过多,不算紧邻
            break
        start_byte = prev.start_byte
        start_row = prev.start_point[0]
        cur = prev
    return start_byte, start_row


@dataclass
class Chunk:
    symbol: str | None
    kind: str            # function | method | class | block
    start_line: int      # 1-based
    end_line: int
    text: str


def _node_name(node, source: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source[name_node.start_byte : name_node.end_byte].decode("utf-8", "ignore")
    # 退而求其次:找第一个 identifier 子节点
    for child in node.children:
        if "identifier" in child.type:
            return source[child.start_byte : child.end_byte].decode("utf-8", "ignore")
    return None


def _kind_of(node_type: str) -> str:
    if "class" in node_type or "interface" in node_type or "enum" in node_type or "record" in node_type:
        return "class"
    if "method" in node_type or "constructor" in node_type:
        return "method"
    return "function"


def _extract_script_from_vue(source: str) -> tuple[str, str, int]:
    """返回 (脚本内容, 语言, 起始行偏移)。"""
    m = re.search(r"<script[^>]*>(.*?)</script>", source, re.DOTALL | re.IGNORECASE)
    if not m:
        return "", "javascript", 0
    script = m.group(1)
    lang = "typescript" if re.search(r'lang=["\']ts', m.group(0), re.IGNORECASE) else "javascript"
    line_offset = source[: m.start(1)].count("\n")
    return script, lang, line_offset


def _window_chunks(source: str, line_offset: int = 0) -> list[Chunk]:
    lines = source.splitlines()
    chunks: list[Chunk] = []
    i = 0
    while i < len(lines):
        window = lines[i : i + WINDOW_LINES]
        if not "".join(window).strip():
            i += WINDOW_LINES - WINDOW_OVERLAP
            continue
        chunks.append(
            Chunk(
                symbol=None,
                kind="block",
                start_line=line_offset + i + 1,
                end_line=line_offset + i + len(window),
                text="\n".join(window),
            )
        )
        i += WINDOW_LINES - WINDOW_OVERLAP
    return chunks


def _ts_chunks(source: str, lang: str, line_offset: int = 0) -> list[Chunk]:
    grammar = LANG_TO_TS_GRAMMAR.get(lang)
    if not grammar:
        return _window_chunks(source, line_offset)
    from app.services.ts import get_parser

    parser = get_parser(grammar)
    if parser is None:
        return _window_chunks(source, line_offset)

    src_bytes = source.encode("utf-8")
    tree = parser.parse(src_bytes)
    targets = DEF_NODE_TYPES.get(lang, set())
    chunks: list[Chunk] = []

    def visit(node) -> None:
        if node.type in targets:
            start = node.start_point[0]
            end = node.end_point[0]
            # 把紧邻在定义上方的注释(Javadoc/行注释)并入 chunk,让中日英文档进入嵌入文本
            c_start_byte, c_start_row = _leading_comment_start(node)
            text = src_bytes[c_start_byte : node.end_byte].decode("utf-8", "ignore")
            chunk = Chunk(
                symbol=_node_name(node, src_bytes),
                kind=_kind_of(node.type),
                start_line=line_offset + c_start_row + 1,
                end_line=line_offset + end + 1,
                text=text,
            )
            # 类太大时,既保留类骨架块,也下钻方法
            if (end - start) > MAX_CHUNK_LINES and chunk.kind == "class":
                chunks.append(chunk)
                for child in node.children:
                    visit(child)
                return
            chunks.append(chunk)
            return
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return chunks if chunks else _window_chunks(source, line_offset)


def chunk_source(source: str, language: str) -> list[Chunk]:
    if not source.strip():
        return []
    if language == "vue":
        script, script_lang, offset = _extract_script_from_vue(source)
        if not script.strip():
            return _window_chunks(source)
        return _ts_chunks(script, script_lang, offset)
    if language == "xml":
        # 整文件一块(超大截断为滑窗)
        if len(source.splitlines()) <= MAX_CHUNK_LINES:
            return [Chunk(symbol=None, kind="block", start_line=1,
                          end_line=len(source.splitlines()) or 1, text=source)]
        return _window_chunks(source)
    return _ts_chunks(source, language)
