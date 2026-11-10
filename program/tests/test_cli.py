"""End-to-end CLI: migrate -> render -> ask -> refused -> answer -> granted."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SEED = Path(__file__).resolve().parent.parent.parent
PROG = Path(__file__).resolve().parent.parent


def run(*args, root):
    """Run the CLI in-process (no subprocess) and capture stdout/stderr."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    from muse_planning.cli import main
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--root", str(root), *args])
    return code, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Copy the seeded repo root (minus STATE.md: frozen, never read here).
        for name in ("STATUS.md", "CONTROL.md", "BACKLOG.md", "QUEUE_author.md"):
            shutil.copy(SEED / name, self.root / name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_flow_on_seeded_files(self):
        # Seeded CONTROL is PAUSED seq 8: migrate + render work, claims refuse.
        code, out, _ = run("migrate", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("state/author.md", out)
        for side in ("author", "harbor", "cc"):
            self.assertTrue((self.root / "state" / f"{side}.md").exists())
        code, out, _ = run("render", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("- author |", out)
        self.assertIn("- harbor |", out)
        self.assertIn("- cc |", out)
        self.assertIn("881", out)
        # Poll under PAUSED is silent (wake false).
        code, out, _ = run("poll", "--side", "author", root=self.root)
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)["wake"])

        # Flip CONTROL to RUN for the claim flow (fixture-only edit).
        (self.root / "CONTROL.md").write_text(
            (self.root / "CONTROL.md").read_text(encoding="utf-8")
            .replace("mode: PAUSED", "mode: RUN")
            .replace("control-seq: 8", "control-seq: 9"),
            encoding="utf-8")
        # Ask cc a question -> #1.
        code, out, _ = run("ask", "--assignee", "cc", "--title", "TUNE-2 vote?",
                           "--asked-in", "author 900", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("#1", out)
        # cc's research claim is refused while #1 is open.
        code, out, err = run("claim", "--side", "cc",
                             "--item", "time-data rows C1/C2/retry",
                             "--kind", "research", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("#1", err)
        # Answer #1, then the same claim is granted.
        code, out, _ = run("answer", "--number", "1", root=self.root)
        self.assertEqual(code, 0)
        code, out, _ = run("claim", "--side", "cc",
                           "--item", "time-data rows C1/C2/retry",
                           "--kind", "research", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("CLAIMED cc", out)
        # A second claim for cc is refused (WIP 1).
        code, out, err = run("claim", "--side", "cc",
                             "--item", "Swing Clock odds-reuse design (3) level-reach + (2) exit/timing",
                             "--kind", "research", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("WIP 1", err)
        # Assign picks a free side (author or harbor), never cc.
        code, out, _ = run("assign", root=self.root)
        self.assertEqual(code, 0)
        self.assertNotIn("ASSIGN cc", out)

    def test_render_write_uses_f1(self):
        run("migrate", root=self.root)
        code, out, _ = run("render", "--write", root=self.root)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "board" / "STATUS.md").exists())
        # A second render --write succeeds (base re-read fresh each time).
        code, _, _ = run("render", "--write", root=self.root)
        self.assertEqual(code, 0)

    def test_questions_first_end_to_end(self):
        """Questions-first (req 1 + req 4) through the CLI: an owed
        question is assigned before backlog work; a fold posted while
        it is owed is flagged and wakes the watcher."""
        run("migrate", root=self.root)
        (self.root / "CONTROL.md").write_text(
            (self.root / "CONTROL.md").read_text(encoding="utf-8")
            .replace("mode: PAUSED", "mode: RUN")
            .replace("control-seq: 8", "control-seq: 9"),
            encoding="utf-8")
        # Ask cc a question -> #1; assign must return the answer, not
        # a backlog item for another side.
        code, out, _ = run("ask", "--assignee", "cc",
                           "--title", "What data does the mining need?",
                           "--asked-in", "author 893", root=self.root)
        self.assertEqual(code, 0)
        code, out, _ = run("assign", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("ASSIGN cc <- 'answer:1'", out)
        # A fold claim for cc is refused while #1 is open.
        code, out, err = run("claim", "--side", "cc", "--item",
                             "fold of author 886", "--kind", "work",
                             root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("#1", err)
        # Rewind the question's ask time and advance cc's last output
        # past it (fixture edits, as the CONTROL flip above): cc posted
        # a fold while #1 was owed -> flags lists it, poll wakes.
        issues = json.loads((self.root / "issues.json").read_text(encoding="utf-8"))
        issues[0]["created_at"] = "2026-11-09T10:00:00Z"
        (self.root / "issues.json").write_text(
            json.dumps(issues, indent=2) + "\n", encoding="utf-8")
        cc_state = (self.root / "state" / "cc.md").read_text(encoding="utf-8")
        cc_state = cc_state.replace("packet 490 2026-11-09T21:05:40Z",
                                    "packet 506 2026-11-09T21:45:54Z")
        (self.root / "state" / "cc.md").write_text(cc_state, encoding="utf-8")
        code, out, _ = run("flags", root=self.root)
        self.assertEqual(code, 0)
        flags = json.loads(out)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["side"], "cc")
        self.assertEqual(flags[0]["question"], 1)
        # Commit all three state files at "now" so no side is A13-stale:
        # the poll wake below must come from the flag alone, not from
        # staleness (in a non-git dir an unknown commit time reads stale).
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        env = dict(os.environ,
                   GIT_AUTHOR_DATE=now, GIT_COMMITTER_DATE=now)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@local"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "test"],
                       cwd=self.root, check=True)
        subprocess.run(["git", "add", "state"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "state"], cwd=self.root,
                       check=True, env=env)
        code, out, _ = run("poll", "--side", "author", root=self.root)
        self.assertEqual(code, 0)
        digest = json.loads(out)
        self.assertEqual(digest["stale_sides"], [])
        self.assertTrue(digest["wake"])
        self.assertEqual(len(digest["questions_first_flags"]), 1)
        # The board shows the owed question ahead of the task lines and
        # carries the flag section.
        code, out, _ = run("render", root=self.root)
        self.assertEqual(code, 0)
        self.assertLess(out.index("## Owed questions"),
                        out.index("- author |"))
        self.assertIn("FLAG cc", out)


if __name__ == "__main__":
    unittest.main()
