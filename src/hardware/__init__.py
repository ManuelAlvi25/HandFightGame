from src.hardware.hardware_interface import ConnectionStatus, HardwareInterface


def create_hardware(cfg: dict) -> HardwareInterface:
    """Fábrica según hardware_config.json -> mode."""
    if cfg.get("mode", "simulation") == "hardware":
        from src.hardware.arduino_wifi import ArduinoLink
        return ArduinoLink(cfg)
    from src.hardware.hardware_simulator import SimulatedHardware
    return SimulatedHardware(cfg.get("simulation", {}), cfg["ultrasonic"])


__all__ = ["ConnectionStatus", "HardwareInterface", "create_hardware"]
