import io, os, re
p = os.path.join("src","ai_strategy_finder.py")
s = io.open(p, "r", encoding="utf-8").read()
s = s.replace('print(f\\\"Matched', 'print(f"Matched').replace('\\\")', '")')
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("Fixed bad quoting in summary print.")
