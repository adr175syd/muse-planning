"""Questions-first flags (F6, packet 870 §12) — reconciled.

The claim gate refuses a new fold/task claim while a question is owed —
but only for a side running the updated program. A side that goes around
the gate (an older version, a hand-edited state file, a fold posted
without a program claim) is caught here, the way the A13 alarm catches
a stale claim: from the state files + issues.json alone, no claim call
needed. The board renders these flags and the watcher (`poll`) wakes on
them.

The rule, in the program's data (reconciled from cc PR #1, Harbor PR #2
and author PR #3): a side is FLAGGED when its non-answer work
demonstrably started or moved AFTER its oldest owed question was asked.
Three legs, any one of which fires the flag — all timestamp-ordered, so
in-flight work (started BEFORE the question) is never flagged:

  1. Held claim (cc): a held non-answer claim whose start time
     (claim-started, then started, then updated) is at/after the
     question's created_at. The gate refuses such a claim, so holding
     one is a bypass.
  2. Bypass current (cc + Harbor's held markers): a fold named in
     `current` with no claim held, started/updated at/after the
     question — excluding items explicitly marked queued / held / not
     started / behind the answer, which are folds waiting behind the
     answer (the rule working, not a breach).
  3. Last output (author): the latest ISO timestamp named in the
     side's last_output / current / progress text is after the
     question's created_at. This leg persists after the claim is
     released — the seeded last-output format ("packet 506
     2026-11-10T02:45:54Z") never contains the word "fold", so a
     text match on last_output could never catch the incident shape;
     the timestamp is the evidence. The packet layer adjudicates
     whether the output was a fold or something else (e.g. an answer
     whose Issue has not been closed yet).

Work with no orderable timestamps (a question filed without
`created_at`, or work with no start time at all) cannot be ordered and
is not flagged — questions filed through `ask` always carry
`created_at`. A side currently holding the answer claim for the owed
question is not flagged — it is answering.

DELIBERATE CHANGE vs Harbor PR #2: Harbor's detector was state-based
(no timestamps) and flagged a held fold claim even when the claim
started BEFORE the question — in-flight work, which the team's
standing rule exempts ("finish it, then answer-first blocks its next
claim"). The reconciled detector requires the timestamp ordering on
every leg; Harbor's test for the held-claim leg now sets the claim
start after the question (same intent, orderable fixture).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .model import SIDES, Issue, SideState, fmt_time, parse_time

WORK_KINDS = ("fold", "task", "work", "research")

_FOLD_RE = re.compile(r"\bfold(?:s|ed|ing)?\b", re.IGNORECASE)
# A current item carrying one of these markers names a fold that is
# waiting behind the answer, not a fold that jumped the queue.
_HELD_MARKERS = ("queued", "not started", "held", "behind the answer",
                 "behind answers", "behind the question")

# A packet/fold post carries its time in the side's last_output, e.g.
# "packet 506 2026-11-10T02:45:54Z" (seeded STATUS.md format).
ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

_MIN = datetime.min.replace(tzinfo=timezone.utc)


def last_output_time(state: SideState) -> datetime | None:
    """Latest ISO timestamp named in the side's last_output / current /
    progress text (the post time a packet/fold carries). None when no
    field names a time — never guessed."""
    best: datetime | None = None
    for text in (state.last_output, state.current, state.progress):
        for m in ISO_TS_RE.finditer(text or ""):
            t = parse_time(m.group(0))
            if t and (best is None or t > best):
                best = t
    return best


def oldest_open_question_for(issues: list[Issue], side: str) -> Issue | None:
    """A side's oldest open assigned question (created_at, then number)."""
    open_q = [i for i in issues if i.assignee == side and i.state == "open"]
    if not open_q:
        return None
    open_q.sort(key=lambda i: (i.created_at or _MIN, i.number))
    return open_q[0]


