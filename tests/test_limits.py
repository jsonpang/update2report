import pytest
from update2report import service

def test_input_limit_checked_before_model_or_files():
    with pytest.raises(ValueError, match='8000'):
        service.generate_report('x' * 8001)

def test_session_limit_and_cached_samples_do_not_consume_quota(monkeypatch):
    import app
    monkeypatch.setattr(app,'is_cached_sample',lambda *args: args[0] == 'cached')
    monkeypatch.setattr(app,'generate_report',lambda *args,**kwargs: ('ok','html','xlsx',{},0))
    assert app.run_report('live',None,'internal',None,4)[-1] == 5
    result = app.run_report('live',None,'internal',None,5)
    assert result[-1] == 5 and 'limit' in result[0].lower()
    assert app.run_report('cached',None,'internal','sample-1',5)[-1] == 5

def test_failed_live_attempt_consumes_quota_and_hides_unexpected_errors(monkeypatch):
    import app
    monkeypatch.setattr(app,'is_cached_sample',lambda *args: False)
    def fail(*args,**kwargs): raise RuntimeError('secret-private-error')
    monkeypatch.setattr(app,'generate_report',fail)
    result = app.run_report('live',None,'internal',None,0)
    assert result[-1] == 1
    assert 'secret-private-error' not in result[0]

def test_load_sample_callback_returns_text_csv_and_id():
    import app
    text,path,sample_id = app.load_selected('sample-1')
    assert text and path.endswith('tasks-1.csv') and sample_id == 'sample-1'

def test_csv_counts_toward_total_input_limit(tmp_path):
    csv_file = tmp_path / 'large.csv'
    csv_file.write_text('task,owner,project,due,status\n' + 'x' * 7950,encoding='utf-8')
    with pytest.raises(ValueError, match='8000'):
        service.generate_report('x' * 100,csv_file)

def test_changed_csv_does_not_match_sample_cache(monkeypatch,tmp_path):
    samples = tmp_path / 'samples'
    (samples / 'cache').mkdir(parents=True)
    import json
    (samples / 'sample-1.json').write_text(json.dumps({'text':'same notes','csv':'tasks.csv'}),encoding='utf-8')
    original = samples / 'tasks.csv'
    original.write_text('task,owner,project,due,status\nShip,A,Atlas,,done\n',encoding='utf-8')
    (samples / 'cache' / 'sample-1.json').write_text(json.dumps({
        'version':service.CACHE_VERSION,'fingerprint':service.input_fingerprint('same notes',original),
        'updates':[], 'summaries':{'internal':'cached'}}),encoding='utf-8')
    changed = tmp_path / 'changed.csv'
    changed.write_text(original.read_text().replace('done','planned'),encoding='utf-8')
    monkeypatch.setattr(service,'SAMPLE_DIR',samples)
    assert service.is_cached_sample('same notes',original,'internal','sample-1')
    assert not service.is_cached_sample('same notes',changed,'internal','sample-1')
