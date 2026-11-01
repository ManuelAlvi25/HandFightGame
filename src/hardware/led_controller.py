"""Lógica de LEDs de vida, independiente de que los LEDs sean físicos o simulados."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LedFrame:
    player: tuple[bool, ...]
    enemy: tuple[bool, ...]
    player_critical: bool = False
    enemy_critical: bool = False


def leds_for_health(pct: float, count: int) -> tuple[bool, ...]:
    """LEDs encendidos de izquierda a derecha. Con cualquier vida > 0 queda al menos uno encendido."""
    pct = min(1.0, max(0.0, pct))
    lit = math.ceil(pct * count - 1e-9) if pct > 0 else 0
    return tuple(i < lit for i in range(count))


class LedController:
    def __init__(self, cfg: dict):
        self.player_count = cfg.get("player_count", 5)
        self.enemy_count = cfg.get("enemy_count", 5)
        self.critical = cfg.get("critical_threshold", 0.25)
        self.blink_hz = cfg.get("blink_hz", 4)

    def update(self, player_pct: float, enemy_pct: float, t: float) -> LedFrame:
        blink_on = int(t * self.blink_hz * 2) % 2 == 0
        p_crit = 0 < player_pct <= self.critical
        e_crit = 0 < enemy_pct <= self.critical
        p = leds_for_health(player_pct, self.player_count)
        e = leds_for_health(enemy_pct, self.enemy_count)
        # vida crítica: los LEDs encendidos parpadean
        if p_crit and not blink_on:
            p = tuple(False for _ in p)
        if e_crit and not blink_on:
            e = tuple(False for _ in e)
        return LedFrame(p, e, p_crit, e_crit)
