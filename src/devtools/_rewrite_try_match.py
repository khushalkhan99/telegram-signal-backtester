# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

new_fn = r"""
def try_match(mm, hh, mmn):
    import os as _os
    strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
    deltas = (0,) if strict else (0,1,2,3,4,5,-1,-2,-3,-4,-5)
    for delta in deltas:
        h2, m2 = hh, mmn + delta
        while m2 >= 60:
            m2 -= 60
            h2 = (h2 + 1) % 24
        while m2 < 0:
            m2 += 60
            h2 = (h2 - 1) % 24
        ts = mm.get((h2 % 24, m2))
        if ts is not None:
            return ts
    return None
"""

# Replace any existing try_match definition with our clean one
pat = re.compile(r"^\s*def\s+try_match\s*\(\s*mm\s*,\s*hh\s*,\s*mmn\s*\)\s*:[\s\S]*?^\s*return\s+None\s*$", re.MULTILINE)
if pat.search(s):
    s = pat.sub(new_fn.strip() + "\n", s, count=1)
else:
    # If not found (pattern drift), just insert above build_lines_strict
    m = re.search(r"^\s*def\s+build_lines_strict\s*\(", s, re.MULTILINE)
    if m:
        s = s[:m.start()] + new_fn + "\n" + s[m.start():]
    else:
        s = s.rstrip() + "\n\n" + new_fn + "\n"

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("Rewrote try_match(mm, hh, mmn) with correct indentation.")
