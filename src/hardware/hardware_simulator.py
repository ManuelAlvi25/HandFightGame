"""Hardware simulado: sensor de distancia controlable y LEDs virtuales."""
from __future__ import annotations

import random

from src.hardware.hardware_interface import ConnectionStatus, HardwareInterface
from src.hardware.led_controller import LedFrame
from src.hardware.protocol import leds_payload


class SimulatedHardware(HardwareInterface):
    def __init__(self, sim_cfg: dict, ultrasonic_cfg: dict, rng: random.Random | None = None):
        self.min_cm = ultrasonic_cfg["min_cm"]
        self.max_cm = ultrasonic_cfg["max_cm"]
        self.distance_cm = float(sim_cfg.get("initial_cm", (self.min_cm + self.max_cm) / 2))
        self.noise_cm = sim_cfg.get("noise_cm", 0.0)
        self.invalid_rate = sim_cfg.get("invalid_rate", 0.0)
        self.rng = rng or random.Random()
        self.leds: LedFrame | None = None
        self.health = (1.0, 1.0)
        self.status = ConnectionStatus.DISCONNECTED

    def connect(self) -> None:
        self.status = ConnectionStatus.SIMULATED

    def disconnect(self) -> None:
        self.status = ConnectionStatus.DISCONNECTED

    def describe(self) -> str:
        return "SIMULACIÓN"

    # controles del simulador (teclado / deslizador en pantalla)
    def adjust(self, delta_cm: float) -> None:
        self.set_distance(self.distance_cm + delta_cm)

    def set_distance(self, cm: float) -> None:
        self.distance_cm = min(self.max_cm, max(self.min_cm, cm))

    def read_distance(self) -> float | None:
        if self.status != ConnectionStatus.SIMULATED:
            return None
        if self.invalid_rate and self.rng.random() < self.invalid_rate:
            return -1.0  # lectura inválida simulada (como un HC-SR04 sin eco)
        return self.distance_cm + self.rng.gauss(0, self.noise_cm) if self.noise_cm else self.distance_cm

    def send_leds(self, frame: LedFrame) -> None:
        self.leds = frame
        self.last_tx = leds_payload(frame)

    def send_health(self, player_pct: float, enemy_pct: float) -> None:
        self.health = (player_pct, enemy_pct)
