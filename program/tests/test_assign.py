"""Assigner: rotation, WIP 1, never double-assigns, answer-first."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.assign import assign, free_sides, pick_head_item  # noqa: E402
from muse_planning.model import Issue, SideState, parse_backlog  # noqa: E402
from muse_planning.store import Refusal  # noqa: E402


class AssignCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.states = {s: SideState.from_text(
            (self.root / "state" / f"{s}.md").read_text(encoding="utf-8"))
            for s in ("author", "harbor", "cc")}
        self.items = parse_backlog(
            (self.root / "BACKLOG.md").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_rotation_goes_least_recently_assigned_first(self):
        """(d) The assigner rotates across sides."""
        t0 = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
        self.states["author"].last_assigned = t2  # most recent
        self.states["harbor"].last_assigned = t0  # least recent
        self.states["cc"].last_assigned = t1
        side, item = assign(self.states, self.items, [])
        self.assertEqual(side, "harbor")
        self.assertEqual(item.title, "time-data rows C1/C2/retry")

    def test_rotation_cycles_through_all_sides(self):
        seen = []
        for _ in range(3):
            side, _ = assign(self.states, self.items, [])
            seen.append(side)
            # Simulate the side finishing (release) so it can be picked again.
            self.states[side].claim = ""
        self.assertEqual(sorted(seen), ["author", "cc", "harbor"])

    def test_never_double_assigns_busy_side(self):
        """(d) WIP 1: a busy side is never assigned twice."""
        self.states["author"].claim = "something"
        self.states["harbor"].claim = "something else"
        side, _ = assign(self.states, self.items, [])
        self.assertEqual(side, "cc")

    def test_owed_question_is_head_of_queue(self):
        """Questions-first (req 1): a side with an open question is
        assigned the ANSWER to it, ahead of any backlog item. This
        supersedes the old behavior (skip the blocked side and assign
        backlog work to someone else) — the owed question is the head
        of the queue, not something to route around."""
        issues = [Issue(number=1, title="TUNE-2 vote?", assignee="author")]
        side, item = assign(self.states, self.items, issues)
        self.assertEqual(side, "author")
        self.assertEqual(item.title, "answer:1")
        self.assertEqual(item.kind, "answer")

    def test_side_with_open_question_not_in_free_sides(self):
        """free_sides still excludes a side with an open question (it
        takes no backlog work); the assigner gives it the answer
        instead (see test_owed_question_is_head_of_queue)."""
        issues = [Issue(number=1, title="TUNE-2 vote?", assignee="author")]
        free = free_sides(self.states, issues)
        self.assertNotIn("author", free)

    def test_oldest_owed_question_first(self):
        """When two sides owe answers, the question that waited longest
        is assigned first."""
        t_old = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 11, 9, 11, 0, tzinfo=timezone.utc)
        issues = [
            Issue(number=2, title="newer Q", assignee="cc", created_at=t_new),
            Issue(number=1, title="older Q", assignee="harbor", created_at=t_old),
        ]
        side, item = assign(self.states, self.items, issues)
        self.assertEqual(side, "harbor")
        self.assertEqual(item.title, "answer:1")

    def test_busy_assignee_answer_waits_other_sides_still_work(self):
        """A question whose assignee holds a claim (WIP 1) waits for that
        side to free up; other free sides still get backlog work — the
        refusal is per-side, and the whole team is not blocked on one
        busy side."""
        issues = [Issue(number=1, title="TUNE-2 vote?", assignee="author")]
        self.states["author"].claim = "busy fold"
        side, item = assign(self.states, self.items, issues)
        self.assertIn(side, ("harbor", "cc"))
        self.assertEqual(item.title, "time-data rows C1/C2/retry")

    def test_no_free_side_refuses(self):
        for s in self.states.values():
            s.claim = "busy"
        with self.assertRaises(Refusal):
            assign(self.states, self.items, [])

    def test_watch_only_head_is_skipped_not_assigned(self):
        items = [i for i in self.items if i.watch_only]
        self.assertEqual(pick_head_item(items), None)
        # With only a watch-only item, assign refuses (A7).
        with self.assertRaises(Refusal):
            assign(self.states, items, [])

    def test_needs_spec_head_is_skipped(self):
        items = [i for i in self.items if i.status.startswith("needs spec")]
        self.assertEqual(pick_head_item(items), None)


if __name__ == "__main__":
    unittest.main()
