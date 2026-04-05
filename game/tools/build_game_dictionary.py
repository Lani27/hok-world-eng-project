"""
Build a pruned game-specific dictionary from the shared dictionary.

This is a SETUP TOOL — run it during initial project bring-up after extracting
the game's Chinese strings. It cross-references the 343K-entry shared dictionary
against actual game strings, keeping only entries that match. The output becomes
the permanent working dictionary for the main translation pipeline.

Workflow:
    1. Extract game strings (Stage 0-1 of pipeline)
    2. Run this tool to prune shared_dictionary → hokw_dictionary.json
    3. Review stats, spot-check results
    4. Re-run if extraction changes or new game updates arrive
    5. Once satisfied, hokw_dictionary.json is the pipeline's dictionary

Matching strategies:
    - Exact: dictionary key appears verbatim as a game string
    - Substring: dictionary key appears inside a longer game string
    - Reverse substring: a game string appears inside a longer dictionary key
      (catches partial phrases the game uses from longer dictionary entries)

Always-keep sources (never pruned):
    - HoK official terms (hok_official_terms.json)
    - Launcher translations (always relevant for shared UI)

Usage:
    python build_game_dictionary.py --game-strings PATH [--shared-dict PATH] [--output PATH]
    python build_game_dictionary.py --game-strings extracted/all_strings.txt --dry-run
"""

import json
import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.utils import contains_chinese

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(SCRIPT_DIR)
TRANSLATIONS_DIR = os.path.join(GAME_DIR, "translations")

DEFAULT_SHARED_DICT = os.path.join(TRANSLATIONS_DIR, "shared_dictionary.json")
DEFAULT_HOK_TERMS = os.path.join(TRANSLATIONS_DIR, "hok_official_terms.json")
DEFAULT_LAUNCHER = os.path.normpath(os.path.join(GAME_DIR, "..", "launcher", "translations.json"))
DEFAULT_OUTPUT = os.path.join(TRANSLATIONS_DIR, "hokw_dictionary.json")

# Matching config
MIN_SUBSTRING_LENGTH = 4   # Minimum Chinese chars for substring matching (avoids noise)
MIN_REVERSE_LENGTH = 4     # Minimum game string length to match inside a dict key


def load_game_strings(path):
    """Load game strings from a file.

    Supports:
        - .json: expects one of:
            - {namespace: {key: chinese_text}} — unified pipeline format (Stage 2 output)
            - {chinese: english} — flat dictionary format
            - [list of strings]
        - .txt/.csv: one string per line (blank lines skipped)

    For the unified pipeline format {ns: {key: cn_text}}, only the VALUES
    are collected (the keys are internal locres identifiers, not Chinese).
    """
    print(f"Loading game strings from: {path}")
    ext = os.path.splitext(path)[1].lower()

    strings = set()

    if ext == ".json":
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if isinstance(data, list):
            strings = {s for s in data if isinstance(s, str) and contains_chinese(s)}
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    # Nested {namespace: {key: chinese_text}} — unified format
                    # Keys are locres identifiers, values are the Chinese strings
                    for inner_val in value.values():
                        if isinstance(inner_val, str) and contains_chinese(inner_val):
                            strings.add(inner_val)
                else:
                    # Flat {chinese: english} — collect Chinese keys
                    if isinstance(key, str) and contains_chinese(key):
                        strings.add(key)
    else:
        # Plain text, one string per line
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and contains_chinese(line):
                    strings.add(line)

    print(f"  Loaded {len(strings):,} unique Chinese strings from game")
    return strings


