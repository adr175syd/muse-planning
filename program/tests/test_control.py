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

    def test_real_control_file_parses_and_gates_consistently(self):
        # The repo-root CONTROL.md is a living file: it flips RUN/PAUSED by
        # packet (RUN seq 9 since the Nov 9 resume), so no test may pin a
        # moment-in-time mode. Pin its structure and the gate decision
        # instead; the fixed modes are covered by test_parse_* above.
        seed = Path(__file__).resolve().parent.parent.parent
        c = parse_control((seed / "CONTROL.md").read_text(encoding="utf-8"))
        self.assertIn(c["mode"], ("RUN", "PAUSED", "WIND-DOWN"))
        self.assertTrue(c["control-seq"].isdigit())
        self.assertTrue(c["set_by"])
        ok, _ = control_allows_claim(c)
        self.assertEqual(ok, c["mode"] == "RUN")


if __name__ == "__main__":
    unittest.main()
