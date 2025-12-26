# -*- coding: utf-8 -*-
import os, io, re

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

target = 248

print(f"---- LINES {target-18}..{target+18} (indent count + content) ----")
show(target-18, target+18)

# Nearest enclosing def above target
def_idx = None
for j in range(target-2, -1, -1):
    if re.match(r"^\s*def\s+\w+\s*\([^)]*\)\s*:\s*$", lines[j]):
        def_idx = j+1
        break
print("\n---- NEAREST DEF ABOVE", target, "----")
print(def_idx if def_idx else "None found")

# Previous 3 non-empty lines before target
print("\n---- PREVIOUS 3 NON-EMPTY LINES BEFORE", target, "----")
cnt = 0
for k in range(target-2, -1, -1):
    if lines[k].strip():
        print(f"{k+1:04d} | {lines[k]}")
        cnt += 1
        if cnt == 3:
            break

# Heuristic: is target inside an open block?
l = lines[target-1]
lead = len(l) - len(l.lstrip(" "))
open_block = False
for j in range(target-2, -1, -1):
    t = lines[j].rstrip()
    if t.endswith(":"):
        open_block = True
        break
print("\n---- HEURISTIC ----")
print(f"line {target} indent = {lead} spaces")
print("there is an open block above? ", open_block)

# Raw repr for target and next line
print("\n---- RAW REPR L{0}..L{1} ----".format(target, target+1))
for i in (target-1, target):
    if 0 <= i < len(lines):
        print(i+1, repr(lines[i]))
