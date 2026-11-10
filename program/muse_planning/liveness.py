"""Liveness from git commit times + the A13 alarm (Harbor items 4 and 6).

A side's staleness = age of its last commit on its own state file. Git
history is the ordering — never Drive modifiedTime or folder listings
(Drive listings lagged a just-posted packet by 30+ minutes and carried
the next file's values; both produced false staleness this cycle).

A13 ("the board is the alarm") survives only if the board is computed:
the alarm lists, per side, staleness (minutes since last state-file
commit) next to its oldest open assigned question/build. A side with no
output for > 60 minutes while a question is pending is STALE.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from .flags import find_violations, format_flag
from .model import STALE_MINUTES, Issue, SideState, parse_time

GIT_TIMEOUT_S = 10


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
    open_q = [i for i in issues if i.assignee == side and i.state == "open"]
    if not open_q:
        return None
    open_q.sort(key=lambda i: i.created_at or datetime.min.replace(tzinfo=timezone.utc))
    return open_q[0]


def alarm(repo_root: str, states: dict[str, SideState],
          issues: list[Issue], now: datetime | None = None) -> list[dict]:
    """A13 alarm rows, one per side: staleness (minutes since last
    state-file commit) next to the oldest open assigned question. Each
    row also carries `questions_first_flag`: the F6 flag text when the
    side started a fold/task while a question was owed (flags.py), else
    None — the flag is caught here the way a stale claim is."""
    now = now or datetime.now(timezone.utc)
    flags = {v["side"]: format_flag(v) for v in find_violations(states, issues)}
    rows = []
    for side in ("author", "harbor", "cc"):
        rel = f"state/{side}.md"
        last = last_commit_time(repo_root, rel)
        mins = staleness_minutes(last, now)
        q = oldest_open_question(issues, side)
        pending = q is not None or bool(states[side].claim)
        rows.append({
            "side": side,
            "last_commit": last.isoformat() if last else None,
            "stale_minutes": round(mins, 1) if mins is not None else None,
            "stale": is_stale(last, now, pending),
            "oldest_open_question": q.number if q else None,
            "oldest_open_question_title": q.title if q else "",
            "claim": states[side].claim,
            "questions_first_flag": flags.get(side),
        })
    return rows
