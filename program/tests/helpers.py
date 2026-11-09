"""Shared fixtures for the offline test suite. Everything is built in a
temp dir; no network, no GitHub, no access to the real repo."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from muse_planning.model import SideState  # noqa: E402

CONTROL_RUN = """# CONTROL — Muse Bridge mode switch (Plan System v2, Amendment A4)

mode: RUN
control-seq: 9
set_by: author
set_at: 2026-11-09 16:30 ET
keeper: author
"""

CONTROL_PAUSED = CONTROL_RUN.replace("mode: RUN", "mode: PAUSED").replace(
    "control-seq: 9", "control-seq: 8")

BACKLOG = """# BACKLOG — test fixture

## Movable research items (head first)

- time-data rows C1/C2/retry | owner: author | working: author | spec: 786 §1 | kill: 334 §1(2) | est: 1 day | status: ready
- Swing Clock odds-reuse design | owner: author | working: author | spec: 814 §2 | kill: PASS RULE | est: 1 day | status: ready
- re-price key stacks at true cost | owner: author | working: author | spec: 820 §1(b) | kill: 334 §1(2) | est: 1 day once spec'd | status: needs spec — NOT movable
- watch the 09:00 bar | owner: author | working: author | spec: 786 §1 | kill: 334 §1(2) | est: 1h | status: ready
"""


def make_repo(root: str | Path, control: str = CONTROL_RUN) -> Path:
    """Build a minimal repo checkout in `root`. Returns the root Path."""
    root = Path(root)
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "CONTROL.md").write_text(control, encoding="utf-8")
    (root / "BACKLOG.md").write_text(BACKLOG, encoding="utf-8")
    (root / "issues.json").write_text("[]\n", encoding="utf-8")
    (root / "ledger.json").write_text(json.dumps({"next": 1}) + "\n", encoding="utf-8")
    for side in ("author", "harbor", "cc"):
        st = SideState(side=side, current="", est="", progress="",
                       last_output=f"packet 1 2026-11-09T00:00:00Z")
        (root / "state" / f"{side}.md").write_text(st.to_text(), encoding="utf-8")
    return root


def set_issue(root: Path, number: int, assignee: str, title: str = "Q?",
              state: str = "open") -> None:
    p = root / "issues.json"
    issues = json.loads(p.read_text(encoding="utf-8"))
    issues.append({"number": number, "title": title, "body": "",
                   "assignee": assignee, "state": state,
                   "created_at": "2026-11-09T10:00:00Z", "closed_at": "",
                   "asked_in": "author 900"})
    p.write_text(json.dumps(issues, indent=2) + "\n", encoding="utf-8")
