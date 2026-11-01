"""Fuentes de movimiento lateral intercambiables: sensor ultrasónico, mano (MediaPipe) o teclado.

Todas se reducen a un valor normalizado 0..1 que se convierte en una posición objetivo
dentro de la arena, con zona muerta y suavizado exponencial.
"""
from __future__ import annotations


def distance_to_position(d: float, d_min: float, d_max: float, invert: bool = False) -> float:
    """Convierte una distancia (cm) en una posición normalizada 0..1, limitada a los extremos."""
    if d_max <= d_min:
        raise ValueError("max_cm debe ser mayor que min_cm")
    v = min(1.0, max(0.0, (d - d_min) / (d_max - d_min)))
    return 1.0 - v if invert else v


class MovementController:
    def __init__(self, cfg: dict, ultrasonic_cfg: dict, arena_left: float, arena_right: float):
        self.sources: list[str] = cfg.get("sources", ["ultrasonic", "hand", "keyboard"])
        self.source: str = cfg.get("source", self.sources[0])
        self.smoothing = cfg.get("smoothing", 0.25)  # fracción por frame a 60 FPS (1 = sin suavizado)
        self.deadzone = cfg.get("deadzone", 0.015)
        self.hand_range = cfg.get("hand_x_range", [0.2, 0.8])
        self.us = ultrasonic_cfg
        self.left, self.right = arena_left, arena_right
        self._raw: float | None = None
        self._smoothed: float | None = None

    def reset(self) -> None:
        self._raw = self._smoothed = None

    def cycle_source(self) -> str:
        self.source = self.sources[(self.sources.index(self.source) + 1) % len(self.sources)]
        self.reset()
        return self.source

    def normalized(self, distance_cm: float | None, hand_x: float | None) -> float | None:
        if self.source == "ultrasonic" and distance_cm is not None:
            return distance_to_position(distance_cm, self.us["min_cm"], self.us["max_cm"], self.us.get("invert", False))
        if self.source == "hand" and hand_x is not None:
            lo, hi = self.hand_range
            return min(1.0, max(0.0, (hand_x - lo) / (hi - lo)))
        return None

    def update(self, dt: float, distance_cm: float | None, hand_x: float | None) -> float | None:
        """Devuelve la x objetivo del jugador o None (sin datos / modo teclado)."""
        raw = self.normalized(distance_cm, hand_x)
        if raw is None:
            return None
        if self._raw is not None and abs(raw - self._raw) < self.deadzone:
            raw = self._raw  # zona muerta: ignora temblores pequeños
        self._raw = raw
        if self._smoothed is None:
            self._smoothed = raw
        else:
            alpha = 1.0 - (1.0 - self.smoothing) ** (dt * 60.0)
            self._smoothed += (raw - self._smoothed) * alpha
        return self.left + self._smoothed * (self.right - self.left)
