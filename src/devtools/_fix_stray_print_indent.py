# -*- coding: utf-8 -*-
import io, os

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

needle = 'print(f"Matched {matched} of {total_jobs} lines (exact HH:MM only). Skipped {total_jobs - matched}.")'
lines = s.splitlines()

changed = False
for i, ln in enumerate(lines):
    # Match the exact print line when it's at column 0
    if ln.lstrip() == needle and (len(ln) - len(ln.lstrip())) == 0:
        lines[i] = "    " + ln  # indent to function-body level
        changed = True

if changed:
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("Indented the strict-match summary print to 4 spaces.")
else:
    print("No change made (print already indented or not found).")
