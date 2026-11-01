"""Luchador controlado por el jugador (gestos/teclado + fuente de movimiento)."""
from __future__ import annotations

from src.game.actions import dispatch
from src.game.character import Character


class Player(Character):
    def apply_input(self, triggers: list[str], holds: set[str], target_x: float | None, axis: float, dt: float) -> None:
        dispatch(self, triggers, holds)
        if target_x is not None:
            self.walk_toward(target_x, dt)
        else:
            self.walk(axis, dt)
