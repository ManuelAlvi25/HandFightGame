"""Resolución de golpes, colisiones entre luchadores y reglas del combate."""
from __future__ import annotations

from dataclasses import dataclass

from src.game.character import Character


@dataclass
class CombatEvent:
    kind: str  # "hit" | "block" | "ko"
    attacker: Character
    defender: Character
    damage: float
    x: float
    heavy: bool = False


class CombatSystem:
    def __init__(self, left: float, right: float, min_separation: float = 70):
        self.left = left
        self.right = right
        self.min_separation = min_separation

    @staticmethod
    def in_range(attacker: Character, defender: Character) -> bool:
        if attacker.move is None:
            return False
        dx = defender.x - attacker.x
        return dx * attacker.facing > 0 and abs(dx) <= attacker.move.reach

    def resolve(self, a: Character, b: Character) -> list[CombatEvent]:
        events: list[CombatEvent] = []
        for att, dfd in ((a, b), (b, a)):
            if att.attack_phase != "active" or att.has_hit or not dfd.alive or not self.in_range(att, dfd):
                continue
            att.has_hit = True  # un golpe por ataque
            move = att.move
            dmg, blocked = dfd.take_hit(move, att.facing, att.power)
            if not blocked:
                att.hits_landed += 1
            x = (att.x + dfd.x) / 2
            events.append(CombatEvent("block" if blocked else "hit", att, dfd, dmg, x, move.name == "heavy"))
            if not dfd.alive:
                events.append(CombatEvent("ko", att, dfd, dmg, x, move.name == "heavy"))
        return events

    def constrain(self, a: Character, b: Character) -> None:
        """Mantiene a ambos dentro de la arena, sin solaparse, y mirándose."""
        for c in (a, b):
            c.x = min(self.right, max(self.left, c.x))
        dx = b.x - a.x
        if abs(dx) < self.min_separation:
            sign = 1 if dx >= 0 else -1
            push = (self.min_separation - abs(dx)) / 2
            a.x -= sign * push
            b.x += sign * push
            for c in (a, b):
                c.x = min(self.right, max(self.left, c.x))
            if abs(b.x - a.x) < self.min_separation:  # uno quedó contra la pared
                wall_a = a.x <= self.left + 0.5 or a.x >= self.right - 0.5
                if wall_a:
                    b.x = a.x + sign * self.min_separation
                else:
                    a.x = b.x - sign * self.min_separation
        if a.alive and b.alive:
            a.facing = 1 if b.x >= a.x else -1
            b.facing = -a.facing


class Match:
    """Temporizador y condición de victoria de un asalto."""

    def __init__(self, round_time: float):
        self.round_time = round_time
        self.time_left = float(round_time)
        self.result: str | None = None  # "player" | "enemy" | "draw"

    def update(self, dt: float, player: Character, enemy: Character) -> str | None:
        if self.result:
            return self.result
        self.time_left = max(0.0, self.time_left - dt)
        if not player.alive and not enemy.alive:
            self.result = "draw"
        elif not enemy.alive:
            self.result = "player"
        elif not player.alive:
            self.result = "enemy"
        elif self.time_left <= 0:
            p, e = player.health_pct, enemy.health_pct
            self.result = "player" if p > e else "enemy" if e > p else "draw"
        return self.result
