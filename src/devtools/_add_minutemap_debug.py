# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

pat = re.compile(r"def\s+build_lines_strict\([^\)]*\)\s*:\s*[\s\S]*?def\s+extract_ts", re.MULTILINE)
if not pat.search(s):
    # fallback: we’ll inject our debug after minute_map() creation
    pass

# Add a one-time debug right after we build minute_map(candles)
s_new, n = re.subn(
    r"(\n\s*mm_map\s*=\s*minute_map\(candles\)\s*\n)",
    r"""\1
    # ---- one-time minute-map debug (printed only for the first job) ----
    try:
        if '___mm_debug_printed' not in globals():
            globals()['___mm_debug_printed'] = True
            uniq_hours = sorted({h for (h, m) in mm_map.keys()})
            sample_minutes = {}
            for h in uniq_hours[:5]:
                sample_minutes[h] = sorted({m for (hh, m) in mm_map.keys() if hh == h})[:10]
            print(f"[candles debug] candles_len={len(candles)} minute_map_size={len(mm_map)} hours_present={uniq_hours[:24]}")
            print(f"[candles debug] sample minutes per first hours: {sample_minutes}")
            # also show first 3 raw candle timestamps (best-effort)
            raw_ts = []
            for c in candles[:3]:
                v = None
                if isinstance(c, dict):
                    for k in ('ts','timestamp','time','t','open_time','openTime'):
                        if k in c:
                            v = c[k]; break
                elif isinstance(c, (list, tuple)) and len(c) > 0:
                    v = c[0]
                raw_ts.append(v)
            print(f"[candles debug] first3_raw_ts_fields={raw_ts}")
    except Exception as _e:
        print(f"[candles debug] error: {_e}")
    # --------------------------------------------------------------------
""",
    s,
    count=1
)

if n == 0:
    print("Did not find insertion point; no changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(s_new)
    print("Added one-time candles/minute-map debug print.")
