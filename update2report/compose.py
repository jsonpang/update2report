import re

SYSTEM = "Write a concise weekly report summary from the supplied evidence. Never invent metrics, counts, percentages, dates, or numbers. Use only numeric values explicitly present in the deterministic statistics."

def numeric_values(stats):
    allowed = set()
    def walk(value):
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            allowed.add(str(value))
        elif isinstance(value, dict):
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(stats)
    return allowed

def validate_summary_numbers(summary, stats):
    allowed = numeric_values(stats)
    found = re.findall(r'(?<![\w.])\d+(?:\.\d+)?%?', summary)
    invalid = [value for value in found if value.rstrip('%') not in allowed]
    if invalid:
        raise ValueError(f'Summary contains numbers absent from deterministic stats: {", ".join(invalid)}')

def compose_summary(client, updates, stats, tone):
    user = f"Tone: {tone}. Evidence: {[u.model_dump() for u in updates]}. Deterministic statistics: {stats}. Write 2-4 concise sentences."
    for attempt in range(2):
        summary = client.complete(SYSTEM, user).strip()
        try:
            validate_summary_numbers(summary, stats)
            return summary
        except ValueError as exc:
            user += f"\nYour prior draft failed validation: {exc}. Rewrite without unsupported numbers."
    raise ValueError('Unable to produce a summary with valid numbers')
