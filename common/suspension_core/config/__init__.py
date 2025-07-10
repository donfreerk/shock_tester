"""
Konfigurationspaket für den Fahrwerkstester.
"""

# Konfigurationsmanager exportieren
# High-Level-Simulator-Konfiguration importieren
from .high_level_config import HIGH_LEVEL_SIMULATOR_CONFIG
from .manager import ConfigManager

# Bestehenden Import für Rückwärtskompatibilität beibehalten
from .settings import (
    API_CONFIG,
    CAN_CONFIG,
    EVALUATION,
    HARDWARE_CONFIG,
    MQTT_CONFIG,
    RESONANCE_PARAMETERS,
    SERVICE_CONFIG,
    TEST_PARAMETERS,
    VEHICLE_TYPES,
)

__all__ = [
    "ConfigManager",
    "MQTT_CONFIG",
    "API_CONFIG",
    "HARDWARE_CONFIG",
    "SERVICE_CONFIG",
    "TEST_PARAMETERS",
    "RESONANCE_PARAMETERS",
    "VEHICLE_TYPES",
    "EVALUATION",
    "CAN_CONFIG",
    "HIGH_LEVEL_SIMULATOR_CONFIG",
]