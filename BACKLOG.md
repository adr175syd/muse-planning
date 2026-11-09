# BACKLOG — Muse Bridge shared research backlog

Created 2026-11-08, author-side build per PLANNING_SYSTEM_BUILD.md (John's pause + build order, main chat ~15:31 ET Nov 8; design: 447 §1 + item-2 pin + item 17). Created under PAUSED (CONTROL.md seq 5) — mode is stated in CONTROL.md, not here (a mode claim in this header goes stale by construction). This file is the shared research pool — the movable work. It is NOT a queue: folds, answers, and gated builds never appear here.

Rules (447 §1 as adopted):
- One line per movable research item, in pull order (head first). The pull takes the head item with status `ready`; items marked `needs spec` or `excluded` are skipped, never pulled.
- Owner never moves. Only `working:` changes, on offload, and the change shows on this file the same cycle.
- An item moves only with a frozen spec + kill criteria already filled in. No spec, no move.
- Ordering is a team decision under A5 (majority carries, John informed and may reverse). No side reorders unilaterally. New items enter at the tail unless the team votes otherwise.
- HARD BOUNDARY: independent verification work NEVER moves — folds, replications, votes; anything live or demo; anything carrying credentials; posting a packet on another side's behalf; any edit to STATE.md or CONTROL.md.
- Rotation happens at completion boundaries only; long tasks split at pre-declared checkpoints (per table / per window / per leg), each part a separate claimable item with its own est.
- A18 auto-pull: when a side's own queue empties (or its head item is only a watch), the side claims the head `ready` item in its own queue file under A8 in the same cycle. The pull is never silent — it shows on the board the same cycle.
- WIP limit 1 per side (John's pin 3): at most one claimed item per side at a time; new work goes to a free side, never stacked on a busy one.
- BACKLOGGED (447 §1 item 2, adopted): a side declares itself backlogged by packet; the watcher flags queue depth >= 6 OR oldest unstarted item > 24h as the prompt; a flag that stands unacted for one full watcher cycle after the flagged side's next output counts as the declaration (Harbor 375 §2 pin, concurred by cc 448 §1).

## Movable research items (head first)

- time-data rows C1/C2/retry | owner: author | working: author | spec: 786 §1(4) (order: SFP, held-only/monthly-held, MTZB stacks, Gotobi; Swing Clock excluded) + 334 amendments 1a/1b/2a/2b/3a/3b (adopted 798; 3-0 per 443 §1) | kill: 334 §1(2) as amended (+5pp lift, Wilson guard, del1 guard) + 334 §1(3) sample floors (n>=50 trusted / 25-49 THIN / <25 UNTRUSTED) | est: 1 day | status: ready
  H-E4 rows built (entry/exit/ladder + six extra columns; records md5 4fcfd797… / aa1a8257…); C1/C2/retry rows not built. Seed: 820 §1(a).
- re-price key stacks at true cost | owner: author | working: author | spec: 820 §1(b) | kill: 334 §1(2)/(3) as amended | est: 1 day once spec'd | status: needs spec — NOT movable
  Gold leg spec'd ($11.20/trade = $14/lot one-way; $25 bar stands pending John's word); GBP true-cost basis UNPINNED — owner must pin it before the item moves. Seed: 820 §1(b).
- Swing Clock odds-reuse design (3) level-reach + (2) exit/timing | owner: author | working: author | spec: 814 §2 + 362 §1(e) frozen spec for (1) + 830 §1(e) | kill: PASS RULE (509) + 362 §1(e) kill (a)-(c) | est: 1 day | status: ready
  Design work only; NO build until John decides (362/830). (1) entry-filter design is the frozen spec; Harbor's provisional entry-filter run (DONE provisional, corrections owed) is not this item. Seed: 820 §1(c).
- time-data framework build | owner: author | working: author | spec: 786 §1 + 334 amendments + 798 adoption + 443 §1 (3-0) | kill: 334 §1(2)/(3) as amended | est: — | status: done
  Framework proven end-to-end on H-E4. Remaining table rows are the C1/C2/retry item above; Gotobi rows are a future item (Gotobi last per 367 §3 / 368 §1(f)). Seed: 820 §1(d).

## Excluded — NOT pool-eligible (recorded, not movable)

- sim gate STOPped (leg (ii) M15) | owner: harbor | working: harbor | spec: 772 §2 (author (b) re-scope) + Harbor 317/322 + cc 446 | kill: n/a — gated build, not a table | est: — | status: excluded — NOT pool-eligible
  Gate state DISPUTED, not one side's claim: author STOPped (leg (ii) M15; sim report md5 e2939ec9…); cc 446 claims the gate PASSES 3-0 (cc's claim, author fold pending). No candidate sims run (763 sequencing, 3-0). Seed: 820 §1(e).
- idea-ledger inconsistency | owner: team | working: — | spec: 348 §5 + 349 §0/§5 + 349 §3 L98 + 812 §3 | kill: n/a — ledger reconcile, not a table | est: — | status: excluded — CLOSED by Harbor as keeper (379 §4(i)): Idea 71 = 1312, Idea 70 = 1308 (1313/1306 superseded)
