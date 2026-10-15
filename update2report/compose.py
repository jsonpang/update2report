import re
import json

from .evidence import numbers, missing_numbers, validate_identities

SYSTEM = "Write a concise weekly report summary from supplied evidence. Preserve every original quantity and percentage verbatim with its task and owner. Never invent people, projects, metrics, counts, percentages, dates, or numbers. Partial progress is in progress, never not started or completed."
UNQUANTIFIED_COUNT_WORDS = {'multiple', 'several', 'few', 'couple', 'dozen', 'dozens', 'pair'}
NUMBER_WORDS = {'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20}

def numeric_values(stats):
    allowed = set()
    def walk(value):
        if isinstance(value, bool) or value is None: return
        if isinstance(value, (int, float)):
            allowed.add(str(value))
            for word, number in NUMBER_WORDS.items():
                if value == number: allowed.add(word)
        elif isinstance(value, dict):
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(stats)
    return allowed

def validate_summary_numbers(summary, stats, numeric_free=False, source_text=None):
    allowed = numeric_values(stats) if source_text is None else set(numbers(source_text))
    if source_text is not None:
        allowed.update(word for word, value in NUMBER_WORDS.items() if str(value) in allowed)
    found = numbers(summary)
    unsupported = [value for value in found if (value.rstrip('%') if source_text is None else value) not in allowed]
    allowed_words = {word for word in NUMBER_WORDS if word in allowed}
    found_words = re.findall(r'\b(?:' + '|'.join(NUMBER_WORDS) + r')\b', summary.lower())
    unsupported.extend(word for word in found_words if word not in allowed_words)
    if numeric_free:
        unsupported.extend(found + found_words)
    unsupported.extend(re.findall(r'\b(?:' + '|'.join(sorted(UNQUANTIFIED_COUNT_WORDS)) + r')\b', summary.lower()))
    if unsupported:
        raise ValueError(f'Summary contains numbers absent from deterministic stats: {", ".join(unsupported)}')

# Some models emit narrow no-break spaces and hyphens that render cramped
# ("fixed\u202f3\u202fbugs"); reports should use plain characters.
_PLAIN = str.maketrans({'\u202f': ' ', '\u00a0': ' ', '\u2007': ' ', '\u2009': ' ', '\u2011': '-'})


def plain_spacing(text):
    return text.translate(_PLAIN)


def compose_summary(client, updates, stats, tone, source_text=None, tasks=None):
    grouped = {project:{'completed':stats.get('completion_items',{}).get(project,[]),
                       'updates':[u.model_dump() for u in updates if u.project == project]}
               for project in stats['projects']}
    extracted = json.dumps([{k:v for k,v in u.model_dump().items() if k != 'confidence'} for u in updates], ensure_ascii=False)
    source = (source_text if source_text is not None else extracted) + '\n' + json.dumps(
        (tasks or []) if source_text is not None else stats.get('completion_items', {}), ensure_ascii=False)
    required = source_text if source_text is not None else extracted
    user = (f"Tone: {tone}. Original source: {source}. Evidence grouped by project: {json.dumps(grouped,ensure_ascii=False)}. "
            "Write 2-4 concise sentences. For each project, mention all completed task names in completion_items, "
            "including CSV-only items. Keep pending work and blockers separate from completions. "
            "Use a separate sentence for each project. Never move a blocker to another project. "
            "Keep each blocker with the person and task it was reported with; never attach it to a teammate's work. "
            "Preserve blocker causes; do not reinterpret extraction confidence as deadline certainty. "
            "status_conflicts indicate stale CSV statuses to reconcile, not unfinished or overdue tasks. "
            "Never say a whole project is finished. Avoid unsupported judgments such as on track. "
            "Preserve every original number/percentage verbatim, attached to its original task and owner. "
            "Do not derive additional counts from task lists or statistics, even as number words. "
            "Mention in-progress tasks with their original percentage; partial completion means started, not still to come.")
    for attempt in range(2):
        summary = plain_spacing(client.complete(SYSTEM, user)).strip()
        missing = missing_numbers(required, summary)
        try:
            validate_summary_numbers(summary, stats, source_text=source)
            validate_identities(summary, source)
            for update in updates:
                for task in update.next:
                    for percentage in (value for value in numbers(task) if value.endswith('%')):
                        keywords = [word for word in re.findall(r'[A-Za-z][\w-]*', task)
                                    if word.lower() not in {'is', 'done', 'started', 'in', 'progress', 'complete', 'completed'}]
                        clauses = [clause for clause in re.split(r';|\n|(?<!\d)\.(?!\d)', summary)
                                   if percentage in numbers(clause) or any(re.search(r'\b' + re.escape(word) + r'\b', clause, re.I) for word in keywords)]
                        if any(re.search(r'\b(still to come|not started|unstarted|yet to start|will start|fully completed)\b', clause, re.I) for clause in clauses):
                            raise ValueError('In-progress task misrepresented as unstarted/completed: ' + task)
        except ValueError as exc:
            user += f"\nYour prior draft failed validation: {exc}. Correct the unsupported facts or task status."
            if missing:
                user += '\nMissing source numbers/percentages: ' + ', '.join(missing)
            continue
        if not missing:
            return summary
        user += '\nMissing source numbers/percentages: ' + ', '.join(missing) + '. Rewrite preserving these with their task, owner and progress.'
        if attempt == 1:
            # Copy original lines, retaining attribution and progress instead of
            # appending a contextless bag of numbers or silently dropping them.
            lines = [line for line in required.splitlines() if set(numbers(line)) & set(missing)]
            summary += '\n\nNumbers from source:\n' + '\n'.join('- ' + line for line in lines)
            validate_summary_numbers(summary, stats, source_text=source)
            validate_identities(summary, source)
            return summary
    raise ValueError('The model summary could not be verified after one correction attempt. Please try again or load a cached sample.')
