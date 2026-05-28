"""多语言代码感知分词:ASCII 标识符子词 + CJK 字符 bigram(中日韩统一,无需语言检测)。

- 英文/代码:拆 camelCase / snake_case
    findByUsername  -> [findbyusername, find, by, username]
    user_repository -> [user_repository, user, repository]
- CJK(中文汉字 / 日文汉字+假名 / 韩文):相邻字符切 2-gram
    字符串判空 -> [字符, 符串, 串判, 判空]
    文字列が空 -> [文字, 字列, 列が, が空]
  query 与语料用同一套规则,天然可匹配(Lucene CJKAnalyzer 同思路)。
"""
import re

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")

# CJK 字符区间:统一表意文字 + 扩展A + 平假名 + 片假名 + 韩文音节
_CJK = (
    "一-鿿"  # CJK Unified Ideographs(中文/日文汉字)
    "㐀-䶿"  # CJK Ext A
    "぀-ゟ"  # Hiragana
    "゠-ヿ"  # Katakana
    "가-힯"  # Hangul Syllables
)
_CJK_RUN = re.compile(f"[{_CJK}]+")


def _cjk_bigrams(run: str) -> list[str]:
    if len(run) == 1:
        return [run]
    return [run[i : i + 2] for i in range(len(run) - 1)]


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    # ASCII 标识符 + 子词
    for word in _WORD.findall(text):
        lw = word.lower()
        tokens.append(lw)
        parts = [p for p in word.split("_") if p]
        sub: list[str] = []
        for p in parts:
            sub.extend(_CAMEL.findall(p))
        for s in sub:
            sl = s.lower()
            if sl and sl != lw:
                tokens.append(sl)
    # CJK bigram
    for run in _CJK_RUN.findall(text):
        tokens.extend(_cjk_bigrams(run))
    return tokens
