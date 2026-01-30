from subsim.audio import AudioEngine
from subsim.events import EventBus, GameEvent, EVENT_PING


def test_event_bus_flushes():
    bus = EventBus()
    bus.emit(EVENT_PING, t=0.0, priority=7)
    assert bus.peek(), "event should be queued"
    events = bus.flush()
    assert len(events) == 1
    assert not bus.peek(), "bus should be empty after flush"


def test_audio_ducking_on_priority_event():
    engine = AudioEngine(headless=True)
    base = engine.duck_gain
    engine.update(0.1, [GameEvent(t=0.0, type=EVENT_PING, priority=80)])
    assert engine.duck_gain < base
    engine.update(1.0, [])
    assert engine.duck_gain <= 1.0
