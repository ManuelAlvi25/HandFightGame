"""Validación y filtrado de lecturas del sensor ultrasónico (HC-SR04 o similar)."""
from __future__ import annotations

import math
import statistics
from collections import deque


class UltrasonicSensor:
    def __init__(self, cfg: dict):
        self.valid_min = cfg.get("valid_min_cm", 2)
        self.valid_max = cfg.get("valid_max_cm", 400)
        self.max_jump = cfg.get("max_jump_cm", 50)
        self.timeout = cfg.get("timeout_s", 1.0)
        self.window: deque[float] = deque(maxlen=max(1, cfg.get("median_window", 5)))
        self.last_valid_time: float | None = None
        self.invalid_count = 0
        self.last_error = ""
        self._rejected_jumps = 0

    def _invalid(self, why: str) -> None:
        self.invalid_count += 1
        self.last_error = why

    def process(self, raw, now: float) -> float | None:
        """Devuelve la distancia filtrada (mediana) o None si no hay datos válidos recientes."""
        if raw is not None:
            try:
                d = float(raw)
            except (TypeError, ValueError):
                d = math.nan
            if not math.isfinite(d):
                self._invalid(f"lectura no numérica: {raw!r}")
            elif not self.valid_min <= d <= self.valid_max:
                self._invalid(f"fuera de rango: {d:.1f} cm")
            elif self.window and abs(d - statistics.median(self.window)) > self.max_jump and self._rejected_jumps < 3:
                self._rejected_jumps += 1  # pico aislado; si se repite 3 veces se acepta como real
                self._invalid(f"salto brusco: {d:.1f} cm")
            else:
                if self._rejected_jumps >= 3:
                    self.window.clear()  # cambio de nivel sostenido: empezar de cero en el nuevo valor
                self._rejected_jumps = 0
                self.window.append(d)
                self.last_valid_time = now
        if self.last_valid_time is None or now - self.last_valid_time > self.timeout:
            self.window.clear()
            return None
        return statistics.median(self.window)
