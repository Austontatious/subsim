"""SubSim package exports."""


def main(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Lazy-import game entrypoint to avoid side effects at package import time."""
    from .game import main as game_main

    return game_main(*args, **kwargs)


__all__ = ["main"]
