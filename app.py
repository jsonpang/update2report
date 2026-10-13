import gradio as gr
from update2report.service import generate_report, load_sample

SAMPLES = ['sample-1', 'sample-2', 'sample-3']

def run_report(text, csv_file, tone, sample_id):
    try:
        summary, html_file, excel_file, stats, _tokens = generate_report(text or '', csv_file, tone, sample_id=sample_id)
        return summary, html_file, excel_file, str(stats)
    except Exception as exc:
        raise gr.Error(str(exc))

def load_selected(sample_id):
    text, csv_file = load_sample(sample_id)
    return text, csv_file, sample_id

with gr.Blocks(title='Update2Report') as demo:
    gr.Markdown('# Update2Report\nTurn messy team updates into a clear weekly report.')
    with gr.Row():
        sample = gr.Dropdown(['sample-1','sample-2','sample-3'], value='sample-1', label='Sample')
        load = gr.Button('Load sample')
    sample_state = gr.State(value=None)
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
    generate.click(run_report, inputs=[updates,tasks,tone,sample_state], outputs=[summary,html_out,excel_out,stats_out])

if __name__ == '__main__':
    demo.launch(server_name='127.0.0.1', server_port=7860)
