import io, os, re, shutil, sys

PATH = os.path.join("src","single_trade_sim_partial_mc.py")
BAK  = PATH + ".bak"

# 1) restore from backup if present (to undo the bad patch)
if os.path.exists(BAK):
    shutil.copyfile(BAK, PATH)
    print("[restore] reverted to backup")

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()
orig = src

# 2) inject helpers (env config + buy/sell helpers) just after the first import block
helpers = '''
import os

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
'''.lstrip()

# insert helpers right after the first block of imports
m = re.search(r"(^import .+?$[\r\n]+(?:from .+?$[\r\n]+|import .+?$[\r\n]+)*)", src, re.MULTILINE)
if m and "def _cfg(" not in src:
    insert_at = m.end()
    src = src[:insert_at] + helpers + src[insert_at:]

# 3) patch BUY leg usage: replace the 2 lines that compute paid_entry/qty + the entry print
src = re.sub(
    r"paid_entry,\s*buy_fee\s*=\s*apply_buy_costs\([^\n]+\)\s*\r?\n\s*qty\s*=\s*invest\s*/\s*paid_entry",
    "slip, slip_mode, slip_side, buy_fee_frac, sell_fee_frac = _cfg()\nqty, paid_entry, buy_fee_usd, buy_log = execute_buy(raw_entry, invest, buy_fee_frac, slip, slip_mode, slip_side)",
    src
)

src = re.sub(
    r'print\(\s*f"Entry\s*@\s*\{e_dt\}\s*[^"]*paid\(3%\+\$1\):\s*\{paid_entry:.*?qty:\{qty:.*?"\s*\)',
    'print(f"Entry @ {e_dt}  {buy_log}  buy_fee:${buy_fee_usd:.2f} [{how}]")',
    src
)

# 4) patch SELL loop: replace proceeds accumulation & fee counting
# First ensure we start with proceeds/sell_fee_total init
src = re.sub(
    r"proceeds\s*=\s*0\.0;\s*sell_fee_total\s*=\s*0\.0",
    "proceeds = 0.0\nsell_fee_total = 0.0",
    src
)

# Replace the body that used recv_px and +1.0 fees
src = re.sub(
    r"for\s*\(\s*tstr,\s*raw_px,\s*frac,\s*reason\s*\)\s*in\s*fills:\s*\r?\n\s*sub_qty\s*=\s*qty\s*\*\s*frac\s*\r?\n\s*proceeds\s*\+=\s*sub_qty\s*\*\s*recv_px\s*\r?\n\s*sell_fee_total\s*\+=\s*1\.0",
    "for (tstr, raw_px, frac, reason) in fills:\n    sub_qty = qty * frac\n    sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(raw_px, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, reason, frac)\n    proceeds += sub_proceeds\n    sell_fee_total += sub_sell_fee\n    print(log_line)",
    src
)

# 5) patch Proceeds/PNL prints under the loop
src = re.sub(
    r'print\(\s*f"Proceeds:\s*\$\{proceeds:,[^}]+\}\s*\|\s*Buy fee:\s*\$1\.00\s*\|\s*Sell fee count:\s*\{\s*len\(fills\)\s*\}\s*\(\$\s*\{\s*len\(fills\):\.2f\}\s*\)\s*"\s*\)',
    'print(f"Proceeds: ${proceeds:,.2f}  | Buy fee: ${buy_fee_usd:.2f}  | Sell fee total: ${sell_fee_total:,.2f}")',
    src
)

# 6) ensure PNL uses new math and print matches
src = re.sub(
    r"pnl_usd\s*=\s*proceeds\s*-\s*invest\s*-\s*buy_fee\s*-\s*sell_fee_total",
    "pnl_usd = proceeds - invest - buy_fee_usd",
    src
)
src = re.sub(
    r'print\(\s*f"PNL:\s*\$\{pnl_usd:,[^}]+\}\s*Return:\s*\{\s*ret_pct:.[^}]+\}%"\s*\)',
    'print(f"PNL: ${pnl_usd:,.2f}   Return: {ret_pct:.2f}%")',
    src
)

changed = (src != orig)
with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("[ok] patched single_trade_sim_partial_mc.py" if changed else "[info] no changes (maybe already patched)")
