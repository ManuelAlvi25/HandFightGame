"""Luchador controlado por la IA."""
from __future__ import annotations

from src.game.ai import AIIntent, EnemyAI
from src.game.character import Character


class Enemy(Character):
    def __init__(self, *args, ai: EnemyAI, damage_mult: float = 1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai = ai
        self.power *= damage_mult

    def think(self, dt: float, opponent: Character) -> AIIntent:
        intent = self.ai.update(dt, self, opponent)
        apply_intent(self, intent, dt)
        return intent


def apply_intent(ch: Character, intent: AIIntent, dt: float) -> None:
    ch.set_blocking(intent.block)
    if intent.attack:
        ch.request_attack(intent.attack)
    ch.walk(intent.move, dt)
