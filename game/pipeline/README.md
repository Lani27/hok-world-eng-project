# Translation Pipeline

This directory will contain the numbered pipeline scripts for translating HoK World game files to English. The pipeline follows the same proven approach used by the WOJD English Patch.

## Planned Pipeline Stages

### Core Pipeline (Required)

| Stage | Script | Purpose | Status |
|-------|--------|---------|--------|
| 0 | `0_build_patch.py` | Orchestrator - runs all stages in sequence | Pending |
| 1 | `1_extract_files.py` | Extract localization files from game PAK archives | Pending |
| 2 | `2_normalize_files.py` | Parse .locres and FormatString files into unified JSON | Pending |
| 3 | `3_apply_translations.py` | Apply shared dictionary + game map translations | Pending |
| 4 | `4_generate_patch.py` | Generate translated .locres and FormatString files | Pending |
| 5 | `5_ai_translate.py` | Send untranslated strings to Gemini for AI translation | Pending |
| 6 | `6_find_inconsistencies.py` | Detect conflicting translations across namespaces | Pending |
| 7 | `7_apply_normalization.py` | Apply manual correction rules from review spreadsheet | Pending |

### Optional Stage (May Not Be Needed)

| Stage | Script | Purpose | Status |
|-------|--------|---------|--------|
| 8 | `8_parse_runtime_log.py` | Capture untranslated strings from game runtime logs | Pending |

**Note on Stage 8**: Runtime log capture hooks into Unreal Engine's `LogTextLocalizationManager` verbose logging to find strings the patch missed during gameplay. Whether this is needed depends on how HoK World handles its localization at runtime:

- **Not needed if**: All translatable strings come from static `.locres` and FormatString files that we can extract and translate ahead of time. Most modern UE games work this way.
- **Needed if**: The game generates or assembles strings at runtime (e.g. dynamic tooltips, server-pushed text, Lua/script-composed strings, or DLC content loaded separately). In WOJD, runtime capture was necessary because some strings only appeared during specific gameplay scenarios and weren't in the static extraction.
- **How it would work**: Enable `LogTextLocalizationManager=VeryVerbose` in the game's `Engine.ini`, play through game content, then parse the log for entries marked "did not exist" or "hash does not match". These missed strings feed back into Stage 3 for the next build cycle.
- **Reference implementation**: WOJD's `8_parse_runtime_log.py` handles multi-encoding log reading (UTF-8, UTF-16-LE, GBK), multiline string reconstruction, and hash mismatch detection. The approach is documented there if we need it.

We will determine after the first patch build whether Stage 8 is necessary.

## Initial Setup: Dictionary Pruning

Before running the main pipeline, use `tools/build_game_dictionary.py` to prune the 343K-entry shared dictionary down to only entries that actually appear in the game. This is a **setup tool**, not a pipeline stage — run it a few times during initial bring-up, then the output (`hokw_dictionary.json`) becomes the permanent working dictionary.

```bash
# After extracting game strings (Stage 1-2):
python tools/build_game_dictionary.py --game-strings extracted/unified.json

# Dry run to see stats without writing:
python tools/build_game_dictionary.py --game-strings extracted/unified.json --dry-run

# Exact-match only (faster, more conservative):
python tools/build_game_dictionary.py --game-strings extracted/unified.json --no-substring
```

The tool:
- Cross-references each shared dictionary entry against actual game strings (exact, substring, reverse substring)
- Always keeps HoK official terms and launcher translations (never pruned)
- Outputs `translations/hokw_dictionary.json` — the pipeline's `shared_dictionary` path in config.json should point here once finalized

Re-run when: game updates add new strings, or you want to adjust matching strategy. Once the dictionary is stable, the main pipeline uses it directly and this tool is no longer needed.

## Prerequisites

Before these scripts can be built, we need to:

1. **Analyze the game client** once it's available:
   - Identify the UE project name (equivalent to "ZhuxianClient" in WOJD)
   - Locate PAK files and determine encryption keys
   - Map the localization file structure (.locres paths, FormatString paths)
   - Determine if UE4 or UE5 (affects .locres binary format version)

2. **Fill in `config.json`** with game-specific values:
   - `ue_project_name`, `paks_dir`, `aes_key`
   - `pak_groups` (which PAK files contain localization data)
   - `locres_targets` and `formatstring_targets`

## What's Ready Now

The shared library modules in `game/lib/` are already built and tested:

- **`lib/ue4_locres.py`** - .locres binary format read/write, CityHash64, CRC32
- **`lib/translation_engine.py`** - Multi-strategy translation lookup (exact, OpenCC, pattern)
- **`lib/gemini_client.py`** - Gemini API client with chunking and glossary injection
- **`lib/postprocessor.py`** - English text post-processing (tag repair, punctuation, expansion checks)
- **`lib/utils.py`** - Common utilities (Chinese detection, BOM cleaning, etc.)

The shared dictionary (`translations/shared_dictionary.json`) with 343K+ Chinese-English pairs is ready to use.

## Normalization System

The normalization system is a two-tier QA process:

### Tier 1: Automatic (Stage 6)
`6_find_inconsistencies.py` scans all translations for the same Chinese string translated differently. When one translation appears 3x+ more often than an alternative, it auto-applies the fix. All other conflicts are exported to a CSV for manual review.

### Tier 2: Manual (Stage 7)
A reviewer examines the CSV in a spreadsheet, decides which corrections are valid, and saves them as `normalization_rules.xlsx`. Stage 7 then applies these rules back to the translation map.

### Pre-built Normalization Rules
`translations/normalization_rules.xlsx` ships with rules we can prepare before the game launches - common AI translation mistakes, gaming terminology standards, and style guide enforcement. See the file for the format and existing rules.

## Typical Workflow

Once the pipeline is built, the workflow will be:

```
0. (Once) Prune shared dictionary → hokw_dictionary.json
1. Extract files from game PAK archives
2. Normalize into unified JSON + hash CSV
3. Apply existing translations (pruned dict + game map)
4. Send untranslated strings to Gemini AI
5. Quality check: find & auto-fix inconsistencies
6. Manual review of flagged translations in spreadsheet
7. Apply reviewed corrections
8. Re-apply translations (second pass with corrections)
9. Post-process English text (tags, punctuation, expansion)
10. Generate final .locres and FormatString files
11. Pack into .pak file and install
12. (If needed) Runtime log capture for missed strings -> back to step 3
```
