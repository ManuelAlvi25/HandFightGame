"""Manos sintéticas y luchadores de prueba."""
import numpy as np

from src.game.character import Character, Move
from src.vision.hand_tracker import HandData

MCP = {"index": (0.44, 0.60), "middle": (0.50, 0.58), "ring": (0.56, 0.60), "pinky": (0.61, 0.63)}
BASE = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}


def make_hand(shape: str = "open", dx: float = 0.0, handedness: str = "Right") -> HandData:
    """shape: open | fist | partial"""
    lm = np.zeros((21, 3), dtype=np.float32)
    lm[0, :2] = (0.5, 0.8)
    lm[1, :2] = (0.42, 0.75)
    lm[2, :2] = (0.37, 0.68)
    lm[3, :2] = (0.31, 0.63) if shape == "open" else (0.42, 0.65)
    lm[4, :2] = (0.25, 0.60) if shape == "open" else (0.47, 0.66)
    offsets = {"open": (-0.08, -0.14, -0.20), "fist": (-0.05, -0.02, 0.04), "partial": (-0.05, -0.08, -0.09)}[shape]
    for f, (x, y) in MCP.items():
        b = BASE[f]
        lm[b, :2] = (x, y)
        for i, off in enumerate(offsets, 1):
            lm[b + i, :2] = (x, y + off)
    lm[:, 0] += dx
    return HandData(lm, handedness, 0.99)


MOVES = {
    "punch": Move("punch", damage=7, startup=0.10, active=0.08, recovery=0.22, reach=125, knockback=0, hitstun=0.28),
    "heavy": Move("heavy", damage=14, startup=0.28, active=0.10, recovery=0.40, reach=140, knockback=0, hitstun=0.45),
}


def fighter(x=0.0, facing=1, cls=Character, **kw):
    return cls("T", x, MOVES, health=kw.pop("health", 100), speed=260, power=1.0, block_reduction=0.8,
               attack_cooldown=0.15, block_move_factor=0.5, facing=facing, **kw)


def step(chars, seconds, dt=1 / 60, each=None):
    for _ in range(int(round(seconds / dt))):
        if each:
            each()
        for c in chars:
            c.update(dt)
