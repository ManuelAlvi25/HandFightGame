"""Efectos de sonido sintetizados con NumPy (sin archivos externos). Opcionales."""
from __future__ import annotations

import logging

import numpy as np
import pygame

log = logging.getLogger(__name__)
RATE = 44100


def _env(n, attack=0.005, decay=8.0):
    t = np.arange(n) / RATE
    return np.minimum(1.0, t / attack) * np.exp(-t * decay)


def _sweep(f0, f1, dur):
    n = int(RATE * dur)
    f = np.linspace(f0, f1, n)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE)


def _synth() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(1)
    s = {}
    n = int(RATE * 0.22)
    s["hit"] = (rng.uniform(-1, 1, n) * _env(n, decay=22) * 0.8 + _sweep(160, 50, 0.22) * _env(n, decay=12))
    n = int(RATE * 0.09)
    s["block"] = np.sign(_sweep(1300, 900, 0.09)) * _env(n, decay=40) * 0.5 + rng.uniform(-1, 1, n) * _env(n, decay=60) * 0.3
    n = int(RATE * 0.14)
    noise = np.convolve(rng.uniform(-1, 1, n), np.ones(30) / 30, "same")
    s["whoosh"] = noise * np.sin(np.linspace(0, np.pi, n)) * 3.0
    n = int(RATE * 0.8)
    s["ko"] = (_sweep(420, 60, 0.8) + 0.5 * np.sign(_sweep(210, 30, 0.8))) * _env(n, attack=0.01, decay=3) * 0.7
    n = int(RATE * 0.06)
    s["select"] = _sweep(880, 1100, 0.06) * _env(n, decay=30) * 0.5
    n = int(RATE * 0.5)
    s["fight"] = sum(_sweep(f, f, 0.5) for f in (440, 554, 659)) / 3 * _env(n, attack=0.01, decay=4)
    return s


class SoundBank:
    def __init__(self, enabled: bool = True, volume: float = 0.5):
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            channels = pygame.mixer.get_init()[2]
            for name, wave in _synth().items():
                pcm = (np.clip(wave, -1, 1) * 32767 * volume).astype(np.int16)
                arr = np.repeat(pcm[:, None], channels, axis=1) if channels > 1 else pcm
                self.sounds[name] = pygame.sndarray.make_sound(np.ascontiguousarray(arr))
        except Exception as e:  # sin dispositivo de audio: el juego sigue en silencio
            log.warning("Audio desactivado: %s", e)
            self.sounds = {}

    def play(self, name: str) -> None:
        snd = self.sounds.get(name)
        if snd:
            snd.play()
