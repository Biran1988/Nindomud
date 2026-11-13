"""Diagnostic runner for the inherited, sequential legacy smoke suite.

Unlike test_smoke.py's first-exception exit, this runs every explicitly
invoked scenario and records each exception. It is deliberately diagnostic,
not an alternative pass/fail gate. Earlier failures may affect later cases.
This script never reads or deletes a live game data directory.
"""
import ast
import contextlib
import importlib
import io
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    smoke = importlib.import_module("test_smoke")
    source = Path(smoke.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = []
    for stmt in tree.body:
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "__name__" and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"):
            continue
        for expression in stmt.body:
            if (isinstance(expression, ast.Expr) and isinstance(expression.value, ast.Call)
                    and isinstance(expression.value.func, ast.Name)
                    and (expression.value.func.id == "main"
                         or expression.value.func.id.startswith("test_"))):
                calls.append(expression.value.func.id)
    failures = []
    passed = 0
    for name in calls:
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                getattr(smoke, name)()
            passed += 1
        except Exception as error:
            last = traceback.extract_tb(error.__traceback__)[-1]
            failures.append((name, type(error).__name__, str(error).replace("\n", " ")[:180],
                             f"{Path(last.filename).name}:{last.lineno}"))
            print(f"FAIL {name}: {type(error).__name__} {str(error)[:150]} ({last.filename}:{last.lineno})")
    print(f"Legacy smoke diagnostics: {passed} passed, {len(failures)} failed, "
          f"{len(calls)} executed; failures may cascade due to shared fixture state.")
    if not calls:
        raise RuntimeError("Legacy smoke runner found no top-level scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
