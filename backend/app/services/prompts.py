"""问答 prompt 构建:强制 grounding,只允许引用检索集内的文件/行号。"""
from app.models.schemas import CodeChunkHit

SYSTEM = """你是 CodeLens,一个本地代码库分析助手。规则:
1. 只能基于「提供的代码片段」回答,不要编造不存在的文件名、行号或函数。
2. 引用代码位置时用 `文件路径:起始行` 格式,且必须来自提供的片段。
3. 若提供的片段不足以回答,直接说明「检索到的代码不足以回答」,不要猜测。
4. 用简体中文回答,代码用 Markdown 代码块。"""


def _format_chunks(hits: list[CodeChunkHit]) -> str:
    blocks = []
    for h in hits:
        header = f"// {h.file_path}:{h.start_line}-{h.end_line}"
        if h.symbol:
            header += f"  [{h.kind} {h.symbol}]"
        blocks.append(f"{header}\n{h.snippet}")
    return "\n\n---\n\n".join(blocks)


def build_messages(
    question: str,
    hits: list[CodeChunkHit],
    history: list[dict],
    selected_code: str | None = None,
    selected_file: str | None = None,
) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": SYSTEM}]
    msgs.extend(history[-6:])  # 控制上下文预算:最近 3 轮

    context_parts: list[str] = []
    if selected_code:
        loc = f"(来自 {selected_file})" if selected_file else ""
        context_parts.append(f"【用户当前选中的代码 {loc}】\n{selected_code}")
    if hits:
        context_parts.append(f"【从代码库检索到的相关片段】\n{_format_chunks(hits)}")

    context = "\n\n".join(context_parts) if context_parts else "(无检索结果)"
    user_content = f"{context}\n\n【问题】\n{question}"
    msgs.append({"role": "user", "content": user_content})
    return msgs
