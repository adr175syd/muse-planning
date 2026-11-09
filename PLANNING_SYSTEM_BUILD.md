# Planning-system build — author-side design pin

Date: 2026-11-08. Authority: John's orders, main chat ~15:31 ET ("Can we all paused first and make the better planning system first") and ~15:36 ET (the three design pins + the think ask). Bridge is WIND-DOWN (CONTROL.md seq 6); the design is ADOPTED (Harbor 377, John's approval 15:56 ET). This spec is the build pin for the AUTHOR side only. Other sides adopt their own machinery on resume; nothing here binds them. STATE.md stays FROZEN. No live changes. No new idea generation (821 stands). The 369 fold claim stays held until resume.

## §0 — John's pins (verbatim, spelling his)

1. "The the system will see what there, who's doing what, what Else is there to do, real time updates see what's there" — the board shows what's there, who's doing what, what else is left to do, with real-time updates.
2. "Rotate the load, not a fix role" — the LOAD rotates across sides; no side holds a fixed role.
3. "Everyone do 1 thing at a time not queue all into 1 person" — WIP limit 1 per side; new work goes to a free side, never stacked on a busy one.
4. "You guys think of if anything need to change or modify" — the team thinks about what else needs changing. The author-side think-list is §3 below. Harbor/cc add theirs when the bridge resumes.

Honest limit on pin 1: "real time" means the board updates on EVERY state change (claim, progress, finish, block, unblock) plus the watcher reading the board every cycle (5 min). It is not second-by-second. Do not oversell it; the spec says this plainly.

## §1 — Adopted design baseline (what the build implements)

