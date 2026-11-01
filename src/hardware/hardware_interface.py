"""Capa de abstracción de hardware.

El juego solo conoce estas interfaces; no sabe si detrás hay un simulador o un Arduino.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from src.hardware.led_controller import LedFrame


class ConnectionStatus(str, Enum):
    SIMULATED = "simulado"
    DISCONNECTED = "desconectado"
    CONNECTING = "conectando"
    CONNECTED = "conectado"
    ERROR = "error"


class DistanceSensor(ABC):
    @abstractmethod
    def read_distance(self) -> float | None:
        """Última distancia del sensor ultrasónico en cm (cruda, sin filtrar) o None."""


class LedOutput(ABC):
    @abstractmethod
    def send_leds(self, frame: LedFrame) -> None: ...


class HealthOutput(ABC):
    @abstractmethod
    def send_health(self, player_pct: float, enemy_pct: float) -> None: ...


class ConnectionMonitor(ABC):
    status: ConnectionStatus
    last_error: str

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def describe(self) -> str: ...


class HardwareInterface(DistanceSensor, LedOutput, HealthOutput, ConnectionMonitor):
    """Interfaz completa que implementan SimulatedHardware y ArduinoLink."""

    status = ConnectionStatus.DISCONNECTED
    last_error = ""
    last_tx = ""  # última línea de protocolo enviada (para depuración en pantalla)

    def update(self, dt: float) -> None:
        """Opcional: trabajo periódico en el hilo del juego."""
