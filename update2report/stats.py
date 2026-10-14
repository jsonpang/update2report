from collections import defaultdict
from datetime import date
import unicodedata
import re

DONE_STATES = {'done', 'complete', 'completed', 'closed', '已完成', '完成'}
COMPLETION_RULE = ('Completed = extracted done items + CSV tasks with completion status; '
                   'deduplicated within each project by task name (Unicode NFKC, case, '
                   'whitespace and punctuation ignored; optional project prefix removed). '
                   'Owners do not affect identity. Different paraphrases remain separate '
                   'unless extraction maps them to the same task name. Bug-fix quantities '
                   'are task details, not additional completions. Missing projects use the owner. CSV may lag chat.')

def task_key(name, project):
    name = re.sub(r';\s*(?:fixed\s+)?\d+\s+bugs?(?:\s+fixed)?[.!]?\s*$', '', name, flags=re.I)
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())
    key, prefix = normalize(name), normalize(project)
    return key[len(prefix):] if prefix and key.startswith(prefix) and key != prefix else key

def calculate_stats(updates, tasks, report_date, team_members):
    projects = defaultdict(lambda: {'completed': 0, 'blockers': 0, 'owners': [], 'in_progress': [], 'blocker_details': []})
    completions = defaultdict(dict)
    def add_done(project, task, source):
        key = task_key(task, project)
        if not key:
            return
        item = completions[project].setdefault(key, {'task': task.strip(), 'sources': []})
        if source.startswith('Text:') and len(task.strip()) > len(item['task']):
            item['task'] = task.strip()
        if source not in item['sources']:
            item['sources'].append(source)
    updated_people = {u.person for u in updates}
    for task in tasks:
        project = task.get('project') or task.get('owner') or task.get('task') or 'Unknown'
        if task.get('owner') and task['owner'] not in projects[project]['owners']:
            projects[project]['owners'].append(task['owner'])
        if (task.get('status') or '').strip().lower() in DONE_STATES:
            add_done(project, task.get('task', ''), 'CSV')
    unassigned_blockers = 0
    for update in updates:
        if update.person not in projects[update.project]['owners']:
            projects[update.project]['owners'].append(update.person)
        projects[update.project]['in_progress'].extend(update.next)
        projects[update.project]['blocker_details'].extend(update.blockers)
        for task in update.done:
            add_done(update.project, task, 'Text: ' + update.person)
        if update.project.strip().lower() in {'unassigned', 'unknown'}:
            unassigned_blockers += len(update.blockers)
        else:
            projects[update.project]['blockers'] += len(update.blockers)
    for project, items in completions.items():
        projects[project]['completed'] = len(items)
    overdue = []
    status_conflicts = []
    for task in tasks:
        project = task.get('project') or task.get('owner') or task.get('task') or 'Unknown'
        status = (task.get('status') or '').strip().lower()
        if task_key(task.get('task',''),project) in completions.get(project,{}):
            if status not in DONE_STATES:
                status_conflicts.append(task)
            continue
        due = (task.get('due') or '').strip()
        try:
            due_date = date.fromisoformat(due[:10])
        except ValueError:
            continue
        status = (task.get('status') or '').strip().lower()
        if due_date < report_date and status not in DONE_STATES:
            overdue.append({**task, 'due': due_date.isoformat()})
    return {'projects': dict(projects), 'completion_items': {p:list(items.values()) for p,items in completions.items()}, 'status_conflicts': status_conflicts, 'overdue': overdue, 'no_updates': sorted(set(team_members) - updated_people), 'unassigned_blockers': unassigned_blockers}

def statistics_table(stats):
    def cell(value):
        from html import escape
        return escape(str(value)).replace('|', '&#124;').replace('\n', ' ')
    lines = ['| Project | Owner | Completed | In progress | Blockers |',
             '| --- | --- | --- | --- | --- |']
    for project, values in stats.get('projects', {}).items():
        completed = '; '.join(item['task'] for item in stats.get('completion_items', {}).get(project, []))
        fields = [project, ', '.join(values.get('owners', [])),
                  f"{values['completed']}: {completed}" if completed else values['completed'],
                  '; '.join(values.get('in_progress', [])) or '—',
                  f"{values['blockers']}: " + '; '.join(values['blocker_details'])
                  if values.get('blocker_details') else values['blockers']]
        lines.append('| ' + ' | '.join(cell(value) for value in fields) + ' |')
    return '\n'.join(lines)

def csv_task_rows(file_path):
    import csv
    if not file_path:
        return []
    with open(file_path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))
