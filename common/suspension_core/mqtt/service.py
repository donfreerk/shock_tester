"""
Zentrale Service-Abstraktion für einheitliche MQTT-Integration

Diese Modul stellt eine standardisierte Basis-Klasse für alle Services zur Verfügung,
die MQTT verwenden. Es löst die Probleme von inkonsistenten Import-Pfaden,
unterschiedlichen Konfigurationsmustern und problematischen Sync/Async-Callbacks.

Usage:
    from suspension_core.mqtt.service import MqttServiceBase, MqttTopics

    class MyService(MqttServiceBase):
        def __init__(self):
            super().__init__("my_service")

        async def setup_mqtt_subscriptions(self):
            self.register_topic_handler(MqttTopics.TEST_STATUS, self.handle_test_status)
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Union

from .handler import MqttHandler
from ..config.manager import ConfigManager

logger = logging.getLogger(__name__)


class MqttTopics:
    """
    Zentrale Definition aller MQTT-Topics für einheitliche Kommunikation

    Diese Klasse definiert alle Topics, die im Fahrwerkstester-System verwendet werden.
    Dadurch wird sichergestellt, dass alle Services konsistente Topic-Namen verwenden.
    """

    # === SERVICE-SPEZIFISCHE COMMANDS ===
    CAN_SIMULATOR_COMMAND = "suspension/simulator/command"
    PI_PROCESSING_COMMAND = "suspension/processing/command"
    HARDWARE_BRIDGE_COMMAND = "suspension/hardware/command"
    TEST_CONTROLLER_COMMAND = "suspension/test/command"

    # === DATENFLUSS ===
    # Rohdaten von verschiedenen Quellen
    CAN_RAW_DATA = "suspension/can/raw"
    MEASUREMENT_RAW_DATA = "suspension/measurements/raw"
    SENSOR_RAW_DATA = "suspension/sensors/raw"
    HARDWARE_RAW_DATA = "suspension/hardware/raw"

    # Verarbeitete Daten
    MEASUREMENT_PROCESSED = "suspension/measurements/processed"
    RESULTS_PROCESSED = "suspension/results/processed"
    TEST_RESULTS_FINAL = "suspension/test/results/final"

    # Spezielle Processing-Topics
    RAW_DATA_COMPLETE = "suspension/raw_data/complete"  # Für Pi Processing Service

    # === TEST-LIFECYCLE ===
    TEST_STATUS = "suspension/test/status"
    TEST_START = "suspension/test/start"
    TEST_STOP = "suspension/test/stop"
    TEST_COMPLETED = "suspension/test/completed"
    TEST_ERROR = "suspension/test/error"

    # === SYSTEM-STATUS ===
    SYSTEM_HEARTBEAT = "suspension/system/heartbeat"
    SYSTEM_STATUS = "suspension/system/status"
    SYSTEM_ERROR = "suspension/system/error"

    # === HARDWARE-STEUERUNG ===
    MOTOR_COMMAND = "suspension/hardware/motor"
    LAMP_COMMAND = "suspension/hardware/lamp"
    SENSOR_CALIBRATION = "suspension/hardware/calibration"

    @staticmethod
    def service_status(service_name: str) -> str:
        """
        Generiert service-spezifisches Status-Topic

        Args:
            service_name: Name des Services

        Returns:
            Topic-String für Service-Status
        """
        return f"suspension/system/service/{service_name}"

    @staticmethod
    def service_command(service_name: str) -> str:
        """
        Generiert service-spezifisches Command-Topic

        Args:
            service_name: Name des Services

        Returns:
            Topic-String für Service-Commands
        """
        return f"suspension/{service_name}/command"

    @staticmethod
    def service_data(service_name: str, data_type: str) -> str:
        """
        Generiert service-spezifisches Daten-Topic

        Args:
            service_name: Name des Services
            data_type: Art der Daten (z.B. "raw", "processed")

        Returns:
            Topic-String für Service-Daten
        """
        return f"suspension/{service_name}/data/{data_type}"


class MqttServiceBase(ABC):
    """
    Basis-Klasse für alle Services mit einheitlicher MQTT-Integration

    Diese Klasse stellt standardisierte Patterns zur Verfügung:
    - Einheitliche Konfiguration und Initialisierung
    - Konsistente Topic-Struktur über MqttTopics
    - Robuste Verbindungsbehandlung mit Auto-Reconnect
    - Saubere Async/Sync Callback-Bridge
    - Standardisierte Status- und Heartbeat-Publishing
    - Umfassendes Error-Handling und Logging

    Usage:
        class MyService(MqttServiceBase):
            def __init__(self):
                super().__init__("my_service")

            async def setup_mqtt_subscriptions(self):
                self.register_topic_handler(MqttTopics.TEST_STATUS, self.handle_test_status)

            async def handle_test_status(self, topic: str, message: Dict[str, Any]):
                # Handle test status updates
                pass
    """

    def __init__(self, service_name: str, config: Optional[ConfigManager] = None):
        """
        Initialisiert Service mit einheitlicher MQTT-Integration

        Args:
            service_name: Name des Services (für Logging, client_id, Topics)
            config: ConfigManager-Instanz oder None für Standard-Config
        """
        self.service_name = service_name
        self.config = config or ConfigManager()
        self.logger = logging.getLogger(f"{__name__}.{service_name}")

        # MQTT-Handler mit standardisierter Konfiguration
        self.mqtt = self._create_mqtt_handler()

        # Async-Support für Message-Processing
        self._message_queue = asyncio.Queue()
        self._running = False
        self._tasks = []

        # Callback-Registry für Topic-Handler
        self._topic_handlers: Dict[str, Callable] = {}

        # Service-Status
        self._status = "initializing"
        self._start_time = None
        self._heartbeat_interval = self.config.get("mqtt.heartbeat_interval", 30.0)

        self.logger.info(f"Service {service_name} initialized")

    def _create_mqtt_handler(self) -> MqttHandler:
        """
        Erstellt standardisierten MqttHandler mit einheitlicher Konfiguration

        Returns:
            Konfigurierter MqttHandler
        """
        return MqttHandler(
            client_id=f"{self.service_name}_{int(time.time())}",
            host=self.config.get("mqtt.broker", "localhost"),
            port=self.config.get("mqtt.port", 1883),
            username=self.config.get("mqtt.username"),
            password=self.config.get("mqtt.password"),
            app_type=self.service_name,
            # keepalive=self.config.get("mqtt.keepalive", 60)
        )

    async def start_mqtt(self) -> bool:
        """
        Startet MQTT-Verbindung und Message-Processing

        Returns:
            True wenn erfolgreich, False bei Fehlern
        """
        try:
            self.logger.info(f"Starting MQTT integration for {self.service_name}")

            # MQTT-Verbindung herstellen mit Retry-Logic
            max_retries = self.config.get("mqtt.connection_retries", 3)
            for attempt in range(max_retries):
                if self.mqtt.connect():
                    self.logger.info(f"MQTT connected on attempt {attempt + 1}")
                    break
                elif attempt < max_retries - 1:
                    self.logger.warning(
                        f"MQTT connection attempt {attempt + 1} failed, retrying..."
                    )
                    await asyncio.sleep(2.0)
                else:
                    self.logger.error("MQTT connection failed after all retries")
                    return False

            # Message-Processing-Task starten
            self._running = True
            self._start_time = time.time()

            # Async-Tasks starten
            tasks = [
                asyncio.create_task(self._process_message_queue()),
                asyncio.create_task(self._heartbeat_loop()),
            ]
            self._tasks.extend(tasks)

            # Service-spezifische Subscriptions einrichten
            await self.setup_mqtt_subscriptions()

            # Service als "ready" markieren
            self._status = "ready"
            await self.publish_status("ready", {"mqtt_connected": True})

            self.logger.info(
                f"MQTT integration started successfully for {self.service_name}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to start MQTT: {e}")
            self._status = "error"
            return False

    async def stop_mqtt(self):
        """
        Stoppt MQTT-Integration sauber
        """
        self.logger.info(f"Stopping MQTT integration for {self.service_name}")

        # Service als "stopping" markieren
        self._status = "stopping"
        await self.publish_status("stopping")

        # Running-Flag setzen
        self._running = False

        # Alle async Tasks beenden
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.clear()

        # MQTT-Verbindung trennen
        try:
            self.mqtt.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting MQTT: {e}")

        self._status = "stopped"
        self.logger.info(f"MQTT integration stopped for {self.service_name}")

    def register_topic_handler(
        self,
        topic: str,
        handler: Union[Callable, Callable[[str, Dict[str, Any]], None]],
    ):
        """
        Registriert Handler für spezifisches MQTT-Topic

        Args:
            topic: MQTT-Topic zum Abonnieren
            handler: Handler-Funktion (kann sync oder async sein)
        """
        self._topic_handlers[topic] = handler

        # Sync Callback-Wrapper für MQTT-Library registrieren
        self.mqtt.subscribe(topic, self._sync_callback_wrapper)

        self.logger.debug(f"Registered handler for topic: {topic}")

    def _sync_callback_wrapper(self, topic: str, message: Dict[str, Any]):
        """
        Bridge zwischen sync MQTT-Callbacks und async Service-Handlers

        Diese Methode wird von der MQTT-Library synchron aufgerufen und
        leitet Messages an die async Message-Queue weiter.

        Args:
            topic: MQTT-Topic
            message: Message-Payload
        """
        try:
            if self._running:
                # Message in async Queue einreihen für Processing
                asyncio.create_task(self._message_queue.put((topic, message)))
        except Exception as e:
            self.logger.error(f"Error in sync callback wrapper for {topic}: {e}")

    async def _process_message_queue(self):
        """
        Async Message-Processing Loop

        Diese Methode läuft kontinuierlich und verarbeitet eingehende MQTT-Messages
        aus der Queue durch die registrierten Handler.
        """
        self.logger.debug("Message processing loop started")

        while self._running:
            try:
                # Warte auf Message mit Timeout
                topic, message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )

                # Entsprechenden Handler finden und aufrufen
                handler = self._topic_handlers.get(topic)
                if handler:
                    try:
                        # Handler aufrufen (async oder sync)
                        if asyncio.iscoroutinefunction(handler):
                            await handler(topic, message)
                        else:
                            handler(topic, message)
                    except Exception as e:
                        self.logger.error(f"Error in topic handler for {topic}: {e}")
                        # Optional: Error-Recovery oder Benachrichtigung
                        await self._handle_handler_error(topic, message, e)
                else:
                    self.logger.warning(f"No handler registered for topic: {topic}")

            except asyncio.TimeoutError:
                # Timeout ist normal, weitermachen
                continue
            except Exception as e:
                self.logger.error(f"Error processing message queue: {e}")
                # Kurze Pause bei Fehlern
                await asyncio.sleep(0.1)

        self.logger.debug("Message processing loop stopped")

    async def _handle_handler_error(
        self, topic: str, message: Dict[str, Any], error: Exception
    ):
        """
        Behandelt Fehler in Message-Handlers

        Args:
            topic: Topic der fehlerhaften Message
            message: Message-Payload
            error: Aufgetretener Fehler
        """
        error_info = {
            "service": self.service_name,
            "topic": topic,
            "error": str(error),
            "message_preview": str(message)[:200],  # Ersten 200 Zeichen
            "timestamp": time.time(),
        }

        # Error auf System-Error-Topic publizieren
        await self.publish(MqttTopics.SYSTEM_ERROR, error_info)

    async def _heartbeat_loop(self):
        """
        Sendet regelmäßige Heartbeat-Signale
        """
        self.logger.debug("Heartbeat loop started")

        while self._running:
            try:
                await self.publish_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5.0)  # Fallback-Intervall bei Fehlern

        self.logger.debug("Heartbeat loop stopped")

    async def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """
        Async-friendly MQTT publish mit Error-Handling

        Args:
            topic: MQTT-Topic
            payload: Message-Payload

        Returns:
            True wenn erfolgreich, False bei Fehlern
        """
        try:
            success = self.mqtt.publish(topic, payload)
            if not success:
                self.logger.warning(f"MQTT publish failed for topic: {topic}")
            return success
        except Exception as e:
            self.logger.error(f"Error publishing to {topic}: {e}")
            return False

    async def publish_status(
        self, status: str, details: Optional[Dict[str, Any]] = None
    ):
        """
        Publiziert Service-Status auf standardisiertem Topic

        Args:
            status: Status-String ("ready", "running", "error", "stopping", etc.)
            details: Zusätzliche Status-Details
        """
        status_topic = MqttTopics.service_status(self.service_name)

        status_payload = {
            "service": self.service_name,
            "status": status,
            "timestamp": time.time(),
            "uptime": time.time() - self._start_time if self._start_time else 0,
            **(details or {}),
        }

        success = await self.publish(status_topic, status_payload)
        if success:
            self._status = status

    async def publish_heartbeat(self, custom_data: Optional[Dict[str, Any]] = None):
        """
        Publiziert Service-Heartbeat mit Standard-Informationen

        Args:
            custom_data: Service-spezifische Heartbeat-Daten
        """
        heartbeat_payload = {
            "service": self.service_name,
            "timestamp": time.time(),
            "status": self._status,
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "message_queue_size": self._message_queue.qsize(),
            **(custom_data or {}),
        }

        await self.publish(MqttTopics.SYSTEM_HEARTBEAT, heartbeat_payload)

    def get_status(self) -> Dict[str, Any]:
        """
        Gibt aktuellen Service-Status zurück

        Returns:
            Status-Dictionary mit Service-Informationen
        """
        return {
            "service": self.service_name,
            "status": self._status,
            "uptime": time.time() - self._start_time if self._start_time else 0,
            "message_queue_size": self._message_queue.qsize(),
            "registered_topics": list(self._topic_handlers.keys()),
            "running": self._running,
        }

    @abstractmethod
    async def setup_mqtt_subscriptions(self):
        """
        Service-spezifische MQTT-Subscriptions einrichten

        Muss in Subklassen implementiert werden. Verwenden Sie:
        self.register_topic_handler(topic, handler)

        Beispiel:
            async def setup_mqtt_subscriptions(self):
                self.register_topic_handler(MqttTopics.TEST_STATUS, self.handle_test_status)
                self.register_topic_handler(MqttTopics.service_command(self.service_name), self.handle_command)
        """
        pass


class SimpleMqttService(MqttServiceBase):
    """
    Einfache Implementierung für Services, die nur grundlegende MQTT-Funktionalität benötigen

    Kann direkt verwendet werden oder als Basis für einfache Services dienen.
    """

    def __init__(self, service_name: str, config: Optional[ConfigManager] = None):
        super().__init__(service_name, config)
        self.message_handlers = {}

    async def setup_mqtt_subscriptions(self):
        """Standard-Subscriptions für einfache Services"""
        # Service-Commands abonnieren
        command_topic = MqttTopics.service_command(self.service_name)
        self.register_topic_handler(command_topic, self.handle_command)

    async def handle_command(self, topic: str, message: Dict[str, Any]):
        """Standard-Command-Handler"""
        command = message.get("command")

        if command == "status":
            await self.publish_status("running", self.get_status())
        elif command == "ping":
            await self.publish_heartbeat({"response": "pong"})
        else:
            self.logger.warning(f"Unknown command: {command}")

    def add_message_handler(self, topic: str, handler: Callable):
        """Fügt Message-Handler hinzu"""
        self.register_topic_handler(topic, handler)
        self.message_handlers[topic] = handler
