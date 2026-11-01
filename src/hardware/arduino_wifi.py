"""Enlace con Arduino por Wi-Fi (TCP) o USB serie, usando el protocolo de protocol.py.

La E/S corre en un hilo propio: conexión, reconexión, ping y detección de pérdida de
conexión nunca bloquean el juego. NO probado con hardware físico (no disponible aún).
"""
from __future__ import annotations

import logging
import socket
import threading
import time
from abc import ABC, abstractmethod

from src.hardware.hardware_interface import ConnectionStatus, HardwareInterface
from src.hardware.led_controller import LedFrame
from src.hardware.protocol import ProtocolError, decode, encode, health_payload, leds_payload, parse_distance

log = logging.getLogger(__name__)


class Transport(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def write(self, data: str) -> None: ...

    @abstractmethod
    def read_lines(self) -> list[str]:
        """Líneas completas recibidas (no bloqueante)."""

    @property
    @abstractmethod
    def is_open(self) -> bool: ...


class _LineBuffer:
    def __init__(self):
        self._buf = b""

    def feed(self, data: bytes) -> list[str]:
        self._buf += data
        *lines, self._buf = self._buf.split(b"\n")
        if len(self._buf) > 4096:  # basura sin salto de línea
            self._buf = b""
        return [ln.decode("ascii", "replace").strip() for ln in lines if ln.strip()]


class TcpTransport(Transport):
    def __init__(self, host: str, port: int, connect_timeout: float = 2.0):
        self.host, self.port, self.connect_timeout = host, port, connect_timeout
        self.sock: socket.socket | None = None
        self._lines = _LineBuffer()

    def open(self) -> None:
        s = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        s.setblocking(False)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def write(self, data: str) -> None:
        self.sock.sendall(data.encode("ascii"))

    def read_lines(self) -> list[str]:
        try:
            data = self.sock.recv(4096)
        except BlockingIOError:
            return []
        if not data:
            raise ConnectionError("el Arduino cerró la conexión")
        return self._lines.feed(data)

    @property
    def is_open(self) -> bool:
        return self.sock is not None


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 115200):
        self.port, self.baudrate = port, baudrate
        self.ser = None
        self._lines = _LineBuffer()

    def open(self) -> None:
        import serial  # pyserial

        self.ser = serial.Serial(self.port, self.baudrate, timeout=0, write_timeout=0.5)

    def close(self) -> None:
        if self.ser:
            self.ser.close()
            self.ser = None

    def write(self, data: str) -> None:
        self.ser.write(data.encode("ascii"))

    def read_lines(self) -> list[str]:
        n = self.ser.in_waiting
        return self._lines.feed(self.ser.read(n)) if n else []

    @property
    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open


def create_transport(cfg: dict) -> Transport:
    kind = cfg.get("transport", "tcp")
    if kind == "tcp":
        t = cfg["tcp"]
        return TcpTransport(t["host"], t["port"], t.get("connect_timeout", 2.0))
    if kind == "serial":
        s = cfg["serial"]
        return SerialTransport(s["port"], s.get("baudrate", 115200))
    raise ValueError(f"transport desconocido: {kind} (use 'tcp' o 'serial')")


class ArduinoLink(HardwareInterface):
    def __init__(self, cfg: dict, transport: Transport | None = None, clock=time.monotonic):
        p = cfg.get("protocol", {})
        self.use_checksum = p.get("checksum", True)
        self.ping_interval = p.get("ping_interval", 1.0)
        self.timeout = p.get("timeout", 3.0)
        self.reconnect_interval = p.get("reconnect_interval", 2.0)
        self.send_interval = p.get("send_interval", 0.1)
        self.cfg = cfg
        self.transport = transport or create_transport(cfg)
        self.clock = clock
        self.status = ConnectionStatus.DISCONNECTED
        self.last_error = ""
        self.board = ""
        self.errors = 0
        self._lock = threading.Lock()
        self._distance: float | None = None
        self._distance_time = 0.0
        self._last_rx = 0.0
        self._last_ping = 0.0
        self._last_attempt = float("-inf")
        self._last_send = 0.0
        self._out: dict[str, str] = {}   # último payload por comando, pendiente de enviar
        self._sent: dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def describe(self) -> str:
        if self.cfg.get("transport") == "serial":
            return f"SERIE {self.cfg['serial']['port']}"
        return f"WIFI {self.cfg['tcp']['host']}:{self.cfg['tcp']['port']}"

    # --- HardwareInterface ----------------------------------------------------
    def connect(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="arduino", daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._close("desconectado por el juego")
        self.status = ConnectionStatus.DISCONNECTED

    def read_distance(self) -> float | None:
        with self._lock:
            if self._distance is None or self.clock() - self._distance_time > self.timeout:
                return None
            return self._distance

    def send_leds(self, frame: LedFrame) -> None:
        with self._lock:
            self._out["LED"] = leds_payload(frame)

    def send_health(self, player_pct: float, enemy_pct: float) -> None:
        with self._lock:
            self._out["HP"] = health_payload(player_pct, enemy_pct)

    # --- E/S (llamable directamente en pruebas) -------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            self.step()
            time.sleep(0.01)

    def _close(self, why: str) -> None:
        try:
            self.transport.close()
        except Exception:
            pass
        if why:
            self.last_error = why

    def _fail(self, why: str) -> None:
        log.warning("Arduino: %s", why)
        self.errors += 1
        self._close(why)
        self._last_attempt = self.clock()  # esperar reconnect_interval antes de reintentar
        self.status = ConnectionStatus.ERROR
        with self._lock:
            self._distance = None
            self._sent.clear()

    def _write(self, payload: str) -> None:
        self.transport.write(encode(payload, self.use_checksum))
        self.last_tx = payload

    def step(self) -> None:
        now = self.clock()
        if not self.transport.is_open:
            if now - self._last_attempt < self.reconnect_interval:
                return
            self._last_attempt = now
            self.status = ConnectionStatus.CONNECTING
            try:
                self.transport.open()
            except Exception as e:
                self._fail(f"no se pudo conectar ({e})")
                return
            self._last_rx = self._last_ping = now
            self._write("PING")
        try:
            for line in self.transport.read_lines():
                self._handle(line, now)
            if now - self._last_ping >= self.ping_interval:
                self._last_ping = now
                self._write("PING")
            if now - self._last_send >= self.send_interval:
                self._last_send = now
                with self._lock:
                    pending = {k: v for k, v in self._out.items() if self._sent.get(k) != v}
                for k, v in pending.items():
                    self._write(v)
                    self._sent[k] = v
        except Exception as e:
            self._fail(f"error de comunicación ({e})")
            return
        if now - self._last_rx > self.timeout:
            self._fail(f"sin respuesta durante {self.timeout:.0f}s")

    def _handle(self, line: str, now: float) -> None:
        try:
            cmd, args = decode(line, self.use_checksum)
            if cmd == "D":
                d = parse_distance(args)
                with self._lock:
                    self._distance, self._distance_time = d, now
            elif cmd == "HELLO":
                self.board = args[0] if args else "?"
                log.info("Arduino conectado: %s", ",".join(args))
            elif cmd == "ERR":
                self.errors += 1
                self.last_error = "Arduino: " + ",".join(args)
            elif cmd != "PONG":
                raise ProtocolError(f"comando desconocido: {cmd}")
        except ProtocolError as e:
            self.errors += 1
            self.last_error = str(e)
            return
        self._last_rx = now
        self.status = ConnectionStatus.CONNECTED
