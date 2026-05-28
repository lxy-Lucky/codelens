"""扩展名 → 语言,以及 tree-sitter 语法名映射。"""

# 扩展名 → 内部语言标识
EXT_TO_LANG: dict[str, str] = {
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".vue": "vue",
    ".xml": "xml",
    # 后续:".jsp": "jsp",
}

# 内部语言 → tree-sitter-language-pack 语法名
LANG_TO_TS_GRAMMAR: dict[str, str] = {
    "java": "java",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "xml": "xml",
    # vue 走特殊处理(抽取 <script> 后按 ts/js 解析),无独立语法
}

SUPPORTED_EXTS = set(EXT_TO_LANG.keys())


def detect_language(path: str) -> str | None:
    for ext, lang in EXT_TO_LANG.items():
        if path.endswith(ext):
            return lang
    return None
