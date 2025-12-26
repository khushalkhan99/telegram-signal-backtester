import csv, argparse, pathlib, datetime as dt
import itertools
from statistics import mean, median, stdev
from rich.console import Console
from rich.table import Table

from single_trade_from_cache import simulate_trade
from fetch_and_cache_candles import get_top_pool, fetch_gt_candles, http_get

OUTDIR = pathlib.Path(__file__).resolve().parent.parent / "out"
console = Console()

net_map = {
    "SOL": "solana",
    "ETH": "eth", 
    "BNB": "bsc"
}

# --- Strategy Parameter Ranges (Smaller set for testing) ---
TP_RANGE = [0.2, 0.5, 1.0, 2.0]  # 20%, 50%, 100%, 200%
SL_RANGE = [0.1, 0.2, 0.3, 0.5]  # 10%, 20%, 30%, 50%
TSL_RANGE = [0.1, 0.2, 0.3, 0.5]  # 10%, 20%, 30%, 50%

# --- Helpers ---
def parse_mc(s):
    s = str(s).upper().strip()
    if s.endswith("K"):
        return float(s[:-1]) * 1000
    if s.endswith("M"):
        return float(s[:-1]) * 1_000_000
    return float(s)

def fetch_coin_name(chain, token):
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/{net_map[chain]}/tokens/{token}"
        data = http_get(url)
        return data["data"]["attributes"].get("name") or token[:6]
    except:
        return token[:6]

def calculate_strategy_metrics(results):
    """Calculate strategy performance metrics"""
    if not results:
        return {}
    
    pnls = [r.get("pnl", 0) for r in results if r.get("pnl") is not None]
    returns = [r.get("return_pct", 0) for r in results if r.get("return_pct") is not None]
    
    if not pnls:
        return {}
    
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    return {
        "total_trades": len(results),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(pnls) * 100 if pnls else 0,
        "total_pnl": sum(pnls),
        "avg_pnl": mean(pnls),
        "max_pnl": max(pnls),
        "min_pnl": min(pnls),
        "avg_return": mean(returns) if returns else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else float('inf')
    }

def test_strategy_on_signal(signal, tp, sl, tsl):
    """Test a single strategy on a single signal"""
    try:
        chain = signal["chain"].upper()
        token = signal["token"]
        time_str = signal["time"]
        entry_mc = parse_mc(signal["entry_mc"])
        
        # Convert PKT time to unix
        PKT = dt.timezone(dt.timedelta(hours=5))
        now_utc = dt.datetime.now(dt.timezone.utc)
        now_pkt = now_utc.astimezone(PKT)
        hh, mm = map(int, time_str.split(":"))
        cand_pkt = now_pkt.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cand_pkt > now_pkt:
            cand_pkt -= dt.timedelta(days=1)
        cand_utc = cand_pkt.astimezone(dt.timezone.utc)
        unix = int(cand_utc.timestamp())
        
        # Fetch candles with smart caching
        pool = get_top_pool(net_map[chain], token)
        candles = fetch_gt_candles(net_map[chain], pool, start_unix=unix, signal_unix=unix)
        
        # Run trade simulation
        res = simulate_trade(candles, unix, tp=tp, sl=sl, tsl=tsl, entry_mc=entry_mc)
        
        # Add signal info
        res.update({
            "chain": chain,
            "token": token,
            "coin": fetch_coin_name(chain, token),
            "unix": unix,
            "entry_mc": entry_mc
        })
        
        return res
        
    except Exception as e:
        console.print(f"[red]Error processing signal {signal}: {e}[/red]")
        return None

