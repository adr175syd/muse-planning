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

from .liveness import alarm, questions_first_flags
from .model import SIDES, SideState, parse_status_line, parse_time
from .store import Repo, atomic_write


def render_board(states: dict[str, SideState], issues, now: datetime | None = None) -> str:
    """Render the STATUS view. Same one-line-per-side shape as the seeded
    STATUS.md, so the output is a drop-in replacement for the Drive board
    — plus an A13 alarm section computed from commit-time liveness (the
    caller passes alarm rows; render_board does not call git itself).

    Questions-first (John's fix order, Nov 9 2026): owed questions are
    the HEAD of the queue, so the open-questions section renders ABOVE
    the per-side task lines — the board shows what is owed before what
    is being worked on."""
    now = now or datetime.now(timezone.utc)
    lines = [
        "# STATUS — Muse Bridge (rendered by muse-planning from state/*.md + issues.json)",
        "# Rendered, never hand-written. Each side owns only its own state file.",
        f"# Rendered: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
    ]
    open_q = [i for i in issues if i.state == "open"]
    open_q.sort(key=lambda x: (x.created_at or datetime.min.replace(tzinfo=timezone.utc), x.number))
    lines.append(f"## Owed questions (head of queue — answer first): {len(open_q)}")
    for i in open_q:
        asked = f" (asked {i.created_at.strftime('%Y-%m-%dT%H:%M:%SZ')})" if i.created_at else ""
        lines.append(
            f"- #{i.number} [{i.assignee}] {i.title} (asked in {i.asked_in}){asked}"
        )
    lines.append("")
    for side in SIDES:
        lines.append(states[side].board_line())
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
        )
    flags = questions_first_flags(states, issues)
    lines.append("")
    lines.append("## Questions-first flags (output posted while a question was owed)")
    if not flags:
        lines.append("- none")
    for f in flags:
        lines.append(
            f"- FLAG {f['side']}: posted {f['last_output']!r} "
            f"({f['last_output_time']}) while question #{f['question']} "
            f"{f['question_title']!r} was owed (asked {f['question_created_at']})"
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
