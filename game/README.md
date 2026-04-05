# Game English Patch

English translation for the Honor of Kings: World game client.

## Status

The game has not yet launched. The translation infrastructure is set up and ready for when the game becomes available.

## What's Ready

### Shared Dictionary (343K+ entries)
A cross-game Chinese-to-English dictionary extracted from a proven translation project (WOJD) and merged with our launcher translations. This saves significant API costs by pre-translating common UI strings, system messages, and gaming terminology.

### Library Modules (`lib/`)
Reusable Python modules for the translation pipeline:
- **`ue4_locres.py`** - UE4/UE5 .locres binary format tools (CityHash64, CRC32, read/write)
- **`translation_engine.py`** - Multi-strategy translation lookup (exact match, OpenCC S/T conversion, number pattern matching)
- **`gemini_client.py`** - Gemini AI translation client with chunking, glossary injection, and validation
- **`utils.py`** - Common utilities (Chinese character detection, BOM cleaning, sorting)

### Tools (`tools/`)
- **`extract_shared_dictionary.py`** - Extract/rebuild the shared dictionary from WOJD data
- **`import_launcher_translations.py`** - Merge new launcher translations into the shared dictionary

## Structure

```
game/
  config.json                    # Game-specific configuration (placeholders)
  requirements.txt               # Python dependencies
  translations/
    shared_dictionary.json       # 343K Chinese-English pairs (cross-game)
    hokw_map.json                # HoK World-specific translations (empty)
    glossary.json                # Game-specific term control (empty)
  lib/                           # Reusable library modules
  tools/                         # One-time/utility scripts
  pipeline/                      # Translation pipeline scripts (pending)
```

## Setup

```bash
cd game
pip install -r requirements.txt
```

## When the Game Launches

1. Analyze the game client (PAK structure, encryption, UE version)
2. Fill in `config.json` with game-specific values
3. Build pipeline scripts in `pipeline/`
4. Run the pipeline to generate English patch

## Refreshing the Shared Dictionary

To re-extract from WOJD (if WOJD translations have been updated):
```bash
python tools/extract_shared_dictionary.py
```

To merge new launcher translations:
```bash
python tools/import_launcher_translations.py
```
