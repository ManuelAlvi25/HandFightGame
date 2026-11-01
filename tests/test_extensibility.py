"""Registrar gestos y acciones nuevos sin tocar el controlador de combate."""
from src.game.actions import ACTIONS, dispatch, register_action
from src.game.character import State
from src.game.player import Player
from src.vision.gesture_manager import GestureDefinition, GestureManager
from src.vision.gesture_recognizer import DETECTORS, register_detector
from tests.helpers import fighter, make_hand


def test_new_gesture_new_detector_and_new_action():
    calls = []

    @register_detector("test_point")
    def _point(f, params):
        return f.extension["index"] * (1 - f.extension["middle"])

    @register_action("test_special", "trigger")
    def _special(ch, active):
        calls.append(ch)

    try:
        mgr = GestureManager([])
        mgr.register(GestureDefinition(id="point", name="Índice", detector="test_point", action="test_special",
                                       min_frames=1, priority=1))
        # una mano abierta tiene índice y medio extendidos -> 0; forzamos con una mano en puño + índice
        h = make_hand("fist")
        h.landmarks[6:9, 1] = [0.52, 0.46, 0.40]  # índice extendido
        out = mgr.update([h], 0.0)
        assert out.triggered == ["test_special"]
        p = fighter(cls=Player)
        dispatch(p, out.triggered, set(out.held))
        assert calls == [p]
    finally:
        DETECTORS.pop("test_point", None)
        ACTIONS.pop("test_special", None)


def test_two_hand_gesture_has_priority_over_single_fist():
    defs = [
        GestureDefinition(id="fist", name="Puño", detector="fist", action="attack", min_frames=1, priority=10),
        GestureDefinition(id="two_fists", name="Dos puños", detector="fist", action="heavy_attack", hands="both",
                          min_frames=1, priority=20),
    ]
    mgr = GestureManager(defs)
    out = mgr.update([make_hand("fist"), make_hand("fist", dx=0.2, handedness="Left")], 0.0)
    assert out.dominant == "two_fists" and out.triggered == ["heavy_attack"]
    out = GestureManager(defs).update([make_hand("fist")], 0.0)
    assert out.dominant == "fist" and out.triggered == ["attack"]


def test_heavy_attack_action_uses_heavy_move():
    p = fighter(cls=Player)
    dispatch(p, ["heavy_attack"], set())
    assert p.state == State.ATTACK and p.move.name == "heavy"


def test_duplicate_gesture_id_rejected():
    mgr = GestureManager([GestureDefinition(id="a", name="a", detector="fist", action="attack")])
    try:
        mgr.register(GestureDefinition(id="a", name="a", detector="open_palm", action="block"))
        assert False, "debió fallar"
    except ValueError:
        pass
