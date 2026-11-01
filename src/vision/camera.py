"""Captura de la cámara web con OpenCV."""
from __future__ import annotations

import logging
import sys

import cv2

log = logging.getLogger(__name__)


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        self.index, self.width, self.height = index, width, height
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        # DirectShow abre mucho más rápido que MSMF en Windows; si falla se usa el backend por defecto.
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
        for backend in backends:
            cap = cv2.VideoCapture(self.index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, _ = cap.read()
                if ok:
                    self.cap = cap
                    log.info("Cámara %d abierta (backend %d)", self.index, backend)
                    return True
            cap.release()
        log.warning("No se pudo abrir la cámara %d", self.index)
        return False

    @property
    def is_open(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def read(self):
        """Devuelve un frame BGR o None."""
        if not self.is_open:
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
