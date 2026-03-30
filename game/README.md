# Game English Patch - Coming Soon

English translation for the Honor of Kings: World game client.

## Status

The game has not yet launched. This directory is a placeholder for the future game translation project.

## Planned Approach

Honor of Kings: World uses Unreal Engine. Game translation will likely involve:
- Localization asset files (`.locres` / `.uasset`)
- Text table extraction and replacement
- Possibly PAK file patching

The approach will be determined once the game client is available for analysis.

## Structure (Planned)

```
game/
  translations/            - Translation files (format TBD)
  src/                     - Patching tools
  dist/                    - Built patcher output
  README.md                - This file
```

## Contributing

Once the game launches, we will need help with:
- Extracting game text strings
- Translating Chinese to English
- Testing translations in-game
- Documenting the patching process

Check back after the game launches for contribution guidelines.
