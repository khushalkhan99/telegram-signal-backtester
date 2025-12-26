# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# 1) Tolerant minute lookup: replace strict block inside build_lines_strict()
s_new, n1 = re.subn(
    r"""
(\s*)hh,\s*mm\s*=\s*\[int\(x\)\s+for\s+x\s+in\s+hhmm\.split\(":"\)\]\s*\n
\1ts_exact\s*=\s*find_entry_minute\(\s*candles,\s*hh,\s*mm\s*\)\s*\n
\1if\s+ts_exact\s+is\s+None:\s*\n
\1\s*continue
""",
    r"""\1hh, mm = [int(x) for x in hhmm.split(":")]
\1ts = find_entry_minute(candles, hh, mm)
\1if ts is None:
\1    # try ±1 minute tolerance with hour wrap
\1    hh_prev, mm_prev = (hh - 1, 59) if mm == 0 else (hh, mm - 1)
\1    hh_next, mm_next = (hh + 1, 0) if mm == 59 else (hh, mm + 1)
\1    ts = find_entry_minute(candles, hh_prev % 24, mm_prev) or find_entry_minute(candles, hh_next % 24, mm_next)
\1if ts is None:
\1    continue
""",
    s,
    flags=re.VERBOSE
)

# 2) Update the match summary message to reflect tolerance (if present)
s_new = s_new.replace(
    'print(f"Matched {matched} of {total_jobs} lines (exact HH:MM only). Skipped {total_jobs - matched}.")',
    'print(f"Matched {matched} of {total_jobs} lines (±1 min tolerance). Skipped {total_jobs - matched}.")'
)

if n1 == 0:
    print("Could not find the strict minute block to replace. No change made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(s_new)
    print("Applied ±1 minute tolerance in build_lines_strict() and updated summary text.")
