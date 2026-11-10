"""Priority column (JJ's order, Nov 10 2026): every board item carries
a priority field, shown as its own column on the rendered board.

Ordering: owed questions first (870 §12, unchanged), then priority
items (P1, then P2, then P3), then the rest. A priority item stays
visible at the top of its section until it is done or explicitly
deprioritized — a newly arrived ordinary item never buries it.
Levels: P1/P2/P3, with High/Med/Low accepted as aliases; the team pins
the final levels by packet.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.assign import assign, pick_head_item  # noqa: E402
from muse_planning.board import render_board, render_board_with_alarm  # noqa: E402
from muse_planning.model import (BacklogItem, Issue, SideState,  # noqa: E402
                                 normalize_priority, parse_backlog)
from muse_planning.queue import (format_queue, ordered_queue,  # noqa: E402
                                 ordered_queue_all)
from muse_planning.store import Refusal  # noqa: E402


def _item(title, priority="", status="ready"):
    return BacklogItem(title=title, status=status, spec="s", kill="k",
                       priority=priority)


def _states():
    return {s: SideState(side=s) for s in ("author", "harbor", "cc")}


def run_cli(*args, root):
    from muse_planning.cli import main
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--root", str(root), *args])
    return code, out.getvalue(), err.getvalue()


class ParseCase(unittest.TestCase):
    def test_priority_segment_parsed(self):
        text = """# BACKLOG

## Movable research items (head first)

- ordinary task | owner: author | spec: s | kill: k | est: 1d | status: ready
- urgent task | owner: author | priority: P1 | spec: s | kill: k | est: 1d | status: ready
- medium task | owner: author | priority: P2 | spec: s | kill: k | est: 1d | status: ready
"""
        items = parse_backlog(text)
        by_title = {i.title: i for i in items}
        self.assertEqual(by_title["ordinary task"].priority, "")
        self.assertEqual(by_title["urgent task"].priority, "P1")
        self.assertEqual(by_title["medium task"].priority, "P2")

    def test_aliases_normalized(self):
        for label, want in (("High", "P1"), ("high", "P1"), ("HIGH", "P1"),
                            ("Med", "P2"), ("medium", "P2"), ("Low", "P3"),
                            ("p1", "P1"), ("P3", "P3")):
            self.assertEqual(normalize_priority(label), want, label)

    def test_unknown_label_is_unprioritized_not_an_error(self):
        self.assertEqual(normalize_priority("urgent"), "")
        self.assertEqual(normalize_priority(""), "")
        text = ("## Movable research items (head first)\n\n"
                "- typo task | owner: author | priority: urgent | spec: s "
                "| kill: k | est: 1d | status: ready\n")
        self.assertEqual(parse_backlog(text)[0].priority, "")

    def test_priority_rank_orders_p1_first(self):
        self.assertLess(_item("a", "P1").priority_rank,
                        _item("b", "P2").priority_rank)
        self.assertLess(_item("b", "P2").priority_rank,
                        _item("c", "P3").priority_rank)
        self.assertLess(_item("c", "P3").priority_rank,
                        _item("d", "").priority_rank)


class OrderingCase(unittest.TestCase):
    def setUp(self):
        self.items = [_item("ordinary one"), _item("urgent one", "P1"),
                      _item("medium one", "P2"), _item("ordinary two"),
                      _item("low one", "P3")]
        self.states = _states()

    def test_per_side_queue_priority_first_then_pull_order(self):
        queue = ordered_queue("author", [], self.states["author"], self.items)
        titles = [e.title for e in queue]
        self.assertEqual(titles, ["urgent one", "medium one", "low one",
                                  "ordinary one", "ordinary two"])
        self.assertEqual([e.priority for e in queue],
                         ["P1", "P2", "P3", "", ""])

    def test_unified_queue_priority_first_then_pull_order(self):
        queue = ordered_queue_all(self.states, [], self.items)
        titles = [e.title for e in queue]
        self.assertEqual(titles, ["urgent one", "medium one", "low one",
                                  "ordinary one", "ordinary two"])

    def test_owed_question_still_heads_ahead_of_priority(self):
        """F6 outranks priority: an owed question is the head even when
        a P1 item is waiting. Questions carry no priority field."""
        q = Issue(number=1, title="what data?", assignee="author",
                  created_at=datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc))
        queue = ordered_queue("author", [q], self.states["author"], self.items)
        self.assertEqual(queue[0].kind, "answer")
        self.assertEqual(queue[0].ref, "answer:1")
        self.assertEqual(queue[0].priority, "")
        self.assertEqual(queue[1].title, "urgent one")

    def test_format_queue_carries_the_priority_column(self):
        queue = ordered_queue("author", [], self.states["author"], self.items)
        out = format_queue(queue)
        self.assertIn("prio P1", out)
        self.assertIn("prio P2", out)
        self.assertIn("prio \u2014", out)  # unprioritized shows an em dash
        self.assertIn("HEAD OF QUEUE", out.splitlines()[0])


class StickinessCase(unittest.TestCase):
    def test_new_ordinary_item_does_not_bury_a_priority_item(self):
        """A priority item stays at the top of its section: appending a
        new ordinary item at the tail leaves the P1 item head."""
        items = [_item("urgent one", "P1"), _item("ordinary one")]
        states = _states()
        head = ordered_queue("author", [], states["author"], items)[0]
        self.assertEqual(head.title, "urgent one")
        items.append(_item("brand new ordinary"))
        queue = ordered_queue("author", [], states["author"], items)
        self.assertEqual(queue[0].title, "urgent one")
        self.assertEqual(queue[-1].title, "brand new ordinary")

    def test_new_priority_item_does_not_bury_a_higher_priority_item(self):
        items = [_item("urgent one", "P1")]
        states = _states()
        items.append(_item("new medium", "P2"))
        queue = ordered_queue("author", [], states["author"], items)
        self.assertEqual(queue[0].title, "urgent one")
        self.assertEqual(queue[1].title, "new medium")

    def test_deprioritization_drops_the_item_back_to_pull_order(self):
        items = [_item("ordinary one"), _item("was urgent", "P1")]
        states = _states()
        queue = ordered_queue("author", [], states["author"], items)
        self.assertEqual(queue[0].title, "was urgent")
        items[1].priority = ""  # explicitly deprioritized
        queue = ordered_queue("author", [], states["author"], items)
        self.assertEqual([e.title for e in queue],
                         ["ordinary one", "was urgent"])

    def test_done_priority_item_leaves_the_queue(self):
        items = [_item("urgent one", "P1"), _item("ordinary one")]
        states = _states()
        items[0].status = "done"
        queue = ordered_queue("author", [], states["author"], items)
        self.assertEqual([e.title for e in queue], ["ordinary one"])


class AssignerCase(unittest.TestCase):
    def test_assign_picks_the_priority_item_first(self):
        items = [_item("ordinary one"), _item("urgent one", "P1")]
        side, item = assign(_states(), items, [])
        self.assertEqual(item.title, "urgent one")
        self.assertEqual(item.priority, "P1")

    def test_assign_still_returns_the_answer_before_priority(self):
        q = Issue(number=1, title="what data?", assignee="cc",
                  created_at=datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc))
        items = [_item("urgent one", "P1")]
        side, item = assign(_states(), items, [q])
        self.assertEqual(side, "cc")
        self.assertEqual(item.title, "answer:1")

    def test_pick_head_item_skips_watch_only_even_when_priority(self):
        items = [_item("watch the bar", "P1")]
        items[0].kind = "watch"
        self.assertIsNone(pick_head_item(items))


class BoardCase(unittest.TestCase):
    def test_board_queue_section_shows_priority_column(self):
        states = _states()
        items = [_item("ordinary one"), _item("urgent one", "P1")]
        out = render_board(states, [], items)
        self.assertIn("## Queue (questions first)", out)
        self.assertIn("prio P1", out)
        self.assertLess(out.index("urgent one"), out.index("ordinary one"))
        self.assertIn("HEAD OF QUEUE", out)

    def test_board_priority_item_stays_at_top_of_its_section(self):
        states = _states()
        items = [_item("urgent one", "P1"), _item("ordinary one"),
                 _item("brand new ordinary")]
        out = render_board_with_alarm(Path("/nonexistent"), states, [], items)
        queue_section = out.split("## Queue (questions first)")[1]
        queue_section = queue_section.split("## Questions-first flags")[0]
        first_task = [ln for ln in queue_section.splitlines()
                      if ln.startswith("1. ")][0]
        self.assertIn("urgent one", first_task)
        self.assertIn("prio P1", first_task)


class CliCase(unittest.TestCase):
    BACKLOG = """# BACKLOG — test fixture

