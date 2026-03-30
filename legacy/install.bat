@echo off
title Honor of Kings: World - English Patch Installer
echo.
echo  ===================================================
echo   Honor of Kings: World - Launcher English Patch
echo  ===================================================
echo.

:: Auto-elevate to admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Try default location first
set "KING_BASE="
set "LAUNCHER_DIR="
if exist "C:\Program Files\KingLauncher" (
    set "KING_BASE=C:\Program Files\KingLauncher"
)

:: If not found at default, ask user to select
if "%KING_BASE%"=="" (
    echo  KingLauncher not found at the default location.
    echo  Please select your KingLauncher folder.
    echo.
    echo  IMPORTANT: Select the "KingLauncher" folder itself,
    echo  NOT a subfolder inside it.
    echo.
    echo  Example: D:\Games\KingLauncher
    echo.

    :: Use PowerShell folder picker
    for /f "usebackq delims=" %%F in (`powershell -Command "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Select your KingLauncher folder'; $f.ShowNewFolderButton = $false; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath } else { '' }"`) do set "KING_BASE=%%F"

    if "!KING_BASE!"=="" (
        echo  No folder selected. Installation cancelled.
        echo.
        pause
        exit /b 1
    )
)

setlocal enabledelayedexpansion

:: Re-check KING_BASE with delayed expansion
if "%KING_BASE%"=="" (
    if exist "C:\Program Files\KingLauncher" (
        set "KING_BASE=C:\Program Files\KingLauncher"
    ) else (
        echo  No folder selected. Installation cancelled.
        echo.
        pause
        exit /b 1
    )
)

:: Validate: look for a version subfolder with resources\app.asar
set "LAUNCHER_DIR="
for /d %%D in ("%KING_BASE%\*") do (
    if exist "%%D\resources\app.asar" set "LAUNCHER_DIR=%%D"
)

if "%LAUNCHER_DIR%"=="" (
    echo.
    echo  ERROR: Invalid KingLauncher folder!
    echo.
    echo  The selected folder does not contain a valid KingLauncher installation.
    echo  Could not find a version subfolder with "resources\app.asar" inside:
    echo    %KING_BASE%
    echo.
    echo  Make sure you selected the correct "KingLauncher" folder
    echo  ^(e.g., C:\Program Files\KingLauncher^)
    echo.
    echo  IMPORTANT: Use the official Windows PC launcher from https://world.qq.com/
    echo  The WeGame launcher is NOT supported.
    echo.
    pause
    exit /b 1
)

echo  Found launcher: %LAUNCHER_DIR%

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Node.js is required but not installed.
    echo  Download it from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

:: Kill launcher if running
taskkill /f /im "王者荣耀世界.exe" >nul 2>&1

set "RESOURCES=%LAUNCHER_DIR%\resources"
set "ASAR=%RESOURCES%\app.asar"
set "SCRIPT_DIR=%~dp0"

:: Backup original (only first time)
if not exist "%ASAR%.original" (
    echo  Backing up original app.asar...
    copy /y "%ASAR%" "%ASAR%.original" >nul
)

:: Extract
echo  Extracting app.asar...
call npx @electron/asar extract "%ASAR%" "%TEMP%\kl_eng_patch_tmp" >nul 2>&1
if not exist "%TEMP%\kl_eng_patch_tmp\package.json" (
    echo  ERROR: Failed to extract app.asar
    pause
    exit /b 1
)

:: Apply patch
echo  Applying English patch...
copy /y "%SCRIPT_DIR%patch_files\main.92fa614d.js" "%TEMP%\kl_eng_patch_tmp\main.92fa614d.js" >nul
copy /y "%SCRIPT_DIR%patch_files\eng_patch_renderer.js" "%TEMP%\kl_eng_patch_tmp\eng_patch_renderer.js" >nul

:: Repack
echo  Repacking app.asar...
call npx @electron/asar pack "%TEMP%\kl_eng_patch_tmp" "%TEMP%\kl_eng_patched.asar" --unpack-dir "{game,node_modules}" >nul 2>&1
if not exist "%TEMP%\kl_eng_patched.asar" (
    echo  ERROR: Failed to repack app.asar
    pause
    exit /b 1
)

:: Install
echo  Installing...
copy /y "%TEMP%\kl_eng_patched.asar" "%ASAR%" >nul
rmdir /s /q "%RESOURCES%\app.asar.unpacked" 2>nul
mkdir "%RESOURCES%\app.asar.unpacked" 2>nul
xcopy /e /i /y /q "%TEMP%\kl_eng_patched.asar.unpacked\*" "%RESOURCES%\app.asar.unpacked\" >nul

:: Cleanup
rmdir /s /q "%TEMP%\kl_eng_patch_tmp" 2>nul
del "%TEMP%\kl_eng_patched.asar" 2>nul
rmdir /s /q "%TEMP%\kl_eng_patched.asar.unpacked" 2>nul

echo.
echo  ===================================================
echo   English Patch installed successfully!
echo  ===================================================
echo.
echo  You can now launch the game normally.
echo  If the launcher updates, just run this again.
echo.
pause
