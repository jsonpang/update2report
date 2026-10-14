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

Turn messy team notes into a printable weekly HTML report and an Excel workbook. Open-weight models are the core of Update2Report—they extract structured tasks from unstructured updates and draft natural summaries, while deterministic Python code computes trusted statistics and cross-checks every number in the summary against ground truth. The public demo uses the official DeepSeek API (`deepseek-chat`) by default, while teams can run open-weight models locally via Ollama (such as `qwen2.5:7b`), keeping sensitive project data entirely on-device. All bundled Northwind Studio data is fictional.

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

Open-weight models power Update2Report's core intelligence. The app connects to any OpenAI-compatible API endpoint using `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`. Set all three before live generation.

| Provider | LLM_BASE_URL | LLM_MODEL |
|---|---|---|
| DeepSeek official | `https://api.deepseek.com` | `deepseek-chat` |
| Local Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` |

For local processing, use an installed open-weight model (such as `qwen2.5:7b`) via Ollama and a local base URL (for Ollama, `LLM_API_KEY` can be set to any placeholder like `ollama`). Notes stay on the machine only when your endpoint is local, ensuring complete data privacy. Cached samples need no model credentials. Do not paste sensitive data into a public demo. Uploads and generated reports remain on its server until cleanup or restart.

## Trusted statistics

Completed = extracted done items + CSV tasks in done/complete/completed/closed or Chinese completion states. Deduplicate within each project using Unicode NFKC, case folding, ignoring whitespace/punctuation and an optional project prefix. Owners do not affect identity. Extraction uses exact CSV task names where applicable and canonical names for repeated multilingual mentions. Different unmatched paraphrases remain separate; there is no fuzzy merge. HTML and Excel show every counted task and its text/CSV sources. Chat can record completion while CSV still says in progress. Text-completed tasks are excluded from overdue; stale CSV statuses are listed separately for reconciliation. Relative dates in notes remain verbatim.

Upload optional UTF-8 CSV with task,owner,project,due,status columns and ISO YYYY-MM-DD due dates. Counts are computed in Python. The numeric-free model summary is checked for unsupported numbers; this does not independently prove semantic extraction accuracy.

## Demo limits

Live generation allows 5 attempts per Gradio session, including model failures. Combined notes and decoded CSV are limited to 8000 characters; file uploads are limited to 32 KB. Both sample tones are cached and matched to the notes AND CSV content, so unchanged samples use no tokens. Editing notes or replacing CSV uses a live attempt. A new browser session resets the quota; this is demo cost protection, not account-level abuse prevention. Model requests have a 45-second timeout and one transport retry; invalid extraction JSON gets one correction attempt. Errors return a friendly message without exposing provider details. Live outputs have independent directories and never modify sample caches.

## Hugging Face Spaces preparation (not deployed)

Create a Space with the Gradio SDK and upload the tracked repository, including samples/cache. Exclude .env, .git, out and local logs. The YAML above selects app.py, Python 3.11 and verified Gradio 5.50.0. Spaces binds to 0.0.0.0:7860; local startup uses 127.0.0.1:7860.

Configure Settings > Variables and secrets:

| Name | Kind | Value |
|---|---|---|
| LLM_API_KEY | Secret | Your provider key, never included in Git or screenshots |
| LLM_BASE_URL | Variable or Secret | Publicly reachable OpenAI-compatible API base URL |
| LLM_MODEL | Variable or Secret | Exact model ID supported by that endpoint |

Use the DeepSeek official API for the public demo as planned. A cloud Space cannot reach a localhost endpoint. Cached samples work in either tone even before secrets are configured. See the [Spaces configuration reference](https://huggingface.co/docs/hub/spaces-config-reference) and [Spaces secrets documentation](https://huggingface.co/docs/hub/spaces-overview).

## Verification and sample refresh

```powershell
python -m pytest -q
python scripts/refresh_samples.py
python scripts/check_reports.py
```

Refresh performs real extraction and both summary tones with the configured model, updates only fictional sample caches, writes HTML/Excel and records elapsed time and API-reported token totals. It deliberately bypasses the cache. The checker compares each HTML snapshot row with its counted-completion evidence and deterministic stats.
