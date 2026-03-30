@echo off
title KingLauncher English Patch - Build EXE
echo.
echo  Building KingLauncher English Patch Installer EXE...
echo.

:: Navigate to launcher/ directory (parent of build/)
cd /d "%~dp0.."

:: Step 1: Build patch files from translations
echo  [1/5] Building patch files from translations.json...
node src\build-patch.js
if %errorlevel% neq 0 (
    echo  ERROR: Patch build failed
    pause
    exit /b 1
)

:: Step 2: Bundle JS files into single file
echo  [2/5] Bundling source files...
node build\bundle.js
if %errorlevel% neq 0 (
    echo  ERROR: Bundle failed
    pause
    exit /b 1
)

:: Step 2: Generate SEA blob
echo  [3/5] Generating SEA blob...
node --experimental-sea-config build\sea-config.json
if %errorlevel% neq 0 (
    echo  ERROR: SEA config generation failed
    pause
    exit /b 1
)

:: Step 3: Copy node.exe and inject blob
echo  [4/5] Creating executable...
if not exist dist mkdir dist
:: Find node.exe
for /f "delims=" %%N in ('where node') do set "NODE_EXE=%%N"
copy /y "%NODE_EXE%" dist\KingLauncher-EngPatch.exe >nul
if %errorlevel% neq 0 (
    echo  ERROR: Failed to copy node.exe
    pause
    exit /b 1
)

:: Step 4: Inject the SEA blob
echo  [5/5] Injecting patch into executable...
npx postject dist\KingLauncher-EngPatch.exe NODE_SEA_BLOB build\sea-prep.blob --sentinel-fuse NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2 --overwrite
if %errorlevel% neq 0 (
    echo  ERROR: Blob injection failed
    pause
    exit /b 1
)

:: Done
echo.
echo  ===================================================
echo   Build complete!
echo  ===================================================
echo.
echo   Output: dist\KingLauncher-EngPatch.exe
for %%F in (dist\KingLauncher-EngPatch.exe) do echo   Size: %%~zF bytes

echo.
echo   Install:    KingLauncher-EngPatch.exe
echo   Uninstall:  KingLauncher-EngPatch.exe --uninstall
echo.
pause
