"""Convierte confianzas de gestos por frame en acciones estables.

- Confirmación temporal: un gesto se activa tras `min_frames` frames y `min_time_ms` por encima
  de `confidence_threshold`.
- Histéresis: se desactiva solo cuando baja de `release_threshold` durante `release_frames` frames.
- Prioridad: si varios gestos están activos, gana el de mayor prioridad (desempate: confianza).
- mode "trigger": dispara su acción una sola vez por activación (hay que soltar el gesto para
  repetir) y respeta `cooldown_ms`. mode "hold": la acción se mantiene mientras el gesto siga activo.
- Sin manos: todo vuelve a estado neutral.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.vision.gesture_recognizer import DETECTORS, HandFeatures, extract_features
from src.vision.hand_tracker import HandData

VALID_MODES = ("trigger", "hold")
VALID_HANDS = ("any", "both", "left", "right")


@dataclass
class GestureDefinition:
    id: str
    name: str
    detector: str
    action: str
    mode: str = "trigger"
    hands: str = "any"
    confidence_threshold: float = 0.75
    release_threshold: float = 0.5
    min_frames: int = 2
    min_time_ms: float = 0.0
    cooldown_ms: float = 0.0
    priority: int = 0
    enabled: bool = True
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.detector not in DETECTORS:
            raise ValueError(f"Gesto '{self.id}': detector desconocido '{self.detector}'. Disponibles: {sorted(DETECTORS)}")
        if self.mode not in VALID_MODES:
            raise ValueError(f"Gesto '{self.id}': mode debe ser {VALID_MODES}")
        if self.hands not in VALID_HANDS:
            raise ValueError(f"Gesto '{self.id}': hands debe ser {VALID_HANDS}")
        if not 0 <= self.release_threshold <= self.confidence_threshold <= 1:
            raise ValueError(f"Gesto '{self.id}': se requiere 0 <= release_threshold <= confidence_threshold <= 1")

    @classmethod
    def from_dict(cls, d: dict) -> "GestureDefinition":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class _Track:
    active: bool = False
    frames: int = 0
    since: float | None = None
    release_frames: int = 0
    confidence: float = 0.0
    fired: bool = False
    last_fire: float = float("-inf")


@dataclass
class GestureOutput:
    dominant: str | None = None
    dominant_name: str = ""
    confidence: float = 0.0
    triggered: list[str] = field(default_factory=list)
    held: frozenset = frozenset()
    confidences: dict = field(default_factory=dict)
    hands: int = 0
    features: list = field(default_factory=list)


class GestureManager:
    def __init__(self, definitions: list[GestureDefinition], feature_params: dict | None = None, release_frames: int = 2):
        self.definitions: list[GestureDefinition] = []
        self.feature_params = feature_params or {}
        self.release_frames = release_frames
        self._tracks: dict[str, _Track] = {}
        self._dominant: str | None = None
        for d in definitions:
            self.register(d)

    @classmethod
    def from_config(cls, cfg: dict) -> "GestureManager":
        defs = [GestureDefinition.from_dict(g) for g in cfg.get("gestures", []) if g.get("enabled", True)]
        return cls(defs, cfg.get("features"), cfg.get("release_frames", 2))

    def register(self, definition: GestureDefinition) -> None:
        if any(d.id == definition.id for d in self.definitions):
            raise ValueError(f"Gesto duplicado: {definition.id}")
        self.definitions.append(definition)
        self._tracks[definition.id] = _Track()

    def reset(self) -> None:
        for k in self._tracks:
            self._tracks[k] = _Track(last_fire=self._tracks[k].last_fire)
        self._dominant = None

    @staticmethod
    def _confidence(defn: GestureDefinition, feats: list[HandFeatures]) -> float:
        det = DETECTORS[defn.detector]
        if defn.hands == "both":
            return min(det(f, defn.params) for f in feats) if len(feats) >= 2 else 0.0
        if defn.hands in ("left", "right"):
            feats = [f for f in feats if f.handedness.lower() == defn.hands]
        return max((det(f, defn.params) for f in feats), default=0.0)

    def update(self, hands: list[HandData], now: float) -> GestureOutput:
        if not hands:
            self.reset()
            return GestureOutput()
        feats = [extract_features(h, self.feature_params) for h in hands]
        confs: dict[str, float] = {}
        for d in self.definitions:
            tr = self._tracks[d.id]
            c = self._confidence(d, feats)
            confs[d.id] = tr.confidence = c
            if not tr.active:
                if c >= d.confidence_threshold:
                    tr.frames += 1
                    tr.since = now if tr.since is None else tr.since
                    if tr.frames >= d.min_frames and (now - tr.since) * 1000 >= d.min_time_ms:
                        tr.active, tr.release_frames, tr.fired = True, 0, False
                else:
                    tr.frames, tr.since = 0, None
            else:
                tr.release_frames = tr.release_frames + 1 if c < d.release_threshold else 0
                if tr.release_frames >= self.release_frames:
                    tr.active, tr.frames, tr.since = False, 0, None

        active = [d for d in self.definitions if self._tracks[d.id].active]
        out = GestureOutput(confidences=confs, hands=len(hands), features=feats)
        if not active:
            self._dominant = None
            return out
        dom = max(active, key=lambda d: (d.priority, self._tracks[d.id].confidence))
        tr = self._tracks[dom.id]
        self._dominant = dom.id
        out.dominant, out.dominant_name, out.confidence = dom.id, dom.name, tr.confidence
        if dom.mode == "hold":
            out.held = frozenset([dom.action])
        elif not tr.fired:
            tr.fired = True  # una activación = como mucho un disparo, aunque esté en cooldown
            if (now - tr.last_fire) * 1000 >= dom.cooldown_ms:
                tr.last_fire = now
                out.triggered.append(dom.action)
        return out
