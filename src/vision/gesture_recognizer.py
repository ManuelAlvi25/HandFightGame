"""Extracción de características de la mano y detectores de gestos registrables.

Un detector es una función (HandFeatures, params) -> confianza 0..1. Para añadir uno:

    @register_detector("pinch")
    def pinch(f, params):
        return 1.0 - f.extension["index"] ...

y referenciarlo desde config/gesture_config.json con "detector": "pinch".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from src.vision.hand_tracker import HandData

WRIST = 0
FINGERS = {  # (mcp, pip, dip, tip)
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
LONG_FINGERS = ("index", "middle", "ring", "pinky")

DEFAULT_FEATURE_PARAMS = {"curled_ratio": 1.15, "extended_ratio": 1.70, "thumb_curled": 0.45, "thumb_extended": 0.80}


@dataclass
class HandFeatures:
    extension: dict[str, float]  # 0 = doblado, 1 = extendido (con tolerancia por rampa lineal)
    ratios: dict[str, float]     # valores crudos, útiles para calibrar
    handedness: str
    center: tuple[float, float]
    size: float


def _ramp(v: float, lo: float, hi: float) -> float:
    return float(min(1.0, max(0.0, (v - lo) / (hi - lo))))


def extract_features(hand: HandData, params: dict | None = None) -> HandFeatures:
    p = {**DEFAULT_FEATURE_PARAMS, **(params or {})}
    lm = hand.landmarks
    d = lambda a, b: float(np.linalg.norm(lm[a] - lm[b])) or 1e-6  # noqa: E731
    palm = d(WRIST, 9)
    ratios, ext = {}, {}
    for name in LONG_FINGERS:
        mcp, _, _, tip = FINGERS[name]
        # punta lejos de la muñeca (relativo a la falange base) => dedo extendido
        ratios[name] = d(tip, WRIST) / d(mcp, WRIST)
        ext[name] = _ramp(ratios[name], p["curled_ratio"], p["extended_ratio"])
    ratios["thumb"] = d(4, 5) / palm  # punta del pulgar respecto a la base del índice
    ext["thumb"] = _ramp(ratios["thumb"], p["thumb_curled"], p["thumb_extended"])
    return HandFeatures(ext, ratios, hand.handedness, hand.center, hand.size)


Detector = Callable[[HandFeatures, dict], float]
DETECTORS: dict[str, Detector] = {}


def register_detector(name: str):
    def deco(fn: Detector) -> Detector:
        DETECTORS[name] = fn
        return fn
    return deco


@register_detector("fist")
def fist(f: HandFeatures, params: dict) -> float:
    w = params.get("thumb_weight", 0.0)
    curl = float(np.mean([1.0 - f.extension[n] for n in LONG_FINGERS]))
    return (1 - w) * curl + w * (1.0 - f.extension["thumb"])


@register_detector("open_palm")
def open_palm(f: HandFeatures, params: dict) -> float:
    w = params.get("thumb_weight", 0.2)
    ext = float(np.mean([f.extension[n] for n in LONG_FINGERS]))
    return (1 - w) * ext + w * f.extension["thumb"]


@register_detector("index_point")
def index_point(f: HandFeatures, params: dict) -> float:
    others = float(np.mean([1.0 - f.extension[n] for n in ("middle", "ring", "pinky")]))
    return f.extension["index"] * others
