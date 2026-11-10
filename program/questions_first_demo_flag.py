"""Demonstration 2 (questions-first fix, req 4): the FLAG.

Reproduces the cc case as it HAPPENED, and shows the flag that did
not exist then: the data question (893 §12) was asked of cc at
2026-11-10T02:34:38Z; cc posted three folds while it was owed —
506 at 02:45:54Z, 507 at 02:59:35Z, 508 at 03:14:40Z — with no flag
firing, because no such flag existed. With the fix, `flags`, the
board, and the watcher digest all catch it.

Run: python3 questions_first_demo_flag.py
Output is also saved to questions_first_fix_demo_flag.txt.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(HERE))
from helpers import make_repo, set_issue  # noqa: E402


def cli(root, *args):
    p = subprocess.run([sys.executable, "-m", "muse_planning", "--root",
                        str(root), *args], cwd=HERE, capture_output=True,
                       text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    tmp = tempfile.mkdtemp(prefix="qf-demo-flag-")
    root = Path(make_repo(tmp))
    print(f"demo repo: {root} (temp fixture; CONTROL RUN seq 9)")

    section("1. The setup: question #12 owed to cc, asked 2026-11-10T02:34:38Z")
    # set_issue writes created_at 2026-11-09T10:00:00Z; fix it to the
    # real 893 §12 ask time, and give the question its real title.
    set_issue(root, 12, "cc", "What data does the mining need?")
    issues = json.loads((root / "issues.json").read_text(encoding="utf-8"))
    issues[0]["created_at"] = "2026-11-10T02:34:38Z"
    issues[0]["asked_in"] = "author 893"
    (root / "issues.json").write_text(json.dumps(issues, indent=2) + "\n",
                                      encoding="utf-8")
    print("issues.json: #12 [cc] 'What data does the mining need?' "
          "(asked in author 893, created 2026-11-10T02:34:38Z, open)")

    section("2. cc posts folds while #12 is owed (506 02:45:54Z, 507 02:59:35Z, 508 03:14:40Z)")
    cc_state = (root / "state" / "cc.md").read_text(encoding="utf-8")
    cc_state = cc_state.replace("packet 1 2026-11-09T00:00:00Z",
                                "packet 508 2026-11-10T03:14:40Z")
    (root / "state" / "cc.md").write_text(cc_state, encoding="utf-8")
    print("state/cc.md last-output: packet 508 2026-11-10T03:14:40Z "
          "(~40 minutes after the question was asked)")

    section("3. `flags`: the fold-while-owed flag FIRES")
    code, out, err = cli(root, "flags")
    print("$ flags")
    print(f"exit {code}:")
    print(out or err)
    rows = json.loads(out)
    # `flags` exits 2 while a flag stands (reconciled decision: the
    # refusal/blocked code, not 0 and not Harbor's 1).
    assert code == 2 and len(rows) == 1 and rows[0]["side"] == "cc"
    assert rows[0]["question"] == 12
    assert rows[0]["last_output_time"] == "2026-11-10T03:14:40Z"

    section("4. `render`: the board carries the flag (and the owed question on top)")
    code, out, err = cli(root, "render")
    print("$ render")
    print(f"exit {code}:")
    print(out)
    assert code == 0
    assert "FLAG questions-first: cc" in out and "#12" in out
    assert out.index("## Owed questions") < out.index("- author |")

    section("5. `poll`: the watcher digest WAKES on the flag (and on nothing else)")
    # Commit the state files at "now" so no side is A13-stale: the wake
    # below must come from the flag alone, not from staleness.
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    env = dict(os.environ, GIT_AUTHOR_DATE=now, GIT_COMMITTER_DATE=now)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "demo@local"],
                   cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "demo"], cwd=root, check=True)
    subprocess.run(["git", "add", "state"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "state"], cwd=root, check=True,
                   env=env)
    code, out, err = cli(root, "poll", "--side", "author")
    print("$ poll --side author")
    print(f"exit {code}:")
    print(out or err)
    digest = json.loads(out)
    assert code == 0
    assert digest["stale_sides"] == []
    assert digest["wake"] is True
    assert len(digest["questions_first_flags"]) == 1
    assert digest["questions_first_flags"][0]["side"] == "cc"

    print("\nDEMONSTRATION 2 COMPLETE: the flag fires on `flags`, on the "
          "board, and in the watcher digest — the cc 506/507/508 case can "
          "no longer pass silently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
