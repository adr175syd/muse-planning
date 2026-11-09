"""Ledger: serial numbering at merge, never a handwritten number."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.ledger import load_head, merge, merge_file  # noqa: E402


class LedgerCase(unittest.TestCase):
    def test_serial_numbers_from_head(self):
        """(e) Ledger numbers are assigned serially at merge."""
        numbered, new_head, warnings = merge(
            [{"proposed": None, "text": "first"},
             {"proposed": None, "text": "second"}], head=100)
        self.assertEqual([n["number"] for n in numbered], [100, 101])
        self.assertEqual(new_head, 102)
        self.assertEqual(warnings, [])

    def test_handwritten_numbers_are_ignored(self):
        numbered, new_head, _ = merge(
            [{"proposed": 1628, "text": "a"}, {"proposed": 1628, "text": "b"}],
            head=50)
        # The 1628 x2 duplicate from the real ledger: both lines still get
        # distinct program-assigned numbers.
        self.assertEqual([n["number"] for n in numbered], [50, 51])
        self.assertEqual(new_head, 52)

    def test_duplicate_handwritten_numbers_warn(self):
        _, _, warnings = merge(
            [{"proposed": 1770, "text": "a"}, {"proposed": 1770, "text": "b"}],
            head=1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("1770", warnings[0])

    def test_head_advances_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ledger.json"
            self.assertEqual(load_head(p), 1)
            numbered, _ = merge_file(p, [{"proposed": 5, "text": "x"}])
            self.assertEqual(numbered[0]["number"], 1)
            self.assertEqual(load_head(p), 2)
            numbered, _ = merge_file(p, [{"proposed": 5, "text": "y"}])
            self.assertEqual(numbered[0]["number"], 2)
            self.assertEqual(load_head(p), 3)

    def test_no_duplicates_across_merges(self):
        """(e) No duplicates, ever, across successive merges."""
        seen = set()
        head = 1
        for batch in range(5):
            numbered, head, _ = merge(
                [{"proposed": 1628, "text": f"batch {batch} line {i}"}
                 for i in range(3)], head)
            for n in numbered:
                self.assertNotIn(n["number"], seen)
                seen.add(n["number"])
        self.assertEqual(len(seen), 15)


if __name__ == "__main__":
    unittest.main()
