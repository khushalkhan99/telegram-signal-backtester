# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# Replace the single append(...) to include the matched minute instead of original hhmm
# We also compute dt from the `found` ts and build hhmm_use = f"{dt.hour:02d}:{dt.minute:02d}"
pat = re.compile(
    r"""
(^\s*)            # indent cap (group 1)
lines\.append\(\(mint,\s*hhmm,\s*float\(invest\),\s*"realistic",\s*candles\)\)\s*\n
\1matched\s*\+=\s*1
""",
    re.MULTILINE | re.VERBOSE
)

rep = (
    "\\1dt_found = datetime.fromtimestamp(int(found), timezone.utc)\n"
    "\\1hhmm_use = f\"{dt_found.hour:02d}:{dt_found.minute:02d}\"\n"
    "\\1lines.append((mint, hhmm_use, float(invest), \"realistic\", candles))\n"
    "\\1matched += 1\n"
)

new_s, n = pat.subn(rep, s, count=1)

if n == 0:
    print("Did not find append(...) pattern to replace. No changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline=\"\n\").write(new_s)
    print("build_lines_strict(): now passes the matched HH:MM to downstream.")
