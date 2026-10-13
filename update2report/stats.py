from collections import defaultdict
from datetime import date, datetime

DONE_STATES = {'done', 'complete', 'completed', 'closed', '已完成', '完成'}

def calculate_stats(updates, tasks, report_date, team_members):
    projects = defaultdict(lambda: {'completed': 0, 'blockers': 0})
    updated_people = {u.person for u in updates}
    for task in tasks:
        project = task.get('project') or 'Unassigned'
        if (task.get('status') or '').strip().lower() in DONE_STATES:
            projects[project]['completed'] += 1
    unassigned_blockers = 0
    for update in updates:
        if update.project.strip().lower() in {'unassigned', 'unknown'}:
            unassigned_blockers += len(update.blockers)
        else:
            projects[update.project]['blockers'] += len(update.blockers)
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
    return {'projects': dict(projects), 'overdue': overdue, 'no_updates': sorted(set(team_members) - updated_people), 'unassigned_blockers': unassigned_blockers}

def csv_task_rows(file_path):
    import csv
    if not file_path:
        return []
    with open(file_path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))
