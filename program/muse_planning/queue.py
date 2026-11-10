"""A side's work queue, questions first (F6, packet 870 §12, cc 487).

The standing rule is "questions first, tasks wait": an owed question
goes to the HEAD of the queue, ahead of folds and tasks. This module is
the program's one ordering for a side's work:

  1. open assigned questions, oldest first — each is an `answer:<n>` item;
  2. the side's current claim, if any (fold / task / research);
  3. the movable backlog pool, in pull order.

The queue is what the side works next, in order. The assigner
(assign.py) never assigns backlog work to a side with an open question,
and the claim gate (gate.py) refuses any non-answer claim while one is
owed — this module is the ordering those two enforce. Folds and answers
never move between sides (PLANNING_SYSTEM_BUILD §1 item 16); only the
order within a side's own queue is defined here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .model import SIDES, BacklogItem, Issue, SideState, fmt_time


@dataclass
class QueueEntry:
    """One entry in a side's ordered queue."""
    kind: str  # "answer" | "fold" | "work" | "research"
    ref: str  # "answer:<n>" for questions, the claim id / item title otherwise
    title: str
    detail: str = ""


def _question_time(issue: Issue) -> datetime:
    return issue.created_at or datetime.min.replace(tzinfo=timezone.utc)


def open_questions_for(issues: list[Issue], side: str) -> list[Issue]:
    """A side's owed questions, oldest first (creation order, then number)."""
    owed = [i for i in issues if i.assignee == side and i.state == "open"]
    owed.sort(key=lambda i: (_question_time(i), i.number))
    return owed


def ordered_queue(side: str, issues: list[Issue], state: SideState,
                  backlog_items: list[BacklogItem] | None = None) -> list[QueueEntry]:
    """A side's work queue, questions first. Answers head the queue ahead
    of the side's current fold/task and ahead of the backlog pool."""
    if side not in SIDES:
        raise ValueError(f"unknown side {side!r} (want one of {SIDES})")
    queue: list[QueueEntry] = []
    for q in open_questions_for(issues, side):
        queue.append(QueueEntry(
            kind="answer", ref=f"answer:{q.number}", title=q.title,
            detail=f"asked in {q.asked_in or 'unknown'}"
                   + (f" at {fmt_time(q.created_at)}" if q.created_at else ""),
        ))
    if state.claim:
        kind = state.claim_kind if state.claim_kind in ("answer", "fold", "work", "research") else "work"
        queue.append(QueueEntry(
            kind=kind, ref=state.claim, title=state.claim,
            detail=f"started {fmt_time(state.claim_started)}" if state.claim_started else "in progress",
        ))
    for item in backlog_items or []:
        if not item.movable or item.watch_only:
            continue
        queue.append(QueueEntry(kind="research", ref=item.title,
                                title=item.title, detail=f"status {item.status}"))
    return queue


def head_of_queue(side: str, issues: list[Issue], state: SideState,
                  backlog_items: list[BacklogItem] | None = None) -> QueueEntry | None:
    """The single next item for a side: its oldest owed question if any,
    else its current claim, else the head movable backlog item."""
    queue = ordered_queue(side, issues, state, backlog_items)
    return queue[0] if queue else None
