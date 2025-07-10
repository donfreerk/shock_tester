import json
import logging
from typing import Any, Dict, Optional

from common.suspension_core.mqtt.handler import MqttHandler


from common.suspension_core.config.manager import ConfigManager

logger = logging.getLogger(__name__)


class MqttPublisher:
	"""
	MQTT Publisher for the Hardware Bridge Service.

	This class handles publishing CAN messages to MQTT topics
	and receiving commands via MQTT.
	"""

	def __init__(self, config: Optional[ConfigManager] = None):
		"""
		Initialize the MQTT Publisher.

		Args:
			config: Configuration manager (optional)
		"""
		self.config = config or ConfigManager()
		self.mqtt_handler = MqttHandler



(
	app_type="hardware_bridge",
broker=self.config.get("mqtt.broker", "localhost"),
port = self.config.get("mqtt.port", 1883)
)
self.command_callbacks = {}
self.connected = False


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
			self.connected = True
			# Subscribe to command topics
			self.mqtt_handler.subscribe("suspension/hardware/command")
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
		if self.connected:
			self.mqtt_handler.disconnect()
			logger.info("Disconnected from MQTT broker")
			self.connected = False
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
	if not self.connected:
		logger.error("Cannot publish: Not connected to MQTT broker")
		return False

	try:
		payload = {
			"id": can_id,
			"data": list(data),
			"timestamp": timestamp
		}
		return self.mqtt_handler.publish(
			f"suspension/can/raw/hardware/{can_id}",
			json.dumps(payload)
		)
	except Exception as e:
		logger.error(f"Error publishing CAN frame: {e}")
		return False


def publish_interpreted_data(self, topic: str, data: Dict[str, Any]) -> bool:
	"""
	Publish interpreted CAN data to MQTT.

	Args:
		topic: MQTT topic suffix
		data: Data to publish

	Returns:
		True if publishing was successful, False otherwise
	"""
	if not self.connected:
		logger.error("Cannot publish: Not connected to MQTT broker")
		return False

	try:
		return self.mqtt_handler.publish(
			f"suspension/can/interpreted/{topic}",
			json.dumps(data)
		)
	except Exception as e:
		logger.error(f"Error publishing interpreted data: {e}")
		return False


def publish_status(self, status: Dict[str, Any]) -> bool:
	"""
	Publish status information to MQTT.

	Args:
		status: Status information

	Returns:
		True if publishing was successful, False otherwise
	"""
	if not self.connected:
		logger.error("Cannot publish: Not connected to MQTT broker")
		return False

	try:
		return self.mqtt_handler.publish(
			"suspension/hardware/status",
			json.dumps(status)
		)
	except Exception as e:
		logger.error(f"Error publishing status: {e}")
		return False


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

		if topic == "suspension/hardware/command":
			command = payload.get("command")
			if command in self.command_callbacks:
				self.command_callbacks[command](payload)
			else:
				logger.warning(f"No callback registered for command: {command}")
	except json.JSONDecodeError:
		logger.error(f"Invalid JSON in message: {msg.payload}")
	except Exception as e:
		logger.error(f"Error handling MQTT message: {e}")