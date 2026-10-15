import json

from .schemas import UpdateBundle
import re
from .evidence import missing_numbers, numbers

SYSTEM = "Extract only explicitly stated facts from the team update. Return only a JSON array, no Markdown, of objects with person, project, done, next, blockers, due_dates, confidence (0..1). Do not infer missing facts."

# Words that name what a project is rather than which project it is.
GENERIC_PROJECT_WORDS = {'app', 'application', 'project', 'service', 'site', 'website', 'web', 'team', 'platform', 'product'}


def project_key(name):
    words = re.findall(r'\w+', name.casefold())
    core = [w for w in words if w not in GENERIC_PROJECT_WORDS]
    return ' '.join(core or words)


def unify_projects(updates):
    """Merge spellings like "Harbor" and "Harbor app" into one project.

    The most frequently used spelling wins; ties go to the shorter one.
    Purely deterministic, so statistics stay reproducible."""
    groups = {}
    for u in updates:
        groups.setdefault(project_key(u.project), []).append(u.project)
    canonical = {}
    for names in groups.values():
        best = min(set(names), key=lambda n: (-names.count(n), len(n), n))
        for n in names:
            canonical[n] = best
    for u in updates:
        u.project = canonical[u.project]
    return updates


def extract_updates(client, text, tasks=None, report_date=None):
    context = (f'Report date: {report_date}. Keep relative dates verbatim; do not guess calendar dates. '
               f'CSV task names: {json.dumps(tasks or [], ensure_ascii=False)}. '
               'For done and next only, use exact CSV task names for matching facts. Use one canonical task name for repeated mentions, '
               'including multilingual paraphrases. Preserve every source quantity and percentage in task text. '
               'For tasks with no quantity, done and next must contain ONLY the exact CSV canonical name, '
               'without completion verbs, status suffixes or pending work appended. '
               'Never put next steps or blockers into done. Header/report dates are context, not personal due_dates. '
               'If a CSV canonical name drops a number, attach the original quantity as task detail. '
               'Keep partial percentage progress in next, never in done or as not started. '
               'Bug-fix quantities are details of the associated completed task, not extra completion items. '
               'Use the person as project when no project is explicitly named; never invent a project or speaker. '
               'blockers must preserve the specific cause (e.g. waiting on client credentials or legal approval), not just a task name. '
               'Include every speaker, merge their messages by person/project. '
               'Use one consistent name per project; do not write both "Harbor" and "Harbor app" for the same project. '
               'Waiting on someone is a blocker; mostly done is not done. Never infer completion from CSV.\n')
    prompt = context + text
    last_error = None
    for attempt in range(2):
        raw = client.complete(SYSTEM, prompt)
        try:
            fenced = re.fullmatch(r'\s*```(?:json)?\s*\n?([\s\S]*?)\n?```\s*', raw, re.IGNORECASE)
            data = json.loads(fenced.group(1) if fenced else raw)
            if not isinstance(data, list):
                raise ValueError('Expected a JSON list')
            updates = [UpdateBundle.model_validate(item) for item in data]
            evidence = json.dumps([{key: value for key, value in u.model_dump().items()
                                    if key != 'confidence'} for u in updates], ensure_ascii=False)
            task_text = '\n'.join(line for line in text.splitlines()
                                  if not (line.startswith('[') and 'report date' in line.lower()))
            missing = missing_numbers(task_text, evidence)
            if missing:
                raise ValueError('Missing source numbers/percentages: ' + ', '.join(missing))
            source = text + json.dumps(tasks or [], ensure_ascii=False)
            for update in updates:
                for name in (update.person, update.project):
                    if name not in {'Unknown', 'Unassigned'} and name.casefold() not in source.casefold():
                        raise ValueError('Identity absent from source: ' + name)
            if set(numbers(evidence)) - set(numbers(source)):
                raise ValueError('Extracted numbers absent from source')
            return unify_projects(updates)
        except Exception as exc:
            last_error = exc
            prompt = f"{context}{text}\n\nYour previous response failed validation: {exc}. Return corrected JSON only. Previous response: {raw}"
    raise ValueError('The model returned an invalid update format after one correction attempt. Please try again or load a cached sample.') from None
