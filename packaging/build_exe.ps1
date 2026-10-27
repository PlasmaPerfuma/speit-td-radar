$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$python = $env:TD_RADAR_PYTHON
if (-not $python) { $python = "python" }

if (-not (Test-Path ".tools\pyinstaller\PyInstaller")) {
    $env:PIP_CACHE_DIR = "$root\.tools\pip-cache"
    $env:TMP = "$root\.tools\tmp"
    $env:TEMP = "$root\.tools\tmp"
    & $python -m pip install --disable-pip-version-check --no-warn-script-location `
        --target .tools\pyinstaller pyinstaller
}

$env:PYTHONPATH = "$root\.tools\pyinstaller"
& $python -m PyInstaller --noconfirm --clean `
    --onedir --console --name tdradar `
    --paths app --distpath dist --workpath build\pyinstaller `
    app\tdradar.py

Write-Host "Built: $root\dist\tdradar\tdradar.exe"
