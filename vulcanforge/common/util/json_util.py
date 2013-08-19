import json


class JSONSafe(dict):
    """Marks a dictionary as safe (not needing sanitization)"""
    pass


class StrictJSONError(ValueError):
    pass


def _parse_constant(constant):
    if constant in ('-Infinity', 'Infinity', 'NaN'):
        raise StrictJSONError(constant)


def strict_load(fp, **kwargs):
    return json.load(fp, parse_constant=_parse_constant, **kwargs)
