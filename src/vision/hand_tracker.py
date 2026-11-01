"""Detección de manos y landmarks con MediaPipe Hands."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class HandData:
    landmarks: np.ndarray  # (21, 3) coordenadas normalizadas (x, y en 0..1 respecto a la imagen)
    handedness: str = "Right"  # "Left" | "Right" (imagen en modo espejo)
    score: float = 1.0

    @property
    def center(self) -> tuple[float, float]:
        x, y = self.landmarks[:, 0], self.landmarks[:, 1]
        return float((x.min() + x.max()) / 2), float((y.min() + y.max()) / 2)

    @property
    def size(self) -> float:
        """Diagonal del recuadro de la mano (0..~1.4). Mayor = más cerca de la cámara."""
        x, y = self.landmarks[:, 0], self.landmarks[:, 1]
        return float(np.hypot(x.max() - x.min(), y.max() - y.min()))


class HandTracker:
    def __init__(self, max_hands: int = 2, model_complexity: int = 0,
                 min_detection_confidence: float = 0.6, min_tracking_confidence: float = 0.5):
        import mediapipe as mp  # import diferido: el juego funciona aunque falte mediapipe

        self._mp_hands = mp.solutions.hands
        self._draw = mp.solutions.drawing_utils
        self._styles = mp.solutions.drawing_styles
        self._hands = self._mp_hands.Hands(
            static_image_mode=False, max_num_hands=max_hands, model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence, min_tracking_confidence=min_tracking_confidence)
        self._last = None

    def process(self, rgb_frame: np.ndarray) -> list[HandData]:
        rgb_frame.flags.writeable = False
        res = self._hands.process(rgb_frame)
        self._last = res
        hands: list[HandData] = []
        if res.multi_hand_landmarks:
            for lms, hd in zip(res.multi_hand_landmarks, res.multi_handedness):
                arr = np.array([[p.x, p.y, p.z] for p in lms.landmark], dtype=np.float32)
                c = hd.classification[0]
                hands.append(HandData(arr, c.label, float(c.score)))
        return hands

    def draw_last(self, bgr_frame: np.ndarray) -> None:
        if self._last is not None and self._last.multi_hand_landmarks:
            for lms in self._last.multi_hand_landmarks:
                self._draw.draw_landmarks(bgr_frame, lms, self._mp_hands.HAND_CONNECTIONS,
                                          self._styles.get_default_hand_landmarks_style(),
                                          self._styles.get_default_hand_connections_style())

    def close(self) -> None:
        self._hands.close()
