"""Questions-first flags (F6, packet 870 §12, cc 487).

The claim gate refuses a new fold/task claim while a question is owed —
but only for a side running the updated program. A side that goes around
the gate (an older version, a hand-edited state file, a fold posted
without a program claim) is caught here, the way the A13 alarm catches
a stale claim: from the state files + issues.json alone, no claim call
needed. The board renders these flags and the watcher (`poll`) wakes on
them.

The rule, in the program's data: a side VIOLATES questions-first when
its current non-answer work started AFTER its oldest owed question was
asked. Work started BEFORE the question is in-flight — the side
finishes it, then answer-first blocks its next claim; that is not a
flag. Work with no orderable timestamps (a question filed without
`created_at`, or work with no start time at all) cannot be ordered and
is not flagged — questions filed through `ask` always carry
`created_at`, so this only bites on hand-filed issues.

Work is the side's held claim when there is one (claim kind fold /
work / research — anything but `answer`), and a fold named in `current`
with no claim held (the bypass case: a fold posted without ever
claiming it in the program). The start time is `claim-started` first,
then `started`, then `updated`.
"""
from __future__ import annotations

from datetime import datetime

from .model import SIDES, Issue, SideState, fmt_time

WORK_KINDS = ("fold", "work", "research")


def _work_of(state: SideState) -> tuple[str, str, datetime | None] | None:
    """The side's current non-answer work, or None.

    Returns (claim_or_current, kind, started). A held claim wins; with
    no claim held, a fold named in `current` is the work (bypass case).
    An answer claim is not work for this rule."""
    if state.claim:
        if state.claim_kind == "answer":
            return None
        kind = state.claim_kind if state.claim_kind in WORK_KINDS else "work"
        started = state.claim_started or state.started or state.updated
        return state.claim, kind, started
    if state.current and "fold" in state.current.lower():
        # Bypass case. `started` is when the work began; `updated` only
        # as a fallback (it also moves on a progress refresh, which is
        # not a new fold).
        return state.current, "fold", state.started or state.updated
    return None


def find_violations(states: dict[str, SideState],
                    issues: list[Issue]) -> list[dict]:
    """One violation per offending side, naming the oldest question that
    was already owed when the side's current fold/task started. A side
    with no open question, no non-answer work, or only in-flight work
    (started before its oldest owed question) has no violation."""
    violations = []
    for side in SIDES:
        state = states.get(side)
        if state is None:
            continue
        work = _work_of(state)
        if work is None:
            continue
        claim, kind, started = work
        if started is None:
            continue
        owed = [i for i in issues if i.assignee == side and i.state == "open"]
        # Oldest first: created_at, then number. (created_at may be None;
        # those sort last and can never establish the order.)
        owed.sort(key=lambda i: (i.created_at is None,
                                 i.created_at or datetime.min.replace(tzinfo=started.tzinfo),
                                 i.number))
        for q in owed:
            if q.created_at is None:
                continue
            if started >= q.created_at:
                violations.append({
                    "side": side,
                    "question": q.number,
                    "question_title": q.title,
                    "asked_in": q.asked_in,
                    "question_created_at": fmt_time(q.created_at),
                    "claim": claim,
                    "claim_kind": kind,
                    "work_started": fmt_time(started),
                    "rule": "questions-first (F6): answer the question before any fold/task",
                })
                break
    return violations


def format_flag(v: dict) -> str:
    return (
        f"FLAG questions-first: {v['side']} started {v['claim_kind']} "
        f"{v['claim']!r} at {v['work_started']} while question "
        f"#{v['question']} {v['question_title']!r} (asked in "
        f"{v['asked_in'] or 'unknown'}, {v['question_created_at']}) was owed "
        f"— answer first (F6)"
    )
