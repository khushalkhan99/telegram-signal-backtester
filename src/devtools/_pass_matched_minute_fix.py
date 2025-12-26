# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# Replace the append(...) inside build_lines_strict so we pass the actually matched minute
pat = re.compile(
    r'(^\s*)lines\.append\(\(mint,\s*hhmm,\s*float\(invest\),\s*"realistic",\s*candles\)\)\s*\n\1matched\s*\+=\s*1',
    re.MULTILINE
)

rep = (
    r'\1dt_found = datetime.fromtimestamp(int(found), timezone.utc)\n'
    r'\1hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"\n'
    r'\1lines.append((mint, hhmm_use, float(invest), "realistic", candles))\n'
    r'\1matched += 1'
)

new_s, n = pat.subn(rep, s, count=1)

if n == 0:
    print("Did not find the append(...) pattern; no changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(new_s)
    print("build_lines_strict(): now passes the matched HH:MM to downstream.")
