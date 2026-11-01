"""Arena: límites del escenario y fondo generado por código."""
from __future__ import annotations

import random
from dataclasses import dataclass

import pygame


@dataclass
class Arena:
    width: int
    height: int
    left: float
    right: float
    floor_y: float

    def render_background(self) -> pygame.Surface:
        w, h, fy = self.width, self.height, int(self.floor_y)
        surf = pygame.Surface((w, h))
        top, horizon = (14, 8, 38), (150, 50, 90)
        for y in range(fy):
            k = y / fy
            surf.fill(tuple(int(top[i] + (horizon[i] - top[i]) * k ** 1.6) for i in range(3)), (0, y, w, 1))
        pygame.draw.circle(surf, (255, 190, 120), (w * 3 // 4, fy - 250), 70)
        pygame.draw.circle(surf, (255, 220, 160), (w * 3 // 4, fy - 250), 56)
        rng = random.Random(7)
        for layer, (col, hmin, hmax) in enumerate((((48, 22, 70), 120, 260), ((28, 14, 44), 70, 190))):
            x = -20
            while x < w:
                bw = rng.randint(50, 120)
                bh = rng.randint(hmin, hmax)
                pygame.draw.rect(surf, col, (x, fy - 40 - bh, bw, bh + 40))
                if layer == 1:
                    for wy in range(fy - 30 - bh, fy - 50, 18):
                        for wx in range(x + 8, x + bw - 10, 16):
                            if rng.random() < 0.35:
                                surf.fill(rng.choice([(255, 210, 110), (255, 170, 80), (120, 200, 255)]), (wx, wy, 6, 8))
                x += bw + rng.randint(0, 12)
        # suelo con perspectiva
        for y in range(fy - 20, h):
            k = (y - fy + 20) / (h - fy + 20)
            surf.fill((int(60 - 30 * k), int(36 - 20 * k), int(70 - 30 * k)), (0, y, w, 1))
        cx = w // 2
        for i in range(-12, 13):
            pygame.draw.line(surf, (90, 60, 110), (cx + i * 40, fy - 20), (cx + i * 160, h), 1)
        for y in (fy - 20, fy + 14, fy + 60, fy + 120):
            pygame.draw.line(surf, (90, 60, 110), (0, y), (w, y), 1)
        pygame.draw.line(surf, (255, 80, 200), (0, fy - 20), (w, fy - 20), 3)
        # focos
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        for x in (w // 5, w // 2, w * 4 // 5):
            pygame.draw.polygon(glow, (255, 240, 200, 22), [(x - 20, 0), (x + 20, 0), (x + 170, fy + 10), (x - 170, fy + 10)])
        surf.blit(glow, (0, 0))
        # límites de la arena
        for x in (self.left - 45, self.right + 45):
            pygame.draw.rect(surf, (35, 20, 50), (x - 6, fy - 140, 12, 130))
            pygame.draw.circle(surf, (255, 80, 200), (int(x), fy - 140), 8)
        return surf
