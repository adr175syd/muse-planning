"""F1: a stale-base write aborts and the file is byte-unchanged."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.store import (StaleBaseError, f1_write,  # noqa: E402
                                 f1_write_own_line, sha256_hex)


class F1Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / "board.md"
        self.p.write_text("- author | current: a\n- harbor | current: h\n- cc | current: c\n",
                          encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _sha(self):
        return sha256_hex(self.p.read_bytes())

    def test_write_with_fresh_base_succeeds(self):
        new = f1_write(self.p, self._sha(), b"- author | current: a2\n")
        self.assertEqual(self.p.read_bytes(), b"- author | current: a2\n")
        self.assertEqual(new, sha256_hex(b"- author | current: a2\n"))

    def test_stale_base_aborts_and_file_unchanged(self):
        """(c) A stale-base write ABORTS (F1)."""
        base = self._sha()
        before = self.p.read_bytes()
        # Someone else moved the file under us.
        self.p.write_text("- author | current: MOVED\n- harbor | current: h\n- cc | current: c\n",
                          encoding="utf-8")
        with self.assertRaises(StaleBaseError):
            f1_write(self.p, base, b"- author | current: a2\n")
        self.assertEqual(self.p.read_bytes(),
                         b"- author | current: MOVED\n- harbor | current: h\n- cc | current: c\n")
        self.assertNotEqual(self.p.read_bytes(), before)  # moved, but not by us

    def test_own_line_write_touches_only_that_line(self):
        base = self._sha()
        f1_write_own_line(self.p, base, "harbor", "- harbor | current: h2")
        lines = self.p.read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[0], "- author | current: a")
        self.assertEqual(lines[1], "- harbor | current: h2")
        self.assertEqual(lines[2], "- cc | current: c")

    def test_own_line_write_aborts_on_stale_base(self):
        base = self._sha()
        self.p.write_text("- author | current: MOVED\n- harbor | current: h\n- cc | current: c\n",
                          encoding="utf-8")
        with self.assertRaises(StaleBaseError):
            f1_write_own_line(self.p, base, "harbor", "- harbor | current: h2")

    def test_own_line_write_refuses_unknown_side(self):
        with self.assertRaises(ValueError):
            f1_write_own_line(self.p, self._sha(), "mallory", "- mallory | x")


if __name__ == "__main__":
    unittest.main()
