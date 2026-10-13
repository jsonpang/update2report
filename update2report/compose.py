import re
import json

SYSTEM = "Write a concise weekly report summary from the supplied evidence. Never invent metrics, counts, percentages, dates, or numbers. Do not include digits or date references in the summary; keep it numeric-free."
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

def validate_summary_numbers(summary, stats, numeric_free=False):
    allowed = numeric_values(stats)
    found = re.findall(r'(?<![\w.])\d+(?:\.\d+)?%?', summary)
    unsupported = [value for value in found if value.rstrip('%') not in allowed]
    allowed_words = {word for word in NUMBER_WORDS if word in allowed}
    found_words = re.findall(r'\b(?:' + '|'.join(NUMBER_WORDS) + r')\b', summary.lower())
    unsupported.extend(word for word in found_words if word not in allowed_words)
    if numeric_free:
        unsupported.extend(found + found_words)
    unsupported.extend(re.findall(r'\b(?:' + '|'.join(sorted(UNQUANTIFIED_COUNT_WORDS)) + r')\b', summary.lower()))
    if unsupported:
        raise ValueError(f'Summary contains numbers absent from deterministic stats: {", ".join(unsupported)}')

def compose_summary(client, updates, stats, tone):
    grouped = {project:{'completed':stats.get('completion_items',{}).get(project,[]),
                       'updates':[u.model_dump() for u in updates if u.project == project]}
               for project in stats['projects']}
    user = (f"Tone: {tone}. Evidence grouped by project: {json.dumps(grouped,ensure_ascii=False)}. Deterministic statistics: {stats}. "
            "Write 2-4 concise sentences. For each project, mention all completed task names in completion_items, "
            "including CSV-only items. Keep pending work and blockers separate from completions. "
            "Use a separate sentence for each project. Never move a blocker to another project. "
            "Preserve blocker causes; do not reinterpret extraction confidence as deadline certainty. "
            "status_conflicts indicate stale CSV statuses to reconcile, not unfinished or overdue tasks. "
            "Never say a whole project is finished. Avoid unsupported judgments such as on track. "
            "Do not use digits or number words, even for counts found in statistics.")
    last_error = None
    for attempt in range(2):
        summary = client.complete(SYSTEM, user).strip()
        try:
            validate_summary_numbers(summary, stats, numeric_free=True)
            return summary
        except ValueError as exc:
            last_error = str(exc)
            user += f"\nYour prior draft failed validation: {exc}. Rewrite without unsupported numbers."
    raise ValueError('The model summary could not be verified after one correction attempt. Please try again or load a cached sample.')
