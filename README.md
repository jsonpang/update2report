---
title: Update2Report
emoji: "\U0001F4CB"
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.50.0
python_version: "3.11"
app_file: app.py
pinned: false
license: mit
---

# Update2Report

Turn messy team notes into a printable weekly HTML report and an Excel workbook. Open-weight models are the core of Update2Report—they extract structured tasks from unstructured updates and draft natural summaries, while deterministic Python code computes trusted statistics and cross-checks every number in the summary against ground truth. The public demo runs OpenAI's open-weight gpt-oss-120b (Apache 2.0) through an OpenAI-compatible gateway; point `LLM_BASE_URL` at another provider or a local Ollama instance to use a different backend. All bundled Northwind Studio data is fictional.

## Run locally

```powershell
git clone https://github.com/jsonpang/weeklyreport-ai.git
cd weeklyreport-ai
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your own endpoint, key and model, then start:
python app.py
```

Open http://127.0.0.1:7860. Load a sample, select internal or client-facing tone and click Generate report. Download HTML and Excel. app.py loads .env without overriding existing process environment variables. Never commit .env. Stop with Ctrl+C.

## Model setup and privacy

Open-weight models power Update2Report's core intelligence. The app connects to any OpenAI-compatible API endpoint using `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`. Set all three before live generation. An optional `LLM_FALLBACK_MODEL` can be configured to automatically retry requests with a secondary model if the primary model encounters rate limits (429), server errors (5xx), timeouts, or connection failures. `LLM_FALLBACK_DELAY` (seconds, default 0) waits before that retry; setting the fallback to the primary model with a short delay rides out brief rate limits.

| Provider | LLM_BASE_URL | LLM_MODEL |
|---|---|---|
| DeepSeek official | `https://api.deepseek.com` | `deepseek-chat` |
| Local Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

For local processing, use an installed open-weight model (such as `qwen2.5:7b`) via Ollama and a local base URL (for Ollama, `LLM_API_KEY` can be set to any placeholder like `ollama`). Notes stay on the machine only when your endpoint is local, ensuring complete data privacy. Cached samples need no model credentials. Do not paste sensitive data into a public demo. Uploads and generated reports remain on its server until cleanup or restart.

## Trusted statistics

Completed = extracted done items + CSV tasks in done/complete/completed/closed or Chinese completion states. Deduplicate within each project using Unicode NFKC, case folding, ignoring whitespace/punctuation and an optional project prefix. Owners do not affect identity. Extraction uses exact CSV task names where applicable and canonical names for repeated multilingual mentions. Different unmatched paraphrases remain separate; there is no fuzzy merge. HTML and Excel show every counted task and its text/CSV sources. Chat can record completion while CSV still says in progress. Text-completed tasks are excluded from overdue; stale CSV statuses are listed separately for reconciliation. Relative dates in notes remain verbatim.

Upload optional UTF-8 CSV with task,owner,project,due,status columns and ISO YYYY-MM-DD due dates. Counts are computed in Python. The model summary must keep every number from the source and may not add numbers that are not in it; this does not independently prove semantic extraction accuracy.

## Demo limits

Live generation is capped at 5 attempts per Gradio session, 5 per IP per hour (`DEMO_PER_IP_HOURLY`) and 60 per day (`DEMO_DAILY_CAP`); `DEMO_LIVE=0` pauses live generation while cached samples keep working. Combined notes and decoded CSV are limited to 8000 characters; file uploads are limited to 32 KB. Both sample tones are cached and matched to the notes AND CSV content, so unchanged samples use no tokens. Editing notes or replacing CSV uses a live attempt. A new browser session resets only the session quota; the per-IP and daily caps still apply. This is demo cost protection, not account-level abuse prevention. Model requests have a 45-second timeout and one transport retry; invalid extraction JSON gets one correction attempt. Errors return a friendly message without exposing provider details. Live outputs have independent directories and never modify sample caches.

## Self-hosting

Deploy behind nginx as a reverse-proxy with a systemd service.

### Minimal setup

```bash
# 1. Upload code (no .git, .env, or out/)
git archive HEAD | ssh user@host "mkdir -p /opt/update2report && tar -x -C /opt/update2report"

# 2. Create a venv and install dependencies
python3.11 -m venv /opt/update2report/.venv
/opt/update2report/.venv/bin/pip install -r /opt/update2report/requirements.txt

# 3. Create /etc/update2report.env (chmod 600) with:
#    LLM_BASE_URL=<your OpenAI-compatible endpoint>
#    LLM_API_KEY=<your key>
#    LLM_MODEL=<model id>
#    GRADIO_SERVER_NAME=127.0.0.1
#    GRADIO_SERVER_PORT=7860

# 4. systemd service (/etc/systemd/system/update2report.service)
#    EnvironmentFile=/etc/update2report.env
#    WorkingDirectory=/opt/update2report
#    ExecStart=/opt/update2report/.venv/bin/python app.py
#    Restart=always

# 5. nginx reverse-proxy to 127.0.0.1:7860
#    proxy_set_header X-Real-IP $remote_addr;
#    proxy_set_header Upgrade $http_upgrade;
#    proxy_read_timeout 120s;
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `GRADIO_SERVER_NAME` | `127.0.0.1` | Bind address for the Gradio server |
| `GRADIO_SERVER_PORT` | `7860` | Bind port for the Gradio server |
| `DEMO_LIVE` | `1` | Set to `0` to disable live generation (cached samples still work) |
| `DEMO_PER_IP_HOURLY` | `5` | Max live generations per client IP per hour |
| `DEMO_DAILY_CAP` | `60` | Max total live generations per UTC+8 calendar day |
| `LLM_FALLBACK_MODEL` | (none) | Optional secondary model to retry when primary model fails |

When `DEMO_LIVE=0` the UI displays "Live generation is paused; cached samples still work." and all live generation requests return a friendly message without calling the model.

If the model endpoint is unreachable or times out, the app returns "Live model is temporarily offline; cached samples still work." without exposing stack traces.

## Verification and sample refresh

```powershell
python -m pytest -q
python scripts/refresh_samples.py
python scripts/check_reports.py
```

Refresh performs real extraction and both summary tones with the configured model, updates only fictional sample caches, writes HTML/Excel and records elapsed time and API-reported token totals. It deliberately bypasses the cache. The checker compares each HTML snapshot row with its counted-completion evidence and deterministic stats.