## Movable research items (head first)

- ordinary task | owner: author | working: author | spec: s | kill: k | est: 1d | status: ready
- urgent task | owner: author | working: author | spec: s | kill: k | est: 1d | status: ready
- urgent task follow-up | owner: author | working: author | spec: s | kill: k | est: 1d | status: ready
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)
        (self.root / "BACKLOG.md").write_text(self.BACKLOG, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_priority_sets_the_level(self):
        code, out, _ = run_cli("priority", "--item", "urgent task",
                               "--level", "P1", root=self.root)
        # "urgent task" matches two titles — refused as ambiguous.
        self.assertEqual(code, 2)
        self.assertIn("ambiguous", out + _)
        code, out, _ = run_cli("priority", "--item", "urgent task follow-up",
                               "--level", "High", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("P1", out)
        items = parse_backlog((self.root / "BACKLOG.md").read_text(encoding="utf-8"))
        by_title = {i.title: i for i in items}
        self.assertEqual(by_title["urgent task follow-up"].priority, "P1")
        self.assertEqual(by_title["urgent task"].priority, "")
        # And the queue now heads with it.
        code, out, _ = run_cli("queue", "--side", "author", root=self.root)
        self.assertEqual(code, 0)
        self.assertLess(out.index("urgent task follow-up"),
                        out.index("ordinary task"))
        self.assertIn("prio P1", out)

    def test_priority_none_deprioritizes(self):
        run_cli("priority", "--item", "urgent task follow-up",
                "--level", "P1", root=self.root)
        code, out, _ = run_cli("priority", "--item", "urgent task follow-up",
                               "--level", "none", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("deprioritized", out)
        items = parse_backlog((self.root / "BACKLOG.md").read_text(encoding="utf-8"))
        by_title = {i.title: i for i in items}
        self.assertEqual(by_title["urgent task follow-up"].priority, "")
        self.assertNotIn("priority:",
                         (self.root / "BACKLOG.md").read_text(encoding="utf-8"))

    def test_priority_unknown_level_refused(self):
        code, _, err = run_cli("priority", "--item", "ordinary task",
                               "--level", "urgent", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("unknown priority level", err)

    def test_priority_no_match_refused(self):
        code, _, err = run_cli("priority", "--item", "no such task",
                               "--level", "P1", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("no backlog item matching", err)

    def test_priority_alias_med_accepted(self):
        code, out, _ = run_cli("priority", "--item", "ordinary task",
                               "--level", "Med", root=self.root)
        self.assertEqual(code, 0)
        items = parse_backlog((self.root / "BACKLOG.md").read_text(encoding="utf-8"))
        by_title = {i.title: i for i in items}
        self.assertEqual(by_title["ordinary task"].priority, "P2")


if __name__ == "__main__":
    unittest.main()
