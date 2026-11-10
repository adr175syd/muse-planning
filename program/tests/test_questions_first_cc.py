"""Questions-first enforcement (F6, packet 870 §12, cc 487) —
ported to the reconciled implementation (author/reconciled-
questions-first-priority). Adaptations vs cc PR #1, all deliberate:

  - queue vocabulary unified: backlog pool entries are kind "task"
    (not "research") — see queue.py; the ordering assertions are
    unchanged.
  - board header is the reconciled "## Owed questions (head of
    queue — answer first): N" (author's wording); the pinned
    behavior (owed section above the side lines, owed: before
    current:) is unchanged.
  - the detector is the reconciled flags.find_violations (same
    timestamp-ordered legs as cc's flags.py, plus the author's
    last-output leg and Harbor's held markers).
  - `flags` still exits 2 while a flag stands (reconciled decision).
  - `poll` still wakes on the polling side's own flag (and now on
    ANY side's flag — the any-side case is covered by Harbor's port).

The incident: the mining-data question (author 893 §12, out since
21:37 ET Nov 9) waited ~45 minutes while cc posted three folds
(506, 507, 508) with no answer, and no flag fired — because no such
flag existed. These tests pin the four enforcement pieces:

  1. queue: an owed question heads the queue, ahead of folds/tasks.
  2. claim: a fold/task claim is REFUSED while a question is owed.
  3. board: owed questions render ahead of tasks.
  4. flags: a fold started while a question is owed is FLAGGED —
     the watcher/board catch it the way they catch a stale claim.
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
from muse_planning.board import render_board_with_alarm  # noqa: E402
from muse_planning.flags import find_violations, format_flag  # noqa: E402
from muse_planning.gate import (answer_question, ask_question, claim,  # noqa: E402
                                release)
from muse_planning.liveness import alarm  # noqa: E402
from muse_planning.model import Issue, SideState, parse_backlog  # noqa: E402
from muse_planning.queue import head_of_queue, ordered_queue  # noqa: E402
from muse_planning.store import Refusal, Repo  # noqa: E402

# The incident, in UTC: question out 21:37 ET Nov 9 = 02:37Z Nov 10.
Q_AT = datetime(2026, 11, 10, 2, 37, tzinfo=timezone.utc)
FOLD_AT = datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)   # after the question
BEFORE_AT = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)  # before it


def run_cli(*args, root):
    from muse_planning.cli import main
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["--root", str(root), *args])
    return code, out.getvalue(), err.getvalue()


def _states(root):
    return {s: SideState.from_text(
        (root / "state" / f"{s}.md").read_text(encoding="utf-8"))
        for s in ("author", "harbor", "cc")}


def _mining_question():
    return Issue(number=1, title="mining-data question", assignee="cc",
                 created_at=Q_AT, asked_in="author 893")


def _fold_claim(state, at=FOLD_AT, kind="fold", claim="fold 506"):
    state.claim = claim
    state.claim_kind = kind
    state.claim_started = at
    state.current = claim
    state.started = at
    state.updated = at
    return state


class QueueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.states = _states(self.root)
        self.items = parse_backlog(
            (self.root / "BACKLOG.md").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_owed_question_heads_queue_ahead_of_fold_and_tasks(self):
        """(1) An owed question goes to the HEAD of the queue."""
        issues = [_mining_question()]
        _fold_claim(self.states["cc"])
        queue = ordered_queue("cc", issues, self.states["cc"], self.items)
        self.assertEqual(queue[0].kind, "answer")
        self.assertEqual(queue[0].ref, "answer:1")
        kinds = [e.kind for e in queue]
        self.assertEqual(kinds[1], "fold")
        self.assertIn("task", kinds)
        self.assertLess(kinds.index("answer"), kinds.index("fold"))
        self.assertLess(kinds.index("answer"), kinds.index("task"))

    def test_oldest_owed_question_is_head(self):
        q2 = Issue(number=2, title="second question", assignee="cc",
                   created_at=datetime(2026, 11, 10, 2, 50, tzinfo=timezone.utc),
                   asked_in="author 894")
        issues = [q2, _mining_question()]  # out of order on purpose
        head = head_of_queue("cc", issues, self.states["cc"], self.items)
        self.assertEqual(head.ref, "answer:1")

    def test_no_question_head_is_current_claim_then_backlog(self):
        _fold_claim(self.states["cc"])
        head = head_of_queue("cc", [], self.states["cc"], self.items)
        self.assertEqual(head.kind, "fold")
        head2 = head_of_queue("author", [], self.states["author"], self.items)
        self.assertEqual(head2.kind, "task")
        self.assertEqual(head2.title, "time-data rows C1/C2/retry")

    def test_empty_queue(self):
        self.assertIsNone(head_of_queue("author", [], self.states["author"], []))
        self.assertEqual(ordered_queue("author", [], self.states["author"], []), [])


class FoldClaimCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.repo = Repo(self.root)
        self.states = _states(self.root)
        self.items = parse_backlog(
            (self.root / "BACKLOG.md").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_fold_claim_refused_while_question_owed(self):
        """(2) A fold claim is REFUSED while a question is owed — the
        incident replay: question 21:37 ET, fold claim after it."""
        issues = [_mining_question()]
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "cc", "fold 506", "fold", None, issues,
                  self.states["cc"], at=FOLD_AT)
        msg = str(cm.exception)
        self.assertIn("#1", msg)
        self.assertIn("mining-data question", msg)
        self.assertIn("fold", msg.lower())

    def test_work_claim_refused_while_question_owed(self):
        issues = [_mining_question()]
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "cc", "some task", "work", None, issues,
                  self.states["cc"], at=FOLD_AT)
        self.assertIn("#1", str(cm.exception))

    def test_fold_claim_granted_once_question_closed(self):
        issues = [_mining_question()]
        answer_question(issues, 1)
        st = claim(self.repo, "cc", "fold 506", "fold", None, issues,
                   self.states["cc"], at=FOLD_AT)
        self.assertEqual(st.claim, "fold 506")
        self.assertEqual(st.claim_kind, "fold")

    def test_answer_claim_still_granted_while_question_open(self):
        issues = []
        q = ask_question(issues, "mining-data question", "", "cc",
                         "author 893", at=Q_AT)
        st = claim(self.repo, "cc", f"answer:{q.number}", "answer", None,
                   issues, self.states["cc"], at=FOLD_AT)
        self.assertEqual(st.claim, f"answer:{q.number}")

    def test_unknown_claim_kind_refused(self):
        with self.assertRaises(Refusal):
            claim(self.repo, "cc", "fold 506", "packet", None, [],
                  self.states["cc"])


class BoardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.states = _states(self.root)
        self.states["cc"].current = "fold 506 — fold of author 893"

    def tearDown(self):
        self.tmp.cleanup()

    def test_owed_questions_render_ahead_of_task_lines(self):
        """(3) The board renders owed questions ahead of tasks: the Open
        questions section comes before the side lines, and each side's
        `owed:` field comes before its `current:`."""
        issues = [_mining_question()]
        out = render_board_with_alarm(self.root, self.states, issues)
        self.assertLess(out.index("## Owed questions (head of queue — answer first): 1"),
                        out.index("- cc |"))
        self.assertLess(out.index("#1 [cc] mining-data question"),
                        out.index("- cc |"))
        cc_line = [ln for ln in out.splitlines() if ln.startswith("- cc |")][0]
        self.assertLess(cc_line.index("owed: #1 mining-data question"),
                        cc_line.index("current: fold 506"))
        self.assertIn("## Questions-first flags", out)

    def test_clean_board_shows_no_flags(self):
        out = render_board_with_alarm(self.root, self.states, [])
        self.assertIn("## Questions-first flags", out)
        self.assertIn("- none", out)
        cc_line = [ln for ln in out.splitlines() if ln.startswith("- cc |")][0]
        self.assertIn("owed: none", cc_line)


class FlagsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.states = _states(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fold_started_after_question_is_flagged(self):
        """(4) The incident, as the watcher sees it: a fold claim started
        after the question was asked is FLAGGED."""
        _fold_claim(self.states["cc"])
        violations = find_violations(self.states, [_mining_question()])
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v["side"], "cc")
        self.assertEqual(v["question"], 1)
        self.assertEqual(v["claim"], "fold 506")
        self.assertEqual(v["claim_kind"], "fold")
        text = format_flag(v)
        self.assertIn("FLAG questions-first", text)
        self.assertIn("cc", text)
        self.assertIn("#1", text)

    def test_in_flight_fold_started_before_question_is_not_flagged(self):
        """Work started BEFORE the question is in-flight: finish it, then
        answer-first blocks the next claim. Not a violation."""
        _fold_claim(self.states["cc"], at=BEFORE_AT)
        self.assertEqual(find_violations(self.states, [_mining_question()]), [])

    def test_answer_claim_is_not_flagged(self):
        st = self.states["cc"]
        st.claim = "answer:1"
        st.claim_kind = "answer"
        st.claim_started = FOLD_AT
        st.current = "answer:1"
        self.assertEqual(find_violations(self.states, [_mining_question()]), [])

    def test_no_open_question_no_flag(self):
        _fold_claim(self.states["cc"])
        self.assertEqual(find_violations(self.states, []), [])

    def test_bypass_fold_posted_without_a_claim_is_flagged(self):
        """A fold posted without ever claiming it in the program (the
        actual incident shape) is still caught: `current` names a fold
        and the state moved after the question was asked."""
        st = self.states["cc"]
        st.current = "fold 506 — fold of author 893"
        st.updated = FOLD_AT
        violations = find_violations(self.states, [_mining_question()])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["claim_kind"], "fold")

    def test_bypass_state_that_predates_question_is_not_flagged(self):
        st = self.states["cc"]
        st.current = "fold 506 — fold of author 893"
        st.updated = BEFORE_AT
        self.assertEqual(find_violations(self.states, [_mining_question()]), [])

    def test_unorderable_question_is_not_flagged(self):
        """A question with no created_at cannot establish order — no
        flag (and no false positive). Questions filed via `ask` always
        carry created_at."""
        q = Issue(number=1, title="mining-data question", assignee="cc",
                  created_at=None, asked_in="author 893")
        _fold_claim(self.states["cc"])
        self.assertEqual(find_violations(self.states, [q]), [])

    def test_flag_names_oldest_question_owed_when_work_started(self):
        q2 = Issue(number=2, title="later question", assignee="cc",
                   created_at=datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc),
                   asked_in="author 894")
        _fold_claim(self.states["cc"], at=FOLD_AT)
        violations = find_violations(self.states, [_mining_question(), q2])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["question"], 1)

    def test_alarm_row_carries_the_flag(self):
        _fold_claim(self.states["cc"])
        rows = alarm(str(self.root), self.states, [_mining_question()])
        cc_row = next(r for r in rows if r["side"] == "cc")
        self.assertIsNotNone(cc_row["questions_first_flag"])
        self.assertIn("FLAG questions-first", cc_row["questions_first_flag"])
        author_row = next(r for r in rows if r["side"] == "author")
        self.assertIsNone(author_row["questions_first_flag"])


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _ask_mining_question(self):
        code, out, _ = run_cli("ask", "--assignee", "cc",
                               "--title", "mining-data question",
                               "--asked-in", "author 893", root=self.root)
        self.assertEqual(code, 0)
        return json.loads((self.root / "issues.json").read_text(encoding="utf-8"))[0]

    def test_cli_fold_claim_refused_and_queue_shows_question_first(self):
        """End-to-end (2) + (1) through the CLI."""
        self._ask_mining_question()
        code, out, err = run_cli("claim", "--side", "cc", "--item", "fold 506",
                                 "--kind", "fold", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("#1", err)
        self.assertIn("mining-data question", err)
        code, out, _ = run_cli("queue", "--side", "cc", root=self.root)
        self.assertEqual(code, 0)
        self.assertLess(out.index("[answer] answer:1"),
                        out.index("[task]"))
        self.assertIn("HEAD", out)

    def test_cli_flags_fire_on_bypass_and_poll_wakes(self):
        """End-to-end (4) through the CLI: flag fires, poll wakes."""
        q = self._ask_mining_question()
        code, out, _ = run_cli("flags", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("No questions-first flags", out)
        # Simulate the bypass: cc's state holds a fold claim started
        # after the question was asked, posted outside the claim gate.
        q_at = datetime.fromisoformat(q["created_at"].replace("Z", "+00:00"))
        st = SideState.from_text(
            (self.root / "state" / "cc.md").read_text(encoding="utf-8"))
        st.claim = "fold 506"
        st.claim_kind = "fold"
        st.claim_started = datetime.fromtimestamp(
            q_at.timestamp() + 1800, tz=timezone.utc)
        st.current = "fold 506"
        st.started = st.claim_started
        st.updated = st.claim_started
        (self.root / "state" / "cc.md").write_text(st.to_text(), encoding="utf-8")
        code, out, _ = run_cli("flags", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("FLAG questions-first", out)
        self.assertIn("cc", out)
        self.assertIn("#1", out)
        code, out, _ = run_cli("poll", "--side", "cc", root=self.root)
        self.assertEqual(code, 0)
        digest = json.loads(out)
        self.assertTrue(digest["wake"])
        self.assertEqual(len(digest["questions_first_flags"]), 1)
        self.assertEqual(digest["questions_first_flags"][0]["question"], 1)
        # Second poll: the question is now seen, so the flag alone must
        # still wake the watcher.
        code, out, _ = run_cli("poll", "--side", "cc", root=self.root)
        digest = json.loads(out)
        self.assertEqual(digest["new_questions"], [])
        self.assertTrue(digest["wake"])
        self.assertEqual(len(digest["questions_first_flags"]), 1)
        code, out, _ = run_cli("render", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("FLAG questions-first", out)
        self.assertIn("fold 506", out)


if __name__ == "__main__":
    unittest.main()
