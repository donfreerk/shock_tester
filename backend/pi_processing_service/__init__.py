"""
Pi Processing Service Package

Hauptservice für Post-Processing der Fahrwerkstester-Messdaten auf dem Raspberry Pi.

Komponenten:
- main: Haupt-Service für MQTT-Integration und Service-Orchestrierung
- processing: Phase-Shift-Berechnung und Datenvalidierung  
- config: Konfigurationsmanagement
- utils: Hilfsfunktionen für Signalverarbeitung

Verwendung:
    # Service direkt starten
    python -m backend.pi_processing_service.main
    
    # Oder als Service verwenden
    from backend.pi_processing_service import PiProcessingService
    service = PiProcessingService()
    await service.start()
"""

from .main import PiProcessingService

__version__ = "1.0.0"
__author__ = "Fahrwerkstester Team"

# Public API
__all__ = [
    "PiProcessingService"
]
