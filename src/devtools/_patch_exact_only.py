import io, os, re

PATH = os.path.join("src","ai_strategy_finder.py")
with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Make find_entry_minute strict again (exact HH:MM only, within last 48h)
src = re.sub(
    r"def find_entry_minute\([^\)]*\):[\s\S]*?return [^\n]+\n",
    '''def find_entry_minute(candles, hh: int, mm: int):
    """
    Strict: require an exact HH:MM (UTC) candle within last 48h.
    Return latest matching ts, or None if not present.
    """
    now = int(time.time()); cutoff = now - 48*60*60
    exact = []
    for ts, *_ in candles:
        ts = int(ts)
        if not (cutoff <= ts <= now):
            continue
        t = datetime.fromtimestamp(ts, tz=timezone.utc)
        if t.hour == hh and t.minute == mm:
            exact.append(ts)
    return max(exact) if exact else None
''',
    src, flags=re.DOTALL
)

# Add a small summary print in run() after we build "lines"
src = re.sub(
    r"(if not lines:\s*print\(\"no valid lines to simulate\"\); sys\.exit\(3\))",
    r"\1\n\n    # summary of matches\n    print(f\"Matched {len(lines)} of {len(jobs)} lines (exact HH:MM). Skipped {len(jobs)-len(lines)} with no exact candle.\")",
    src
)

with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("Patched: ai_strategy_finder.py (exact-only + match summary)")
