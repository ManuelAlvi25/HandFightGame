"""HUD: barras de vida animadas, nombres, tiempo y panel de estado (gesto, cámara, Arduino, LEDs, sensor)."""
from __future__ import annotations

import pygame

from src.ui import theme
from src.ui.theme import text


class HealthBar:
    def __init__(self, rect: pygame.Rect, anchor_right: bool):
        self.rect = rect
        self.anchor_right = anchor_right  # True: la barra se vacía hacia la derecha (pegada al reloj)
        self.reset()

    def reset(self):
        self.shown = self.trail = 1.0
        self.delay = 0.0

    def update(self, pct: float, dt: float):
        if pct < self.shown - 1e-4:
            self.delay = 0.45
        self.shown += (pct - self.shown) * min(1.0, dt * 18)
        if self.trail > self.shown:
            self.delay -= dt
            if self.delay <= 0:
                self.trail = max(self.shown, self.trail - dt * 0.6)
        else:
            self.trail = self.shown

    def _part(self, frac):
        r = self.rect
        w = int(r.w * max(0.0, min(1.0, frac)))
        return pygame.Rect(r.right - w if self.anchor_right else r.x, r.y, w, r.h)

    def draw(self, surface, t: float):
        r = self.rect
        pygame.draw.rect(surface, (40, 10, 20), r.inflate(8, 8), border_radius=6)
        pygame.draw.rect(surface, (70, 20, 30), r)
        pygame.draw.rect(surface, (255, 240, 240), self._part(self.trail))
        pct = self.shown
        col = (60, 220, 90) if pct > 0.5 else (240, 200, 40) if pct > 0.25 else (240, 50, 40)
        if pct <= 0.25 and int(t * 6) % 2:
            col = (255, 120, 90)
        fill = self._part(pct)
        pygame.draw.rect(surface, col, fill)
        pygame.draw.rect(surface, tuple(min(255, c + 60) for c in col), (fill.x, fill.y, fill.w, fill.h // 3))
        for i in range(1, 10):
            x = r.x + r.w * i // 10
            pygame.draw.line(surface, (0, 0, 0), (x, r.y), (x, r.bottom), 1)
        pygame.draw.rect(surface, (255, 215, 80), r.inflate(8, 8), 3, border_radius=6)


class HUD:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        bw = 470
        self.p_bar = HealthBar(pygame.Rect(width // 2 - 70 - bw, 28, bw, 30), anchor_right=True)
        self.e_bar = HealthBar(pygame.Rect(width // 2 + 70, 28, bw, 30), anchor_right=False)
        self.panel = pygame.Rect(0, height - 118, width, 118)
        self.slider = pygame.Rect(width - 395, height - 32, 300, 14)

    def reset(self):
        self.p_bar.reset()
        self.e_bar.reset()

    def update(self, player, enemy, dt):
        self.p_bar.update(player.health_pct, dt)
        self.e_bar.update(enemy.health_pct, dt)

    def draw_top(self, surface, player, enemy, time_left: float, t: float):
        self.p_bar.draw(surface, t)
        self.e_bar.draw(surface, t)
        text(surface, player.name, (self.p_bar.rect.x, self.p_bar.rect.bottom + 8), 26, theme.P1)
        text(surface, "P1", (self.p_bar.rect.right, self.p_bar.rect.bottom + 8), 20, theme.MUTED, "topright")
        text(surface, enemy.name, (self.e_bar.rect.right, self.e_bar.rect.bottom + 8), 26, theme.CPU, "topright")
        text(surface, "CPU", (self.e_bar.rect.x, self.e_bar.rect.bottom + 8), 20, theme.MUTED)
        box = pygame.Rect(0, 0, 96, 66)
        box.midtop = (self.w // 2, 12)
        pygame.draw.rect(surface, (20, 15, 40), box, border_radius=10)
        pygame.draw.rect(surface, theme.ACCENT, box, 3, border_radius=10)
        col = theme.BAD if time_left <= 10 else theme.TEXT
        text(surface, f"{int(time_left + 0.999):02d}", box.center, 46, col, "center")

    def draw_panel(self, surface, vision, hw, leds, sensor_cm, movement, t, fps, sim: bool):
        p = self.panel
        s = pygame.Surface(p.size, pygame.SRCALPHA)
        s.fill((14, 12, 30, 225))
        surface.blit(s, p.topleft)
        pygame.draw.line(surface, theme.PANEL_EDGE, p.topleft, p.topright, 2)
        y0 = p.y + 10

        # --- Gesto y cámara
        x = 16
        text(surface, "GESTO", (x, y0), 16, theme.MUTED)
        name = vision.gesture_name or ("sin mano" if vision.hands == 0 else "neutral")
        gcol = {"fist": theme.CPU, "open_palm": theme.P1}.get(vision.gesture_id, theme.TEXT)
        text(surface, name.upper(), (x, y0 + 18), 30, gcol)
        bar = pygame.Rect(x, y0 + 56, 200, 10)
        pygame.draw.rect(surface, (50, 50, 70), bar, border_radius=4)
        pygame.draw.rect(surface, gcol, (bar.x, bar.y, int(bar.w * vision.confidence), bar.h), border_radius=4)
        held = ", ".join(sorted(vision.held)) or "-"
        text(surface, f"manos: {vision.hands}   acción: {held}", (x, y0 + 72), 15, theme.MUTED, bold=False)
        cs = vision.status.value
        pygame.draw.circle(surface, theme.status_color(cs), (x + 6, y0 + 98), 6)
        msg = f"Cámara: {cs}" + (f" ({vision.fps:.0f} fps)" if cs == "activa" else "")
        text(surface, msg, (x + 18, y0 + 89), 15, theme.TEXT, bold=False)

        # --- LEDs + Arduino
        x = 410
        text(surface, "LEDS DE VIDA" + (" (simulados)" if sim else ""), (x, y0), 16, theme.MUTED)
        if leds:
            for row, (lab, bits, crit, col) in enumerate((("P1", leds.player, leds.player_critical, (60, 230, 90)),
                                                         ("CPU", leds.enemy, leds.enemy_critical, (255, 70, 60)))):
                yy = y0 + 32 + row * 28
                text(surface, lab, (x, yy - 10), 16, theme.P1 if row == 0 else theme.CPU)
                for i, on in enumerate(bits):
                    c = (x + 58 + i * 26, yy)
                    lc = (255, 60, 40) if crit else col
                    if on:
                        glow = pygame.Surface((30, 30), pygame.SRCALPHA)
                        pygame.draw.circle(glow, (*lc, 70), (15, 15), 14)
                        surface.blit(glow, (c[0] - 15, c[1] - 15))
                    pygame.draw.circle(surface, lc if on else (45, 40, 55), c, 8)
                    pygame.draw.circle(surface, (0, 0, 0), c, 8, 2)
                if crit:
                    text(surface, "¡CRÍTICO!", (x + 66 + len(bits) * 26, yy - 9), 15, theme.BAD)
        hs = hw.status.value
        pygame.draw.circle(surface, theme.status_color(hs), (x + 6, y0 + 98), 6)
        err = f" - {hw.last_error}" if hw.last_error and hs != "conectado" and not sim else ""
        text(surface, f"Arduino: {hw.describe()} [{hs}]{err}"[:70], (x + 18, y0 + 89), 15, theme.TEXT, bold=False)

        # --- Movimiento / sensor
        x = self.w - 420
        text(surface, "MOVIMIENTO  [M]", (x, y0), 16, theme.MUTED)
        src = {"ultrasonic": "SENSOR ULTRASÓNICO", "hand": "POSICIÓN DE LA MANO", "keyboard": "TECLADO"}[movement.source]
        text(surface, src, (x, y0 + 18), 22, theme.ACCENT)
        text(surface, f"{fps:.0f} FPS · P pausa · C cámara", (self.w - 12, y0), 14, theme.MUTED, "topright", bold=False)
        dist_txt = f"{sensor_cm:.1f} cm" if sensor_cm is not None else "sin lectura"
        if movement.source == "ultrasonic":
            hint = "arrastra o usa A/D ←/→" if sim else "lectura del Arduino"
            text(surface, f"distancia: {dist_txt}  ·  {hint}", (x, y0 + 48), 15, theme.TEXT, bold=False)
            sl = self.slider
            pygame.draw.rect(surface, (50, 50, 70), sl, border_radius=7)
            if sensor_cm is not None:
                lo, hi = movement.us["min_cm"], movement.us["max_cm"]
                k = min(1.0, max(0.0, (sensor_cm - lo) / (hi - lo)))
                pygame.draw.rect(surface, theme.P1, (sl.x, sl.y, int(sl.w * k), sl.h), border_radius=7)
                pygame.draw.circle(surface, theme.TEXT, (sl.x + int(sl.w * k), sl.centery), 10)
            text(surface, f"{movement.us['min_cm']}", (sl.x - 6, sl.centery), 14, theme.MUTED, "midright", bold=False)
            text(surface, f"{movement.us['max_cm']} cm", (sl.right + 8, sl.centery), 14, theme.MUTED, "midleft", bold=False)
        elif movement.source == "hand":
            pos = f"x={vision.hand_x:.2f}  cercanía={vision.proximity:.2f}" if vision.hand_x is not None else "sin mano (usa A/D)"
            text(surface, f"mano: {pos}", (x, y0 + 48), 15, theme.TEXT, bold=False)
            text(surface, "mueve la mano a izquierda/derecha", (x, y0 + 72), 15, theme.MUTED, bold=False)
        else:
            text(surface, "A/D o ←/→", (x, y0 + 48), 15, theme.TEXT, bold=False)
