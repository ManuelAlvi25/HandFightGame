"""Carga de archivos JSON de configuración."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


class ConfigError(RuntimeError):
    pass


def load_config(name: str, config_dir: Path | str | None = None) -> dict:
    path = Path(config_dir or CONFIG_DIR) / name
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"No existe el archivo de configuración: {path}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSON inválido en {path}: línea {e.lineno}: {e.msg}") from e
