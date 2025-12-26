# src/batch_sim.py  (CSV adds coin_symbol/coin_name; console unchanged)
import os, sys, re, subprocess, csv, time
import httpx
from collections import Counter
import argparse

API_ROOT = "https://api.geckoterminal.com/api/v2"
BATCH_FILE = os.path.join("src", "batch_lines.txt")
OUT_DIR = "out"
OUT_CSV = os.path.join(OUT_DIR, "batch_results.csv")

PNL_RE        = re.compile(r"PNL:\s*\$([-\d,\.]+)\s+Return:\s*([-\d\.]+)%")
ENTRY_RE      = re.compile(r"Entry\s*@\s*([0-9\-: ]+UTC)")
EXIT_LINE_RE  = re.compile(r"-\s*Exit\s+([A-Za-z0-9@._\-\(\)]+)\s*@\s*([0-9\-: ]+UTC)\s+raw:([0-9\.]+)\s+recv.*?part:([0-9\.]+)%")
NET_RE        = re.compile(r"Net:\s*([a-z_]+)\s*\|")
STATS_RE      = re.compile(r"^STATS:\s*(.+)$", re.MULTILINE)

def parse_args():
    p = argparse.ArgumentParser(description="Batch run Telegram backtest lines")
    # backtest knobs (we only *forward* these; math is updated in step 2)
    p.add_argument('--slip', type=float, default=0.00,
               help='Slippage fraction, e.g. 0.03 = 3 percent')
    p.add_argument('--slip-mode', choices=['price','amount'], default='amount',
               help='Apply slippage to price (price) or cash (amount)')
    p.add_argument('--slip-side', choices=['both','buy','sell'], default='sell',
               help='Which leg gets slippage')
    p.add_argument('--buy-fee', type=float, default=0.01,
               help='Buy fee fraction, e.g. 0.01 = 1 percent')
    p.add_argument('--sell-fee', type=float, default=0.01,
               help='Sell fee fraction, e.g. 0.01 = 1 percent')

    return p.parse_args()

def get_token_info(net: str, mint: str):
    try:
        r = httpx.get(f"{API_ROOT}/networks/{net}/tokens/{mint}",
                      headers={"accept":"application/json"}, timeout=6.0)
        r.raise_for_status()
        js = r.json()
        data = js.get("data") or []
        if not data: return {"symbol": mint[:4]+"…", "name": mint}
        attrs = data[0].get("attributes", {})
        sym = attrs.get("symbol") or (mint[:4]+"…")
        name = attrs.get("name") or sym
        return {"symbol": sym, "name": name}
    except Exception:
        return {"symbol": mint[:4]+"…", "name": mint}

def parse_stats(blob: str):
    m = STATS_RE.search(blob)
    out = {}
    if not m: return out
    parts = m.group(1).strip().split()
    for p in parts:
        if "=" in p:
            k,v = p.split("=",1)
            out[k]=v
    return out

def human_mc(x):
    try: n = float(x)
    except: return ""
    for unit,div in [("t",1e12),("b",1e9),("m",1e6),("k",1e3)]:
        if abs(n) >= div: return f"{n/div:.2f}{unit}"
    return f"{n:.0f}"

def fmt_dur(mins):
    try: m = int(mins)
    except: return ""
    h = m//60; mm = m%60
    return f"{h}h {mm}m" if h else f"{mm}m"

def clean_parts(line: str):
    if "|" in line: parts = [p.strip() for p in line.split("|")]
    else:           parts = [p.strip() for p in line.split(",")]
    return [p for p in parts if p != ""]

