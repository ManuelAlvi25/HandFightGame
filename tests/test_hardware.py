"""Protocolo, simulador y enlace Arduino contra un Arduino simulado en memoria."""
import random

import pytest

from src.hardware import create_hardware
from src.hardware.arduino_wifi import ArduinoLink, Transport, _LineBuffer
from src.hardware.hardware_interface import ConnectionStatus
from src.hardware.hardware_simulator import SimulatedHardware
from src.hardware.led_controller import LedFrame
from src.hardware.protocol import ProtocolError, checksum, decode, encode, leds_payload, parse_distance

CFG = {"transport": "tcp", "tcp": {"host": "x", "port": 1},
       "protocol": {"checksum": True, "ping_interval": 1.0, "timeout": 3.0, "reconnect_interval": 2.0, "send_interval": 0.1}}


def test_protocol_roundtrip_and_checksum():
    line = encode("D:23.5")
    assert line == f"D:23.5*{checksum('D:23.5')}\n"
    assert decode(line) == ("D", ["23.5"])
    assert decode("PONG", require_checksum=False) == ("PONG", [])
    with pytest.raises(ProtocolError):
        decode("D:23.5*00")
    with pytest.raises(ProtocolError):
        decode("D:23.5")
    for bad in (["abc"], ["nan"], [], ["1", "2"]):
        with pytest.raises(ProtocolError):
            parse_distance(bad)


def test_led_payload():
    f = LedFrame((True, True, False), (True, False, False, False), True, False)
    assert leds_payload(f) == "LED:110,1000,10"


def test_line_buffer_handles_partial_lines():
    b = _LineBuffer()
    assert b.feed(b"D:1") == []
    assert b.feed(b"0*AB\nPON") == ["D:10*AB"]
    assert b.feed(b"G\n") == ["PONG"]


def test_simulator():
    hw = SimulatedHardware({"initial_cm": 25, "noise_cm": 0}, {"min_cm": 10, "max_cm": 60})
    assert hw.read_distance() is None          # aún no conectado
    hw.connect()
    assert hw.status == ConnectionStatus.SIMULATED and hw.read_distance() == 25
    hw.adjust(100)
    assert hw.read_distance() == 60            # limitado al rango calibrado
    hw.send_leds(LedFrame((True,), (False,)))
    assert hw.last_tx == "LED:1,0,00"
    bad = SimulatedHardware({"invalid_rate": 1.0}, {"min_cm": 10, "max_cm": 60}, random.Random(0))
    bad.connect()
    assert bad.read_distance() == -1.0


def test_factory_selects_mode():
    base = {"ultrasonic": {"min_cm": 10, "max_cm": 60}, **CFG}
    assert isinstance(create_hardware({**base, "mode": "simulation"}), SimulatedHardware)
    assert isinstance(create_hardware({**base, "mode": "hardware"}), ArduinoLink)


class FakeArduino(Transport):
    """Imita el firmware: responde PONG, guarda lo recibido, puede fallar o enmudecer."""

    def __init__(self):
        self.opened = False
        self.fail_open = False
        self.mute = False
        self.inbox: list[str] = []
        self.received: list[str] = []
        self.opens = 0

    def open(self):
        self.opens += 1
        if self.fail_open:
            raise OSError("host inalcanzable")
        self.opened = True
        if not self.mute:
            self.inbox.append(encode("HELLO:TEST,5,5").strip())

    def close(self):
        self.opened = False

    def write(self, data):
        for line in data.splitlines():
            cmd, _ = decode(line)
            self.received.append(line)
            if cmd == "PING" and not self.mute:
                self.inbox.append(encode("PONG").strip())

    def read_lines(self):
        out, self.inbox = self.inbox, []
        return out

    @property
    def is_open(self):
        return self.opened


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


def test_link_connects_receives_distance_and_sends_state():
    fake, clk = FakeArduino(), Clock()
    link = ArduinoLink(CFG, fake, clk)
    link.step()
    link.step()
    assert link.status == ConnectionStatus.CONNECTED and link.board == "TEST"
    fake.inbox.append(encode("D:33.3").strip())
    link.step()
    assert link.read_distance() == pytest.approx(33.3)
    link.send_health(0.75, 0.4)
    link.send_leds(LedFrame((True, False), (False, False), True, False))
    clk.t = 0.2
    link.step()
    sent = [decode(l)[0] + ":" + ",".join(decode(l)[1]) for l in fake.received]
    assert "HP:75,40" in sent and "LED:10,00,10" in sent
    n = len(fake.received)
    clk.t = 0.4
    link.step()
    assert len(fake.received) == n           # sin cambios: no reenvía


def test_link_counts_corrupted_messages():
    fake, clk = FakeArduino(), Clock()
    link = ArduinoLink(CFG, fake, clk)
    link.step()
    fake.inbox += ["D:10*00", "BASURA", encode("D:abc").strip()]
    link.step()
    assert link.errors == 3 and link.status == ConnectionStatus.CONNECTED


def test_link_detects_lost_connection_and_reconnects():
    fake, clk = FakeArduino(), Clock()
    link = ArduinoLink(CFG, fake, clk)
    link.step()
    fake.inbox.append(encode("D:20").strip())
    link.step()
    fake.mute = True
    for i in range(1, 40):
        clk.t = i * 0.1
        link.step()
    assert link.status == ConnectionStatus.ERROR and "sin respuesta" in link.last_error
    assert link.read_distance() is None
    assert fake.opens == 1                    # no reintenta antes de reconnect_interval
    fake.mute = False
    clk.t = 7.0
    link.step()
    link.step()
    assert link.status == ConnectionStatus.CONNECTED and fake.opens == 2


def test_link_open_failure_retries_after_interval():
    fake, clk = FakeArduino(), Clock()
    fake.fail_open = True
    link = ArduinoLink(CFG, fake, clk)
    link.step()
    assert link.status == ConnectionStatus.ERROR and "no se pudo conectar" in link.last_error
    clk.t = 1.0
    link.step()
    assert fake.opens == 1                    # espera reconnect_interval
    clk.t = 2.1
    link.step()
    assert fake.opens == 2


def test_real_tcp_unreachable_does_not_raise():
    cfg = {**CFG, "tcp": {"host": "127.0.0.1", "port": 9, "connect_timeout": 0.3}}
    link = ArduinoLink(cfg)
    link.step()
    assert link.status == ConnectionStatus.ERROR
