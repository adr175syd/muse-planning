"""End-to-end CLI: migrate -> render -> ask -> refused -> answer -> granted."""
import json
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


if __name__ == "__main__":
    unittest.main()
