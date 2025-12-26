# -*- coding: utf-8 -*-
import os, io, re, sys

P = os.path.join("src","ai_strategy_finder.py")
data = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t", "    ")
lines = data.splitlines()

def show(start, end):
    n = len(lines)
    start = max(1, start); end = min(n, end)
    for i in range(start, end+1):
        s = lines[i-1]
        lead = len(s) - len(s.lstrip(" "))
        print(f"{i:04d} | {lead:02d} | {s}")

# 1) Dump the neighborhood around 277
print("---- LINES 260..290 (indent count + content) ----")
show(260, 290)

# 2) Show the nearest enclosing 'def ...:' above 277
def_idx = None
for j in range(276, -1, -1):
    if re.match(r"^\s*def\s+\w+\s*\([^)]*\)\s*:\s*$", lines[j]):
        def_idx = j+1
        break
print("\n---- NEAREST DEF ABOVE 277 ----")
print(def_idx if def_idx else "None found")

# 3) Show the previous 3 non-empty lines before 277 (raw)
print("\n---- PREVIOUS 3 NON-EMPTY LINES BEFORE 277 ----")
cnt = 0
for k in range(275, -1, -1):
    if lines[k].strip():
        print(f"{k+1:04d} | {lines[k]}")
        cnt += 1
        if cnt == 3:
            break

# 4) Heuristic: is line 277 at module level but indented?
l277 = lines[276]
lead277 = len(l277) - len(l277.lstrip(" "))
module_level = True
for j in range(276, -1, -1):
    t = lines[j].rstrip()
    if t.endswith(":"):
        module_level = False
        break
print("\n---- HEURISTIC ----")
print(f"line 277 indent = {lead277} spaces")
print("appears module-level (no open block above with ':')? ", module_level)

# 5) Print line 277 and 278 raw repr (to catch stray chars)
print("\n---- RAW REPR L277..L278 ----")
for i in (276, 277):
    if 0 <= i < len(lines):
        print(i+1, repr(lines[i]))
