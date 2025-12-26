import csv, argparse

def load_candles(csvfile):
    rows = []
    with open(csvfile,newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "ts": int(r["ts"]),
                "o": float(r["o"]),
                "h": float(r["h"]),
                "l": float(r["l"]),
                "c": float(r["c"]),
                "v": float(r["v"])
            })
    return rows

def simulate_trade(candles, entry_unix, invest_usd=100, tp=None, sl=None, tsl=None, slip=0.03, fee=1.0, entry_mc=None):
    # 1. Smart entry with ±5s tolerance and MC validation
    entry_candle = None
    best_match = None
    min_time_diff = float('inf')
    
    # First try exact match
    entry_candle = next((c for c in candles if c["ts"] == entry_unix), None)
    
    # If no exact match, find closest within ±5 seconds
    if not entry_candle:
        for c in candles:
            time_diff = abs(c["ts"] - entry_unix)
            if time_diff <= 5 and time_diff < min_time_diff:  # ±5 seconds tolerance
                best_match = c
                min_time_diff = time_diff
        
        if best_match:
            entry_candle = best_match
    
    if not entry_candle:
        return {
            "status": "no_entry",
            "pnl": 0.0,
            "exit_reason": "no_entry",
            "trade_ath": None,
            "market_ath": None,
            "duration": None
        }

    # Smart entry price: use candle open (most realistic for signal timing)
    entry_price = entry_candle["o"] * (1+slip)
    tokens = (invest_usd - fee) / entry_price

    tp_level = entry_price * (1+tp) if tp else None
    sl_level = entry_price * (1-sl) if sl else None

    trade_ath = entry_price
    market_ath = entry_price
    trade_atl = entry_price  # Track all-time low between entry and ATH
    exit_price, exit_reason = entry_price, "neutral"
    exit_ts = None
    exited = False

    # 2. Walk candles forward
    for c in candles:
        if c["ts"] <= entry_unix:
            continue

        # Always update market ATH, regardless of exit
        market_ath = max(market_ath, c["h"])

        if not exited:
            # Only update trade ATH while trade is alive
            trade_ath = max(trade_ath, c["h"])
            # Track all-time low between entry and current ATH
            trade_atl = min(trade_atl, c["l"])
            tsl_level = trade_ath * (1-tsl) if tsl else None

            hit_sl = sl_level and c["l"] <= sl_level
            hit_tp = tp_level and c["h"] >= tp_level
            hit_tsl = tsl_level and c["l"] <= tsl_level if tsl else False

            # Single trigger
            if hit_sl and not (hit_tp or hit_tsl):
                exit_price = sl_level * (1-slip)
                exit_reason = "SL"
                exit_ts = c["ts"]
                exited = True
            elif hit_tp and not (hit_sl or hit_tsl):
                exit_price = tp_level * (1-slip)
                exit_reason = "TP"
                exit_ts = c["ts"]
                exited = True
            elif hit_tsl and not (hit_tp or hit_sl):
                exit_price = tsl_level * (1-slip)
                exit_reason = "TSL"
                exit_ts = c["ts"]
                exited = True

            # Multiple triggers same candle
            elif (hit_tp and hit_sl) or (hit_tp and hit_tsl) or (hit_sl and hit_tsl):
                if c["o"] >= entry_price:
                    if hit_tp:
                        exit_price = tp_level * (1-slip) if tp_level else entry_price*(1-slip)
                        exit_reason = "TP"
                    else:
                        exit_price = tsl_level * (1-slip)
                        exit_reason = "TSL"
                elif c["o"] < entry_price:
                    if hit_sl:
                        exit_price = sl_level * (1-slip)
                        exit_reason = "SL"
                    else:
                        exit_price = tsl_level * (1-slip)
                        exit_reason = "TSL"
                else:
                    exit_price = entry_price * (1-slip)
                    exit_reason = "neutral"
                exit_ts = c["ts"]
                exited = True

    # If never hit → neutral at last close
    if not exited and candles[-1]["ts"] > entry_unix:
        exit_price = candles[-1]["c"] * (1-slip)
        exit_reason = "neutral"
        exit_ts = candles[-1]["ts"]

    proceeds = tokens*exit_price - fee
    pnl = proceeds - invest_usd

    return {
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl": pnl,
        "return_pct": pnl/invest_usd*100,
        "trade_ath": trade_ath/entry_price if entry_price else None,
        "market_ath": market_ath/entry_price if entry_price else None,
        "trade_atl": trade_atl/entry_price if entry_price else None,  # All-time low multiplier
        "max_drawdown": (entry_price - trade_atl)/entry_price*100 if entry_price else None,  # Max drawdown %
        "duration": exit_ts - entry_unix if exit_ts else None
    }



if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--unix", type=int, required=True)
    p.add_argument("--tp", type=float, default=None)
    p.add_argument("--sl", type=float, default=None)
    p.add_argument("--tsl", type=float, default=None)
    args = p.parse_args()

    candles = load_candles(args.csv)
    res = simulate_trade(candles, args.unix, tp=args.tp, sl=args.sl, tsl=args.tsl)

    print("== TRADE RESULT ==")
    for k,v in res.items():
        print(f"{k}: {v}")
