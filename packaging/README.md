# TD Radar packaging

## Console exe (PyInstaller onedir)

Built artifact: `dist/tdradar/tdradar.exe` (24 MB onedir folder).

Rebuild:

```powershell
.\packaging\build_exe.ps1
```

Smoke test (dev data dir):

```powershell
$env:TD_RADAR_DATA = "$PWD\data"
.\dist\tdradar\tdradar.exe doctor
.\dist\tdradar\tdradar.exe canvas poll --once --download
```

## Runtime data

When frozen, `paths.py` uses `%APPDATA%\TD Radar\` for token/config/state/logs/inbox/out.
In dev or when `TD_RADAR_DATA` is set, it uses that directory instead.

First run needs:

- `data\canvas_token.txt`
- `data\llm_config.json`

The installer/first-run wizard should seed these from templates; not built yet.

## Still to do

- Bundle a Tectonic sidecar (or detect MiKTeX); current exe calls system `xelatex`.
- Inno Setup per-user installer (`PrivilegesRequired=lowest`).
- Task Scheduler / Startup shortcut; tray; notifications.
- Wire Canvas `poll --download` to `pipeline.process_pdf` automatically.
- Phone push / AI chat / workflow interfaces.
