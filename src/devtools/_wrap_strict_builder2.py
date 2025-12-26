# -*- coding: utf-8 -*-
import io, os, re, sys

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

# 1) Ensure helper function exists (idempotent)
builder_fn = r"""
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
            ts_exact = find_entry_minute(candles, hh, mm)
            if ts_exact is None:
                continue
            lines.append((mint, hhmm, float(invest), "realistic", candles))
            matched += 1
        except Exception:
            continue
    return lines, matched, total_jobs
"""

if "def build_lines_strict(" not in text:
    # insert the function right before the main guard if possible, else append
    m = re.search(r"\nif\s+__name__\s*==\s*[\"']__main__[\"']\s*:\s*", text)
    if m:
        text = text[:m.start()] + "\n" + builder_fn + "\n" + text[m.start():]
    else:
        text = text.rstrip() + "\n\n" + builder_fn + "\n"

# 2) Replace the fragile inline strict block with a call to the function (best-effort)
# Find a region that starts with "lines = []" and contains "for parts in jobs:" and ends at the strict summary print.
pattern = re.compile(
    r"(?P<start>^\s*lines\s*=\s*\[\]\s*$)"
    r"[\s\S]{0,2000}?"               # the body
    r"^\s*print\(\s*f\"Matched\s*\{matched\}\s*of\s*\{total_jobs\}\s*lines\s*\(exact HH:MM only\)\.\s*Skipped\s*\{total_jobs\s*-\s*matched\}\.\s*\"\s*\)\s*$",
    re.MULTILINE
)

replacement = (
    "lines, matched, total_jobs = build_lines_strict(jobs)\n"
    "print(f\"Matched {matched} of {total_jobs} lines (exact HH:MM only). Skipped {total_jobs - matched}.\")"
)

new_text, n = pattern.subn(replacement, text, count=1)

if n == 0:
    # If we didn't match (text drift), try a looser fallback: replace any top-level 'lines=[]/matched=0/total_jobs=len(jobs)/for parts in jobs:' cluster
    alt_pat = re.compile(
        r"^\s*lines\s*=\s*\[\]\s*$[\s\S]{0,2000}?^\s*for\s+parts\s+in\s+jobs\s*:\s*$[\s\S]{0,2000}?^\s*print\(\s*f\"Matched",
        re.MULTILINE
    )
    new_text, n = alt_pat.sub(replacement, text, count=1)

if n == 0:
    print("Did not find the inline strict builder to replace. No changes made to that block.")
    # Still write the function if we added it
    io.open(P, "w", encoding="utf-8", newline="\n").write(text)
else:
    io.open(P, "w", encoding="utf-8", newline="\n").write(new_text)
    print("Replaced inline strict-matching block with build_lines_strict() call.")

print("Patch completed.")
