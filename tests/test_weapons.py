from subsim.contacts import Contact
from subsim.weapons import Mine, Torpedo, WeaponManager


def moving_contact() -> Contact:
    return Contact(
        ident="target",
        kind="merchant",
        position=(250.0, 0.0, -120.0),
        heading_deg=180.0,
        speed_mps=5.0,
        depth_m=-120.0,
        noise=0.3,
    )


def test_mine_arms_and_detonates():
    contact = moving_contact()
    mine = Mine(position=(0.0, 0.0, -120.0), arm_delay=0.5)
    t = 0.0
    dt = 0.1
    event = None
    for _ in range(200):
        contact.update(dt)
        t += dt
        event = mine.update(dt, [contact], t)
        if event:
            break
    assert event is not None, "mine should detonate"
    assert mine.detonated


def test_torpedo_reaches_target():
    target = moving_contact()
    torpedo = Torpedo(position=(0.0, 0.0, -120.0), heading_deg=0.0, target_id=target.ident, run_up=0.2)
    dt = 0.1
    t = 0.0
    event = None
    for _ in range(400):
        target.update(dt)
        t += dt
        event = torpedo.update(dt, [target], t)
        if event:
            break
    assert event is not None, "torpedo should intercept"
    assert torpedo.detonated
