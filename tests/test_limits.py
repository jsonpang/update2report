import time
import pytest
from types import SimpleNamespace
from update2report import service


def test_input_limit_checked_before_model_or_files():
    with pytest.raises(ValueError, match='8000'):
        service.generate_report('x' * 8001)


def _make_request(ip='1.2.3.4', peer='127.0.0.1'):
    """Build a minimal gr.Request-like object for testing."""
    return SimpleNamespace(
        client=SimpleNamespace(host=peer),
        headers={'x-real-ip': ip},
    )


def test_session_limit_and_cached_samples_do_not_consume_quota(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: args[0] == 'cached')
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('ok', 'html', 'xlsx', {}, 0))
    monkeypatch.setenv('DEMO_LIVE', '1')
    req = _make_request('10.0.0.99')
    assert app.run_report('live', None, 'internal', None, 4, request=req)[-1] == 5
    result = app.run_report('live', None, 'internal', None, 5, request=req)
    assert result[-1] == 5 and 'limit' in result[0].lower()
    assert app.run_report('cached', None, 'internal', 'sample-1', 5, request=req)[-1] == 5


def test_failed_live_attempt_consumes_quota_and_hides_unexpected_errors(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: False)
    monkeypatch.setenv('DEMO_LIVE', '1')
    def fail(*args, **kwargs):
        raise RuntimeError('secret-private-error')
    monkeypatch.setattr(app, 'generate_report', fail)
    req = _make_request('10.0.0.100')
    result = app.run_report('live', None, 'internal', None, 0, request=req)
    assert result[-1] == 1
    assert 'secret-private-error' not in result[0]


def test_load_sample_callback_returns_text_csv_and_id():
    import app
    text, path, sample_id = app.load_selected('sample-1')
    assert text and path.endswith('tasks-1.csv') and sample_id == 'sample-1'


def test_csv_counts_toward_total_input_limit(tmp_path):
    csv_file = tmp_path / 'large.csv'
    csv_file.write_text('task,owner,project,due,status\n' + 'x' * 7950, encoding='utf-8')
    with pytest.raises(ValueError, match='8000'):
        service.generate_report('x' * 100, csv_file)


def test_changed_csv_does_not_match_sample_cache(monkeypatch, tmp_path):
    samples = tmp_path / 'samples'
    (samples / 'cache').mkdir(parents=True)
    import json
    (samples / 'sample-1.json').write_text(
        json.dumps({'text': 'same notes', 'csv': 'tasks.csv'}), encoding='utf-8')
    original = samples / 'tasks.csv'
    original.write_text('task,owner,project,due,status\nShip,A,Atlas,,done\n', encoding='utf-8')
    (samples / 'cache' / 'sample-1.json').write_text(json.dumps({
        'version': service.CACHE_VERSION,
        'fingerprint': service.input_fingerprint('same notes', original),
        'updates': [],
        'summaries': {'internal': 'cached'},
    }), encoding='utf-8')
    changed = tmp_path / 'changed.csv'
    changed.write_text(original.read_text().replace('done', 'planned'), encoding='utf-8')
    monkeypatch.setattr(service, 'SAMPLE_DIR', samples)
    assert service.is_cached_sample('same notes', original, 'internal', 'sample-1')
    assert not service.is_cached_sample('same notes', changed, 'internal', 'sample-1')


# ── Per-IP hourly rate limiting ────────────────────────────────────────────

