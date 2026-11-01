"""Lógica de un luchador: estados, ataques, defensa y vida. Sin dependencias de pygame."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    ATTACK = "attack"
    BLOCK = "block"
    HIT = "hit"
    KO = "ko"
    VICTORY = "victory"


ACTIONABLE = (State.IDLE, State.WALK, State.BLOCK)


@dataclass(frozen=True)
class Move:
    name: str
    damage: float
    startup: float
    active: float
    recovery: float
    reach: float  # distancia máxima centro-a-centro para conectar
    knockback: float = 170.0  # velocidad de empuje inicial (px/s)
    hitstun: float = 0.25

    @property
    def total(self) -> float:
        return self.startup + self.active + self.recovery

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "Move":
        return cls(name=name, **d)


class Character:
    def __init__(self, name: str, x: float, moves: dict[str, Move], health: float = 100, speed: float = 260,
                 power: float = 1.0, block_reduction: float = 0.8, attack_cooldown: float = 0.15,
                 block_move_factor: float = 0.5, facing: int = 1, profile: dict | None = None):
        self.name = name
        self.moves = moves
        self.max_health = float(health)
        self.speed = float(speed)
        self.power = float(power)
        self.block_reduction = block_reduction
        self.attack_cooldown = attack_cooldown
        self.block_move_factor = block_move_factor
        self.profile = profile or {}
        self.reset(x, facing)

    def reset(self, x: float, facing: int = 1) -> None:
        self.x = float(x)
        self.facing = facing
        self.health = self.max_health
        self.state = State.IDLE
        self.state_time = 0.0
        self.move: Move | None = None
        self.has_hit = False
        self.stun = 0.0
        self.cooldown = 0.0
        self.knockback_v = 0.0
        self.flash = 0.0
        self.attacks_started = 0
        self.hits_landed = 0
        self.hits_blocked = 0

    # --- consultas -------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self.health > 0

    @property
    def health_pct(self) -> float:
        return self.health / self.max_health

    @property
    def is_blocking(self) -> bool:
        return self.state == State.BLOCK

    @property
    def attack_phase(self) -> str | None:
        if self.state != State.ATTACK or self.move is None:
            return None
        if self.state_time < self.move.startup:
            return "startup"
        if self.state_time < self.move.startup + self.move.active:
            return "active"
        return "recovery"

    def _set_state(self, s: State) -> None:
        if s != self.state:
            self.state = s
            self.state_time = 0.0

    # --- órdenes ---------------------------------------------------------
    def request_attack(self, move_name: str) -> bool:
        move = self.moves.get(move_name)
        if move is None or not self.alive or self.state not in ACTIONABLE or self.cooldown > 0:
            return False
        self.move = move
        self.has_hit = False
        self.attacks_started += 1
        self._set_state(State.ATTACK)
        return True

    def set_blocking(self, on: bool) -> None:
        if on and self.state in (State.IDLE, State.WALK):
            self._set_state(State.BLOCK)
        elif not on and self.state == State.BLOCK:
            self._set_state(State.IDLE)

    def walk(self, direction: float, dt: float) -> None:
        """direction en [-1, 1]."""
        if self.state in (State.IDLE, State.WALK):
            self.x += direction * self.speed * dt
            self._set_state(State.WALK if abs(direction) > 0.05 else State.IDLE)
        elif self.state == State.BLOCK:
            self.x += direction * self.speed * self.block_move_factor * dt

    def walk_toward(self, target_x: float, dt: float) -> None:
        """Camina hacia target_x sin pasarse, a velocidad máxima limitada."""
        max_step = self.speed * dt * (self.block_move_factor if self.state == State.BLOCK else 1.0)
        dx = target_x - self.x
        direction = 0.0 if abs(dx) < 1.0 or max_step <= 0 else max(-1.0, min(1.0, dx / max_step))
        self.walk(direction, dt)

    def take_hit(self, move: Move, direction: int, damage_mult: float = 1.0) -> tuple[float, bool]:
        """Aplica un golpe. Devuelve (daño aplicado, bloqueado)."""
        if not self.alive:
            return 0.0, False
        blocked = self.state == State.BLOCK
        dmg = move.damage * damage_mult * ((1.0 - self.block_reduction) if blocked else 1.0)
        self.health = max(0.0, self.health - dmg)
        self.knockback_v = direction * move.knockback * (0.35 if blocked else 1.0)
        if blocked:
            self.hits_blocked += 1
        if not self.alive:
            self.move = None
            self._set_state(State.KO)
        elif not blocked:
            self.move = None
            self.stun = move.hitstun
            self.flash = 0.12
            self._set_state(State.HIT)
        return dmg, blocked

    def win(self) -> None:
        if self.alive:
            self.move = None
            self._set_state(State.VICTORY)

    # --- simulación ------------------------------------------------------
    def update(self, dt: float) -> None:
        self.state_time += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        self.flash = max(0.0, self.flash - dt)
        if self.knockback_v:
            self.x += self.knockback_v * dt
            self.knockback_v *= max(0.0, 1.0 - 10.0 * dt)
            if abs(self.knockback_v) < 5:
                self.knockback_v = 0.0
        if self.state == State.ATTACK and self.move and self.state_time >= self.move.total:
            self.move = None
            self.cooldown = self.attack_cooldown
            self._set_state(State.IDLE)
        elif self.state == State.HIT:
            self.stun -= dt
            if self.stun <= 0:
                self._set_state(State.IDLE)


def build_character(cls, profile: dict, moves: dict[str, Move], combat_cfg: dict, x: float, facing: int, **extra):
    """Crea un luchador a partir de una entrada del roster de game_config.json."""
    return cls(name=profile["name"], x=x, moves=moves, health=profile["health"], speed=profile["speed"],
               power=profile["power"], block_reduction=combat_cfg["block_reduction"],
               attack_cooldown=combat_cfg["attack_cooldown"], block_move_factor=combat_cfg["block_move_factor"],
               facing=facing, profile=profile, **extra)
