"""Liveness from git commit times + the A13 alarm (Harbor items 4 and 6).

A side's staleness = age of its last commit on its own state file. Git
history is the ordering — never Drive modifiedTime or folder listings
(Drive listings lagged a just-posted packet by 30+ minutes and carried
the next file's values; both produced false staleness this cycle).

A13 ("the board is the alarm") survives only if the board is computed:
the alarm lists, per side, staleness (minutes since last state-file
commit) next to its oldest open assigned question/build. A side with no
output for > 60 minutes while a question is pending is STALE.

Questions-first flags (John's fix order, Nov 9 2026): the same alarm
idea, for the case F6 alone cannot stop — a side that posts output
while a question is owed to it. The program cannot stop a packet post
(folds go through Drive, not through `claim`), so the board/watcher
must CATCH it. The detector lives in flags.py (reconciled from cc PR
#1, Harbor PR #2, author PR #3); alarm() carries its rows here so the
board and the watcher digest see staleness and flags side by side.
The flag is a detector, like A13's STALE — the packet layer
adjudicates whether the output was a fold or something else (e.g. an
answer whose Issue has not been closed yet).
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from .flags import find_violations, format_flag
from .model import STALE_MINUTES, Issue, SideState, parse_time

GIT_TIMEOUT_S = 10


def oldest_open_question_for(issues: list[Issue], side: str) -> Issue | None:
    open_q = [i for i in issues if i.assignee == side and i.state == "open"]
    if not open_q:
        return None
    open_q.sort(key=lambda i: (i.created_at or datetime.min.replace(tzinfo=timezone.utc), i.number))
    return open_q[0]


def last_commit_time(repo_root: str, rel_path: str) -> datetime | None:
    """Last commit time (author date, UTC) touching `rel_path`, or None if
    the file has no commits / git is unavailable / the path is not in a
    repo. Never raises — a missing commit time is 'unknown', not 'fresh'."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "log", "-1", "--format=%cI", "--", rel_path],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    stamp = out.stdout.strip()
    return parse_time(stamp) if stamp else None


def staleness_minutes(last_commit: datetime | None, now: datetime) -> float | None:
    if last_commit is None:
        return None
    return (now - last_commit).total_seconds() / 60.0


def is_stale(last_commit: datetime | None, now: datetime,
             pending: bool = True) -> bool:
    """STALE iff a question/build is pending and the last commit is older
    than STALE_MINUTES. Unknown commit time (None) with a pending item is
    stale — never silently fresh."""
    if not pending:
        return False
    mins = staleness_minutes(last_commit, now)
    if mins is None:
        return True
    return mins > STALE_MINUTES


def oldest_open_question(issues: list[Issue], side: str) -> Issue | None:
    return oldest_open_question_for(issues, side)


def alarm(repo_root: str, states: dict[str, SideState],
          issues: list[Issue], now: datetime | None = None) -> list[dict]:
    """A13 alarm rows, one per side: staleness (minutes since last
    state-file commit) next to the oldest open assigned question, plus
    the side's questions-first flag (if any).

    Flag fields (one detector, two names, so no side's watcher has to
    guess): `questions_first_flag` is the formatted flag text (or None
    when clear); `question_violation` is the same fact as a boolean and
    `question_violation_detail` its text."""
    now = now or datetime.now(timezone.utc)
    flags = {f["side"]: f for f in find_violations(states, issues)}
    rows = []
    for side in ("author", "harbor", "cc"):
        rel = f"state/{side}.md"
        last = last_commit_time(repo_root, rel)
        mins = staleness_minutes(last, now)
        q = oldest_open_question(issues, side)
        pending = q is not None or bool(states[side].claim)
        flag = flags.get(side)
        rows.append({
            "side": side,
            "last_commit": last.isoformat() if last else None,
            "stale_minutes": round(mins, 1) if mins is not None else None,
            "stale": is_stale(last, now, pending),
            "oldest_open_question": q.number if q else None,
            "oldest_open_question_title": q.title if q else "",
            "claim": states[side].claim,
            "questions_first_flag": format_flag(flag) if flag else None,
            "question_violation": bool(flag),
            "question_violation_detail": flag["detail"] if flag else "",
        })
    return rows
