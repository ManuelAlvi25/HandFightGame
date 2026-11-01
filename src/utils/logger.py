"""Configuración del registro (consola + logs/game.log)."""
from __future__ import annotations

import logging

from src.utils.config_loader import ROOT


def setup_logging(debug: bool = False) -> None:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_dir / "game.log", mode="w", encoding="utf-8"))
    except OSError:
        pass  # sin permisos de escritura: solo consola
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
