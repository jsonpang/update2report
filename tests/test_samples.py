import json
from pathlib import Path
import pytest
from update2report import service

@pytest.mark.parametrize('number',[1,2,3])
def test_bundled_samples_both_tones_are_offline_and_match_expected_counts(number,monkeypatch,tmp_path):
    def forbidden_model():
        raise AssertionError('An unchanged bundled sample must not call the model')
    monkeypatch.setattr(service,'LLMClient',forbidden_model)
    monkeypatch.setattr(service,'OUT_DIR',tmp_path / 'out')
    sample_id = f'sample-{number}'
    text,csv_path,_ = service.load_sample(sample_id)
    sample = json.loads((service.SAMPLE_DIR / f'{sample_id}.json').read_text(encoding='utf-8'))
    cache_before = (service.SAMPLE_DIR / 'cache' / f'{sample_id}.json').read_bytes()
    for tone in ['internal','client-facing']:
        summary,html,excel,stats,tokens = service.generate_report(text,csv_path,tone,sample_id)
        assert tokens == 0 and not stats['no_updates']
        assert {p:v['completed'] for p,v in stats['projects'].items()} == sample['expected_completed']
        assert len({u['person'] for u in json.loads(cache_before)['updates']}) == 6
        assert Path(html).exists() and Path(excel).exists()
        assert '\ufffd' not in Path(html).read_text(encoding='utf-8')
    assert (service.SAMPLE_DIR / 'cache' / f'{sample_id}.json').read_bytes() == cache_before
