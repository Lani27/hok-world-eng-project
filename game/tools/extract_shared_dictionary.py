"""
Extract a shared Chinese-English dictionary from the WOJD translation map
and merge in launcher translations.

This creates a flat {chinese: english} dictionary that can be reused across
games to avoid re-translating common terms, UI strings, and phrases.

Usage:
    python extract_shared_dictionary.py [--wojd-map PATH] [--launcher PATH] [--output PATH]
"""

import json
import os
import sys
import re
import argparse
from collections import defaultdict, Counter

# Add parent dir to path for lib imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.utils import contains_chinese, count_chinese_chars


# Defaults
DEFAULT_WOJD_MAP = "D:/Games/WOJD/EngPatch/PATCHER/chinese_english_map.json"
DEFAULT_LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "..", "launcher", "translations.json")
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "translations", "shared_dictionary.json")

# Filter thresholds
MAX_TEXT_LENGTH = 500          # Skip very long game-specific paragraphs
MIN_TRANSLATION_LENGTH = 1    # Skip empty translations


def load_wojd_map(path):
    """Load the WOJD namespaced chinese_english_map.json."""
    print(f"Loading WOJD translation map from: {path}")
    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    total = sum(len(v) for v in data.values() if isinstance(v, dict))
    print(f"  Loaded {total} entries across {len(data)} namespaces")
    return data


def load_launcher_translations(path):
    """Load the flat launcher translations.json."""
    print(f"Loading launcher translations from: {path}")
    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} entries")
    return data


def is_valid_entry(chinese, english):
    """Check if a translation pair is valid for the shared dictionary."""
    if not isinstance(chinese, str) or not isinstance(english, str):
        return False
    if not english.strip():
        return False
    if len(english) < MIN_TRANSLATION_LENGTH:
        return False
    if len(chinese) > MAX_TEXT_LENGTH:
        return False
    if not contains_chinese(chinese):
        return False
    # Skip entries that are purely formatting tokens or code
    if chinese.startswith('{') and chinese.endswith('}'):
        return False
    # Skip entries with only whitespace/punctuation in Chinese
    stripped = re.sub(r'[\s\d\W]+', '', chinese)
    if not contains_chinese(stripped) and len(stripped) < 1:
        return False
    return True


def flatten_wojd_map(wojd_map):
    """
    Flatten namespaced WOJD map to {chinese: [list_of_translations]}.

    The WOJD map structure is {namespace: {chinese_or_key: english}}.
    Some keys are UE4 hashes (hex strings), not Chinese text - skip those.
    """
    print("Flattening WOJD map...")
    translations = defaultdict(list)
    skipped_hash_keys = 0
    skipped_invalid = 0

    for namespace, entries in wojd_map.items():
        if not isinstance(entries, dict):
            continue
        for chinese_key, english_value in entries.items():
            # Skip hash-like keys (UE4 GUIDs like "0001F33B4C4DC032A0FCFA9FE06134C9")
            if re.match(r'^[0-9A-Fa-f]{20,}$', chinese_key):
                skipped_hash_keys += 1
                continue

            if is_valid_entry(chinese_key, english_value):
                translations[chinese_key].append(english_value)
            else:
                skipped_invalid += 1

    print(f"  Flattened to {len(translations)} unique Chinese keys")
    print(f"  Skipped {skipped_hash_keys} hash/GUID keys, {skipped_invalid} invalid entries")
    return translations


def deduplicate(translations_map):
    """
    For each Chinese key with multiple translations, pick the most frequent one.

    Returns flat {chinese: english} dict.
    """
    print("Deduplicating translations...")
    result = {}
    multi_translation_count = 0

    for chinese, translation_list in translations_map.items():
        if len(translation_list) == 1:
            result[chinese] = translation_list[0]
        else:
            multi_translation_count += 1
            most_common, count = Counter(translation_list).most_common(1)[0]
            result[chinese] = most_common

    print(f"  {multi_translation_count} Chinese keys had multiple translations (resolved by frequency)")
    return result


def merge_launcher(shared_dict, launcher_dict):
    """
    Merge launcher translations into the shared dictionary.

    Launcher translations are human-curated and take priority over WOJD entries.
    """
    print(f"Merging {len(launcher_dict)} launcher translations...")
    new_count = 0
    override_count = 0

    for chinese, english in launcher_dict.items():
        if not isinstance(chinese, str) or not isinstance(english, str):
            continue
        if not english.strip():
            continue
        if chinese in shared_dict:
            if shared_dict[chinese] != english:
                override_count += 1
            shared_dict[chinese] = english  # Launcher always takes priority
        else:
            shared_dict[chinese] = english
            new_count += 1

    print(f"  Added {new_count} new entries, overrode {override_count} existing")
    return shared_dict


def save_dictionary(shared_dict, output_path):
    """Save the shared dictionary as sorted JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sorted_dict = dict(sorted(shared_dict.items()))

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nSaved shared dictionary to: {output_path}")
    print(f"  {len(sorted_dict)} entries, {size_mb:.1f} MB")


def print_stats(shared_dict):
    """Print statistics about the dictionary."""
    print("\n--- Dictionary Statistics ---")

    # Length distribution
    lengths = [len(k) for k in shared_dict.keys()]
    print(f"  Chinese key lengths: min={min(lengths)}, max={max(lengths)}, avg={sum(lengths)/len(lengths):.1f}")

    # Category breakdown by length
    short = sum(1 for k in shared_dict if count_chinese_chars(k) <= 4)
    medium = sum(1 for k in shared_dict if 5 <= count_chinese_chars(k) <= 20)
    long = sum(1 for k in shared_dict if count_chinese_chars(k) > 20)
    print(f"  Short (1-4 chars): {short}")
    print(f"  Medium (5-20 chars): {medium}")
    print(f"  Long (>20 chars): {long}")

    # Sample entries
    print("\n  Sample entries (short):")
    for i, (k, v) in enumerate(shared_dict.items()):
        if count_chinese_chars(k) <= 4 and i < 10:
            print(f"    {k} -> {v}")


def main():
    parser = argparse.ArgumentParser(description="Extract shared Chinese-English dictionary")
    parser.add_argument("--wojd-map", default=DEFAULT_WOJD_MAP,
                        help="Path to WOJD chinese_english_map.json")
    parser.add_argument("--launcher", default=DEFAULT_LAUNCHER,
                        help="Path to launcher translations.json")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="Output path for shared_dictionary.json")
    parser.add_argument("--no-launcher", action="store_true",
                        help="Skip merging launcher translations")
    args = parser.parse_args()

    # Normalize paths
    args.wojd_map = os.path.normpath(args.wojd_map)
    args.launcher = os.path.normpath(args.launcher)
    args.output = os.path.normpath(args.output)

    print("=== Shared Dictionary Extraction ===\n")

    # Load and flatten WOJD
    wojd_map = load_wojd_map(args.wojd_map)
    translations = flatten_wojd_map(wojd_map)
    shared_dict = deduplicate(translations)

    # Merge launcher translations
    if not args.no_launcher:
        if os.path.exists(args.launcher):
            launcher = load_launcher_translations(args.launcher)
            shared_dict = merge_launcher(shared_dict, launcher)
        else:
            print(f"  Launcher translations not found at: {args.launcher} (skipping)")

    # Save and report
    save_dictionary(shared_dict, args.output)
    print_stats(shared_dict)


if __name__ == "__main__":
    main()
