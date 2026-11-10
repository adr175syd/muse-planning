"""The work queue, questions first (F6, packet 870 §12) — reconciled.

Reconciles the three questions-first implementations (cc PR #1, Harbor
PR #2, author PR #3) into the program's ONE ordering for work:

  1. owed questions, oldest first — each is an `answer:<n>` item;
  2. the side's current claim, if any (in-flight work — finished, then
     answer-first blocks the next claim; it is never pre-empted);
  3. the movable backlog pool, ordered by PRIORITY first (P1, then P2,
     then P3), then pull order within a rank.

Two views over the same ordering (cc's per-side queue + Harbor's
unified global queue):
  - `ordered_queue(side, ...)` — one side's queue (what that side
    works next, in order). The assigner never assigns backlog work to
    a side with an open question, and the claim gate refuses any
    non-answer claim while one is owed.
  - `ordered_queue_all(states, ...)` — the one global queue the board,
    the assigner and the watcher all read. Every open question heads
    it, oldest first, ahead of every fold and every task.

Priority (JJ's priority-column order, Nov 10 2026): a priority item
(P1/P2/P3 on the backlog item) orders ahead of unprioritized pool
items and stays at the top of its section until it is done or
explicitly deprioritized — a newly arrived ordinary item never buries
it, because the order is a pure function of (priority rank, pull
order), not arrival time. Priority reorders the POOL only: it never
jumps ahead of an owed question (F6 outranks priority — questions
carry no priority field) or ahead of in-flight work (a held claim).

Kind vocabulary (unified — the three branches used three): "answer"
(the answer to an owed question), "fold", "task" (held work that is
not a fold, and every movable backlog item). The claim kinds are the
same vocabulary plus "work" / "research" (gate.claim accepts all five;
"work" and "research" claims render as "task" entries here).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .model import SIDES, SIDES_ORDER, BacklogItem, Issue, SideState, fmt_time

# Queue classes: lower sorts first. Questions, then folds, then tasks.
PRIO_QUESTION = 0
PRIO_FOLD = 1
PRIO_TASK = 2

_MIN = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class QueueEntry:
    """One entry in an ordered queue."""
    kind: str  # "answer" | "fold" | "task"
    ref: str  # "answer:<n>" for questions, the claim id / item title otherwise
    title: str
    side: str = ""  # owning side ("" for an unassigned backlog task)
    at: datetime | None = None
    priority: str = ""  # "" | "P1" | "P2" | "P3" (pool items only)
    detail: str = ""

    @property
    def queue_class(self) -> int:
        return {"answer": PRIO_QUESTION, "fold": PRIO_FOLD,
                "task": PRIO_TASK}[self.kind]


def _question_time(issue: Issue) -> datetime:
    return issue.created_at or _MIN


def open_questions_for(issues: list[Issue], side: str) -> list[Issue]:
    """A side's owed questions, oldest first (creation order, then number)."""
    owed = [i for i in issues if i.assignee == side and i.state == "open"]
    owed.sort(key=lambda i: (_question_time(i), i.number))
    return owed


def open_questions(issues: list[Issue]) -> list[Issue]:
    """All owed questions, oldest first (created_at, then number)."""
    qs = [i for i in issues if i.state == "open"]
    qs.sort(key=lambda i: (_question_time(i), i.number))
    return qs


def _pool_entries(backlog_items: list[BacklogItem] | None) -> list[QueueEntry]:
    """Movable backlog pool as task entries, ordered by priority rank
    (P1, P2, P3) then pull order within a rank. A new ordinary item
    appended at the tail never buries a priority item."""
    pool = [i for i in (backlog_items or [])
            if i.movable and not i.watch_only]
    pool.sort(key=lambda i: i.priority_rank)
    return [QueueEntry(kind="task", ref=i.title, title=i.title,
                       priority=i.priority, detail=f"status {i.status}")
            for i in pool]


def _claim_entry(state: SideState) -> QueueEntry | None:
    """The side's current claim as a queue entry, or None when it holds
    no claim. An answer claim is not duplicated — the question it
    answers already heads the queue."""
    if not state.claim:
        return None
    if state.claim_kind == "answer":
        return None
    kind = "fold" if state.claim_kind == "fold" else "task"
    return QueueEntry(
        kind=kind, ref=state.claim, title=state.claim, side=state.side,
        at=state.claim_started,
        detail=(f"started {fmt_time(state.claim_started)}"
                if state.claim_started else "in progress"),
    )


