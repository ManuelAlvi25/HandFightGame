"""Panel de depuración con la imagen de la cámara y los landmarks (dentro de la ventana del juego)."""
from __future__ import annotations

import pygame

from src.ui import theme
from src.ui.theme import text


class CameraPanel:
    def __init__(self, rect: pygame.Rect, visible: bool = True):
        self.rect = rect
        self.visible = visible

    def draw(self, surface, snap) -> None:
        if not self.visible:
            return
        r = self.rect
        pygame.draw.rect(surface, (0, 0, 0), r.inflate(6, 6), border_radius=6)
        frame = snap.debug_frame
        if frame is not None:
            h, w = frame.shape[:2]
            img = pygame.image.frombuffer(frame.tobytes(), (w, h), "RGB")
            surface.blit(pygame.transform.smoothscale(img, r.size), r)
        else:
            pygame.draw.rect(surface, (25, 22, 40), r)
            text(surface, f"Cámara: {snap.status.value}", r.center, 18, theme.MUTED, "center")
            if snap.error:
                text(surface, snap.error[:40], (r.centerx, r.centery + 22), 13, theme.BAD, "center", bold=False)
        pygame.draw.rect(surface, theme.status_color(snap.status.value), r.inflate(6, 6), 3, border_radius=6)
