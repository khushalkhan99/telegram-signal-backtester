# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8", errors="replace").read()

# Replace the minute-map debug block (between our start/end markers) with a safe try/except version
pat = re.compile(
    r"\n(?P<ind>\s*)# ---- one-time minute-map debug.*?\n(?P=ind)# --------------------------------------------------------------------\n",
    re.DOTALL | re.MULTILINE
)

rep = (
    "\n\\g<ind># ---- one-time minute-map debug (safe) ----\n"
    "\\g<ind>try:\n"
    "\\g<ind>    if '___mm_debug_printed' not in globals():\n"
    "\\g<ind>        globals()['___mm_debug_printed'] = True\n"
    "\\g<ind>        uniq_hours = sorted({h for (h, m) in mm_map.keys()})\n"
    "\\g<ind>        sample_minutes = {}\n"
    "\\g<ind>        for hh0 in uniq_hours[:5]:\n"
    "\\g<ind>            sample_minutes[hh0] = sorted({m for (hh, m) in mm_map.keys() if hh == hh0})[:10]\n"
    "\\g<ind>        print(f\"[candles debug] candles_len={len(candles)} minute_map_size={len(mm_map)} hours_present={uniq_hours[:24]}\")\n"
    "\\g<ind>        print(f\"[candles debug] sample minutes per first hours: {sample_minutes}\")\n"
    "\\g<ind>        raw_ts = []\n"
    "\\g<ind>        for c in candles[:3]:\n"
    "\\g<ind>            v = None\n"
    "\\g<ind>            if isinstance(c, dict):\n"
    "\\g<ind>                for k in ('ts','timestamp','time','t','open_time','openTime'):\n"
    "\\g<ind>                    if k in c:\n"
    "\\g<ind>                        v = c[k]; break\n"
    "\\g<ind>            elif isinstance(c, (list, tuple)) and len(c) > 0:\n"
    "\\g<ind>                v = c[0]\n"
    "\\g<ind>            raw_ts.append(v)\n"
    "\\g<ind>        print(f\"[candles debug] first3_raw_ts_fields={raw_ts}\")\n"
    "\\g<ind>except Exception as _e:\n"
    "\\g<ind>    print(f\"[candles debug] error: {_e}\")\n"
    "\\g<ind># --------------------------------------------\n"
)

new_s, n = pat.subn(rep, s, count=1)
if n == 0:
    print("Did not find the debug block markers; no changes made.")
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(new_s)
    print("Replaced debug block with safe try/except version.")
