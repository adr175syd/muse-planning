"""Merge-time ledger numbering (Harbor item 3).

Writers propose text; the program assigns numbers serially AT MERGE.
Never trust a handwritten number: the local ledger carries duplicates
(1628 x2, 1632 x2, 1569 x2, 1571 x2, 1770 x2) because two writers read
the same head concurrently. Serialized assignment at merge kills the
class.

A proposal is a list of {"proposed": <handwritten number or None>,
"text": <line>}. The merge returns numbered lines with program-assigned
numbers starting at the ledger head, and advances the head by the count
merged. Collisions in the proposed numbers are reported, not fatal —
each line still gets a distinct serial number.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def load_head(path: Path) -> int:
    if not path.exists():
        return 1
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("next", 1))
    except (ValueError, KeyError, TypeError):
        return 1


def save_head(path: Path, head: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"next": head}) + "\n", encoding="utf-8")


def merge(proposals: list[dict], head: int) -> tuple[list[dict], int, list[str]]:
    """Assign serial numbers starting at `head`. Returns
    (numbered_lines, new_head, warnings). Each numbered line is
    {"number": <assigned>, "proposed": <handwritten or None>,
     "text": <line>}."""
    proposed_numbers = [p.get("proposed") for p in proposals
                        if p.get("proposed") is not None]
    dups = [n for n, c in Counter(proposed_numbers).items() if c > 1]
    warnings: list[str] = []
    if dups:
        warnings.append(
            f"duplicate handwritten numbers ignored (program-assigned "
            f"instead): {sorted(dups)}"
        )
    numbered = []
    n = head
    for p in proposals:
        numbered.append({"number": n, "proposed": p.get("proposed"),
                         "text": p["text"]})
        n += 1
    return numbered, n, warnings


def merge_file(ledger_path: Path, proposals: list[dict]) -> tuple[list[dict], list[str]]:
    """Load the head, merge, advance the head, save. Returns
    (numbered_lines, warnings)."""
    head = load_head(ledger_path)
    numbered, new_head, warnings = merge(proposals, head)
    save_head(ledger_path, new_head)
    return numbered, warnings
