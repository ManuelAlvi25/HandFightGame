"""Protocolo de texto por líneas entre PC y Arduino (igual por TCP/Wi-Fi o por USB serie).

Formato: <COMANDO>[:<arg1>,<arg2>...][*<XX>]\\n   donde XX = XOR de los bytes antes de '*', en hex.

Arduino -> PC                       PC -> Arduino
  HELLO:<placa>,<n_led_j>,<n_led_e>   PING
  D:<cm>          distancia           HP:<vida_j%>,<vida_e%>
  PONG                                 LED:<bits_jugador>,<bits_enemigo>,<crit_j><crit_e>
  ERR:<motivo>                         (bits: '1' encendido, '0' apagado)
"""
from __future__ import annotations

import math

from src.hardware.led_controller import LedFrame


class ProtocolError(ValueError):
    pass


def checksum(payload: str) -> str:
    x = 0
    for b in payload.encode("ascii"):
        x ^= b
    return f"{x:02X}"


def encode(payload: str, use_checksum: bool = True) -> str:
    return f"{payload}*{checksum(payload)}\n" if use_checksum else f"{payload}\n"


def decode(line: str, require_checksum: bool = True) -> tuple[str, list[str]]:
    line = line.strip()
    if not line:
        raise ProtocolError("línea vacía")
    if "*" in line:
        payload, chk = line.rsplit("*", 1)
        if chk.upper() != checksum(payload):
            raise ProtocolError(f"checksum inválido en '{line}'")
    elif require_checksum:
        raise ProtocolError(f"falta checksum en '{line}'")
    else:
        payload = line
    cmd, _, rest = payload.partition(":")
    return cmd.upper(), rest.split(",") if rest else []


def parse_distance(args: list[str]) -> float:
    if len(args) != 1:
        raise ProtocolError("D espera 1 argumento")
    try:
        d = float(args[0])
    except ValueError as e:
        raise ProtocolError(f"distancia no numérica: {args[0]}") from e
    if not math.isfinite(d):
        raise ProtocolError(f"distancia no finita: {args[0]}")
    return d


def health_payload(player_pct: float, enemy_pct: float) -> str:
    clamp = lambda v: int(round(min(1.0, max(0.0, v)) * 100))  # noqa: E731
    return f"HP:{clamp(player_pct)},{clamp(enemy_pct)}"


def leds_payload(frame: LedFrame) -> str:
    bits = lambda t: "".join("1" if b else "0" for b in t) or "0"  # noqa: E731
    return f"LED:{bits(frame.player)},{bits(frame.enemy)},{int(frame.player_critical)}{int(frame.enemy_critical)}"
