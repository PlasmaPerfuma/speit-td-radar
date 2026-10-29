@echo off
setlocal
cd /d "%~dp0"
title TD Radar Control Panel

set "INSTALLED=%LOCALAPPDATA%\Programs\TD Radar\tdradar.exe"

if exist "%~dp0dist\tdradar\tdradar.exe" (
    set "TD_RADAR_DATA=%~dp0data"
    start "" /min "%~dp0dist\tdradar\tdradar.exe" panel
    exit /b 0
)

if exist "%INSTALLED%" (
    start "" /min "%INSTALLED%" panel
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo TD Radar was not found.
    echo Expected dist\tdradar\tdradar.exe or an installed TD Radar.
    pause
    exit /b 1
)

set "TD_RADAR_DATA=%~dp0data"
start "" /min python "%~dp0app\tdradar.py" panel
exit /b 0
