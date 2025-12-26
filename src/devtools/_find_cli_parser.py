import os, ast, textwrap, sys

ROOT = os.path.join(os.getcwd(), "src")
found = []

def scan_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src, filename=path)
    except Exception as e:
        return

    # track argparse alias (e.g., "import argparse as ap")
    argparse_names = set(["argparse"])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "argparse":
                    argparse_names.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.module == "argparse":
            # from argparse import ArgumentParser as AP
            for alias in node.names:
                if alias.name == "ArgumentParser":
                    argparse_names.add(alias.asname or alias.name)

    parser_vars = set()

    # find parser = argparse.ArgumentParser(...)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            # argparse.ArgumentParser(...)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.attr == "ArgumentParser" and func.value.id in argparse_names:
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            parser_vars.add(t.id)
            # ArgumentParser(...) when imported directly
            if isinstance(func, ast.Name) and func.id in argparse_names:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        parser_vars.add(t.id)

    if not parser_vars:
        return

    adds = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # parser.add_argument(...)
            if isinstance(node.func.value, ast.Name) and node.func.attr == "add_argument":
                if node.func.value.id in parser_vars:
                    # extract first arg (flag) if present
                    flag = None
                    if node.args:
                        a0 = node.args[0]
                        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                            flag = a0.value
                    # or check keywords for 'dest'
                    dest = None
                    for kw in node.keywords or []:
                        if kw.arg == "dest" and isinstance(kw.value, ast.Constant):
                            dest = kw.value.value
                    adds.append((getattr(node, "lineno", -1), flag, dest))

    found.append((path, sorted(list(parser_vars)), sorted(adds, key=lambda x: x[0])))

for dirpath, dirnames, filenames in os.walk(ROOT):
    for fn in filenames:
        if fn.endswith(".py"):
            scan_file(os.path.join(dirpath, fn))

if not found:
    print("NO argparse parser found in src/*.py")
    sys.exit(0)

print("=== argparse parsers found ===")
for path, parsers, adds in found:
    print(f"\nFILE: {os.path.relpath(path)}")
    print(f"parser vars: {parsers}")
    if adds:
        print("add_argument calls:")
        for ln, flag, dest in adds:
            f = flag or ""
            d = (f" dest={dest}" if dest else "")
            print(f"  - line {ln}: {f}{d}")
    else:
        print("add_argument calls: (none)")
