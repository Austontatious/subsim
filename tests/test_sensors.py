from subsim.contacts import Contact
from subsim.sensors import SensorSuite
from subsim.world import World
from subsim.config import SPEED_OF_SOUND


def make_contact(ident: str, x: float, y: float, z: float) -> Contact:
    return Contact(
        ident=ident,
        kind="merchant",
        position=(x, y, z),
        heading_deg=0.0,
        speed_mps=2.0,
        depth_m=z,
        noise=0.3,
    )


def test_passive_gain_rolloff():
    world = World()
    suite = SensorSuite()
    near = make_contact("near", 150.0, 0.0, -120.0)
    far = make_contact("far", 900.0, 0.0, -120.0)
    tracks = suite.sample_passive(world, [near, far])
    gains = {t.contact_id: t.gain for t in tracks}
    assert gains["near"] > gains["far"]


def test_passive_thermocline_occlusion():
    world = World()
    suite = SensorSuite()
    above = make_contact("above", 0.0, 0.0, -80.0)
    below = make_contact("below", 0.0, 0.0, -260.0)
    tracks = suite.sample_passive(world, [above, below])
    gains = {t.contact_id: t.gain for t in tracks}
    assert gains["above"] > gains["below"]


def test_ping_return_delay_matches_physics():
    world = World()
    suite = SensorSuite()
    target = make_contact("target", 300.0, 0.0, -120.0)
    suite.emit_ping(world.time)
    returns = suite.process_active(world, [target], ping_requested=False)
    assert len(returns) == 1
    expected_delay = 2.0 * 300.0 / SPEED_OF_SOUND
    assert abs(returns[0].delay_s - expected_delay) < 1e-3
