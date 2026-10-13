"""Check generated HTML and print its summary and counted evidence for human review."""
import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from update2report.service import generate_report, load_sample


def main():
    for number in range(1,4):
        sample_id = f'sample-{number}'
        html = (ROOT / 'out' / f'{sample_id}_weekly_report.html').read_text(encoding='utf-8')
        assert '\ufffd' not in html and '<meta charset="utf-8">' in html
        cache = json.loads((ROOT / 'samples' / 'cache' / f'{sample_id}.json').read_text(encoding='utf-8'))
        text,csv_path,_ = load_sample(sample_id)
        for tone in ['internal','client-facing']:
            _,_,_,stats,tokens = generate_report(text,csv_path,tone,sample_id)
            assert tokens == 0, 'Unchanged samples must not call the model'
        snapshot = html.split('<h2>Project snapshot</h2>')[1].split('</table>')[0]
        rows = re.findall(r'<tr><td>(.*?)</td><td>(\d+)</td><td>(\d+)</td></tr>',snapshot)
        actual = {unescape(p):int(count) for p,count,_ in rows}
        fixture = json.loads((ROOT / 'samples' / f'{sample_id}.json').read_text(encoding='utf-8'))
        assert actual == fixture['expected_completed']
        assert actual == {p:v['completed'] for p,v in stats['projects'].items()}
        evidence = html.split('<h2>Counted completions</h2><ul>')[1].split('</ul>')[0]
        print(sample_id + ' summary: ' + cache['summaries']['internal'])
        for project,count in actual.items():
            items = stats['completion_items'][project]
            assert count == len(items)
            for item in items:
                assert unescape(item['task']) in unescape(evidence)
            print(f"  {project}: HTML={count}, evidence={len(items)}; " + '; '.join(item['task'] for item in items))
        assert not stats['no_updates']
    print('PASS: 9 project counts, UTF-8, six speakers, both tones offline.')


if __name__ == '__main__':
    main()
