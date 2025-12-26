# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")
lines = text.splitlines()

# Find the real build_lines_strict() definition
def_idx = None
for i, ln in enumerate(lines):
    if re.match(r"^\s*def\s+build_lines_strict\s*\(", ln):
        def_idx = i
        break

if def_idx is None:
    print("No build_lines_strict() found; nothing removed.")
else:
    # Look for a stray tolerance-start line BEFORE the function: indented 'hh, mm = [int(x) for x in hhmm.split(":")]'
    start_idx = None
    pat = re.compile(r"^\s+hh,\s*mm\s*=\s*\[int\(x\)\s+for\s+x\s+in\s+hhmm\.split\(\"\:\"\)\]\s*$")
    for i in range(def_idx - 1, -1, -1):
        if pat.match(lines[i]):
            start_idx = i
            break

    if start_idx is None:
        print("No orphaned 'hh, mm = ...' block found before build_lines_strict(); nothing removed.")
    else:
        # Remove from the start of that block up to the line just before def build_lines_strict
        removed = lines[start_idx:def_idx]
        del lines[start_idx:def_idx]
        io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        print(f"Removed orphaned block lines {start_idx+1}..{def_idx} (just before build_lines_strict()).")

