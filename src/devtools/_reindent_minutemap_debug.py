# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
txt = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")
lines = txt.splitlines()

# Find the minute-map debug block by its start/end comments
start = end = None
for i, ln in enumerate(lines):
    if "# ---- one-time minute-map debug (safe) ----" in ln:
        start = i
        break

if start is not None:
    for j in range(start+1, len(lines)):
        if "# --------------------------------------------" in lines[j]:
            end = j
            break

if start is None or end is None:
    print("Could not find the debug block markers; no changes made.")
else:
    # Desired base indent inside the outer try: 12 spaces
    BASE = " " * 12
    # Reindent every line in [start, end] so the block sits at 12-spaces base
    # Keep each line's relative indentation beneath the marker line.
    # Compute current base indent of the start line:
    cur_base = len(lines[start]) - len(lines[start].lstrip(" "))
    rel = 0  # we will normalize start line to BASE exactly

    # Strip leading spaces and reapply BASE + relative spaces
    for k in range(start, end+1):
        body = lines[k].lstrip(" ")
        # For the first line (the comment), no extra relative indent
        if k == start:
            lines[k] = BASE + body
            continue
        # For subsequent lines, derive their original relative indent
        cur_lead = len(lines[k]) - len(lines[k].lstrip(" "))
        rel_spaces = max(cur_lead - cur_base, 0)
        lines[k] = BASE + (" " * rel_spaces) + body

    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"Reindented debug block to 12 spaces (lines {start+1}..{end+1}).")
