# src/_audit_src.py
import ast, os, py_compile, sys, re
SRC = os.path.dirname(__file__)
rows = []
mains, argparsers, compile_errs = [], [], []
core, devtools, debug = [], [], []

def bucket(fn):
    n = os.path.basename(fn)
    if n in {
        "batch_sim.py","single_trade_sim.py","single_trade_sim_partial.py",
        "single_trade_sim_partial_mc.py","ai_strategy_finder.py","gt_ohlvc.py",
        "gt_entry_from_time.py","gt_find_pools.py","report_from_csv.py","param_sweep.py"
    }: return "core"
    if re.search(r"(externalize|replace_build|reset_build|inspect_build|rewrite_try|minutemap|matched|tz|strict|widen|relax|mc_)", n):
        return "dev"
    if re.search(r"(dump_|fix_|surgical_|patch_|demo|test_|\.(bak|old)$)", n):
        return "debug"
    return "other"

for root,_,files in os.walk(SRC):
    for f in files:
        if not f.endswith(".py"): continue
        path = os.path.join(root,f)
        # compile check
        try:
            py_compile.compile(path, doraise=True)
        except Exception as e:
            compile_errs.append((f, str(e).splitlines()[-1]))
        # AST scan
        with open(path, "rb") as fh:
            src = fh.read()
        try:
            tree = ast.parse(src, filename=f)
        except Exception:
            continue
        text = src.decode("utf-8", "ignore")
        if '__main__' in text:
            mains.append(f)
        if re.search(r"\bargparse\b", text):
            argparsers.append(f)
        b = bucket(f)
        if b=="core": core.append(f)
        elif b=="dev": devtools.append(f)
        elif b=="debug": debug.append(f)
rows.append(("CORE", sorted(core)))
rows.append(("DEVTOOLS", sorted(devtools)))
rows.append(("DEBUG/ONE-OFF", sorted(debug)))
print("=== COMPILE ERRORS ===")
if not compile_errs: print("None ✅")
else:
    for f,msg in compile_errs: print(f"- {f}: {msg}")
print("\n=== RUNNABLE (has __main__) ===")
print("\n".join(sorted(mains)) or "None")
print("\n=== USES argparse (likely CLI) ===")
print("\n".join(sorted(argparsers)) or "None")
print("\n=== BUCKETS ===")
for title, lst in rows:
    print(f"\n[{title}] ({len(lst)})")
    for n in lst: print(" ", n)
