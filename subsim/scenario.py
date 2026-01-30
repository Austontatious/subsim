"""Scenario generation and difficulty presets."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .engine.contacts import Contact
from .config import MAX_WORLD_EXTENT_M


@dataclass(frozen=True)
class DifficultyPreset:
    name: str
    enemy_min: int
    enemy_max: int
    merchant_chance: float
    sensor_noise: float
    enemy_aggression: float
    time_limit: Optional[float]
    spawn_radius: float


DIFFICULTY: Dict[str, DifficultyPreset] = {
    "easy": DifficultyPreset(
        name="easy",
        enemy_min=1,
        enemy_max=1,
        merchant_chance=0.6,
        sensor_noise=0.04,
        enemy_aggression=0.15,
        time_limit=None,
        spawn_radius=0.45,
    ),
    "normal": DifficultyPreset(
        name="normal",
        enemy_min=1,
        enemy_max=2,
        merchant_chance=0.4,
        sensor_noise=0.12,
        enemy_aggression=0.45,
        time_limit=None,
        spawn_radius=0.6,
    ),
    "hard": DifficultyPreset(
        name="hard",
        enemy_min=2,
        enemy_max=3,
        merchant_chance=0.25,
        sensor_noise=0.2,
        enemy_aggression=0.75,
        time_limit=420.0,
        spawn_radius=0.8,
    ),
}


@dataclass
class Scenario:
    seed: int
    difficulty: DifficultyPreset
    contacts: List[Contact]
    objective_branch: str
    time_limit: Optional[float]


def generate_skirmish(seed: int, difficulty: DifficultyPreset) -> Scenario:
    rng = random.Random(seed)
    enemy_count = rng.randint(difficulty.enemy_min, difficulty.enemy_max)
    contacts: List[Contact] = []

    for idx in range(enemy_count):
        radius = difficulty.spawn_radius
        x = rng.uniform(-radius, radius) * MAX_WORLD_EXTENT_M
        y = rng.uniform(-radius, radius) * MAX_WORLD_EXTENT_M
        depth = rng.uniform(-240.0, -90.0)
        heading = rng.uniform(0.0, 360.0)
        speed = rng.uniform(2.5, 4.5) + difficulty.enemy_aggression * 1.5
        noise = 0.35 + difficulty.enemy_aggression * 0.25
        ident = f"enemy-{idx+1}"
        contacts.append(
            Contact(
                ident=ident,
                kind="hunter",
                position=(x, y, depth),
                heading_deg=heading,
                speed_mps=speed,
                depth_m=depth,
                noise=noise,
            )
        )

    if rng.random() < difficulty.merchant_chance:
        radius = min(0.9, difficulty.spawn_radius + 0.1)
        x = rng.uniform(-radius, radius) * MAX_WORLD_EXTENT_M
        y = rng.uniform(-radius, radius) * MAX_WORLD_EXTENT_M
        depth = rng.uniform(-160.0, -80.0)
        heading = rng.uniform(0.0, 360.0)
        speed = rng.uniform(1.8, 3.0)
        contacts.append(
            Contact(
                ident="merchant",
                kind="merchant",
                position=(x, y, depth),
                heading_deg=heading,
                speed_mps=speed,
                depth_m=depth,
                noise=0.25,
            )
        )

    objective_branch = "engage" if enemy_count > 0 else "evade"
    return Scenario(
        seed=seed,
        difficulty=difficulty,
        contacts=contacts,
        objective_branch=objective_branch,
        time_limit=difficulty.time_limit,
    )


__all__ = ["Scenario", "DifficultyPreset", "DIFFICULTY", "generate_skirmish"]
