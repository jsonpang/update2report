import json
import os
from datetime import date
from pathlib import Path
from .schemas import UpdateBundle
from .stats import calculate_stats, csv_task_rows
from .compose import compose_summary, validate_summary_numbers
from .render_html import render_html
from .render_excel import render_excel
from .llm import LLMClient

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / 'samples'
OUT_DIR = ROOT / 'out'

def generate_report(text, csv_path=None, tone='internal', sample_id=None, client=None, report_date=None):
    if not text.strip(): raise ValueError('Please paste team updates first.')
    OUT_DIR.mkdir(exist_ok=True)
    report_date = report_date or date.today()
    sample_file = SAMPLE_DIR / f'{sample_id}.json' if sample_id else None
    sample_matches = False
    if sample_file and sample_file.exists():
        sample_data = json.loads(sample_file.read_text(encoding='utf-8-sig'))
        sample_matches = text.strip() == sample_data.get('text', '').strip()
    cache_file = SAMPLE_DIR / 'cache' / f'{sample_id}.json' if sample_matches else None
    cached = None
    if cache_file and cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding='utf-8-sig'))
    cached_rows = cached.get('updates', []) if isinstance(cached, dict) else cached
    has_cached_summary = isinstance(cached, dict) and tone in cached.get('summaries', {})
    needs_model = not cached_rows or not has_cached_summary
    if client is None and needs_model:
        client = LLMClient()
    if cached_rows:
        updates = [UpdateBundle.model_validate(row) for row in cached_rows]
    else:
        from .extract import extract_updates
        updates = extract_updates(client, text)
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {'updates': [item.model_dump() for item in updates], 'summaries': cached.get('summaries', {}) if isinstance(cached, dict) else {}}
        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding='utf-8')
    tasks = csv_task_rows(csv_path)
    members = sorted({u.person for u in updates} | {row.get('owner','').strip() for row in tasks if row.get('owner','').strip()})
    stats = calculate_stats(updates, tasks, report_date, members)
    if has_cached_summary:
        summary = cached['summaries'][tone]
        try:
            validate_summary_numbers(summary, stats)
        except ValueError:
            has_cached_summary = False
            client = client or LLMClient()
    if not has_cached_summary:
        summary = compose_summary(client, updates, stats, tone)
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {'updates': [item.model_dump() for item in updates], 'summaries': cached.get('summaries', {}) if isinstance(cached, dict) else {}}
        cache_data['summaries'][tone] = summary
        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = {'date': report_date.isoformat(), 'tone': tone, 'summary': summary, 'updates': updates, 'stats': stats}
    file_prefix = f'{sample_id}_' if sample_matches else ''
    payload['html_path'] = str(OUT_DIR / f'{file_prefix}weekly_report.html')
    payload['excel_path'] = str(OUT_DIR / f'{file_prefix}weekly_report.xlsx')
    Path(payload['html_path']).write_text(render_html(payload), encoding='utf-8')
    render_excel(payload, payload['excel_path'])
    return summary, payload['html_path'], payload['excel_path'], stats, getattr(client, 'total_tokens', 0) if client else 0

def load_sample(sample_id):
    data = json.loads((SAMPLE_DIR / f'{sample_id}.json').read_text(encoding='utf-8-sig'))
    return data['text'], str(SAMPLE_DIR / data['csv']), sample_id
