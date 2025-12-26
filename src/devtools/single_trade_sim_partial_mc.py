# src/single_trade_sim_partial_mc.py — partial fills (TP1/TP2/SL), env-driven slip/fees
import sys, time, os
from datetime import datetime, timezone
import httpx

API_ROOT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana","bsc","eth","base"]

# ---------- HTTP / data ----------
def http_get(url, params=None):
    r = httpx.get(url, params=params or {}, headers={"accept":"application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def detect_network_and_pool(mint: str):
    for net in NETWORKS:
        try:
            js = http_get(f"{API_ROOT}/networks/{net}/tokens/{mint}/pools", {"page": 1})
        except Exception:
            continue
        data = js.get("data") or []
        if data:
            addr = data[0].get("attributes", {}).get("address")
            if addr:
                return net, addr
    raise RuntimeError("No pools found across solana/bsc/eth/base")

def fetch_ohlcv_1m_last_48h(network: str, pool: str):
    url = f"{API_ROOT}/networks/{network}/pools/{pool}/ohlcv/minute"
    out = []
    now = int(time.time())
    cutoff = now - 48*60*60
    before = now + 60
    for _ in range(6):
        js = http_get(url, {"aggregate":1, "limit":500, "before_timestamp": before})
        attrs = (js.get("data") or {}).get("attributes", {})
        lst = attrs.get("ohlcv_list") or []
        if not lst: break
        out.extend(lst)
        oldest = int(lst[0][0])
        before = oldest
        if oldest <= cutoff: break
        time.sleep(0.25)
    out.sort(key=lambda r: int(r[0]))
    return [r for r in out if int(r[0]) >= cutoff]

def find_entry_minute(candles, hh: int, mm: int):
    target_ts = None
    now = int(time.time()); cutoff = now - 48*60*60
    for ts, *_ in candles:
        t = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        if t.hour == hh and t.minute == mm and cutoff <= int(ts) <= now:
            target_ts = int(ts)
    return target_ts

def entry_fill(o,h,l,c, mode: str):
    lo, hi = float(l), float(h)
    op, cl = float(o), float(c)
    rng_up = max(0.0, hi - op)
    rng_dn = max(0.0, op - lo)
    is_green = cl >= op
    if mode == "optimistic":
        raw = op
    elif mode == "realistic":
        raw = op + (0.30*rng_up if is_green else -0.30*rng_dn)
    elif mode == "pessimistic":
        raw = hi
    else:
        raise RuntimeError("mode must be optimistic|realistic|pessimistic")
    raw = max(lo, min(hi, raw))
    return raw

def decide_exit_in_bar(bar_open, bar_high, bar_low, tp_px, sl_px, mode, ref_for_distance):
    hit_tp = bar_high >= tp_px
    hit_sl = bar_low  <= sl_px
    if hit_tp and hit_sl:
        if mode == "optimistic": return "TP"
        if mode == "pessimistic": return "SL"
        d_tp = abs(tp_px - ref_for_distance)
        d_sl = abs(ref_for_distance - sl_px)
        return "TP" if d_tp <= d_sl else "SL"
    if hit_tp: return "TP"
    if hit_sl: return "SL"
    return None

def fmt_usd(x): 
    return f"${x:,.2f}"

# ---------- env-driven slippage/fees ----------
def _cfg():
    slip = float(os.getenv("TB_SLIP", "0"))
    slip_mode = os.getenv("TB_SLIP_MODE", "amount")      # 'price' | 'amount'
    slip_side = os.getenv("TB_SLIP_SIDE", "sell")        # 'both' | 'buy' | 'sell'
    buy_fee = float(os.getenv("TB_BUY_FEE", "0.01"))     # fraction
    sell_fee = float(os.getenv("TB_SELL_FEE", "0.01"))   # fraction
    return slip, slip_mode, slip_side, buy_fee, sell_fee

def execute_buy(raw_price, invest_usd, buy_fee, slip, slip_mode, slip_side):
    """Return qty, paid_entry_px, buy_fee_usd, log_str"""
    buy_fee_usd = invest_usd * buy_fee
    cash_after_fee = invest_usd - buy_fee_usd
    if slip_side in ("both","buy"):
        if slip_mode == "price":
            paid_entry_px = raw_price * (1 + slip)
            qty = cash_after_fee / paid_entry_px
            log = f"raw:{raw_price:.8f}  paid(price,{int(slip*100)}%+fee): {paid_entry_px:.8f}  qty:{qty:.8f}"
            return qty, paid_entry_px, buy_fee_usd, log
        else:
            eff_cash = cash_after_fee * (1 - slip)
            qty = eff_cash / raw_price
            log = f"raw:{raw_price:.8f}  paid(amount,{int(slip*100)}%+fee) cash:{eff_cash:.2f}  qty:{qty:.8f}"
            return qty, raw_price, buy_fee_usd, log
    qty = cash_after_fee / raw_price
    log = f"raw:{raw_price:.8f}  paid(fee only): {raw_price:.8f}  qty:{qty:.8f}"
    return qty, raw_price, buy_fee_usd, log

def execute_sell_fill(raw_price, sub_qty, sell_fee, slip, slip_mode, slip_side, tstr, reason, frac):
    """Return sub_proceeds, sub_sell_fee_usd, log_line"""
    sub_gross = sub_qty * raw_price
    sub_sell_fee = sub_gross * sell_fee
    after_fee = sub_gross - sub_sell_fee
    if slip_side in ("both","sell"):
        if slip_mode == "price":
            recv_px = raw_price * (1 - slip)
            sub_proceeds = sub_qty * recv_px * (1 - sell_fee)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(price,{int(slip*100)}%):{recv_px:.8f}  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
        else:
            sub_proceeds = after_fee * (1 - slip)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(amount,{int(slip*100)}%)  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
    sub_proceeds = after_fee
    log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(no slip)  part:{frac*100:.1f}%"
    return sub_proceeds, sub_sell_fee, log

# ---------- main ----------
def main():
    if len(sys.argv) < 11:
        print("Usage: python src/single_trade_sim_partial_mc.py <mint> <HH:MM_UTC> <mc_hint> <invest_usd> <tp1_up_pct> <tp1_size_pct> <tp2_up_pct> <tp2_size_pct> <sl_down_pct> [mode]")
        sys.exit(1)

    mint   = sys.argv[1].strip()
    hhmm   = sys.argv[2].strip()
    mc_hint= sys.argv[3].strip()  # not used for math; kept for compatibility
    invest = float(sys.argv[4])
    tp1_up = float(sys.argv[5]) / 100.0
    tp1_sz = float(sys.argv[6]) / 100.0
    tp2_up = float(sys.argv[7]) / 100.0
    tp2_sz = float(sys.argv[8]) / 100.0
    sl_pct = float(sys.argv[9]) / 100.0
    mode   = sys.argv[10] if len(sys.argv) > 10 else "realistic"

    hh, mm = [int(x) for x in hhmm.split(":")]

    net, pool = detect_network_and_pool(mint)
    candles = fetch_ohlcv_1m_last_48h(net, pool)
    if not candles:
        print("No candles in last 48h."); sys.exit(2)

    entry_ts = find_entry_minute(candles, hh, mm)
    if not entry_ts:
        print("No candle found at that HH:MM within last 48h."); sys.exit(3)

    idx = next(i for i, r in enumerate(candles) if int(r[0]) == entry_ts)
    ts, o,h,l,c = int(candles[idx][0]), float(candles[idx][1]), float(candles[idx][2]), float(candles[idx][3]), float(candles[idx][4])
    e_dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # entry + thresholds
    raw_entry = entry_fill(o,h,l,c, mode)
    slip, slip_mode, slip_side, buy_fee_frac, sell_fee_frac = _cfg()
    qty, paid_entry, buy_fee_usd, buy_log = execute_buy(raw_entry, invest, buy_fee_frac, slip, slip_mode, slip_side)

    tp1_px = paid_entry * (1 + tp1_up)
    tp2_px = paid_entry * (1 + tp2_up)
    sl_px  = paid_entry * (1 - sl_pct)

    # selling plan: up to two TP fills (tp1_sz, tp2_sz) and remainder goes to SL or final bar
    remaining = qty
    proceeds = 0.0
    sell_fee_total = 0.0
    fills_for_avg = []
    max_high = float(h)

    print(f"Entry @ {e_dt}  {buy_log}  buy_fee:${buy_fee_usd:.2f} [mc]")

    # iterate bars from entry onward
    last_ts = ts
    for j in range(idx, min(idx+2000, len(candles))):
        ts2, o2,h2,l2,c2 = int(candles[j][0]), float(candles[j][1]), float(candles[j][2]), float(candles[j][3]), float(candles[j][4])
        last_ts = ts2
        max_high = max(max_high, h2)
        tstr = datetime.fromtimestamp(ts2, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # fill TP1 if not done and price hits
        if remaining > 0 and tp1_sz > 0:
            hit1 = decide_exit_in_bar(o2,h2,l2, tp1_px, sl_px, mode, paid_entry)
            if hit1 == "TP":
                sub_qty = qty * tp1_sz
                sub_qty = min(sub_qty, remaining)
                sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(o2, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, "TP@1", tp1_sz)
                proceeds += sub_proceeds; sell_fee_total += sub_sell_fee; remaining -= sub_qty
                fills_for_avg.append(o2)
                print(log_line)
                tp1_sz = 0.0  # done

        # fill TP2 if not done and price hits
        if remaining > 0 and tp2_sz > 0:
            hit2 = decide_exit_in_bar(o2,h2,l2, tp2_px, sl_px, mode, paid_entry)
            if hit2 == "TP":
                sub_qty = qty * tp2_sz
                sub_qty = min(sub_qty, remaining)
                sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(o2, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, "TP@2", tp2_sz)
                proceeds += sub_proceeds; sell_fee_total += sub_sell_fee; remaining -= sub_qty
                fills_for_avg.append(o2)
                print(log_line)
                tp2_sz = 0.0  # done

        # stop loss on remaining if SL hit
        if remaining > 0:
            hit_sl = decide_exit_in_bar(o2,h2,l2, 9e99, sl_px, mode, paid_entry) == "SL"
            if hit_sl:
                sub_qty = remaining
                sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(o2, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, "SL", sub_qty/qty)
                proceeds += sub_proceeds; sell_fee_total += sub_sell_fee; remaining = 0
                fills_for_avg.append(o2)
                print(log_line)
                break

        if remaining <= 0:
            break

    # if anything remains, close at last close
    if remaining > 0:
        ts2, o2,h2,l2,c2 = int(candles[-1][0]), float(candles[-1][1]), float(candles[-1][2]), float(candles[-1][3]), float(candles[-1][4])
        tstr = datetime.fromtimestamp(ts2, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sub_qty = remaining
        sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(c2, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, "TIME", sub_qty/qty)
        proceeds += sub_proceeds; sell_fee_total += sub_sell_fee; remaining = 0
        fills_for_avg.append(c2)
        print(log_line)
        last_ts = ts2

    pnl_usd = proceeds - invest - buy_fee_usd
    ret_pct = (pnl_usd / invest) * 100.0
    print(f"Proceeds: {fmt_usd(proceeds)}  | Buy fee: ${buy_fee_usd:.2f}  | Sell fee total: ${sell_fee_total:,.2f}")
    print(f"PNL: {fmt_usd(pnl_usd)}   Return: {ret_pct:.2f}%")

    # stats for batch parser
    hold_min = max(0, int((last_ts - ts) / 60))
    exit_raw_avg = (sum(fills_for_avg)/len(fills_for_avg)) if fills_for_avg else raw_entry
    ath_mult = (max_high / raw_entry) if raw_entry > 0 else 0.0
    print(f"STATS: net={net} entry_raw={raw_entry:.8f} exit_raw_avg={exit_raw_avg:.8f} max_high={max_high:.8f} "
          f"ath_mult={ath_mult:.6f} invest={invest} mode={mode} hold_min={hold_min} "
          f"pnl_usd={pnl_usd:.8f} pnl_token={(pnl_usd/raw_entry):.8f} exit_reason={'SL' if ret_pct<0 else 'TP'}")

if __name__ == "__main__":
    main()
