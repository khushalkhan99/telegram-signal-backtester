# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# 1) Make try_match respect strict exact mode via env TB_STRICT_EXACT
s = re.sub(
    r"def\s+try_match\(mm,\s*hh,\s*mmn\):\s*[\s\S]*?return\s+None\s*",
    r'''def try_match(mm, hh, mmn):
    import os as _os
    strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
    deltas = (0,) if strict else (0,1,2,3,4,5,-1,-2,-3,-4,-5)
    for delta in deltas:
        h2, m2 = hh, mmn + delta
        while m2 >= 60:
            m2 -= 60
            h2 = (h2 + 1) % 24
        while m2 < 0:
            m2 += 60
            h2 = (h2 - 1) % 24
        ts = mm.get((h2 % 24, m2))
        if ts is not None:
            return ts
    return None
''',
    s, count=1, flags=re.MULTILINE
)

# 2) Control input timezone via env TB_INPUT_TZ (KHI or UTC).
# Replace the block that tries UTC then KHI->UTC with an env-driven path.
s = re.sub(
    r"# 1\) UTC direct[\s\S]*?# 3\) Nearest-hour fallback",
    r'''# 1) Determine input timezone
            import os as _os
            _tz = _os.environ.get("TB_INPUT_TZ", "UTC").upper()
            if _tz == "KHI":
                # Karachi HH:MM -> convert to UTC
                hh_input_utc = (hh - 5) % 24
            else:
                hh_input_utc = hh

            # 2) Try to match using configured input timezone
            found = try_match(mm_map, hh_input_utc, mmn)

            # 3) Nearest-hour fallback (only if NOT strict)
            _strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
            if (not _strict) and (found is None):
                hours_present = sorted({h for (h, _m) in mm_map.keys()})
                if hours_present:
                    candidates = [hh_input_utc]
                    def hour_dist(a,b):
                        d = abs(a-b) % 24
                        return min(d, 24-d)
                    best_hour = min(hours_present, key=lambda H: min(hour_dist(H, c) for c in candidates))
                    found = try_match(mm_map, best_hour, mmn)
                    if found is None:
                        mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                        if mins_at_hour:
                            fallback_min = mins_at_hour[0]
                            found = mm_map.get((best_hour, fallback_min))
                            print(f"[strict-match fallback] using {best_hour:02d}:{fallback_min:02d} UTC (nearest hour to {hh_input_utc:02d}:{mmn:02d})")
''',
    s, count=1, flags=re.MULTILINE
)

# 3) Ensure we still pass the actually matched HH:MM downstream
if 'hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"' not in s:
    s = re.sub(
        r'(^\s*)lines\.append\(\(mint,\s*hhmm,\s*float\(invest\),\s*"realistic",\s*candles\)\)\s*\n\1matched\s*\+=\s*1',
        r'\1dt_found = datetime.fromtimestamp(int(found), timezone.utc)\n\1hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"\n\1lines.append((mint, hhmm_use, float(invest), "realistic", candles))\n\1matched += 1',
        s, count=1, flags=re.MULTILINE
    )

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("Added TB_STRICT_EXACT + TB_INPUT_TZ switches and ensured matched HH:MM is passed.")
