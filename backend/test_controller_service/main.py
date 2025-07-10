import asyncio
import logging
import json
import time
from typing import Dict, Any

from suspension_core.mqtt.service import MqttServiceBase, MqttTopics
from common.suspension_core.config.manager import ConfigManager
from test_manager import TestManager
from data_processor import DataProcessor

logger = logging.getLogger(__name__)


class TestControllerService(MqttServiceBase):
    """
    Modernisierter Test Controller Service mit einheitlicher MQTT-Integration

    This service orchestrates test sequences, processes measurement data,
    and publishes results via MQTT.
    """

    def __init__(self, config=None):
        """Initialize the Test Controller Service."""
        super().__init__("test_controller", config)

        # Initialize test manager and data processor
        self.test_manager = TestManager(self.config)
        self.data_processor = DataProcessor(self.config)

        # State tracking
        self.current_test = None

    async def setup_mqtt_subscriptions(self):
        """MQTT-Subscriptions für Test Controller"""
        # Test Commands
        self.register_topic_handler(MqttTopics.TEST_CONTROLLER_COMMAND, self.handle_test_command)

        # Measurement Data
        self.register_topic_handler(MqttTopics.MEASUREMENT_RAW_DATA, self.handle_measurement_data)

        # Service Status (für Monitoring anderer Services)
        self.register_topic_handler("suspension/system/service/+", self.handle_service_status)

    async def start(self):
        """Start the test controller service."""
        # MQTT starten
        if not await self.start_mqtt():
            raise RuntimeError("Failed to connect to MQTT broker")

        logger.info("Test Controller Service started")

        # Publish initial status
        await self.publish_status("ready", {"state": "idle", "ready": True})

        # Main service loop
        while self._running:
            # Process any pending tasks
            if self.current_test:
                status = self.test_manager.get_test_status()
                if status["state"] == "completed":
                    # Test completed, process results
                    results = self.test_manager.get_test_results()
                    processed_results = self.data_processor.process_results(results)
                    await self.publish_results(processed_results)
                    self.current_test = None

                # Update status periodically
                await self.publish_status("running", status)

            # Sleep to avoid CPU hogging
            await asyncio.sleep(0.1)

    async def handle_test_command(self, topic: str, message: Dict[str, Any]):
        """
        Handle test commands received via MQTT.

        Args:
            topic: MQTT topic
            message: Command message
        """
        try:
            command = message.get("command")

            if command == "start_test":
                # Start a new test
                test_params = message.get("parameters", {})
                await self.start_test(test_params)

            elif command == "stop_test":
                # Stop the current test
                await self.stop_test()

            elif command == "configure":
                # Update configuration
                config_params = message.get("parameters", {})
                await self.configure_test(config_params)

            elif command == "status":
                # Send status report
                await self.publish_status("running", self.get_service_status())

        except Exception as e:
            logger.error(f"Error handling test command: {e}")

    async def handle_measurement_data(self, topic: str, message: Dict[str, Any]):
        """
        Handle measurement data received via MQTT.

        Args:
            topic: MQTT topic
            message: Measurement data message
        """
        try:
            # Forward data to test manager if a test is running
            if self.current_test:
                self.test_manager.process_measurement(message)

        except Exception as e:
            logger.error(f"Error handling measurement data: {e}")

    async def handle_service_status(self, topic: str, message: Dict[str, Any]):
        """Handle service status updates from other services"""
        service_name = message.get("service")
        status = message.get("status")
        logger.debug(f"Service {service_name} status: {status}")

    async def start_test(self, test_params: Dict[str, Any]):
        """Startet Test mit einheitlichem Status-Publishing"""
        try:
            # Test starten
            self.current_test = self.test_manager.start_test(test_params)

            # Status publizieren auf standardisiertem Topic
            await self.publish(MqttTopics.TEST_STATUS, {
                "status": "started",
                "test_id": self.current_test.id if hasattr(self.current_test, 'id') else str(time.time()),
                "parameters": test_params,
                "timestamp": time.time()
            })

            logger.info(f"Test started with parameters: {test_params}")

        except Exception as e:
            logger.error(f"Failed to start test: {e}")
            await self.publish(MqttTopics.TEST_STATUS, {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            })

    async def stop_test(self):
        """Stoppt aktuellen Test"""
        if self.current_test:
            try:
                self.test_manager.stop_test()

                await self.publish(MqttTopics.TEST_STATUS, {
                    "status": "stopped",
                    "test_id": self.current_test.id if hasattr(self.current_test, 'id') else "unknown",
                    "timestamp": time.time()
                })

                self.current_test = None
                logger.info("Test stopped")

            except Exception as e:
                logger.error(f"Error stopping test: {e}")

    async def configure_test(self, config_params: Dict[str, Any]):
        """Konfiguriert Test-Parameter"""
        try:
            self.test_manager.configure(config_params)
            logger.info(f"Test configuration updated: {config_params}")

        except Exception as e:
            logger.error(f"Error configuring test: {e}")

    async def publish_results(self, results: Dict[str, Any]):
        """Publiziert Test-Ergebnisse über standardisierte Topics"""
        try:
            # Publiziere auf finales Ergebnis-Topic
            await self.publish(MqttTopics.TEST_RESULTS_FINAL, results)
            logger.info(f"Published test results: {results}")

        except Exception as e:
            logger.error(f"Error publishing results: {e}")

    def get_service_status(self) -> Dict[str, Any]:
        """Gibt aktuellen Service-Status zurück"""
        return {
            "current_test": self.current_test.id if self.current_test and hasattr(self.current_test, 'id') else None,
            "test_running": self.current_test is not None,
            "timestamp": time.time()
        }

    async def stop(self):
        """Stop the test controller service."""
        # Stop any running test
        if self.current_test:
            await self.stop_test()

        # Stop MQTT
        await self.stop_mqtt()

        logger.info("Test Controller Service stopped")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create and start the service
    service = TestControllerService()

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        asyncio.run(service.stop())
