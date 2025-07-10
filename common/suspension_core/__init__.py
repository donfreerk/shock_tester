"""
Fahrwerkstester Common Library

This library provides common functionality for the Fahrwerkstester system,
including MQTT communication, configuration management, and standardized
message formats.

Components:
- mqtt: MQTT client and handler for communication.
- config: Configuration management.
- protocols: Standardized message formats.
"""

__version__ = "1.0.0"

# Import key components for easier access
from common.suspension_core.config.manager import ConfigManager


from .mqtt.client import MqttClient
from .mqtt.handler import MqttHandler

from .protocols.messages import (
    MessageType,
    Position,
    TestMethod,
    TestState,
    create_command_message,
    create_measurement_message,
    create_status_message,
)

# Define what's available when using "from suspension_core import *"
__all__ = [
    "MqttClient",
    "MqttHandler",
    "ConfigManager",
    "MessageType",
    "TestState",
    "Position",
    "TestMethod",
    "create_command_message",
    "create_status_message",
    "create_measurement_message",
]