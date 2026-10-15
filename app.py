import os
import sys
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import gradio as gr
from update2report.service import generate_report, load_sample, is_cached_sample, validate_input
from update2report.stats import statistics_table

SAMPLES = ['sample-1', 'sample-2', 'sample-3']
load_dotenv(Path(__file__).with_name('.env'), override=False)

# ---------------------------------------------------------------------------
# Demo rate-limiting (in-memory, single process)
# ---------------------------------------------------------------------------
DEMO_PER_IP_HOURLY = int(os.getenv('DEMO_PER_IP_HOURLY', '5'))
DEMO_DAILY_CAP = int(os.getenv('DEMO_DAILY_CAP', '60'))
_CST = timezone(timedelta(hours=8))

_ip_calls: dict[str, list[float]] = defaultdict(list)  # ip -> [timestamp, ...]
_daily_calls: list[float] = []                          # [timestamp, ...]
_current_day: list[str] = ['']                          # [YYYY-MM-DD] for reset

# ---------------------------------------------------------------------------
# Structured stdout logger
# ---------------------------------------------------------------------------
_log = logging.getLogger('update2report.demo')
_log.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter('%(message)s'))
_log.addHandler(_handler)


def _get_client_ip(request: gr.Request | None) -> str:
    """Return the real client IP.

    Trust X-Real-IP only when the direct connection comes from 127.0.0.1
    (i.e. behind nginx on the same host). Otherwise use the peer address.
    """
    if request is None:
        return '127.0.0.1'
    peer = request.client.host if request.client else '127.0.0.1'
    if peer == '127.0.0.1':
        forwarded = request.headers.get('x-real-ip')
        if forwarded:
            return forwarded
    return peer


def _today_cst() -> str:
    return datetime.now(_CST).strftime('%Y-%m-%d')


def _prune_hourly(ip: str, now: float) -> int:
    """Remove entries older than 1 hour and return remaining count."""
    cutoff = now - 3600
    _ip_calls[ip] = [t for t in _ip_calls[ip] if t > cutoff]
    return len(_ip_calls[ip])


def _prune_daily(now: float) -> int:
    """Reset on new UTC+8 day; return today's count."""
    today = _today_cst()
    if _current_day[0] != today:
        _daily_calls.clear()
        _current_day[0] = today
    return len(_daily_calls)


def _check_rate_limit(ip: str) -> str | None:
    """Return a user-facing message if rate-limited, else None."""
    now = time.time()
    if _prune_hourly(ip, now) >= DEMO_PER_IP_HOURLY:
        return (f'Hourly limit reached ({DEMO_PER_IP_HOURLY} live generations per IP). '
                'Load a cached sample to continue exploring.')
    if _prune_daily(now) >= DEMO_DAILY_CAP:
        return (f'Daily demo capacity reached ({DEMO_DAILY_CAP} total). '
                'Load a cached sample to continue exploring.')
    return None


def _record_call(ip: str) -> None:
    now = time.time()
    _ip_calls[ip].append(now)
    _daily_calls.append(now)


def _log_call(ip: str, result: str, tokens: int) -> None:
    ts = datetime.now(_CST).strftime('%Y-%m-%d %H:%M:%S')
    _log.info('live_call time=%s ip=%s result=%s tokens=%d', ts, ip, result, tokens)


def launch_config():
    return {
        'server_name': os.getenv('GRADIO_SERVER_NAME', '127.0.0.1'),
        'server_port': int(os.getenv('GRADIO_SERVER_PORT', '7860')),
    }


def run_report(text, csv_file, tone, sample_id, live_count=0, request: gr.Request = None):
    text = text or ''
    ip = _get_client_ip(request)
    try:
        validate_input(text, csv_file)
        cached = is_cached_sample(text, csv_file, tone, sample_id)
        if not cached:
            # Kill switch
            if os.getenv('DEMO_LIVE', '1') == '0':
                return ('Live generation is paused; cached samples still work.',
                        None, None, '', live_count)
            # Session limit (preserved)
            if live_count >= 5:
                return ('Session limit reached (5 live attempts). '
                        'Load a cached sample to continue.', None, None, '', live_count)
            # Per-IP / daily rate limit
            limit_msg = _check_rate_limit(ip)
            if limit_msg:
                _log_call(ip, 'limited', 0)
                return limit_msg, None, None, '', live_count
            live_count += 1
            _record_call(ip)
        summary, html_file, excel_file, stats, _tokens = generate_report(
            text, csv_file, tone, sample_id=sample_id)
        if not cached:
            _log_call(ip, 'ok', _tokens)
        return summary, html_file, excel_file, statistics_table(stats), live_count
    except ValueError as exc:
        gr.Warning(str(exc))
        return str(exc), None, None, '', live_count
    except RuntimeError as exc:
        # LLM connectivity / timeout errors raised by LLMClient
        msg = str(exc)
        if 'unavailable' in msg.lower() or 'timed out' in msg.lower():
            _log_call(ip, 'offline', 0)
            offline_msg = 'Live model is temporarily offline; cached samples still work.'
            gr.Warning(offline_msg)
            return (f'> ⚠️ **{offline_msg}**',
                    None, None, '', live_count)
        _log_call(ip, 'error', 0)
        err_msg = 'Generation failed. Please check model settings or try a cached sample.'
        gr.Warning(err_msg)
        return (f'> ⚠️ **{err_msg}**',
                None, None, '', live_count)
    except Exception:
        _log_call(ip, 'error', 0)
        err_msg = 'Generation failed. Please check model settings or try a cached sample.'
        gr.Warning(err_msg)
        return (f'> ⚠️ **{err_msg}**',
                None, None, '', live_count)


def load_selected(sample_id):
    return load_sample(sample_id)

# ---------------------------------------------------------------------------
# Live-paused banner
# ---------------------------------------------------------------------------
_live_banner = ''
if os.getenv('DEMO_LIVE', '1') == '0':
    _live_banner = '\n\n> **Live generation is paused; cached samples still work.**\n'

with gr.Blocks(title='Update2Report', analytics_enabled=False) as demo:
    gr.Markdown('# Update2Report\nTurn messy team updates into a clear weekly report.' + _live_banner)
    with gr.Row():
        sample = gr.Dropdown(['sample-1','sample-2','sample-3'], value='sample-1', label='Sample')
        load = gr.Button('Load sample')
    sample_state = gr.State(value=None)
    live_count = gr.State(value=0)
    gr.Markdown('Fictional samples use cached results. Live generation: 5 attempts per session; 8000 characters including CSV. Editing a sample uses live generation.')
    updates = gr.Textbox(label='Team updates', lines=12, placeholder='Paste chat or stand-up notes...')
    tasks = gr.File(label='Optional task CSV', file_types=['.csv'], type='filepath')
    tone = gr.Radio(['client-facing','internal'], value='internal', label='Tone')
    generate = gr.Button('Generate report', variant='primary')
    summary = gr.Markdown(label='Summary')
    with gr.Row():
        html_out = gr.File(label='Download HTML report')
        excel_out = gr.File(label='Download Excel workbook')
    stats_out = gr.Markdown(label='Deterministic statistics')
    load.click(load_selected, inputs=sample, outputs=[updates,tasks,sample_state])
    generate.click(run_report, inputs=[updates,tasks,tone,sample_state,live_count], outputs=[summary,html_out,excel_out,stats_out,live_count], concurrency_limit=1, api_name=False)

if __name__ == '__main__':
    demo.queue(max_size=16).launch(**launch_config(), show_error=False, max_file_size='32kb')
