"""Colores y fuentes compartidos por la interfaz."""
from __future__ import annotations

import pygame

BG = (12, 10, 24)
PANEL = (20, 18, 38)
PANEL_EDGE = (90, 70, 160)
TEXT = (240, 240, 250)
MUTED = (150, 150, 175)
ACCENT = (255, 200, 40)
P1 = (70, 160, 255)
CPU = (255, 80, 80)
OK = (60, 220, 120)
WARN = (255, 180, 40)
BAD = (240, 60, 60)

_cache: dict[tuple, pygame.font.Font] = {}


def font(size: int, bold: bool = True) -> pygame.font.Font:
    key = (size, bold)
    if key not in _cache:
        name = "impact,arialblack,arial" if bold else "segoeui,arial"
        try:
            _cache[key] = pygame.font.SysFont(name, size)
        except Exception:
            _cache[key] = pygame.font.Font(None, size)
    return _cache[key]


def text(surface, msg: str, pos, size=24, color=TEXT, anchor="topleft", bold=True, shadow=True):
    f = font(size, bold)
    img = f.render(msg, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surface.blit(f.render(msg, True, (0, 0, 0)), rect.move(2, 2))
    surface.blit(img, rect)
    return rect


def status_color(status_value: str) -> tuple:
    return {"activa": OK, "conectado": OK, "simulado": P1, "iniciando": WARN, "conectando": WARN,
            "desactivada": MUTED, "desconectado": MUTED}.get(status_value, BAD)
