#!/usr/bin/env python3
"""Regenerate the compact Unicode category table with Python 3.12 (Unicode 15)."""
from pathlib import Path
import unicodedata

if unicodedata.unidata_version != "15.0.0":
    raise SystemExit("Use Python 3.12 with Unicode 15.0.0 to reproduce this table")

groups = {"L": 1, "N": 2, "M": 3}
ranges = []
start = 0
previous = 0
for cp in range(0x110001):
    current = groups.get(unicodedata.category(chr(cp))[0], 0) if cp < 0x110000 else 0
    if current != previous:
        if previous:
            ranges.extend((start, cp - 1, previous))
        start, previous = cp, current

lines = [
    "// SPDX-License-Identifier: GPL-3.0-only",
    "// Generated from Python unicodedata 15.0.0. 1=letter, 2=number, 3=mark.",
    "const ranges = [",
]
for offset in range(0, len(ranges), 18):
    line = "    " + ", ".join(hex(value) for value in ranges[offset:offset + 18])
    lines.append(line + ("," if offset + 18 < len(ranges) else ""))
lines.append("""];

export function category(cp) {
    let low = 0;
    let high = ranges.length / 3 - 1;
    while (low <= high) {
        const middle = (low + high) >> 1;
        const i = middle * 3;
        if (cp < ranges[i]) high = middle - 1;
        else if (cp > ranges[i + 1]) low = middle + 1;
        else return ranges[i + 2];
    }
    return 0;
}
""")

destination = Path(__file__).resolve().parents[1] / "src/unicode.mjs"
destination.write_text("\n".join(lines), encoding="utf-8")
print(f"Generated {len(ranges) // 3} Unicode ranges")
