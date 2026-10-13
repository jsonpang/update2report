from collections import defaultdict
from datetime import date
import unicodedata

DONE_STATES = {'done', 'complete', 'completed', 'closed', '已完成', '完成'}
COMPLETION_RULE = ('Completed = extracted done items + CSV tasks with completion status; '
                   'deduplicated within each project by task name (Unicode NFKC, case, '
                   'whitespace and punctuation ignored; optional project prefix removed). '
                   'Owners do not affect identity. Different paraphrases remain separate '
                   'unless extraction maps them to the same task name. CSV may lag chat.')

def task_key(name, project):
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())
    key, prefix = normalize(name), normalize(project)
    return key[len(prefix):] if prefix and key.startswith(prefix) and key != prefix else key

def calculate_stats(updates, tasks, report_date, team_members):
    projects = defaultdict(lambda: {'completed': 0, 'blockers': 0})
    completions = defaultdict(dict)
    def add_done(project, task, source):
        key = task_key(task, project)
        if not key:
            return
        item = completions[project].setdefault(key, {'task': task.strip(), 'sources': []})
        if source not in item['sources']:
            item['sources'].append(source)
    updated_people = {u.person for u in updates}
    for task in tasks:
        project = task.get('project') or 'Unassigned'
        if (task.get('status') or '').strip().lower() in DONE_STATES:
            add_done(project, task.get('task', ''), 'CSV')
    unassigned_blockers = 0
    for update in updates:
        for task in update.done:
            add_done(update.project, task, 'Text: ' + update.person)
        if update.project.strip().lower() in {'unassigned', 'unknown'}:
            unassigned_blockers += len(update.blockers)
        else:
            projects[update.project]['blockers'] += len(update.blockers)
    for project, items in completions.items():
        projects[project]['completed'] = len(items)
    overdue = []
    for task in tasks:
        due = (task.get('due') or '').strip()
        try:
            due_date = date.fromisoformat(due[:10])
        except ValueError:
            continue
        status = (task.get('status') or '').strip().lower()
        if due_date < report_date and status not in DONE_STATES:
            overdue.append({**task, 'due': due_date.isoformat()})
    return {'projects': dict(projects), 'completion_items': {p:list(items.values()) for p,items in completions.items()}, 'overdue': overdue, 'no_updates': sorted(set(team_members) - updated_people), 'unassigned_blockers': unassigned_blockers}

def csv_task_rows(file_path):
    import csv
    if not file_path:
        return []
    with open(file_path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))
