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

def test_stats_counts_completion_overdue_blockers_and_no_update():
    updates = [UpdateBundle.model_validate({'person':'Ari','project':'Atlas','done':['Ship'],'next':[],'blockers':['API'],'due_dates':[],'confidence':0.8})]
    rows = [{'task':'Write spec','owner':'Bea','project':'Atlas','due':'2026-10-10','status':'in progress'}, {'task':'Ship','owner':'Ari','project':'Atlas','due':'2026-10-12','status':'done'}]
    stats = calculate_stats(updates, rows, date(2026, 10, 13), ['Ari','Bea'])
    assert stats['projects']['Atlas']['completed'] == 1
    assert stats['projects']['Atlas']['blockers'] == 1
    assert [item['task'] for item in stats['overdue']] == ['Write spec']
    assert stats['no_updates'] == ['Bea']

def test_summary_rejects_numbers_not_in_stats():
    stats = {'projects': {'Atlas': {'completed': 2, 'blockers': 1}}, 'overdue': [{'task':'x'}], 'no_updates': []}
    validate_summary_numbers('Atlas completed 2 tasks and has 1 blocker.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas completed 3 tasks.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas completed three tasks.', stats)
    with pytest.raises(ValueError): validate_summary_numbers('Atlas had multiple completions.', stats)
