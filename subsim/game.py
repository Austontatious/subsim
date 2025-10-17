"""Game orchestration layer."""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Optional

from .ai import AiController
from .audio import AudioEngine
from .config import FRAME_DT
from .contacts import ContactManager
from .render import Renderer
from .sensors import SensorSuite
from .ui import InputController
from .weapons import WeaponManager
from .world import World, clamp


CONTACT_AUDIO = {
    "merchant": "merchant",
    "hunter": "hunter",
}


@dataclass
class Game:
    headless: bool = False
    seed: int = 0
    duration: Optional[float] = None

    def __post_init__(self) -> None:
        self.world = World(seed=self.seed)
        self.contacts = ContactManager(seed=self.seed)
        self.contacts.spawn_demo_contacts()
        self.sensors = SensorSuite()
        self.weapons = WeaponManager()
        self.audio = AudioEngine(headless=self.headless)
        self.renderer = Renderer(headless=self.headless)
        self.input = InputController(self.renderer)
        self.ai = AiController(self.contacts)
        self._telegraph_cooldown = 0.0
        self._pending_ping = False
        self.running = True

    def shutdown(self) -> None:
        self.audio.shutdown()
        if self.renderer:
            self.renderer.close()

    def _apply_controls(self, dt: float) -> None:
        state = self.input.collect()
        if state.quit:
            self.running = False

        if state.turn:
            self.world.player.change_heading(state.turn * 65.0 * dt)
        if state.depth_delta:
            self.world.player.change_depth(state.depth_delta)
        if self._telegraph_cooldown <= 0.0:
            if state.speed_delta > 0:
                self.world.player.telegraph_step(True)
                self._telegraph_cooldown = 0.4
            elif state.speed_delta < 0:
                self.world.player.telegraph_step(False)
                self._telegraph_cooldown = 0.4
        else:
            self._telegraph_cooldown = max(0.0, self._telegraph_cooldown - dt)

        if state.drop_mine:
            self.weapons.drop_mine(self.world.player.position)
            self.audio.earcon("mine", gain_db=-6.0)
        if state.fire_torpedo:
            contacts = list(self.contacts.contacts.values())
            if contacts:
                target = min(contacts, key=lambda c: World.distance(self.world.player.position, c.position))
                self.weapons.launch_torpedo(self.world.player.position, self.world.player.heading_deg, target.ident)
                self.audio.earcon("torpedo", gain_db=-4.0)
        self._pending_ping = state.ping

    def _update_audio(self) -> None:
        passive = self.sensor_tick.passive_tracks
        for track in passive:
            contact = self.contacts.contacts[track.contact_id]
            asset = CONTACT_AUDIO.get(contact.kind, "merchant")
            self.audio.play_loop(asset, track.contact_id)
            self.audio.set_contact_mix(
                track.contact_id,
                azimuth_deg=track.azimuth_deg,
                distance_m=track.distance_m,
                confidence=track.confidence,
                occlusion_layers=track.occlusion_layers,
                own_noise=self.world.player.own_noise,
            )

    def tick(self, dt: float) -> None:
        self._apply_controls(dt)
        self.world.update(dt)
        self.contacts.update(dt)
        self.ai.update(self.world, dt)

        ping_now = getattr(self, "_pending_ping", False)
        if ping_now:
            self.ai.notify_ping(self.world.time)
            self.audio.earcon("ping")
        self.sensor_tick = self.sensors.step(self.world, self.contacts, ping=ping_now)
        self._pending_ping = False
        self._update_audio()

        events = self.weapons.update(dt, self.world.time, list(self.contacts))
        for evt in events:
            if evt.kind == "torpedo-detonation":
                self.audio.earcon("torpedo")
            elif evt.kind == "mine-detonation":
                self.audio.earcon("mine")

    def run(self) -> None:
        start = time.perf_counter()
        last = start
        target_dt = FRAME_DT
        while self.running:
            now = time.perf_counter()
            dt = clamp(now - last, 0.0, 0.2)
            last = now
            self.tick(dt)
            if not self.headless:
                self.renderer.draw(self.world, list(self.contacts))
            else:
                time.sleep(max(0.0, target_dt - dt))
            if self.duration is not None and (now - start) >= self.duration:
                break
        self.shutdown()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SubSim prototype")
    parser.add_argument("--headless", action="store_true", help="run without window or audio")
    parser.add_argument("--seed", type=int, default=0, help="random seed")
    parser.add_argument("--duration", type=float, default=None, help="max runtime in seconds")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    duration = args.duration
    if args.headless and duration is None:
        duration = 3.0
    game = Game(headless=args.headless, seed=args.seed, duration=duration)
    game.run()


__all__ = ["main", "Game"]
