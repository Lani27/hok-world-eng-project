"""
Translation engine with multi-strategy lookup.

Supports exact match, OpenCC simplified/traditional Chinese conversion,
and pattern matching with number extraction for reusing existing translations.
Extracted and generalized from the WOJD translation pipeline.
"""

import re
import json
from collections import defaultdict

from .utils import contains_chinese_or_cyrillic

# Lazy imports for optional dependencies
_opencc_loaded = False
_s2t_converter = None
_t2s_converter = None


def _ensure_opencc():
    """Lazily initialize OpenCC converters."""
    global _opencc_loaded, _s2t_converter, _t2s_converter
    if not _opencc_loaded:
        try:
            import opencc
            _s2t_converter = opencc.OpenCC('s2t')
            _t2s_converter = opencc.OpenCC('t2s')
        except ImportError:
            print("WARNING: opencc-python-reborn not installed. S/T conversion disabled.")
        _opencc_loaded = True


class TranslationEngine:
    """
    Multi-strategy translation lookup engine.

    Lookup chain:
    1. Exact match in game-specific map (namespace-aware)
    2. Exact match in shared dictionary (flat)
    3. OpenCC simplified <-> traditional conversion + lookup
    4. Pattern match with number/placeholder extraction
    """

    def __init__(self, strip_tags=None):
        """
        Args:
            strip_tags: Optional list of tag patterns to strip during pattern normalization.
                        Defaults to empty. Example: ['<RTP_Default></>']
        """
        self._shared_dict = {}       # flat {chinese: english}
        self._game_map = {}          # namespaced {ns: {chinese: english}}
        self._index = None           # pre-computed lookup index
        self._pattern_cache = {}
        self._conversion_cache = {}
        self._cross_ns_cache = {}
        self._stats = defaultdict(int)
        self._strip_tags = strip_tags or []
        self._expansion_warnings = []  # tracks text expansion ratio issues

    def load_shared_dictionary(self, path):
        """Load a flat Chinese-English shared dictionary."""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                self._shared_dict = json.load(f)
            print(f"Loaded shared dictionary: {len(self._shared_dict)} entries from '{path}'")
        except FileNotFoundError:
            print(f"INFO: Shared dictionary not found at '{path}'. Starting empty.")
        except Exception as e:
            print(f"ERROR loading shared dictionary: {e}")

    def load_game_map(self, path):
        """Load a namespaced game-specific translation map."""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                self._game_map = json.load(f)
            total = sum(len(v) for v in self._game_map.values() if isinstance(v, dict))
            print(f"Loaded game map: {total} entries across {len(self._game_map)} namespaces from '{path}'")
        except FileNotFoundError:
            print(f"INFO: Game map not found at '{path}'. Starting empty.")
        except Exception as e:
            print(f"ERROR loading game map: {e}")

    def translate(self, text, namespace=""):
        """
        Attempt to translate a Chinese string using all available strategies.

        Args:
            text: Chinese text to translate.
            namespace: Optional namespace for namespace-specific lookups.

        Returns:
            Tuple of (translation, method) where method describes how it was found,
            or (None, None) if no translation available.
        """
        if not isinstance(text, str) or not text:
            return None, None

        if not contains_chinese_or_cyrillic(text):
            return None, None

        # Strategy 1: Exact match in game map (namespace-specific)
        ns_dict = self._game_map.get(namespace)
        if ns_dict and isinstance(ns_dict, dict):
            trans = ns_dict.get(text)
            if isinstance(trans, str) and trans:
                self._stats["game_map_exact"] += 1
                return trans, "game_map_exact"

        # Strategy 2: Exact match in shared dictionary
        trans = self._shared_dict.get(text)
        if isinstance(trans, str) and trans:
            self._stats["shared_dict_exact"] += 1
            return trans, "shared_dict_exact"

        # Strategy 3: Cross-namespace lookup in game map
        if text in self._cross_ns_cache:
            cached = self._cross_ns_cache[text]
            if cached[0] is not None:
                self._stats["game_map_cross_ns"] += 1
                return cached
        else:
            normalized = self._normalize_for_pattern(text)
            for ns, ns_dict in self._game_map.items():
                if not isinstance(ns_dict, dict) or ns == namespace:
                    continue
                # Try both raw and normalized text
                trans = ns_dict.get(text) or ns_dict.get(normalized)
                if isinstance(trans, str) and trans:
                    self._cross_ns_cache[text] = (trans, "game_map_cross_ns")
                    self._stats["game_map_cross_ns"] += 1
                    return trans, "game_map_cross_ns"

        # Strategy 4: OpenCC S/T conversion + lookup
        _ensure_opencc()
        if _s2t_converter and _t2s_converter:
            traditional, simplified = self._get_opencc_conversions(text)
            for variant in [traditional, simplified]:
                if variant != text:
                    # Check shared dict
                    trans = self._shared_dict.get(variant)
                    if isinstance(trans, str) and trans:
                        self._stats["opencc_shared"] += 1
                        return trans, "opencc_shared"
                    # Check all game map namespaces
                    for ns_dict in self._game_map.values():
                        if isinstance(ns_dict, dict):
                            trans = ns_dict.get(variant)
                            if isinstance(trans, str) and trans:
                                self._stats["opencc_game_map"] += 1
                                return trans, "opencc_game_map"

        # Strategy 5: Pattern match (number extraction)
        result = self._pattern_match(text)
        if result:
            self._stats["pattern_match"] += 1
            return result, "pattern_match"

        self._cross_ns_cache[text] = (None, None)
        self._stats["not_found"] += 1
        return None, None

    def translate_batch(self, unified_data):
        """
        Translate a full unified data structure (namespaced).

        Args:
            unified_data: dict of {namespace: {key: chinese_text}}

        Returns:
            Tuple of (translated_data, untranslated) where both are
            {namespace: {key: text}} dicts.
        """
        from tqdm import tqdm

        translated = {}
        untranslated = defaultdict(dict)
        self._stats.clear()
        self._cross_ns_cache.clear()
        self._pattern_cache.clear()

        for namespace, kv_pairs in tqdm(unified_data.items(), desc="Translating"):
            translated[namespace] = {}
            if not isinstance(kv_pairs, dict):
                translated[namespace] = kv_pairs
                continue

            for key, value in kv_pairs.items():
                if not isinstance(value, str):
                    translated[namespace][key] = value
                    continue

                self._stats["total"] += 1

                if not contains_chinese_or_cyrillic(value):
                    translated[namespace][key] = value
                    self._stats["skipped_no_cjk"] += 1
                    continue

                trans, method = self.translate(value, namespace)
                if trans:
                    translated[namespace][key] = trans
                    # Track text expansion ratio for UI overflow detection
                    ratio = len(trans) / max(len(value), 1)
                    if ratio > 2.5:
                        self._expansion_warnings.append({
                            "namespace": namespace,
                            "key": key,
                            "chinese": value[:80],
                            "english": trans[:80],
                            "ratio": round(ratio, 2)
                        })
                else:
                    translated[namespace][key] = value
                    untranslated[namespace][value] = ""

        self._print_stats()
        if self._expansion_warnings:
            print(f"\n  WARNING: {len(self._expansion_warnings)} translations exceed 2.5x expansion ratio")
            for w in self._expansion_warnings[:5]:
                print(f"    [{w['ratio']}x] {w['chinese'][:40]}... -> {w['english'][:40]}...")
        return translated, dict(untranslated)

    def build_glossary(self, min_chars=2, max_chars=8):
        """
        Build a glossary of short, frequently-used terms for AI translation context.

        Scans both the shared dictionary and game map for short Chinese terms
        (likely proper nouns, skill names, item names).

        Returns:
            dict of {chinese_term: english_translation}
        """
        from collections import Counter
        from .utils import count_chinese_chars

        term_translations = defaultdict(list)

        # From shared dictionary
        for chinese, english in self._shared_dict.items():
            if not isinstance(english, str) or not english.strip():
                continue
            cn_count = count_chinese_chars(chinese)
            if min_chars <= cn_count <= max_chars:
                if '<' not in chinese and '\n' not in chinese and '{' not in chinese:
                    term_translations[chinese].append(english)

        # From game map
        for ns, entries in self._game_map.items():
            if not isinstance(entries, dict):
                continue
            for chinese, english in entries.items():
                if not isinstance(english, str) or not english.strip():
                    continue
                cn_count = count_chinese_chars(chinese)
                if min_chars <= cn_count <= max_chars:
                    if '<' not in chinese and '\n' not in chinese and '{' not in chinese:
                        term_translations[chinese].append(english)

        # Pick most frequent translation for each term
        glossary = {}
        for term, translations in term_translations.items():
            most_common, _ = Counter(translations).most_common(1)[0]
            glossary[term] = most_common

        print(f"Built glossary: {len(glossary)} terms")
        return glossary

    def get_stats(self):
        """Return translation statistics."""
        return dict(self._stats)

    # --- Internal helpers ---

    def _normalize_for_pattern(self, text):
        """Normalize text for pattern key matching."""
        if not isinstance(text, str):
            return text
        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        for tag in self._strip_tags:
            normalized = normalized.replace(tag, '')
        normalized = re.sub(r'\n{2,}', '\n', normalized)
        return normalized.strip()

    def _extract_number_pattern(self, text):
        """Extract a pattern key and numbers from text for pattern-based matching."""
        if not isinstance(text, str):
            return None, []
        if text in self._pattern_cache:
            return self._pattern_cache[text]

        normalized = self._normalize_for_pattern(text)
        number_re = r'[\d]+(?:\.[\d]+)?%?'
        numbers = re.findall(number_re, text)
        pattern_key = re.sub(number_re, '{}', normalized)

        result = (pattern_key, numbers)
        self._pattern_cache[text] = result
        return result

    def _get_opencc_conversions(self, text):
        """Get traditional and simplified variants of text."""
        if text in self._conversion_cache:
            return self._conversion_cache[text]
        try:
            traditional = _s2t_converter.convert(text)
            simplified = _t2s_converter.convert(text)
            result = (traditional, simplified)
        except Exception:
            result = (text, text)
        self._conversion_cache[text] = result
        return result

    def _pattern_match(self, text):
        """Try to find a translation by matching number patterns."""
        input_pattern, input_numbers = self._extract_number_pattern(text)
        if not input_pattern or not input_numbers:
            return None

        # Search shared dict
        for chinese, english in self._shared_dict.items():
            if not isinstance(english, str) or not english:
                continue
            candidate_pattern, candidate_numbers = self._extract_number_pattern(chinese)
            if candidate_pattern == input_pattern and len(candidate_numbers) == len(input_numbers):
                adapted = self._replace_numbers(text, chinese, english)
                if adapted:
                    return adapted

        # Search game map
        for ns_dict in self._game_map.values():
            if not isinstance(ns_dict, dict):
                continue
            for chinese, english in ns_dict.items():
                if not isinstance(english, str) or not english:
                    continue
                candidate_pattern, candidate_numbers = self._extract_number_pattern(chinese)
                if candidate_pattern == input_pattern and len(candidate_numbers) == len(input_numbers):
                    adapted = self._replace_numbers(text, chinese, english)
                    if adapted:
                        return adapted

        return None

    def _replace_numbers(self, original, template_chinese, template_english):
        """Replace numbers in a template translation with numbers from the original."""
        _, orig_numbers = self._extract_number_pattern(original)
        _, template_numbers = self._extract_number_pattern(template_chinese)
        _, trans_numbers = self._extract_number_pattern(template_english)

        if len(orig_numbers) != len(template_numbers) or len(orig_numbers) != len(trans_numbers):
            return None

        result = template_english
        for old_num, new_num in zip(trans_numbers, orig_numbers):
            result = re.sub(r'\b' + re.escape(old_num) + r'\b', new_num, result, count=1)
        return result

    def _print_stats(self):
        """Print translation statistics."""
        print("\n--- Translation Summary ---")
        for key, value in sorted(self._stats.items()):
            print(f"  {key.replace('_', ' ').capitalize()}: {value}")
