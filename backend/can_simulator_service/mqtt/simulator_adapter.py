# backend/can_simulator_service/mqtt/simulator_adapter.py
"""
MQTT-Adapter für EGEA-Simulator
Infrastructure Layer - verbindet Domain-Logik mit MQTT
Folgt hexagonaler Architektur
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import asdict

from suspension_core.mqtt import MqttHandler
from ..core.egea_simulator import (
	EGEASimulator,
	EGEASimulationEvent,
	TestStartedEvent,
	TestStoppedEvent,
	DataGeneratedEvent,
	TestCompletedEvent,
	SimulationDataPoint
)

logger = logging.getLogger(__name__)


class SimulatorMqttAdapter:
	"""
	MQTT-Adapter für EGEA-Simulator

	Verantwortlichkeiten:
	- Übersetzt Domain-Events in MQTT-Messages
	- Verarbeitet eingehende MQTT-Commands
	- Publiziert Simulationsdaten in verschiedenen Formaten
	- Stellt Kompatibilität zu bestehenden Topics sicher
	"""

	def __init__(self, simulator: EGEASimulator, mqtt_handler: MqttHandler):
		"""
		Initialisiert MQTT-Adapter

		Args:
			simulator: EGEA-Simulator Instanz
			mqtt_handler: MQTT-Handler für Kommunikation
		"""
		self.simulator = simulator
		self.mqtt = mqtt_handler
		self.component_id = "egea_simulator"

		# Event-Handler beim Simulator registrieren
		self.simulator.subscribe_to_events(self._handle_simulation_event)

		# MQTT-Command-Handler registrieren
		self._setup_command_handlers()

		# Status-Tracking
		self._last_heartbeat = 0.0
		self._heartbeat_interval = 5.0  # Sekunden

	def _setup_command_handlers(self):
		"""Richtet MQTT-Command-Handler ein"""
		# Command-Topic abonnieren
		command_topic = self.mqtt.topics.get("SIMULATOR_COMMAND", "suspension/simulator/command")
		self.mqtt.subscribe(command_topic, self._handle_mqtt_command)

		logger.info(f"MQTT-Command-Handler registriert für Topic: {command_topic}")

	def _handle_simulation_event(self, event: EGEASimulationEvent):
		"""
		Verarbeitet Events vom Simulator und publiziert sie über MQTT

		Args:
			event: Simulation Event
		"""
		try:
			if isinstance(event, TestStartedEvent):
				self._publish_test_started(event)
			elif isinstance(event, TestStoppedEvent):
				self._publish_test_stopped(event)
			elif isinstance(event, DataGeneratedEvent):
				self._publish_simulation_data(event)
			elif isinstance(event, TestCompletedEvent):
				self._publish_test_completed(event)
			else:
				logger.warning(f"Unbekannter Event-Typ: {type(event)}")

		except Exception as e:
			logger.error(f"Fehler beim Verarbeiten von Simulation-Event: {e}")

	def _publish_test_started(self, event: TestStartedEvent):
		"""Publiziert Test-Start-Nachricht"""
		message = {
			"event": "test_started",
			"component": self.component_id,
			"timestamp": event.timestamp,
			"data": {
				"side": event.side,
				"duration": event.duration,
				"method": "phase_shift",
				"standard": "egea"
			}
		}

		self._publish_status_message(message)
		self._publish_system_status("testing", f"Test gestartet: {event.side}")

	def _publish_test_stopped(self, event: TestStoppedEvent):
		"""Publiziert Test-Stop-Nachricht"""
		message = {
			"event": "test_stopped",
			"component": self.component_id,
			"timestamp": event.timestamp,
			"data": {
				"side": event.side,
				"reason": "manual_stop"
			}
		}

		self._publish_status_message(message)
		self._publish_system_status("ready", "Test gestoppt")

	def _publish_test_completed(self, event: TestCompletedEvent):
		"""Publiziert Test-Completion-Nachricht"""
		message = {
			"event": "test_completed",
			"component": self.component_id,
			"timestamp": event.timestamp,
			"data": {
				"side": event.side,
				"duration": event.duration,
				"status": "completed"
			}
		}

		self._publish_status_message(message)
		self._publish_system_status("ready", "Test abgeschlossen")

		# Test-Result publizieren
		self._publish_test_result(event)

	def _publish_simulation_data(self, event: DataGeneratedEvent):
		"""
		Publiziert Simulationsdaten in verschiedenen Formaten

		Args:
			event: DataGeneratedEvent mit SimulationDataPoint
		"""
		data_point = event.data_point

		# 1. High-Level Measurement (für GUI)
		self._publish_high_level_measurement(data_point, event.side)

		# 2. Raw CAN-Style Data (für Kompatibilität)
		self._publish_can_style_data(data_point, event.side)

		# 3. Verarbeitete Messdaten
		self._publish_processed_measurement(data_point, event.side)

	def _publish_high_level_measurement(self, data: SimulationDataPoint, side: str):
		"""Publiziert High-Level Messdaten für GUI"""
		message = {
			"type": "high_level",
			"event": "test_data",
			"method": "phase_shift",
			"side": side,
			"position": "front_left" if side == "left" else "front_right",
			"timestamp": data.timestamp,
			"elapsed": data.elapsed,
			"frequency": data.frequency,
			"platform_position": data.platform_position,
			"tire_force": data.tire_force,
			"static_weight": 512,  # Konstant für Simulation
			"phase_shift": data.phase_shift,
			"dms_values": data.dms_values
		}

		# Topic für High-Level Measurements
		topic = self.mqtt.topics.get("MEASUREMENTS", "suspension/measurements/processed")
		self.mqtt.publish(topic, message)

	def _publish_can_style_data(self, data: SimulationDataPoint, side: str):
		"""Publiziert CAN-Style Daten für Rückwärtskompatibilität"""
		# Simuliert CAN-Frame Format
		can_data = {
			"type": "can_frame",
			"timestamp": data.timestamp,
			"arbitration_id": 0x1820FE71 if side == "left" else 0x1820FE72,
			"extended": True,
			"data": data.dms_values,  # DMS-Werte als Payload
			"side": side
		}

		# CAN-Data Topic
		can_topic = f"{self.mqtt.topics.get('CAN_DATA', 'suspension/can_data')}/{side}"
		self.mqtt.publish(can_topic, can_data)

	def _publish_processed_measurement(self, data: SimulationDataPoint, side: str):
		"""Publiziert verarbeitete Messdaten"""
		processed = {
			"component": self.component_id,
			"timestamp": data.timestamp,
			"measurement_type": "phase_shift_simulation",
			"side": side,
			"values": {
				"frequency_hz": data.frequency,
				"platform_position_mm": data.platform_position,
				"tire_force_n": data.tire_force,
				"phase_shift_deg": data.phase_shift,
				"elapsed_time_s": data.elapsed
			},
			"raw_data": {
				"dms1": data.dms_values[0],
				"dms2": data.dms_values[1],
				"dms3": data.dms_values[2],
				"dms4": data.dms_values[3]
			}
		}

		# Raw Measurements Topic
		topic = self.mqtt.topics.get("RAW_MEASUREMENTS", "suspension/measurements/raw")
		self.mqtt.publish(topic, processed)

	def _publish_test_result(self, event: TestCompletedEvent):
		"""Publiziert finales Testergebnis"""
		# Simulierte EGEA-konforme Bewertung
		simulator_status = self.simulator.get_current_status()
		damping_quality = simulator_status["damping_quality"]

		# Test-Result basierend auf Dämpfungsqualität
		result = {
			"test_id": f"sim_{int(event.timestamp)}",
			"timestamp": event.timestamp,
			"component": self.component_id,
			"method": "phase_shift",
			"standard": "egea",
			"side": event.side,
			"position": "front_left" if event.side == "left" else "front_right",
			"duration": event.duration,
			"results": {
				"damping_quality": damping_quality,
				"phase_shift_min": self._get_simulated_phase_result(damping_quality),
				"test_passed": damping_quality in ["excellent", "good"],
				"recommendation": self._get_recommendation(damping_quality)
			},
			"metadata": {
				"simulated": True,
				"config": simulator_status["config"]
			}
		}

		# Test Results Topic
		topic = self.mqtt.topics.get("TEST_RESULTS", "suspension/test/result")
		self.mqtt.publish(topic, result)

		# Full Test Result mit allen Details
		full_topic = self.mqtt.topics.get("FULL_TEST_RESULT", "suspension/test/full_result")
		self.mqtt.publish(full_topic, result)

	def _get_simulated_phase_result(self, quality: str) -> float:
		"""Gibt simuliertes Phasenverschiebungs-Ergebnis zurück"""
		phase_map = {
			"excellent": 48.0,
			"good": 38.0,
			"acceptable": 28.0,
			"poor": 18.0
		}
		return phase_map.get(quality, 25.0)

	def _get_recommendation(self, quality: str) -> str:
		"""Gibt Empfehlung basierend auf Dämpfungsqualität zurück"""
		recommendations = {
			"excellent": "Dämpfer in ausgezeichnetem Zustand",
			"good": "Dämpfer in gutem Zustand",
			"acceptable": "Dämpfer sollten überwacht werden",
			"poor": "Dämpfer müssen ausgetauscht werden"
		}
		return recommendations.get(quality, "Qualität unbekannt")

	def _handle_mqtt_command(self, topic: str, message: Dict[str, Any]):
		"""
		Verarbeitet eingehende MQTT-Commands

		Args:
			topic: MQTT-Topic
			message: Command-Message
		"""
		try:
			command = message.get("command")
			params = message.get("params", {})

			if command == "start_test":
				side = params.get("side", "left")
				duration = params.get("duration", 30.0)
				self.simulator.start_test(side, duration)

			elif command == "stop_test":
				self.simulator.stop_test()

			elif command == "set_damping_quality":
				quality = params.get("quality", "good")
				self.simulator.set_damping_quality(quality)

			elif command == "get_status":
				self._publish_status_response()

			else:
				logger.warning(f"Unbekannter Command: {command}")

		except Exception as e:
			logger.error(f"Fehler beim Verarbeiten von MQTT-Command: {e}")
			self._publish_error_response(str(e))

	def _publish_status_message(self, message: Dict[str, Any]):
		"""Publiziert Status-Nachricht"""
		topic = self.mqtt.topics.get("STATUS", "suspension/status")
		self.mqtt.publish(topic, message)

	def _publish_system_status(self, state: str, description: str):
		"""Publiziert System-Status"""
		message = {
			"component": self.component_id,
			"timestamp": time.time(),
			"state": state,
			"description": description,
			"details": self.simulator.get_current_status()
		}

		topic = self.mqtt.topics.get("SYSTEM_STATUS", "suspension/system/status")
		self.mqtt.publish(topic, message)

	def _publish_status_response(self):
		"""Publiziert Status-Response auf Anfrage"""
		status = self.simulator.get_current_status()

		response = {
			"event": "status_response",
			"component": self.component_id,
			"timestamp": time.time(),
			"status": status
		}

		self._publish_status_message(response)

	def _publish_error_response(self, error_message: str):
		"""Publiziert Fehler-Response"""
		response = {
			"event": "error",
			"component": self.component_id,
			"timestamp": time.time(),
			"error": error_message
		}

		self._publish_status_message(response)

	def publish_heartbeat(self):
		"""Publiziert Heartbeat-Signal"""
		current_time = time.time()

		if current_time - self._last_heartbeat >= self._heartbeat_interval:
			heartbeat = {
				"component": self.component_id,
				"timestamp": current_time,
				"alive": True,
				"test_active": self.simulator.test_active
			}

			topic = self.mqtt.topics.get("SYSTEM_HEARTBEAT", "suspension/system/heartbeat")
			self.mqtt.publish(topic, heartbeat)

			self._last_heartbeat = current_time

	def disconnect(self):
		"""Trennt MQTT-Verbindung und cleaned up"""
		# Event-Handler beim Simulator entfernen
		self.simulator.unsubscribe_from_events(self._handle_simulation_event)

		# Final Status publizieren
		self._publish_system_status("shutdown", "Simulator wird beendet")

		logger.info("MQTT-Adapter getrennt")
