"""Une teclado y gestos en una lista de acciones por frame."""
from __future__ import annotations

import logging

import pygame

from src.game.actions import action_kind

log = logging.getLogger(__name__)


class InputManager:
    def __init__(self, keymap: dict[str, list[str]], vision=None):
        self.vision = vision
        self.keys: dict[str, list[int]] = {}
        for action, names in keymap.items():
            codes = []
            for n in names:
                try:
                    codes.append(pygame.key.key_code(n))
                except ValueError:
                    log.warning("Tecla desconocida en game_config.json: %s", n)
            self.keys[action] = codes
        self._pending: list[str] = []

    def handle_event(self, ev) -> None:
        if ev.type == pygame.KEYDOWN:
            for action, codes in self.keys.items():
                if ev.key in codes and action_kind(action) == "trigger":
                    self._pending.append(action)

    def collect(self) -> tuple[list[str], set[str], float]:
        """(triggers, holds, eje_horizontal) acumulados desde la última llamada."""
        pressed = pygame.key.get_pressed()
        down = lambda a: any(pressed[c] for c in self.keys.get(a, []))  # noqa: E731
        holds = {a for a in self.keys if action_kind(a) == "hold" and down(a)}
        axis = float(down("move_right")) - float(down("move_left"))
        triggers, self._pending = self._pending, []
        if self.vision is not None:
            triggers += self.vision.drain_triggers()
            holds |= self.vision.snapshot().held
        return triggers, holds, axis
