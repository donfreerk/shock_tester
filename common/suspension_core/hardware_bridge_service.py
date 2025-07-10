#!/usr/bin/env python3
"""
Hardware Bridge Service für den Fahrwerkstester.

Dieser Service verbindet die echte CAN-Hardware mit dem MQTT-System
und macht die Hardware vollständig austauschbar mit dem Simulator.
"""

import logging
import threading
import time
from typing import Any, Dict

# Import from the common library
from suspension_core.can.can_interface import CanInterface
from suspension_core.can.converters.json_converter import CanMessageConverter
from suspension_core.config.manager import ConfigManager


from suspension_core.protocols import create_protocol
from suspension_core.protocols.messages import (
    create_measurement_message,
    create_status_message,
)
from common.suspension_core.mqtt.handler import MqttHandler
from test_controller_service.phase_shift_processor import PhaseShiftProcessor

logger = logging.getLogger(__name__)


class HardwareBridge:
    """
    Bridge-Service zwischen CAN-Hardware und MQTT.

    Dieser Service:
    - Empfängt CAN-Nachrichten von der Hardware
    - Konvertiert sie in standardisierte JSON-Formate
    - Publiziert sie über MQTT
    - Empfängt Steuerbefehle über MQTT
    - Leitet sie an die Hardware weiter
    """

    def __init__(self):
        """Initialisiert den Bridge-Service."""
        self.config = ConfigManager()
        self.running = False

        # Hardware-Komponenten
        self.can_interface = None
        self.protocol = None
        self.can_converter = CanMessageConverter()

        # MQTT-Handler
        self.mqtt_handler = MqttHandler(
            broker=self.config.get(["mqtt", "broker"], "localhost"),
            port=self.config.get(["mqtt", "port"], 1883),
            client_id=f"hardware_bridge_{int(time.time())}",
            app_type="bridge",
        )

        # Prozessoren für Datenverarbeitung
        self.phase_shift_processor = PhaseShiftProcessor()

        # Zu        standsvariablen
        self.test_running = False
        self.current_position = None
        self.test_start_time = None
        self.measurement_buffer = []


def start(self):
    """Startet den Bridge-Service."""
    logger.info("Starte Hardware Bridge Service...")

    # CAN-Interface initialisieren
    if not self._init_can_interface():
        logger.error("CAN-Interface konnte nicht initialisiert werden")
        return False

    # MQTT verbinden
    if not self._connect_mqtt():
        logger.error("MQTT-Verbindung fehlgeschlagen")
        return False

    self.running = True

    # Status senden
    self._send_status("online", "ready")

    # Hauptschleife in separatem Thread
    self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
    self.main_thread.start()

    logger.info("Hardware Bridge Service gestartet")
    return True


def stop(self):
    """Stoppt den Bridge-Service."""
    logger.info("Stoppe Hardware Bridge Service...")
    self.running = False

    # Status senden
    self._send_status("offline", "stopped")

    # Verbindungen trennen
    if self.can_interface:
        self.can_interface.shutdown()
    if self.mqtt_handler:
        self.mqtt_handler.disconnect()

    logger.info("Hardware Bridge Service gestoppt")


def _init_can_interface(self) -> bool:
    """Initialisiert die CAN-Schnittstelle."""
    try:
        # CAN-Interface erstellen
        self.can_interface = CanInterface(
            channel=self.config.get(["can", "interface"], "can0"),
            baudrate=self.config.get(["can", "baudrate"], 1000000),
            auto_detect_baud=self.config.get(["can", "auto_detect_baud"], True),
        )

        if not self.can_interface.connected:
            return False

        # Protokoll erstellen
        protocol_type = self.config.get(["can", "protocol"], "eusama")
        self.protocol = create_protocol(protocol_type, self.can_interface)

        # Callbacks registrieren
        self.protocol.register_callbacks()
        self.protocol.add_callback("raw_data", self._on_raw_data)
        self.protocol.add_callback("motor_status", self._on_motor_status)

        return True

    except Exception as e:
        logger.error(f"Fehler bei CAN-Initialisierung: {e}")
        return False


def _connect_mqtt(self) -> bool:
    """Verbindet mit dem MQTT-Broker."""
    try:
        if not self.mqtt_handler.connect():
            return False

        # Callbacks registrieren
        self.mqtt_handler.add_callback("tester_command", self._on_tester_command)
        self.mqtt_handler.add_callback("gui_command", self._on_gui_command)

        return True

    except Exception as e:
        logger.error(f"Fehler bei MQTT-Verbindung: {e}")
        return False


def _main_loop(self):
    """Hauptschleife des Services."""
    while self.running:
        try:
            # Messdaten verarbeiten, wenn Test läuft
            if self.test_running and self.measurement_buffer:
                self._process_measurements()

            # Kurze Pause
            time.sleep(0.01)

        except Exception as e:
            logger.error(f"Fehler in Hauptschleife: {e}")


def _on_raw_data(self, data: Dict[str, Any]):
    """
    Callback für Rohdaten vom CAN-Bus.

    Args:
                    data: Dictionary mit DMS-Werten
    """
    if not self.test_running:
        return

    # Daten in Puffer speichern
    self.measurement_buffer.append({"timestamp": time.time(), "data": data})


