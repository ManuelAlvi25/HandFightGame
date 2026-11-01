import pytest

from src.utils.config_loader import load_config
from src.vision.gesture_manager import GestureDefinition, GestureManager
from src.vision.gesture_recognizer import DETECTORS, extract_features
from tests.helpers import make_hand


def conf(name, shape, params=None):
    return DETECTORS[name](extract_features(make_hand(shape)), params or {})


def test_fist_and_palm_are_recognized():
    assert conf("fist", "fist") > 0.9
    assert conf("open_palm", "fist") < 0.1
    assert conf("open_palm", "open") > 0.9
    assert conf("fist", "open") < 0.1


def test_half_closed_hand_is_neither():
    assert conf("fist", "partial") < 0.75
    assert conf("open_palm", "partial", {"thumb_weight": 0.2}) < 0.75


@pytest.fixture
def mgr():
    return GestureManager.from_config(load_config("gesture_config.json"))


def feed(mgr, shape, frames, t0, dt=1 / 30):
    outs = []
    for i in range(frames):
        hands = [] if shape is None else [make_hand(shape)]
        outs.append(mgr.update(hands, t0 + i * dt))
    return outs, t0 + frames * dt


def test_config_loads_enabled_gestures(mgr):
    ids = [d.id for d in mgr.definitions]
    assert ids == ["fist", "open_palm"]  # two_fists está deshabilitado en la config


def test_fist_triggers_once_after_confirmation(mgr):
    outs, t = feed(mgr, "fist", 1, 0.0)
    assert outs[0].triggered == []           # 1 frame no basta (min_frames=2)
    outs, t = feed(mgr, "fist", 20, t)
    triggers = [a for o in outs for a in o.triggered]
    assert triggers == ["attack"]            # puño sostenido: un solo ataque
    assert outs[-1].dominant == "fist"


def test_repeat_attack_requires_reopening_hand(mgr):
    _, t = feed(mgr, "fist", 5, 0.0)
    outs, t = feed(mgr, "open", 10, t)
    assert outs[-1].held == {"block"}        # palma abierta => defensa mantenida
    outs, t = feed(mgr, "fist", 5, t)
    assert [a for o in outs for a in o.triggered] == ["attack"]


def test_cooldown_blocks_fast_repeats(mgr):
    _, t = feed(mgr, "fist", 3, 0.0)
    _, t = feed(mgr, "open", 2, t, dt=0.01)   # se suelta muy rápido
    outs, _ = feed(mgr, "fist", 3, t, dt=0.01)  # dentro de los 300 ms de cooldown
    assert all(not o.triggered for o in outs)


def test_hysteresis_tolerates_small_variations(mgr):
    _, t = feed(mgr, "fist", 3, 0.0)
    outs, t = feed(mgr, "partial", 5, t)      # confianza ~0.5: no suelta el puño ni re-dispara
    assert all(o.dominant == "fist" and not o.triggered for o in outs)


def test_palm_hold_and_release_to_neutral(mgr):
    outs, t = feed(mgr, "open", 2, 0.0)
    assert outs[-1].held == frozenset()      # aún no confirmado (min_frames=3, 60 ms)
    outs, t = feed(mgr, "open", 5, t)
    assert outs[-1].held == {"block"}
    outs, t = feed(mgr, "fist", 1, t)
    assert outs[-1].held == {"block"}        # histéresis: 1 frame no basta para soltar
    outs, t = feed(mgr, "fist", 1, t)
    assert outs[-1].held == frozenset()


def test_no_hand_returns_to_neutral(mgr):
    _, t = feed(mgr, "open", 6, 0.0)
    outs, _ = feed(mgr, None, 1, t)
    assert outs[0].dominant is None and outs[0].held == frozenset() and outs[0].hands == 0


def test_invalid_definitions_are_rejected():
    with pytest.raises(ValueError):
        GestureDefinition(id="x", name="x", detector="no_existe", action="attack")
    with pytest.raises(ValueError):
        GestureDefinition(id="x", name="x", detector="fist", action="attack", mode="toggle")
    with pytest.raises(ValueError):
        GestureDefinition(id="x", name="x", detector="fist", action="attack", confidence_threshold=0.4, release_threshold=0.6)