def run_line(parts, args_env):
    mc = ""
    if len(parts) == 9:
        mint, hhmm, invest, tp1_up, tp1_sz, tp2_up, tp2_sz, sl_dn, mode = parts
        cmd = [sys.executable, os.path.join("src","single_trade_sim_partial.py"),
               mint, hhmm, str(invest), str(tp1_up), str(tp1_sz), str(tp2_up), str(tp2_sz), str(sl_dn), mode]
    elif len(parts) >= 10:
        mint, hhmm, mc, invest, tp1_up, tp1_sz, tp2_up, tp2_sz, sl_dn, mode = parts[:10]
        cmd = [sys.executable, os.path.join("src","single_trade_sim_partial_mc.py"),
               mint, hhmm, mc, str(invest), str(tp1_up), str(tp1_sz), str(tp2_up), str(tp2_sz), str(sl_dn), mode]
    else:
        raise ValueError(f"Bad line (need 9 or 10 fields): {parts}")
    # IMPORTANT: forward slippage/fee config to child via environment (used in Step 2)
    env = os.environ.copy()
    env.update(args_env)
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (res.stdout or "") + (res.stderr or "")
    pnl = ret = None
    m = PNL_RE.search(out)
    if m:
        pnl = float(m.group(1).replace(",","")); ret = float(m.group(2))
    entry_dt = (ENTRY_RE.search(out).group(1) if ENTRY_RE.search(out) else "")
    exits = EXIT_LINE_RE.findall(out)
    exit_dt = exits[-1][1] if exits else ""
    exit_reason = exits[-1][0] if exits else ""
    net = (NET_RE.search(out).group(1) if NET_RE.search(out) else "")
    stats = parse_stats(out)
    entry_raw = stats.get("entry_raw","")
    exit_raw_avg = stats.get("exit_raw_avg","")
    ath_mult = stats.get("ath_mult","")
    hold_min = stats.get("hold_min","")
    pnl_token = stats.get("pnl_token","")
    entry_mc = stats.get("entry_mc","")
    exit_mc = stats.get("exit_mc","")
    mode = stats.get("mode", parts[-1])
    invest = float(stats.get("invest", parts[2 if len(parts)==9 else 3]))
    # NEW: fetch coin name/symbol (fast timeout, safe fallback)
    info = get_token_info(net or "solana", mint)
    coin_symbol = info.get("symbol")
    coin_name = info.get("name")
    return out, {
        "mint": mint,
        "coin_symbol": coin_symbol,
        "coin_name": coin_name,
        "net": net,
        "time_hhmm_utc": parts[1],
        "mc": (parts[2] if len(parts)>=10 else ""),
        "invest_usd": invest,
        "mode": mode,
        "pnl_usd": pnl,
        "return_pct": ret,
        "entry_dt_utc": entry_dt,
        "exit_dt_utc": exit_dt,
        "exit_reason": exit_reason,
        "hold_min": hold_min,
        "entry_raw": entry_raw,
        "exit_raw_avg": exit_raw_avg,
        "ath_mult": ath_mult,
        "pnl_token": pnl_token,
        "entry_mc": entry_mc,
        "exit_mc": exit_mc,
    }

