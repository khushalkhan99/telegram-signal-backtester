import csv, argparse, pathlib, datetime as dt
import itertools
import json
from statistics import mean, median, stdev
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID
import time
import os

from single_trade_from_cache import simulate_trade, load_candles

OUTDIR = pathlib.Path(__file__).resolve().parent.parent / "out"
CACHEDIR = pathlib.Path(__file__).resolve().parent.parent / "cache"
OUTDIR.mkdir(exist_ok=True)
CACHEDIR.mkdir(exist_ok=True)

console = Console()

# --- Strategy Parameter Ranges ---
TP_RANGE = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0]  # 10% to 500%
SL_RANGE = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0]  # 5% to 100%
TSL_RANGE = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 1.0]  # 5% to 100%

# --- Helpers ---
def parse_mc(s):
    s = str(s).upper().strip()
    if s.endswith("K"):
        return float(s[:-1]) * 1000
    if s.endswith("M"):
        return float(s[:-1]) * 1_000_000
    return float(s)

def load_cached_data_from_batch_results():
    """Load cached data from existing batch results"""
    batch_file = OUTDIR / "batch_results.csv"
    if not batch_file.exists():
        console.print("[red]No batch results found! Please run batch_trade_runner.py first.[/red]")
        return None
    
    # Load the batch results to get the data we already have
    with open(batch_file, newline="") as f:
        reader = csv.DictReader(f)
        results = list(reader)
    
    console.print(f"[green]Loaded {len(results)} cached results from batch run[/green]")
    return results

def create_synthetic_candles_from_result(result):
    """Create synthetic candles from batch result for strategy testing"""
    # This is a simplified approach - in reality you'd want to store the actual candle data
    # For now, we'll create a basic synthetic dataset based on the result
    
    entry_price = float(result.get("entry_price", 1.0))
    exit_price = float(result.get("exit_price", entry_price))
    trade_ath = float(result.get("trade_ath", 1.0)) * entry_price
    trade_atl = float(result.get("trade_atl", 1.0)) * entry_price
    duration = int(result.get("duration", 3600))  # Default 1 hour
    
    # Create synthetic candles that match the result
    candles = []
    unix = int(result.get("unix", 0))
    
    # Create candles that go from entry -> ATL -> ATH -> exit
    num_candles = max(duration // 60, 10)  # At least 10 candles
    
    for i in range(num_candles):
        progress = i / (num_candles - 1)
        
        # Simple price movement: entry -> ATL (first 30%) -> ATH (next 40%) -> exit (last 30%)
        if progress < 0.3:
            # Going down to ATL
            price = entry_price - (entry_price - trade_atl) * (progress / 0.3)
        elif progress < 0.7:
            # Going up to ATH
            atl_progress = (progress - 0.3) / 0.4
            price = trade_atl + (trade_ath - trade_atl) * atl_progress
        else:
            # Going down to exit
            ath_progress = (progress - 0.7) / 0.3
            price = trade_ath - (trade_ath - exit_price) * ath_progress
        
        # Add some volatility
        volatility = 0.02  # 2% volatility
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        
        candle = {
            "ts": unix + (i * 60),
            "o": price,
            "h": high,
            "l": low,
            "c": price,
            "v": 1000.0
        }
        candles.append(candle)
    
    return candles

def calculate_strategy_metrics(results):
    """Calculate comprehensive strategy performance metrics"""
    if not results:
        return {}
    
    pnls = [r.get("pnl", 0) for r in results if r.get("pnl") is not None]
    returns = [r.get("return_pct", 0) for r in results if r.get("return_pct") is not None]
    durations = [r.get("duration", 0) for r in results if r.get("duration") is not None]
    max_dds = [r.get("max_drawdown", 0) for r in results if r.get("max_drawdown") is not None]
    
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
        "median_pnl": median(pnls),
        "max_pnl": max(pnls),
        "min_pnl": min(pnls),
        "avg_return": mean(returns) if returns else 0,
        "avg_duration": mean(durations) if durations else 0,
        "avg_max_dd": mean(max_dds) if max_dds else 0,
        "max_dd": max(max_dds) if max_dds else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else float('inf'),
        "sharpe_ratio": mean(returns) / stdev(returns) if len(returns) > 1 and stdev(returns) > 0 else 0
    }

