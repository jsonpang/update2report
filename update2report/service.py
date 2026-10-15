import hashlib
import json
import tempfile
from datetime import date
from pathlib import Path
from .schemas import UpdateBundle
from .stats import calculate_stats, csv_task_rows
from .compose import compose_summary, validate_summary_numbers
from .evidence import missing_numbers, validate_identities, without_header
from .render_html import render_html
from .render_excel import render_excel
from .llm import LLMClient

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / 'samples'
OUT_DIR = ROOT / 'out'
MAX_INPUT_CHARS = 8000
CACHE_VERSION = 3


def input_fingerprint(text, csv_path):
    csv_text = Path(csv_path).read_text(encoding='utf-8-sig') if csv_path else ''
    return hashlib.sha256((text.strip() + '\nCSV\n' + csv_text).encode('utf-8')).hexdigest()


def cached_sample(text, csv_path, tone, sample_id):
    if not sample_id or sample_id not in {'sample-1','sample-2','sample-3','offline'}:
        return None
    sample_file = SAMPLE_DIR / f'{sample_id}.json'
    cache_file = SAMPLE_DIR / 'cache' / f'{sample_id}.json'
    try:
        sample = json.loads(sample_file.read_text(encoding='utf-8-sig'))
        expected_csv = SAMPLE_DIR / sample['csv']
        if input_fingerprint(text, csv_path) != input_fingerprint(sample['text'], expected_csv):
            return None
        cache = json.loads(cache_file.read_text(encoding='utf-8-sig'))
        if cache.get('version') != CACHE_VERSION or cache.get('fingerprint') != input_fingerprint(text, csv_path):
            return None
        if tone not in cache.get('summaries', {}):
            return None
        return cache
    except (OSError, ValueError, KeyError):
        return None


def is_cached_sample(text, csv_path, tone, sample_id):
    return cached_sample(text, csv_path, tone, sample_id) is not None


def validate_input(text, csv_path=None):
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError('Input limit: 8000 characters including optional CSV.')
    if not text.strip():
        raise ValueError('Please paste team updates first.')
    if csv_path:
        with open(csv_path, encoding='utf-8-sig') as handle:
            csv_text = handle.read(MAX_INPUT_CHARS + 1)
        if len(text) + len(csv_text) > MAX_INPUT_CHARS:
            raise ValueError('Input limit: 8000 characters including optional CSV.')


def generate_report(text, csv_path=None, tone='internal', sample_id=None, client=None, report_date=None):
    validate_input(text, csv_path)
    if tone not in {'internal','client-facing'}:
        raise ValueError('Please select a supported tone.')
    OUT_DIR.mkdir(exist_ok=True)
    report_date = report_date or date.today()
    tasks = csv_task_rows(csv_path)
    cached = cached_sample(text, csv_path, tone, sample_id)
    if cached:
        updates = [UpdateBundle.model_validate(row) for row in cached['updates']]
    else:
        client = client or LLMClient()
        from .extract import extract_updates
        updates = extract_updates(client, text, tasks, report_date)
    members = sorted({u.person for u in updates} | {r.get('owner','').strip() for r in tasks if r.get('owner','').strip()})
    stats = calculate_stats(updates, tasks, report_date, members)
    if cached:
        summary = cached['summaries'][tone]
        source = text + '\n' + json.dumps(tasks, ensure_ascii=False)
        validate_summary_numbers(summary, stats, source_text=source)
        validate_identities(summary, source)
        if missing_numbers(without_header(text), summary):
            raise ValueError('Cached summary is missing source numbers; refresh the sample cache.')
    else:
        summary = compose_summary(client, updates, stats, tone, source_text=text, tasks=tasks)
    payload = {'date':report_date.isoformat(), 'tone':tone, 'summary':summary, 'updates':updates, 'stats':stats}
    directory = Path(tempfile.mkdtemp(prefix='report-', dir=OUT_DIR))
    prefix = f'{sample_id}_' if cached else ''
    html_path = directory / f'{prefix}weekly_report.html'
    excel_path = directory / f'{prefix}weekly_report.xlsx'
    html_path.write_text(render_html(payload), encoding='utf-8')
    render_excel(payload, excel_path)
    return summary, str(html_path), str(excel_path), stats, getattr(client, 'total_tokens', 0) if client else 0


def load_sample(sample_id):
    if sample_id not in {'sample-1','sample-2','sample-3'}:
        raise ValueError('Please select a bundled sample.')
    data = json.loads((SAMPLE_DIR / f'{sample_id}.json').read_text(encoding='utf-8-sig'))
    return data['text'], str(SAMPLE_DIR / data['csv']), sample_id