def ordered_queue(side: str, issues: list[Issue], state: SideState,
                  backlog_items: list[BacklogItem] | None = None) -> list[QueueEntry]:
    """A side's work queue, questions first. Answers head the queue ahead
    of the side's current claim and ahead of the backlog pool; the pool
    is ordered by priority, then pull order."""
    if side not in SIDES:
        raise ValueError(f"unknown side {side!r} (want one of {SIDES})")
    queue: list[QueueEntry] = []
    for q in open_questions_for(issues, side):
        queue.append(QueueEntry(
            kind="answer", ref=f"answer:{q.number}", title=q.title, side=side,
            at=q.created_at,
            detail=f"asked in {q.asked_in or 'unknown'}"
                   + (f" at {fmt_time(q.created_at)}" if q.created_at else ""),
        ))
    entry = _claim_entry(state)
    if entry is not None:
        queue.append(entry)
    queue.extend(_pool_entries(backlog_items))
    return queue


def head_of_queue(side: str, issues: list[Issue], state: SideState,
                  backlog_items: list[BacklogItem] | None = None) -> QueueEntry | None:
    """The single next item for a side: its oldest owed question if any,
    else its current claim, else the head movable backlog item (highest
    priority first)."""
    queue = ordered_queue(side, issues, state, backlog_items)
    return queue[0] if queue else None


def ordered_queue_all(states: dict[str, SideState], issues: list[Issue],
                      backlog_items: list[BacklogItem] | None = None) -> list[QueueEntry]:
    """The unified queue, questions first.

    Order: (1) every owed question, oldest first; (2) held / current
    folds, in side order; (3) held / current other work, in side order,
    then ready backlog tasks ordered by priority, then pull order.
    Answer claims are not duplicated here — the question they answer
    already heads the queue. Entries are built in class order and
    stable-sorted by class only, so the within-class order built here
    (oldest-first questions, side order, priority-then-pull tasks) is
    preserved."""
    entries: list[QueueEntry] = []
    for q in open_questions(issues):
        entries.append(QueueEntry("answer", f"answer:{q.number}", q.title,
                                  q.assignee, q.created_at))
    for side in SIDES_ORDER:
        st = states.get(side) if states else None
        if st is None:
            continue
        if st.claim:
            entry = _claim_entry(st)
            if entry is not None:
                entries.append(entry)
        elif st.current:
            # No claim held: the side's current item, if any (a fold
            # posted without a program claim still sits in the queue).
            kind = "fold" if "fold" in st.current.lower() else "task"
            entries.append(QueueEntry(kind, st.current, st.current, side,
                                      st.started))
    entries.extend(_pool_entries(backlog_items))
    # Stable sort by class only: questions were appended oldest first,
    # folds/tasks in side / priority / pull order — that insertion order
    # is the order within each class and must be preserved (a backlog
    # task's pull order is its list order, not its name).
    entries.sort(key=lambda e: e.queue_class)
    return entries


def head_for_side(side: str, states: dict[str, SideState],
                  issues: list[Issue],
                  backlog_items: list[BacklogItem] | None = None) -> QueueEntry | None:
    """The head item for one side. If that side owes a question, the
    head IS the (oldest) owed question — never a fold or a task."""
    for e in ordered_queue_all(states, issues, backlog_items):
        if e.side == side:
            return e
    return None


def format_queue(entries: list[QueueEntry], show_side: bool = False) -> str:
    """Render queue entries as numbered lines with the priority column.

    Every line carries `prio <level>` — `prio P1` / `prio P2` /
    `prio P3` for priority items, `prio —` for everything else
    (questions carry no priority: F6 already puts them first). The
    head entry is marked `HEAD OF QUEUE`."""
    lines: list[str] = []
    for n, e in enumerate(entries, 1):
        side_txt = f" {e.side}:" if show_side and e.side else ""
        prio = f"prio {e.priority}" if e.priority else "prio \u2014"
        head = "  <-- HEAD OF QUEUE" if n == 1 else ""
        detail = f" ({e.detail})" if e.detail else ""
        lines.append(f"{n}. [{e.kind}]{side_txt} {e.ref} \u2014 {e.title}"
                     f"{detail} | {prio}{head}")
    return "\n".join(lines)
