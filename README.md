# Honor of Kings: World - English Patch

Community English translation patches for Honor of Kings: World (王者荣耀世界).

## Projects

### [Launcher Patch](launcher/) - Available Now
Translates the KingLauncher desktop application UI from Chinese to English.
- 1,600+ translated strings covering menus, settings, FAQ, and more
- One-click standalone installer (.exe) - no dependencies required
- [Download the latest release](../../releases)

### [Game Patch](game/) - Coming Soon
English translation for the game client itself. Currently in development - the game has not yet launched.

## Important: Correct Launcher

Download the **Windows PC launcher** from https://world.qq.com/ (the one with the Windows icon).

**Do NOT use the WeGame launcher** - it is a different application.

## Quick Start

### For Users
1. Download `KingLauncher-EngPatch.exe` from [Releases](../../releases)
2. Double-click to install (admin privileges required)
3. Launch the game normally

### For Developers
```bash
git clone <repo-url>
cd HoK-World-EngPatch

# Build the launcher patch exe
launcher\build\build.bat

# Or run directly (requires Node.js v20+)
node launcher/src/installer.js

# Add new translations
# 1. Edit launcher/translations.json
# 2. Rebuild patch files:
node launcher/src/build-patch.js
# 3. Rebuild exe:
launcher\build\build.bat
```

## Contributing

### Adding Launcher Translations
1. Run the launcher with the patch installed
2. Find untranslated strings: `node launcher/tools/scan-strings.js`
3. Add translations to `launcher/translations.json`
4. Rebuild: `node launcher/src/build-patch.js`
5. Submit a pull request

### Translation Format
`translations.json` is a simple Chinese-to-English mapping:
```json
{
  "设置": "Settings",
  "退出": "Exit",
  "更新修复": "Update & Repair"
}
```

## License

MIT License - See [LICENSE](LICENSE)
