# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# Normalize tabs and weird whitespace in leading indentation
s = s.replace("\r\n","\n").replace("\r","\n").replace("\t","    ")
UNI = ["\u00A0","\u1680","\u180E","\u2000","\u2001","\u2002","\u2003","\u2004","\u2005","\u2006","\u2007","\u2008","\u2009","\u200A","\u202F","\u205F","\u3000"]
def fix_lead(line):
    i=0
    while i<len(line) and line[i].isspace(): i+=1
    lead = line[:i]
    for ch in UNI: lead = lead.replace(ch," ")
    return lead + line[i:]
s = "\n".join(fix_lead(ln) for ln in s.split("\n"))

lines = s.split("\n")

# Find the run() block
run_start = None
for i, ln in enumerate(lines):
    if re.match(r"^\s*def\s+run\s*\(\s*\)\s*:\s*$", ln):
        run_start = i
        break

if run_start is None:
    print("Could not find def run(): no changes made.")
    raise SystemExit(0)

# Find the end of run(): next top-level def or if __name__ == "__main__"
run_end = len(lines)
for j in range(run_start+1, len(lines)):
    if re.match(r"^\s*def\s+\w+\s*\(", lines[j]) or re.match(r'^\s*if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:\s*$', lines[j]):
        # only treat as end if it's top-level (no leading spaces)
        if len(lines[j]) - len(lines[j].lstrip(" ")) == 0:
            run_end = j
            break

# Ensure every non-blank, non-comment line inside run() has at least 4-space indent
changed = 0
for k in range(run_start+1, run_end):
    ln = lines[k]
    if ln.strip() == "" or re.match(r"^\s*#.*$", ln):
        continue
    lead = len(ln) - len(ln.lstrip(" "))
    if lead < 4:
        lines[k] = "    " + ln.lstrip()
        changed += 1

# Also fix any lone "except:"/ "elif"/ "else:" lines that may have been dedented to 0 by mistake
for k in range(run_start+1, run_end):
    ln = lines[k]
    if re.match(r"^(except\b|elif\b|else:)", ln.strip()):
        if not ln.startswith("    "):
            lines[k] = "    " + ln
            changed += 1

out = "\n".join(lines) + ("\n" if not lines[-1].endswith("\n") else "")
io.open(P, "w", encoding="utf-8", newline="\n").write(out)
print(f"Re-indented run() block: {changed} line(s) adjusted between {run_start+2}..{run_end}.")
