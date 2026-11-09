# muse-planning

The planning system for the Muse Bridge — the shared board, queue, and rules
for the three verification sides (author, Harbor, cc) working on the MTZB
gold system. Moved here from Google Drive on John's order (Nov 9, 2026):
Drive's last-writer-wins replace caused 41 board clobbers; git makes a stale
write a conflict instead of a silent overwrite.

## Status

- **Bridge: PAUSED (CONTROL seq 8, Nov 9, 2026).** No new work starts.
  Resume only on John's word.
- **Pause message:** author packet 881 (Nov 9, 2026). Harbor answered in
  Harbor 493, cc in cc 490. Both honored the pause; both gave add/modify
  items (below) and neither has a GitHub username yet.
- **No new build** until the answers landed — they have. The build is the
  program in `program/` (see below).

## Files (seeded from Drive, Nov 9, 2026)

- `STATUS.md` — the live board: what each side is doing, what's left.
- `CONTROL.md` — the mode switch (RUN / PAUSED / WIND-DOWN). A4 semantics
  pinned: one file, mode + control-seq, changed only on John's word.
- `BACKLOG.md` — the ordered backlog of work items.
- `QUEUE_author.md` — the author's live queue (currently empty).
- `STATE.md` — frozen archive of verdicts (do not edit by hand).
- `PLANNING_SYSTEM_BUILD.md` — the adopted 17-item design spec
  (cc 447 §1 + item 17).

## Design (adopted) + additions from Harbor 493 and cc 490

Adopted design: the 17-item spec in `PLANNING_SYSTEM_BUILD.md` — board shows
what's there / who's doing what / what's left, real-time; rotate the load,
not a fixed role; everyone does 1 thing at a time (WIP 1 per side); answer
first (a question is answered before any new task is started); auto-assign;
no single owner.

Harbor's six additions (Harbor 493 §2):
1. Per-side state files; the board is rendered by the program, never written
   by a side.
2. A question becomes a GitHub Issue the same cycle it is asked (label
   `question`, assignee = the side; the packet cites the Issue number).
3. Ledger/note numbers assigned by the program at merge time, never
   handwritten.
4. Liveness, A7, and seen-set checks read git commit times on each side's
   own files, not Drive listings.
5. CONTROL keeps its A4 semantics exactly through the move.
6. The program renders the A13 alarm from the three state files + open
   assigned Issues.

cc's three additions (cc 490 §2):
- (a) F1 for the program's own writes: re-read the live board, assert the
  base md5 immediately before writing, abort on mismatch, touch only its
  own side's line.
- (b) One watcher per side: the GitHub poll folds into each side's existing
  watcher; no second watcher process or cron.
- (c) A7 in the assigner: never assign a watch/read-only item as a side's
  sole item.

## The program (`program/`)

Not yet built. It will: claim/assign work (WIP 1, rotate the load),
enforce answer-first (refuse a new claim while an assigned question is
open), render the board from per-side state files, assign ledger numbers
at merge, and check liveness from git commit times. GitHub Actions rebuild
the board on push; each side's watcher polls GitHub every 20–60s.

## Access

One GitHub account (adr175syd). The same repo-scoped key is shared by the
three sides (John's decision, Nov 9, 2026). Each side holds it in its own
secure storage; it is never committed to this repo and never pasted in chat.
