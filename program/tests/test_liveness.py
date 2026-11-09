"""Liveness: commit times, not mtimes. Uses real temp git repos."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.liveness import (alarm, is_stale, last_commit_time,  # noqa: E402
                                    staleness_minutes)
from muse_planning.model import Issue, SideState  # noqa: E402


def git(*args, cwd, env=None):
    e = dict(os.environ)
    e.update(env or {})
    subprocess.run(["git", *args], cwd=cwd, env=e, check=True,
                   capture_output=True, text=True)


def init_repo_with_commits(root: Path) -> None:
    """A git repo where state/author.md was last committed 2026-11-09
    10:00 UTC and state/harbor.md 2026-11-09 12:30 UTC; state/cc.md is
    uncommitted (never committed)."""
    git("init", "-q", cwd=root)
    git("config", "user.email", "test@local", cwd=root)
    git("config", "user.name", "test", cwd=root)
    (root / "state").mkdir(exist_ok=True)
    (root / "state" / "author.md").write_text("author state\n", encoding="utf-8")
    git("add", "state/author.md", cwd=root)
    git("commit", "-qm", "author state", cwd=root,
        env={"GIT_AUTHOR_DATE": "2026-11-09T10:00:00Z",
             "GIT_COMMITTER_DATE": "2026-11-09T10:00:00Z"})
    (root / "state" / "harbor.md").write_text("harbor state\n", encoding="utf-8")
    git("add", "state/harbor.md", cwd=root)
    git("commit", "-qm", "harbor state", cwd=root,
        env={"GIT_AUTHOR_DATE": "2026-11-09T12:30:00Z",
             "GIT_COMMITTER_DATE": "2026-11-09T12:30:00Z"})
    (root / "state" / "cc.md").write_text("cc state (uncommitted)\n", encoding="utf-8")


class LivenessCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        init_repo_with_commits(self.root)
        self.now = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def test_last_commit_time_reads_git_not_mtime(self):
        """(f) Liveness reads commit times."""
        t = last_commit_time(str(self.root), "state/author.md")
        self.assertEqual(t, datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc))
        t = last_commit_time(str(self.root), "state/harbor.md")
        self.assertEqual(t, datetime(2026, 11, 9, 12, 30, tzinfo=timezone.utc))
        # cc.md is uncommitted: no commit time (unknown, never fresh).
        self.assertIsNone(last_commit_time(str(self.root), "state/cc.md"))
        # A file that does not exist: None, not an exception.
        self.assertIsNone(last_commit_time(str(self.root), "state/nope.md"))

    def test_staleness_minutes_from_commit_time(self):
        t = last_commit_time(str(self.root), "state/author.md")
        self.assertAlmostEqual(staleness_minutes(t, self.now), 180.0)

    def test_is_stale_threshold_60m_with_pending(self):
        old = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
        fresh = datetime(2026, 11, 9, 12, 30, tzinfo=timezone.utc)
        self.assertTrue(is_stale(old, self.now, pending=True))
        self.assertFalse(is_stale(fresh, self.now, pending=True))
        # Nothing pending: never stale.
        self.assertFalse(is_stale(old, self.now, pending=False))
        # Unknown commit time + pending: stale (never silently fresh).
        self.assertTrue(is_stale(None, self.now, pending=True))

    def test_alarm_rows_pair_staleness_with_oldest_question(self):
        states = {s: SideState(side=s) for s in ("author", "harbor", "cc")}
        issues = [Issue(number=3, title="old Q", assignee="author",
                        created_at=datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)),
                  Issue(number=5, title="newer Q", assignee="author",
                        created_at=datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc))]
        rows = alarm(str(self.root), states, issues, self.now)
        by_side = {r["side"]: r for r in rows}
        # author: last commit 10:00, now 13:00 -> 180m, stale, oldest Q is #3.
        self.assertTrue(by_side["author"]["stale"])
        self.assertEqual(by_side["author"]["oldest_open_question"], 3)
        self.assertAlmostEqual(by_side["author"]["stale_minutes"], 180.0)
        # harbor: last commit 12:30 -> 30m, fresh, no question.
        self.assertFalse(by_side["harbor"]["stale"])
        self.assertIsNone(by_side["harbor"]["oldest_open_question"])
        # cc: uncommitted -> unknown time, stale (a claim is pending? no
        # claim and no question -> not stale). Give cc a claim: stale.
        self.assertFalse(by_side["cc"]["stale"])
        states["cc"].claim = "something"
        rows = alarm(str(self.root), states, issues, self.now)
        by_side = {r["side"]: r for r in rows}
        self.assertTrue(by_side["cc"]["stale"])
        self.assertIsNone(by_side["cc"]["stale_minutes"])


if __name__ == "__main__":
    unittest.main()
