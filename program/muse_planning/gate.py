"""Gates: answer-first (F6), WIP 1, A7-in-assigner, A18 fence, CONTROL.

Claim rules, in the order they are checked (first refusal wins, and the
refusal names its reason):
  1. CONTROL: mode PAUSED (or WIND-DOWN for non-redesign work) refuses
     every claim — no new work starts; resume only on John's word (A4).
     The program never changes mode itself.
  2. Answer-first (F6): a side with an open assigned question may claim
     ONLY the answer item for that question. Any other claim is refused
     and names the blocking question(s).
  3. WIP 1: a side holding a claim may not take a second one.
  4. A7 in the assigner: a watch/read-only item is never a side's sole
     item — it is refused as a claim unless the side already holds an
     unconditional item (which WIP 1 forbids, so in practice a watch-only
     item is never claimable alone; see assign.py).
  5. A18 fence: auto-pulled research items must be research kind with a
     frozen spec + kill criteria. Verification/fold work never auto-pulls
     (it comes through the queue).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .model import SIDES, BacklogItem, Issue, SideState, parse_control
from .store import Repo, Refusal


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_control(repo: Repo) -> dict[str, str]:
    return parse_control(repo.control_path().read_text(encoding="utf-8"))


def control_allows_claim(control: dict[str, str]) -> tuple[bool, str]:
    mode = control.get("mode", "")
    seq = control.get("control-seq", "?")
    if mode == "RUN":
        return True, ""
    return False, (
        f"CONTROL {mode} seq {seq} — no new work starts; "
        f"resume only on John's word (A4)"
    )


def open_questions_for(issues: list[Issue], side: str) -> list[Issue]:
    return [i for i in issues if i.assignee == side and i.state == "open"]


# Claim kinds. "answer" is the answer to an owed question; "fold" a
# fold (through the queue); "task" any other piece of work; "work" and
# "research" are the older names for the same two (kept — main's CLI
# and tests use them). NON_ANSWER_KINDS is every kind the F6 gate
# refuses while a question is owed (i.e. everything but "answer").
CLAIM_KINDS = ("answer", "fold", "task", "work", "research")
NON_ANSWER_KINDS = ("fold", "task", "work", "research", "verification", "build")


def check_answer_first(issues: list[Issue], side: str, item_kind: str, item_id: str) -> None:
    """F6. Raises Refusal naming the blocking question(s) unless this
    claim IS the answer to one of them."""
    open_q = open_questions_for(issues, side)
    if not open_q:
        return
    if item_kind == "answer":
        # An answer claim must cite the question it answers: item_id is
        # "answer:<issue-number>".
        try:
            n = int(item_id.split(":", 1)[1])
        except (IndexError, ValueError):
            raise Refusal(
                f"answer-first: side {side} has open question(s) "
                f"{[i.number for i in open_q]}; an answer claim must cite "
                f"its issue as answer:<number>"
            )
        if any(i.number == n for i in open_q):
            return
        raise Refusal(
            f"answer-first: side {side} has open question(s) "
            f"{[i.number for i in open_q]}; claim answers #{n}, which is "
            f"not among them"
        )
    names = ", ".join(f"#{i.number} {i.title!r}" for i in open_q)
    raise Refusal(
        f"answer-first: side {side} has open question(s) {names}; "
        f"a {item_kind} claim is refused while they are owed — "
        f"answer the question(s) before any new claim (F6)"
    )


# Harbor's name for the same gate (PR #2); kept as an alias.
check_questions_first = check_answer_first


def check_wip1(state: SideState) -> None:
    if state.claim:
        raise Refusal(
            f"WIP 1: side {state.side} already holds claim {state.claim!r} "
            f"(started {state.claim_started}); finish or release it first"
        )


def check_a7(item: BacklogItem) -> None:
    """A7 in the assigner: a watch/read-only item is never a side's sole
    item. A claim is the side's sole item while it is held (WIP 1), so a
    watch-only claim is always refused here; the assigner pairs a watch
    with an unconditional item instead (see assign.py)."""
    if item.watch_only:
        raise Refusal(
            f"A7: {item.title!r} is watch/read-only and can never be a "
            f"side's sole item"
        )


def check_a18(item: BacklogItem) -> None:
    """A18 fence (auto-pull only): research items only, never verification
    or fold work; frozen spec + kill criteria first."""
    if item.kind != "research":
        raise Refusal(
            f"A18: {item.title!r} is {item.kind}, not research — "
            f"verification/fold work never auto-pulls"
        )
    if not item.movable:
        raise Refusal(
            f"A18: {item.title!r} has no frozen spec/kill criteria "
            f"(status {item.status!r}) — spec first, then pull"
        )


def claim(repo: Repo, side: str, item_id: str, item_kind: str,
          item: BacklogItem | None, issues: list[Issue],
          state: SideState, at: datetime | None = None) -> SideState:
    """Grant a claim, returning the updated state (the caller writes it).
    Raises Refusal with the reason on any failed gate. Kinds: "answer"
    (the answer to an open question), "fold" (a fold, through the
    queue), "task" (any other work), "work" (older name for "task"),
    "research" (a backlog pull). A fold/task claim is refused by
    answer-first like any other non-answer claim while a question is
    owed; folds never auto-pull (A18) and are never watch-only claims
    (A7 does not apply — a fold is unconditional work, not a watch)."""
    if side not in SIDES:
        raise Refusal(f"unknown side {side!r} (want one of {SIDES})")
    if item_kind not in CLAIM_KINDS:
        raise Refusal(
            f"unknown claim kind {item_kind!r} "
            f"(want one of {' | '.join(CLAIM_KINDS)})"
        )
    at = at or now_utc()
    control = load_control(repo)
    ok, why = control_allows_claim(control)
    if not ok:
        raise Refusal(why)
    check_answer_first(issues, side, item_kind, item_id)
    check_wip1(state)
    if item is not None:
        check_a7(item)
        if item_kind == "research":
            check_a18(item)
    state.claim = item_id
    state.claim_kind = item_kind
    state.claim_started = at
    state.current = item_id
    state.started = at
    state.updated = at
    return state


def release(repo: Repo, side: str, state: SideState,
            at: datetime | None = None) -> SideState:
    """Release a held claim (no output). Raises Refusal if none is held."""
    if not state.claim:
        raise Refusal(f"side {side} holds no claim to release")
    at = at or now_utc()
    state.claim = ""
    state.claim_kind = ""
    state.claim_started = None
    state.current = ""
    state.updated = at
    return state


def record_progress(state: SideState, note: str,
                    at: datetime | None = None) -> SideState:
    """Heartbeat progress: refresh only on real output (A7)."""
    at = at or now_utc()
    state.progress = note
    state.updated = at
    return state


def ask_question(issues: list[Issue], title: str, body: str, assignee: str,
                 asked_in: str, at: datetime | None = None) -> Issue:
    """File a question as an Issue the same cycle it is asked (Harbor item
    2). The number is assigned HERE by the program, serially — the packet
    cites the returned number; no handwritten number is trusted."""
    if assignee not in SIDES:
        raise Refusal(f"unknown assignee {assignee!r} (want one of {SIDES})")
    at = at or now_utc()
    n = max((i.number for i in issues), default=0) + 1
    issue = Issue(number=n, title=title, body=body, assignee=assignee,
                  state="open", created_at=at, asked_in=asked_in)
    issues.append(issue)
    return issue


def answer_question(issues: list[Issue], number: int,
                    at: datetime | None = None) -> Issue:
    """Close an assigned question (the answer itself is the packet)."""
    at = at or now_utc()
    for i in issues:
        if i.number == number:
            if i.state == "closed":
                raise Refusal(f"question #{number} is already closed")
            i.state = "closed"
            i.closed_at = at
            return i
    raise Refusal(f"no question #{number}")
