# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

new_fn = r"""
def build_lines_strict(jobs):
    lines = []
    matched = 0
    total_jobs = len(jobs)
    for parts in jobs:
        if len(parts) == 9:
            mint, hhmm, invest, *_ = parts
        elif len(parts) >= 10:
            mint, hhmm, mc, invest, *_ = parts
        else:
            continue
        try:
            net, pool = detect_network_and_pool(mint)
            candles = fetch_ohlcv_1m_last_48h(net, pool)
            if not candles:
                continue
            hh, mm = [int(x) for x in hhmm.split(":")]
            # Try exact + ±1..±5 minute tolerance with hour wrap
            ts = None
            for delta in (0,1,2,3,4,5,-1,-2,-3,-4,-5):
                hh2, mm2 = hh, mm
                if delta != 0:
                    mm2 = mm + delta
                    while mm2 >= 60:
                        mm2 -= 60
                        hh2 = (hh2 + 1) % 24
                    while mm2 < 0:
                        mm2 += 60
                        hh2 = (hh2 - 1) % 24
                ts = find_entry_minute(candles, hh2 % 24, mm2)
                if ts is not None:
                    break
            if ts is None:
                # Debug hint: show a small sample of available minutes near the requested hour
                try:
                    from datetime import datetime
                    avail = []
                    for c in candles[:120]:  # sample first ~2 hours
                        t = c[0]
                        if t > 10_000_000_000:  # ms → s
                            t = t // 1000
                        dt = datetime.utcfromtimestamp(int(t))
                        if dt.hour == hh:
                            avail.append(f"{dt.hour:02d}:{dt.minute:02d}")
                    avail = sorted(set(avail))[:10]
                    print(f"[strict-match debug] no HH:MM match for {hh:02d}:{mm:02d}; sample minutes at hour {hh:02d}: {avail}")
                except Exception:
                    pass
                continue
            lines.append((mint, hhmm, float(invest), "realistic", candles))
            matched += 1
        except Exception:
            continue
    return lines, matched, total_jobs
"""

# Replace the entire build_lines_strict function body, if it exists
pat = re.compile(r"^\s*def\s+build_lines_strict\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)", re.MULTILINE)
if pat.search(text):
    text = pat.sub(new_fn + "\n", text, count=1)
    print("Replaced existing build_lines_strict() with a clean version.")
else:
    # If not found, insert above main guard or append
    m = re.search(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*$", text, re.MULTILINE)
    if m:
        text = text[:m.start()] + new_fn + "\n" + text[m.start():]
        print("Inserted new build_lines_strict() above __main__ guard.")
    else:
        text = text.rstrip() + "\n\n" + new_fn + "\n"
        print("Appended new build_lines_strict() to end of file.")

io.open(P, "w", encoding="utf-8", newline="\n").write(text)
print("Saved ai_strategy_finder.py (UTF-8, LF).")
