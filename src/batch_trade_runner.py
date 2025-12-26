import csv, argparse, pathlib, datetime as dt
from statistics import mean, mode
from rich.console import Console
from rich.table import Table

import sys
import os
sys.path.append(os.path.dirname(__file__))
from single_trade_from_cache import simulate_trade
from fetch_and_cache_candles import get_top_pool, fetch_gt_candles, http_get

OUTDIR = pathlib.Path(__file__).resolve().parent.parent / "out"
OUTDIR.mkdir(exist_ok=True)

console = Console()

net_map = {
    "SOL": "solana",
    "ETH": "eth",
    "BNB": "bsc"
}

# --- Helpers ---
def parse_mc(s):
    s = str(s).upper().strip()
    if s.endswith("K"):
        return float(s[:-1]) * 1000
    if s.endswith("M"):
        return float(s[:-1]) * 1_000_000
    return float(s)

def format_mc(v):
    if v is None:
        return "N/A"
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    return f"{v/1000:.2f}K"

def format_duration(seconds):
    if not seconds:
        return "N/A"
    if seconds < 60:
        return f"{seconds}m"  # Always show in minutes format
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, r = divmod(seconds, 3600)
        m, _ = divmod(r, 60)
        return f"{h}h {m}m"

def fetch_coin_name(chain, token):
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{net_map[chain]}/tokens/{token}"
        data = http_get(url)
        return data["data"]["attributes"].get("name") or token[:6]
    except:
        return token[:6]

# --- Batch runner ---
def run_batch(input_file, tp, sl, tsl):
    results = []
    PKT = dt.timezone(dt.timedelta(hours=5))

    with open(input_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chain = row["chain"].upper()
            token = row["token"]
            time_str = row["time"]
            entry_mc = parse_mc(row["entry_mc"])

            # Convert PKT time to unix
            now_utc = dt.datetime.now(dt.timezone.utc)
            now_pkt = now_utc.astimezone(PKT)
            hh, mm = map(int, time_str.split(":"))
            cand_pkt = now_pkt.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if cand_pkt > now_pkt:
                cand_pkt -= dt.timedelta(days=1)
            cand_utc = cand_pkt.astimezone(dt.timezone.utc)
            unix = int(cand_utc.timestamp())

            # Fetch candles with smart caching around signal time
            pool = get_top_pool(net_map[chain], token)
            candles = fetch_gt_candles(net_map[chain], pool, start_unix=unix, signal_unix=unix)

            # Run trade simulation with improved entry logic
            res = simulate_trade(candles, unix, tp=tp, sl=sl, tsl=tsl, entry_mc=entry_mc)

            # Calculate exit_mc
            entry_price = res.get("entry_price")
            exit_price = res.get("exit_price")
            exit_mc = entry_mc * (exit_price/entry_price) if entry_price and exit_price else None

            coin_name = fetch_coin_name(chain, token)

            res.update({
                "chain": chain,
                "token": token,
                "coin": coin_name,
                "unix": unix,
                "entry_mc": entry_mc,
                "exit_mc": exit_mc
            })
            results.append(res)

    # --- Print Rich table ---
    table = Table(title="Batch Backtest Results")
    table.add_column("Coin")
    table.add_column("Trade ATH(x)")
    table.add_column("Market ATH(x)")
    table.add_column("Trade ATL(x)")
    table.add_column("Max DD%")
    table.add_column("Entry MC")
    table.add_column("Exit MC")
    table.add_column("PNL($)")
    table.add_column("Duration")
    table.add_column("Exit Reason")

    for r in results:
        coin = r["coin"]
        trade_ath = f"{r['trade_ath']:.2f}x" if r.get("trade_ath") else "N/A"
        market_ath = f"{r['market_ath']:.2f}x" if r.get("market_ath") else "N/A"
        trade_atl = f"{r['trade_atl']:.2f}x" if r.get("trade_atl") else "N/A"
        max_dd = f"{r['max_drawdown']:.1f}%" if r.get("max_drawdown") else "N/A"
        entry_mc = format_mc(r["entry_mc"])
        exit_mc = format_mc(r["exit_mc"])
        pnl = r.get("pnl", 0)
        duration = format_duration(r.get("duration"))
        reason = r.get("exit_reason", "no_entry")

        if pnl > 0:
            pnl_str = f"[green]{pnl:.2f}[/green]"
            reason_str = f"[green]{reason}[/green]"
        elif pnl < 0:
            pnl_str = f"[red]{pnl:.2f}[/red]"
            reason_str = f"[red]{reason}[/red]"
        else:
            pnl_str = f"[yellow]{pnl:.2f}[/yellow]"
            reason_str = f"[yellow]{reason}[/yellow]"

        table.add_row(coin, trade_ath, market_ath, trade_atl, max_dd, entry_mc, exit_mc, pnl_str, duration, reason_str)

    console.print(table)

    # --- Summary ---
    pnl_total = sum(r.get("pnl", 0) for r in results)
    durations = [r["duration"] for r in results if r.get("duration")]
    exit_reasons = [r["exit_reason"] for r in results if r.get("exit_reason") and r["exit_reason"] != "no_entry"]

    wins = [r for r in results if r.get("pnl", 0) > 0]
    losses = [r for r in results if r.get("pnl", 0) < 0]
    neutral = [r for r in results if r.get("pnl", 0) == 0]

    console.print("\n[bold]SUMMARY[/bold]:")
    console.print(f"Total calls: {len(results)}")
    console.print(f"Winning calls: {len(wins)}")
    console.print(f"Losing calls: {len(losses)}")
    console.print(f"Neutral calls: {len(neutral)}")
    console.print(f"Total PnL: {pnl_total:+.2f}")
    if durations:
        console.print(f"Average trade duration: {mean(durations)/60:.1f}m")
    if exit_reasons:
        try:
            console.print(f"Most common exit reason: {mode(exit_reasons)}")
        except:
            pass

    # --- Save CSV ---
    outfile = OUTDIR / "batch_results.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "coin","token","unix","entry_mc","exit_mc",
            "trade_ath","market_ath","trade_atl","max_drawdown",
            "pnl","return_pct","duration","exit_reason"
        ])
        w.writeheader()
        for r in results:
            w.writerow({
                "coin": r["coin"], "token": r["token"], "unix": r["unix"],
                "entry_mc": r["entry_mc"], "exit_mc": r.get("exit_mc"),
                "trade_ath": r.get("trade_ath"), "market_ath": r.get("market_ath"),
                "trade_atl": r.get("trade_atl"), "max_drawdown": r.get("max_drawdown"),
                "pnl": r.get("pnl"), "return_pct": r.get("return_pct"),
                "duration": r.get("duration"), "exit_reason": r.get("exit_reason")
            })
    console.print(f"\nSaved results -> {outfile}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="CSV file with columns: chain,token,time,entry_mc")
    p.add_argument("--tp", type=float, default=None)
    p.add_argument("--sl", type=float, default=None)
    p.add_argument("--tsl", type=float, default=None)
    args = p.parse_args()
    run_batch(args.input, tp=args.tp, sl=args.sl, tsl=args.tsl)
