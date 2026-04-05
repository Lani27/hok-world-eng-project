"""
Merge launcher translations into an existing shared dictionary.

Use this when new launcher translations have been added and you want
to update the shared dictionary without re-extracting from WOJD.

Usage:
    python import_launcher_translations.py [--launcher PATH] [--dictionary PATH]
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "..", "launcher", "translations.json")
DEFAULT_DICTIONARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "translations", "shared_dictionary.json")


def main():
    parser = argparse.ArgumentParser(description="Import launcher translations into shared dictionary")
    parser.add_argument("--launcher", default=DEFAULT_LAUNCHER,
                        help="Path to launcher translations.json")
    parser.add_argument("--dictionary", default=DEFAULT_DICTIONARY,
                        help="Path to shared_dictionary.json")
    args = parser.parse_args()

    args.launcher = os.path.normpath(args.launcher)
    args.dictionary = os.path.normpath(args.dictionary)

    # Load existing dictionary
    shared_dict = {}
    if os.path.exists(args.dictionary):
        with open(args.dictionary, 'r', encoding='utf-8-sig') as f:
            shared_dict = json.load(f)
        print(f"Loaded existing dictionary: {len(shared_dict)} entries")
    else:
        print("No existing dictionary found. Creating new one.")

    # Load launcher translations
    if not os.path.exists(args.launcher):
        print(f"ERROR: Launcher translations not found: {args.launcher}")
        sys.exit(1)

    with open(args.launcher, 'r', encoding='utf-8-sig') as f:
        launcher = json.load(f)
    print(f"Loaded launcher translations: {len(launcher)} entries")

    # Merge (launcher takes priority)
    new_count = 0
    updated_count = 0
    for chinese, english in launcher.items():
        if not isinstance(chinese, str) or not isinstance(english, str):
            continue
        if not english.strip():
            continue
        if chinese not in shared_dict:
            new_count += 1
        elif shared_dict[chinese] != english:
            updated_count += 1
        shared_dict[chinese] = english

    # Save
    sorted_dict = dict(sorted(shared_dict.items()))
    os.makedirs(os.path.dirname(args.dictionary), exist_ok=True)
    with open(args.dictionary, 'w', encoding='utf-8') as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)

    print(f"\nMerged: {new_count} new, {updated_count} updated")
    print(f"Total dictionary: {len(sorted_dict)} entries")
    print(f"Saved to: {args.dictionary}")


if __name__ == "__main__":
    main()
