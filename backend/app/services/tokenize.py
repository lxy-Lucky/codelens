"""代码感知分词:拆 camelCase / snake_case / 点号,小写化。

findByUsername  -> [findbyusername, find, by, username]
user_repository -> [user_repository, user, repository]
"""
import re

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word in _WORD.findall(text):
        lw = word.lower()
        tokens.append(lw)
        # 拆下划线
        parts = [p for p in word.split("_") if p]
        # 再对每段拆 camelCase
        sub: list[str] = []
        for p in parts:
            sub.extend(_CAMEL.findall(p))
        for s in sub:
            sl = s.lower()
            if sl and sl != lw:
                tokens.append(sl)
    return tokens
