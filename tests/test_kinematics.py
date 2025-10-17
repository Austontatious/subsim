from subsim.config import TELEGRAPH_SPEEDS
from subsim.world import World


def test_player_accelerates_to_order():
    world = World()
    player = world.player
    player.telegraph = "FULL"
    for _ in range(120):
        world.update(1 / 30)
    assert abs(player.speed_mps - TELEGRAPH_SPEEDS["FULL"]) < 0.5


def test_player_depth_tracks_command():
    world = World()
    start_depth = world.player.position[2]
    world.player.change_depth(-50.0)
    for _ in range(120):
        world.update(1 / 30)
    assert world.player.position[2] < start_depth - 10.0
    world.player.change_depth(50.0)
    for _ in range(120):
        world.update(1 / 30)
    assert world.player.position[2] > start_depth - 5.0
