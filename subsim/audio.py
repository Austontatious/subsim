"""Audio mixing and playback helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

from .assets import ensure_assets
from .config import AUDIO_SAMPLE_RATE
from .events import (
    GameEvent,
    EVENT_PING,
    EVENT_TORP_LAUNCH,
    EVENT_DETONATION,
    EVENT_TORP_HIT,
    EVENT_UI_CONFIRM,
    EVENT_UI_ALERT,
    EVENT_FIRE_SOLUTION_START,
    EVENT_FIRE_SOLUTION_READY,
    EVENT_FIRE_SOLUTION_MISS,
    EVENT_TORP_IN_WATER,
)

try:  # pragma: no cover - optional dependency
    import pygame

    _HAVE_PYGAME = True
except Exception:  # pragma: no cover
    pygame = None  # type: ignore
    _HAVE_PYGAME = False


def _db_to_gain(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def _equal_power_pan(azimuth_rad: float) -> tuple[float, float]:
    az = max(-math.pi, min(math.pi, azimuth_rad))
    left = math.sqrt(0.5 * (1.0 + math.cos(az)))
    right = math.sqrt(0.5 * (1.0 - math.cos(az)))
    return left, right


def _pan_from_bearing(bearing_deg: float) -> tuple[float, float]:
    return _equal_power_pan(math.radians(bearing_deg))


@dataclass
class _Channel:
    left: float = 0.0
    right: float = 0.0
    channel: Optional["pygame.mixer.Channel"] = None

    def set_volume(self, left: float, right: float) -> None:
        self.left, self.right = left, right
        if self.channel:
            self.channel.set_volume(left, right)


class AudioEngine:
    """High-level audio driver that mixes contact loops and earcons."""

    def __init__(self, headless: bool = False) -> None:
        self.assets = ensure_assets()
        self.headless = headless or not _HAVE_PYGAME
        self.master_gain = 1.0
        self.channels: Dict[str, _Channel] = {}
        self.sounds: Dict[str, "pygame.mixer.Sound"] = {}
        self.duck_gain = 1.0
        self._duck_timer = 0.0
        self._duck_duration = 0.6
        self._duck_min_gain = 0.45
        self._duck_release = 0.35

        if not self.headless and pygame is not None:
            try:
                pygame.mixer.pre_init(AUDIO_SAMPLE_RATE, size=-16, channels=2, buffer=512)
                pygame.mixer.init()
                for name, variants in self.assets.items():
                    wav = variants["clean"]
                    self.sounds[name] = pygame.mixer.Sound(wav.as_posix())
            except Exception:
                # Fallback to silent mode if audio init fails.
                self.headless = True
                self.sounds = {}

    def play_loop(self, asset_name: str, key: str) -> None:
        if key in self.channels:
            return
        chan = _Channel()
        if not self.headless and pygame is not None:
            handle = pygame.mixer.find_channel()
            if handle is None:
                handle = pygame.mixer.Channel(pygame.mixer.get_num_channels() - 1)
            sound = self.sounds.get(asset_name)
            if sound:
                handle.play(sound, loops=-1)
            chan.channel = handle
        self.channels[key] = chan

    def stop_loop(self, key: str) -> None:
        channel = self.channels.pop(key, None)
        if channel and channel.channel:
            channel.channel.fadeout(150)

    def earcon(self, asset_name: str, gain_db: float = 0.0) -> None:
        if self.headless or pygame is None:
            return
        sound = self.sounds.get(asset_name)
        if sound is None:
            return
        gain = self.master_gain * _db_to_gain(gain_db)
        sound.set_volume(gain)
        sound.play()

    def set_master_volume(self, db: float) -> None:
        self.master_gain = max(0.0, min(1.0, _db_to_gain(db)))
        for ch in self.channels.values():
            ch.set_volume(ch.left * self.master_gain * self.duck_gain, ch.right * self.master_gain * self.duck_gain)

    def set_contact_mix(
        self,
        key: str,
        *,
        azimuth_deg: float,
        distance_m: float,
        confidence: float,
        occlusion_layers: int,
        own_noise: float,
    ) -> None:
        channel = self.channels.get(key)
        if not channel:
            return
        d0 = 450.0
        gain = 1.0 / (1.0 + (distance_m / d0) ** 2)
        gain *= max(0.0, min(1.0, confidence))
        gain *= max(0.2, 1.0 - min(0.9, own_noise))
        gain *= math.pow(0.6, max(0, occlusion_layers))
        gain = max(0.0, min(1.0, gain))
        azimuth_rad = math.radians(azimuth_deg)
        left, right = _equal_power_pan(azimuth_rad)
        channel.set_volume(
            left * gain * self.master_gain * self.duck_gain,
            right * gain * self.master_gain * self.duck_gain,
        )

    def update(self, dt: float, events: list[GameEvent]) -> None:
        if events:
            if any(evt.priority >= 70 for evt in events):
                self._duck_timer = max(self._duck_timer, self._duck_duration)
            for evt in events:
                self._play_event(evt)

        if self._duck_timer > 0.0:
            self._duck_timer = max(0.0, self._duck_timer - dt)
            target = self._duck_min_gain
        else:
            target = 1.0
        if abs(self.duck_gain - target) > 1e-3:
            alpha = min(1.0, dt / max(1e-6, self._duck_release))
            self.duck_gain += (target - self.duck_gain) * alpha

    def _play_event(self, evt: GameEvent) -> None:
        if self.headless or pygame is None:
            return

        asset = None
        if evt.type in (EVENT_PING, EVENT_FIRE_SOLUTION_READY):
            asset = "ping"
        elif evt.type in (EVENT_TORP_LAUNCH, EVENT_TORP_IN_WATER):
            asset = "torpedo"
        elif evt.type in (EVENT_DETONATION, EVENT_TORP_HIT):
            if evt.payload.get("weapon") == "mine":
                asset = "mine"
            else:
                asset = "torpedo"
        elif evt.type in (EVENT_UI_CONFIRM, EVENT_UI_ALERT, EVENT_FIRE_SOLUTION_START, EVENT_FIRE_SOLUTION_MISS):
            asset = "ping"

        if asset is None:
            return
        sound = self.sounds.get(asset)
        if sound is None:
            return
        handle = pygame.mixer.find_channel()
        if handle is None:
            handle = pygame.mixer.Channel(pygame.mixer.get_num_channels() - 1)

        if evt.bearing_deg is not None:
            left, right = _pan_from_bearing(evt.bearing_deg)
        else:
            left, right = 1.0, 1.0
        gain = self.master_gain
        handle.set_volume(left * gain, right * gain)
        handle.play(sound)

    def shutdown(self) -> None:
        if not self.headless and pygame is not None:
            pygame.mixer.quit()


__all__ = ["AudioEngine"]
