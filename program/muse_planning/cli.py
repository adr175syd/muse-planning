"""CLI for muse-planning.

Usage (repo root = the checkout of adr175syd/muse-planning, default `.`):

  python3 -m muse_planning render [--root DIR]
      Render the board from state/*.md + issues.json to stdout
      (use --write to also write board/STATUS.md via F1).
  python3 -m muse_planning migrate [--root DIR]
      One-time: parse the seeded STATUS.md into state/<side>.md.
  python3 -m muse_planning claim --side author --item <id> --kind <answer|fold|work|research>
      Claim one item (answer-first, WIP 1, A7, A18, CONTROL gates apply).
      A fold claim is refused while an assigned question is owed (F6).
  python3 -m muse_planning queue --side cc
      The side's work queue, questions first: owed answers at the head,
      then its current claim, then the movable backlog pool.
  python3 -m muse_planning flags
      Questions-first flags: sides that started a fold/task while a
      question was owed. Exits 2 when any flag stands, 0 when none.
  python3 -m muse_planning release --side author
  python3 -m muse_planning progress --side author --note "..."
  python3 -m muse_planning ask --assignee cc --title "..." --asked-in "author 882"
      File a question as an Issue (number assigned serially here).
  python3 -m muse_planning answer --number N
      Close question #N.
  python3 -m muse_planning assign
      Assign the head ready backlog item to the least-recently-assigned
      free side (rotation). Prints the assignment; the side still claims
      it itself (claim re-checks every gate).
  python3 -m muse_planning merge --proposals FILE
      Assign ledger numbers serially at merge (FILE is JSON lines of
      {"proposed": <n|null>, "text": "..."}). Prints numbered lines.
  python3 -m muse_planning alarm
      A13 alarm rows (commit-time liveness + oldest open question).
  python3 -m muse_planning poll --side author
      Watcher contract: one digest line (JSON). CONTROL PAUSED/WIND-DOWN
      prints {"mode": ..., "wake": false} and exits 0 — silent.

All commands are offline: they read the repo checkout only. No GitHub
API calls, no network. The watcher syncs issues.json from GitHub
(`gh issue list --label question`) before calling poll.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .assign import assign as do_assign
from .board import migrate_status_to_state, render_board_with_alarm, write_state
from .flags import find_violations, format_flag
from .gate import (answer_question, ask_question, claim as do_claim,
                   load_control, record_progress, release as do_release)
from .ledger import merge_file
from .liveness import alarm as do_alarm
from .model import (SIDES, SideState, dump_issues, load_issues,
                    parse_backlog)
from .queue import ordered_queue
from .store import Repo, Refusal, atomic_write, f1_write, sha256_hex


def _repo(args) -> Repo:
    return Repo(args.root)


def _load_states(repo: Repo) -> dict[str, SideState]:
    states = {}
    for side in SIDES:
        p = repo.state_path(side)
        if not p.exists():
            raise Refusal(f"state file missing: {p} (run `migrate` first)")
        states[side] = SideState.from_text(p.read_text(encoding="utf-8"))
    return states


def _load_issues(repo: Repo):
    p = repo.issues_path()
    return load_issues(p.read_text(encoding="utf-8")) if p.exists() else []


def _save_issues(repo: Repo, issues) -> None:
    atomic_write(repo.issues_path(), dump_issues(issues).encode("utf-8"))


def cmd_render(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    out = render_board_with_alarm(repo, states, issues)
    if args.write:
        board = repo.board_path()
        if board.exists():
            base = sha256_hex(board.read_bytes())
            f1_write(board, base, out.encode("utf-8"))
        else:
            atomic_write(board, out.encode("utf-8"))
    sys.stdout.write(out)
    return 0


def cmd_migrate(args) -> int:
    repo = _repo(args)
    status = repo.path("STATUS.md").read_text(encoding="utf-8")
    states = migrate_status_to_state(status)
    for side in SIDES:
        write_state(repo, states[side])
        print(f"state/{side}.md <- STATUS line ({states[side].current[:60]})")
    return 0


def cmd_claim(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    item = None
    if args.kind == "research":
        items = parse_backlog(repo.backlog_path().read_text(encoding="utf-8"))
        item = next((i for i in items if i.title == args.item), None)
        if item is None:
            raise Refusal(f"no backlog item titled {args.item!r}")
    state = do_claim(repo, args.side, args.item, args.kind, item, issues,
                     states[args.side])
    write_state(repo, state)
    print(f"CLAIMED {args.side} <- {args.item} ({args.kind})")
    return 0


def cmd_queue(args) -> int:
    """A side's work queue, questions first (queue.py). The head is the
    next thing the side works: its oldest owed question, else its current
    claim, else the head movable backlog item."""
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    items = parse_backlog(repo.backlog_path().read_text(encoding="utf-8"))
    queue = ordered_queue(args.side, issues, states[args.side], items)
    if not queue:
        print(f"QUEUE {args.side}: empty")
        return 0
    print(f"QUEUE {args.side} (head first — owed questions ahead of folds/tasks):")
    for n, entry in enumerate(queue, 1):
        mark = " <- HEAD" if n == 1 else ""  # head_of_queue is queue[0]
        print(f"  {n}. [{entry.kind}] {entry.ref} — {entry.title}"
              + (f" ({entry.detail})" if entry.detail else "") + mark)
    return 0


def cmd_flags(args) -> int:
    """Questions-first flags (flags.py). A side that started a fold/task
    while a question was owed is flagged by name. Exits 2 while any flag
    stands — the same way a refused claim exits 2 — so a watcher or CI
    step can fail on it."""
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    violations = find_violations(states, issues)
    if not violations:
        print("No questions-first flags.")
        return 0
    for v in violations:
        print(format_flag(v))
    return 2


def cmd_release(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    state = do_release(repo, args.side, states[args.side])
    write_state(repo, state)
    print(f"RELEASED {args.side}")
    return 0


def cmd_progress(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    state = record_progress(states[args.side], args.note)
    write_state(repo, state)
    print(f"PROGRESS {args.side}: {args.note}")
    return 0


def cmd_ask(args) -> int:
    repo = _repo(args)
    issues = _load_issues(repo)
    issue = ask_question(issues, args.title, args.body or "", args.assignee,
                         args.asked_in)
    _save_issues(repo, issues)
    print(f"QUESTION #{issue.number} -> {args.assignee}: {args.title!r} "
          f"(asked in {args.asked_in})")
    return 0


def cmd_answer(args) -> int:
    repo = _repo(args)
    issues = _load_issues(repo)
    issue = answer_question(issues, args.number)
    _save_issues(repo, issues)
    print(f"ANSWERED #{issue.number}: {issue.title!r}")
    return 0


def cmd_assign(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    items = parse_backlog(repo.backlog_path().read_text(encoding="utf-8"))
    side, item = do_assign(states, items, issues)
    write_state(repo, states[side])
    print(f"ASSIGN {side} <- {item.title!r} (claim it with `claim`)")
    return 0


def cmd_merge(args) -> int:
    repo = _repo(args)
    proposals = [json.loads(ln) for ln in
                 Path(args.proposals).read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
    numbered, warnings = merge_file(repo.ledger_path(), proposals)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    for ln in numbered:
        print(f"{ln['number']}: {ln['text']}  (proposed: {ln['proposed']})")
    return 0


def cmd_alarm(args) -> int:
    repo = _repo(args)
    states = _load_states(repo)
    issues = _load_issues(repo)
    rows = do_alarm(str(repo.root), states, issues)
    print(json.dumps(rows, indent=2))
    return 0


def cmd_poll(args) -> int:
    """Watcher contract. One JSON digest line. The existing watcher calls
    this every 20-60s; it does NOT create a second watcher. CONTROL
    PAUSED/WIND-DOWN -> {"wake": false} (silent, exit 0). A questions-first
    flag naming this side wakes it, like a new question or a stale side."""
    repo = _repo(args)
    control = load_control(repo)
    mode = control.get("mode", "")
    if mode != "RUN":
        print(json.dumps({"mode": mode, "seq": control.get("control-seq"),
                          "wake": False, "reason": "CONTROL not RUN (A4)"}))
        return 0
    states = _load_states(repo)
    issues = _load_issues(repo)
    mine = [i for i in issues if i.assignee == args.side and i.state == "open"]
    seen_path = repo.seen_path(args.side)
    seen = set()
    if seen_path.exists():
        try:
            seen = set(json.loads(seen_path.read_text(encoding="utf-8")))
        except ValueError:
            seen = set()
    new_q = [i.number for i in mine if i.number not in seen]
    rows = do_alarm(str(repo.root), states, issues)
    stale = [r["side"] for r in rows if r["stale"]]
    own_flags = [v for v in find_violations(states, issues)
                 if v["side"] == args.side]
    wake = bool(new_q) or bool(stale) or bool(own_flags)
    seen |= {i.number for i in mine}
    atomic_write(seen_path, json.dumps(sorted(seen)).encode("utf-8"))
    print(json.dumps({
        "mode": mode, "seq": control.get("control-seq"), "wake": wake,
        "new_questions": new_q,
        "stale_sides": stale,
        "questions_first_flags": own_flags,
        "open_questions": {s: len([i for i in issues if i.assignee == s and i.state == "open"]) for s in SIDES},
    }))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="muse-planning",
                                description="Planning system for the Muse Bridge (GitHub).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--root", default=".", help="repo checkout root (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render the board from state files + issues")
    r.add_argument("--write", action="store_true", help="also write board/STATUS.md via F1")
    r.set_defaults(fn=cmd_render)
    m = sub.add_parser("migrate", help="one-time: STATUS.md -> state/<side>.md")
    m.set_defaults(fn=cmd_migrate)
    c = sub.add_parser("claim", help="claim one item (gates apply)")
    c.add_argument("--side", required=True, choices=list(SIDES))
    c.add_argument("--item", required=True)
    c.add_argument("--kind", required=True, choices=["answer", "fold", "work", "research"])
    c.set_defaults(fn=cmd_claim)
    q = sub.add_parser("queue", help="a side's work queue, questions first")
    q.add_argument("--side", required=True, choices=list(SIDES))
    q.set_defaults(fn=cmd_queue)
    fl = sub.add_parser("flags", help="questions-first flags (exit 2 if any stand)")
    fl.set_defaults(fn=cmd_flags)
    r2 = sub.add_parser("release", help="release a held claim")
    r2.add_argument("--side", required=True, choices=list(SIDES))
    r2.set_defaults(fn=cmd_release)
    pr = sub.add_parser("progress", help="heartbeat progress (real output only)")
    pr.add_argument("--side", required=True, choices=list(SIDES))
    pr.add_argument("--note", required=True)
    pr.set_defaults(fn=cmd_progress)
    a = sub.add_parser("ask", help="file a question as an Issue")
    a.add_argument("--assignee", required=True, choices=list(SIDES))
    a.add_argument("--title", required=True)
    a.add_argument("--body", default="")
    a.add_argument("--asked-in", required=True, help="packet that asks it")
    a.set_defaults(fn=cmd_ask)
    an = sub.add_parser("answer", help="close a question")
    an.add_argument("--number", required=True, type=int)
    an.set_defaults(fn=cmd_answer)
    asg = sub.add_parser("assign", help="assign head ready item to a free side")
    asg.set_defaults(fn=cmd_assign)
    mg = sub.add_parser("merge", help="assign ledger numbers at merge")
    mg.add_argument("--proposals", required=True, help="JSON-lines file")
    mg.set_defaults(fn=cmd_merge)
    al = sub.add_parser("alarm", help="A13 alarm rows")
    al.set_defaults(fn=cmd_alarm)
    po = sub.add_parser("poll", help="watcher digest (one JSON line)")
    po.add_argument("--side", required=True, choices=list(SIDES))
    po.set_defaults(fn=cmd_poll)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
