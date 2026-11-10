"""Questions-first flags (F6, packet 870 §12) — reconciled detector.

Ports the author's test_liveness.QuestionsFirstFlagsCase (last-output
leg) plus cc's flag cases (held-claim leg, bypass leg, in-flight
exemption) and Harbor's held-marker exemption, all against the one
reconciled detector in muse_planning.flags (find_violations).

The incident: the data question (author 893 §12, out 21:37 ET Nov 9)
waited ~45 minutes while cc posted three folds (506, 507, 508) with
no answer and no flag — because no such flag existed.
"""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_repo  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.flags import (find_violations, format_flag,  # noqa: E402
                                 last_output_time)
from muse_planning.liveness import alarm  # noqa: E402
from muse_planning.model import Issue, SideState  # noqa: E402

Q_AT = datetime(2026, 11, 10, 2, 34, 38, tzinfo=timezone.utc)  # 893 §12 asked
FOLD_AT = datetime(2026, 11, 10, 2, 45, 54, tzinfo=timezone.utc)  # packet 506
BEFORE_AT = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)  # before it


def _question(number=12, assignee="cc", created_at=None):
    return Issue(number=number, title="What data does the mining need?",
                 assignee=assignee, asked_in="author 893",
                 created_at=created_at if created_at is not None else Q_AT)


def _states():
    return {s: SideState(side=s) for s in ("author", "harbor", "cc")}


class LastOutputLegCase(unittest.TestCase):
    """Author's leg: latest named output time after the question."""

    def setUp(self):
        self.states = _states()
        self.states["cc"].last_output = "packet 506 2026-11-10T02:45:54Z"

    def test_flag_fires_when_output_postdates_open_question(self):
        rows = find_violations(self.states, [_question()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["side"], "cc")
        self.assertEqual(rows[0]["question"], 12)
        self.assertEqual(rows[0]["last_output"], "packet 506 2026-11-10T02:45:54Z")
        self.assertEqual(rows[0]["last_output_time"], "2026-11-10T02:45:54Z")
        self.assertEqual(rows[0]["question_created_at"], "2026-11-10T02:34:38Z")
        text = format_flag(rows[0])
        self.assertIn("FLAG questions-first", text)
        self.assertIn("cc", text)
        self.assertIn("#12", text)
        self.assertIn("packet 506", text)

    def test_no_flag_when_output_predates_question(self):
        self.states["cc"].last_output = "packet 505 2026-11-10T02:31:53Z"
        self.assertEqual(find_violations(self.states, [_question()]), [])

    def test_no_flag_when_no_open_question(self):
        q = _question()
        q.state = "closed"
        self.assertEqual(find_violations(self.states, [q]), [])

    def test_no_flag_when_side_is_answering(self):
        self.states["cc"].claim = "answer:12"
        self.states["cc"].claim_kind = "answer"
        self.assertEqual(find_violations(self.states, [_question()]), [])

    def test_no_flag_without_ask_time(self):
        q = _question()
        q.created_at = None
        self.assertEqual(find_violations(self.states, [q]), [])

    def test_no_flag_without_named_output_time(self):
        self.states["cc"].last_output = "packet 506 (no timestamp recorded)"
        self.assertEqual(find_violations(self.states, [_question()]), [])

    def test_oldest_owed_question_is_the_flagged_one(self):
        newer = Issue(number=13, title="volume question?", assignee="cc",
                      asked_in="author 895",
                      created_at=datetime(2026, 11, 10, 3, 0, 0, tzinfo=timezone.utc))
        rows = find_violations(self.states, [newer, _question()])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["question"], 12)

    def test_last_output_time_takes_latest_named_time(self):
        st = SideState(side="cc",
                       last_output="packet 506 2026-11-10T02:45:54Z",
                       current="fold 853 — started 2026-11-10T02:59:35Z")
        self.assertEqual(last_output_time(st),
                         datetime(2026, 11, 10, 2, 59, 35, tzinfo=timezone.utc))
        self.assertIsNone(last_output_time(SideState(side="cc")))


