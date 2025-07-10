import json
import logging
from typing import Any, Dict, Optional

from common.suspension_core.config.manager import ConfigManager
from common.suspension_core.mqtt.handler import MqttHandler

logger = logging.getLogger(__name__)


class MqttBridge:
    """
    MQTT Bridge for the CAN Simulator Service.

    This class handles the MQTT communication for the CAN Simulator Service,
    including publishing CAN messages to MQTT topics and handling commands
    received via MQTT.
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the MQTT Bridge.

        Args:
                config: Configuration manager (optional)
        """
        self.config = config or ConfigManager()
        self.mqtt_handler = MqttHandler(
            app_type="can_simulator",
            broker=self.config.get("mqtt.broker", "localhost"),
            port=self.config.get("mqtt.port", 1883),
        )
        self.command_callbacks = {}


def connect(self) -> bool:
    """
    Connect to the MQTT broker.

    Returns:
            True if connection was successful, False otherwise
    """
    try:
        result = self.mqtt_handler.connect()
        if result:
            logger.info("Connected to MQTT broker")
            # Subscribe to command topics
            self.mqtt_handler.subscribe("suspension/simulator/command")
            self.mqtt_handler.add_callback("message", self._on_message)
        else:
            logger.error("Failed to connect to MQTT broker")
        return result
    except Exception as e:
        logger.error(f"Error connecting to MQTT broker: {e}")
        return False


def disconnect(self) -> None:
    """Disconnect from the MQTT broker."""
    try:
        self.mqtt_handler.disconnect()
        logger.info("Disconnected from MQTT broker")
    except Exception as e:
        logger.error(f"Error disconnecting from MQTT broker: {e}")


def publish_can_frame(self, can_id: str, data: bytes, timestamp: float) -> bool:
    """
    Publish a CAN frame to MQTT.

    Args:
            can_id: CAN ID as a hexadecimal string
            data: CAN data as bytes
            timestamp: Timestamp of the CAN frame

    Returns:
            True if publishing was successful, False otherwise
    """
    try:
        payload = {"id": can_id, "data": list(data), "timestamp": timestamp}
        return self.mqtt_handler.publish(f"suspension/can/raw/{can_id}", json.dumps(payload))
    except Exception as e:
        logger.error(f"Error publishing CAN frame: {e}")
        return False


def publish_interpreted_data(self, topic: str, data: Dict[str, Any]) -> bool:
    """Publiziert interpretierte CAN-Daten zu MQTT - Thread-sicher."""
    try:
        # Daten für JSON vorbereiten
        clean_data = self._clean_data_for_json(data)

        # Mit ensure_ascii=False für bessere Performance
        json_string = json.dumps(clean_data, ensure_ascii=False, separators=(",", ":"))

        return self.mqtt_handler.publish("suspension/can/interpreted", json_string)

    except (TypeError, ValueError) as e:
        self.logger.error(f"JSON-Serialisierung fehlgeschlagen: {e}")
        self.logger.debug(f"Problematische Daten: {data}")
        return False
    except Exception as e:
        self.logger.error(f"MQTT-Publish fehlgeschlagen: {e}")
        return False


def _clean_data_for_json(self, data: Any) -> Any:
    """Bereitet Daten für JSON-Serialisierung vor."""
    if isinstance(data, dict):
        return {k: self._clean_data_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [self._clean_data_for_json(item) for item in data]
    if isinstance(data, bool):
        return data  # Booleans SIND JSON-serialisierbar
    if isinstance(data, (int, float, str, type(None))):
        return data
    if hasattr(data, "isoformat"):  # datetime objects
        return data.isoformat()
    return str(data)  # Fallback für komplexe Objekte


def register_command_callback(self, command: str, callback: callable) -> None:
    """
    Register a callback for a specific command.

    Args:
            command: Command name
            callback: Callback function
    """
    self.command_callbacks[command] = callback
    logger.debug(f"Registered callback for command: {command}")


def _on_message(self, client, userdata, msg) -> None:
    """
    Handle incoming MQTT messages.

    Args:
            client: MQTT client
            userdata: User data
            msg: MQTT message
    """
    try:
        topic = msg.topic
        payload = json.loads(msg.payload)

        if topic == "suspension/simulator/command":
            command = payload.get("command")
            if command in self.command_callbacks:
                self.command_callbacks[command](payload)
            else:
                logger.warning(f"No callback registered for command: {command}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in message: {msg.payload}")
    except Exception as e:
        logger.error(f"Error handling MQTT message: {e}")