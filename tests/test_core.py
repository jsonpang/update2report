from datetime import date

import pytest

from update2report.extract import extract_updates
from update2report.schemas import UpdateBundle
from update2report.stats import calculate_stats
from update2report.compose import validate_summary_numbers

class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []
    def complete(self, system, user):
        self.prompts.append((system, user))
        return self.outputs.pop(0)

def test_extract_retries_invalid_json_and_feeds_error_back():
    client = FakeClient(['not json', '[{"person":"Ari","project":"Atlas","done":["Ship"],"next":[],"blockers":[],"due_dates":[],"confidence":0.8}]'])
    result = extract_updates(client, 'Ari shipped Atlas')
    assert result[0].person == 'Ari'
    assert len(client.prompts) == 2
    assert 'not json' in client.prompts[1][1]

def test_extract_normalizes_scalar_null_fields_and_missing_identity():
    client = FakeClient(['[{"person":null,"project":null,"done":"Ship","next":null,"blockers":null,"due_dates":null,"confidence":0.8}]'])
    result = extract_updates(client, 'Someone shipped something')
    assert result[0].done == ['Ship']
    assert result[0].next == []
    assert result[0].person == 'Unknown'
    assert result[0].project == 'Unassigned'

def test_extract_accepts_valid_json_inside_a_single_markdown_fence():
    client = FakeClient(['```json\n[{"person":"Mira","project":"Atlas","done":["QA checklist"],"confidence":0.9}]\n```'])
    result = extract_updates(client,'Mira [Atlas]: QA checklist done')
    assert result[0].done == ['QA checklist']
    assert len(client.prompts) == 1

def test_stats_counts_completion_overdue_blockers_and_no_update():
    updates = [UpdateBundle.model_validate({'person':'Ari','project':'Atlas','done':['Ship'],'next':[],'blockers':['API'],'due_dates':[],'confidence':0.8})]
    rows = [{'task':'Write spec','owner':'Bea','project':'Atlas','due':'2026-10-10','status':'in progress'}, {'task':'Ship','owner':'Ari','project':'Atlas','due':'2026-10-12','status':'done'}]
    stats = calculate_stats(updates, rows, date(2026, 10, 13), ['Ari','Bea'])
    assert stats['projects']['Atlas']['completed'] == 1
    assert stats['projects']['Atlas']['blockers'] == 1
    assert [item['task'] for item in stats['overdue']] == ['Write spec']
    assert stats['no_updates'] == ['Bea']
    unknown = UpdateBundle.model_validate({'person':'Cai','project':'Unassigned','done':[],'next':[],'blockers':['Need owner'],'due_dates':[],'confidence':0.5})
    stats = calculate_stats([*updates, unknown], rows, date(2026, 10, 13), ['Ari','Bea','Cai'])
    assert 'Unassigned' not in stats['projects']
    assert stats['unassigned_blockers'] == 0
    assert stats['projects']['Cai']['blockers'] == 1

def test_summary_rejects_numbers_not_in_stats():
    stats = {'projects': {'Atlas': {'completed': 2, 'blockers': 1}}, 'overdue': [{'task':'x'}], 'no_updates': []}
    validate_summary_numbers('Atlas completed 2 tasks and has 1 blocker.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas completed 3 tasks.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas completed three tasks.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas had multiple completions.', stats)

def test_text_only_completions_and_repeated_mentions_are_counted_once():
    updates = [UpdateBundle(person=person, project='Atlas',
                            done=['Landing page', 'QA checklist'], confidence=0.9)
               for person in ['Mira', 'Lee']]
    rows = [{'project':'Atlas','task':'Atlas QA checklist','status':'in progress'},
            {'project':'Atlas','task':' landing PAGE! ','status':'完成'},
            {'project':'Atlas','task':'Export button','status':'done'},
            {'project':'Atlas','task':'Export button','status':'completed'}]
    stats = calculate_stats(updates, rows, date(2026,10,13), ['Mira','Lee'])
    assert stats['projects']['Atlas']['completed'] == 3
    assert len(stats['completion_items']['Atlas']) == 3
    text_only = calculate_stats(updates, [], date(2026,10,13), ['Mira','Lee'])
    assert text_only['projects']['Atlas']['completed'] == 2

def test_completion_identity_keeps_projects_separate():
    updates = [UpdateBundle(person='A',project=p,done=['Ship'],confidence=1)
               for p in ['Atlas','Beacon']]
    stats = calculate_stats(updates, [], date(2026,10,13), ['A'])
    assert [v['completed'] for v in stats['projects'].values()] == [1,1]

def test_composer_retries_numbers_even_if_another_project_has_that_count():
    from update2report.compose import compose_summary
    stats = {'projects':{'Atlas':{'completed':1,'blockers':0},'Cedar':{'completed':2,'blockers':0}}}
    client = FakeClient(['Atlas completed two tasks.','Atlas finished its landing page.'])
    assert compose_summary(client,[],stats,'internal', source_text='Atlas finished its landing page. Cedar finished QA.') == 'Atlas finished its landing page.'
    assert len(client.prompts) == 2

def test_text_completion_prevents_stale_csv_overdue_but_preserves_conflict():
    update = UpdateBundle(person='Mira',project='Atlas',done=['QA checklist'],confidence=1)
    row = {'project':'Atlas','task':'QA checklist','status':'in progress','due':'2026-10-12'}
    stats = calculate_stats([update],[row],date(2026,10,13),['Mira'])
    assert stats['projects']['Atlas']['completed'] == 1
    assert stats['overdue'] == []
    assert stats['status_conflicts'] == [row]


def test_project_spellings_are_unified():
    from update2report.extract import unify_projects
    from update2report.schemas import UpdateBundle
    ups = [UpdateBundle(person='Dana', project='Harbor app', done=['invoice export'], confidence=1),
           UpdateBundle(person='Eli', project='Harbor', next=['push queue'], confidence=1),
           UpdateBundle(person='Gus', project='harbor', next=['docs'], confidence=1),
           UpdateBundle(person='Fay', project='Lumen', done=['articles'], confidence=1)]
    assert [u.project for u in unify_projects(ups)] == ['Harbor', 'Harbor', 'Harbor', 'Lumen']


def test_distinct_projects_stay_separate():
    from update2report.extract import unify_projects
    from update2report.schemas import UpdateBundle
    ups = [UpdateBundle(person='A', project='Harbor Billing', confidence=1), UpdateBundle(person='B', project='Harbor', confidence=1)]
    assert [u.project for u in unify_projects(ups)] == ['Harbor Billing', 'Harbor']


def test_summary_spacing_is_plain():
    from update2report.compose import plain_spacing
    assert plain_spacing('fixed 3 bugs; push‑notifications') == 'fixed 3 bugs; push-notifications'
