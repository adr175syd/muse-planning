"""Assigner: rotate the load, one thing at a time.

John's pin 2: "Rotate the load, not a fix role." No side holds a fixed
role and no single owner exists (decided 2-1 under A5, cc 445). The
assigner picks, for the head ready backlog item:
  - the free side (no claim held — WIP 1),
  - with no open assigned question (answer-first: a side with an open
    question must answer it before it takes new work),
  - least recently assigned first (round-robin by last_assigned; ties
    break in the fixed side order author -> harbor -> cc),
  - and never assigns a watch/read-only item as a side's sole item (A7:
    a watch is only ever paired with an unconditional item, which WIP 1
    makes impossible in a single assignment — so a watch-only head item
    is skipped, not assigned).

The assigner only PROPOSES. The side still claims the item itself (the
claim goes through gate.claim, which re-checks every rule). Assignment
never moves a fold/answer — those come through the queue (see queue.py:
owed questions head a side's queue, ahead of folds and tasks, and a
side with an open question is not free here at all).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .gate import check_a18, check_a7
from .model import SIDES_ORDER, BacklogItem, Issue, SideState
from .store import Refusal


def free_sides(states: dict[str, SideState], issues: list[Issue]) -> list[str]:
    """Sides that may take new work right now: no claim held, no open
    assigned question. Ordered least-recently-assigned first."""
    free = []
    for side in SIDES_ORDER:
        st = states[side]
        if st.claim:
            continue
        if any(i.assignee == side and i.state == "open" for i in issues):
            continue
        free.append(side)
    free.sort(key=lambda s: (states[s].last_assigned or datetime.min.replace(tzinfo=timezone.utc), SIDES_ORDER.index(s)))
    return free


def pick_head_item(items: list[BacklogItem]) -> BacklogItem | None:
    """Head ready item, in pull order. Skips needs-spec / done / excluded
    and watch-only items (A7: never a sole item)."""
    for it in items:
        if not it.movable:
            continue
        if it.watch_only:
            continue
        return it
    return None


def assign(states: dict[str, SideState], items: list[BacklogItem],
           issues: list[Issue], at: datetime | None = None) -> tuple[str, BacklogItem]:
    """Return (side, item) for the next assignment. Raises Refusal naming
    the reason when nothing can be assigned (no free side, no ready item,
    every ready item blocked by A18/A7)."""
    at = at or datetime.now(timezone.utc)
    free = free_sides(states, issues)
    if not free:
        busy = [s for s in SIDES_ORDER if states[s].claim]
        blocked = [s for s in SIDES_ORDER
                   if not states[s].claim
                   and any(i.assignee == s and i.state == "open" for i in issues)]
        raise Refusal(
            "assigner: no free side "
            f"(busy: {busy or 'none'}; answering first: {blocked or 'none'})"
        )
    head = pick_head_item(items)
    if head is None:
        raise Refusal("assigner: no ready, movable backlog item (head is "
                      "needs-spec, done, excluded, or watch-only)")
    # A18: auto-pull is research only, spec + kill first.
    check_a18(head)
    check_a7(head)
    side = free[0]
    states[side].last_assigned = at
    return side, head
