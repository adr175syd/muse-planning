"""Gates: answer-first (F6), WIP 1, A7, A18, CONTROL."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import CONTROL_PAUSED, make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.gate import (answer_question, ask_question, claim,  # noqa: E402
                                record_progress, release)
from muse_planning.model import Issue, SideState, parse_backlog  # noqa: E402
from muse_planning.store import Refusal, Repo  # noqa: E402


class GateCase(unittest.TestCase):
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

    def test_claim_granted_when_clean(self):
        st = claim(self.repo, "author", "time-data rows C1/C2/retry",
                   "research", self.items[0], [], self.states["author"])
        self.assertEqual(st.claim, "time-data rows C1/C2/retry")

    def test_answer_first_refuses_new_claim_and_names_question(self):
        """(b) A claim is REFUSED while an assigned question is open."""
        issues = [Issue(number=1, title="TUNE-2 vote?", assignee="cc")]
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "cc", "time-data rows C1/C2/retry", "research",
                  self.items[0], issues, self.states["cc"])
        self.assertIn("#1", str(cm.exception))
        self.assertIn("TUNE-2 vote?", str(cm.exception))

    def test_answer_first_refuses_fold_claim_while_question_owed(self):
        """Questions-first (req 2): a FOLD claim is refused while a
        question is owed to the side — the cc 506/507/508 case (three
        folds posted while 893 §12 waited). A fold is kind=work; the
        refusal is the same F6 gate and names the blocking question."""
        issues = [Issue(number=12, title="What data does the mining need?",
                        assignee="cc")]
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "cc", "fold of author 886", "work", None,
                  issues, self.states["cc"])
        self.assertIn("#12", str(cm.exception))
        self.assertIn("What data does the mining need?", str(cm.exception))
        # The answer claim for that question is still allowed.
        st = claim(self.repo, "cc", "answer:12", "answer", None,
                   issues, self.states["cc"])
        self.assertEqual(st.claim, "answer:12")

    def test_answer_first_grants_answer_claim_then_claim_after_close(self):
        """(b) ...and GRANTED once the question is closed."""
        issues = []
        q = ask_question(issues, "TUNE-2 vote?", "", "cc", "author 900")
        # Answer claim for that question is allowed even with it open.
        st = claim(self.repo, "cc", f"answer:{q.number}", "answer", None,
                   issues, self.states["cc"])
        self.assertEqual(st.claim, f"answer:{q.number}")
        # A different claim is still refused.
        with self.assertRaises(Refusal):
            claim(self.repo, "cc", "time-data rows C1/C2/retry", "research",
                  self.items[0], issues, self.states["cc"])
        # Close the question: the next claim is granted.
        answer_question(issues, q.number)
        st2 = SideState(side="cc")
        st2 = claim(self.repo, "cc", "time-data rows C1/C2/retry", "research",
                    self.items[0], issues, st2)
        self.assertEqual(st2.claim, "time-data rows C1/C2/retry")

    def test_wip1_refuses_second_claim(self):
        st = claim(self.repo, "author", "time-data rows C1/C2/retry",
                   "research", self.items[0], [], self.states["author"])
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "author", "Swing Clock odds-reuse design",
                  "research", self.items[1], [], st)
        self.assertIn("WIP 1", str(cm.exception))
        # After release, a new claim works.
        st = release(self.repo, "author", st)
        self.assertEqual(st.claim, "")
        st = claim(self.repo, "author", "Swing Clock odds-reuse design",
                   "research", self.items[1], [], st)
        self.assertEqual(st.claim, "Swing Clock odds-reuse design")

    def test_a7_refuses_watch_only_claim(self):
        watch = next(i for i in self.items if i.title.startswith("watch the"))
        self.assertTrue(watch.watch_only)
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "author", watch.title, "research", watch, [],
                  self.states["author"])
        self.assertIn("A7", str(cm.exception))

    def test_a18_refuses_needs_spec_and_verification(self):
        needs = next(i for i in self.items if i.status.startswith("needs spec"))
        with self.assertRaises(Refusal) as cm:
            claim(self.repo, "author", needs.title, "research", needs, [],
                  self.states["author"])
        self.assertIn("A18", str(cm.exception))

    def test_control_paused_refuses_every_claim(self):
        root2 = make_repo(tempfile.mkdtemp(), control=CONTROL_PAUSED)
        repo2 = Repo(root2)
        st = SideState.from_text(
            (root2 / "state" / "author.md").read_text(encoding="utf-8"))
        with self.assertRaises(Refusal) as cm:
            claim(repo2, "author", "time-data rows C1/C2/retry", "research",
                  self.items[0], [], st)
        self.assertIn("PAUSED", str(cm.exception))

    def test_progress_refreshes_heartbeat(self):
        st = record_progress(self.states["author"], "900 posted")
        self.assertEqual(st.progress, "900 posted")
        self.assertIsNotNone(st.updated)


if __name__ == "__main__":
    unittest.main()
