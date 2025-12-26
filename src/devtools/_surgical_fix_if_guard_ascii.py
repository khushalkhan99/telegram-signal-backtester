# -*- coding: utf-8 -*-
import io, os, re, sys

P = os.path.join("src", "ai_strategy_finder.py")

# Read as bytes, then decode safely
raw = open(P, "rb").read()
for enc in ("utf-8", "utf-16-le", "utf-16-be"):
    try:
        src = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
else:
    print("Could not decode ai_strategy_finder.py; please save it as UTF-8.")
    sys.exit(1)

# Normalize tabs -> 4 spaces (avoid mixed indent)
src = src.replace("\t", "    ")
lines = src.splitlines()

# Find the first 'if not lines:' guard
guard_idx = None
for i, ln in enumerate(lines):
    if re.match(r"^\s*if\s+not\s+lines\s*:\s*$", ln):
        guard_idx = i
        break

if guard_idx is None:
    print("Guard `if not lines:` not found; nothing to fix.")
else:
    # Find enclosing def ...:
    def_idx = None
    def_indent = 0
    for j in range(guard_idx - 1, -1, -1):
        m = re.match(r"^(\s*)def\s+\w+\s*\([^)]*\)\s*:\s*$", lines[j])
        if m:
            def_idx = j
            def_indent = len(m.group(1))
            break

    if def_idx is None:
        print("Enclosing function for the guard not found; skipping re-indent.")
    else:
        desired = " " * (def_indent + 4)
        # Ensure previous line is not a line-continuation
        if guard_idx > 0 and lines[guard_idx - 1].rstrip().endswith("\\"):
            lines.insert(guard_idx, "")
            guard_idx += 1
        # Re-indent the guard line to function-body level
        lines[guard_idx] = re.sub(r"^\s*", desired, lines[guard_idx])

        # If immediate next line is a print/return/sys.exit and not indented enough, indent it one level
        if guard_idx + 1 < len(lines):
            nxt = lines[guard_idx + 1]
            cur_lead = len(re.match(r"^(\s*)", nxt).group(1))
            if cur_lead <= len(desired) and re.search(r"^\s*(print\(|return\b|sys\.exit\()", nxt):
                lines[guard_idx + 1] = " " * (len(desired) + 4) + nxt.lstrip()

        print("Re-indented `if not lines:` inside its function.")

# Write back as UTF-8 LF
out = "\n".join(lines) + ("\n" if not lines or not lines[-1].endswith("\n") else "")
io.open(P, "w", encoding="utf-8", newline="\n").write(out)
print("Normalized tabs->spaces and saved ai_strategy_finder.py as UTF-8.")
