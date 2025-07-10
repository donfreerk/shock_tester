# Import the MqttHandler and new service components
from .handler import MqttHandler
from .service import MqttServiceBase, MqttTopics, SimpleMqttService

# Create an instance of the MqttHandler for backward compatibility
_handler = MqttHandler()

# Export the main classes for new code
__all__ = [
    "MqttHandler",
    "MqttServiceBase", 
    "MqttTopics",
    "SimpleMqttService",
    # Legacy functions for backward compatibility
    "add_callback",
    "remove_callback",
    "publish",
    "connect",
    "disconnect",
    "send_test_command",
    "send_motor_command",
    "send_status_update"
]

# Expose the methods of the MqttHandler as module-level functions for backward compatibility


def add_callback(category, callback):
	"""
	Adds a callback for a specific topic category.

	Args:
		category: The callback category ('status', 'measurements', etc.)
		callback: Callback function to be called when a message is received
	"""
	return _handler.add_callback(category, callback)


def remove_callback(category, callback):
	"""
	Removes a callback for a specific topic category.

	Args:
		category: The callback category ('status', 'measurements', etc.)
		callback: Callback to be removed
	"""
	return _handler.remove_callback(category, callback)


def publish(topic, message, retain=False):
	"""
	Publishes a message to a topic.

	Args:
		topic: The topic to publish to
		message: The message to publish
		retain: Whether to retain the message
	"""
	return _handler.publish(topic, message, retain)


def connect():
	"""Connects to the MQTT broker."""
	return _handler.connect()


def disconnect():
	"""Disconnects from the MQTT broker."""
	return _handler.disconnect()


def send_test_command(command, position, method="phase_shift", parameters=None):
	"""
	Sends a test command to the backend, respecting namespaces.

	Args:
		command: "start", "stop", etc.
		position: "front_left", "front_right", etc.
		method: "phase_shift", "resonance"
		parameters: Additional parameters for the command
	"""
	return _handler.send_test_command(command, position, method, parameters)


def send_motor_command(motor, frequency=None):
	"""
	Sends a motor control command.

	Args:
		motor: "left", "right", "both" or "stop"
		frequency: Optional frequency (in Hz)
	"""
	return _handler.send_motor_command(motor, frequency)


def send_status_update(status, test_status=None, details=None):
	"""
	Sends a status update.

	Args:
		status: Application status ("idle", "test_running", etc.)
		test_status: Optional - Test status ("ready", "running", "completed", etc.)
		details: Optional - Additional details about the status
	"""
	return _handler.send_status_update(status, test_status, details)
