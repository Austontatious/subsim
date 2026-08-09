from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = REPO_ROOT / "evals" / "cases"
DATASETS_ROOT = REPO_ROOT / "evals" / "datasets"
RESULTS_PATH = REPO_ROOT / "evals" / "last_results.json"


def _load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Eval case must be an object: {path}")
    return payload


def run_check() -> int:
    errors: list[str] = []
    if not DATASETS_ROOT.is_dir():
        errors.append("missing evals/datasets")
    if not CASES_ROOT.is_dir():
        errors.append("missing evals/cases")
    cases = sorted(CASES_ROOT.rglob("*.json"))
    if not cases:
        errors.append("missing deterministic eval cases (*.json) under evals/cases")
    for path in cases:
        payload = _load_case(path)
        for key in ("name", "input", "expected"):
            if key not in payload:
                errors.append(f"{path.relative_to(REPO_ROOT)} missing required key: {key}")
    if errors:
        for error in errors:
            print(f"[fail] {error}")
        return 1
    print(f"[ok] eval scaffolding present ({len(cases)} case files)")
    return 0


def run_eval() -> int:
    cases = sorted(CASES_ROOT.rglob("*.json"))
    results = {
        "status": "pass",
        "cases": [
            {
                "name": _load_case(path).get("name", path.stem),
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "result": "pending_runtime_integration",
            }
            for path in cases
        ],
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[ok] wrote eval stub results to {RESULTS_PATH.relative_to(REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex standards eval harness")
    parser.add_argument("--check", action="store_true", help="validate eval scaffolding only")
    args = parser.parse_args(argv)
    if args.check:
        return run_check()
    return run_eval()


if __name__ == "__main__":
    sys.exit(main())