RE-BASED 2026-11-08 (cc 448 §5 flag — the 370/371/836 text is provenance, not the decision text): the text under decision is **cc 447 §1, the 16-item converged design, ADOPTED** — Harbor 375 concurred (items 1, 3–16 as written; item 2 with the deemed-declared pin), cc 448 §1 concurs on the pin and §2 accepts the A5 adoption rule (adoption lands on the author's concur; John informed, may reverse), the author concurs in 842, and John approved it all (main chat 2026-11-08 15:56 ET, verbatim: "Yes all approved, next time you guys decide but need to be reasonable").

The 16 items (447 §1; provenance in brackets):
1. Record form — STATUS.md extended (fixed fields) + BACKLOG.md [author 836 §2(a) + Harbor 370; cc's SHARED_STATUS.md dropped].
2. Backlog trigger — self-declaration by packet + watcher flag (depth ≥ 6 OR oldest unstarted > 24h) as the prompt; a flag unacted for one full watcher cycle after the flagged side's next output counts as the declaration [Harbor 375 §2 pin, concurred by cc 448 §1].
3. Ordering rule — John-ordered first, then spec+kills-ready, then oldest; applied by the team under A5 [cc 445 §3 + Harbor 370].
4. Rotation — split at pre-declared joints, claim in pull order, handoff by packet, third-side verification [Harbor 370 + author 836 §2(b) + cc 445 §4].
5. A18 auto-pull in Harbor's fenced form + blocked-skip [cc 445 §3 + Harbor 370].
6. STATUS-write discipline — F1 base-md5 + detection audit; one fault-injection drill per side [Harbor 371 F1 + cc 444 §3(2) + author 836 §2(c)].
7. Per-side seen-sets [cc 444 §3(1) + author 836 §2(d) + Harbor 371 §2].
8. A7 idle-timer reader [cc 444 §3(4) + author 836 §2(e)].
9. Fetch/run liveness on the heartbeat `progress:` line [author 836 §2(f) + cc 444 §3(3)].
10. Stamped §5 snapshots (F2) [Harbor 371 F2].
11. Ledger numbering (F3, Harbor-internal) [Harbor 371 F3].
12. Handoff ledger-head (F4) [Harbor 371 F4 + cc 444 §3(1)].
13. Timezone pin (F5) [Harbor 371 F5].
14. Answers-never-behind-folds (F6) [Harbor 371 F6 + author 836 §1(11)].
15. Estimates as a standing field (Harbor 369's figures first entries) [Harbor 369 §2(3) + 833 §1 + cc 445 §2].
16. Hard boundaries — verification NEVER moves; a side's own folds/answers never move; another side's file authorship never moves; nothing live or credential-bearing moves [833 §2 + 834 §2 + cc 445 §3 + Harbor 370 + author 836 §2(b)].

Ownership (447 §3(a)): NO single owner — decided 2–1 under A5 (Harbor 371 §4(d) + author 836 §4(d) vs cc 445) and approved by John. One named owner per mechanism; the rules are the team's; design changes by team packet.

Fast lane (447 §3(b)): ADOPTED — author proposed (836 §2(g)); Harbor YES with the pin (any new correction of any kind, verdict-neutral included, and any non-concur item reverts that fold to full form); cc concurs (448 §6); John approved.

Item 17 (ADOPTED 3-0): WIP limit 1 per side (cc 448 §3(3)) — Harbor concurred (378 §2), author concurred (843 §1), adopted on John's approval (449 §1). The author's build already implements it (§2.3, §2.5).

Standing rule (John, 15:56 ET): **the team decides** — bridge and planning-system decisions are not brought to John for step-by-step approval; they must be REASONABLE (inside the evidence and the pre-registered rules, no more time/compute than the item warrants, no live or irreversible exposure, recorded by packet with reasons — Harbor 377 §2). John is informed by digest and may reverse anything, at any time. Unchanged: CONTROL mode (A4 — John's alone), anything live/demo (John's direct word only), the idea-rotation stop, the hard boundary. Evidence items still land on evidence.

Provenance (kept for the record): Harbor 370's seven decisions (fixed-field STATUS line; shared BACKLOG.md; BACKLOGGED threshold; A18 fenced; rotation at completion boundaries + pre-declared split checkpoints; backlog ordering under A5; estimates as a standing field); Harbor 371's F1/F2/F6 (adopted author-side where they bind the author); author 836's proposals (833 status record; 833 offload + 834 rotation; STATUS-write check; per-side seen-sets; A7 idle-timer reader; fetch liveness — author runs no decisive-test fetch).

## §2 — Build scope (author side)

1. **BACKLOG.md** — create the shared file in the bridge root (Drive, packets folder's parent: the "Muse Bridge — MTZB" folder `1OIuiNktGVEmFnUyZ3Cb2hPvcOC3ncshT`). Seed with the 820 §1(a)–(e) pool items: (a) time-of-day breakdowns for H-E4/C1/C2/retry; (b) re-price key stacks at true cost; (c) Swing Clock 814 odds-reuse design work; (d) time-data build (786/334/798); (e) sim gate STOPped (NOT pool-eligible — record it as excluded, with the reason). Each line carries owner / working / spec / kill / est / status. An item with an empty spec or kill field is marked `needs spec` and is NOT movable until its owner fills them. Spec refs must be verified firsthand from the cited packets — do not copy a ref from another packet's report without checking it.
2. **STATUS line format** — switch the author's STATUS line to the 370 §1(a) fixed fields. Keep the author's line informative but one screen-line. The switch happens once, at build time, and is recorded in the build report.
3. **Watcher script** (`~/hooks/scripts/bridge_watch.sh`) — BACK UP the script before editing (timestamped `.bak` in `~/workspace/`). Changes:
   - Per-side seen-sets (cc fix 1): detection must not drop arrivals when several packets land in one tick (the §2 gap, second occurrence Nov 8). Track seen packet ids per side; a tick that finds an unseen packet wakes on it even if a newer packet from the same side also arrived.
   - A18 auto-pull: when the author's queue holds NO unconditional item (folds/answers owed are unconditional while they last; a watch-only head is the A7 condition), the watcher flags the head BACKLOG.md item for pull — the pull itself is claimed in the queue file under A8 before work starts, and shows on the board the same cycle. The watcher only FLAGS; the main session claims.
   - BACKLOGGED flag: depth ≥ 6 or oldest unstarted item > 24h, read off the board; surfaced in the digest.
   - A13 freshness check: a side with no output for > 60 minutes while a packet addressed to it is pending is flagged by name; an item whose `est:` has passed with no new output is flagged as late on the board.
   - WIP=1 enforcement: the watcher never flags a second pull while the author's queue holds a claimed in-progress item.
   - Verify with `bash -n` + isolated-HOME dry runs against EVERY mode value (RUN / PAUSED / WIND-DOWN) + `hooks.dry_run`. Under PAUSED the tick must stay silent. Do NOT enable or run anything that wakes the bridge while PAUSED.
4. **Worker template** (the author fold/answer brief template — update the standing template text, not a single brief):
   - F1 base-md5 enforcement: re-download immediately before every board upload; abort on md5 mismatch, re-base, never force.
   - F2 stamped §5 snapshots: boards-as-of line with all three md5s from the posting minute.
   - F6 queue rule: answer items outrank folds; a fold never jumps an unclaimed answer.
   - Machine-checked queue removal: a verified helper that removes ONLY the claim line + its progress lines and asserts the empty-state md5 (`d1428714…`) — no hand edits to the queue file.
   - Packet writing: muse.write only (never unquoted shell heredoc); /bin/bash grep = 0; dollar figures spot-checked; Drive upload via `--upload` form; parents verified after every create (`1lr-praXjfRXNib4sCl6xjMxtFbU5P-Lk`).
   - The board never originates a fact: a STATUS line may only state what a packet states, with the packet cited.
5. **Queue rule** — one thing at a time per side (John's pin 3): at most one `[x]` claimed item in QUEUE_author.md at any time; new work goes to a free side via the backlog head, never stacked on a busy one. Record the rule in the template and in the watcher.

## §3 — Author-side think-list (what else needs changing)

From Muse's answer to John's "you guys think" ask (~15:36 ET Nov 8):

- (a) STATUS race — F1 (§1) is the fix; the board can't be real-time if writes clobber each other.
- (b) Queue-removal stray-blank-line class (12 occurrences) — machine-checked removal (§2.4).
- (c) Header-time slips — F2 (§1); every board line carries started + est.
- (d) Watcher detection gap — per-side seen-sets (§2.3).
- (e) Answers-never-behind-folds (F6) adopted author-side too — the author's queue had the same head-first shape.
- (f) A7 idle-timer reader — the board needs a freshness check (A13 watcher flag + est: showing lateness on the board itself).
- (g) Idea-ledger inconsistency — CLOSED by Harbor as keeper (379 §4(i)): Idea 71 = 1312, Idea 70 = 1308 (1313/1306 superseded). The build RECORDS it as a closed item on the backlog's excluded list with its citations, so it stays visible.
- (h) Board never originates a fact (§2.4) — the entry-filter "DONE provisional" was STATUS-line-only.
- (i) Sim gate state must show disagreement, not one side's claim (author STOPped vs cc 446 PASS). The board's gate field carries the three-side state or marks it disputed; it never carries one side's claim as the gate state.
- (j) Worker-discipline traps (675 shell-expansion, Drive upload/parents traps) encoded as enforced steps in the worker template (§2.4), not just documented lessons.

## §4 — Out of scope

- Other sides' machinery (Harbor's watcher, cc's watcher, their queue files) — they adopt on resume.
- STATE.md — frozen archive; no line applied, no line edited.
- CONTROL.md — WIND-DOWN seq 6; the mode changes only on John's word (A4). The build does NOT touch CONTROL.md.
- Live/demo trading — untouched.
- The 369 fold claim — held; resumes on John's word.
- No packet is posted by this build. The build reports to the parent (main chat); the parent decides what, if anything, goes to the team by packet on resume.

## §5 — Verification (each piece, before the build is called done)

- BACKLOG.md: re-downloaded from Drive, md5 + parents verified; every seed line's spec/kill ref checked firsthand against the cited packet; every `needs spec` line marked as not movable.
- STATUS line: re-downloaded, author line only changed, Harbor/cc lines byte-identical; the line parses against the 370 §1(a) field order.
- Watcher: `bash -n` clean; isolated-HOME dry runs pass for RUN / PAUSED / WIND-DOWN (PAUSED stays silent); `hooks.dry_run` shows the WAKE decision only where a real new packet exists — under the current PAUSED state it must NOT wake.
- Worker template: the F1 abort drill — an attempted board write from a stale base aborts with the board byte-unchanged; the queue-removal helper passes on a synthetic queue (including the stray-blank-line case).
- Report: one concise report per piece with the evidence (md5s, dry-run outputs, drill results). Anything that fails stays open and is named, not papered over.
