import io, re, sys, os

P = os.path.join("src","ai_strategy_finder.py")
src = io.open(P, "r", encoding="utf-8").read()

# 1) Normalize tabs ? 4 spaces (prevents mixed indentation)
src = src.replace("\t", "    ")

lines = src.splitlines()

# Find the line that contains `if not lines:` (first match)
guard_idx = None
for i, ln in enumerate(lines):
    if re.match(r"\s*if\s+not\s+lines\s*:\s*$", ln):
        guard_idx = i
        break

if guard_idx is None:
    print("Could not find `if not lines:` — aborting")
    sys.exit(1)

# Find the enclosing function (nearest preceding 'def ...:' that is less indented)
def_idx = None
for i in range(guard_idx - 1, -1, -1):
    m = re.match(r"^(\s*)def\s+\w+\s*\([^)]*\)\s*:\s*$", lines[i])
    if m:
        def_idx = i
        def_indent = len(m.group(1))
        break

if def_idx is None:
    print("Could not find enclosing function for the guard — aborting")
    sys.exit(1)

# Desired indent for a simple statement inside the function body
desired_indent = " " * (def_indent + 4)

# Re-indent the guard line to the function-body level
lines[guard_idx] = re.sub(r"^\s*", desired_indent, lines[guard_idx])

# Also: if the next physical line is the guard’s block body (e.g., print(...) or return),
# keep their relative indentation (do nothing) — we only fix the guard itself.

out = "\n".join(lines) + ("\n" if not lines[-1].endswith("\n") else "")
io.open(P, "w", encoding="utf-8", newline="\n").write(out)
print("Re-indented `if not lines:` to function-body level and normalized tabs ? spaces.")
