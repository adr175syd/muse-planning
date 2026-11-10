"""Data model for the muse-planning program.

Everything here is plain data + parsers. No I/O beyond reading text that
the caller hands in, no network, no GitHub calls. The repo layout the
program works on (repo root = the directory holding STATUS.md etc.):

  state/<side>.md    one file per side (author | harbor | cc) — the side's
                     STATUS-line equivalent + heartbeat progress:. Owned
                     ONLY by that side. The program never writes another
                     side's file.
  issues.json        local mirror of GitHub Issues labelled `question`
                     (offline-safe; in deployment the watcher syncs it
                     from `gh issue list --label question`).
  ledger.json        {"next": <int>} — next serial ledger number. Only the
                     merge step advances it.
  board/STATUS.md    RENDERED board (derived artifact). Sides never
                     hand-write it; the program renders it from the three
                     state files + issues.json.
  BACKLOG.md         shared research pool (adopted format, see
                     PLANNING_SYSTEM_BUILD.md §2.1).
  CONTROL.md         mode switch. The program READS it; it NEVER writes it
                     (A4: mode changes only on John's word).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

SIDES = ("author", "harbor", "cc")
SIDES_ORDER = ("author", "harbor", "cc")  # tie-break order for rotation

# A13 staleness: no output for > 60 min while a packet/question is pending.
STALE_MINUTES = 60


def parse_time(value: str) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp; returns None on garbage (never raise)."""
    value = value.strip().rstrip("Z")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_time(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SideState:
    """One side's state file (state/<side>.md)."""
    side: str
    updated: datetime | None = None
    current: str = ""
    started: datetime | None = None
    est: str = ""
    blocked_on: str = ""
    progress: str = ""
    last_output: str = ""
    # claim: "" (none) or "<item-id>" while WIP 1 is held.
    claim: str = ""
    claim_kind: str = ""  # "answer" | "fold" | "work" | "research"
    claim_started: datetime | None = None
    # last assignment time, for rotation (least-recently-assigned first).
    last_assigned: datetime | None = None

    def to_text(self) -> str:
        lines = [
            f"# state — {self.side}",
            f"side: {self.side}",
            f"updated: {fmt_time(self.updated) if self.updated else ''}",
            f"current: {self.current}",
            f"started: {fmt_time(self.started) if self.started else ''}",
            f"est: {self.est}",
            f"blocked-on: {self.blocked_on}",
            f"progress: {self.progress}",
            f"last-output: {self.last_output}",
            f"claim: {self.claim}",
            f"claim-kind: {self.claim_kind}",
            f"claim-started: {fmt_time(self.claim_started) if self.claim_started else ''}",
            f"last-assigned: {fmt_time(self.last_assigned) if self.last_assigned else ''}",
        ]
        return "\n".join(lines) + "\n"

    @classmethod
    def from_text(cls, text: str) -> "SideState":
        fields: dict[str, str] = {}
        for line in text.splitlines():
            m = re.match(r"^([a-z-]+):\s?(.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2).strip()
        return cls(
            side=fields.get("side", ""),
            updated=parse_time(fields["updated"]) if fields.get("updated") else None,
            current=fields.get("current", ""),
            started=parse_time(fields["started"]) if fields.get("started") else None,
            est=fields.get("est", ""),
            blocked_on=fields.get("blocked-on", ""),
            progress=fields.get("progress", ""),
            last_output=fields.get("last-output", ""),
            claim=fields.get("claim", ""),
            claim_kind=fields.get("claim-kind", ""),
            claim_started=parse_time(fields["claim-started"]) if fields.get("claim-started") else None,
            last_assigned=parse_time(fields["last-assigned"]) if fields.get("last-assigned") else None,
        )

    def board_line(self, owed: list[Issue] | None = None) -> str:
        """The side's one line on the rendered board (same shape as the
        seeded STATUS.md lines: `- <side> | q: ... | current: ...`).
        Owed questions render AHEAD of the current task (`owed:` before
        `current:`), so the state is visible: questions first, tasks
        wait. `owed` is the side's open assigned questions, oldest
        first; pass None (or []) for none owed."""
        q = "folds 0 / answers 0 / builds 0"
        if owed:
            owed_s = "; ".join(f"#{i.number} {i.title}" for i in owed)
        else:
            owed_s = "none"
        started = fmt_time(self.started) if self.started else ""
        return (
            f"- {self.side} | q: {q} | owed: {owed_s}"
            f" | current: {self.current}"
            f" | started: {started} | est: {self.est}"
            f" | blocked-on: {self.blocked_on or 'nothing'}"
            f" | progress: {self.progress}"
            f" | last output: {self.last_output}"
        )


@dataclass
class Issue:
    """A GitHub Issue labelled `question` (local mirror row)."""
    number: int
    title: str
    body: str = ""
    assignee: str = ""  # side the question is asked of
    state: str = "open"  # open | closed
    created_at: datetime | None = None
    closed_at: datetime | None = None
    asked_in: str = ""  # packet that asked it (must cite the Issue number)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "body": self.body,
            "assignee": self.assignee,
            "state": self.state,
            "created_at": fmt_time(self.created_at) if self.created_at else "",
            "closed_at": fmt_time(self.closed_at) if self.closed_at else "",
            "asked_in": self.asked_in,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        return cls(
            number=int(d["number"]),
            title=d.get("title", ""),
            body=d.get("body", ""),
            assignee=d.get("assignee", ""),
            state=d.get("state", "open"),
            created_at=parse_time(d["created_at"]) if d.get("created_at") else None,
            closed_at=parse_time(d["closed_at"]) if d.get("closed_at") else None,
            asked_in=d.get("asked_in", ""),
        )


@dataclass
class BacklogItem:
    """One movable research item from BACKLOG.md."""
    title: str
    owner: str = ""
    working: str = ""
    spec: str = ""
    kill: str = ""
    est: str = ""
    status: str = ""  # ready | needs spec | done | excluded
    kind: str = "research"  # research | verification | fold | watch
    # kind is inferred: status `excluded`/`done` never move; a title that
    # names a fold/verification is kind=verification (A18 fence).

    @property
    def movable(self) -> bool:
        return self.status == "ready" and bool(self.spec.strip()) and bool(self.kill.strip())

    @property
    def watch_only(self) -> bool:
        return self.kind == "watch"


def parse_backlog(text: str) -> list[BacklogItem]:
    """Parse BACKLOG.md items. One line per item: `- <title> | owner: X |
    working: Y | spec: ... | kill: ... | est: ... | status: ...`. Only
    lines under the 'Movable research items' or 'Excluded' sections are
    items — the 'Rules' bullets are not (they have no owner/spec/kill).
    Continuation lines (indented notes) are ignored."""
    items: list[BacklogItem] = []
    in_items = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_items = line.startswith("## Movable research items") or line.startswith("## Excluded")
            continue
        if not in_items or not line.startswith("- "):
            continue
        body = line[2:]
        parts = [p.strip() for p in body.split(" | ")]
        if not parts:
            continue
        title = parts[0]
        fields: dict[str, str] = {}
        for p in parts[1:]:
            m = re.match(r"^([a-z]+):\s?(.*)$", p)
            if m:
                fields[m.group(1)] = m.group(2)
        title_l = title.lower()
        kind = "research"
        if "fold" in title_l or "verif" in title_l or "replication" in title_l:
            kind = "verification"
        if "watch" in title_l:
            kind = "watch"
        items.append(BacklogItem(
            title=title,
            owner=fields.get("owner", ""),
            working=fields.get("working", ""),
            spec=fields.get("spec", ""),
            kill=fields.get("kill", ""),
            est=fields.get("est", ""),
            status=fields.get("status", ""),
            kind=kind,
        ))
    return items


def parse_control(text: str) -> dict[str, str]:
    """Parse CONTROL.md header. Returns mode + control-seq (+ set_by etc.).
    Raises ValueError if mode/seq are missing — a CONTROL file without them
    is not a control file and the program refuses to act on it."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^(mode|control-seq|set_by|set_at|keeper):\s?(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    if "mode" not in fields or "control-seq" not in fields:
        raise ValueError("CONTROL.md has no mode/control-seq — refusing to act")
    return fields


def parse_status_line(line: str) -> dict[str, str]:
    """Parse one seeded STATUS.md line (`- <side> | field: value | ...`)
    into a field dict. Used by `migrate` to build state files from the
    seeded board. Tolerant of the board's two real quirks: field names
    with spaces ('last output') and the colon-less 'started <ts>' form
    the author/cc lines use."""
    if not line.startswith("- "):
        raise ValueError("not a STATUS line")
    body = line[2:]
    parts = [p.strip() for p in body.split(" | ")]
    out: dict[str, str] = {"side": parts[0]}
    for p in parts[1:]:
        m = re.match(r"^([a-z][a-z -]*):\s?(.*)$", p)
        if m:
            out[m.group(1).strip()] = m.group(2)
            continue
        m = re.match(r"^(started|est)\s+(.+)$", p)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def load_issues(text: str) -> list[Issue]:
    data = json.loads(text) if text.strip() else []
    return [Issue.from_dict(d) for d in data]


def dump_issues(issues: list[Issue]) -> str:
    return json.dumps([i.to_dict() for i in issues], indent=2) + "\n"
