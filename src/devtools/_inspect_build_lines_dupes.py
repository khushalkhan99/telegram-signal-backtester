# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
data = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")
lines = data.splitlines()

def show(start, end):
    n = len(lines)
    start = max(1, start); end = min(n, end)
    for i in range(start, end+1):
        s = lines[i-1]
        lead = len(s) - len(s.lstrip(" "))
        print(f"{i:04d} | {lead:02d} | {s}")

print("---- OCCURRENCES OF def build_lines_strict ----")
occ = []
for i, ln in enumerate(lines, 1):
    if re.match(r"^\s*def\s+build_lines_strict\s*\(", ln):
        occ.append(i)
        print(f"def at line {i}")

if not occ:
    print("No build_lines_strict() found")

print("\n---- SNIPPETS AFTER EACH def (next 8 lines) ----")
for i in occ:
    show(i, i+8)
    print("-"*60)

target = 297
print(f"\n---- LINES {target-12}..{target+12} (indent counts) ----")
show(target-12, target+12)
