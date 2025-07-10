"""
MQTT Infrastructure für EGEA-Simulator

Verbindet Domain-Logik mit MQTT-Infrastructure:
- SimulatorMqttAdapter: Haupt-MQTT-Adapter
- Event-zu-MQTT Mapping
- Command-Handler
- Status-Publikation
"""

from .simulator_adapter import SimulatorMqttAdapter

__all__ = [
    "SimulatorMqttAdapter"
]
