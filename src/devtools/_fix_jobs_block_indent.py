# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")
lines = s.splitlines()

# Any of these at column 0 must be inside the function body (indent 4)
patterns = [
    r"^lines\s*=\s*\[\]\s*$",
    r"^matched\s*=\s*0\s*$",
    r"^total_jobs\s*=\s*len\(\s*jobs\s*\)\s*$",
    r"^for\s+parts\s+in\s+jobs\s*:\s*$",
    r"^print\(f\"Matched\s+\{matched\}\s+of\s+\{total_jobs\}.*Skipped\s+\{total_jobs\s*-\s*matched\}.*\"\)\s*$",
]

def needs_indent(ln: str) -> bool:
    if ln.strip() == "":
        return False
    if len(ln) - len(ln.lstrip(" ")) != 0:
        return False
    return any(re.match(p, ln) for p in patterns)

changed = False
for i, ln in enumerate(lines):
    if needs_indent(ln):
        lines[i] = "    " + ln
        changed = True

if changed:
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("Indented stray jobs-related lines to 4 spaces.")
else:
    print("No stray jobs-related lines at column 0 were found.")

