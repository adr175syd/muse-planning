"""Questions-first enforcement (870 §12): queue head, claim refusal
for folds/tasks, board order, and the violation flag — ported to the
reconciled implementation (author/reconciled-questions-first-
priority). Adaptations vs Harbor PR #2, all deliberate:

  - queue vocabulary unified: owed-question entries are kind
    "answer" (not "question") — the item a side claims is
    "answer:<n>"; the ordering assertions are unchanged.
  - board header is the reconciled "## Owed questions (head of
    queue — answer first): N"; the flags section is the reconciled
    "## Questions-first flags" (always present), not Harbor's
    violations-only section.
  - the detector is timestamp-ordered (reconciled decision): the
    held-claim flag test now sets the claim start AFTER the
    question — Harbor's state-based leg flagged in-flight work,
    which the team's standing rule exempts.
  - `flags` exits 2 while a flag stands (reconciled decision: the
    refusal/blocked code), not Harbor's 1.
  - `poll` wakes on ANY side's flag (reconciled decision; Harbor
    already did this — the test below is unchanged in intent).

The incident these tests pin: author 893 §12 (mining-data question,
out 21:37 ET) waited ~45 minutes while cc posted folds 506/507/508
with no answer and no flag — the rule was a promise, not enforcement.
"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.board import render_board, render_board_with_alarm  # noqa: E402
from muse_planning.gate import answer_question, ask_question, claim  # noqa: E402
from muse_planning.liveness import alarm  # noqa: E402
from muse_planning.model import Issue, SideState, parse_backlog  # noqa: E402
from muse_planning.flags import find_violations as question_violations  # noqa: E402
from muse_planning.queue import (head_for_side, ordered_queue,  # noqa: E402
                                 ordered_queue_all)
from muse_planning.store import Refusal, Repo  # noqa: E402

T0 = datetime(2026, 11, 9, 21, 37, tzinfo=timezone.utc)   # author 893 §12 out
T1 = datetime(2026, 11, 9, 22, 22, tzinfo=timezone.utc)   # ~45 min later


def mining_question():
    return Issue(number=12, title="mining-data question (893 §12)",
                 assignee="cc", created_at=T0, asked_in="author 893")


class QuestionsFirstCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)
        self.repo = Repo(self.root)
        self.states = {s: SideState.from_text(
            (self.root / "state" / f"{s}.md").read_text(encoding="utf-8"))
            for s in ("author", "harbor", "cc")}
        self.items = parse_backlog(
            (self.root / "BACKLOG.md").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    # -- 1. Queue head -------------------------------------------------
    def test_owed_question_is_head_of_queue_ahead_of_folds_and_tasks(self):
        self.states["harbor"].claim = "fold of author 880"
        self.states["harbor"].claim_kind = "fold"
        q = ordered_queue_all(self.states, [mining_question()], self.items)
        self.assertEqual(q[0].kind, "answer")
        self.assertEqual(q[0].ref, "answer:12")
        self.assertEqual(q[0].side, "cc")
        kinds = [e.kind for e in q]
        self.assertLess(kinds.index("answer"), kinds.index("fold"))
        self.assertLess(kinds.index("answer"), kinds.index("task"))

    def test_head_for_owed_side_is_the_question_not_a_task(self):
        head = head_for_side("cc", self.states, [mining_question()], self.items)
        self.assertIsNotNone(head)
        self.assertEqual(head.kind, "answer")
        self.assertEqual(head.ref, "answer:12")

    def test_oldest_question_heads_when_several_owed(self):
        older = Issue(number=9, title="older Q", assignee="harbor",
                      created_at=datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc))
        q = ordered_queue_all(self.states, [mining_question(), older], self.items)
        self.assertEqual([e.ref for e in q[:2]], ["answer:9", "answer:12"])

    # -- 2. Claim refusal ---------------------------------------------
    def test_fold_claim_refused_while_question_owed(self):
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "cc", "fold of author 893", "fold", None,
                  [mining_question()], self.states["cc"])
        self.assertIn("#12", str(cm.exception))
        self.assertIn("mining-data", str(cm.exception))
        self.assertIn("fold", str(cm.exception))

    def test_task_claim_refused_while_question_owed(self):
        with self.assertRaises(Refusal):
            claim(self.repo, "cc", "some task", "task", None,
                  [mining_question()], self.states["cc"])

    def test_work_and_research_claims_still_refused_while_owed(self):
        for kind, item in (("work", None), ("research", self.items[0])):
            with self.assertRaises(Refusal, msg=kind):
                claim(self.repo, "cc", "x", kind, item,
                      [mining_question()], SideState(side="cc"))

    def test_fold_claim_granted_after_question_answered(self):
        issues = []
        q = ask_question(issues, "mining-data question (893 §12)", "",
                         "cc", "author 893")
        with self.assertRaises(Refusal):
            claim(self.repo, "cc", "fold of author 893", "fold", None,
                  issues, self.states["cc"])
        answer_question(issues, q.number)
        st = claim(self.repo, "cc", "fold of author 893", "fold", None,
                   issues, SideState(side="cc"))
        self.assertEqual(st.claim, "fold of author 893")
        self.assertEqual(st.claim_kind, "fold")

    def test_other_sides_fold_claim_unaffected(self):
        st = claim(self.repo, "harbor", "fold of author 893", "fold", None,
                   [mining_question()], self.states["harbor"])
        self.assertEqual(st.claim_kind, "fold")

    # -- 3. Board order ------------------------------------------------
    def test_board_renders_owed_question_ahead_of_task_lines(self):
        self.states["cc"].current = "fold of author 893"
        out = render_board(self.states, [mining_question()])
        qpos = out.index("#12 [cc] mining-data question")
        taskpos = out.index("- cc |")
        self.assertLess(qpos, taskpos)
        self.assertIn("HEAD OF QUEUE", out)
        # Queue section also orders question before the fold entry.
        self.assertLess(out.index("[answer] cc"), out.index("[fold]"))

    def test_board_without_questions_still_renders(self):
        out = render_board(self.states, [])
        self.assertIn("## Owed questions (head of queue — answer first): 0", out)
        for side in ("author", "harbor", "cc"):
            self.assertIn(f"- {side} |", out)

    # -- 4. Violation flag ---------------------------------------------
    def test_flag_fires_when_fold_claimed_while_question_owed(self):
        # Bypass: the claim gate was never used; the state file shows
        # a held fold claim started AFTER the question was owed.
        # (Reconciled detector is timestamp-ordered: the fixture sets
        # the claim start after the question; an in-flight claim
        # started before it is exempt — see test_flags.py.)
        self.states["cc"].claim = "fold 506"
        self.states["cc"].claim_kind = "fold"
        self.states["cc"].claim_started = T1
        self.states["cc"].current = "fold 506"
        self.states["cc"].started = T1
        self.states["cc"].updated = T1
        rows = question_violations(self.states, [mining_question()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["side"], "cc")
        self.assertEqual(rows[0]["questions"], [12])

    def test_flag_fires_when_fold_posted_via_current_and_last_output(self):
        # Bypass: no claim at all — the side simply posted folds
        # (506/507/508 in the incident) and recorded them in its state.
        self.states["cc"].current = "fold 508"
        self.states["cc"].last_output = "fold 508 posted 2026-11-09T22:22:00Z"
        rows = question_violations(self.states, [mining_question()])
        self.assertEqual(len(rows), 1)
        self.assertIn("fold 508", " ".join(rows[0]["evidence"]))

    def test_flag_on_board_and_alarm(self):
        # Orderable fixture (reconciled detector is timestamp-ordered):
        # the held fold claim started after the question was owed.
        self.states["cc"].claim = "fold 506"
        self.states["cc"].claim_kind = "fold"
        self.states["cc"].claim_started = T1
        self.states["cc"].current = "fold 506"
        self.states["cc"].started = T1
        self.states["cc"].updated = T1
        out = render_board_with_alarm(self.repo, self.states,
                                      [mining_question()], now=T1)
        self.assertIn("## Questions-first flags", out)
        self.assertIn("FLAG", out)
        rows = alarm(str(self.root), self.states, [mining_question()], T1)
        cc = next(r for r in rows if r["side"] == "cc")
        self.assertTrue(cc["question_violation"])
        self.assertIn("#12", cc["question_violation_detail"])
        others = [r for r in rows if r["side"] != "cc"]
        self.assertTrue(all(not r["question_violation"] for r in others))

    def test_no_flag_for_answer_claim_or_queued_fold(self):
        self.states["cc"].claim = "answer:12"
        self.states["cc"].claim_kind = "answer"
        self.states["cc"].current = "answer:12"
        self.assertEqual(question_violations(self.states, [mining_question()]), [])
        # A fold explicitly queued behind the answer is the rule working.
        st2 = {s: SideState(side=s) for s in self.states}
        st2["cc"].current = "fold of author 880 queued behind the answers"
        self.assertEqual(question_violations(st2, [mining_question()]), [])

    def test_no_flag_when_no_question_owed(self):
        self.states["cc"].claim = "fold 506"
        self.states["cc"].claim_kind = "fold"
        self.assertEqual(question_violations(self.states, []), [])


class QuestionsFirstCliCase(unittest.TestCase):
    """CLI level: refusal exit code, queue command, flags command, poll."""

    def run_cli(self, *args, root):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from muse_planning.cli import main
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--root", str(root), *args])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def ask_mining(self):
        code, out, _ = self.run_cli(
            "ask", "--assignee", "cc", "--title", "mining-data question (893 §12)",
            "--asked-in", "author 893", root=self.root)
        self.assertEqual(code, 0)
        return out

    def test_cli_fold_claim_refused_then_granted_after_answer(self):
        self.ask_mining()
        code, _, err = self.run_cli("claim", "--side", "cc", "--item",
                                    "fold 506", "--kind", "fold", root=self.root)
        self.assertEqual(code, 2)
        self.assertIn("#1", err)
        code, out, _ = self.run_cli("queue", root=self.root)
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[0].startswith("1. [answer] cc"))
        code, _, _ = self.run_cli("answer", "--number", "1", root=self.root)
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("claim", "--side", "cc", "--item",
                                    "fold 506", "--kind", "fold", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("CLAIMED cc", out)

    def test_cli_flags_and_poll_catch_posted_fold(self):
        import json
        from datetime import datetime, timedelta, timezone
        self.ask_mining()
        # Bypass the gate: write cc's state as if it posted a fold.
        # Orderable fixture (reconciled detector is timestamp-ordered):
        # the fold claim started 30 min after the question was asked.
        q = json.loads((self.root / "issues.json").read_text(encoding="utf-8"))[0]
        q_at = datetime.fromisoformat(q["created_at"].replace("Z", "+00:00"))
        fold_at = q_at + timedelta(minutes=30)
        p = self.root / "state" / "cc.md"
        st = SideState.from_text(p.read_text(encoding="utf-8"))
        st.claim = "fold 506"
        st.claim_kind = "fold"
        st.claim_started = fold_at
        st.current = "fold 506"
        st.started = fold_at
        st.updated = fold_at
        p.write_text(st.to_text(), encoding="utf-8")
        code, out, _ = self.run_cli("flags", root=self.root)
        # Reconciled decision: `flags` exits 2 while a flag stands
        # (the refusal/blocked code), not Harbor's 1.
        self.assertEqual(code, 2)
        self.assertIn("FLAG", out)
        self.assertIn("cc", out)
        code, out, _ = self.run_cli("poll", "--side", "harbor", root=self.root)
        self.assertEqual(code, 0)
        digest = json.loads(out)
        self.assertTrue(digest["wake"])
        self.assertEqual(digest["question_violations"][0]["side"], "cc")


if __name__ == "__main__":
    unittest.main()
