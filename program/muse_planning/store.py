"""Repo store: paths, hashing, atomic writes, and the F1 discipline.

F1 (Harbor 442, cc 490 §2(a)): any program write to shared board state
re-reads the live board, asserts the base sha/md5 immediately before
writing, aborts on mismatch, and touches only its own side's line. A
program that writes on a stale base reproduces the 34th-41st strikes at
machine speed — so it must not.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


class StaleBaseError(Exception):
    """The live file moved under us: expected base sha != live sha. Abort,
    write nothing."""


class Refusal(Exception):
    """A gate refused the requested action. The message names the reason
    (and, for answer-first, the blocking question)."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    """Write via a temp file + rename, so a reader never sees a half file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Repo:
    """A checkout of adr175syd/muse-planning (or a fixture copy of it)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    # -- state files ---------------------------------------------------
    def state_path(self, side: str) -> Path:
        return self.path("state", f"{side}.md")

    def state_exists(self, side: str) -> bool:
        return self.state_path(side).exists()

    # -- shared files --------------------------------------------------
    def control_path(self) -> Path:
        return self.path("CONTROL.md")

    def backlog_path(self) -> Path:
        return self.path("BACKLOG.md")

    def issues_path(self) -> Path:
        return self.path("issues.json")

    def ledger_path(self) -> Path:
        return self.path("ledger.json")

    def board_path(self) -> Path:
        return self.path("board", "STATUS.md")

    def seen_path(self, side: str) -> Path:
        return self.path(".seen", f"{side}.json")


def f1_write(path: Path, base_sha: str, new_data: bytes) -> str:
    """F1 checked write. Re-reads `path` immediately before writing and
    aborts (raising StaleBaseError, writing nothing) unless the live sha
    still equals `base_sha`. Returns the new sha on success."""
    if not path.exists():
        raise FileNotFoundError(f"f1_write: {path} does not exist")
    live = path.read_bytes()
    if sha256_hex(live) != base_sha:
        raise StaleBaseError(
            f"f1_write ABORT: {path} moved under us "
            f"(base {base_sha[:12]}... != live {sha256_hex(live)[:12]}...); "
            f"wrote nothing"
        )
    atomic_write(path, new_data)
    return sha256_hex(new_data)


def f1_write_own_line(path: Path, base_sha: str, side: str, new_line: str) -> str:
    """F1 checked write scoped to one side's board line. Re-reads the board,
    asserts the base sha, replaces ONLY the line starting with `- <side> |`
    and asserts every other line is byte-identical to the base. Returns the
    new sha. Raises StaleBaseError on a moved base; ValueError if the side
    has no line (a side that is not on the board cannot write to it)."""
    if not path.exists():
        raise FileNotFoundError(f"f1_write_own_line: {path} does not exist")
    live = path.read_bytes()
    if sha256_hex(live) != base_sha:
        raise StaleBaseError(
            f"f1_write_own_line ABORT: {path} moved under us "
            f"(base {base_sha[:12]}... != live {sha256_hex(live)[:12]}...); "
            f"wrote nothing"
        )
    lines = live.decode("utf-8").split("\n")
    prefix = f"- {side} |"
    idx = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(idx) != 1:
        raise ValueError(
            f"f1_write_own_line: side {side!r} has {len(idx)} board lines "
            f"(need exactly 1); wrote nothing"
        )
    lines[idx[0]] = new_line
    return f1_write(path, base_sha, "\n".join(lines).encode("utf-8"))
