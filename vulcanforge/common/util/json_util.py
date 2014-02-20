import json


class JSONSafe(dict):
    """Marks a dictionary as safe (not needing sanitization)"""
    pass


class StrictJSONError(ValueError):
    pass


def _parse_constant(constant):
    if constant in ('-Infinity', 'Infinity', 'NaN'):
        raise StrictJSONError(constant)


def strict_loads(s, **kwargs):
    return json.loads(s, parse_constant=_parse_constant, **kwargs)


def strict_load(fp, **kwargs):
    return strict_loads(fp.read(), **kwargs)
