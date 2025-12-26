# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# Replace the minute-matching logic inside build_lines_strict with a ±5 min sweep and a small debug on failure
pat = re.compile(
    r"""def\s+build_lines_strict\([^\)]*\)\s*:\s*         # function header
[\s\S]*?                                                # until our hh,mm lines
(^\s*)hh,\s*mm\s*=\s*\[int\(x\)\s+for\s+x\s+in\s+hhmm\.split\(":"\)\]\s*\n
\1(?:ts|ts_exact)\s*=\s*find_entry_minute\(\s*candles,\s*hh,\s*mm\s*\)\s*\n
\1if\s+(?:ts|ts_exact)\s+is\s+None:\s*\n
(?:\1\s*.*\n)*?                                         # the prior tolerance block, if any
\1if\s+(?:ts|ts_exact)\s+is\s+None:\s*\n
\1\s*continue
""",
    re.VERBOSE | re.MULTILINE
)

repl = (
r"""\1hh, mm = [int(x) for x in hhmm.split(":")]
\1# Try exact + ±1..±5 minute tolerance with hour wrap
\1ts = None
\1for delta in (0,1,2,3,4,5,-1,-2,-3,-4,-5):
\1    hh2, mm2 = hh, mm
\1    if delta != 0:
\1        if delta > 0:
\1            mm2 = mm + delta
\1            while mm2 >= 60:
\1                mm2 -= 60
\1                hh2 = (hh2 + 1) % 24
\1        else:
\1            mm2 = mm + delta
\1            while mm2 < 0:
\1                mm2 += 60
\1                hh2 = (hh2 - 1) % 24
\1    ts = find_entry_minute(candles, hh2 % 24, mm2)
\1    if ts is not None:
\1        break
\1if ts is None:
\1    # Debug hint: show a small sample of available minutes near the requested hour
\1    try:
\1        from datetime import datetime, timezone
\1        avail = []
\1        for c in candles[:120]:  # check first 2 hours worth as a sample
\1            # assume candle ts in seconds; adjust if your fetch returns ms
\1            t = c[0]
\1            if t > 10_000_000_000:  # looks like ms
\1                t = t // 1000
\1            dt = datetime.utcfromtimestamp(int(t))
\1            if dt.hour == hh:
\1                avail.append(f"{dt.hour:02d}:{dt.minute:02d}")
\1        avail = sorted(set(avail))[:10]
\1        print(f"[strict-match debug] no HH:MM match for {hh:02d}:{mm:02d}; sample minutes at hour {hh:02d}: {avail}")
\1    except Exception:
\1        pass
\1    continue
"""
)

s_new, n = pat.subn(repl, s, count=1)

if n == 0:
    print("Could not locate the strict minute block to widen; no changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(s_new)
    print("Widened minute tolerance to ±5 and added a small debug hint on failures.")
