import io, os, re, sys, shutil

ROOT = os.getcwd()
FILES = [
    os.path.join("src", "single_trade_sim_partial.py"),
    os.path.join("src", "single_trade_sim_partial_mc.py"),
]

# helpers to patch sections by regex anchors
def patch_file(path, patterns_replacements):
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    orig = src
    for desc, pattern, repl, flags in patterns_replacements:
        m = re.search(pattern, src, flags)
        if not m:
            print(f"[WARN] pattern not found for: {desc} in {path}")
            continue
        src = src[:m.start()] + repl + src[m.end():]
        print(f"[OK] patched: {desc} in {path}")
    if src != orig:
        # backup
        bak = path + ".bak"
        if not os.path.exists(bak):
            shutil.copyfile(path, bak)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
        return True
    return False

# common code we inject (helpers + env config)
HELPERS_BLOCK = r"""
import os

def _cfg():
    slip = float(os.getenv("TB_SLIP", "0"))
    slip_mode = os.getenv("TB_SLIP_MODE", "amount")      # 'price' | 'amount'
    slip_side = os.getenv("TB_SLIP_SIDE", "sell")        # 'both' | 'buy' | 'sell'
    buy_fee = float(os.getenv("TB_BUY_FEE", "0.01"))     # fraction
    sell_fee = float(os.getenv("TB_SELL_FEE", "0.01"))   # fraction
    return slip, slip_mode, slip_side, buy_fee, sell_fee

def execute_buy(raw_price, invest_usd, buy_fee, slip, slip_mode, slip_side):
    \"\"\"Return qty, paid_entry_px, buy_fee_usd, log_str\"\"\"
    buy_fee_usd = invest_usd * buy_fee
    cash_after_fee = invest_usd - buy_fee_usd
    if slip_side in ("both","buy"):
        if slip_mode == "price":
            paid_entry_px = raw_price * (1 + slip)
            qty = cash_after_fee / paid_entry_px
            log = f"raw:{raw_price:.8f}  paid(price,{int(slip*100)}%+fee): {paid_entry_px:.8f}  qty:{qty:.8f}"
            return qty, paid_entry_px, buy_fee_usd, log
        else:  # amount
            eff_cash = cash_after_fee * (1 - slip)
            qty = eff_cash / raw_price
            log = f"raw:{raw_price:.8f}  paid(amount,{int(slip*100)}%+fee) cash:{eff_cash:.2f}  qty:{qty:.8f}"
            return qty, raw_price, buy_fee_usd, log
    # no slippage on buy
    qty = cash_after_fee / raw_price
    log = f"raw:{raw_price:.8f}  paid(fee only): {raw_price:.8f}  qty:{qty:.8f}"
    return qty, raw_price, buy_fee_usd, log
"""

# sell helper for non-MC (single fill)
SELL_HELPER_SINGLE = r"""
def execute_sell(raw_price, qty, sell_fee, slip, slip_mode, slip_side):
    \"\"\"Return proceeds_usd, recv_price_for_log, sell_fee_usd, log_str\"\"\"
    gross = qty * raw_price
    sell_fee_usd = gross * sell_fee
    after_fee = gross - sell_fee_usd

    if slip_side in ("both","sell"):
        if slip_mode == "price":
            recv_px = raw_price * (1 - slip)
            proceeds = qty * recv_px * (1 - sell_fee)  # equivalent to fee on price
            log = f"raw:{raw_price:.8f}  recv(price,{int(slip*100)}%):{recv_px:.8f}"
            return proceeds, recv_px, sell_fee_usd, log
        else:  # amount
            proceeds = after_fee * (1 - slip)
            log = f"raw:{raw_price:.8f}  recv(amount,{int(slip*100)}%)"
            return proceeds, raw_price, sell_fee_usd, log
    # no slippage on sell
    proceeds = after_fee
    log = f"raw:{raw_price:.8f}  recv(no slip)"
    return proceeds, raw_price, sell_fee_usd, log
"""

# sell helper for MC (multiple fills)
SELL_HELPER_MC = r"""
def execute_sell_fill(raw_price, sub_qty, sell_fee, slip, slip_mode, slip_side, tstr, reason, frac):
    \"\"\"Return sub_proceeds, sub_sell_fee_usd, log_line\"\"\"
    sub_gross = sub_qty * raw_price
    sub_sell_fee = sub_gross * sell_fee
    after_fee = sub_gross - sub_sell_fee

    if slip_side in ("both","sell"):
        if slip_mode == "price":
            recv_px = raw_price * (1 - slip)
            sub_proceeds = sub_qty * recv_px * (1 - sell_fee)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(price,{int(slip*100)}%):{recv_px:.8f}  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
        else:  # amount
            sub_proceeds = after_fee * (1 - slip)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(amount,{int(slip*100)}%)  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
    # no slippage on sell
    sub_proceeds = after_fee
    log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(no slip)  part:{frac*100:.1f}%"
    return sub_proceeds, sub_sell_fee, log
"""