def _held_claim_work(state: SideState) -> tuple[str, str, datetime | None] | None:
    """The side's held non-answer claim as (claim, kind, started), or
    None when no claim is held or the claim is the answer. The start
    time is claim-started first, then started, then updated."""
    if not state.claim:
        return None
    if state.claim_kind == "answer":
        return None
    kind = state.claim_kind if state.claim_kind in WORK_KINDS else "work"
    started = state.claim_started or state.started or state.updated
    return state.claim, kind, started


def find_violations(states: dict[str, SideState],
                    issues: list[Issue]) -> list[dict]:
    """One flag row per offending side, naming the oldest question that
    was already owed when the side's non-answer work started or its
    output posted. A side with no open question, no non-answer work, or
    only in-flight work (started before its oldest owed question) has
    no flag. A side holding the answer claim is not flagged."""
    rows: list[dict] = []
    for side in SIDES:
        state = states.get(side)
        if state is None:
            continue
        q = oldest_open_question_for(issues, side)
        if q is None or q.created_at is None:
            continue
        if state.claim_kind == "answer" and state.claim == f"answer:{q.number}":
            continue
        evidence: list[str] = []
        claim = ""
        claim_kind = ""
        work_started: datetime | None = None
        # Leg 1: held non-answer claim started at/after the question.
        held = _held_claim_work(state)
        if held is not None:
            claim, claim_kind, work_started = held
            if work_started is not None and work_started >= q.created_at:
                evidence.append(
                    f"held claim {claim!r} (kind {claim_kind}) started "
                    f"{fmt_time(work_started)}")
        # Leg 2: a fold named in `current` with no claim held (bypass).
        cur = state.current or ""
        if (cur and cur != state.claim and not cur.startswith("answer:")
                and _FOLD_RE.search(cur)
                and not any(m in cur.lower() for m in _HELD_MARKERS)):
            cur_started = state.started or state.updated
            if cur_started is not None and cur_started >= q.created_at:
                if not claim:
                    claim, claim_kind = cur, "fold"
                evidence.append(
                    f"current item is a fold: {cur!r} "
                    f"(started {fmt_time(cur_started)})")
        # Leg 3: latest named output time after the question.
        out_time = last_output_time(state)
        if out_time is not None and out_time > q.created_at:
            evidence.append(
                f"last output {state.last_output!r} at "
                f"{fmt_time(out_time)}")
        if not evidence:
            continue
        owed = [i for i in issues
                if i.assignee == side and i.state == "open"]
        detail = (
            f"{side} posted/claimed non-answer work while owed "
            f"question(s) " + ", ".join(f"#{i.number} {i.title!r}" for i in owed)
            + " — questions first (870 §12 / F6); evidence: "
            + "; ".join(evidence)
        )
        rows.append({
            "side": side,
            "question": q.number,
            "questions": [i.number for i in owed],
            "question_title": q.title,
            "question_titles": [i.title for i in owed],
            "asked_in": q.asked_in,
            "question_created_at": fmt_time(q.created_at),
            "claim": claim,
            "claim_kind": claim_kind,
            "work_started": fmt_time(work_started) if work_started else "",
            "last_output": state.last_output,
            "last_output_time": fmt_time(out_time) if out_time else "",
            "evidence": evidence,
            "detail": detail,
            "flag": f"FLAG questions-first: {detail}",
            "rule": "questions-first (F6): answer the question before any fold/task",
        })
    return rows


# The author's name for the same detector (PR #3); kept as an alias so
# the author's demo scripts and liveness call sites read unchanged.
questions_first_flags = find_violations


def format_flag(v: dict) -> str:
    """The one-line human-readable flag (board + alarm rows)."""
    return v.get("flag") or (
        f"FLAG questions-first: {v['side']} started {v['claim_kind']} "
        f"{v['claim']!r} at {v.get('work_started', '?')} while question "
        f"#{v['question']} {v['question_title']!r} was owed "
        f"— answer first (F6)"
    )
