import json

from .schemas import UpdateBundle
import re

SYSTEM = "Extract only explicitly stated facts from the team update. Return only a JSON array, no Markdown, of objects with person, project, done, next, blockers, due_dates, confidence (0..1). Do not infer missing facts."

def extract_updates(client, text, tasks=None, report_date=None):
    context = (f'Report date: {report_date}. Keep relative dates verbatim; do not guess calendar dates. '
               f'CSV task names: {json.dumps(tasks or [], ensure_ascii=False)}. '
               'For done and next only, use exact CSV task names for matching facts. Use one canonical task name for repeated mentions, '
               'including multilingual paraphrases. done contains task names, not sentences. '
               'blockers must preserve the specific cause (e.g. waiting on client credentials or legal approval), not just a task name. '
               'Include every speaker, merge their messages by person/project. '
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
            return [UpdateBundle.model_validate(item) for item in data]
        except Exception as exc:
            last_error = exc
            prompt = f"{context}{text}\n\nYour previous response failed validation: {exc}. Return corrected JSON only. Previous response: {raw}"
    raise ValueError('The model returned an invalid update format after one correction attempt. Please try again or load a cached sample.') from None
