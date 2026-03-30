@echo off
title KingLauncher English Patch Wrapper - Build EXE
echo.
echo  Building KingLauncher English Patch Wrapper EXE...
echo.

:: Navigate to repo root (grandparent of build/)
cd /d "%~dp0..\.."

:: Step 1: Build patch files from translations (shared with launcher/)
echo  [1/4] Building translation script...
node launcher\src\build-patch.js
if %errorlevel% neq 0 (
    echo  ERROR: Patch build failed
    pause
    exit /b 1
)

:: Step 2: Generate SEA blob
echo  [2/4] Generating SEA blob...
node --experimental-sea-config launcher-wrapper\build\sea-config.json
if %errorlevel% neq 0 (
    echo  ERROR: SEA blob generation failed
    pause
    exit /b 1
)

:: Step 3: Copy node.exe
echo  [3/4] Creating executable...
if not exist launcher-wrapper\dist mkdir launcher-wrapper\dist

for /f "delims=" %%N in ('where node') do set "NODE_EXE=%%N"
copy /y "%NODE_EXE%" launcher-wrapper\dist\KingLauncher-EngPatch-Wrapper.exe >nul
if %errorlevel% neq 0 (
    echo  ERROR: Failed to copy node.exe
    pause
    exit /b 1
)

:: Step 4: Inject the SEA blob
echo  [4/4] Injecting patch into executable...
npx postject launcher-wrapper\dist\KingLauncher-EngPatch-Wrapper.exe NODE_SEA_BLOB launcher-wrapper\build\sea-prep.blob --sentinel-fuse NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2 --overwrite
if %errorlevel% neq 0 (
    echo  ERROR: Blob injection failed
    pause
    exit /b 1
)

echo.
echo  ===================================================
echo   Build complete!
echo  ===================================================
echo.
echo   Output: launcher-wrapper\dist\KingLauncher-EngPatch-Wrapper.exe
for %%F in (launcher-wrapper\dist\KingLauncher-EngPatch-Wrapper.exe) do echo   Size: %%~zF bytes
echo.
echo   Usage: Just run the exe to launch the game with English translations.
echo   No admin required. No file modifications. Update resistant.
echo.
pause
