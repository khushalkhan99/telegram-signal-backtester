# src/report_from_csv.py (use coin_symbol if present; offline)
import os, csv
from collections import Counter

CSV_PATH = os.path.join("out", "batch_results.csv")

def human_mc(x: str) -> str:
    if not x: return ""
    try: n = float(x)
    except: return ""
    for unit, div in (("t",1e12),("b",1e9),("m",1e6),("k",1e3)):
        if abs(n) >= div: return f"{n/div:.2f}{unit}"
    return f"{n:.0f}"

def fmt_dur(mins: str) -> str:
    if not mins or not str(mins).isdigit(): return ""
    m = int(mins); h, mm = divmod(m, 60)
    return f"{h}h {mm}m" if h else f"{mm}m"

def short_symbol(mint: str) -> str:
    return (mint[:4] + "…") if mint else "—"

def main():
    if not os.path.isfile(CSV_PATH):
        print("No CSV found. Run the batch first so out/batch_results.csv exists.")
        return

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    headers = ["Coin","ATH x","Entry MC","Exit MC","PnL (coin)","Hold","Exit reason"]
    table = []
    total_pnl = 0.0; holds=[]; reasons=[]; ath_vals=[]
    for r in rows:
        coin = (r.get("coin_symbol") or "").strip() or short_symbol(r.get("mint",""))
        athx = f"{float(r['ath_mult']):.2f}x" if r.get("ath_mult") else ""
        if r.get("ath_mult"): 
            try: ath_vals.append(float(r["ath_mult"]))
            except: pass
        emc = human_mc(r.get("entry_mc","")); xmc = human_mc(r.get("exit_mc",""))
        pnl_coin = f"{float(r['pnl_token']):.4f}" if r.get("pnl_token") else ""
        hold = fmt_dur(r.get("hold_min","")); reason=(r.get("exit_reason") or "").strip()
        table.append([coin, athx, emc, xmc, pnl_coin, hold, reason])
        try: total_pnl += float(r.get("pnl_usd",0) or 0)
        except: pass
        if (r.get("hold_min") or "").isdigit(): holds.append(int(r["hold_min"]))
        if reason: reasons.append(reason)

    widths = [len(h) for h in headers]
    for row in table:
        for i, cell in enumerate(row): widths[i] = max(widths[i], len(str(cell)))
    def line(cells): return " | ".join(str(cells[i]).ljust(widths[i]) for i in range(len(headers)))

    print(line(headers)); print("-+-".join("-"*w for w in widths))
    for row in table: print(line(row))

    avg_hold = (sum(holds)/len(holds)) if holds else 0.0
    from math import floor
    h = floor(avg_hold/60); mm = int(avg_hold%60)
    avg_athx = (sum(ath_vals)/len(ath_vals)) if ath_vals else 0.0
    from collections import Counter
    top_reason, top_count = (Counter(reasons).most_common(1)[0] if reasons else ("",0))
    win_rate = (100.0 * sum(1 for r in rows if r.get("pnl_usd") and float(r["pnl_usd"])>0) / len(rows)) if rows else 0.0

    print("\n=== SUMMARY ===")
    print(f"Total PNL (USD): {total_pnl:+.2f}")
    print(f"Average hold: {f'{h}h {mm}m' if h else f'{mm}m'}")
    print(f"Average ATH multiple from entry: {avg_athx:.2f}x")
    print(f"Win rate: {win_rate:.1f}%")
    if top_reason: print(f"Most common exit reason: {top_reason} ({top_count})")
if __name__ == "__main__":
    main()
