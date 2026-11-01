"""IA enemiga basada en una máquina de estados finita (sin modelos externos)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from src.game.character import ACTIONABLE, Character, State


class AIState(str, Enum):
    IDLE = "idle"
    APPROACH = "approach"
    ATTACK = "attack"
    DEFEND = "defend"
    RECOVER = "recover"
    RETREAT = "retreat"
    VICTORY = "victory"
    DEFEAT = "defeat"


@dataclass
class AIIntent:
    move: float = 0.0          # -1..1
    attack: str | None = None  # nombre del movimiento
    block: bool = False


DEFAULTS = {
    "reaction_time": 0.15, "aggression": 0.5, "block_chance": 0.4, "error_rate": 0.2,
    "think_time": [0.3, 0.6], "recover_time": [0.5, 0.8], "retreat_chance": 0.3, "speed_factor": 0.9,
    "heavy_chance": 0.15, "combo_chance": 0.2, "block_duration": [0.35, 0.7], "retreat_time": [0.3, 0.7],
}


class EnemyAI:
    def __init__(self, params: dict, rng: random.Random | None = None,
                 arena_left: float = float("-inf"), arena_right: float = float("inf")):
        self.p = {**DEFAULTS, **params}
        self.rng = rng or random.Random()
        self.left, self.right = arena_left, arena_right
        self.reset()

    def reset(self) -> None:
        self.state = AIState.IDLE
        self.timer = 0.4
        self._seen_attack = 0
        self._defend_delay: float | None = None
        self._attack_range = 0.0
        self._attack_id = -1
        self._combo_left = 0
        self._was_hit = False

    def _rand(self, key: str) -> float:
        lo, hi = self.p[key]
        return self.rng.uniform(lo, hi)

    def _enter(self, s: AIState, duration: float = 0.0) -> None:
        self.state = s
        self.timer = duration

    def _start_attack(self, me: Character, chain: bool = False) -> None:
        self._enter(AIState.ATTACK, 0.3)
        self._attack_id = -1
        if not chain:
            self._combo_left = 1 if self.rng.random() < self.p["combo_chance"] else 0

    def _decide(self, me: Character, dist: float, reach: float) -> None:
        r = self.rng.random
        if dist > reach * 0.95:
            # error controlado: a veces ataca desde demasiado lejos y falla
            self._attack_range = reach * (1.6 if r() < self.p["error_rate"] else 0.85)
            self._enter(AIState.APPROACH, 2.0)
        elif r() < self.p["aggression"]:
            self._start_attack(me)
        elif r() < self.p["block_chance"] * 0.5:
            self._enter(AIState.DEFEND, self._rand("block_duration"))
        elif r() < self.p["retreat_chance"]:
            self._enter(AIState.RETREAT, self._rand("retreat_time"))
        else:
            self._enter(AIState.IDLE, self._rand("think_time"))

    def update(self, dt: float, me: Character, opp: Character) -> AIIntent:
        if not me.alive:
            self._enter(AIState.DEFEAT)
            return AIIntent()
        if not opp.alive:
            self._enter(AIState.VICTORY)
            return AIIntent()

        self.timer -= dt
        dist = abs(opp.x - me.x)
        toward = 1 if opp.x >= me.x else -1
        reach = me.moves["punch"].reach
        p = self.p

        # Reacción a un ataque entrante (con tiempo de reacción según dificultad)
        if opp.state == State.ATTACK and opp.attacks_started != self._seen_attack:
            self._seen_attack = opp.attacks_started
            threat = opp.move is not None and dist <= opp.move.reach + 25
            if threat and self.state != AIState.ATTACK and self.rng.random() < p["block_chance"]:
                self._defend_delay = p["reaction_time"]
        if self._defend_delay is not None:
            self._defend_delay -= dt
            if self._defend_delay <= 0:
                self._defend_delay = None
                if me.state in ACTIONABLE:
                    self._enter(AIState.DEFEND, self._rand("block_duration"))

        # Recibió un golpe: retroceder o recuperarse
        hit_now = me.state == State.HIT
        if hit_now and not self._was_hit:
            if self.rng.random() < p["retreat_chance"]:
                self._enter(AIState.RETREAT, self._rand("retreat_time"))
            else:
                self._enter(AIState.RECOVER, self._rand("recover_time") * 0.5)
        self._was_hit = hit_now
        if hit_now:
            return AIIntent()

        intent = AIIntent()
        s = self.state
        if s in (AIState.VICTORY, AIState.DEFEAT):  # revancha sin reset explícito
            self._enter(AIState.IDLE, 0.3)
        elif s == AIState.IDLE:
            if self.timer <= 0:
                self._decide(me, dist, reach)
        elif s == AIState.APPROACH:
            intent.move = toward * p["speed_factor"]
            if dist <= self._attack_range:
                if self.rng.random() < p["aggression"]:
                    self._start_attack(me)
                else:
                    self._enter(AIState.IDLE, self._rand("think_time"))
            elif self.timer <= 0:
                self._enter(AIState.IDLE, 0.0)
        elif s == AIState.ATTACK:
            if self._attack_id < 0:
                if me.state in ACTIONABLE and me.cooldown <= 0:
                    intent.attack = "heavy" if self.rng.random() < p["heavy_chance"] else "punch"
                    self._attack_id = me.attacks_started + 1
                elif self.timer <= 0:
                    self._enter(AIState.RECOVER, self._rand("recover_time"))
            elif me.attacks_started >= self._attack_id and me.state != State.ATTACK:
                if self._combo_left > 0 and dist <= reach:
                    self._combo_left -= 1
                    self._start_attack(me, chain=True)
                else:
                    self._enter(AIState.RECOVER, self._rand("recover_time"))
            elif me.attacks_started < self._attack_id and self.timer <= 0:
                self._enter(AIState.RECOVER, self._rand("recover_time"))  # ataque rechazado
        elif s == AIState.DEFEND:
            intent.block = True
            if self.timer <= 0:
                self._enter(AIState.IDLE, self._rand("think_time") * 0.5)
        elif s == AIState.RECOVER:
            if self.timer <= 0:
                if self.rng.random() < p["retreat_chance"] * 0.5:
                    self._enter(AIState.RETREAT, self._rand("retreat_time"))
                else:
                    self._enter(AIState.IDLE, 0.0)
        elif s == AIState.RETREAT:
            intent.move = -toward * p["speed_factor"] * 0.8
            at_wall = me.x <= self.left + 2 or me.x >= self.right - 2
            if self.timer <= 0 or at_wall:
                self._enter(AIState.IDLE, self._rand("think_time"))
        return intent
