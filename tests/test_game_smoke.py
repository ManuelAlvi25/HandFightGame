"""Ejecuta el juego completo sin ventana (driver dummy) en modo demo."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.game.game import Game, Scene  # noqa: E402
from src.utils.config_loader import load_config  # noqa: E402


def make_game(**kw):
    return Game(load_config("game_config.json"), load_config("gesture_config.json"),
                load_config("hardware_config.json"), use_camera=False, **kw)


def test_demo_fight_runs_without_errors():
    g = make_game(demo=True)
    g.cfg["match"]["countdown"] = 0.3
    g.run(max_frames=360, auto=True)  # ~6 s reales a 60 FPS
    assert g.scene in (Scene.FIGHT, Scene.RESULT)
    assert g.player.attacks_started + g.enemy.attacks_started > 0
    assert g.led_frame is not None and g.sensor_cm is not None


def test_simulated_sensor_moves_player():
    g = make_game()
    try:
        g.start_fight()
        g.countdown = 0
        g.hardware.set_distance(60)  # extremo derecho
        x0 = g.player.x
        import time
        from src.vision.vision_service import VisionSnapshot
        for _ in range(60):
            g.sensor_cm = g.sensor.process(g.hardware.read_distance(), time.monotonic())
            g._update_fight(1 / 60, [], set(), 0.0, VisionSnapshot())
        assert g.player.x > x0 + 50
    finally:
        g.shutdown()
