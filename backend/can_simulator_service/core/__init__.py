"""
Core Domain Logic für EGEA-Simulator

Enthält die reine Geschäftslogik ohne externe Dependencies:
- EGEASimulator: Hauptsimulator-Klasse
- Konfigurationsklassen
- Domain Events
- Physik-Berechnungen
"""

from .egea_simulator import (
    EGEASimulator,
    DampingQuality,
    DampingParameters,
    SimulationDataPoint,
    EGEASimulationEvent,
    TestStartedEvent,
    TestStoppedEvent,
    DataGeneratedEvent,
    TestCompletedEvent
)
from .config import TestConfiguration, SimulatorConfiguration

__all__ = [
    # Hauptklassen
    "EGEASimulator",
    "TestConfiguration",
    "SimulatorConfiguration",
    
    # Enums und Datenklassen
    "DampingQuality",
    "DampingParameters", 
    "SimulationDataPoint",
    
    # Events
    "EGEASimulationEvent",
    "TestStartedEvent",
    "TestStoppedEvent", 
    "DataGeneratedEvent",
    "TestCompletedEvent"
]