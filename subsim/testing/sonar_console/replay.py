"""Replay logging helpers for sonar console streams."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from .contracts import GroundTruthFrame, SonarConsoleFrame


def write_jsonl(
    *,
    path: str | Path,
    perceived_frames: Sequence[SonarConsoleFrame],
    truth_frames: Sequence[GroundTruthFrame],
    actions: Sequence[dict[str, Any]] | None = None,
) -> Path:
    if len(perceived_frames) != len(truth_frames):
        raise ValueError("Perceived and truth stream lengths must match")
    actions = actions or []
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for idx, (perceived, truth) in enumerate(zip(perceived_frames, truth_frames)):
            action_payload = actions[idx] if idx < len(actions) else {"tick": perceived.tick, "t": perceived.t, "action": {}}
            record = {
                "tick": perceived.tick,
                "t": perceived.t,
                "perceived": perceived.to_dict(),
                "truth": truth.to_dict(),
                "action": action_payload,
            }
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return out_path


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("Replay row must be an object")
            rows.append(payload)
    return rows


def parse_streams(rows: Iterable[dict[str, Any]]) -> tuple[list[SonarConsoleFrame], list[GroundTruthFrame], list[dict[str, Any]]]:
    perceived_frames: list[SonarConsoleFrame] = []
    truth_frames: list[GroundTruthFrame] = []
    actions: list[dict[str, Any]] = []
    for row in rows:
        perceived_frames.append(SonarConsoleFrame.from_dict(row["perceived"]))
        truth_frames.append(GroundTruthFrame.from_dict(row["truth"]))
        actions.append(dict(row.get("action", {})))
    return perceived_frames, truth_frames, actions


def replay_jsonl(path: str | Path) -> tuple[list[SonarConsoleFrame], list[GroundTruthFrame], list[dict[str, Any]]]:
    return parse_streams(load_jsonl(path))


__all__ = ["write_jsonl", "load_jsonl", "parse_streams", "replay_jsonl"]
