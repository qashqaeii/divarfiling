"""Consistent priority ordering for management action queues.

Pure presentation helper: no database access or business-state mutation.
"""
from __future__ import annotations

from typing import Any

PRIORITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'opportunity': 3}


def prioritize_management_actions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Critical/high first, larger cohorts next; stable order for ties.

    Do not mutate callers' lists: several view contexts also reuse them for
    diagnostic counts or links.
    """
    return sorted(
        items,
        key=lambda item: (
            PRIORITY_RANK.get(item.get('priority'), 9),
            -max(0, int(item.get('count') or 0)),
        ),
    )
