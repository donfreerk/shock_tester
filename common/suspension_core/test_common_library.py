#!/usr/bin/env python3
"""
Test script for the suspension_core library.

This script tests the basic functionality of the common library components
to ensure they work correctly together.
"""

import logging
import time
from typing import Any, Dict

from suspension_core import (
    ConfigManager,
    MqttClient,
    MqttHandler,
    Position,
    TestState,
    create_command_message,
    create_measurement_message,
    create_status_message,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def on_message_received(topic: str, message: Dict[str, Any]):
    """Callback for received MQTT messages."""
    logger.info(f"Received message on topic {topic}: {message}")


def test_mqtt_client():
    """Test the MqttClient class."""
    logger.info("Testing MqttClient...")

    # Create a client
    client = MqttClient(broker="localhost", client_id="test_client")

    # Connect to broker
    try:
        client.connect()
        logger.info("Connected to MQTT broker")

        # Subscribe to a topic
        client.subscribe("test/topic", on_message_received)
        logger.info("Subscribed to test/topic")

        # Publish a message
        client.publish("test/topic", {"message": "Hello from test_mqtt_client"})
        logger.info("Published message to test/topic")

        # Wait for message to be received
        time.sleep(1)

        # Disconnect
        client.disconnect()
        logger.info("Disconnected from MQTT broker")

        return True
    except Exception as e:
        logger.error(f"Error testing MqttClient: {e}")
        return False


def test_mqtt_handler():
    """Test the MqttHandler

    class."""
    logger.info("Testing MqttHandler...")

    # Create a handler
    handler = MqttHandler(
        broker="localhost", client_id="test_handler", app_type="backend"
    )

    # Connect to broker
    try:
        handler.connect()
        logger.info("Connected to MQTT broker")

        # Add a callback
        handler.add_callback("command", on_message_received)
        logger.info("Added callback for command messages")

        # Send a test command
        handler.send_test_command(
            command="start",
            position="front_left",
            method="phase_shift",
            parameters={"frequency": 10.0, "amplitude": 5.0},
        )
        logger.info("Sent test command")

        # Send a status update
        handler.send_status_update(
            state="running", test_status="active", details={"progress": 50}
        )
        logger.info("Sent status update")

        # Send a measurement
        handler.send_measurement(
            position="front_left",
            platform_position=10.5,
            tire_force=500.0,
            frequency=15.0,
            phase_shift=45.0,
        )
        logger.info("Sent measurement")

        # Wait for messages to be processed
        time.sleep(1)

        # Disconnect
        handler.disconnect()
        logger.info("Disconnected from MQTT broker")

        return True
    except Exception as e:
        logger.error(f"Error testing MqttHandler: {e}")
        return False


def test_config_manager():
    """Test the ConfigManager class."""
    logger.info("Testing ConfigManager...")

    try:
        # Create a config manager
        config = ConfigManager()
        logger.info("Created ConfigManager")

        # Get a configuration value
        mqtt_broker = config.get("mqtt.broker")
        logger.info(f"MQTT broker: {mqtt_broker}")

        # Set a configuration value
        config.set("test.value", "test_value")
        logger.info("Set test.value to 'test_value'")

        # Get the value back
        test_value = config.get("test.value")
        logger.info(f"Retrieved test.value: {test_value}")

        # Check if the value is correct
        if test_value != "test_value":
            logger.error(f"Expected 'test_value', got '{test_value}'")
            return False

        return True
    except Exception as e:
        logger.error(f"Error testing ConfigManager: {e}")
        return False


def test_message_formats():
    """Test the message format functions."""
    logger.info("Testing message formats...")

    try:
        # Create a command message
        command_message = create_command_message(
            command="start",
            position=Position.FRONT_LEFT,
            method="phase_shift",
            parameters={"frequency": 10.0, "amplitude": 5.0},
        )
        logger.info(f"Command message: {command_message}")

        # Create a status message
        status_message = create_status_message(
            state=TestState.RUNNING,
            test_status=TestState.RUNNING,
            details={"progress": 50},
        )
        logger.info(f"Status message: {status_message}")

        # Create a measurement message
        measurement_message = create_measurement_message(
            position=Position.FRONT_LEFT,
            platform_position=10.5,
            tire_force=500.0,
            frequency=15.0,
            phase_shift=45.0,
        )
        logger.info(f"Measurement message: {measurement_message}")

        return True
    except Exception as e:
        logger.error(f"Error testing message formats: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("Starting tests for suspension_core library")

    tests = [
        ("ConfigManager", test_config_manager),
        ("Message Formats", test_message_formats),
        ("MqttClient", test_mqtt_client),
        ("MqttHandler", test_mqtt_handler),
    ]

    results = {}

    for name, test_func in tests:
        logger.info(f"Running test: {name}")
        try:
            result = test_func()
            results[name] = result
            logger.info(f"Test {name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"Error running test {name}: {e}")
            results[name] = False

    # Print summary
    logger.info("\nTest Summary:")
    for name, result in results.items():
        logger.info(f"{name}: {'PASSED' if result else 'FAILED'}")

    # Overall result
    if all(results.values()):
        logger.info("\nAll tests PASSED")
        return 0
    logger.error("\nSome tests FAILED")
    return 1


if __name__ == "__main__":
    main()