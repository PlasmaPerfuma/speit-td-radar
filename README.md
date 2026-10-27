# TD Radar

**Turn Canvas TD PDFs into structured French/Chinese revision PDFs.**

[简体中文](README.zh-CN.md) | **English**

TD Radar watches Canvas courses, downloads newly published TD (travaux dirigés) files, extracts their text, checks the text layer, asks an LLM for a structured solution, and renders a compact LaTeX PDF.

> Personal project, built for the SPEIT / SJTU Canvas workflow. Not affiliated with SJTU, Canvas, or DeepSeek.
> The sample PDF in `docs/` is synthetic, not course material.

![sample page](docs/sample.png)

## What it does

- **Canvas polling** — list, poll and download TD files with a local state file.
- **Text quality gate** — catches broken PDF text layers before sending them to an LLM.
- **Structured LLM output** — French solution, Chinese translation, inline conditions, and centered key formulas.
- **LaTeX PDF rendering** — A4, Tahoma + SimHei, bold math, controlled page breaks.
- **Reusable pipeline** — `PDF -> extract -> gate -> LLM -> JSON -> PDF`.
- **Console CLI** — `tdradar doctor`, `tdradar canvas`, `tdradar generate`.
- **Packaged console build** — PyInstaller onedir executable.

## Demo

- Synthetic sample: [`docs/sample.pdf`](docs/sample.pdf)
- Preview: [`docs/sample.png`](docs/sample.png)

## Requirements

- Windows 10/11
- Python 3.12 (development)
- A LaTeX engine: currently **MiKTeX `xelatex`**; Tectonic bundling is planned
- A Canvas personal access token
- An OpenAI-compatible DeepSeek endpoint + key

## Setup

```powershell
git clone https://github.com/PlasmaPerfuma/speit-td-radar.git
cd speit-td-radar

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy data\llm_config.example.json data\llm_config.json
copy data\canvas_token.example.txt data\canvas_token.txt
```

Edit `data\llm_config.json`:

```json
{
  "base_url": "https://api.deepseek.com",
  "api_key": "sk-...",
  "model": "deepseek-flash",
  "max_tokens": 100000,
  "timeout": 180,
  "reasoning_effort": null
}
```

Put your Canvas token in `data\canvas_token.txt` (one line, no quotes).

Never commit `data\llm_config.json` or `data\canvas_token.txt`; both are in `.gitignore`.

## Usage

```powershell
# Check token / LLM config / LaTeX / state
python app\tdradar.py doctor

# List TD files found in the configured Canvas courses
python app\tdradar.py canvas list

# First run: mark current files as seen, do NOT bulk-download
python app\tdradar.py canvas poll --once --bootstrap

# Later: download only new/updated files
python app\tdradar.py canvas poll --once --download

# Auto download + generate the detail PDF for new sujets
python app\tdradar.py canvas poll --once --download --process

# Continuous polling (5 minutes)
python app\tdradar.py canvas poll --interval 300 --download

# Download one file by name
python app\tdradar.py canvas download --course 95175 --match TD7_e

# Manual end-to-end generation for a downloaded PDF
python app\tdradar.py generate --pdf inbox\canvas\algebre\TD7\Algèbre_TD7_e.pdf `
  --course "Algèbre I" --td TD7
```

Outputs go to `out\<course>_<td>\`:

- `llm_raw.json`
- `td_detail.json`
- `td_detail.pdf`
- `meta.json`

## Architecture

```text
Canvas API ──► app/canvas.py ──► data/canvas_state.json
                    │
                    ▼
              inbox/canvas/...
                    │
app/pipeline.py ──► extract.py ──► quality.py ──► analyze.py ──► td_render.py
                                                          │
                                                          ▼
                                                    out/.../td_detail.pdf
```

| Path | Role |
|---|---|
| `app/tdradar.py` | Console entrypoint: `doctor` / `canvas` / `generate` |
| `app/canvas.py` | Canvas discovery, polling, state, signed-URL download |
| `app/pipeline.py` | Reusable PDF -> quality gate -> LLM -> PDF |
| `app/extract.py` | `pdftotext` wrapper |
| `app/quality.py` | Broken text-layer metrics and gate |
| `app/analyze.py` | LLM prompt, JSON schema, normalization |
| `app/llm.py` | OpenAI-compatible client + local config |
| `app/td_render.py` | LaTeX renderer and compile wrapper |
| `app/paths.py` | Repo paths in dev; `%APPDATA%\TD Radar` when frozen |
| `packaging/` | PyInstaller build script and notes |

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Tests are offline and do not require a Canvas token or an API key.

## Privacy and security

- Canvas token and API key live only in local `data/` (ignored by Git).
- Downloaded course PDFs, corrigés, logs and generated PDFs are ignored by Git.
- Do not publish course materials; only the source code is licensed here.
- If a token/key was ever committed, rotate it immediately.
- Check Canvas/DeepSeek terms of service before using this with your account.
- Logs and generated files stay local.

## Current limitations

- Windows-first; paths and `xelatex` are Windows-oriented.
- Canvas course IDs are currently SJTU-specific (`app/canvas.py`).
- The packaged exe still calls system MiKTeX; Tectonic is not bundled yet.
- `--process` wires download to generation for **sujets**; corrigé auto-processing is not enabled.
- No scheduler, tray, installer, push notification, or OCR/VLM fallback yet.
- Full-TD generation has not been validated end-to-end; the sample focuses on one exercise.

## Roadmap

- [x] Wire `canvas poll --download` into `pipeline.process_pdf`
- [ ] Bundle Tectonic / portable LaTeX
- [ ] Inno Setup per-user installer, no UAC
- [ ] Windows Task Scheduler / tray / notifications
- [ ] Generic Canvas base URL and course config
- [ ] OCR/VLM fallback for broken text layers
- [ ] Optional phone push / AI chat / workflow hooks

## License

MIT for the source code. Course PDFs, corrigés, and other teaching materials are **not** part of this project and must not be redistributed.
