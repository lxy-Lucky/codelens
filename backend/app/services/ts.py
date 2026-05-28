"""tree-sitter parser 工厂:线程本地缓存。

tree-sitter 的 Parser 是 unsendable(不能跨线程释放)。我们用 asyncio.to_thread
在线程池里跑解析,若用 language-pack 的模块级缓存会出现「Parser 在另一线程被 drop」崩溃。
这里按线程各自持有 parser:同线程创建、同线程释放,彻底规避。
"""
import threading
from concurrent.futures import ThreadPoolExecutor

_local = threading.local()

# 全应用唯一的「解析线程」:所有 tree-sitter 解析+索引嵌入都在此单线程执行,
# 保证 unsendable 的 Parser 全程同线程创建/复用/释放。索引/构图本就串行,无吞吐损失。
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="codelens-ts")


def get_parser(grammar: str):
    """返回当前线程专属的 Parser;无对应语法或加载失败返回 None。"""
    cache = getattr(_local, "parsers", None)
    if cache is None:
        cache = {}
        _local.parsers = cache
    if grammar in cache:
        return cache[grammar]

    parser = None
    try:
        from tree_sitter import Parser
        from tree_sitter_language_pack import get_language

        lang = get_language(grammar)
        try:
            parser = Parser(lang)            # tree-sitter >= 0.22
        except TypeError:
            parser = Parser()                # 旧 API 回退
            parser.set_language(lang)
    except Exception:
        parser = None

    cache[grammar] = parser
    return parser
