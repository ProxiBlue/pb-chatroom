"""Escalation evaluator — matches dispatch stdout against escalation rules."""

from __future__ import annotations

import re
from collections.abc import Callable

EscalationRule = tuple[str, Callable[[str], bool]]


def _has_multiple_competing(text: str) -> bool:
    return bool(re.search(r'competing approach|approach [AB].*approach [AB]|trade.off', text, re.I))


def _has_arch_changes(text: str) -> bool:
    paths = re.findall(r'\b\w+/\w+(?:/\w+)*\.py\b', text)
    return len(set(paths)) >= 3


ESCALATION_RULES: list[EscalationRule] = [
    ('multiple_competing_approaches', _has_multiple_competing),
    ('architectural_changes', _has_arch_changes),
    (
        'prod_data_access',
        lambda t: bool(re.search(r'production database|live data|prod db', t, re.I)),
    ),
    (
        'cost_trigger',
        lambda t: bool(re.search(r'budget.*(cap|limit|exceeded)', t, re.I)),
    ),
    (
        'confidence_below_threshold',
        lambda t: bool(re.search(r'not confident|uncertain|low confidence', t, re.I)),
    ),
    (
        'external_credentials',
        lambda t: bool(re.search(r'api_key|access_token|secret_key', t, re.I)),
    ),
    (
        'tests_broken',
        lambda t: bool(re.search(r'tests that were passing|broke.*passing test', t, re.I)),
    ),
]


def evaluate_escalation(stdout_text: str) -> list[str]:
    """Returns list of triggered rule names. Empty = no escalation."""
    return [name for name, pred in ESCALATION_RULES if pred(stdout_text)]
