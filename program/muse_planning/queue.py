"""Questions-first queue ordering + violation detection (870 §12).

The standing rule (packet 870 §12, confirmed by cc in 487) is:
questions first, tasks wait — an owed question outranks folds and
tasks. Until now that rule lived only in the claim gate (F6): a side
that posted a fold *outside* the claim path broke it silently, and
nothing flagged it (the mining-data question, author 893 §12, waited
~45 minutes while three folds posted). This module makes the rule
structural:

  1. Queue head. `ordered_queue` builds the one queue the board, the
     assigner and the watcher all read. Every open (owed) question is
     at the HEAD, oldest first, ahead of every fold and every task.
  2. Violation flag. `question_violations` detects a fold/task that
     was claimed or posted while a question was owed to that side —
     the bypass the gate cannot see — so the board / alarm / poll can
     flag it the way they flag a stale claim.

Detection evidence is the side's own state file, which board
discipline already requires a side to update when it posts output:

  - a held claim whose kind is not ``answer`` while a question is
    owed (the gate refuses such a claim, so holding one is a bypass);
  - a current item that IS a fold (text naming a fold, excluding
    items explicitly marked queued / held / not started — a fold
    queued *behind* an answer is the rule working, not a breach);
  - a last-output line naming a fold (a fold packet was posted).

An answer claim for the owed question is never a violation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .model import SIDES_ORDER, BacklogItem, Issue, SideState

_FOLD_RE = re.compile(r"\bfold(?:s|ed|ing)?\b", re.IGNORECASE)
# A current item carrying one of these markers names a fold that is
# waiting behind the answer, not a fold that jumped the queue.
_HELD_MARKERS = ("queued", "not started", "held", "behind the answer",
                 "behind answers", "behind the question")

# Queue priorities: lower sorts first. Questions, then folds, then tasks.
PRIO_QUESTION = 0
PRIO_FOLD = 1
PRIO_TASK = 2

_MIN = datetime.min.replace(tzinfo=timezone.utc)


def is_fold_text(text: str) -> bool:
    return bool(_FOLD_RE.search(text or ""))


def open_questions(issues: list[Issue]) -> list[Issue]:
    """All owed questions, oldest first (created_at, then number)."""
    qs = [i for i in issues if i.state == "open"]
    qs.sort(key=lambda i: (i.created_at or _MIN, i.number))
    return qs


@dataclass
class QueueEntry:
    kind: str          # "question" | "fold" | "task"
    side: str          # owning side ("" for an unassigned backlog task)
    ref: str           # "answer:<n>" for a question, claim/item id else
    title: str
    at: datetime | None = None

    @property
    def priority(self) -> int:
        return {"question": PRIO_QUESTION, "fold": PRIO_FOLD,
                "task": PRIO_TASK}[self.kind]


def ordered_queue(states: dict[str, SideState], issues: list[Issue],
                  backlog_items: list[BacklogItem] | None = None) -> list[QueueEntry]:
    """The unified queue, questions first.

    Order: (1) every owed question, oldest first; (2) held / current
    folds; (3) held / current other work and ready backlog tasks in
    pull order. Answer claims are not duplicated here — the question
    they answer already heads the queue.
    """
    entries: list[QueueEntry] = []
    for q in open_questions(issues):
        entries.append(QueueEntry("question", q.assignee, f"answer:{q.number}",
                                  q.title, q.created_at))
    for side in SIDES_ORDER:
        st = states.get(side) if states else None
        if st is None:
            continue
        if st.claim:
            if st.claim_kind == "answer":
                continue
            kind = "fold" if (st.claim_kind == "fold" or is_fold_text(st.claim)) else "task"
            entries.append(QueueEntry(kind, side, st.claim, st.claim,
                                      st.claim_started))
        elif st.current:
            kind = "fold" if is_fold_text(st.current) else "task"
            entries.append(QueueEntry(kind, side, st.current, st.current,
                                      st.started))
    for item in backlog_items or []:
        if not item.movable or item.watch_only:
            continue
        entries.append(QueueEntry("task", "", item.title, item.title, None))
    # Stable sort by priority only: questions were appended oldest
    # first, folds/tasks in side / pull order — that insertion order
    # is the order within each priority class and must be preserved
    # (a backlog task's pull order is its list order, not its name).
    entries.sort(key=lambda e: e.priority)
    return entries


def head_for_side(side: str, states: dict[str, SideState],
                  issues: list[Issue],
                  backlog_items: list[BacklogItem] | None = None) -> QueueEntry | None:
    """The head item for one side. If that side owes a question, the
    head IS the (oldest) owed question — never a fold or a task."""
    for e in ordered_queue(states, issues, backlog_items):
        if e.side == side:
            return e
    return None


def question_violations(states: dict[str, SideState],
                        issues: list[Issue]) -> list[dict]:
    """Flag rows: a fold/task claimed or posted while a question was
    owed to that side. One row per violating side, naming the owed
    question(s) and the evidence from the side's own state file."""
    rows: list[dict] = []
    for side in SIDES_ORDER:
        owed = [i for i in open_questions(issues) if i.assignee == side]
        if not owed:
            continue
        st = states.get(side) if states else None
        if st is None:
            continue
        evidence: list[str] = []
        if st.claim and st.claim_kind != "answer":
            evidence.append(
                f"held claim {st.claim!r} (kind {st.claim_kind or '?'}) "
                f"while a question was owed")
        cur = st.current or ""
        if (cur and cur != st.claim and not cur.startswith("answer:")
                and is_fold_text(cur)
                and not any(m in cur.lower() for m in _HELD_MARKERS)):
            evidence.append(f"current item is a fold: {cur!r}")
        lo = st.last_output or ""
        if is_fold_text(lo):
            evidence.append(f"last output is a fold: {lo!r}")
        if not evidence:
            continue
        rows.append({
            "side": side,
            "flag": "QUESTIONS-FIRST VIOLATION",
            "questions": [i.number for i in owed],
            "question_titles": [i.title for i in owed],
            "evidence": evidence,
            "detail": (
                f"{side} posted/claimed a fold or task while owed "
                f"question(s) "
                + ", ".join(f"#{i.number} {i.title!r}" for i in owed)
                + " — questions first (870 §12 / F6)"
            ),
        })
    return rows
