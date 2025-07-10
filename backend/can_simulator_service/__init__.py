# backend/can_simulator_service/__init__.py
"""
EGEA CAN-Simulator Service Package

Modulare Implementierung des Fahrwerkstesters nach hexagonaler Architektur.
Ersetzt die monolithische raspi_can_simulator.py.

Hauptkomponenten:
- core: Domain-Logik (EGEA-Simulation)
- mqtt: Infrastructure (MQTT-Integration)
- main: Application Layer (Service-Orchestrierung)

Verwendung:
    python -m backend.can_simulator_service.main
    python backend/can_simulator_service/
"""

# Nur Core-Domain-Module direkt importieren (keine Infrastructure)
from .core.egea_simulator import EGEASimulator
from .core.config import TestConfiguration, SimulatorConfiguration

__version__ = "2.0.0"
__author__ = "Fahrwerkstester Team"

# Public API (ohne SimulatorMqttAdapter um Zirkularimport zu vermeiden)
__all__ = [
    "EGEASimulator",
    "TestConfiguration", 
    "SimulatorConfiguration"
]

# SimulatorMqttAdapter wird nur bei Bedarf importiert (Lazy Loading)
def create_mqtt_adapter(simulator, mqtt_handler):
    """
    Factory-Funktion für SimulatorMqttAdapter
    Vermeidet Zirkularimporte durch Lazy Loading
    """
    from .mqtt.simulator_adapter import SimulatorMqttAdapter
    return SimulatorMqttAdapter(simulator, mqtt_handler)