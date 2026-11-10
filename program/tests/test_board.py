"""Board rendering: from the seeded Drive files, and from fixtures."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.board import (migrate_status_to_state,  # noqa: E402
                                 render_board_with_alarm)
from muse_planning.model import SIDES, SideState  # noqa: E402

SEED = Path(__file__).resolve().parent.parent.parent  # github-seed/


class TestMigrateSeededBoard(unittest.TestCase):
    def test_migrate_real_status_md(self):
        """(a) The board renders from the seeded state files: migrate the
        real STATUS.md and check all three sides come out with their
        real current items."""
        text = (SEED / "STATUS.md").read_text(encoding="utf-8")
        states = migrate_status_to_state(text)
        self.assertEqual(set(states), set(SIDES))
        self.assertIn("881", states["author"].current)
        self.assertIn("493", states["harbor"].current)
        self.assertIn("845", states["cc"].current)
        # The board's quirks parse too: colon-less 'started <ts>' on the
        # author/cc lines, and 'last output' (space in the field name).
        self.assertIsNotNone(states["author"].started)
        self.assertIsNotNone(states["cc"].started)
        self.assertIn("881", states["author"].last_output)
        self.assertIn("490", states["cc"].last_output)
        # Round-trip: state file serialises and re-parses identically.
        for side, st in states.items():
            self.assertEqual(SideState.from_text(st.to_text()).current, st.current)

    def test_migrate_missing_side_raises(self):
        with self.assertRaises(ValueError):
            migrate_status_to_state("- author | current: x\n")


class TestRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.states = {}
        for side in SIDES:
            p = self.root / "state" / f"{side}.md"
            self.states[side] = SideState.from_text(p.read_text(encoding="utf-8"))
        self.states["author"].current = "author 900 - test item"
        self.states["author"].progress = "900 posted"

    def tearDown(self):
        self.tmp.cleanup()

    def test_render_has_one_line_per_side(self):
        out = render_board_with_alarm(self.root, self.states, [])
        for side in SIDES:
            self.assertIn(f"- {side} |", out)
        self.assertIn("author 900 - test item", out)
        self.assertIn("## Owed questions (head of queue — answer first): 0", out)
        self.assertIn("## A13 alarm", out)
        self.assertIn("## Questions-first flags", out)
        self.assertIn("- none", out)

    def test_render_lists_open_questions(self):
        from muse_planning.model import Issue
        issues = [Issue(number=7, title="TUNE-2 vote?", assignee="cc",
                        asked_in="author 900")]
        out = render_board_with_alarm(self.root, self.states, issues)
        self.assertIn("## Owed questions (head of queue — answer first): 1", out)
        self.assertIn("#7 [cc] TUNE-2 vote?", out)

    def test_owed_questions_render_ahead_of_task_lines(self):
        """Questions-first (req 3): the owed-questions section renders
        ABOVE the per-side task lines — the board shows what is owed
        before what is being worked on."""
        from muse_planning.model import Issue
        issues = [Issue(number=7, title="TUNE-2 vote?", assignee="cc",
                        asked_in="author 900")]
        out = render_board_with_alarm(self.root, self.states, issues)
        q_at = out.index("## Owed questions")
        first_side = min(out.index(f"- {s} |") for s in SIDES)
        self.assertLess(q_at, first_side)

    def test_render_flags_fold_while_question_owed(self):
        """Questions-first (req 4): a side that posted output after its
        question was asked is flagged on the board, with the evidence."""
        from datetime import datetime, timezone
        from muse_planning.model import Issue
        self.states["cc"].last_output = "packet 506 2026-11-10T02:45:54Z"
        issues = [Issue(number=12, title="What data does the mining need?",
                        assignee="cc", asked_in="author 893",
                        created_at=datetime(2026, 11, 10, 2, 34, 38,
                                            tzinfo=timezone.utc))]
        out = render_board_with_alarm(self.root, self.states, issues)
        # The flag's canonical text names the rule + side (reconciled:
        # "FLAG questions-first: cc ..."); the board also names the
        # question and the posted output as evidence.
        self.assertIn("FLAG questions-first: cc", out)
        self.assertIn("#12", out)
        self.assertIn("packet 506", out)


if __name__ == "__main__":
    unittest.main()
