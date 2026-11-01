"""Partículas de impacto, textos flotantes y vibración de pantalla."""
from __future__ import annotations

import math
import random

import pygame


class Effects:
    def __init__(self):
        self.particles: list[list] = []   # [x, y, vx, vy, life, max_life, color, size]
        self.rings: list[list] = []       # [x, y, r, life, max_life, color]
        self.texts: list[list] = []       # [x, y, msg, life, color, size]
        self.shake = 0.0
        self.flash = 0.0

    def clear(self):
        self.__init__()

    def impact(self, x, y, heavy=False):
        n = 26 if heavy else 16
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(150, 520 if heavy else 380)
            col = random.choice([(255, 240, 120), (255, 170, 40), (255, 90, 30), (255, 255, 255)])
            life = random.uniform(0.2, 0.45)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s - 80, life, life, col, random.randint(3, 6)])
        self.rings.append([x, y, 10, 0.25, 0.25, (255, 220, 120)])
        self.shake = max(self.shake, 14 if heavy else 7)

    def block(self, x, y):
        for _ in range(12):
            a = random.uniform(-1.2, 1.2) + (math.pi if random.random() < 0.5 else 0)
            s = random.uniform(120, 300)
            life = random.uniform(0.15, 0.3)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, life, life,
                                   random.choice([(120, 220, 255), (200, 240, 255)]), random.randint(2, 4)])
        self.rings.append([x, y, 14, 0.2, 0.2, (120, 210, 255)])
        self.shake = max(self.shake, 3)

    def ko(self):
        self.flash = 0.35
        self.shake = 20

    def popup(self, x, y, msg, color=(255, 255, 255), size=28):
        self.texts.append([x, y, msg, 0.8, color, size])

    def update(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 900 * dt
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        for r in self.rings:
            r[2] += 420 * dt
            r[3] -= dt
        self.rings = [r for r in self.rings if r[3] > 0]
        for t in self.texts:
            t[1] -= 60 * dt
            t[3] -= dt
        self.texts = [t for t in self.texts if t[3] > 0]
        self.shake = max(0.0, self.shake - 60 * dt)
        self.flash = max(0.0, self.flash - dt)

    def offset(self):
        if self.shake <= 0:
            return 0, 0
        return random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake) * 0.6

    def draw(self, surface, offset=(0, 0)):
        from src.ui.theme import text
        ox, oy = offset
        for x, y, r, life, ml, col in self.rings:
            w = max(1, int(6 * life / ml))
            pygame.draw.circle(surface, col, (x + ox, y + oy), int(r), w)
        for x, y, vx, vy, life, ml, col, size in self.particles:
            k = life / ml
            pygame.draw.line(surface, col, (x + ox, y + oy), (x + ox - vx * 0.03 * k, y + oy - vy * 0.03 * k), max(1, int(size * k)))
        for x, y, msg, life, col, size in self.texts:
            text(surface, msg, (x + ox, y + oy), size, col, anchor="center")
        if self.flash > 0:
            s = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            s.fill((255, 255, 255, int(200 * self.flash / 0.35)))
            surface.blit(s, (0, 0))
