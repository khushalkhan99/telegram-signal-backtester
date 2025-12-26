# -*- coding: utf-8 -*-
import io, os

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")
lines = s.splitlines()

def show(a,b):
    a = max(1,a); b = min(len(lines),b)
    for i in range(a,b+1):
        L = lines[i-1]
        lead = len(L) - len(L.lstrip(" "))
        print(f"{i:04d} | {lead:02d} | {L}")

print("---- LINES 360..400 ----")
show(360,400)