def patch_single(path):
    patterns = []

    # 1) replace old buy/sell helpers with our env-driven helpers
    patterns.append((
        "replace old buy/sell helpers",
        r"def\s+apply_buy_costs\([^\)]*\):[\s\S]*?def\s+apply_sell_costs\([^\)]*\):[\s\S]*?(?:\n|\r\n)",
        HELPERS_BLOCK + SELL_HELPER_SINGLE + "\n",
        re.DOTALL
    ))

    # 2) replace buy usage & entry print
    patterns.append((
        "replace buy leg + entry print",
        r"paid_entry,\s*buy_fee\s*=\s*apply_buy_costs\([^\n]+\)\s*\n\s*qty\s*=\s*invest\s*/\s*paid_entry\s*[\s\S]*?print\(\s*f\"Entry\s*@\s*\{e_dt\}[^\n]+\"\s*\)",
        r"""slip, slip_mode, slip_side, buy_fee_frac, sell_fee_frac = _cfg()
qty, paid_entry, buy_fee_usd, buy_log = execute_buy(raw_entry, invest, buy_fee_frac, slip, slip_mode, slip_side)
print(f"Entry @ {e_dt}  {buy_log}  buy_fee:${buy_fee_usd:.2f}")""",
        re.DOTALL
    ))

    # 3) replace sell usage + proceeds/pnl prints
    patterns.append((
        "replace sell leg + prints",
        r"exit_recv,\s*sell_fee\s*=\s*apply_sell_costs\([^\n]+\)\s*\n\s*proceeds\s*=\s*qty\s*\*\s*exit_recv\s*\n\s*pnl_usd\s*=\s*proceeds\s*-\s*invest\s*-\s*buy_fee\s*-\s*sell_fee\s*[\s\S]*?print\(\s*f\"PNL:[^\n]+\"\s*\)\s*\n\s*print\(\s*f\"STATS:[^\n]+\"\s*\)",
        r"""proceeds, recv_px, sell_fee_usd, sell_log = execute_sell(exit_raw, qty, sell_fee_frac, slip, slip_mode, slip_side)
pnl_usd = proceeds - invest - buy_fee_usd
ret_pct = (pnl_usd / invest) * 100.0

print(f"- Exit {exit_reason:<14} @ {x_dt}  {sell_log}  part:100.0%")
print(f"Proceeds: ${proceeds:,.2f}  | Buy fee: ${buy_fee_usd:.2f}  | Sell fee: ${sell_fee_usd:.2f}")
print(f"PNL: ${pnl_usd:,.2f}   Return: {ret_pct:.2f}%")
print(f"STATS: net={net} entry_raw={raw_entry:.8f} exit_raw_avg={exit_raw:.8f} max_high={max_high:.8f} ath_mult={ath_mult:.6f} invest={invest} mode={mode} hold_min={hold_min} pnl_usd={pnl_usd:.8f} pnl_token={(pnl_usd/raw_entry):.8f} exit_reason={exit_reason}")""",
        re.DOTALL
    ))
    return patch_file(path, patterns)

def patch_mc(path):
    patterns = []

    # 1) replace helpers
    patterns.append((
        "replace old buy/sell helpers (mc)",
        r"def\s+apply_buy_costs\([^\)]*\):[^\n]*\n\s*def\s+apply_sell_costs\([^\)]*\):[^\n]*\n",
        HELPERS_BLOCK + SELL_HELPER_MC + "\n",
        re.DOTALL
    ))

    # 2) replace buy usage & entry print
    patterns.append((
        "replace buy leg + entry print (mc)",
        r"paid_entry,\s*buy_fee\s*=\s*apply_buy_costs\([^\n]+\)\s*\n\s*qty\s*=\s*invest\s*/\s*paid_entry\s*[\s\S]*?print\(\s*f\"Entry\s*@\s*\{e_dt\}[^\n]+\"\s*\)",
        r"""slip, slip_mode, slip_side, buy_fee_frac, sell_fee_frac = _cfg()
qty, paid_entry, buy_fee_usd, buy_log = execute_buy(raw_entry, invest, buy_fee_frac, slip, slip_mode, slip_side)
print(f"Entry @ {e_dt}  {buy_log}  buy_fee:${buy_fee_usd:.2f} [{how}]")""",
        re.DOTALL
    ))

    # 3) replace sell loop + prints
    patterns.append((
        "replace sell loop + prints (mc)",
        r"proceeds\s*=\s*0\.0;\s*sell_fee_total\s*=\s*0\.0[\s\S]*?for\s*\([^)]+\)\s*in\s*fills:\s*\n\s*sub_qty\s*=\s*qty\s*\*\s*frac\s*\n\s*proceeds\s*\+=\s*sub_qty\s*\*\s*recv_px\s*\n\s*sell_fee_total\s*\+=\s*1\.0[\s\S]*?print\(\s*f\"Proceeds:[^\n]+\"\s*\)\s*\n\s*print\(\s*f\"PNL:[^\n]+\"\s*\)",
        r"""proceeds = 0.0
sell_fee_total = 0.0

for (tstr, raw_px, frac, reason) in fills:
    sub_qty = qty * frac
    sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(raw_px, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, reason, frac)
    proceeds += sub_proceeds
    sell_fee_total += sub_sell_fee
    print(log_line)

pnl_usd = proceeds - invest - buy_fee_usd
ret_pct = (pnl_usd / invest) * 100.0

print(f"Proceeds: ${proceeds:,.2f}  | Buy fee: ${buy_fee_usd:.2f}  | Sell fee total: ${sell_fee_total:,.2f}")
print(f"PNL: ${pnl_usd:,.2f}   Return: {ret_pct:.2f}%")""",
        re.DOTALL
    ))
    return patch_file(path, patterns)

any_changed = False
for p in FILES:
    if not os.path.exists(p):
        print(f"[SKIP] missing: {p}")
        continue
    if p.endswith("_mc.py"):
        any_changed |= patch_mc(p)
    else:
        any_changed |= patch_single(p)

if not any_changed:
    print("No changes applied (patterns not found or already patched).")
else:
    print("Patching complete. Backups saved as .bak")
