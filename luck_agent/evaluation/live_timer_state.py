"""Raw timer parsing for the two V099-observed symbol types, not simulation.

Parsing alone establishes neither a settled choice nor a complete rules context.
In particular, no next payout or board presence is inferred from this object.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ObservedTimer:
    symbol_type: str
    times_displayed: int
    parameters: tuple[int, int]
    raw_values: tuple[int, ...]


def parse_timer(symbol: dict) -> ObservedTimer:
    if not isinstance(symbol, dict):
        raise ValueError('invalid_symbol')
    kind = symbol.get('type')
    if kind not in ('magpie', 'gambler'):
        raise ValueError('unverified_timer_kind')
    if symbol.get('modded') is not False or symbol.get('inherit_effects') is not False:
        raise ValueError('modified_or_unknown_rule_source')
    count = symbol.get('times_displayed')
    if type(count) is not int or count < 0:
        raise ValueError('missing_or_invalid_timer')
    raw = symbol.get('values')
    expected = (9, 4) if kind == 'magpie' else (0, 2)
    # Only the two lengths actually captured in V099 are verified. Preserve raw
    # values for diagnosis instead of silently deleting arbitrary parameters.
    if (not isinstance(raw, list) or len(raw) not in (2, 4)
            or any(type(v) is not int for v in raw)
            or tuple(raw[:2]) != expected or any(v != 0 for v in raw[2:])):
        raise ValueError('unverified_timer_parameters')
    return ObservedTimer(kind, count, expected, tuple(raw))