def test_strategies(signals, max_strategies=50):
    """Test multiple strategies on signals"""
    console.print(f"[bold blue]Testing strategies on {len(signals)} signals...[/bold blue]")
    
    # Generate strategy combinations
    all_combinations = list(itertools.product(TP_RANGE, SL_RANGE, TSL_RANGE))
    if len(all_combinations) > max_strategies:
        import random
        all_combinations = random.sample(all_combinations, max_strategies)
    
    console.print(f"[green]Testing {len(all_combinations)} strategy combinations...[/green]")
    
    strategy_results = []
    
    for i, (tp, sl, tsl) in enumerate(all_combinations):
        console.print(f"[cyan]Testing Strategy {i+1}/{len(all_combinations)}: TP{tp*100:.0f}% SL{sl*100:.0f}% TSL{tsl*100:.0f}%[/cyan]")
        
        # Test this strategy on all signals
        strategy_results_for_combo = []
        
        for signal in signals:
            result = test_strategy_on_signal(signal, tp, sl, tsl)
            if result:
                strategy_results_for_combo.append(result)
        
        # Calculate metrics for this strategy
        metrics = calculate_strategy_metrics(strategy_results_for_combo)
        if metrics:
            metrics.update({
                "tp": tp,
                "sl": sl, 
                "tsl": tsl,
                "strategy_id": f"TP{tp*100:.0f}_SL{sl*100:.0f}_TSL{tsl*100:.0f}"
            })
            strategy_results.append(metrics)
    
    return strategy_results

def display_results(strategy_results, top_n=10):
    """Display the best strategies"""
    if not strategy_results:
        console.print("[red]No strategies found![/red]")
        return
    
    # Sort by total PnL
    sorted_strategies = sorted(strategy_results, key=lambda x: x.get("total_pnl", 0), reverse=True)
    best_strategies = sorted_strategies[:top_n]
    
    table = Table(title="🏆 Top Strategy Results")
    table.add_column("Rank", style="bold")
    table.add_column("Strategy", style="cyan")
    table.add_column("TP%", justify="right")
    table.add_column("SL%", justify="right") 
    table.add_column("TSL%", justify="right")
    table.add_column("Total PnL", justify="right", style="green")
    table.add_column("Win Rate%", justify="right")
    table.add_column("Avg PnL", justify="right")
    table.add_column("Profit Factor", justify="right")
    
    for i, strategy in enumerate(best_strategies, 1):
        rank = f"#{i}"
        strategy_name = strategy["strategy_id"]
        tp = f"{strategy['tp']*100:.0f}%"
        sl = f"{strategy['sl']*100:.0f}%"
        tsl = f"{strategy['tsl']*100:.0f}%"
        total_pnl = f"${strategy['total_pnl']:.2f}"
        win_rate = f"{strategy['win_rate']:.1f}%"
        avg_pnl = f"${strategy['avg_pnl']:.2f}"
        pf = f"{strategy['profit_factor']:.2f}"
        
        table.add_row(rank, strategy_name, tp, sl, tsl, total_pnl, win_rate, avg_pnl, pf)
    
    console.print(table)
    
    # Show best strategy details
    if best_strategies:
        best = best_strategies[0]
        console.print(f"\n[bold green]🏆 BEST STRATEGY:[/bold green]")
        console.print(f"TP: {best['tp']*100:.0f}% | SL: {best['sl']*100:.0f}% | TSL: {best['tsl']*100:.0f}%")
        console.print(f"Total PnL: ${best['total_pnl']:.2f} | Win Rate: {best['win_rate']:.1f}%")
        console.print(f"Profit Factor: {best['profit_factor']:.2f}")

def main():
    parser = argparse.ArgumentParser(description="Simple Strategy Tester")
    parser.add_argument("--input", required=True, help="CSV file with signals")
    parser.add_argument("--max-strategies", type=int, default=50, help="Maximum strategies to test")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top strategies to display")
    args = parser.parse_args()
    
    # Load signals
    signals = []
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            signals.append(row)
    
    console.print(f"[bold]Loaded {len(signals)} signals for testing[/bold]")
    
    # Test strategies
    strategy_results = test_strategies(signals, args.max_strategies)
    
    console.print(f"[green]Tested {len(strategy_results)} strategies[/green]")
    
    # Display results
    display_results(strategy_results, args.top_n)
    
    # Save results
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTDIR / f"strategy_test_{timestamp}.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        if strategy_results:
            w = csv.DictWriter(f, fieldnames=strategy_results[0].keys())
            w.writeheader()
            for r in strategy_results:
                w.writerow(r)
    
    console.print(f"[green]Saved results -> {output_file}[/green]")

if __name__ == "__main__":
    main()