def test_per_ip_hourly_limit(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: False)
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('ok', 'html', 'xlsx', {}, 0))
    monkeypatch.setenv('DEMO_LIVE', '1')
    app.DEMO_PER_IP_HOURLY = 3
    app.DEMO_DAILY_CAP = 1000
    app._ip_calls.clear()
    app._daily_calls.clear()
    ip = '192.168.1.1'
    req = _make_request(ip)
    for i in range(3):
        result = app.run_report('live text', None, 'internal', None, 0, request=req)
        assert result[0] == 'ok', f'Call {i+1} should succeed'
    # Fourth call should be rate-limited
    result = app.run_report('live text', None, 'internal', None, 0, request=req)
    assert 'Hourly limit' in result[0]
    # Different IP still works
    req2 = _make_request('192.168.1.2')
    result2 = app.run_report('live text', None, 'internal', None, 0, request=req2)
    assert result2[0] == 'ok'
    # Restore defaults
    app.DEMO_PER_IP_HOURLY = int(monkeypatch.getenv('DEMO_PER_IP_HOURLY', '5') if hasattr(monkeypatch, 'getenv') else '5')


# ── Daily global cap ───────────────────────────────────────────────────────

def test_daily_cap(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: False)
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('ok', 'html', 'xlsx', {}, 0))
    monkeypatch.setenv('DEMO_LIVE', '1')
    app.DEMO_PER_IP_HOURLY = 1000
    app.DEMO_DAILY_CAP = 2
    app._ip_calls.clear()
    app._daily_calls.clear()
    app._current_day[0] = app._today_cst()
    # Use different IPs so per-IP limit is not hit
    for i in range(2):
        req = _make_request(f'10.0.{i}.1')
        result = app.run_report('live text', None, 'internal', None, 0, request=req)
        assert result[0] == 'ok'
    req = _make_request('10.0.99.1')
    result = app.run_report('live text', None, 'internal', None, 0, request=req)
    assert 'Daily' in result[0] or 'capacity' in result[0].lower()


# ── Kill switch ────────────────────────────────────────────────────────────

def test_demo_live_kill_switch(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: False)
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('ok', 'html', 'xlsx', {}, 0))
    monkeypatch.setenv('DEMO_LIVE', '0')
    req = _make_request('10.0.0.200')
    result = app.run_report('live text', None, 'internal', None, 0, request=req)
    assert 'paused' in result[0].lower()
    assert result[-1] == 0  # live_count not incremented


def test_kill_switch_allows_cached_samples(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: True)
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('cached ok', 'html', 'xlsx', {}, 0))
    monkeypatch.setenv('DEMO_LIVE', '0')
    req = _make_request('10.0.0.201')
    result = app.run_report('cached text', None, 'internal', 'sample-1', 0, request=req)
    assert result[0] == 'cached ok'


# ── Offline degradation ───────────────────────────────────────────────────

def test_offline_fallback_on_runtime_error(monkeypatch):
    import app
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: False)
    monkeypatch.setenv('DEMO_LIVE', '1')
    app._ip_calls.clear()
    app._daily_calls.clear()
    app.DEMO_PER_IP_HOURLY = 100
    app.DEMO_DAILY_CAP = 1000
    def model_down(*args, **kwargs):
        raise RuntimeError('The model service is unavailable or timed out after one retry.')
    monkeypatch.setattr(app, 'generate_report', model_down)
    req = _make_request('10.0.0.202')
    result = app.run_report('live text', None, 'internal', None, 0, request=req)
    assert 'offline' in result[0].lower()
    assert 'cached samples still work' in result[0].lower()
    # Must NOT expose the internal RuntimeError message
    assert 'retry' not in result[0].lower()


# ── Client IP resolution ──────────────────────────────────────────────────

def test_client_ip_trusts_x_real_ip_only_from_localhost():
    import app
    # Behind nginx (peer=127.0.0.1) → trust X-Real-IP
    req = _make_request(ip='203.0.113.5', peer='127.0.0.1')
    assert app._get_client_ip(req) == '203.0.113.5'
    # Direct connection (peer != 127.0.0.1) → use peer, ignore header
    req2 = _make_request(ip='spoofed', peer='198.51.100.7')
    assert app._get_client_ip(req2) == '198.51.100.7'
    # No request at all
    assert app._get_client_ip(None) == '127.0.0.1'
