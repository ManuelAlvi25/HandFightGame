"""Pantallas: inicio, selección de luchador/dificultad, pausa y resultado."""
from __future__ import annotations

import math

import pygame

from src.game.character import Character, State
from src.ui import theme
from src.ui.fighter_renderer import draw_fighter
from src.ui.theme import text

CONTROLS = [
    ("Puño cerrado (cámara)", "ATACAR", "J / Espacio"),
    ("Palma abierta (cámara)", "DEFENDER", "K (mantener)"),
    ("Sensor / mano / teclado", "MOVER", "A D  ← →"),
    ("", "GOLPE FUERTE", "L"),
    ("", "Pausa · Cámara · Fuente mov.", "P · C · M"),
]


def _overlay(surface, alpha=170):
    s = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    s.fill((5, 3, 15, alpha))
    surface.blit(s, (0, 0))


def draw_title(surface, t: float, camera_status: str, hw_desc: str):
    w, h = surface.get_size()
    _overlay(surface, 120)
    for i, col in enumerate(((120, 30, 160), (255, 90, 40), (255, 220, 80))):
        text(surface, "HANDFIGHT", (w // 2 + (2 - i) * 3, 130 + (2 - i) * 3), 96, col, "center", shadow=False)
    text(surface, "Combate 2D controlado con gestos de la mano", (w // 2, 200), 26, theme.TEXT, "center", bold=False)
    if int(t * 2) % 2 == 0:
        text(surface, "PULSA ENTER PARA EMPEZAR", (w // 2, 300), 36, theme.ACCENT, "center")
    box = pygame.Rect(w // 2 - 330, 350, 660, 200)
    pygame.draw.rect(surface, (15, 12, 32), box, border_radius=12)
    pygame.draw.rect(surface, theme.PANEL_EDGE, box, 2, border_radius=12)
    for i, (gesture, action, key) in enumerate(CONTROLS):
        y = box.y + 22 + i * 34
        text(surface, action, (box.x + 24, y), 22, theme.ACCENT)
        text(surface, gesture, (box.x + 290, y + 2), 18, theme.TEXT, bold=False)
        text(surface, key, (box.right - 24, y + 2), 18, theme.MUTED, "topright", bold=False)
    text(surface, f"Cámara: {camera_status}    Hardware: {hw_desc}    ESC salir", (w // 2, 580), 18, theme.MUTED, "center", bold=False)


def make_previews(roster: list[dict], moves) -> list[Character]:
    return [Character(p["name"], 0, moves, p["health"], p["speed"], p["power"], profile=p) for p in roster]


def draw_select(surface, roster, previews, sel: int, difficulties: list[tuple[str, str]], diff_idx: int, t: float):
    w, h = surface.get_size()
    _overlay(surface, 150)
    text(surface, "ELIGE TU LUCHADOR", (w // 2, 50), 54, theme.ACCENT, "center")
    n = len(roster)
    cw, gap = 230, 24
    x0 = (w - (n * cw + (n - 1) * gap)) // 2
    max_hp = max(p["health"] for p in roster)
    max_sp = max(p["speed"] for p in roster)
    max_pw = max(p["power"] for p in roster)
    for i, (prof, ch) in enumerate(zip(roster, previews)):
        r = pygame.Rect(x0 + i * (cw + gap), 100, cw, 370)
        on = i == sel
        pygame.draw.rect(surface, (30, 24, 60) if on else (18, 15, 36), r, border_radius=14)
        pygame.draw.rect(surface, theme.ACCENT if on else theme.PANEL_EDGE, r, 4 if on else 2, border_radius=14)
        ch.x, ch.facing = r.centerx, 1
        ch.state = State.WALK if on else State.IDLE
        ch.state_time = t
        draw_fighter(surface, ch, r.y + 245, t, scale=1.0)
        text(surface, prof["name"], (r.centerx, r.y + 255), 34, theme.TEXT, "midtop")
        style = f"{prof['style']} · {prof['height']:.2f} m" if prof.get("height") else prof["style"]
        text(surface, style, (r.centerx, r.y + 292), 18, theme.MUTED, "midtop", bold=False)
        for j, (lab, v) in enumerate((("VIDA", prof["health"] / max_hp), ("VELOC.", prof["speed"] / max_sp), ("PODER", prof["power"] / max_pw))):
            yy = r.y + 320 + j * 15
            text(surface, lab, (r.x + 14, yy - 2), 12, theme.MUTED, bold=False, shadow=False)
            pygame.draw.rect(surface, (50, 50, 70), (r.x + 70, yy, 140, 8), border_radius=4)
            pygame.draw.rect(surface, theme.ACCENT, (r.x + 70, yy, int(140 * v), 8), border_radius=4)
    y = 500
    text(surface, "DIFICULTAD", (w // 2, y), 24, theme.MUTED, "center")
    dw = 190
    dx0 = w // 2 - (len(difficulties) * dw) // 2
    for i, (_, label) in enumerate(difficulties):
        r = pygame.Rect(dx0 + i * dw + 10, y + 22, dw - 20, 46)
        on = i == diff_idx
        pygame.draw.rect(surface, (255, 200, 40) if on else (30, 26, 50), r, border_radius=10)
        text(surface, label, r.center, 26, (20, 10, 10) if on else theme.TEXT, "center", shadow=not on)
    text(surface, "←/→ luchador · ↑/↓ dificultad · ENTER combatir · ESC volver", (w // 2, 610), 20, theme.TEXT, "center", bold=False)
    text(surface, "El rival se elige al azar", (w // 2, 640), 16, theme.MUTED, "center", bold=False)


def draw_banner(surface, msg: str, sub: str = "", color=theme.ACCENT, t: float = 0.0):
    w, h = surface.get_size()
    size = int(110 + 8 * math.sin(t * 10))
    text(surface, msg, (w // 2, h // 2 - 70), size, color, "center")
    if sub:
        text(surface, sub, (w // 2, h // 2 + 10), 30, theme.TEXT, "center")


def draw_pause(surface):
    w, h = surface.get_size()
    _overlay(surface)
    text(surface, "PAUSA", (w // 2, h // 2 - 90), 90, theme.ACCENT, "center")
    for i, line in enumerate(("P / ESC  continuar", "R  reiniciar combate", "Q  volver a selección", "C  mostrar/ocultar cámara · M  fuente de movimiento")):
        text(surface, line, (w // 2, h // 2 + i * 36), 24, theme.TEXT, "center", bold=False)


def draw_result(surface, result: str, player, enemy, elapsed: float):
    w, h = surface.get_size()
    _overlay(surface)
    title, col = {"player": ("¡VICTORIA!", theme.OK), "enemy": ("DERROTA", theme.BAD), "draw": ("EMPATE", theme.ACCENT)}[result]
    text(surface, title, (w // 2, 170), 100, col, "center")
    rows = [("Golpes acertados", player.hits_landed, enemy.hits_landed),
            ("Golpes bloqueados", player.hits_blocked, enemy.hits_blocked),
            ("Vida restante", f"{player.health_pct * 100:.0f}%", f"{enemy.health_pct * 100:.0f}%")]
    text(surface, player.name, (w // 2 - 160, 260), 30, theme.P1, "center")
    text(surface, enemy.name, (w // 2 + 160, 260), 30, theme.CPU, "center")
    for i, (lab, a, b) in enumerate(rows):
        y = 310 + i * 40
        text(surface, lab, (w // 2, y), 20, theme.MUTED, "center", bold=False)
        text(surface, str(a), (w // 2 - 160, y), 26, theme.TEXT, "center")
        text(surface, str(b), (w // 2 + 160, y), 26, theme.TEXT, "center")
    text(surface, f"Duración: {elapsed:.0f} s", (w // 2, 450), 20, theme.MUTED, "center", bold=False)
    text(surface, "R / ENTER revancha   ·   Q selección   ·   ESC salir", (w // 2, 520), 26, theme.TEXT, "center")
