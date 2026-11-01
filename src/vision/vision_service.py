"""Hilo de visión: cámara -> MediaPipe -> gestos, desacoplado del bucle del juego.

El juego solo lee `snapshot()` (estado más reciente) y `drain_triggers()` (acciones disparadas
desde la última lectura), así que la detección nunca bloquea el renderizado.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

import numpy as np

from src.vision.gesture_manager import GestureManager

log = logging.getLogger(__name__)


class CameraStatus(str, Enum):
    DISABLED = "desactivada"
    STARTING = "iniciando"
    ACTIVE = "activa"
    NO_CAMERA = "sin cámara"
    ERROR = "error"


@dataclass(frozen=True)
class VisionSnapshot:
    status: CameraStatus = CameraStatus.DISABLED
    gesture_id: str | None = None
    gesture_name: str = ""
    confidence: float = 0.0
    held: frozenset = frozenset()
    hands: int = 0
    hand_x: float | None = None     # 0 = izquierda, 1 = derecha (vista espejo)
    hand_y: float | None = None
    proximity: float = 0.0          # 0 = lejos, 1 = muy cerca de la cámara
    fps: float = 0.0
    error: str = ""
    debug_frame: np.ndarray | None = None  # RGB pequeño para el panel


class VisionService:
    PANEL_SIZE = (320, 240)

    def __init__(self, cfg: dict, manager: GestureManager):
        self.cfg = cfg
        self.manager = manager
        self.want_debug_frame = True
        self._lock = threading.Lock()
        self._snap = VisionSnapshot(status=CameraStatus.STARTING)
        self._triggers: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- API para el juego --------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="vision", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def snapshot(self) -> VisionSnapshot:
        with self._lock:
            return self._snap

    def drain_triggers(self) -> list[str]:
        with self._lock:
            t, self._triggers = self._triggers, []
        return t

    # --- hilo ----------------------------------------------------------------
    def _publish(self, **kw) -> None:
        with self._lock:
            self._snap = VisionSnapshot(**kw)

    def _run(self) -> None:
        import cv2

        from src.vision.camera import Camera
        from src.vision.hand_tracker import HandTracker

        c = self.cfg
        retry = c.get("retry_seconds", 3.0)
        cam = Camera(c.get("camera_index", 0), c.get("width", 640), c.get("height", 480))
        tracker = None
        fails, fps, t_prev = 0, 0.0, time.perf_counter()
        show_cv = c.get("opencv_debug_window", False)

        while not self._stop.is_set():
            if not cam.is_open:
                self._publish(status=CameraStatus.STARTING)
                if not cam.open():
                    self._publish(status=CameraStatus.NO_CAMERA, error=f"Cámara {cam.index} no disponible; reintento en {retry:.0f}s")
                    self._stop.wait(retry)
                    continue
                fails = 0
            if tracker is None:
                try:
                    tracker = HandTracker(c.get("max_hands", 2), c.get("model_complexity", 0),
                                          c.get("min_detection_confidence", 0.6), c.get("min_tracking_confidence", 0.5))
                except Exception as e:  # mediapipe ausente o roto
                    log.exception("Fallo al iniciar MediaPipe")
                    self._publish(status=CameraStatus.ERROR, error=f"MediaPipe: {e}")
                    self._stop.wait(retry)
                    continue

            frame = cam.read()
            if frame is None:
                fails += 1
                if fails > 30:
                    log.warning("La cámara dejó de entregar imágenes; reabriendo")
                    cam.release()
                    self.manager.reset()
                    self._publish(status=CameraStatus.NO_CAMERA, error="La cámara dejó de responder")
                time.sleep(0.01)
                continue
            fails = 0
            if c.get("mirror", True):
                frame = cv2.flip(frame, 1)

            try:
                hands = tracker.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            except Exception as e:
                log.exception("MediaPipe falló procesando un frame")
                tracker.close()
                tracker = None
                self.manager.reset()
                self._publish(status=CameraStatus.ERROR, error=f"MediaPipe: {e}")
                continue

            out = self.manager.update(hands, time.monotonic())
            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(1e-3, now - t_prev))
            t_prev = now

            hand_x = hand_y = None
            proximity = 0.0
            if hands:
                main = max(hands, key=lambda h: h.size)  # la mano más cercana
                hand_x, hand_y = main.center
                proximity = min(1.0, max(0.0, (main.size - 0.15) / 0.45))

            debug = None
            if self.want_debug_frame or show_cv:
                tracker.draw_last(frame)
                self._annotate(cv2, frame, out)
                if show_cv:
                    cv2.imshow("Gesture Fighter - camara", frame)
                    cv2.waitKey(1)
                if self.want_debug_frame:
                    debug = cv2.cvtColor(cv2.resize(frame, self.PANEL_SIZE), cv2.COLOR_BGR2RGB)

            with self._lock:
                self._triggers.extend(out.triggered)
                self._snap = VisionSnapshot(CameraStatus.ACTIVE, out.dominant, out.dominant_name, out.confidence,
                                            out.held, out.hands, hand_x, hand_y, proximity, fps, "", debug)

        cam.release()
        if tracker:
            tracker.close()
        if show_cv:
            cv2.destroyAllWindows()

    @staticmethod
    def _annotate(cv2, frame, out) -> None:
        label = f"{out.dominant_name or 'neutral'} {out.confidence:.2f}"
        cv2.putText(frame, label, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4)
        cv2.putText(frame, label, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (80, 255, 120), 2)
        # ratios crudos de la primera mano, para calibrar gesture_config.json
        if out.features:
            r = out.features[0].ratios
            txt = " ".join(f"{k[0].upper()}{v:.2f}" for k, v in r.items())
            cv2.putText(frame, txt, (10, frame.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
            cv2.putText(frame, txt, (10, frame.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
