"""Punto de entrada: python main.py [--no-camera] [--hardware] [--difficulty normal] [--demo]"""
from __future__ import annotations

import argparse
import logging
import sys

from src.utils.config_loader import ConfigError, load_config
from src.utils.logger import setup_logging


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gesture Fighter - juego de peleas 2D controlado por gestos")
    ap.add_argument("--no-camera", action="store_true", help="no usar la cámara (solo teclado)")
    ap.add_argument("--hardware", action="store_true", help="forzar modo hardware (Arduino) aunque la config diga simulación")
    ap.add_argument("--simulation", action="store_true", help="forzar modo simulación de hardware")
    ap.add_argument("--difficulty", choices=["facil", "normal", "dificil"])
    ap.add_argument("--demo", action="store_true", help="el jugador también lo controla la IA (F2 alterna)")
    ap.add_argument("--auto", action="store_true", help="salta los menús y encadena combates")
    ap.add_argument("--frames", type=int, help="salir tras N frames (pruebas)")
    ap.add_argument("--screenshots", help="carpeta donde guardar capturas cada 150 frames")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    setup_logging(args.debug)
    try:
        game_cfg = load_config("game_config.json")
        gesture_cfg = load_config("gesture_config.json")
        hw_cfg = load_config("hardware_config.json")
    except ConfigError as e:
        logging.error("%s", e)
        return 1
    if args.hardware:
        hw_cfg["mode"] = "hardware"
    if args.simulation:
        hw_cfg["mode"] = "simulation"

    from src.game.game import Game  # importa pygame solo después de validar la config

    Game(game_cfg, gesture_cfg, hw_cfg, use_camera=not args.no_camera, demo=args.demo,
         difficulty=args.difficulty).run(max_frames=args.frames, auto=args.auto, screenshot_dir=args.screenshots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
