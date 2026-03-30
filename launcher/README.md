# Launcher English Patch

Translates the KingLauncher (王者荣耀世界) desktop application UI from Chinese to English using runtime DOM injection.

## Download

**[Download KingLauncher-EngPatch.exe](https://github.com/Lani27/hok-world-eng-project/releases/latest)** from the Releases page. No Node.js or other software required.

## Install

1. Close the launcher completely
2. Run **KingLauncher-EngPatch.exe** (it will request admin privileges)
3. If the launcher is not at `C:\Program Files\KingLauncher`, a folder picker will appear
4. Wait for "installed successfully"
5. Launch the game normally

## Uninstall

```
KingLauncher-EngPatch.exe --uninstall
```

## After Launcher Updates

If the launcher updates and reverts to Chinese, just run the installer again.

## Build from Source

Requires [Node.js](https://nodejs.org/) v20+.

```bash
# From the repo root:
launcher\build\build.bat

# Output: launcher/dist/KingLauncher-EngPatch.exe
```

Or run directly without building an exe:
```bash
node launcher/src/installer.js            # Install
node launcher/src/installer.js --uninstall # Uninstall
```

## Adding Translations

1. Edit `translations.json` (Chinese key -> English value)
2. Rebuild patch files: `node launcher/src/build-patch.js`
3. Rebuild exe: `launcher\build\build.bat`

To find untranslated strings:
```bash
# Run the launcher with the patch first, then:
node launcher/tools/scan-strings.js
```

## How It Works

The patch modifies the Electron app's main process entry point (`main.92fa614d.js`) to inject a translation engine (`eng_patch_renderer.js`) into every renderer window via `executeJavaScript()`.

The engine uses a MutationObserver to watch for Chinese text in the DOM and replaces it with English translations in real-time:
- **Layer 1**: Exact text node matching (all entries)
- **Layer 2**: Substring replacement for longer phrases (6+ chars only, to avoid garbling)

## Project Structure

```
launcher/
  translations.json        - Master translation file (edit this!)
  src/
    asar.js                - Pure JS asar archive library
    installer.js           - Installer + uninstaller logic
    build-patch.js         - Generates patch files from translations
  patch_files/             - Generated patch output
    eng_patch_renderer.js  - DOM translation engine
    main.92fa614d.js       - Main process loader
  build/                   - EXE build pipeline
    build.bat              - One-click build script
    bundle.js              - JS bundler for Node.js SEA
    sea-config.json        - SEA configuration
  tools/
    scan-strings.js        - Find new untranslated strings
  dist/                    - Built exe output (gitignored)
```

## Notes

- Only the launcher UI is translated, not the game itself
- Some image-based text (logos, banners) cannot be translated
- The original `app.asar` is backed up as `app.asar.original`
