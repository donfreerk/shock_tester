"""
MQTT-Client-Modul für die Fahrwerkstester-Kommunikation.

Dieses Modul bietet eine robuste MQTT-Client-Implementierung mit:
- Automatischer Wiederverbindung
- Thread-sicherer Nachrichtenverarbeitung
- Topic-spezifischen Callbacks
- Wildcard-Unterstützung
"""

import json
import logging
import queue
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttClient:
    """
    Robuste MQTT-Client-Klasse für die Fahrwerkstester-Kommunikation.

    Features:
    - Automatische Wiederverbindung bei Verbindungsverlust
    - Thread-sichere Operationen
    - JSON-Serialisierung/Deserialisierung
    - Topic-basierte Callback-Verwaltung
    - Wildcard-Unterstützung für Topics
    """

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        clean_session: bool = True,
        reconnect_interval: float = 5.0,
        max_reconnect_interval: float = 60.0,
    ):
        """
        Initialisiert den MQTT-Client.

        Args:
                broker: MQTT-Broker Hostname oder IP
                port: MQTT-Broker Port
                client_id: Eindeutige Client-ID (wird generiert wenn None)
                username: MQTT-Benutzername (optional)
                password: MQTT-Passwort (optional)
                clean_session: Ob die Session beim Verbinden bereinigt werden soll
                reconnect_interval: Initiales Wiederverbindungsintervall in Sekunden
                max_reconnect_interval: Maximales Wiederverbindungsintervall in Sekunden
        """
        # Verbindungsparameter
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.clean_session = clean_session

        # Client-ID generieren wenn nicht angegeben
        self.client_id = (
            client_id or f"fahrwerkstester_{random.randint(1000, 9999)}_{int(time.time())}"
        )

        # Wiederverbindungsparameter
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_interval = max_reconnect_interval
        self.current_reconnect_interval = reconnect_interval

        # Zustandsvariablen
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.connecting = False
        self._stop_requested = False

        # Callback-Verwaltung
        self.callbacks: Dict[str, list] = {}
        self._callback_lock = threading.RLock()

        # Thread-Management
        self.reconnect_thread: Optional[threading.Thread] = None
        self.reconnect_event = threading.Event()

        # Statistiken
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "connection_attempts": 0,
            "successful_connections": 0,
        }

    def connect(self, timeout: float = 5.0) -> bool:
        """
        Stellt eine Verbindung zum MQTT-Broker her.

        Args:
                timeout: Maximale Wartezeit für die Verbindung in Sekunden

        Returns:
                bool: True bei erfolgreicher Verbindung, sonst False
        """
        if self.connected:
            logger.warning("Bereits verbunden")
            return True

        if self.connecting:
            logger.warning("Verbindungsversuch läuft bereits")
            return False

        self.connecting = True
        self.stats["connection_attempts"] += 1

        try:
            # MQTT-Client erstellen
            self.client = mqtt.Client(
                client_id=self.client_id, clean_session=self.clean_session, protocol=mqtt.MQTTv311
            )

            # Callbacks setzen
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            # Authentifizierung wenn angegeben
            if self.username:
                self.client.username_pw_set(self.username, self.password)

            # Verbindung herstellen
            logger.info(f"Verbinde mit MQTT-Broker {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, keepalive=60)

            # Event-Loop starten
            self.client.loop_start()

            # Auf Verbindung warten
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if self.connected:
                logger.info("MQTT-Verbindung erfolgreich hergestellt")
                self.stats["successful_connections"] += 1
                return True
            logger.error("MQTT-Verbindung fehlgeschlagen (Timeout)")
            self.client.loop_stop()
            return False

        except Exception as e:
            logger.error(f"Fehler beim Verbinden: {e}")
            self.connecting = False
            return False

    def disconnect(self):
        """Trennt die Verbindung zum MQTT-Broker."""
        self._stop_requested = True

        # Wiederverbindung stoppen
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_event.set()
            self.reconnect_thread.join(timeout=2.0)

        # Client trennen
        if self.client and self.connected:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT-Verbindung getrennt")
            except Exception as e:
                logger.error(f"Fehler beim Trennen: {e}")

        self.connected = False
        self.connecting = False

    def publish(self, topic: str, payload: Any, qos: int = 1, retain: bool = False) -> bool:
        """
        Veröffentlicht eine Nachricht auf einem Topic.

        Args:
                topic: MQTT-Topic
                payload: Nachricht (wird automatisch zu JSON konvertiert wenn Dict)
                qos: Quality of Service Level (0, 1 oder 2)
                retain: Ob die Nachricht vom Broker gespeichert werden soll

        Returns:
                bool: True bei erfolgreicher Veröffentlichung
        """
        if not self.connected:
            logger.warning("Nicht verbunden - kann nicht publizieren")
            return False

        try:
            # Payload vorbereiten
            if isinstance(payload, (dict, list)):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)

            # Nachricht senden
            result = self.client.publish(topic, payload_str, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.stats["messages_sent"] += 1
                logger.debug(f"Nachricht publiziert auf {topic}")
                return True
            logger.error(f"Fehler beim Publizieren: {result.rc}")
            return False

        except Exception as e:
            logger.error(f"Fehler beim Publizieren auf {topic}: {e}")
            return False

    def subscribe(
        self, topic: str, callback: Optional[Callable[[str, Any], None]] = None, qos: int = 1
    ) -> bool:
        """
        Abonniert ein Topic mit optionalem Callback.

        Args:
                topic: MQTT-Topic (unterstützt Wildcards + und #)
                callback: Funktion die bei Nachrichten aufgerufen wird
                qos: Quality of Service Level

        Returns:
                bool: True bei erfolgreichem Abonnement
        """
        if not self.connected:
            logger.warning("Nicht verbunden - kann nicht abonnieren")
            return False

        try:
            # Callback registrieren wenn angegeben
            if callback:
                with self._callback_lock:
                    if topic not in self.callbacks:
                        self.callbacks[topic] = []
                    if callback not in self.callbacks[topic]:
                        self.callbacks[topic].append(callback)

            # Topic abonnieren
            result = self.client.subscribe(topic, qos)

            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Topic abonniert: {topic}")
                return True
            logger.error(f"Fehler beim Abonnieren von {topic}: {result[0]}")
            return False

        except Exception as e:
            logger.error(f"Fehler beim Abonnieren von {topic}: {e}")
            return False

    def unsubscribe(self, topic: str) -> bool:
        """
        Beendet das Abonnement eines Topics.

        Args:
                topic: MQTT-Topic

        Returns:
                bool: True bei erfolgreicher Abmeldung
        """
        if not self.connected:
            logger.warning("Nicht verbunden - kann Abonnement nicht beenden")
            return False

        try:
            # Topic abmelden
            result = self.client.unsubscribe(topic)

            # Callbacks entfernen
            with self._callback_lock:
                if topic in self.callbacks:
                    del self.callbacks[topic]

            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Abonnement beendet: {topic}")
                return True
            logger.error(f"Fehler beim Beenden des Abonnements: {result[0]}")
            return False

        except Exception as e:
            logger.error(f"Fehler beim Beenden des Abonnements von {topic}: {e}")
            return False

    def add_callback(self, topic: str, callback: Callable[[str, Any], None]):
        """
        Fügt einen Callback für ein Topic hinzu.

        Args:
                topic: MQTT-Topic
                callback: Callback-Funktion
        """
        with self._callback_lock:
            if topic not in self.callbacks:
                self.callbacks[topic] = []
            if callback not in self.callbacks[topic]:
                self.callbacks[topic].append(callback)

    def remove_callback(self, topic: str, callback: Callable[[str, Any], None]):
        """
        Entfernt einen Callback für ein Topic.

        Args:
                topic: MQTT-Topic
                callback: Zu entfernender Callback
        """
        with self._callback_lock:
            if topic in self.callbacks and callback in self.callbacks[topic]:
                self.callbacks[topic].remove(callback)
                if not self.callbacks[topic]:
                    del self.callbacks[topic]

    def is_connected(self) -> bool:
        """
        Prüft ob der Client verbunden ist.

        Returns:
                bool: Verbindungsstatus
        """
        return self.connected

    def get_stats(self) -> Dict[str, int]:
        """
        Gibt Statistiken über die MQTT-Verbindung zurück.

        Returns:
                Dict mit Statistiken
        """
        return self.stats.copy()

    def _on_connect(self, client, userdata, flags, rc):
        """Callback für erfolgreiche Verbindung."""
        if rc == 0:
            logger.info("Mit MQTT-Broker verbunden")
            self.connected = True
            self.connecting = False
            self.current_reconnect_interval = self.reconnect_interval

            # Abonnements wiederherstellen
            self._restore_subscriptions()
        else:
            error_messages = {
                1: "Falsche Protokollversion",
                2: "Ungültige Client-ID",
                3: "Server nicht verfügbar",
                4: "Falscher Benutzername/Passwort",
                5: "Nicht autorisiert",
            }
            error_msg = error_messages.get(rc, f"Unbekannter Fehler: {rc}")
            logger.error(f"Verbindung fehlgeschlagen: {error_msg}")
            self.connecting = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback für getrennte Verbindung."""
        self.connected = False
        self.connecting = False

        if rc != 0 and not self._stop_requested:
            logger.warning(f"Unerwartete Trennung (Code: {rc})")
            self._start_reconnect()
        else:
            logger.info("Verbindung ordnungsgemäß getrennt")

    def _on_message(self, client, userdata, msg):
        """Callback für empfangene Nachrichten."""
        try:
            # Payload dekodieren
            payload_str = msg.payload.decode("utf-8")

            # JSON parsen wenn möglich
            try:
                if payload_str.startswith("{") or payload_str.startswith("["):
                    payload = json.loads(payload_str)
                else:
                    payload = payload_str
            except json.JSONDecodeError:
                payload = payload_str

            # Statistik aktualisieren
            self.stats["messages_received"] += 1

            # Callbacks ausführen
            topic = msg.topic
            with self._callback_lock:
                # Direkte Topic-Matches
                if topic in self.callbacks:
                    for callback in self.callbacks[topic]:
                        self._execute_callback(callback, topic, payload)

                # Wildcard-Matches prüfen
                for pattern, callbacks in self.callbacks.items():
                    if self._topic_matches(pattern, topic) and pattern != topic:
                        for callback in callbacks:
                            self._execute_callback(callback, topic, payload)

        except Exception as e:
            logger.error(f"Fehler bei Nachrichtenverarbeitung: {e}")

    def _execute_callback(self, callback: Callable, topic: str, payload: Any):
        """Führt einen Callback sicher aus."""
        try:
            callback(topic, payload)
        except Exception as e:
            logger.error(f"Fehler in Callback für {topic}: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """
        Prüft ob ein Topic einem Pattern mit Wildcards entspricht.

        Args:
                pattern: Topic-Pattern (kann + und # enthalten)
                topic: Tatsächliches Topic

        Returns:
                bool: True wenn Pattern passt
        """
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, pattern_part in enumerate(pattern_parts):
            # Multi-level wildcard
            if pattern_part == "#":
                return True

            # Nicht genug Topic-Teile
            if i >= len(topic_parts):
                return False

            # Single-level wildcard
            if pattern_part == "+":
                continue

            # Exakte Übereinstimmung
            if pattern_part != topic_parts[i]:
                return False

        # Pattern und Topic müssen gleich lang sein (außer bei #)
        return len(pattern_parts) == len(topic_parts)

    def _restore_subscriptions(self):
        """Stellt Abonnements nach Wiederverbindung wieder her."""
        with self._callback_lock:
            for topic in self.callbacks:
                try:
                    self.client.subscribe(topic)
                    logger.info(f"Abonnement wiederhergestellt: {topic}")
                except Exception as e:
                    logger.error(f"Fehler beim Wiederherstellen von {topic}: {e}")

    def _start_reconnect(self):
        """Startet den Wiederverbindungsthread."""
        if self._stop_requested:
            return

        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return

        self.reconnect_event.clear()
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()

    def _reconnect_loop(self):
        """Wiederverbindungsschleife."""
        while not self._stop_requested and not self.connected:
            logger.info(f"Wiederverbindungsversuch in {self.current_reconnect_interval}s")

            # Warten
            if self.reconnect_event.wait(self.current_reconnect_interval):
                break  # Abbruch angefordert

            try:
                # Wiederverbindung versuchen
                self.client.reconnect()

            except Exception as e:
                logger.error(f"Wiederverbindung fehlgeschlagen: {e}")
                # Intervall erhöhen (exponentielles Backoff)
                self.current_reconnect_interval = min(
                    self.current_reconnect_interval * 1.5, self.max_reconnect_interval
                )