def _on_motor_status(self, status: Dict[str, Any]):
    """
    Callback für Motorstatus.

    Args:
                    status: Dictionary mit Motorstatus
    """
    # Status über MQTT publizieren
    mqtt_data = {
        "event": "motor_status",
        "left_running": status.get("left_running", False),
        "right_running": status.get("right_running", False),
        "remaining_time": status.get("remaining_time", 0),
        "timestamp": time.time(),
    }

    self.mqtt_handler.publish("suspension/status", mqtt_data)


def _on_tester_command(self, command: Dict[str, Any]):
    """
    Verarbeitet Befehle für den Tester.

    Args:
                    command: Befehlsnachricht
    """
    cmd = command.get("command")

    if cmd == "start":
        self._start_test(command)
    elif cmd == "stop":
        self._stop_test()


def _on_gui_command(self, command: Dict[str, Any]):
    """
    Verarbeitet GUI-Befehle.

    Args:
                    command: Befehlsnachricht
    """
    # Gleiche Verarbeitung wie Tester-Befehle
    self._on_tester_command(command)


def _start_test(self, command: Dict[str, Any]):
    """Startet einen Test."""
    position = command.get("position", "front_left")
    method = command.get("method", "phase_shift")
    parameters = command.get("parameters", {})

    # Test-Parameter extrahieren
    duration = parameters.get("duration", 30)

    # Position in Seite umwandeln
    side = "left" if "left" in position else "right"

    # Motor starten
    if self.protocol:
        self.protocol.send_motor_command(side, duration)

    # Test-Zustand setzen
    self.test_running = True
    self.current_position = position
    self.test_start_time = time.time()
    self.measurement_buffer.clear()

    # Status senden
    self._send_status(
        "test_running", "running", {"position": position, "method": method}
    )

    logger.info(f"Test gestartet: {position}, Methode: {method}")


def _stop_test(self):
    """Stoppt den laufenden Test."""
    # Motoren stoppen
    if self.protocol:
        self.protocol.send_motor_command("stop", 0)

    # Test-Zustand zurücksetzen
    self.test_running = False

    # Status senden
    self._send_status("idle", "stopped")

    logger.info("Test gestoppt")


def _process_measurements(self):
    """
    Verarbeitet gesammelte Messdaten und publiziert sie über MQTT.
    """
    if not self.measurement_buffer:
        return

    # Aktuelle Daten aus Puffer nehmen
    current_batch = self.measurement_buffer[:10]  # Max 10 pro Durchlauf
    self.measurement_buffer = self.measurement_buffer[10:]

    for measurement in current_batch:
        timestamp = measurement["timestamp"]
        raw_data = measurement["data"]

        # Rohdaten in sinnvolle Werte umwandeln
        side = raw_data.get("side", "left")

        if side == "left":
            platform_pos = (raw_data.get("dms1", 0) + raw_data.get("dms2", 0)) / 2
            tire_force = (raw_data.get("dms3", 0) + raw_data.get("dms4", 0)) / 2
        else:
            platform_pos = (raw_data.get("dms5", 0) + raw_data.get("dms6", 0)) / 2
            tire_force = (raw_data.get("dms7", 0) + raw_data.get("dms8", 0)) / 2

        # Frequenz berechnen (Beispiel)
        elapsed = timestamp - self.test_start_time
        frequency = 25.0 - (elapsed / 30.0) * 19.0  # Linear von 25 Hz auf 6 Hz

        # Standardisierte Messnachricht erstellen
        measurement_message = create_measurement_message(
            position=self.current_position,
            platform_position=platform_pos,
            tire_force=tire_force,
            frequency=frequency,
            phase_shift=45.0,  # Würde berechnet werden
            static_weight=512.0,  # Beispielwert
            elapsed=elapsed,
            timestamp=timestamp,
        )

        # Über MQTT publizieren
        topic = self.mqtt_handler.topics.get(
            "measurement", "fahrwerkstester/measurement"
        )
        self.mqtt_handler.publish(topic, measurement_message)


def _send_status(self, state: str, test_status: str, details: Dict[str, Any] = None):
    """Sendet einen Statusupdate."""
    # Verwende die standardisierte Nachrichtenformat-Funktion
    status_message = create_status_message(
        state=state, test_status=test_status, details=details
    )
    # Sende die Nachricht über den MQTT-Handler
    topic = self.mqtt_handler.topics.get("status", "fahrwerkstester/status")
    self.mqtt_handler.publish(topic, status_message)


def main():
    """Hauptfunktion zum Starten des Bridge-Services."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Service erstellen und starten
    service = HardwareBridge()

    try:
        if service.start():
            logger.info("Bridge-Service läuft. Drücken Sie Strg+C zum Beenden.")
            # Hauptthread am Leben halten
            while True:
                time.sleep(1)
        else:
            logger.error("Bridge-Service konnte nicht gestartet werden")

    except KeyboardInterrupt:
        logger.info("Beende Bridge-Service...")
        service.stop()


if __name__ == "__main__":
    main()