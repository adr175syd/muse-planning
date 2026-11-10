# muse-planning program

The program that runs the Muse Bridge planning system on GitHub
(repo `adr175syd/muse-planning`). Python 3.12, standard library only,
fully offline — it reads the repo checkout and nothing else. No GitHub
API calls, no network.

## Layout

```
program/
  muse_planning/          the program (one module per rule)
    model.py              data + parsers (state files, issues, backlog, CONTROL)
    store.py              paths, hashing, atomic writes, F1 checked writes
    gate.py               answer-first (F6), WIP 1, A7, A18, CONTROL gates
    queue.py              questions-first queue order (870 §12) + violation flags
    assign.py             assigner: rotate the load, least-recently-assigned
    ledger.py             merge-time serial ledger numbering
    liveness.py           git-commit-time liveness + A13 alarm
    board.py              render the board; migrate STATUS.md -> state files
    cli.py                `python3 -m muse_planning <cmd>`
  tests/                  unittest suite, all offline
  demo.py                 end-to-end demo against the seeded fixtures
  .github/workflows/board.yml   (place at repo root) rebuild board on push
```

## Rules implemented (spec: PLANNING_SYSTEM_BUILD.md + Harbor 493 §2 + cc 490 §2)

1. **Per-side state files + rendered board.** Each side owns exactly one
   file, `state/<side>.md` (its STATUS-line equivalent + heartbeat
   `progress:`). The program renders `board/STATUS.md` from the three
   state files + `issues.json`. No side hand-writes the combined board.
2. **Claim / assign.** WIP 1 per side (a second claim is refused);
   the assigner rotates the load (least-recently-assigned free side
   first; no fixed role, no single owner).
3. **Answer-first gate (F6).** Before any new claim, the side's open
   assigned questions (Issues labelled `question`) are checked. An open
   question blocks every claim except the answer to that question, and
   the refusal names the blocking question(s). `ask` files a question
   as an Issue the same cycle it is asked; the program assigns its
   number serially and the packet cites it.
3b. **Questions-first enforcement (870 §12).** The rule above is now
   structural, not a promise (the mining-data question, author 893
   §12, waited ~45 min while three folds posted, with no flag):
   (1) `queue.py:ordered_queue` puts every owed question at the HEAD
   of the unified queue, ahead of folds and tasks — the board renders
   owed questions and the queue in that order, ahead of task lines;
   (2) the claim gate refuses fold and task claims explicitly, like
   every other non-answer kind — a side cannot claim a fold until the
   owed question is answered; (3) `queue.question_violations` flags a
   fold/task claimed or posted *outside* the gate while a question
   was owed (evidence: the side's own state file — held non-answer
   claim, fold current item, or fold last-output), rendered on the
   board, carried in A13 alarm rows, returned by `poll` (which wakes
   on it), and printed by the `flags` command (exit 1 when firing).
4. **Merge-time ledger numbering.** Writers propose text; `merge`
   assigns serial numbers from `ledger.json` at merge. Handwritten
   numbers are never trusted (duplicates are reported, each line still
   gets a distinct serial).
5. **Git-commit-time liveness.** A side's staleness = age of its last
   commit on its own state file (`git log -1 --format=%cI`). Never
   Drive modifiedTime or folder listings.
6. **CONTROL A4, unchanged.** The program reads `CONTROL.md` (mode +
   control-seq) and refuses claims while PAUSED/WIND-DOWN. It never
   writes CONTROL and never changes mode.
7. **A13 alarm, rendered.** From the three state files + open Issues:
   per side, staleness next to its oldest open assigned question.
8. **F1 on the program's own writes.** Any write to shared board state
   re-reads the live file, asserts the base sha immediately before
   writing, aborts on mismatch, and touches only the writer's own line.
9. **A7 in the assigner.** A watch/read-only item is never a side's
   sole item; the assigner skips watch-only head items.
10. **A18 fence.** Auto-pull is research items only, never verification
    or fold work; frozen spec + kill criteria first.
11. **GitHub Actions.** `.github/workflows/board.yml` re-renders the
    board on push.
12. **Watcher polling contract.** Each side's existing watcher calls
    `poll --side <side>` every 20–60s (no second watcher). It prints
    one JSON digest line; CONTROL PAUSED/WIND-DOWN prints
    `{"wake": false}` and exits 0 (silent).

## Run it

From `program/`:

```sh
python3 -m muse_planning --root .. migrate   # one-time: STATUS.md -> state/*.md
python3 -m muse_planning --root .. render    # board to stdout
python3 -m muse_planning --root .. render --write   # + write board/STATUS.md (F1)
python3 -m muse_planning --root .. poll --side author
python3 -m muse_planning --root .. assign
python3 -m muse_planning --root .. claim --side author --item "time-data rows C1/C2/retry" --kind research
python3 -m muse_planning --root .. claim --side cc --item "fold of author 893" --kind fold   # REFUSED while cc owes a question
python3 -m muse_planning --root .. queue     # owed questions at the head, then folds, then tasks
python3 -m muse_planning --root .. flags     # questions-first violation flags (exit 1 if any)
python3 -m muse_planning --root .. ask --assignee cc --title "TUNE-2 vote?" --asked-in "author 882"
python3 -m muse_planning --root .. answer --number 1
python3 -m muse_planning --root .. alarm
python3 -m muse_planning --root .. merge --proposals proposals.jsonl
```

## Tests + demo

```sh
python3 -m unittest discover -s tests -v   # all offline, no network
python3 demo.py                             # end-to-end demo on seeded fixtures
```

## Ambiguities resolved (simplest reading that satisfies the rule)

- **PAUSED + answer-first.** Under PAUSED the program refuses *every*
  claim, including answer claims. The exempt answer exchange named in
  881 §2.1 is initiated by a human/packet, not auto-granted by the
  program. If the team wants the program to grant answer claims under
  PAUSED, that is a one-line change in `gate.control_allows_claim`.
- **Watch-only pairing.** A7 says a watch is never a side's *sole*
  item. With WIP 1 a claim is always the sole item, so a watch-only
  item is never claimable alone; the assigner skips watch-only head
  items rather than pairing them (pairing would need WIP 2).
- **Issue numbering.** The program assigns Issue numbers serially from
  the local `issues.json` mirror. In deployment the watcher syncs the
  mirror from `gh issue list --label question` before calling `ask`,
  so the next number matches GitHub's.
- **Board `q:` field.** The rendered board line keeps the seeded
  `q: folds 0 / answers 0 / builds 0` shape; the program does not yet
  count queue depths (queue files for harbor/cc are not in the repo
  seed). The counts are placeholders carried in the same format.
- **Ledger head start.** The ledger starts at 1 (no ledger file in the
  seed). The historical ledger (notes 1628+ with duplicates) is not
  imported; the program numbers only what it merges from now on.

## Not yet built (gaps)

- The `gh` sync step (issues.json <-> GitHub Issues) is a watcher-side
  shell step, documented in `cli.py`, not implemented here.
- `board/STATUS.md` is written by `render --write`; the workflow file
  must be placed at the repo root by the parent.
- No `state/harbor.md` / `state/cc.md` seed exists yet beyond what
  `migrate` derives from STATUS.md; the harbor/cc queue files are not
  in the repo seed, so the assigner works from BACKLOG.md only.
- The program does not post packets and never touches STATE.md.
