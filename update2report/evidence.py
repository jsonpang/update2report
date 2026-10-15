"""Validate facts against original input rather than generated statistics."""
import re

NUMBER_PATTERN = r'\d+(?:[.,]\d+)*%?'

def numbers(text):
    return list(dict.fromkeys(re.findall(NUMBER_PATTERN, text)))

def missing_numbers(source, output):
    return [value for value in numbers(source) if value not in set(numbers(output))]

def validate_identities(output, source):
    starters = set(('The A An In On For With While However Meanwhile Additionally '
                    'Completed Finished Migrated Wrote Fixed Started Pending Blocked '
                    'Progress Work Team This These They All No Next Summary '
                    'Internal Client Report Numbers Source Done Still Chinese English').lower().split())
    known = set(re.findall(r'\b[\w-]+\b', source.casefold()))
    for short, full in [('mon', 'monday'), ('tue', 'tuesday'), ('wed', 'wednesday'),
                        ('thu', 'thursday'), ('fri', 'friday'), ('sat', 'saturday'), ('sun', 'sunday')]:
        if short in known:
            known.add(full)
    invented = [word for word in re.findall(r'\b[A-Z][\w-]*\b', output)
                if not all(part in known | starters for part in word.casefold().split('-'))]
    if invented:
        raise ValueError('Names absent from source: ' + ', '.join(dict.fromkeys(invented)))


def without_header(text):
    """Drop "[... report date YYYY-MM-DD]" header lines: context, not figures to preserve."""
    return '\n'.join(line for line in text.splitlines()
                     if not (line.startswith('[') and 'report date' in line.lower()))
