"""文件读取:自动检测编码(支持 cp932/gb2312 等非 UTF-8 源码),避免乱码。

tree-sitter 假定 UTF-8,所以解析前统一把内容重新编码成 UTF-8 字节。
"""
from pathlib import Path


def detect_encoding(raw: bytes) -> str:
    """检测文件编码,返回编码名称字符串。ASCII 升级为 utf-8。"""
    for encoding in ("utf-8", "cp932", "gb2312", "cp1252", "latin-1"):
        try:
            raw.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def decode_bytes(raw: bytes) -> str:
    return raw.decode(detect_encoding(raw), errors="replace")


def read_text(path: Path) -> str:
    return decode_bytes(path.read_bytes())


def read_utf8_bytes(path: Path) -> bytes:
    """按检测编码解码后重新编码为 UTF-8 字节,供 tree-sitter 解析(其按字节偏移取文本)。"""
    return decode_bytes(path.read_bytes()).encode("utf-8")
