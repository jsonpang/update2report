import json
from datetime import date

import pytest
from update2report.extract import extract_updates
from update2report.compose import compose_summary
from update2report.schemas import UpdateBundle
from update2report.stats import calculate_stats

TEXT = ('Alice: finished login page redesign, 2 bugs fixed, blocked on API spec.\n'
        'Bob: migrated billing cron to new scheduler; load test pending.\n'
        'Chen: wrote 5 onboarding docs; started FAQ, 40% done.')
ROWS = [dict(person='Alice', project='Unassigned', done=['login page redesign', '2 bugs fixed'], blockers=['API spec'], confidence=1),
        dict(person='Bob', project='Unassigned', done=['billing cron migration'], next=['load test pending'], confidence=1),
        dict(person='Chen', project='Unassigned', done=['5 onboarding docs'], next=['FAQ 40% done'], confidence=1)]

class Client:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.prompts = []
    def complete(self, system, user):
        self.prompts.append((system, user))
        return next(self.outputs)

def evidence():
    updates = [UpdateBundle(**row) for row in ROWS]
    return updates, calculate_stats(updates, [], date(2026, 10, 14), ['Alice', 'Bob', 'Chen'])

def test_extract_retries_lost_quantities_and_progress():
    bad = [{**row, 'done': ['onboarding docs'], 'next': ['FAQ pending']} if row['person'] == 'Chen' else row for row in ROWS]
    client = Client([json.dumps(bad), json.dumps(ROWS)])
    result = extract_updates(client, TEXT)
    assert len(client.prompts) == 2
    assert '40%' in client.prompts[1][1]
    assert result[2].next == ['FAQ 40% done']
    assert result[0].project == 'Alice'
    assert len(result[0].done) == 1 and '2' in result[0].done[0]

def test_summary_retries_missing_numbers_then_falls_back():
    updates, stats = evidence()
    client = Client(['Alice finished the redesign. Chen wrote docs.', 'Alice fixed 2 bugs. Chen wrote 5 onboarding docs.'])
    result = compose_summary(client, updates, stats, 'internal', source_text=TEXT)
    assert '40%' in client.prompts[1][1]
    assert 'Numbers from source:' in result
    assert all(value in result for value in ['2', '5', '40%'])
    assert 'FAQ' in result

def test_summary_accepts_quantities_and_keeps_progress():
    updates, stats = evidence()
    summary = 'Alice finished the login page redesign and fixed 2 bugs, blocked on API spec. Bob migrated billing cron; load test pending. Chen wrote 5 onboarding docs; FAQ is 40% done.'
    client = Client([summary])
    assert compose_summary(client, updates, stats, 'internal', source_text=TEXT) == summary
    assert len(client.prompts) == 1

@pytest.mark.parametrize('draft', ['Alice fixed 99 bugs.', 'Mallory completed the redesign.', 'Alice completed ProjectZeus.'])
def test_summary_rejects_invented_evidence(draft):
    updates, stats = evidence()
    with pytest.raises(ValueError):
        compose_summary(Client([draft, draft]), updates, stats, 'internal', source_text=TEXT)

def test_stats_group_by_owner_and_count_quantity_as_detail():
    _, stats = evidence()
    assert stats['projects']['Alice']['completed'] == 1
    assert 'Unassigned' not in stats['projects']
    assert stats['projects']['Chen']['in_progress'] == ['FAQ 40% done']

def test_statistics_ui_is_a_table(monkeypatch):
    import app
    _, stats = evidence()
    monkeypatch.setattr(app, 'is_cached_sample', lambda *args: True)
    monkeypatch.setattr(app, 'generate_report', lambda *args, **kwargs: ('ok', 'html', 'xlsx', stats, 0))
    table = app.run_report(TEXT, None, 'internal', None, 0)[3]
    assert '| Project | Owner | Completed | In progress | Blockers |' in table
    assert '40%' in table
    assert 'API spec' in table
    assert app.stats_out.__class__.__name__ == 'Markdown'

def test_percentage_cannot_be_rewritten_as_unstarted():
    updates, stats = evidence()
    bad = 'Alice fixed 2 bugs. Chen wrote 5 onboarding docs; FAQ 40% is still to come.'
    good = 'Alice fixed 2 bugs. Chen wrote 5 onboarding docs; FAQ is 40% done.'
    client = Client([bad, good])
    assert compose_summary(client, updates, stats, 'internal', source_text=TEXT) == good
    assert len(client.prompts) == 2

def test_missing_percentage_does_not_allow_unstarted_claim():
    updates, stats = evidence()
    bad = 'Alice fixed 2 bugs. Chen wrote 5 onboarding docs; FAQ is still to come.'
    good = 'Alice fixed 2 bugs. Chen wrote 5 onboarding docs; FAQ is 40% done.'
    client = Client([bad, good])
    assert compose_summary(client, updates, stats, 'internal', source_text=TEXT) == good
    assert 'misrepresented' in client.prompts[1][1]

def test_quantity_detail_does_not_double_count_csv_completion():
    updates, _ = evidence()
    tasks = [dict(owner='Alice', project='', task='login page redesign', status='done')]
    stats = calculate_stats(updates, tasks, date(2026, 10, 14), ['Alice', 'Bob', 'Chen'])
    assert stats['projects']['Alice']['completed'] == 1

def test_downloads_do_not_invent_a_company_name(tmp_path):
    from update2report.render_html import render_html
    from update2report.render_excel import render_excel
    from openpyxl import load_workbook
    updates, stats = evidence()
    payload = dict(date='2026-10-14', tone='internal', summary=TEXT, updates=updates, stats=stats)
    assert 'Northwind Studio' not in render_html(payload)
    path = tmp_path / 'report.xlsx'
    render_excel(payload, path)
    workbook = load_workbook(path, read_only=True)
    try:
        assert 'Northwind Studio' not in workbook['Summary']['A1'].value
    finally:
        workbook.close()
