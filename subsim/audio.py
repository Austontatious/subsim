"""Audio mixing and playback helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .acoustic_contract import AcousticFoundationState
from .assets import ensure_assets
from .config import AUDIO_SAMPLE_RATE
from .events import (
    EVENT_DETONATION,
    EVENT_FIRE_SOLUTION_MISS,
    EVENT_FIRE_SOLUTION_READY,
    EVENT_FIRE_SOLUTION_START,
    EVENT_PING,
    EVENT_RETURN,
    EVENT_TORP_HIT,
    EVENT_TORP_IN_WATER,
    EVENT_TORP_LAUNCH,
    EVENT_UI_ALERT,
    EVENT_UI_CONFIRM,
    GameEvent,
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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class _Channel:
    left: float = 0.0
    right: float = 0.0
    channel: Optional["pygame.mixer.Channel"] = None
    asset_name: str = ""
    variant: str = "clean"

    def set_volume(self, left: float, right: float) -> None:
        self.left, self.right = left, right
        if self.channel:
            self.channel.set_volume(left, right)


class AudioEngine:
    """High-level audio driver that mixes contact loops, foundations, and earcons."""

    FOUNDATION_AMBIENT_KEY = "__ambient__"
    FOUNDATION_SELF_NOISE_KEY = "__self_noise__"
    FOUNDATION_HUM_KEY = "__player_hum__"

    def __init__(self, headless: bool = False) -> None:
        self.assets = ensure_assets()
        self.headless = headless or not _HAVE_PYGAME
        self.master_gain = 1.0
        self.channels: Dict[str, _Channel] = {}
        self.sounds: Dict[str, Dict[str, "pygame.mixer.Sound"]] = {}
        self.external_sounds: Dict[str, "pygame.mixer.Sound"] = {}
        self.duck_gain = 1.0
        self._duck_timer = 0.0
        self._duck_duration = 0.6
        self._duck_min_gain = 0.45
        self._duck_release = 0.35

        if not self.headless and pygame is not None:
            try:
                pygame.mixer.pre_init(AUDIO_SAMPLE_RATE, size=-16, channels=2, buffer=512)
                pygame.mixer.init()
                for asset_name, variants in self.assets.items():
                    loaded: Dict[str, "pygame.mixer.Sound"] = {}
                    for variant, wav in variants.items():
                        loaded[variant] = pygame.mixer.Sound(wav.as_posix())
                    self.sounds[asset_name] = loaded
            except Exception:
                # Fallback to silent mode if audio init fails.
                self.headless = True
                self.sounds = {}

    def _get_sound(self, asset_name: str, variant: str = "clean") -> Optional["pygame.mixer.Sound"]:
        variants = self.sounds.get(asset_name, {})
        return variants.get(variant) or variants.get("clean")

    def _get_or_load_external_sound(self, wav_path: str) -> Optional["pygame.mixer.Sound"]:
        if self.headless or pygame is None:
            return None
        cached = self.external_sounds.get(wav_path)
        if cached is not None:
            return cached
        path = Path(wav_path)
        if not path.exists():
            return None
        try:
            sound = pygame.mixer.Sound(path.as_posix())
        except Exception:
            return None
        self.external_sounds[wav_path] = sound
        return sound

    def _find_or_open_channel(self) -> Optional["pygame.mixer.Channel"]:
        if self.headless or pygame is None:
            return None
        handle = pygame.mixer.find_channel()
        if handle is not None:
            return handle
        channel_count = pygame.mixer.get_num_channels()
        if channel_count <= 0:
            return None
        return pygame.mixer.Channel(channel_count - 1)

    def play_loop(self, asset_name: str, key: str, *, variant: str = "clean") -> None:
        channel = self.channels.get(key)
        if channel and channel.asset_name == asset_name and channel.variant == variant:
            return

        if channel and channel.channel:
            channel.channel.fadeout(120)

        chan = _Channel(asset_name=asset_name, variant=variant)
        if not self.headless and pygame is not None:
            handle = self._find_or_open_channel()
            sound = self._get_sound(asset_name, variant=variant)
            if handle and sound:
                handle.play(sound, loops=-1)
                chan.channel = handle
        self.channels[key] = chan

    def play_external_loop(self, wav_path: str, key: str) -> None:
        marker = f"file:{wav_path}"
        channel = self.channels.get(key)
        if channel and channel.asset_name == marker and channel.variant == "external":
            return

        if channel and channel.channel:
            channel.channel.fadeout(120)

        chan = _Channel(asset_name=marker, variant="external")
        if not self.headless and pygame is not None:
            handle = self._find_or_open_channel()
            sound = self._get_or_load_external_sound(wav_path)
            if handle and sound:
                handle.play(sound, loops=-1)
                chan.channel = handle
        self.channels[key] = chan

    def stop_loop(self, key: str) -> None:
        channel = self.channels.pop(key, None)
        if channel and channel.channel:
            channel.channel.fadeout(150)

    def earcon(self, asset_name: str, gain_db: float = 0.0, *, variant: str = "clean") -> None:
        if self.headless or pygame is None:
            return
        sound = self._get_sound(asset_name, variant=variant)
        if sound is None:
            return
        gain = self.master_gain * _db_to_gain(gain_db)
        sound.set_volume(gain)
        sound.play()

    def _rescale_channels(self, ratio: float) -> None:
        if abs(ratio - 1.0) <= 1e-6:
            return
        for ch in self.channels.values():
            ch.set_volume(ch.left * ratio, ch.right * ratio)

    def set_master_volume(self, db: float) -> None:
        old = self.master_gain
        self.master_gain = max(0.0, min(1.0, _db_to_gain(db)))
        if old <= 1e-6:
            return
        self._rescale_channels(self.master_gain / old)

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
        gain *= _clamp01(confidence)
        gain *= max(0.2, 1.0 - min(0.9, own_noise))
        gain *= math.pow(0.6, max(0, occlusion_layers))
        gain = _clamp01(gain)
        azimuth_rad = math.radians(azimuth_deg)
        left, right = _equal_power_pan(azimuth_rad)
        channel.set_volume(
            left * gain * self.master_gain * self.duck_gain,
            right * gain * self.master_gain * self.duck_gain,
        )

    def _set_foundation_mix(self, key: str, gain: float) -> None:
        channel = self.channels.get(key)
        if not channel:
            return
        g = _clamp01(gain) * self.master_gain * self.duck_gain
        channel.set_volume(g, g)

    def set_runtime_layer_mix(self, key: str, gain: float) -> None:
        self._set_foundation_mix(key, gain)

    def update_foundation(
        self,
        foundation: AcousticFoundationState,
        *,
        profile_overrides: dict[str, float] | None = None,
    ) -> None:
        """Update foundational channels: ambient bed, self-noise, and player hum."""
        self.play_loop("ambient", self.FOUNDATION_AMBIENT_KEY, variant="lp3")
        self.play_loop("ambient", self.FOUNDATION_SELF_NOISE_KEY, variant="lp1")
        hum_variant = "clean" if foundation.player_hum_level >= 0.25 else "lp1"
        self.play_loop("player_hum", self.FOUNDATION_HUM_KEY, variant=hum_variant)

        ambient_gain = foundation.ambient_level
        self_noise_gain = foundation.self_noise_level * 0.38
        hum_gain = foundation.player_hum_level
        if foundation.ping_active:
            ambient_gain *= 0.92
            hum_gain *= 0.88
        if profile_overrides:
            ambient_gain = float(profile_overrides.get("ambient_gain", ambient_gain))
            self_noise_gain = float(profile_overrides.get("self_noise_gain", self_noise_gain))
            hum_gain = float(profile_overrides.get("hum_gain", hum_gain))
        self._set_foundation_mix(self.FOUNDATION_AMBIENT_KEY, ambient_gain)
        self._set_foundation_mix(self.FOUNDATION_SELF_NOISE_KEY, self_noise_gain)
        self._set_foundation_mix(self.FOUNDATION_HUM_KEY, hum_gain)

    def update(self, dt: float, events: list[GameEvent]) -> None:
        if events:
            if any(evt.priority >= 70 for evt in events):
                self._duck_timer = max(self._duck_timer, self._duck_duration)
            for evt in events:
                self._play_event(evt)

        old_duck = self.duck_gain
        if self._duck_timer > 0.0:
            self._duck_timer = max(0.0, self._duck_timer - dt)
            target = self._duck_min_gain
        else:
            target = 1.0
        if abs(self.duck_gain - target) > 1e-3:
            alpha = min(1.0, dt / max(1e-6, self._duck_release))
            self.duck_gain += (target - self.duck_gain) * alpha
        if old_duck > 1e-6:
            self._rescale_channels(self.duck_gain / old_duck)

    def _play_event(self, evt: GameEvent) -> None:
        if self.headless or pygame is None:
            return

        asset = None
        variant = "clean"
        if evt.type in (EVENT_PING, EVENT_FIRE_SOLUTION_READY):
            asset = "ping"
        elif evt.type in (EVENT_RETURN,):
            asset = "ping"
            variant = "lp1"
        elif evt.type in (EVENT_TORP_LAUNCH, EVENT_TORP_IN_WATER):
            asset = "torpedo"
        elif evt.type in (EVENT_DETONATION, EVENT_TORP_HIT):
            if evt.payload.get("weapon") == "mine":
                asset = "mine"
            else:
                asset = "torpedo"
        elif evt.type in (EVENT_UI_CONFIRM, EVENT_UI_ALERT, EVENT_FIRE_SOLUTION_START, EVENT_FIRE_SOLUTION_MISS):
            asset = "ping"
            variant = "lp2"

        if asset is None:
            return
        sound = self._get_sound(asset, variant=variant)
        if sound is None:
            return
        handle = self._find_or_open_channel()
        if handle is None:
            return

        if evt.bearing_deg is not None:
            left, right = _pan_from_bearing(evt.bearing_deg)
        else:
            left, right = 1.0, 1.0
        distance_scale = 1.0
        if evt.distance_norm is not None:
            distance_scale = max(0.35, 1.0 - (_clamp01(evt.distance_norm) * 0.45))
        gain = self.master_gain * distance_scale
        handle.set_volume(left * gain, right * gain)
        handle.play(sound)

    def shutdown(self) -> None:
        if not self.headless and pygame is not None:
            pygame.mixer.quit()
        self.external_sounds = {}


__all__ = ["AudioEngine"]
