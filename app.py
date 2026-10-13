import os
from pathlib import Path
from dotenv import load_dotenv
import gradio as gr
from update2report.service import generate_report, load_sample, is_cached_sample, validate_input

SAMPLES = ['sample-1', 'sample-2', 'sample-3']
load_dotenv(Path(__file__).with_name('.env'), override=False)

def launch_config():
    return {'server_name':'0.0.0.0' if os.getenv('SPACE_ID') else '127.0.0.1', 'server_port':7860}

def run_report(text, csv_file, tone, sample_id, live_count=0):
    text = text or ''
    try:
        validate_input(text, csv_file)
        cached = is_cached_sample(text, csv_file, tone, sample_id)
        if not cached:
            if live_count >= 5:
                return 'Session limit reached (5 live attempts). Load a cached sample to continue.', None, None, '', live_count
            live_count += 1
        summary, html_file, excel_file, stats, _tokens = generate_report(text, csv_file, tone, sample_id=sample_id)
        return summary, html_file, excel_file, str(stats), live_count
    except ValueError as exc:
        return str(exc), None, None, '', live_count
    except Exception:
        return 'Generation failed. Please check model settings or try a cached sample.', None, None, '', live_count

def load_selected(sample_id):
    return load_sample(sample_id)

with gr.Blocks(title='Update2Report', analytics_enabled=False) as demo:
    gr.Markdown('# Update2Report\nTurn messy team updates into a clear weekly report.')
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
    stats_out = gr.Textbox(label='Deterministic statistics', lines=6)
    load.click(load_selected, inputs=sample, outputs=[updates,tasks,sample_state])
    generate.click(run_report, inputs=[updates,tasks,tone,sample_state,live_count], outputs=[summary,html_out,excel_out,stats_out,live_count], concurrency_limit=1, api_name=False)

if __name__ == '__main__':
    demo.queue(max_size=16).launch(**launch_config(), show_error=False, max_file_size='32kb')
