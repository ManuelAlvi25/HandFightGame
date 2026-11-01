import math

import pytest

from src.controls.movement_controller import MovementController, distance_to_position
from src.hardware.ultrasonic_sensor import UltrasonicSensor

US = {"min_cm": 10, "max_cm": 60, "invert": False}


def test_distance_mapping_and_limits():
    assert distance_to_position(10, 10, 60) == 0
    assert distance_to_position(35, 10, 60) == 0.5
    assert distance_to_position(60, 10, 60) == 1
    assert distance_to_position(-5, 10, 60) == 0
    assert distance_to_position(500, 10, 60) == 1
    assert distance_to_position(20, 10, 60, invert=True) == pytest.approx(0.8)
    with pytest.raises(ValueError):
        distance_to_position(20, 60, 10)


def ctrl(**kw):
    return MovementController({"source": "ultrasonic", "smoothing": kw.get("smoothing", 1.0),
                               "deadzone": kw.get("deadzone", 0.0)}, US, 100, 1100)


def test_target_spans_arena():
    c = ctrl()
    assert c.update(1 / 60, 10, None) == 100
    assert c.update(1 / 60, 60, None) == 1100


def test_smoothing_avoids_jumps_and_converges():
    c = ctrl(smoothing=0.2)
    c.update(1 / 60, 10, None)
    first = c.update(1 / 60, 60, None)
    assert 100 < first < 400
    for _ in range(120):
        x = c.update(1 / 60, 60, None)
    assert x == pytest.approx(1100, abs=1)


def test_deadzone_ignores_jitter():
    c = ctrl(deadzone=0.02)
    x0 = c.update(1 / 60, 35, None)
    assert c.update(1 / 60, 35.5, None) == x0  # 0.5 cm = 0.01 normalizado < zona muerta
    assert c.update(1 / 60, 40, None) > x0


def test_sources_are_interchangeable():
    c = MovementController({"source": "hand", "smoothing": 1.0, "hand_x_range": [0.2, 0.8]}, US, 0, 100)
    assert c.update(1 / 60, 35, None) is None          # sin mano: sin objetivo
    assert c.update(1 / 60, None, 0.5) == pytest.approx(50)
    assert c.update(1 / 60, None, 0.95) == pytest.approx(100)
    assert c.cycle_source() == "keyboard"
    assert c.update(1 / 60, 35, 0.5) is None           # teclado: movimiento directo
    assert c.cycle_source() == "ultrasonic"


@pytest.fixture
def sensor():
    return UltrasonicSensor({"valid_min_cm": 2, "valid_max_cm": 400, "median_window": 5, "max_jump_cm": 50, "timeout_s": 1.0})


@pytest.mark.parametrize("bad", [None, -1, 0, 1000, math.nan, math.inf, "abc", object()])
def test_invalid_readings_are_rejected(sensor, bad):
    assert sensor.process(bad, 0.0) is None
    if bad is not None:
        assert sensor.invalid_count == 1


def test_median_filter_and_spike_rejection(sensor):
    for i, d in enumerate([30, 31, 29, 30, 30]):
        sensor.process(d, i * 0.05)
    assert sensor.process(150, 0.3) == 30           # pico aislado descartado
    assert sensor.process(32, 0.35) == 30           # mediana
    for i in range(3):
        sensor.process(150, 0.4 + i * 0.05)
    assert sensor.process(150, 0.6) > 100           # cambio sostenido: se acepta


def test_sensor_timeout(sensor):
    sensor.process(30, 0.0)
    assert sensor.process(None, 0.5) == 30
    assert sensor.process(None, 1.6) is None
