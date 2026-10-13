# Update2Report

Update2Report turns informal team notes into a structured weekly update, a printable HTML report, and an Excel workbook.

## Privacy and model setup

The only AI integration is an open-weight language model served through an OpenAI-compatible API. The application reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` from the process environment. It does not include a provider key in source, reports, or logs. Configure those variables before generating uncached reports.

For local-only processing, run an open-weight model with Ollama and set `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_API_KEY=ollama`, and `LLM_MODEL` to the model name installed in Ollama. Team notes stay on the machine when the endpoint is local. Copy `.env.example` to `.env` only for local setup; `.env` is ignored by Git. Sample reports also work without model credentials because their extraction results are bundled in `samples/cache/`.

## Run

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:7860`. Paste team notes or load one of the three fictional Northwind Studio examples. Optionally upload a CSV with `task,owner,project,due,status` columns. Select a tone and generate both downloadable reports.

## Validation

```powershell
python -m pytest -q
```

Task counts, overdue items, and missing updates are calculated in Python. The generated summary is checked against those deterministic statistics and retried if it uses unsupported numbers.