class HeldClaimLegCase(unittest.TestCase):
    """cc's leg: held non-answer claim started at/after the question."""

    def setUp(self):
        self.states = _states()
        st = self.states["cc"]
        st.claim = "fold 506"
        st.claim_kind = "fold"
        st.claim_started = FOLD_AT
        st.current = "fold 506"
        st.started = FOLD_AT
        st.updated = FOLD_AT

    def test_fold_claim_started_after_question_is_flagged(self):
        rows = find_violations(self.states, [_question()])
        self.assertEqual(len(rows), 1)
        v = rows[0]
        self.assertEqual(v["side"], "cc")
        self.assertEqual(v["question"], 12)
        self.assertEqual(v["claim"], "fold 506")
        self.assertEqual(v["claim_kind"], "fold")
        self.assertIn("held claim", v["evidence"][0])

    def test_in_flight_fold_started_before_question_is_not_flagged(self):
        """Work started BEFORE the question is in-flight: finish it,
        then answer-first blocks the next claim. Not a violation —
        this is the reconciled detector's deliberate change vs
        Harbor's state-based detector (which flagged it)."""
        st = self.states["cc"]
        st.claim_started = BEFORE_AT
        st.started = BEFORE_AT
        st.updated = BEFORE_AT
        # No last_output timestamp after the question either.
        self.assertEqual(find_violations(self.states, [_question()]), [])

    def test_answer_claim_is_not_flagged(self):
        st = self.states["cc"]
        st.claim = "answer:12"
        st.claim_kind = "answer"
        st.claim_started = FOLD_AT
        st.current = "answer:12"
        self.assertEqual(find_violations(self.states, [_question()]), [])

    def test_no_open_question_no_flag(self):
        self.assertEqual(find_violations(self.states, []), [])

    def test_flag_names_oldest_question_owed_when_work_started(self):
        q2 = Issue(number=13, title="later question", assignee="cc",
                   created_at=datetime(2026, 11, 10, 3, 30, tzinfo=timezone.utc),
                   asked_in="author 894")
        rows = find_violations(self.states, [_question(), q2])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["question"], 12)


class BypassLegCase(unittest.TestCase):
    """cc's bypass leg + Harbor's held markers: a fold named in
    `current` with no claim held."""

    def test_bypass_fold_posted_without_a_claim_is_flagged(self):
        states = _states()
        st = states["cc"]
        st.current = "fold 506 — fold of author 893"
        st.started = FOLD_AT
        st.updated = FOLD_AT
        rows = find_violations(states, [_question()])
        self.assertEqual(len(rows), 1)
        # The bypass leg names the work it caught: the fold in `current`.
        self.assertEqual(rows[0]["claim"], "fold 506 — fold of author 893")
        self.assertEqual(rows[0]["claim_kind"], "fold")
        self.assertIn("current item is a fold", rows[0]["evidence"][0])

    def test_bypass_state_that_predates_question_is_not_flagged(self):
        states = _states()
        st = states["cc"]
        st.current = "fold 506 — fold of author 893"
        st.started = BEFORE_AT
        st.updated = BEFORE_AT
        self.assertEqual(find_violations(states, [_question()]), [])

    def test_fold_queued_behind_the_answer_is_not_flagged(self):
        """Harbor's held markers: a fold explicitly queued behind the
        answer is the rule working, not a breach."""
        states = _states()
        st = states["cc"]
        st.current = "fold of author 880 queued behind the answers"
        st.started = FOLD_AT
        st.updated = FOLD_AT
        self.assertEqual(find_violations(states, [_question()]), [])

    def test_unorderable_question_is_not_flagged(self):
        """A question with no created_at cannot establish order — no
        flag (and no false positive)."""
        states = _states()
        st = states["cc"]
        st.claim = "fold 506"
        st.claim_kind = "fold"
        st.claim_started = FOLD_AT
        st.current = "fold 506"
        q = Issue(number=12, title="What data does the mining need?",
                  assignee="cc", created_at=None, asked_in="author 893")
        self.assertEqual(find_violations(states, [q]), [])


class AlarmCarriesFlagCase(unittest.TestCase):
    """The A13 alarm rows carry the flag (both names)."""

    def test_alarm_row_carries_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp)
            states = {s: SideState.from_text(
                (Path(root) / "state" / f"{s}.md").read_text(encoding="utf-8"))
                for s in ("author", "harbor", "cc")}
            st = states["cc"]
            st.claim = "fold 506"
            st.claim_kind = "fold"
            st.claim_started = FOLD_AT
            st.current = "fold 506"
            st.started = FOLD_AT
            st.updated = FOLD_AT
            rows = alarm(str(root), states, [_question()])
            cc_row = next(r for r in rows if r["side"] == "cc")
            self.assertTrue(cc_row["question_violation"])
            self.assertIn("#12", cc_row["question_violation_detail"])
            self.assertIsNotNone(cc_row["questions_first_flag"])
            self.assertIn("FLAG questions-first", cc_row["questions_first_flag"])
            author_row = next(r for r in rows if r["side"] == "author")
            self.assertFalse(author_row["question_violation"])
            self.assertIsNone(author_row["questions_first_flag"])


if __name__ == "__main__":
    unittest.main()
