import json

from .schemas import UpdateBundle

SYSTEM = "Extract only explicitly stated facts from the team update. Return a JSON array of objects with person, project, done, next, blockers, due_dates, confidence (0..1). Do not infer missing facts."

def extract_updates(client, text):
    prompt = text
    last_error = None
    for attempt in range(2):
        raw = client.complete(SYSTEM, prompt)
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError('Expected a JSON list')
            return [UpdateBundle.model_validate(item) for item in data]
        except Exception as exc:
            last_error = exc
            prompt = f"{text}\n\nYour previous response failed validation: {exc}. Return corrected JSON only. Previous response: {raw}"
    raise ValueError(f'Could not extract valid updates after retry: {last_error}')
