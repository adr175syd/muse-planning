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

Questions-first (John's fix order, Nov 9 2026): an owed question is the
HEAD of the queue, ahead of folds and tasks. `assign()` therefore looks
for an answerable owed question FIRST — the oldest open question whose
assignee is free to take it — and assigns the answer to that side
before any backlog item is considered. Only when no owed question is
answerable does it fall back to the head backlog item among free sides.
A question whose assignee is busy (holding a claim, WIP 1) waits for
that side to free up; other free sides still get backlog work — the
refusal in gate.claim is per-side, and blocking the whole team on one
busy side would break rotation.

The assigner only PROPOSES. The side still claims the item itself (the
claim goes through gate.claim, which re-checks every rule). Assignment
never moves a fold/answer — those come through the queue.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .gate import check_a18, check_a7
from .model import SIDES_ORDER, BacklogItem, Issue, SideState
from .store import Refusal


def answer_item(question: Issue) -> BacklogItem:
    """The queue-head item for an owed question: the answer to it. This
    is NOT a backlog item — it never goes through pick_head_item, A18 or
    A7 (an answer has no spec/kill to freeze). Its title is the claim
    id the side claims with: `answer:<number>` (gate.claim accepts
    exactly that form for answer claims)."""
    return BacklogItem(
        title=f"answer:{question.number}",
        kind="answer",
        status="ready",
        spec=f"question #{question.number}: {question.title}",
        kill="answer posted by packet",
    )


def next_owed_answer(issues: list[Issue],
                     states: dict[str, SideState]) -> tuple[str, Issue] | None:
    """Oldest open question whose assignee is free to take it (no claim
    held, WIP 1). Returns (side, issue) or None when no owed question
    is answerable right now. Oldest first by asked time, then number —
    the question that has waited longest is the head of the queue."""
    open_q = [i for i in issues if i.state == "open"]
    open_q.sort(key=lambda i: (i.created_at or datetime.min.replace(tzinfo=timezone.utc), i.number))
    for q in open_q:
        st = states.get(q.assignee)
        if st is not None and not st.claim:
            return q.assignee, q
    return None


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
    """Head ready item. Skips needs-spec / done / excluded and
    watch-only items (A7: never a sole item). Among the movable items
    the HIGHEST PRIORITY goes first (P1, then P2, then P3), then pull
    order within a rank — the priority column (JJ's order, Nov 10
    2026): a priority item is the next assignment ahead of ordinary
    backlog work, and a newly arrived ordinary item never buries it."""
    ready = [it for it in items if it.movable and not it.watch_only]
    if not ready:
        return None
    ready.sort(key=lambda it: it.priority_rank)
    return ready[0]


def assign(states: dict[str, SideState], items: list[BacklogItem],
           issues: list[Issue], at: datetime | None = None) -> tuple[str, BacklogItem]:
    """Return (side, item) for the next assignment. Raises Refusal naming
    the reason when nothing can be assigned (no free side, no ready item,
    every ready item blocked by A18/A7).

    Questions-first: an answerable owed question is the head of the
    queue and is assigned before any backlog item. Only when no owed
    question is answerable does the head backlog item go to the
    least-recently-assigned free side."""
    at = at or datetime.now(timezone.utc)
    owed = next_owed_answer(issues, states)
    if owed is not None:
        side, question = owed
        states[side].last_assigned = at
        return side, answer_item(question)
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
