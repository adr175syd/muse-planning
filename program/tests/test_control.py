"""CONTROL parsing + A4 semantics (read-only, never writes mode)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from muse_planning.gate import control_allows_claim  # noqa: E402
from muse_planning.model import parse_control  # noqa: E402


class ControlCase(unittest.TestCase):
    def test_parse_run(self):
        c = parse_control("mode: RUN\ncontrol-seq: 9\nset_by: author\n")
        self.assertEqual(c["mode"], "RUN")
        self.assertEqual(c["control-seq"], "9")
        ok, _ = control_allows_claim(c)
        self.assertTrue(ok)

    def test_parse_paused(self):
        c = parse_control("mode: PAUSED\ncontrol-seq: 8\n")
        ok, why = control_allows_claim(c)
        self.assertFalse(ok)
        self.assertIn("PAUSED", why)
        self.assertIn("John", why)

    def test_parse_wind_down(self):
        c = parse_control("mode: WIND-DOWN\ncontrol-seq: 3\n")
        ok, _ = control_allows_claim(c)
        self.assertFalse(ok)

    def test_missing_mode_raises(self):
        with self.assertRaises(ValueError):
            parse_control("control-seq: 9\n")

    def test_real_seeded_control_is_paused_seq_8(self):
        seed = Path(__file__).resolve().parent.parent.parent
        c = parse_control((seed / "CONTROL.md").read_text(encoding="utf-8"))
        self.assertEqual(c["mode"], "PAUSED")
        self.assertEqual(c["control-seq"], "8")
        self.assertEqual(c["set_by"], "author")


if __name__ == "__main__":
    unittest.main()
