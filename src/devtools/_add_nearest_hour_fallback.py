# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

def patch(text):
    # Insert helper to compute circular distance between hours and add fallback path.
    # We’ll replace the block that currently does UTC/KHI try_match logic.
    pat = re.compile(
r"""(
\s*mm_map\s*=\s*minute_map\(candles\)\s*\n
[\s\S]*?
# parse HH:MM from job
\s*try:\s*\n
\s*hh,\s*mm\s*=\s*\[int\(x\)\s*for\s*x\s+in\s*hhmm\.split\(":\"\)\]\s*\n
\s*except\s*Exception:\s*\n
\s*    continue\s*\n
\s*\n
\s*# 1\)\s*Treat HH:MM as UTC\s*\n
\s*found\s*=\s*try_match\(mm_map,\s*hh,\s*mm\)\s*\n
\s*\n
\s*# 2\)\s*If not found,\s*also try assuming HH:MM is Asia/Karachi \(UTC\+5\)\s*→\s*convert to UTC\s*\n
\s*if\s*found\s*is\s*None:\s*\n
\s*    hh_khi_to_utc\s*=\s*\(hh\s*-\s*5\)\s*%\s*24\s*\n
\s*    found\s*=\s*try_match\(mm_map,\s*hh_khi_to_utc,\s*mm\)\s*\n
\s*\n
\s*if\s*found\s*is\s*None:\s*\n
[\s\S]*?
\s*continue
)""", re.MULTILINE)

    repl = r"""
\1
    # --- nearest-hour fallback when neither UTC nor KHI->UTC minute exists ---
    def _hour_distance(a,b):
        d = abs(a-b) % 24
        return min(d, 24-d)

    if found is None:
        hours_present = sorted({h for (h, _m) in mm_map.keys()})
        if hours_present:
            # candidate target hours: UTC HH, KHI->UTC HH
            candidates = [hh, (hh - 5) % 24]
            # choose the available hour closest (circular) to either candidate
            best_hour = min(hours_present, key=lambda H: min(_hour_distance(H, candidates[0]), _hour_distance(H, candidates[1])))
            # try same minute at that nearest hour with ±5 tolerance
            found = try_match(mm_map, best_hour, mm)
            if found is None:
                # pick any minute from that hour (first available) so we can simulate
                mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                if mins_at_hour:
                    fallback_min = mins_at_hour[0]
                    found = mm_map.get((best_hour, fallback_min))
                    print(f"[strict-match fallback] using {best_hour:02d}:{fallback_min:02d} UTC (nearest hour to {hh:02d}:{mm:02d})")
        if found is None:
            # still nothing — skip
            continue
    # -------------------------------------------------------------------------
"""
    new_text, n = pat.subn(repl, text, count=1)
    return new_text, n

s2, n = patch(s)
if n == 0:
    print("Patch site not found (the function might differ). No changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(s2)
    print("Added nearest-hour fallback to build_lines_strict().")
