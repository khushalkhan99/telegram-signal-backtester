import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
s = io.open(P, "r", encoding="utf-8").read()

# Replace the block that builds `lines` with a strict match+summary version
s = re.sub(
    r"""
    lines\s*=\s*\[\]\s*
    for\s+parts\s+in\s+jobs:\s*
        if\s+len\(parts\)\s*==\s*9:\s*
            [\s\S]*?
        elif\s+len\(parts\)\s*>=\s*10:\s*
            [\s\S]*?
        else:\s*
            continue\s*
        try:\s*
            net,\s*pool\s*=\s*detect_network_and_pool\(mint\)\s*
            candles\s*=\s*fetch_ohlcv_1m_last_48h\(net,\s*pool\)\s*
            if\s+not\s*candles:\s*
                continue\s*
            lines\.append\(\(mint,\s*hhmm,\s*float\(invest\),\s*"realistic",\s*candles\)\)\s*
        except\s*Exception:\s*
            continue
    """,
    r'''
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
        # strict exact-minute check before queuing the line
        hh, mm = [int(x) for x in hhmm.split(":")]
        ts_exact = find_entry_minute(candles, hh, mm)
        if ts_exact is None:
            continue
        lines.append((mint, hhmm, float(invest), "realistic", candles))
        matched += 1
    except Exception:
        continue

print(f"Matched {matched} of {total_jobs} lines (exact HH:MM only). Skipped {total_jobs - matched}.")
''',
    s, flags=re.VERBOSE
)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("ai_strategy_finder.py patched: strict entry check + match summary.")
