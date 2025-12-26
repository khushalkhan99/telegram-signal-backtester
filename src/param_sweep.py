import os, sys, subprocess
from collections import defaultdict, namedtuple, Counter

BATCH_FILE = os.path.join("src","batch_lines.txt")

# --- richer, still small grid ---
TP1_UPS = [5, 8, 12]      # %
TP1_SZS = [30, 50, 70]    # % of pos
TP2_UPS = [15]            # %
TP2_SZS = [70, 50, 30]    # % (ignored when 1-TP)
SLS     = [5, 8, 10]      # %
USE_ONE_TP = [True, False]  # try 1-TP vs 2-TP
MODE    = "realistic"

Strategy = namedtuple("Strategy", "one_tp tp1_up tp1_sz tp2_up tp2_sz sl_dn")

def clean_parts(line: str):
    line = line.strip()
    if not line or line.lstrip().startswith("#"):
        return None
    parts = [p.strip() for p in (line.split("|") if "|" in line else line.split(","))]
    parts = [p for p in parts if p]
    return parts

def run_one(parts, strat: Strategy, env):
    # Prepare command matching your simulators (MC if 10+ fields, partial if 9)
    if len(parts) == 9:
        mint, hhmm, invest, _tp1_up, _tp1_sz, _tp2_up, _tp2_sz, _sl_dn, mode = parts
        tp2_sz = 0 if strat.one_tp else strat.tp2_sz
        cmd = [
            sys.executable, os.path.join("src","single_trade_sim_partial.py"),
            mint, hhmm, str(invest),
            str(strat.tp1_up), str(strat.tp1_sz),
            str(TP2_UPS[0]), str(tp2_sz),
            str(strat.sl_dn), MODE
        ]
    elif len(parts) >= 10:
        mint, hhmm, mc, invest, _tp1_up, _tp1_sz, _tp2_up, _tp2_sz, _sl_dn, mode = parts[:10]
        tp2_sz = 0 if strat.one_tp else strat.tp2_sz
        cmd = [
            sys.executable, os.path.join("src","single_trade_sim_partial_mc.py"),
            mint, hhmm, mc, str(invest),
            str(strat.tp1_up), str(strat.tp1_sz),
            str(TP2_UPS[0]), str(tp2_sz),
            str(strat.sl_dn), MODE
        ]
    else:
        return None, None, "bad line shape"

    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (res.stdout or "") + (res.stderr or "")
    pnl_usd, reason, hold_min = None, None, None

    for line in out.splitlines():
        if line.startswith("PNL: $"):
            try:
                val = line.split("$",1)[1].split()[0].replace(",","")
                pnl_usd = float(val)
            except: pass
        if line.startswith("STATS:"):
            # parse exit_reason and hold_min from STATS line
            fields = dict(kv.split("=",1) for kv in line[len("STATS:"):].strip().split() if "=" in kv)
            reason = fields.get("exit_reason")
            hm = fields.get("hold_min")
            try: hold_min = int(hm) if hm is not None else None
            except: hold_min = None

    return pnl_usd, reason, hold_min

def main():
    # Read jobs
    try:
        raw = open(BATCH_FILE, "r", encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        print(f"missing {BATCH_FILE}"); sys.exit(2)
    jobs = [clean_parts(ln) for ln in raw]
    jobs = [p for p in jobs if p]
    if not jobs:
        print("no jobs in batch_lines.txt"); sys.exit(3)

    # Build strategies
    strategies = []
    for one in USE_ONE_TP:
        for t1 in TP1_UPS:
            for s1 in TP1_SZS:
                for sl in SLS:
                    # when 1-TP, tp2_sz is forced to 0 in run_one
                    for s2 in (TP2_SZS if not one else [0]):
                        strategies.append(Strategy(one, t1, s1, TP2_UPS[0], s2, sl))

    # Pick up env once (slippage/fees already set in your shell)
    env = os.environ.copy()

    print(f"Testing {len(strategies)} strategies across {len(jobs)} lines...\n")

    totals = defaultdict(float)
    reason_counts = defaultdict(Counter)
    holds = defaultdict(list)

    for strat in strategies:
        total = 0.0
        for parts in jobs:
            pnl_usd, reason, hold_min = run_one(parts, strat, env)
            if pnl_usd is None:
                continue
            total += pnl_usd
            if reason: reason_counts[strat][reason] += 1
            if hold_min is not None: holds[strat].append(hold_min)
        totals[strat] = total

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:3]
    print("\n=== TOP 3 STRATEGIES (by total PnL) ===")
    for i, (s, total) in enumerate(ranked, 1):
        rc = reason_counts[s]
        avg_hold = (sum(holds[s])/len(holds[s])) if holds[s] else 0
        tp_mode = "1-TP" if s.one_tp else "2-TP"
        print(f"{i}. {tp_mode}  tp1={s.tp1_up}%/{s.tp1_sz}%  tp2={s.tp2_up}%/{s.tp2_sz}%  sl={s.sl_dn}%"
              f"  --> total ${total:,.2f} | exits {dict(rc)} | avg_hold {avg_hold:.0f}m")

if __name__ == "__main__":
    main()
