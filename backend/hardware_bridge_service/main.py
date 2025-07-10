import asyncio
import logging
from suspension_core.mqtt.service import MqttServiceBase, MqttTopics
from common.suspension_core.can.can_interface import CanInterface
from common.suspension_core.config.manager import ConfigManager


class HardwareBridgeService(MqttServiceBase):
    """Modernisierter Hardware Bridge Service mit einheitlicher MQTT-Integration"""

    def __init__(self, config=None):
        super().__init__("hardware_bridge", config)

        # CAN-Interface initialisieren
        self.can_interface = CanInterface(
            channel=self.config.get("can.interface", "can0"),
            baudrate=self.config.get("can.baudrate", 1000000),
        )

    async def setup_mqtt_subscriptions(self):
        """MQTT-Subscriptions für Hardware Bridge"""
        # Hardware Commands
        self.register_topic_handler(MqttTopics.HARDWARE_BRIDGE_COMMAND, self.handle_hardware_command)

        # Motor/Lamp Commands
        self.register_topic_handler(MqttTopics.MOTOR_COMMAND, self.handle_motor_command)
        self.register_topic_handler(MqttTopics.LAMP_COMMAND, self.handle_lamp_command)

    async def start(self):
        """Startet Hardware Bridge mit MQTT und CAN"""
        # MQTT starten
        if not await self.start_mqtt():
            raise RuntimeError("MQTT connection failed")

        # CAN-Interface initialisieren
        if not self.can_interface.connect():
            self.logger.error("CAN connection failed")
            raise RuntimeError("CAN connection failed")

        # CAN-Callback registrieren
        self.can_interface.add_message_callback(self.on_can_message)

        await self.publish_status("ready", {"can_connected": True})

        # Hauptschleife
        while self._running:
            await asyncio.sleep(0.1)

    def on_can_message(self, msg):
        """CAN-Message-Handler (sync, da von CAN-Library aufgerufen)"""
        # Async Task für MQTT-Publishing erstellen
        asyncio.create_task(self.publish_can_data(msg))

    async def publish_can_data(self, msg):
        """Publiziert CAN-Daten async über MQTT"""
        can_data = {
            "id": hex(msg.arbitration_id),
            "data": list(msg.data),
            "timestamp": msg.timestamp,
            "is_extended": msg.is_extended_id
        }

        await self.publish(MqttTopics.CAN_RAW_DATA, can_data)

    async def handle_hardware_command(self, topic: str, message: dict):
        """Hardware-Command-Handler"""
        command = message.get("command")

        if command == "motor_control":
            await self._control_motor(message.get("parameters", {}))
        elif command == "lamp_control":
            await self._control_lamps(message.get("parameters", {}))
        elif command == "calibrate":
            await self._calibrate_sensors(message.get("parameters", {}))
        else:
            self.logger.warning(f"Unknown hardware command: {command}")

    async def handle_motor_command(self, topic: str, message: dict):
        """Motor-Command-Handler"""
        await self._control_motor(message)

    async def handle_lamp_command(self, topic: str, message: dict):
        """Lamp-Command-Handler"""
        await self._control_lamps(message)

    async def _control_motor(self, parameters: dict):
        """Steuert Motor basierend auf Parametern"""
        # TODO: Implementiere Motor-Steuerung
        self.logger.info(f"Motor control: {parameters}")

    async def _control_lamps(self, parameters: dict):
        """Steuert Lampen basierend auf Parametern"""
        # TODO: Implementiere Lampen-Steuerung
        self.logger.info(f"Lamp control: {parameters}")

    async def _calibrate_sensors(self, parameters: dict):
        """Kalibriert Sensoren basierend auf Parametern"""
        # TODO: Implementiere Sensor-Kalibrierung
        self.logger.info(f"Sensor calibration: {parameters}")

    async def stop(self):
        """Stoppt Hardware Bridge Service"""
        await self.publish_status("stopping")

        # CAN-Interface trennen
        try:
            self.can_interface.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting CAN: {e}")

        # MQTT stoppen
        await self.stop_mqtt()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = HardwareBridgeService()
    asyncio.run(service.start())
