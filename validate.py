#!/usr/bin/env python3
"""Repository guard for SubSim."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List


ROOT = Path(__file__).parent


@dataclass
class Check:
    name: str
    func: Callable[[], bool]


def iter_source_files() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        if path.name == "validate.py":
            continue
        if path.parts and ".venv" in path.parts:
            continue
        yield path


def check_banned_phrases() -> bool:
    banned = ["The provided code", "No changes need"]
    ok = True
    for path in iter_source_files():
        text = path.read_text(encoding="utf8", errors="ignore")
        for phrase in banned:
            if phrase in text:
                print(f"  ✗ banned phrase in {path}")
                ok = False
    return ok


def check_ast() -> bool:
    ok = True
    for path in iter_source_files():
        try:
            ast.parse(path.read_text(encoding="utf8"))
        except SyntaxError as exc:
            print(f"  ✗ AST error in {path}: {exc}")
            ok = False
    return ok


def check_setup_absent() -> bool:
    if (ROOT / "setup.py").exists():
        print("  ✗ setup.py should not exist")
        return False
    return True


def check_headless() -> bool:
    env = os.environ.copy()
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    env.setdefault("PYGLET_HEADLESS", "true")
    cmd = [sys.executable, "-m", "subsim", "--headless", "--duration", "1.0"]
    try:
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  ✗ headless run failed: {exc}")
        return False


def check_assets() -> bool:
    from subsim.assets import ensure_assets

    assets = ensure_assets(ROOT / "assets" / "sfx")
    ok = True
    for mapping in assets.values():
        for wav in mapping.values():
            if not wav.exists() or wav.stat().st_size == 0:
                print(f"  ✗ missing asset {wav}")
                ok = False
    return ok


def check_pytest() -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    try:
        subprocess.run(cmd, cwd=ROOT, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  ✗ pytest failed: {exc}")
        return False


def run_checks(checks: List[Check]) -> bool:
    all_ok = True
    for check in checks:
        print(f"▶ {check.name}")
        if check.func():
            print("  ✅ ok")
        else:
            print("  ❌ failed")
            all_ok = False
    return all_ok


def main() -> None:
    checks = [
        Check("banned phrases", check_banned_phrases),
        Check("AST parse", check_ast),
        Check("setup.py absent", check_setup_absent),
        Check("headless smoke", check_headless),
        Check("assets", check_assets),
        Check("pytest", check_pytest),
    ]
    ok = run_checks(checks)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
