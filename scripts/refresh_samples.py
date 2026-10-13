"""Real model runs for fictional examples; never reuse or fabricate cached results."""
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from update2report.llm import LLMClient
from update2report.extract import extract_updates
from update2report.compose import compose_summary
from update2report.stats import calculate_stats, csv_task_rows
from update2report.service import CACHE_VERSION, input_fingerprint, generate_report


def main():
    load_dotenv(ROOT / '.env', override=False)
    records = []
    (ROOT / 'out').mkdir(exist_ok=True)
    for number in range(1, 4):
        sample_id = f'sample-{number}'
        sample = json.loads((ROOT / 'samples' / f'{sample_id}.json').read_text(encoding='utf-8-sig'))
        csv_path = ROOT / 'samples' / sample['csv']
        client = LLMClient()
        started = time.perf_counter()
        record = {'sample':sample_id, 'model':client.model, 'report_date':'2026-10-13'}
        try:
            rows = csv_task_rows(csv_path)
            updates = extract_updates(client, sample['text'], rows, date(2026,10,13))
            (ROOT / 'out' / f'{sample_id}-round2-extraction.json').write_text(
                json.dumps([u.model_dump() for u in updates],ensure_ascii=False,indent=2),encoding='utf-8')
            members = sorted({r['owner'] for r in rows})
            stats = calculate_stats(updates, rows, date(2026,10,13), members)
            expected = sample['expected_completed']
            actual = {p:v['completed'] for p,v in stats['projects'].items()}
            record.update(stats=stats, actual_completed=actual, expected_completed=expected)
            if actual != expected or stats['no_updates']:
                raise ValueError('Sample extraction failed count or speaker coverage check')
            summaries = {tone:compose_summary(client, updates, stats, tone)
                         for tone in ['internal','client-facing']}
            cache = {'version':CACHE_VERSION, 'fingerprint':input_fingerprint(sample['text'],csv_path),
                     'updates':[u.model_dump() for u in updates], 'summaries':summaries,
                     'report_date':'2026-10-13', 'model':client.model}
            (ROOT / 'samples' / 'cache' / f'{sample_id}.json').write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),encoding='utf-8')
            _, html, excel, checked_stats, tokens = generate_report(
                sample['text'], csv_path, 'internal', sample_id, report_date=date(2026,10,13))
            assert tokens == 0 and checked_stats == stats
            for source, extension in [(html,'html'),(excel,'xlsx')]:
                shutil.copyfile(source, ROOT / 'out' / f'{sample_id}_weekly_report.{extension}')
            record.update(status='ok',stats=stats,summaries=summaries)
        except Exception:
            record['status'] = 'failed'
            raise
        finally:
            record.update(elapsed_seconds=round(time.perf_counter()-started,3),total_tokens=client.total_tokens)
            records.append(record)
            (ROOT / 'out' / 'round2-live-metrics.json').write_text(
                json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            (ROOT / 'samples' / 'cache' / 'round2-live-metrics.json').write_text(
                json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f"{sample_id}: {record['status']}, {record['elapsed_seconds']}s, {client.total_tokens} tokens",flush=True)


if __name__ == '__main__':
    main()
