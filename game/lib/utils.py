"""Common utility functions for the HoK World translation pipeline."""

import re


# CJK Unified Ideographs + extensions + compatibility ideographs
_CHINESE_REGEX = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff'
    r'\U00020000-\U0002A6DF\U0002A700-\U0002B73F'
    r'\U0002B740-\U0002B81F\U0002B820-\U0002CEAF'
    r'\U0002CEB0-\U0002EBEF\U0002EBF0-\U0002EE5F'
    r'\U00030000-\U0003134F\U00031350-\U000323AF'
    r'\U0002F800-\U0002FA1F]'
)

_CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

_CYRILLIC_REGEX = re.compile(r'[\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F]')


def contains_chinese(text):
    """Check if text contains any Chinese characters."""
    if not isinstance(text, str):
        return False
    return bool(_CHINESE_REGEX.search(text))


def contains_chinese_or_cyrillic(text):
    """Check if text contains Chinese or Cyrillic characters."""
    if not isinstance(text, str):
        return False
    return bool(_CHINESE_REGEX.search(text) or _CYRILLIC_REGEX.search(text))


def count_chinese_chars(text):
    """Count the number of CJK characters in a string."""
    return len(_CHINESE_CHAR_RE.findall(text))


def clean_key_bom(key_str):
    """Remove BOM character from the start of a string."""
    if isinstance(key_str, str) and key_str.startswith('\ufeff'):
        return key_str[1:]
    return key_str


def normalize_line_endings(text):
    """Normalize all line endings to \\n."""
    if not isinstance(text, str):
        return ""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def normalize_line_endings_for_hash(text):
    """Normalize line endings for UE4 hash calculation (\\n -> \\r\\n)."""
    if not isinstance(text, str):
        return ""
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')


def natural_sort_key(s):
    """Sort key that handles embedded numbers naturally (e.g. 'item2' < 'item10')."""
    if not isinstance(s, str):
        return [s]
    cleaned = clean_key_bom(s)
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'([0-9]+)', cleaned)]


def get_json_size(data):
    """Estimate the byte size of a JSON-serializable dict."""
    import json
    try:
        return len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    except Exception:
        return float('inf')
