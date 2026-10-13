from html import escape
from .stats import COMPLETION_RULE


def render_html(payload):
    projects = ''.join(f"<tr><td>{escape(name)}</td><td>{v['completed']}</td><td>{v['blockers']}</td></tr>" for name, v in payload['stats']['projects'].items())
    details = ''
    for item in payload['updates']:
        fields = ' | '.join(label + ': ' + ('; '.join(values) or 'None reported') for label, values in [('Done',item.done), ('Next',item.next), ('Blockers',item.blockers), ('Due',item.due_dates)])
        details += f'<li><b>{escape(item.person)}</b> &middot; {escape(item.project)} &mdash; {escape(fields)}</li>'
    evidence = ''.join(f"<li>{escape(project)}: {escape(item['task'])} ({escape(', '.join(item['sources']))})</li>" for project, items in payload['stats'].get('completion_items', {}).items() for item in items)
    risks = ''.join(f"<li>Overdue: {escape(str(t.get('task','')))} ({escape(str(t.get('due','')))}), {escape(str(t.get('owner','')))}</li>" for t in payload['stats']['overdue'])
    risks += ''.join(f'<li>No update: {escape(person)}</li>' for person in payload['stats']['no_updates'])
    risks += ''.join(f"<li>CSV status needs reconciliation: {escape(t.get('project',''))} / {escape(t.get('task',''))} is completed in evidence, but CSV says {escape(t.get('status',''))}.</li>" for t in payload['stats'].get('status_conflicts',[]))
    if payload['stats'].get('unassigned_blockers'):
        risks += f"<li>Blockers without an assigned project: {payload['stats']['unassigned_blockers']}</li>"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Northwind Studio Weekly Update</title>
<style>body{{font:16px/1.55 Arial,sans-serif;color:#172033;max-width:900px;margin:40px auto;padding:0 24px;background:#f5f7fb}}
main{{background:white;padding:36px;border-radius:18px;box-shadow:0 12px 40px #18234a14}}h1{{color:#263d78}}
.summary{{font-size:19px;background:#eef3ff;padding:20px;border-radius:12px}}table{{width:100%;border-collapse:collapse}}
td,th{{padding:12px;border-bottom:1px solid #e7eaf1;text-align:left}}@media print{{body{{margin:0;background:white}}main{{box-shadow:none}}}}</style>
</head><body><main><small>Northwind Studio &middot; Weekly update &middot; {escape(payload['date'])} &middot; {escape(payload['tone'])}</small>
<h1>Team progress</h1><p class="summary">{escape(payload['summary'])}</p>
<h2>Project snapshot</h2><table><tr><th>Project</th><th>Completed</th><th>Blockers</th></tr>{projects}</table>
<p>{escape(COMPLETION_RULE)}</p><h2>Counted completions</h2><ul>{evidence}</ul>
<h2>Team updates</h2><ul>{details}</ul><h2>Risks and follow-ups</h2><ul>{risks or '<li>No risks recorded.</li>'}</ul>
</main></body></html>'''
