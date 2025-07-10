#!/usr/bin/env python3
"""
Windows-kompatibles Testprogramm für den CAN-Simulator.

Dieses Skript demonstriert die Verwendung des CAN-Simulators unter Windows,
ohne dass ein echtes CAN-Interface benötigt wird.
"""

import logging

# Windows-spezifische Importpfade
# Angepasst an die aktuelle Struktur während der Refaktorierung
try:
    # Neue Paketstruktur verwenden
    from fahrwerkstester.backend.can_simulator_service.core.simulator import CanSimulator
except ImportError:
    # Fallback auf alte Paketstruktur
    from suspension_tester.can_simulator.simulator import CanSimulator

logger = logging.getLogger(__name__)


class WindowsCanInterface:
    """
    Windows-kompatible Version des CAN-Interfaces ohne Abhängigkeit von python-can.

    Diese Klasse bietet die gleiche Schnittstelle wie SimulatedCanInterface,
    funktioniert aber ohne python-can und ist damit besonders für Windows-Systeme
    ohne CAN-Treiber geeignet.
    """

    def __init__(self, simulation_profile="eusama", message_interval=0.001):
        """
        Initialisiert den Windows-CAN-Simulator.

        Args:
                simulation_profile: Art der zu simulierenden Daten ("eusama" oder "asa")
                message_interval: Zeit zwischen Nachrichten in Sekunden
        """
        self.profile = simulation_profile
        self.message_interval = message_interval
        self.running = False
        self.thread = None
        self.callbacks = []

        # Status-Attribute (kompatibel zu CanInterface)
        self.connected = True  # Immer "verbunden" im Simulationsmodus
        self.current_baudrate = 1000000  # Simulierte Baudrate

        # Simulator erstellen
        self.simulator = CanSimulator(
            profile=simulation_profile, message_interval=message_interval
        )

        # Log-Daten für Protokollierung
        self.log_data = []
        self.max_log_size = 1000

    def connect(self, baudrate=1000000):
        """Simuliert eine Verbindung zum CAN-Bus"""
        self.connected = True
        self.current_baudrate = baudrate
        return True

    def send_message(self, arbitration_id, data, is_extended_id=False, **kwargs):
        """Sendet eine CAN-Nachricht an den simulierten Bus"""
        if isinstance(data, list):
            data = bytes(data)
        # Nachricht durch Simulator verarbeiten lassen
        self.simulator.process_message(arbitration_id, data, is_extended_id)
        return True

    def recv_message(self, timeout=0.1):
        """Empfängt eine simulierte CAN-Nachricht"""
        return self.simulator.get_next_message(timeout)

    def add_message_callback(self, callback):
        """Fügt einen Callback für empfangene Nachrichten hinzu"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            self.simulator.add_message_callback(callback)

    def remove_message_callback(self, callback):
        """Entfernt einen zuvor hinzugefügten Callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            self.simulator.remove_message_callback(callback)

    def shutdown(self):
        """Beendet die Simulation und gibt Ressourcen frei"""
        self.simulator.stop()
        self.connected = False
        logger.info("Windows CAN-Simulator heruntergefahren")