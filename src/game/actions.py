"""Registro de acciones de juego.

Los gestos y las teclas solo producen *nombres* de acción ("attack", "block"...).
Este módulo traduce esos nombres a órdenes sobre el personaje, de modo que añadir un
gesto nuevo no requiere tocar el controlador de combate:

    @register_action("special", "trigger")
    def special(character, active):
        character.request_attack("special")   # y añadir el movimiento en game_config.json

kind = "trigger": se ejecuta una vez por activación.
kind = "hold":    se llama cada frame con active=True/False según se mantenga.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    kind: str
    handler: Callable


ACTIONS: dict[str, ActionSpec] = {}
_warned: set[str] = set()


def register_action(name: str, kind: str):
    if kind not in ("trigger", "hold"):
        raise ValueError(f"Tipo de acción inválido: {kind}")

    def deco(fn):
        ACTIONS[name] = ActionSpec(name, kind, fn)
        return fn
    return deco


def action_kind(name: str) -> str | None:
    spec = ACTIONS.get(name)
    return spec.kind if spec else None


def dispatch(character, triggers: Iterable[str], holds: set[str]) -> list[str]:
    """Aplica las acciones al personaje. Devuelve los triggers ejecutados."""
    done = []
    for name in list(triggers) + [h for h in holds if h not in ACTIONS]:
        spec = ACTIONS.get(name)
        if spec is None:
            if name not in _warned:
                _warned.add(name)
                log.warning("Acción desconocida ignorada: %s", name)
        elif spec.kind == "trigger":
            spec.handler(character, True)
            done.append(name)
    for spec in ACTIONS.values():
        if spec.kind == "hold":
            spec.handler(character, spec.name in holds)
    return done


@register_action("attack", "trigger")
def _attack(character, active):
    character.request_attack("punch")


@register_action("heavy_attack", "trigger")
def _heavy_attack(character, active):
    character.request_attack("heavy")


@register_action("block", "hold")
def _block(character, active):
    character.set_blocking(active)
