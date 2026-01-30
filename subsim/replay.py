"""Trace writer + golden replay utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .config import FRAME_DT
from .game import Game


@dataclass
class CompareResult:
    ok: bool
    message: str


def load_trace(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_trace(*, seed: int, difficulty: str, ticks: int) -> Dict[str, Any]:
    game = Game(
        headless=True,
        seed=seed,
        difficulty=difficulty,
        mode_override="skirmish",
        trace_enabled=True,
    )
    game.run(max_ticks=ticks)
    payload = {
        "meta": {
            "seed": seed,
            "difficulty": difficulty,
            "tick_rate": 1.0 / FRAME_DT,
            "ticks": ticks,
        },
        "trace": game.trace,
    }
    return payload


def compare_traces(expected: Dict[str, Any], actual: Dict[str, Any], tol: float = 1e-3) -> CompareResult:
    exp = expected.get("trace", [])
    act = actual.get("trace", [])
    if len(exp) != len(act):
        return CompareResult(False, f"trace length mismatch: {len(act)} != {len(exp)}")

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= tol

    for idx, (e, a) in enumerate(zip(exp, act)):
        if e.get("action") != a.get("action"):
            return CompareResult(False, f"action mismatch at tick {idx}")
        if e.get("objective") != a.get("objective"):
            return CompareResult(False, f"objective mismatch at tick {idx}")
        for key in ("heading", "speed", "depth"):
            ev = e["player"][key]
            av = a["player"][key]
            if isinstance(ev, (int, float)) and isinstance(av, (int, float)):
                if not close(ev, av):
                    return CompareResult(False, f"player.{key} mismatch at tick {idx}")
        e_contacts = e.get("contacts", [])
        a_contacts = a.get("contacts", [])
        if len(e_contacts) != len(a_contacts):
            return CompareResult(False, f"contact count mismatch at tick {idx}")
        for cexp, cact in zip(e_contacts, a_contacts):
            if cexp.get("id") != cact.get("id"):
                return CompareResult(False, f"contact id mismatch at tick {idx}")
            for key in ("bearing", "distance", "confidence", "classify"):
                ev = cexp.get(key, 0.0)
                av = cact.get(key, 0.0)
                if not close(ev, av):
                    return CompareResult(False, f"contact {key} mismatch at tick {idx}")

        if len(e.get("events", [])) != len(a.get("events", [])):
            return CompareResult(False, f"event count mismatch at tick {idx}")
        for ev, av in zip(e.get("events", []), a.get("events", [])):
            if ev.get("type") != av.get("type"):
                return CompareResult(False, f"event type mismatch at tick {idx}")
            for key in ("bearing", "distance"):
                if ev.get(key) is None or av.get(key) is None:
                    continue
                if not close(ev.get(key, 0.0), av.get(key, 0.0)):
                    return CompareResult(False, f"event {key} mismatch at tick {idx}")
    return CompareResult(True, "ok")


def replay_trace(path: str | Path) -> bool:
    expected = load_trace(path)
    meta = expected.get("meta", {})
    seed = meta.get("seed", 0)
    difficulty = meta.get("difficulty", "normal")
    ticks = meta.get("ticks", 0)
    actual = run_trace(seed=seed, difficulty=difficulty, ticks=ticks)
    result = compare_traces(expected, actual)
    if not result.ok:
        print(result.message)
    return result.ok


__all__ = ["run_trace", "load_trace", "compare_traces", "replay_trace"]
