"""
English text post-processing for game localization.

Handles common issues when translating Chinese to English for game UI:
- Accent/diacritic normalization
- Text length management for UI constraints
- Possessive grammar fixes
- Whitespace and punctuation cleanup
- Formatting tag validation and repair

Extracted patterns from professional MMORPG localization experience.
"""

import re
import unicodedata


# --- Accent / Diacritic Handling ---

def remove_accents(text):
    """
    Remove diacritical marks from text, converting accented characters to ASCII.

    Useful for normalizing AI translations that sometimes introduce accented
    characters not supported by the game's font (e.g. e instead of e).

    Example: "Cafe" -> "Cafe", "naive" -> "naive"
    """
    if not isinstance(text, str):
        return text
    nfkd = unicodedata.normalize('NFD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# --- Text Length Management ---

def break_text_at_spaces(text, max_line_length):
    """
    Break long text into multiple lines at word boundaries.

    For UI elements with maximum line lengths. Breaks at spaces to avoid
    splitting words. Falls back to hard break if no space found.

    Args:
        text: The text to break.
        max_line_length: Maximum characters per line.

    Returns:
        Text with newlines inserted at break points.
    """
    if not isinstance(text, str) or len(text) <= max_line_length:
        return text

    lines = []
    remaining = text
    while len(remaining) > max_line_length:
        # Find last space within the limit
        break_pos = remaining.rfind(' ', 0, max_line_length)
        if break_pos == -1:
            # No space found - hard break
            break_pos = max_line_length
        lines.append(remaining[:break_pos])
        remaining = remaining[break_pos:].lstrip(' ')

    if remaining:
        lines.append(remaining)
    return '\n'.join(lines)


def check_expansion_ratio(chinese, english, warn_threshold=2.0, max_threshold=3.0):
    """
    Check the text expansion ratio from Chinese to English.

    Chinese text is significantly more compact than English. A typical
    expansion ratio is 1.5-2x. Ratios above 2.5x often cause UI overflow.

    Args:
        chinese: Original Chinese text.
        english: Translated English text.
        warn_threshold: Ratio above which to warn (default 2.0).
        max_threshold: Ratio above which text likely overflows UI (default 3.0).

    Returns:
        Tuple of (ratio, severity) where severity is "ok", "warn", or "overflow".
    """
    if not chinese or not english:
        return 0.0, "ok"
    ratio = len(english) / max(len(chinese), 1)
    if ratio > max_threshold:
        return ratio, "overflow"
    elif ratio > warn_threshold:
        return ratio, "warn"
    return ratio, "ok"


# --- Grammar and Punctuation Fixes ---

def fix_possessives(text):
    """
    Fix common English possessive issues from AI translation.

    - "s's" -> "s'" (words ending in s don't need another s)
    - "it's" when possessive should be "its" (not fixable without context, skip)
    """
    if not isinstance(text, str):
        return text
    return re.sub(r"s's\b", "s'", text)


def fix_whitespace(text):
    """
    Normalize whitespace issues common in AI-translated game text.

    - Collapse multiple spaces to single space
    - Remove spaces before punctuation (period, comma, colon, semicolon, !, ?)
    - Remove spaces after opening brackets/parens
    - Remove spaces before closing brackets/parens
    - Trim leading/trailing whitespace per line
    """
    if not isinstance(text, str):
        return text
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    # Remove space before punctuation
    text = re.sub(r' ([.,;:!?%\)\]>])', r'\1', text)
    # Remove space after opening brackets
    text = re.sub(r'([\(\[<]) ', r'\1', text)
    # Trim per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text


def fix_chinese_punctuation(text):
    """
    Replace Chinese punctuation that AI sometimes leaves in English translations.

    Handles: fullwidth comma, period, colon, semicolon, parentheses,
    exclamation, question mark, and Chinese-specific quotes.
    """
    if not isinstance(text, str):
        return text
    replacements = {
        '\uff0c': ', ',    # fullwidth comma
        '\u3002': '. ',    # Chinese period
        '\uff1a': ': ',    # fullwidth colon
        '\uff1b': '; ',    # fullwidth semicolon
        '\uff08': '(',     # fullwidth left paren
        '\uff09': ')',     # fullwidth right paren
        '\uff01': '!',     # fullwidth exclamation
        '\uff1f': '?',     # fullwidth question mark
        '\u3010': '[',     # left black lenticular bracket
        '\u3011': ']',     # right black lenticular bracket
        '\u300a': '"',     # left double angle bracket (book title marks)
        '\u300b': '"',     # right double angle bracket
        '\u201c': '"',     # left double quotation mark (keep or convert)
        '\u201d': '"',     # right double quotation mark
        '\u2018': "'",     # left single quotation mark
        '\u2019': "'",     # right single quotation mark
        '\u2014': ' - ',   # em dash
        '\u2013': '-',     # en dash
        '\u00b7': ' - ',   # middle dot (Chinese name separator)
        '\u30fb': ' - ',   # katakana middle dot
    }
    for chinese_char, english_char in replacements.items():
        text = text.replace(chinese_char, english_char)
    # Clean up double spaces from replacements
    text = re.sub(r' {2,}', ' ', text)
    return text


# --- Formatting Tag Validation ---

def validate_formatting_tags(chinese, english):
    """
    Validate that all formatting tags from the source are preserved in the translation.

    Checks for:
    - XML/HTML-style tags: <tag>, </tag>, </>
    - UE4 format placeholders: {0}, {name}, {1:d}
    - Printf-style: %d, %s, %f, %.2f
    - Custom game tags: [color=...], [/color]

    Returns:
        Tuple of (is_valid, missing_tags) where missing_tags is a list of
        tags present in Chinese but missing from English.
    """
    if not isinstance(chinese, str) or not isinstance(english, str):
        return True, []

    # Collect all tag patterns from source
    tag_patterns = [
        re.compile(r'<[^>]+>'),          # XML/HTML tags
        re.compile(r'</>'),              # Self-closing
        re.compile(r'\{[^}]*\}'),        # UE4 placeholders
        re.compile(r'%[dsfx%]'),         # Printf basic
        re.compile(r'%\.\d+[dsfx]'),     # Printf with precision
        re.compile(r'\[[^\]]+\]'),        # Square bracket tags
    ]

    source_tags = []
    for pattern in tag_patterns:
        source_tags.extend(pattern.findall(chinese))

    missing = [tag for tag in source_tags if tag not in english]
    return len(missing) == 0, missing


def repair_common_tag_issues(text):
    """
    Fix common tag corruption from AI translation.

    AI translators sometimes:
    - Add spaces inside tags: "< />" -> "</>"
    - Translate tag names: "<颜色>" -> should stay as "<color>"
    - Break self-closing tags: "< / >" -> "</>"
    """
    if not isinstance(text, str):
        return text
    # Fix spaced closing tags
    text = re.sub(r'<\s*/\s*>', '</>', text)
    # Fix spaces after < in tags
    text = re.sub(r'<\s+([a-zA-Z_])', r'<\1', text)
    # Fix spaces before > in tags
    text = re.sub(r'([a-zA-Z_/])\s+>', r'\1>', text)
    return text


# --- Full Post-Processing Pipeline ---

def postprocess_translation(chinese, english, max_line_length=None):
    """
    Run the full post-processing pipeline on a single translation.

    Applies all fixes in the correct order:
    1. Repair tag corruption
    2. Fix Chinese punctuation remnants
    3. Fix possessives
    4. Fix whitespace
    5. Remove accents (if font doesn't support them)
    6. Break long lines (if max_line_length specified)

    Args:
        chinese: Original Chinese text (for validation).
        english: Translated English text.
        max_line_length: Optional max chars per line for UI constraints.

    Returns:
        Tuple of (processed_english, warnings) where warnings is a list of
        issue descriptions.
    """
    if not isinstance(english, str):
        return english, []

    warnings = []

    # 1. Repair tags
    processed = repair_common_tag_issues(english)

    # 2. Validate tags survived translation
    tags_ok, missing = validate_formatting_tags(chinese, processed)
    if not tags_ok:
        warnings.append(f"Missing tags: {missing}")

    # 3. Fix leftover Chinese punctuation
    processed = fix_chinese_punctuation(processed)

    # 4. Grammar fixes
    processed = fix_possessives(processed)

    # 5. Whitespace cleanup
    processed = fix_whitespace(processed)

    # 6. Check expansion ratio
    ratio, severity = check_expansion_ratio(chinese, processed)
    if severity == "overflow":
        warnings.append(f"Text expansion {ratio:.1f}x likely overflows UI")
    elif severity == "warn":
        warnings.append(f"Text expansion {ratio:.1f}x may be tight")

    # 7. Line breaking for constrained UI
    if max_line_length and len(processed) > max_line_length:
        processed = break_text_at_spaces(processed, max_line_length)

    return processed, warnings


def postprocess_batch(translated_data, source_data=None, max_line_length=None):
    """
    Post-process an entire translated dataset.

    Args:
        translated_data: dict of {namespace: {key: english_text}}
        source_data: Optional dict of {namespace: {key: chinese_text}} for validation.
        max_line_length: Optional max chars per line.

    Returns:
        Tuple of (processed_data, all_warnings) where all_warnings is a list of
        {namespace, key, warnings} dicts.
    """
    from tqdm import tqdm
    from .utils import contains_chinese_or_cyrillic

    processed = {}
    all_warnings = []

    for namespace, kv_pairs in tqdm(translated_data.items(), desc="Post-processing"):
        processed[namespace] = {}
        if not isinstance(kv_pairs, dict):
            processed[namespace] = kv_pairs
            continue

        for key, english in kv_pairs.items():
            if not isinstance(english, str):
                processed[namespace][key] = english
                continue

            # Get Chinese source for validation (if available)
            chinese = ""
            if source_data:
                chinese = source_data.get(namespace, {}).get(key, "")

            # Skip strings that are still untranslated Chinese
            if contains_chinese_or_cyrillic(english) and chinese:
                processed[namespace][key] = english
                continue

            result, warnings = postprocess_translation(chinese, english, max_line_length)
            processed[namespace][key] = result

            if warnings:
                all_warnings.append({
                    "namespace": namespace,
                    "key": key,
                    "warnings": warnings
                })

    if all_warnings:
        print(f"\n  Post-processing: {len(all_warnings)} strings with warnings")
        tag_issues = sum(1 for w in all_warnings if any("Missing tags" in x for x in w["warnings"]))
        overflow_issues = sum(1 for w in all_warnings if any("overflow" in x for x in w["warnings"]))
        if tag_issues:
            print(f"    Tag issues: {tag_issues}")
        if overflow_issues:
            print(f"    Overflow risks: {overflow_issues}")

    return processed, all_warnings