def main():
    args = parse_args()
    # config banner so we can verify wiring
    print(f"[cfg] slip={args.slip} mode={args.slip_mode} side={args.slip_side} "
          f"buy_fee={args.buy_fee} sell_fee={args.sell_fee}")

    # prepare env vars for children (Step 2 will read these)
    args_env = {
        "TB_SLIP": str(args.slip),
        "TB_SLIP_MODE": args.slip_mode,     # 'price' | 'amount'
        "TB_SLIP_SIDE": args.slip_side,     # 'both' | 'buy' | 'sell'
        "TB_BUY_FEE": str(args.buy_fee),
        "TB_SELL_FEE": str(args.sell_fee),
    }

    if not os.path.isfile(BATCH_FILE):
        print(f"Input file not found: {BATCH_FILE}"); sys.exit(1)
    raw = open(BATCH_FILE, "r", encoding="utf-8").read().splitlines()
    lines = [ln.lstrip("\ufeff") for ln in raw]
    jobs = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    print(f"Running {len(jobs)} lines...\n")

    rows = []
    for i, ln in enumerate(lines, 1):
        line = ln.strip()
        if not line or line.lstrip().startswith("#"): continue
        parts = clean_parts(line)
        try:
            out, row = run_line(parts, args_env=args_env)
            rows.append(row)
            tail = "\n".join(out.strip().splitlines()[-4:])
            print(f"\n--- LINE {i} ---\n{tail}\n")
        except Exception as e:
            print(f"\n--- LINE {i} ERROR --- {e}\n")

    ok = [r for r in rows if r["pnl_usd"] is not None]

    # Console table (kept minimal)
    print("\n=== TRADES ===")
    headers = ["Coin","ATH x","Entry MC","Exit MC","PnL (coin)","Hold","Exit reason"]
    def human_mc(x):
        try: n = float(x)
        except: return ""
        for unit,div in [("t",1e12),("b",1e9),("m",1e6),("k",1e3)]:
            if abs(n) >= div: return f"{n/div:.2f}{unit}"
        return f"{n:.0f}"
    def fmt_dur(mins):
        try: m = int(mins)
        except: return ""
        h = m//60; mm = m%60
        return f"{h}h {mm}m" if h else f"{mm}m"
    table_rows = []
    for r in ok:
        coin = r.get("coin_symbol") or (r["mint"][:4]+"…")
        athx = f"{float(r['ath_mult']):.2f}x" if r["ath_mult"] else ""
        emc = human_mc(r["entry_mc"]) if r["entry_mc"] else ""
        xmc = human_mc(r["exit_mc"]) if r["exit_mc"] else ""
        pnl_coin = f"{float(r['pnl_token']):.4f}" if r["pnl_token"] else ""
        hold = fmt_dur(r["hold_min"])
        reason = r["exit_reason"]
        table_rows.append([coin, athx, emc, xmc, pnl_coin, hold, reason])
    widths = [ max(len(h), max((len(str(row[i])) for row in table_rows), default=0)) for i,h in enumerate(headers) ]
    print(" | ".join(h.ljust(widths[i]) for i,h in enumerate(headers)))
    print("-+-".join("-"*w for w in widths))
    for row in table_rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))))

    # Summary
    total_pnl = sum(r["pnl_usd"] for r in ok)
    avg_hold  = sum(int(r["hold_min"]) for r in ok if str(r["hold_min"]).isdigit()) / len(ok) if ok else 0
    reasons = Counter((r["exit_reason"] for r in ok if r["exit_reason"]))
    top_reason, top_count = (reasons.most_common(1)[0] if reasons else ("",0))
    win_rate = 100.0 * sum(1 for r in ok if r["pnl_usd"]>0) / len(ok) if ok else 0.0
    avg_athx = sum(float(r["ath_mult"]) for r in ok if r["ath_mult"]) / max(1, sum(1 for r in ok if r["ath_mult"]))
    print("\n=== SUMMARY ===")
    print(f"Total PNL (USD): ${total_pnl:,.2f}")
    print(f"Average hold: {fmt_dur(int(avg_hold))}")
    print(f"Average ATH multiple from entry: {avg_athx:.2f}x")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Most common exit reason: {top_reason} ({top_count})")

    # CSV write (now with symbol/name)
    os.makedirs(OUT_DIR, exist_ok=True)
    fields = ["mint","coin_symbol","coin_name","net","time_hhmm_utc","mc","invest_usd","mode","pnl_usd","return_pct",
              "entry_dt_utc","exit_dt_utc","exit_reason","hold_min","entry_raw","exit_raw_avg",
              "ath_mult","pnl_token","entry_mc","exit_mc"]
    try:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in ok: w.writerow(r)
        print(f"\nCSV saved: {OUT_CSV}")
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S")
        alt = os.path.join(OUT_DIR, f"batch_results_{ts}.csv")
        with open(alt, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            for r in ok: w.writerow(r)
        print(f"\nCSV in use — wrote to: {alt}")

if __name__ == "__main__":
    main()
