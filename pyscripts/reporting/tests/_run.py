"""Minimal test runner — pytest-compatible names but no pytest dependency.

Usage: `python -m pyscripts.reporting.tests._run`.
"""

import importlib
import inspect
import pkgutil
import sys
import traceback


def _iter_tests(pkg_name: str):
    pkg = importlib.import_module(pkg_name)
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        if not mod_info.name.startswith("test_"):
            continue
        mod = importlib.import_module(f"{pkg_name}.{mod_info.name}")
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("test_") and fn.__module__ == mod.__name__:
                yield mod.__name__, name, fn


def main() -> int:
    failures = []
    n = 0
    for mod_name, fn_name, fn in _iter_tests("pyscripts.reporting.tests"):
        n += 1
        try:
            fn()
            sys.stdout.write(".")
            sys.stdout.flush()
        except Exception:
            sys.stdout.write("F")
            sys.stdout.flush()
            failures.append((mod_name, fn_name, traceback.format_exc()))
    sys.stdout.write("\n")
    for mod_name, fn_name, tb in failures:
        print(f"\nFAIL {mod_name}.{fn_name}\n{tb}")
    print(f"{n - len(failures)}/{n} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
