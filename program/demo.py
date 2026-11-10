"""End-to-end demo of muse-planning against the seeded fixtures.

Runs fully offline in a temp dir (a copy of the seeded repo root):
  (a) the board renders from the seeded state files
  (b) a claim is REFUSED while an assigned question is open, and GRANTED
      once it is closed
  (c) a stale-base write ABORTS (F1)
  (d) the assigner rotates across sides and never double-assigns (WIP 1)
  (e) ledger numbers are assigned serially at merge with no duplicates
  (f) liveness reads commit times
  (g) questions-first (870 §12): an owed question heads the queue, a
      fold claim is refused while it is owed, and a fold posted outside
      the gate is flagged on the board / poll

Usage: python3 demo.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from muse_planning.assign import assign  # noqa: E402
from muse_planning.board import (migrate_status_to_state,  # noqa: E402
                                 render_board_with_alarm, write_state)
from muse_planning.gate import (answer_question, ask_question,  # noqa: E402
                                claim, release)
from muse_planning.ledger import merge_file  # noqa: E402
from muse_planning.liveness import alarm  # noqa: E402
from muse_planning.model import SideState, parse_backlog  # noqa: E402
from muse_planning.queue import (ordered_queue,  # noqa: E402
                                 question_violations)
from muse_planning.store import (Refusal, Repo, StaleBaseError,  # noqa: E402
                                 f1_write, sha256_hex)

SEED = Path(__file__).resolve().parent.parent


def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main():
    tmp = tempfile.mkdtemp(prefix="muse-planning-demo-")
    root = Path(tmp)
    for name in ("STATUS.md", "CONTROL.md", "BACKLOG.md", "QUEUE_author.md"):
        shutil.copy(SEED / name, root / name)
    repo = Repo(root)
    print(f"demo repo: {root} (temp copy of the seeded files)")

    # (a) Board renders from the seeded state files.
    section("(a) Board renders from the seeded state files")
    states = migrate_status_to_state((root / "STATUS.md").read_text(encoding="utf-8"))
    for side in ("author", "harbor", "cc"):
        write_state(repo, states[side])
    print(render_board_with_alarm(repo, states, []))

    # Flip CONTROL to RUN for the claim flow (demo fixture only).
    (root / "CONTROL.md").write_text(
        (root / "CONTROL.md").read_text(encoding="utf-8")
        .replace("mode: PAUSED", "mode: RUN").replace("control-seq: 8", "control-seq: 9"),
        encoding="utf-8")
    items = parse_backlog((root / "BACKLOG.md").read_text(encoding="utf-8"))
    head = items[0]
    print(f"head backlog item: {head.title!r} (status {head.status})")

    # (b) Answer-first: refused while open, granted once closed.
    section("(b) Answer-first gate (F6)")
    issues = []
    q = ask_question(issues, "TUNE-2 vote?", "", "cc", "author 900")
    print(f"asked question #{q.number} -> cc: {q.title!r}")
    try:
        claim(repo, "cc", head.title, "research", head, issues, states["cc"])
        print("ERROR: claim was granted while the question was open")
    except Refusal as e:
        print(f"REFUSED (expected): {e}")
    answer_question(issues, q.number)
    print(f"answered question #{q.number}")
    st = claim(repo, "cc", head.title, "research", head, issues, states["cc"])
    print(f"GRANTED (expected): cc claimed {st.claim!r}")
    release(repo, "cc", st)

    # (c) F1: stale-base write aborts.
    section("(c) F1 stale-base write aborts")
    board = root / "board" / "STATUS.md"
    board.parent.mkdir(exist_ok=True)
    board.write_text(render_board_with_alarm(repo, states, []), encoding="utf-8")
    base = sha256_hex(board.read_bytes())
    print(f"board base sha: {base[:12]}...")
    board.write_text(board.read_text(encoding="utf-8").replace(
        "author 881", "author 881 (moved by someone else)"), encoding="utf-8")
    print("someone else moved the board under us; attempting our write...")
    try:
        f1_write(board, base, b"our stale write\n")
        print("ERROR: stale write succeeded")
    except StaleBaseError as e:
        print(f"ABORTED (expected): {e}")
    print(f"board unchanged by us: {'author 881 (moved' in board.read_text(encoding='utf-8')}")

    # (d) Rotation + WIP 1.
    section("(d) Assigner rotates, never double-assigns (WIP 1)")
    for side in states.values():
        side.claim = ""
        side.last_assigned = None
    # The seeded BACKLOG has exactly two ready research items; the third
    # round demonstrates the refusal when nothing assignable is left.
    for round_no in range(1, 3):
        side, item = assign(states, items, [])
        print(f"round {round_no}: ASSIGN {side} <- {item.title!r}")
        states[side].claim = item.title  # side holds it (WIP 1)...
        states[side].claim = ""          # ...then finishes, freeing the side
        items = [i for i in items if i is not item]  # item taken, leaves the pool
    try:
        assign(states, items, [])
        print("ERROR: assign succeeded with nothing ready")
    except Refusal as e:
        print(f"round 3: REFUSED (expected — nothing ready left): {e}")

    # (e) Ledger: serial at merge, no duplicates.
    section("(e) Ledger numbers assigned serially at merge")
    proposals = [{"proposed": 1628, "text": "note A (handwritten 1628)"},
                 {"proposed": 1628, "text": "note B (handwritten 1628 — dup)"},
                 {"proposed": None, "text": "note C (no number)"}]
    numbered, warnings = merge_file(repo.ledger_path(), proposals)
    for w in warnings:
        print(f"WARNING: {w}")
    for ln in numbered:
        print(f"  ledger #{ln['number']}: {ln['text']}")
    print(f"ledger head now: {json.loads(repo.ledger_path().read_text())['next']}")

    # (f) Liveness from git commit times.
    section("(f) Liveness reads git commit times")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "demo@local"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "demo"], cwd=root, check=True)
    env = dict(os.environ, GIT_AUTHOR_DATE="2026-11-09T10:00:00Z",
               GIT_COMMITTER_DATE="2026-11-09T10:00:00Z")
    subprocess.run(["git", "add", "state/author.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "author state"], cwd=root, check=True, env=env)
    now = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)
    for row in alarm(str(root), states, issues, now):
        print(f"  {row['side']}: stale={row['stale']} "
              f"last_commit={row['last_commit']} "
              f"stale_minutes={row['stale_minutes']} "
              f"oldest_open_question={row['oldest_open_question']}")

    # (g) Questions-first: head, refusal, and the bypass flag.
    section("(g) Questions-first (870 §12): head, refusal, flag")
    issues2 = []
    q2 = ask_question(issues2, "mining-data question (893 §12)", "", "cc",
                      "author 893")
    for side in states.values():
        side.claim = ""
        side.current = ""
        side.last_output = ""
    states["harbor"].claim = "fold of author 880"
    states["harbor"].claim_kind = "fold"
    queue = ordered_queue(states, issues2, items)
    print("queue order: " + " -> ".join(
        f"[{e.kind}] {e.title}" for e in queue[:3]))
    print(f"head is the owed question: {queue[0].kind == 'question' and queue[0].ref == f'answer:{q2.number}'}")
    try:
        claim(repo, "cc", "fold 506", "fold", None, issues2, states["cc"])
        print("ERROR: fold claim granted while the question was owed")
    except Refusal as e:
        print(f"FOLD CLAIM REFUSED (expected): {e}")
    # Bypass: cc posts the fold anyway and records it in its state.
    states["cc"].current = "fold 506"
    states["cc"].last_output = "fold 506 posted"
    for v in question_violations(states, issues2):
        print(f"FLAG (expected): {v['detail']} — evidence: " + "; ".join(v["evidence"]))

    print(f"\nDemo complete. Temp repo kept at {root} for inspection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
