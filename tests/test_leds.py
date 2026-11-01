from src.hardware.led_controller import LedController, leds_for_health


def test_leds_turn_off_progressively():
    assert leds_for_health(1.0, 5) == (True,) * 5
    assert sum(leds_for_health(0.5, 5)) == 3
    assert sum(leds_for_health(0.2, 5)) == 1
    assert sum(leds_for_health(0.01, 5)) == 1   # con vida queda al menos uno
    assert sum(leds_for_health(0.0, 5)) == 0
    assert leds_for_health(0.4, 5) == (True, True, False, False, False)


def test_adapts_to_led_count():
    for n in (1, 3, 8, 10):
        assert len(leds_for_health(0.7, n)) == n
    assert sum(leds_for_health(0.75, 8)) == 6


def test_critical_health_blinks():
    lc = LedController({"player_count": 5, "enemy_count": 4, "critical_threshold": 0.25, "blink_hz": 4})
    f_on = lc.update(0.2, 0.9, 0.0)
    f_off = lc.update(0.2, 0.9, 0.13)  # 4 Hz: medio periodo = 0.125 s
    assert f_on.player_critical and not f_on.enemy_critical
    assert sum(f_on.player) == 1 and sum(f_off.player) == 0  # parpadeo
    assert sum(f_on.enemy) == sum(f_off.enemy) == 4          # no crítico: fijo
    assert len(f_on.enemy) == 4


def test_dead_is_not_critical():
    f = LedController({}).update(0.0, 1.0, 0.0)
    assert not f.player_critical and sum(f.player) == 0
