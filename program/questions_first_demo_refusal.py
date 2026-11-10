"""Demonstration 1 (questions-first fix, req 1 + req 2): the REFUSAL.

Reproduces the cc case as it SHOULD have gone: the data question
(893 §12) is owed to cc, cc tries to claim a fold, the claim is
REFUSED naming the blocking question; the assigner returns the answer
first; only after the question is answered is the fold claim granted.

Run: python3 questions_first_demo_refusal.py
(Reconciled: fold claims use --kind fold, a real claim kind now.)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))
sys.path.insert(0, str(HERE))
from helpers import make_repo  # noqa: E402


def cli(root, *args):
    p = subprocess.run([sys.executable, "-m", "muse_planning", "--root",
                        str(root), *args], cwd=HERE, capture_output=True,
                       text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    tmp = tempfile.mkdtemp(prefix="qf-demo-refusal-")
    root = make_repo(tmp)
    print(f"demo repo: {root} (temp fixture; CONTROL RUN seq 9)")

    section("1. The data question is asked of cc (893 §12, 2026-11-10T02:34:38Z)")
    code, out, err = cli(root, "ask", "--assignee", "cc",
                         "--title", "What data does the mining need?",
                         "--asked-in", "author 893")
    print(f"$ ask --assignee cc --title 'What data does the mining need?' --asked-in 'author 893'")
    print(f"exit {code}: {out or err}")
    assert code == 0 and "#1" in out

    section("2. cc tries to claim a fold while the question is owed -> REFUSED")
    code, out, err = cli(root, "claim", "--side", "cc",
                         "--item", "fold of author 886", "--kind", "fold")
    print("$ claim --side cc --item 'fold of author 886' --kind fold")
    print(f"exit {code}: {err or out}")
    assert code == 2 and "#1" in err and "What data does the mining need?" in err

    section("3. The assigner returns the ANSWER first, ahead of backlog work")
    code, out, err = cli(root, "assign")
    print("$ assign")
    print(f"exit {code}: {out or err}")
    assert code == 0 and "ASSIGN cc <- 'answer:1'" in out

    section("4. cc claims the answer (allowed), then answers the question")
    code, out, err = cli(root, "claim", "--side", "cc", "--item", "answer:1",
                         "--kind", "answer")
    print("$ claim --side cc --item answer:1 --kind answer")
    print(f"exit {code}: {out or err}")
    assert code == 0
    code, out, err = cli(root, "answer", "--number", "1")
    print("$ answer --number 1")
    print(f"exit {code}: {out or err}")
    assert code == 0

    section("5. With the question answered, the fold claim is GRANTED")
    code, out, err = cli(root, "release", "--side", "cc")
    print("$ release --side cc   (release the answer claim)")
    print(f"exit {code}: {out or err}")
    code, out, err = cli(root, "claim", "--side", "cc",
                         "--item", "fold of author 886", "--kind", "fold")
    print("$ claim --side cc --item 'fold of author 886' --kind fold")
    print(f"exit {code}: {out or err}")
    assert code == 0 and "CLAIMED cc" in out

    print("\nDEMONSTRATION 1 COMPLETE: fold refused while the question was "
          "owed; answer assigned first; fold granted only after the answer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
