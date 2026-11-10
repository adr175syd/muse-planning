"""Board rendering + migration from the seeded Drive board.

The rendered board is a DERIVED artifact: the program renders it from the
three per-side state files + open Issues. No side hand-writes the combined
board (Harbor item 1) — that is what made the 34th-41st strikes
mechanically impossible instead of discipline-dependent. F1 stays in
force for any file that remains shared.

`migrate` parses the seeded STATUS.md (one `- <side> | ...` line per
side) into the three state/<side>.md files. It is run once, at the move.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .liveness import alarm
from .model import SIDES, SideState, parse_status_line, parse_time
from .queue import open_questions, ordered_queue, question_violations
from .store import Repo, atomic_write


def render_board(states: dict[str, SideState], issues, now: datetime | None = None) -> str:
    """Render the STATUS view. Same one-line-per-side shape as the seeded
    STATUS.md, so the output is a drop-in replacement for the Drive board
    — plus an A13 alarm section computed from commit-time liveness (the
    caller passes alarm rows; render_board does not call git itself).

    Questions first (870 §12): owed questions render at the HEAD of
    the board, ahead of every side's task lines, and the unified queue
    renders in queue order (questions, then folds, then tasks) before
    the per-side lines — the state that was invisible when the
    mining-data question waited behind three folds is now the first
    thing on the board."""
    now = now or datetime.now(timezone.utc)
    lines = [
        "# STATUS — Muse Bridge (rendered by muse-planning from state/*.md + issues.json)",
        "# Rendered, never hand-written. Each side owns only its own state file.",
        f"# Rendered: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    open_q = open_questions(issues)
    lines.append(f"## Open questions: {len(open_q)} — owed questions are HEAD of queue (questions first, 870 §12)")
    for i in open_q:
        lines.append(
            f"- #{i.number} [{i.assignee}] {i.title} (asked in {i.asked_in}) — HEAD OF QUEUE"
        )
    lines.append("")
    lines.append("## Queue (questions first)")
    queue = ordered_queue(states, issues)
    if not queue:
        lines.append("- (empty)")
    for n, e in enumerate(queue, start=1):
        who = e.side or "unassigned"
        lines.append(f"- {n}. [{e.kind}] {who}: {e.title} ({e.ref})")
    lines.append("")
    for side in SIDES:
        lines.append(states[side].board_line())
    violations = question_violations(states, issues)
    if violations:
        lines.append("")
        lines.append("## Questions-first violations (FLAG)")
        for v in violations:
            lines.append(f"- FLAG {v['detail']} — evidence: " + "; ".join(v["evidence"]))
    return "\n".join(lines) + "\n"


def render_board_with_alarm(repo: Repo, states, issues, now=None) -> str:
    board = render_board(states, issues, now)
    rows = alarm(str(repo.root), states, issues, now)
    lines = [board.rstrip("\n"), "", "## A13 alarm (commit-time liveness)"]
    for r in rows:
        stale = "STALE" if r["stale"] else "ok"
        mins = f"{r['stale_minutes']}m" if r["stale_minutes"] is not None else "unknown"
        q = (f"oldest open question #{r['oldest_open_question']} "
             f"{r['oldest_open_question_title']!r}" if r["oldest_open_question"]
             else "no open question")
        lines.append(
            f"- {r['side']}: {stale} (last state commit {mins} ago) — {q}"
            + (f" — claim {r['claim']}" if r["claim"] else "")
            + (" — FLAG QUESTIONS-FIRST VIOLATION" if r.get("question_violation") else "")
        )
    return "\n".join(lines) + "\n"


def migrate_status_to_state(status_text: str) -> dict[str, SideState]:
    """Parse the seeded STATUS.md into three SideStates. A STATUS line may
    only state what a packet states; the migration carries the text over
    verbatim and does not originate facts."""
    states: dict[str, SideState] = {}
    for line in status_text.splitlines():
        if not line.startswith("- "):
            continue
        fields = parse_status_line(line)
        side = fields["side"]
        if side not in SIDES:
            continue
        states[side] = SideState(
            side=side,
            updated=parse_time(fields["started"]) if fields.get("started") else None,
            current=fields.get("current", ""),
            started=parse_time(fields["started"]) if fields.get("started") else None,
            est=fields.get("est", ""),
            blocked_on=fields.get("blocked-on", ""),
            progress=fields.get("progress", ""),
            last_output=fields.get("last output", fields.get("last-output", "")),
        )
    missing = [s for s in SIDES if s not in states]
    if missing:
        raise ValueError(f"STATUS.md has no line for side(s): {missing}")
    return states


def write_state(repo: Repo, state: SideState) -> None:
    atomic_write(repo.state_path(state.side), state.to_text().encode("utf-8"))
