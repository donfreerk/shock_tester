"""
MQTT-Handler für die Fahrwerkstester-Anwendungen.

Dieses Modul bietet eine High-Level-Abstraktion über dem MQTT-Client
mit spezifischen Funktionen für die Fahrwerkstester-Kommunikation.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .client import MqttClient

logger = logging.getLogger(__name__)


class MqttHandler:
    """
    High-Level MQTT-Handler für Fahrwerkstester-Komponenten.

    Diese Klasse bietet:
    - Vordefinierte Topic-Strukturen
    - Typsichere Nachrichtenformate
    - Automatische Serialisierung/Deserialisierung
    - Komponenten-spezifische Funktionen
    """

    # Standard-Topics für Fahrwerkstester
    DEFAULT_TOPICS = {
        # Gemeinsame Topics
        "STATUS": "suspension/status",
        "MEASUREMENTS": "suspension/measurements/processed",
        "TEST_RESULTS": "suspension/test/result",
        "SYSTEM_STATUS": "suspension/system/status",
        "SYSTEM_HEARTBEAT": "suspension/system/heartbeat",
        # Komponenten-spezifische Topics
        "GUI_COMMAND": "suspension/gui/command",
        "SIMULATOR_COMMAND": "suspension/simulator/command",
        "TESTER_COMMAND": "suspension/tester/command",
        "TESTER_STATUS": "suspension/tester/status",
        # Daten-Topics
        "CAN_DATA": "suspension/can_data",
        "RAW_MEASUREMENTS": "suspension/measurements/raw",
        "FULL_TEST_RESULT": "suspension/test/full_result",
    }

    def __init__(
        self,
        client_id: Optional[str] = None,
        host: str = "localhost",
        port: int = 1883,
        app_type: str = "generic",
        topics: Optional[Dict[str, str]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        on_message: Optional[Callable] = None,
    ):
        """
        Initialisiert den MQTT-Handler.

        Args:
            client_id: Eindeutige Client-ID (wird generiert wenn None)
            host: MQTT-Broker Hostname oder IP
            port: MQTT-Broker Port
            app_type: Anwendungstyp ("gui", "simulator", "tester", "bridge")
            topics: Optionale Topic-Überschreibungen
            username: MQTT-Benutzername (optional)
            password: MQTT-Passwort (optional)
            on_message: Callback für eingehende Nachrichten (optional)
        """
        self.app_type = app_type
        self.on_message = on_message

        # Topics zusammenführen
        self.topics = self.DEFAULT_TOPICS.copy()
        if topics:
            self.topics.update(topics)

        # MQTT-Client erstellen
        if not client_id:
            client_id = f"fahrwerkstester_{app_type}_{int(time.time())}"

        self.mqtt_client = MqttClient(
            broker=host,
            port=port,
            client_id=client_id,
            username=username,
            password=password,
        )

        # Callback-Kategorien
        self.category_callbacks: Dict[str, List[Callable]] = {
            "status": [],
            "measurements": [],
            "test_results": [],
            "commands": [],
            "system": [],
            "raw_data": [],
        }

        # App-spezifische Initialisierung
        self._last_heartbeat = 0
        self._heartbeat_interval = 30.0  # Sekunden

    def connect(self, timeout: float = 5.0) -> bool:
        """
        Verbindet mit dem MQTT-Broker und abonniert relevante Topics.

        Args:
            timeout: Verbindungs-Timeout in Sekunden

        Returns:
            bool: True bei erfolgreicher Verbindung
        """
        # Verbindung herstellen
        if not self.mqtt_client.connect(timeout):
            return False

        # App-spezifische Topics abonnieren
        self._subscribe_app_topics()

        # Initial-Status senden
        self.send_status_update("online", "ready")

        return True

    def disconnect(self):
        """Trennt die MQTT-Verbindung."""
        # Offline-Status senden
        try:
            self.send_status_update("offline", "disconnected")
        except:
            pass

        # Verbindung trennen
        self.mqtt_client.disconnect()

    def is_connected(self) -> bool:
        """Prüft ob die Verbindung besteht."""
        return self.mqtt_client.is_connected()

    def add_callback(self, category: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Fügt einen Callback für eine Nachrichtenkategorie hinzu.

        Args:
            category: Kategorie ("status", "measurements", etc.)
            callback: Callback-Funktion
        """
        if category in self.category_callbacks:
            if callback not in self.category_callbacks[category]:
                self.category_callbacks[category].append(callback)
        else:
            logger.warning(f"Unbekannte Callback-Kategorie: {category}")

    def remove_callback(
        self, category: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Entfernt einen Callback.

        Args:
            category: Kategorie
            callback: Zu entfernender Callback
        """
        if category in self.category_callbacks:
            if callback in self.category_callbacks[category]:
                self.category_callbacks[category].remove(callback)

    def publish(
        self, topic: str, message: Dict[str, Any], retain: bool = False
    ) -> bool:
        """
        Veröffentlicht eine Nachricht.

        Args:
            topic: MQTT-Topic
            message: Nachricht als Dictionary
            retain: Retain-Flag

        Returns:
            bool: True bei Erfolg
        """
        # Timestamp hinzufügen wenn nicht vorhanden
        if "timestamp" not in message:
            message["timestamp"] = time.time()

        # App-Type hinzufügen wenn nicht vorhanden
        if "source" not in message:
            message["source"] = self.app_type

        return self.mqtt_client.publish(topic, message, retain=retain)

    def subscribe(self, topic: str, callback: Optional[Callable] = None):
        """
        Abonniert ein Topic.

        Args:
            topic: MQTT-Topic
            callback: Optionaler Callback für dieses Topic
        """
        if callback is None and self.on_message is not None:
            callback = lambda t, m: self.on_message(t, m)

        self.mqtt_client.subscribe(topic, callback)

    def unsubscribe(self, topic: str):
        """
        Beendet das Abonnement eines Topics.

        Args:
            topic: MQTT-Topic
        """
        self.mqtt_client.unsubscribe(topic)

    def send_test_command(
        self,
        command: str,
        position: str,
        method: str = "phase_shift",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Sendet einen Testbefehl.

        Args:
            command: Befehl ("start", "stop", etc.)
            position: Radposition
            method: Testmethode
            parameters: Zusätzliche Parameter

        Returns:
            bool: True bei Erfolg
        """
        message = {"command": command, "position": position, "method": method}

        if parameters:
            message["parameters"] = parameters

        # Topic basierend auf App-Typ wählen
        if self.app_type == "gui":
            topic = self.topics["GUI_COMMAND"]
        elif self.app_type == "simulator":
            topic = self.topics["SIMULATOR_COMMAND"]
        else:
            topic = self.topics["TESTER_COMMAND"]

        return self.publish(topic, message)

    def send_status_update(
        self,
        state: str,
        test_status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Sendet ein Statusupdate.

        Args:
            state: Systemzustand
            test_status: Teststatus
            details: Zusätzliche Details

        Returns:
            bool: True bei Erfolg
        """
        message = {"state": state, "app_type": self.app_type}

        if test_status:
            message["test_status"] = test_status

        if details:
            message.update(details)

        return self.publish(self.topics["STATUS"], message)

    def send_measurement(
        self,
        position: str,
        platform_position: float,
        tire_force: float,
        frequency: float,
        phase_shift: float,
        **kwargs,
    ) -> bool:
        """
        Sendet Messdaten.

        Args:
            position: Radposition
            platform_position: Plattformposition
            tire_force: Reifenkraft
            frequency: Frequenz
            phase_shift: Phasenverschiebung
            **kwargs: Weitere Messwerte

        Returns:
            bool: True bei Erfolg
        """
        message = {
            "event": "test_data",
            "type": "phase_shift",
            "position": position,
            "platform_position": platform_position,
            "tire_force": tire_force,
            "frequency": frequency,
            "phase_shift": phase_shift,
        }

        message.update(kwargs)

        return self.publish(self.topics["MEASUREMENTS"], message)

    def send_test_result(
        self, position: str, method: str, result_data: Dict[str, Any]
    ) -> bool:
        """
        Sendet ein Testergebnis.

        Args:
            position: Radposition
            method: Testmethode
            result_data: Ergebnisdaten

        Returns:
            bool: True bei Erfolg
        """
        message = {"event": "test_result", "position": position, "test_method": method}

        message.update(result_data)

        return self.publish(self.topics["TEST_RESULTS"], message)

    def send_heartbeat(self) -> bool:
        """
        Sendet ein Heartbeat-Signal.

        Returns:
            bool: True bei Erfolg
        """
        current_time = time.time()

        # Nur senden wenn Intervall überschritten
        if current_time - self._last_heartbeat < self._heartbeat_interval:
            return True

        message = {
            "app_type": self.app_type,
            "uptime": current_time - self._last_heartbeat,
            "status": "alive",
        }

        self._last_heartbeat = current_time

        return self.publish(self.topics["SYSTEM_HEARTBEAT"], message)

    def _subscribe_app_topics(self):
        """Abonniert die für die App relevanten Topics."""
        # Basis-Topics die alle Apps empfangen
        base_topics = [self.topics["STATUS"], self.topics["SYSTEM_STATUS"]]

        # App-spezifische Topics
        if self.app_type == "gui":
            app_topics = [
                self.topics["MEASUREMENTS"],
                self.topics["TEST_RESULTS"],
                self.topics["GUI_COMMAND"],
            ]
        elif self.app_type == "simulator":
            app_topics = [
                self.topics["GUI_COMMAND"],
                self.topics["SIMULATOR_COMMAND"],
                self.topics["TESTER_COMMAND"],
            ]
        elif self.app_type == "tester":
            app_topics = [self.topics["TESTER_COMMAND"], self.topics["GUI_COMMAND"]]
        elif self.app_type == "bridge":
            # Bridge abonniert alles
            app_topics = list(self.topics.values())
        else:
            app_topics = []

        # Alle relevanten Topics abonnieren
        for topic in set(base_topics + app_topics):
            callback = self._create_topic_callback(topic)
            self.mqtt_client.subscribe(topic, callback)

    def _create_topic_callback(self, topic: str) -> Callable:
        """Erstellt einen Callback für ein spezifisches Topic."""

        def callback(received_topic: str, payload: Any):
            # Kategorie bestimmen
            category = self._determine_category(topic)

            # Callbacks ausführen
            for cb in self.category_callbacks.get(category, []):
                try:
                    cb(payload)
                except Exception as e:
                    logger.error(f"Fehler in Callback: {e}")

        return callback

    def _determine_category(self, topic: str) -> str:
        """Bestimmt die Kategorie basierend auf dem Topic."""
        if "status" in topic.lower():
            return "status"
        if "measurements/processed" in topic:
            return "measurements"
        if "measurements/raw" in topic:
            return "raw_data"
        if "test/result" in topic:
            return "test_results"
        if "command" in topic:
            return "commands"
        if "system" in topic:
            return "system"
        return "unknown"

    def get_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken zurück.

        Returns:
            Dict mit Statistiken
        """
        stats = self.mqtt_client.get_stats()
        stats["app_type"] = self.app_type
        stats["connected"] = self.is_connected()

        return stats