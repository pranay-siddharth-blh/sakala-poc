# Sakala AI POC + Mitra

AI grievance desk for the Government of Karnataka (Praja Seva / Sakala). It has two apps:

- **`app/`**: the Sakala POC. FastAPI + SQLite. It has a WhatsApp-style citizen channel, an officer desk and the Chief Secretary dashboard.
- **`mitra/`**: Mitra, a full-duplex voice agent over the same pipeline (Gemini Live).

The full project handoff (decisions, data, tests) is in **[CLAUDE.md](CLAUDE.md)**.

## Run

```bat
:: 1. secrets: copy the examples and fill in the keys
copy app\.env.example app\.env
copy mitra\.env.example mitra\.env

:: 2. Sakala POC on http://localhost:8020
cd app
pip install -r requirements.txt
python -m uvicorn server.api:app --port 8020

:: 3. Mitra on http://localhost:8030 (needs 8020 running)
mitra\run.bat
```

The POC starts from `app/data/sakala_pristine.db`, which is included.
If you need to rebuild everything from the Excel, run `python -m server.ingest` from `app/`. It takes about 2 minutes.

## Not in this repo
- `.env` files (API keys): use the `.env.example` files.
- Runtime databases (`app/data/sakala.db`, `mitra/data/`): they are created on first run.
- `_run/` (local copies of other projects) and `tools/backups/`.

> Private. This repo contains masked real iPGRS grievance data. Do not make it public.