def optimize_strategies_on_cached_data(cached_results, max_combinations=1000):
    """Optimize strategies using cached batch results"""
    console.print(f"[bold blue]Optimizing strategies on {len(cached_results)} cached results...[/bold blue]")
    
    # Generate strategy combinations
    all_combinations = list(itertools.product(TP_RANGE, SL_RANGE, TSL_RANGE))
    total_combinations = len(all_combinations)
    
    if total_combinations > max_combinations:
        import random
        all_combinations = random.sample(all_combinations, max_combinations)
        console.print(f"[yellow]Sampling {max_combinations} combinations from {total_combinations} total[/yellow]")
    
    console.print(f"[green]Testing {len(all_combinations)} strategy combinations...[/green]")
    
    strategy_results = []
    
    with Progress() as progress:
        task = progress.add_task("[green]Optimizing strategies...", total=len(all_combinations))
        
        for i, (tp, sl, tsl) in enumerate(all_combinations):
            # Test this strategy on all cached results
            strategy_results_for_combo = []
            
            for result in cached_results:
                try:
                    # Skip if no entry found
                    if result.get("exit_reason") == "no_entry":
                        continue
                    
                    # Create synthetic candles from the result
                    candles = create_synthetic_candles_from_result(result)
                    if not candles:
                        continue
                    
                    unix = int(result.get("unix", 0))
                    entry_mc = float(result.get("entry_mc", 0))
                    
                    # Run trade simulation
                    res = simulate_trade(candles, unix, tp=tp, sl=sl, tsl=tsl, entry_mc=entry_mc)
                    
                    # Add result info
                    res.update({
                        "chain": result.get("chain", ""),
                        "token": result.get("token", ""),
                        "coin": result.get("coin", ""),
                        "unix": unix,
                        "entry_mc": entry_mc
                    })
                    
                    strategy_results_for_combo.append(res)
                    
                except Exception as e:
                    console.print(f"[red]Error processing result: {e}[/red]")
                    continue
            
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
            
            progress.update(task, advance=1)
    
    return strategy_results

def find_best_strategies(strategy_results, top_n=10):
    """Find the best performing strategies"""
    if not strategy_results:
        return []
    
    # Sort by multiple criteria (weighted score)
    def strategy_score(metrics):
        # Weighted scoring: 40% total PnL, 30% win rate, 20% profit factor, 10% Sharpe ratio
        pnl_score = metrics.get("total_pnl", 0) / 100  # Normalize PnL
        win_rate_score = metrics.get("win_rate", 0) / 100
        pf_score = min(metrics.get("profit_factor", 0), 10) / 10  # Cap profit factor at 10
        sharpe_score = min(metrics.get("sharpe_ratio", 0), 5) / 5  # Cap Sharpe at 5
        
        return (0.4 * pnl_score + 0.3 * win_rate_score + 0.2 * pf_score + 0.1 * sharpe_score)
    
    # Sort by score
    sorted_strategies = sorted(strategy_results, key=strategy_score, reverse=True)
    return sorted_strategies[:top_n]

def display_optimization_results(best_strategies):
    """Display the best strategies in a formatted table"""
    if not best_strategies:
        console.print("[red]No strategies found![/red]")
        return
    
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
    table.add_column("Sharpe", justify="right")
    
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
        sharpe = f"{strategy['sharpe_ratio']:.2f}"
        
        table.add_row(rank, strategy_name, tp, sl, tsl, total_pnl, win_rate, avg_pnl, pf, sharpe)
    
    console.print(table)

def save_optimization_results(strategy_results, best_strategies, output_file):
    """Save optimization results to CSV"""
    # Save all results
    all_results_file = OUTDIR / f"all_strategies_{output_file}"
    with open(all_results_file, "w", newline="", encoding="utf-8") as f:
        if strategy_results:
            w = csv.DictWriter(f, fieldnames=strategy_results[0].keys())
            w.writeheader()
            for r in strategy_results:
                w.writerow(r)
    
    # Save best strategies
    best_results_file = OUTDIR / f"best_strategies_{output_file}"
    with open(best_results_file, "w", newline="", encoding="utf-8") as f:
        if best_strategies:
            w = csv.DictWriter(f, fieldnames=best_strategies[0].keys())
            w.writeheader()
            for r in best_strategies:
                w.writerow(r)
    
    console.print(f"[green]Saved all results -> {all_results_file}[/green]")
    console.print(f"[green]Saved best strategies -> {best_results_file}[/green]")

def main():
    parser = argparse.ArgumentParser(description="Smart Strategy Optimizer (Uses Cached Data)")
    parser.add_argument("--max-combinations", type=int, default=1000, help="Maximum strategy combinations to test")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top strategies to display")
    args = parser.parse_args()
    
    # Load cached data from batch results
    cached_results = load_cached_data_from_batch_results()
    if not cached_results:
        return
    
    # Run optimization
    start_time = time.time()
    strategy_results = optimize_strategies_on_cached_data(cached_results, args.max_combinations)
    optimization_time = time.time() - start_time
    
    console.print(f"[green]Optimization completed in {optimization_time:.1f} seconds[/green]")
    console.print(f"[green]Tested {len(strategy_results)} strategies[/green]")
    
    # Find best strategies
    best_strategies = find_best_strategies(strategy_results, args.top_n)
    
    # Display results
    display_optimization_results(best_strategies)
    
    # Save results
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"optimization_{timestamp}.csv"
    save_optimization_results(strategy_results, best_strategies, output_file)
    
    # Summary
    if best_strategies:
        best = best_strategies[0]
        console.print(f"\n[bold green]🏆 BEST STRATEGY:[/bold green]")
        console.print(f"TP: {best['tp']*100:.0f}% | SL: {best['sl']*100:.0f}% | TSL: {best['tsl']*100:.0f}%")
        console.print(f"Total PnL: ${best['total_pnl']:.2f} | Win Rate: {best['win_rate']:.1f}%")
        console.print(f"Profit Factor: {best['profit_factor']:.2f} | Sharpe Ratio: {best['sharpe_ratio']:.2f}")

if __name__ == "__main__":
    main()

