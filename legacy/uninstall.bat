@echo off
title Honor of Kings: World - English Patch Uninstaller
echo.
echo  ===================================================
echo   Honor of Kings: World - Remove English Patch
echo  ===================================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

setlocal enabledelayedexpansion

:: Try default location first
set "LAUNCHER_DIR="
if exist "C:\Program Files\KingLauncher" (
    for /d %%D in ("C:\Program Files\KingLauncher\*") do (
        if exist "%%D\resources\app.asar.original" set "LAUNCHER_DIR=%%D"
    )
)

:: If not found at default, ask user to select
if "%LAUNCHER_DIR%"=="" (
    echo  Backup not found at the default location.
    echo  Please select your KingLauncher folder.
    echo.

    for /f "usebackq delims=" %%F in (`powershell -Command "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Select your KingLauncher folder'; $f.ShowNewFolderButton = $false; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath } else { '' }"`) do set "KING_BASE=%%F"

    if "!KING_BASE!"=="" (
        echo  No folder selected. Uninstall cancelled.
        pause
        exit /b 1
    )

    for /d %%D in ("!KING_BASE!\*") do (
        if exist "%%D\resources\app.asar.original" set "LAUNCHER_DIR=%%D"
    )
)

if "%LAUNCHER_DIR%"=="" (
    echo  ERROR: No backup found. Cannot restore.
    echo  The English patch may not be installed, or the backup was removed.
    pause
    exit /b 1
)

taskkill /f /im "王者荣耀世界.exe" >nul 2>&1

echo  Restoring original launcher...
copy /y "%LAUNCHER_DIR%\resources\app.asar.original" "%LAUNCHER_DIR%\resources\app.asar" >nul

echo.
echo  English Patch removed. Launcher restored to Chinese.
echo.
pause