def load_always_keep_keys(hok_terms_path, launcher_path):
    """Load Chinese keys that should never be pruned."""
    keep = set()

    if os.path.exists(hok_terms_path):
        with open(hok_terms_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        keep.update(data.keys())
        print(f"  Always-keep: {len(data):,} HoK official terms")

    if os.path.exists(launcher_path):
        with open(launcher_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        # Launcher translations.json is {cn: en}
        keep.update(k for k in data.keys() if contains_chinese(k))
        print(f"  Always-keep: {len(data):,} launcher translations")

    print(f"  Total always-keep keys: {len(keep):,}")
    return keep


def match_dictionary(shared_dict, game_strings, always_keep):
    """Cross-reference shared dictionary against game strings.

    Returns (matched_dict, stats) where matched_dict contains only entries
    that are used by the game or are in the always-keep set.

    Performance notes:
        - Exact match is O(1) per entry (set lookup)
        - Substring matching is O(dict_size × game_strings) worst case
        - With 343K dict entries and ~50K game strings, substring matching
          can take several minutes. Use --no-substring for fast exact-only mode.
    """
    matched = {}
    stats = {
        "exact": 0,
        "substring_of_game": 0,    # dict key found inside a game string
        "game_substring_of_dict": 0,  # game string found inside a dict key
        "always_keep": 0,
        "pruned": 0,
    }

    game_set = game_strings  # already a set

    # For substring matching, pre-filter game strings by minimum length
    game_strings_for_sub = [gs for gs in game_strings if len(gs) > MIN_SUBSTRING_LENGTH]
    game_strings_for_rev = [gs for gs in game_strings if len(gs) >= MIN_REVERSE_LENGTH]

    total = len(shared_dict)
    checked = 0
    last_pct = -1

    for cn_key, en_val in shared_dict.items():
        checked += 1
        pct = (checked * 100) // total
        if pct != last_pct and pct % 10 == 0:
            print(f"  Matching... {pct}%", end="\r")
            last_pct = pct

        # 1. Always-keep sources
        if cn_key in always_keep:
            matched[cn_key] = en_val
            stats["always_keep"] += 1
            continue

        # 2. Exact match — dict key is a game string
        if cn_key in game_set:
            matched[cn_key] = en_val
            stats["exact"] += 1
            continue

        # 3. Substring match — dict key appears inside a longer game string
        #    Useful for: dictionary has "攻击力" and game has "提升攻击力20%"
        if len(cn_key) >= MIN_SUBSTRING_LENGTH:
            found = False
            for gs in game_strings_for_sub:
                if len(gs) > len(cn_key) and cn_key in gs:
                    matched[cn_key] = en_val
                    stats["substring_of_game"] += 1
                    found = True
                    break
            if found:
                continue

        # 4. Reverse substring — a game string appears inside this dict key
        #    Useful for: game has "暴击伤害" and dict has "暴击伤害提升30%"
        #    Only matches when the game string is substantial (>= MIN_REVERSE_LENGTH)
        #    to avoid keeping entries just because they share a common 2-char word.
        if len(cn_key) > MIN_REVERSE_LENGTH:
            found = False
            for gs in game_strings_for_rev:
                if len(gs) < len(cn_key) and gs in cn_key:
                    matched[cn_key] = en_val
                    stats["game_substring_of_dict"] += 1
                    found = True
                    break
            if found:
                continue

        stats["pruned"] += 1

    print(f"  Matching... done.      ")
    return matched, stats


def main():
    parser = argparse.ArgumentParser(
        description="Build pruned game dictionary from shared dictionary + game strings"
    )
    parser.add_argument(
        "--game-strings", required=True,
        help="Path to extracted game strings (.json or .txt)"
    )
    parser.add_argument(
        "--shared-dict", default=DEFAULT_SHARED_DICT,
        help=f"Path to shared dictionary (default: {DEFAULT_SHARED_DICT})"
    )
    parser.add_argument(
        "--hok-terms", default=DEFAULT_HOK_TERMS,
        help=f"Path to HoK official terms (default: {DEFAULT_HOK_TERMS})"
    )
    parser.add_argument(
        "--launcher", default=DEFAULT_LAUNCHER,
        help=f"Path to launcher translations (default: {DEFAULT_LAUNCHER})"
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show stats without writing output file"
    )
    parser.add_argument(
        "--no-substring", action="store_true",
        help="Disable substring matching (exact + always-keep only)"
    )
    parser.add_argument(
        "--update-config", action="store_true",
        help="Update config.json to point shared_dictionary at the pruned output"
    )

    args = parser.parse_args()

    if not os.path.exists(args.game_strings):
        print(f"Error: Game strings file not found: {args.game_strings}")
        sys.exit(1)

    if not os.path.exists(args.shared_dict):
        print(f"Error: Shared dictionary not found: {args.shared_dict}")
        sys.exit(1)

    print("=" * 60)
    print("HoK World — Game Dictionary Builder")
    print("=" * 60)
    print()

    # Load inputs
    game_strings = load_game_strings(args.game_strings)
    always_keep = load_always_keep_keys(args.hok_terms, args.launcher)

    print(f"\nLoading shared dictionary: {args.shared_dict}")
    with open(args.shared_dict, "r", encoding="utf-8-sig") as f:
        shared_dict = json.load(f)
    print(f"  Shared dictionary entries: {len(shared_dict):,}")

    if args.no_substring:
        print("\n  Substring matching: DISABLED (exact + always-keep only)")

    # Match
    print()
    start = time.time()

    if args.no_substring:
        # Fast path: exact match only
        matched = {}
        stats = {"exact": 0, "substring_of_game": 0, "game_substring_of_dict": 0,
                 "always_keep": 0, "pruned": 0}
        game_set = game_strings
        for cn_key, en_val in shared_dict.items():
            if cn_key in always_keep:
                matched[cn_key] = en_val
                stats["always_keep"] += 1
            elif cn_key in game_set:
                matched[cn_key] = en_val
                stats["exact"] += 1
            else:
                stats["pruned"] += 1
    else:
        matched, stats = match_dictionary(shared_dict, game_strings, always_keep)

    elapsed = time.time() - start

    # Sort output for stable diffs
    sorted_matched = dict(sorted(matched.items()))

    # Stats
    print()
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"  Game strings loaded:      {len(game_strings):>10,}")
    print(f"  Shared dictionary size:   {len(shared_dict):>10,}")
    print(f"  ---")
    print(f"  Exact matches:            {stats['exact']:>10,}")
    print(f"  Substring (key in game):  {stats['substring_of_game']:>10,}")
    print(f"  Substring (game in key):  {stats['game_substring_of_dict']:>10,}")
    print(f"  Always-keep (protected):  {stats['always_keep']:>10,}")
    print(f"  Pruned (unused):          {stats['pruned']:>10,}")
    print(f"  ---")
    total_kept = len(sorted_matched)
    reduction = (1 - total_kept / len(shared_dict)) * 100 if shared_dict else 0
    print(f"  Final dictionary size:    {total_kept:>10,}")
    print(f"  Reduction:                {reduction:>9.1f}%")
    print(f"  Time:                     {elapsed:>9.1f}s")

    if args.dry_run:
        print(f"\n  [DRY RUN] No file written.")
    else:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(sorted_matched, f, ensure_ascii=False, indent=2)
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f"\n  Written to: {args.output}")
        print(f"  File size:  {size_mb:.1f} MB")

        # Optionally update config.json to use pruned dictionary
        if args.update_config:
            config_path = os.path.join(GAME_DIR, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                rel_output = os.path.relpath(args.output, GAME_DIR).replace("\\", "/")
                old_path = config.get("paths", {}).get("shared_dictionary", "")
                config["paths"]["shared_dictionary"] = f"./{rel_output}"
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                print(f"\n  config.json updated:")
                print(f"    shared_dictionary: {old_path} → ./{rel_output}")
                print(f"    (Pipeline Stage 3 will now use the pruned dictionary)")
            else:
                print(f"\n  WARNING: config.json not found at {config_path}")

    print()


if __name__ == "__main__":
    main()
