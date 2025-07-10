# CAN-Bus Communication Module

> **Hardware-abstrahierte CAN-Bus-Kommunikation mit automatischer Simulator-Fallback-Strategie**

## 🎯 Überblick

Das CAN-Modul implementiert die **Infrastructure-Schicht** für robuste CAN-Bus-Kommunikation im Fahrwerkstester-System.
Es bietet eine einheitliche Abstraktionsschicht über verschiedene CAN-Hardware-Interfaces und integrierte Simulatoren
mit automatischer Fallback-Strategie für hardwarefreie Entwicklung.

### 🏗️ Architektur-Rolle

```mermaid
graph TB
    subgraph "Application Layer Services"
        HW[Hardware Bridge Service]
        SIM[CAN Simulator Service]
        BRIDGE[MQTT-CAN Bridge]
    end

    subgraph "CAN Infrastructure Layer"
        FACTORY[Interface Factory]
        INTERFACE[CAN Interface]
        ASYNC[Async Interface]
        CONVERTERS[Message Converters]
    end

    subgraph "Hardware Adapters"
        REAL[Real CAN Hardware]
        HYBRID[Hybrid Simulator]
        HIGHLEVEL[High-Level Simulator]
    end

subgraph "External Systems"
SOCKETCAN[SocketCAN (Linux)]
PCAN[PCAN (Windows)]
EUSAMA[EUSAMA Protocol]
ASA[ASA Protocol]
end

HW --> FACTORY
SIM --> FACTORY
BRIDGE --> FACTORY

FACTORY --> INTERFACE
FACTORY --> ASYNC
INTERFACE --> CONVERTERS

INTERFACE --> REAL
INTERFACE --> HYBRID
INTERFACE --> HIGHLEVEL

REAL --> SOCKETCAN
REAL --> PCAN
HYBRID --> EUSAMA
HYBRID --> ASA
```

## 📦 Modul-Struktur

```
common/suspension_core/can/
├── 🎯 interface_factory.py     # Factory Pattern - Automatische Interface-Auswahl
├── 🔧 can_interface.py         # Haupt-CAN-Interface mit Hardware-Integration
├── ⚡ async_interface.py       # Asynchrone CAN-Kommunikation für moderne Services
├── 🎭 hybrid_simulator.py      # Kombiniert Low-Level CAN + High-Level Daten
├── 📊 high_level_simulator.py  # Interpretierte Daten-Simulation
├── 🔄 converters/              # Message-Format-Konvertierung
│   ├── json_converter.py       # CAN ↔ JSON Transformation
│   └── __init__.py
└── __init__.py                 # Public API
```

## 🌟 Kernkomponenten

### 1. **Interface Factory** - Smart Auto-Selection

**Automatische Auswahl zwischen Hardware und Simulation basierend auf Verfügbarkeit**

```python
from suspension_core.can.interface_factory import create_can_interface
from suspension_core.config.manager import ConfigManager

# Automatische Interface-Auswahl (Smart Detection)
can_interface = create_can_interface()
print(f"Selected: {type(can_interface).__name__}")

# Explizite Konfiguration
config = ConfigManager()
can_interface = create_can_interface(
	config=config,
	simulation_type="hybrid",  # "low_level", "high_level", "hybrid"
	simulation_profile="eusama"  # "eusama", "asa"
)

# Platform-spezifische Auto-Detection
# Windows → Automatisch Simulator
# Linux mit SocketCAN → Hardware-Interface mit Simulator-Fallback
# macOS → Simulator

if can_interface.connect():
	print(f"✅ CAN connected at {can_interface.current_baudrate} bps")

	# Einheitliche API für Hardware & Simulation
	can_interface.send_message(
		arbitration_id=0x08AAAA71,
		data=[0x01, 30, 0, 0, 0, 0, 0, 0],  # Motor links, 30 Sekunden
		is_extended_id=True
	)

	# Message empfangen
	message = can_interface.recv_message(timeout=1.0)
	if message:
		print(f"📨 Received: ID=0x{message.arbitration_id:X}, Data={list(message.data)}")
else:
	print("❌ CAN connection failed")
```

### 2. **CAN Interface** - Robuste Hardware-Integration

**Production-ready CAN-Interface mit Auto-Baudrate-Detection und Fehlerbehandlung**

```python
from suspension_core.can.can_interface import CanInterface

# Hardware CAN-Interface mit Auto-Detection
can_interface = CanInterface(
	channel="can0",  # Linux: can0, can1; Windows: COM3, etc.
	auto_detect_baud=True,  # Automatische Baudrate-Erkennung
	baudrates=[1000000, 500000, 250000],  # Zu testende Baudraten
	protocol="eusama"  # Protokoll-spezifische Defaults
)

# Robuste Verbindung mit Retry-Logic
if can_interface.connect_with_auto_detect():
	print(f"🔗 Connected with {can_interface.current_baudrate} bps")


	# Thread-sichere Message-Callbacks
	@can_interface.add_message_callback
	def handle_eusama_data(message):
		"""Behandelt eingehende EUSAMA-Nachrichten"""
		if message.arbitration_id in [0x08AAAA60, 0x08AAAA61]:
			# DMS-Sensordaten dekodieren
			dms1 = int.from_bytes(message.data[0:2], 'big')
			dms2 = int.from_bytes(message.data[2:4], 'big')
			dms3 = int.from_bytes(message.data[4:6], 'big')
			dms4 = int.from_bytes(message.data[6:8], 'big')

			print(f"🔍 DMS Sensors: {dms1}, {dms2}, {dms3}, {dms4}")


	# Message-Logging für Debugging
	can_interface.log_message(message, log_file="can_messages.log")

	# Aktive CAN-IDs identifizieren
	active_ids = identify_can_ids(can_interface, duration=10)
	print(f"📊 Found {len(active_ids)} active CAN-IDs")

	# Sauberes Herunterfahren
	can_interface.shutdown()
```

### 3. **Async Interface** - Moderne Concurrency

**Asynchrone CAN-Kommunikation für Service-Integration**

```python
from suspension_core.can.async_interface import AsyncCanInterface
import asyncio


async def async_can_example():
	"""Asynchrone CAN-Kommunikation für moderne Services"""

	# Async CAN-Interface erstellen
	async_can = AsyncCanInterface(
		channel="can0",
		baudrate=1000000,
		protocol="eusama"
	)

	# Asynchrone Verbindung
	if await async_can.connect_async():
		print("⚡ Async CAN connected")

		# Async Message-Handler
		@async_can.on_message
		async def handle_async_message(message):
			"""Async Message-Handler"""
			print(f"⚡ Async Message: {message.arbitration_id:X}")

			# Async-Verarbeitung (z.B. MQTT-Publishing)
			await process_message_async(message)

		# Async Message senden
		await async_can.send_message_async(
			arbitration_id=0x08AAAA71,
			data=b'\x01\x1E\x00\x00\x00\x00\x00\x00'
		)

		# Async Message empfangen
		message = await async_can.recv_message_async(timeout=5.0)
		if message:
			print(f"📨 Async received: {message}")

		# Graceful shutdown
		await async_can.shutdown_async()


# Service-Integration
async def can_service_integration():
	"""Integration in async Service-Architektur"""

	async def can_listener_task():
		"""CAN-Listener als separater Task"""
		async_can = AsyncCanInterface()
		await async_can.connect_async()

		async for message in async_can.message_stream():
			# Message an andere Services weiterleiten
			await mqtt_handler.publish_async("suspension/can_data", {
				"id": message.arbitration_id,
				"data": list(message.data),
				"timestamp": message.timestamp
			})

	async def can_sender_task():
		"""CAN-Sender als separater Task"""
		while True:
			# Kommandos von MQTT empfangen und als CAN senden
			command = await mqtt_command_queue.get()
			await async_can.send_message_async(**command)

	# Tasks parallel ausführen
	await asyncio.gather(
		can_listener_task(),
		can_sender_task(),
		main_service_loop()
	)


# Ausführen
asyncio.run(async_can_example())
```

### 4. **Hybrid Simulator** - Best of Both Worlds

**Kombiniert realistische CAN-Frames mit interpretierten High-Level-Daten**

```python
from suspension_core.can.hybrid_simulator import HybridSimulator

# Hybrid-Simulator für vollständige Test-Coverage
hybrid_sim = HybridSimulator()

# Konfiguration
hybrid_sim.set_simulation_profile("eusama")  # EUSAMA-konforme Messages
hybrid_sim.set_damping_quality("good")  # Dämpfungsqualität
hybrid_sim.set_generate_low_level(True)  # CAN-Frames generieren
hybrid_sim.set_test_duration(30.0)  # Test-Dauer


# Test-Steuerung (EUSAMA-kompatibel)
def start_suspension_test(position: str):
	"""Startet Fahrwerkstest mit realistischer CAN-Simulation"""

	print(f"🚀 Starting suspension test: {position}")

	# EUSAMA Motor-Kommando senden
	motor_mask = 0x01 if position == "left" else 0x02
	hybrid_sim.send_message(
		arbitration_id=0x08AAAA71,  # Motor Control
		data=[motor_mask, 30, 0, 0, 0, 0, 0, 0],  # 30 Sekunden
		is_extended_id=True
	)


# Dual-Mode Message-Handling
@hybrid_sim.add_message_callback
def handle_hybrid_messages(message):
	"""Behandelt sowohl CAN-Frames als auch interpretierte Daten"""

	if hasattr(message, 'interpreted_data'):
		# High-Level interpretierte Daten
		data = message.interpreted_data
		print(f"📊 High-Level: {data['event']} - φ={data.get('phase_shift', 0):.1f}°")

		# An GUI weiterleiten
		gui_update = {
			"position": data['position'],
			"frequency": data['frequency'],
			"phase_shift": data['phase_shift'],
			"tire_force": data['tire_force']
		}
		mqtt_handler.publish("suspension/measurements/live", gui_update)

	else:
		# Low-Level CAN-Frame
		can_id = message.arbitration_id

		if can_id in [0x08AAAA60, 0x08AAAA61]:  # DMS-Daten
			# Rohe CAN-Daten dekodieren
			dms_values = []
			for i in range(4):
				dms = int.from_bytes(message.data[i * 2:(i + 1) * 2], 'big')
				dms_values.append(dms)

			print(f"🔧 CAN Frame: ID=0x{can_id:X}, DMS={dms_values}")

			# An Hardware-Bridge weiterleiten
			can_data = {
				"id": can_id,
				"data": list(message.data),
				"timestamp": message.timestamp
			}
			mqtt_handler.publish("suspension/hardware/can", can_data)


# Test ausführen
start_suspension_test("left")

# Kontinuierliche Message-Verarbeitung
while hybrid_sim.test_active:
	message = hybrid_sim.recv_message(timeout=0.1)
	if message:
		handle_hybrid_messages(message)
	time.sleep(0.01)
```

### 5. **Message Converters** - Protocol Translation

**Bidirektionale Konvertierung zwischen CAN-Frames und strukturierten Daten**

```python
from suspension_core.can.converters.json_converter import CanMessageConverter
import can

# Message-Converter für Protokoll-Translation
converter = CanMessageConverter()

# CAN → JSON Konvertierung
can_message = can.Message(
	arbitration_id=0x08AAAA60,
	data=b'\x02\x56\x02\x44\x01\xFF\x01\xF8',  # DMS-Rohdaten
	is_extended_id=True
)

topic, json_data = converter.can_to_json(can_message)
print(f"📤 CAN→JSON: {topic}")
print(f"   Data: {json_data}")

# JSON → CAN Konvertierung
json_command = {
	"command": "motor_control",
	"position": "left",
	"duration": 30,
	"timestamp": time.time()
}

can_message = converter.json_to_can("commands/motor", json_command)
if can_message:
	print(f"📥 JSON→CAN: ID=0x{can_message.arbitration_id:X}")


# Protokoll-spezifische Converter
class EusamaConverter(CanMessageConverter):
	"""EUSAMA-spezifischer Message-Converter"""

	def decode_dms_data(self, can_message):
		"""Dekodiert EUSAMA DMS-Sensordaten"""
		if can_message.arbitration_id in [0x08AAAA60, 0x08AAAA61]:
			data = can_message.data

			# 4 DMS-Sensoren (je 2 Bytes, Big-Endian)
			dms_sensors = []
			for i in range(4):
				dms_raw = int.from_bytes(data[i * 2:(i + 1) * 2], 'big')
				dms_voltage = (dms_raw / 1023.0) * 5.0  # ADC → Spannung
				dms_force = (dms_voltage - 2.5) * 400  # Spannung → Kraft (N)
				dms_sensors.append({
					"sensor": f"DMS{i + 1}",
					"raw": dms_raw,
					"voltage": dms_voltage,
					"force": dms_force
				})

			return {
				"event": "sensor_data",
				"protocol": "eusama",
				"position": "left" if can_message.arbitration_id == 0x08AAAA60 else "right",
				"sensors": dms_sensors,
				"timestamp": can_message.timestamp
			}

		return None

	def encode_motor_command(self, position: str, duration: int):
		"""Erstellt EUSAMA Motor-Kommando"""
		motor_mask = 0x01 if position == "left" else 0x02
		data = bytearray(8)
		data[0] = motor_mask
		data[1] = min(255, duration)  # Max. 255 Sekunden

		return can.Message(
			arbitration_id=0x08AAAA71,
			data=bytes(data),
			is_extended_id=True
		)


# EUSAMA-spezifische Verwendung
eusama_converter = EusamaConverter()

# DMS-Daten dekodieren
sensor_data = eusama_converter.decode_dms_data(can_message)
if sensor_data:
	print(f"🔍 Decoded sensors: {len(sensor_data['sensors'])} DMS")

# Motor-Kommando erstellen
motor_cmd = eusama_converter.encode_motor_command("left", 30)
can_interface.send_message(
	motor_cmd.arbitration_id,
	motor_cmd.data,
	motor_cmd.is_extended_id
)
```

## 🔧 Protokoll-Unterstützung

### EUSAMA-Protokoll Integration

```python
# EUSAMA-spezifische CAN-IDs und Datenformate
EUSAMA_IDS = {
	# DMS-Sensordaten
	"DMS_LEFT": 0x08AAAA60,  # Linke Seite - 4x DMS-Sensoren
	"DMS_RIGHT": 0x08AAAA61,  # Rechte Seite - 4x DMS-Sensoren

	# Motor-Steuerung
	"MOTOR_CONTROL": 0x08AAAA71,  # Motor-Kommandos (Start/Stop)
	"MOTOR_STATUS": 0x08AAAA66,  # Motor-Status-Feedback

	# System-Steuerung  
	"LAMP_CONTROL": 0x08AAAA72,  # Lampen-Steuerung
	"DISPLAY_CONTROL": 0x08AAAA73,  # Display-Anzeige

	# System-Status
	"SYSTEM_STATUS": 0x08AAAA65,  # Allgemeiner System-Status
	"ERROR_STATUS": 0x08AAAA67  # Fehler-Meldungen
}


# EUSAMA Message-Handler
class EusamaMessageHandler:
	"""Umfassender EUSAMA-Message-Handler"""

	def __init__(self, can_interface):
		self.can_interface = can_interface
		self.callbacks = {}

		# Standard-Handler registrieren
		self.register_handlers()

	def register_handlers(self):
		"""Registriert EUSAMA-spezifische Handler"""
		self.can_interface.add_message_callback(self.route_message)

	def route_message(self, message):
		"""Routet Messages basierend auf CAN-ID"""
		can_id = message.arbitration_id

		if can_id in [EUSAMA_IDS["DMS_LEFT"], EUSAMA_IDS["DMS_RIGHT"]]:
			self.handle_dms_data(message)
		elif can_id == EUSAMA_IDS["MOTOR_STATUS"]:
			self.handle_motor_status(message)
		elif can_id == EUSAMA_IDS["SYSTEM_STATUS"]:
			self.handle_system_status(message)
		else:
			self.handle_unknown_message(message)

	def handle_dms_data(self, message):
		"""Behandelt DMS-Sensordaten"""
		position = "left" if message.arbitration_id == EUSAMA_IDS["DMS_LEFT"] else "right"

		# DMS-Werte extrahieren (4 Sensoren × 2 Bytes)
		dms_values = []
		for i in range(4):
			raw_value = int.from_bytes(message.data[i * 2:(i + 1) * 2], byteorder='big')
			# Kalibrierung: ADC → Kraft (N)
			force = (raw_value - 512) * 2.0  # Beispiel-Kalibrierung
			dms_values.append(force)

		# Event an System weiterleiten
		self.emit_event("dms_data", {
			"position": position,
			"sensors": dms_values,
			"timestamp": message.timestamp
		})

	def handle_motor_status(self, message):
		"""Behandelt Motor-Status-Updates"""
		data = message.data
		motor_mask = data[0]
		remaining_time = data[1]
		status_flags = data[2]

		self.emit_event("motor_status", {
			"left_active": bool(motor_mask & 0x01),
			"right_active": bool(motor_mask & 0x02),
			"remaining_time": remaining_time,
			"status_flags": status_flags
		})

	def send_motor_command(self, position: str, duration: int):
		"""Sendet Motor-Kommando"""
		motor_mask = 0x01 if position == "left" else 0x02
		data = bytearray(8)
		data[0] = motor_mask
		data[1] = min(255, duration)

		return self.can_interface.send_message(
			EUSAMA_IDS["MOTOR_CONTROL"],
			bytes(data),
			is_extended_id=True
		)

	def send_lamp_command(self, left=False, drive_in=False, right=False):
		"""Sendet Lampen-Kommando"""
		lamp_mask = 0
		if left: lamp_mask |= 0x01
		if drive_in: lamp_mask |= 0x02
		if right: lamp_mask |= 0x04

		data = bytearray(8)
		data[0] = lamp_mask

		return self.can_interface.send_message(
			EUSAMA_IDS["LAMP_CONTROL"],
			bytes(data),
			is_extended_id=True
		)

	def emit_event(self, event_type: str, data: dict):
		"""Emittiert Events an registrierte Callbacks"""
		if event_type in self.callbacks:
			for callback in self.callbacks[event_type]:
				try:
					callback(data)
				except Exception as e:
					logger.error(f"Error in {event_type} callback: {e}")


# Verwendung
eusama_handler = EusamaMessageHandler(can_interface)


# Event-Handler registrieren
@eusama_handler.on("dms_data")
def handle_sensor_data(data):
	print(f"📊 DMS {data['position']}: {data['sensors']}")


# Motor-Test starten
eusama_handler.send_motor_command("left", 30)
```

### ASA-Protokoll Integration

```python
# ASA-spezifische CAN-IDs (niedrigere Baudraten)
ASA_IDS = {
	"STATUS_MESSAGE": 0x08298A60,  # System-Status
	"MEASUREMENT_DATA": 0x08298A61,  # Messdaten
	"ALIVE_MESSAGE": 0x08298A62,  # Heartbeat
	"COMMAND_MESSAGE": 0x08298A63  # Kommandos
}


class AsaMessageHandler:
	"""ASA-Protokoll-Handler für Rollen-/Plattenprüfstände"""

	def __init__(self, can_interface):
		self.can_interface = can_interface
		self.last_alive = time.time()

	def send_alive_message(self):
		"""Sendet ASA-Alive-Message"""
		data = bytearray(8)
		data[0] = 0xAA  # Alive-Marker
		data[1] = int(time.time() % 256)  # Timestamp-Byte

		return self.can_interface.send_message(
			ASA_IDS["ALIVE_MESSAGE"],
			bytes(data),
			is_extended_id=True
		)

	def decode_asa_measurement(self, message):
		"""Dekodiert ASA-Messdaten"""
		if message.arbitration_id == ASA_IDS["MEASUREMENT_DATA"]:
			data = message.data

			# ASA-Format: Verschiedene Messwerte
			measurement_type = data[0]
			value = int.from_bytes(data[1:5], byteorder='little')
			status = data[5]

			return {
				"type": measurement_type,
				"value": value,
				"status": status,
				"timestamp": message.timestamp
			}
```

## 🚀 Service-Integration Patterns

### Hardware Bridge Service Integration

```python
# Integration in Hardware Bridge Service
from suspension_core.can.interface_factory import create_can_interface
from suspension_core.mqtt.handler import MqttHandler


class CanHardwareBridge:
	"""CAN-Hardware-Bridge für MQTT-Integration"""

	def __init__(self, config):
		# CAN-Interface mit Auto-Detection
		self.can_interface = create_can_interface(
			config=config,
			simulation_type="hybrid"
		)

		# MQTT für Service-Kommunikation
		self.mqtt_handler = MqttHandler(
			client_id="can_hardware_bridge",
			app_type="backend"
		)

		# Event-Handler
		self.setup_handlers()

	def setup_handlers(self):
		"""Setup für bidirektionale CAN↔MQTT-Bridge"""

		# CAN→MQTT: Eingehende CAN-Messages an MQTT weiterleiten
		@self.can_interface.add_message_callback
		def can_to_mqtt(can_message):
			mqtt_message = {
				"id": can_message.arbitration_id,
				"data": list(can_message.data),
				"extended": can_message.is_extended_id,
				"timestamp": can_message.timestamp
			}
			self.mqtt_handler.publish("suspension/hardware/can", mqtt_message)

		# MQTT→CAN: MQTT-Kommandos als CAN-Messages senden
		@self.mqtt_handler.add_callback("commands")
		def mqtt_to_can(mqtt_message):
			if mqtt_message.get('target') == 'can':
				self.can_interface.send_message(
					arbitration_id=mqtt_message['id'],
					data=bytes(mqtt_message['data']),
					is_extended_id=mqtt_message.get('extended', True)
				)

	async def start_bridge(self):
		"""Startet die CAN-MQTT-Bridge"""
		# CAN-Verbindung
		if not self.can_interface.connect():
			raise ConnectionError("CAN connection failed")

		# MQTT-Verbindung
		if not self.mqtt_handler.connect():
			raise ConnectionError("MQTT connection failed")

		print("🌉 CAN-MQTT Bridge active")

		# Bridge-Loop
		while self.running:
			# CAN-Messages werden automatisch durch Callbacks verarbeitet
			await asyncio.sleep(0.01)

	def shutdown(self):
		"""Sauberes Herunterfahren"""
		self.running = False
		self.can_interface.shutdown()
		self.mqtt_handler.disconnect()
```

### CAN Simulator Service Integration

```python
# Integration in CAN Simulator Service
from suspension_core.can.hybrid_simulator import HybridSimulator


class CanSimulatorService:
	"""CAN-Simulator-Service für realistische Test-Daten"""

	def __init__(self):
		self.simulator = HybridSimulator()
		self.mqtt_handler = MqttHandler(
			client_id="can_simulator_service",
			app_type="backend"
		)

		self.setup_simulation()

	def setup_simulation(self):
		"""Setup für MQTT-gesteuerte Simulation"""

		# MQTT-Kommandos empfangen
		@self.mqtt_handler.add_callback("commands")
		def handle_test_commands(message):
			command = message.get('command')

			if command == 'start_test':
				position = message['position']
				duration = message.get('duration', 30)
				quality = message.get('quality', 'good')

				# Simulator konfigurieren
				self.simulator.set_damping_quality(quality)

				# Test starten (EUSAMA-kompatibel)
				motor_mask = 0x01 if position == "left" else 0x02
				self.simulator.send_message(
					arbitration_id=0x08AAAA71,
					data=[motor_mask, duration, 0, 0, 0, 0, 0, 0],
					is_extended_id=True
				)

			elif command == 'stop_test':
				self.simulator.send_message(
					arbitration_id=0x08AAAA71,
					data=[0x00, 0, 0, 0, 0, 0, 0, 0],  # Stop
					is_extended_id=True
				)

		# Simulator-Messages an MQTT weiterleiten
		@self.simulator.add_message_callback
		def forward_to_mqtt(message):
			if hasattr(message, 'interpreted_data'):
				# High-Level Daten an Processing Service
				data = message.interpreted_data
				self.mqtt_handler.publish("suspension/raw_data/complete", data)
			else:
				# Low-Level CAN-Frames an Hardware Bridge
				can_data = {
					"id": message.arbitration_id,
					"data": list(message.data),
					"timestamp": message.timestamp
				}
				self.mqtt_handler.publish("suspension/hardware/can", can_data)
```

## 🔒 Cross-Platform Compatibility

### Linux (SocketCAN)

```python
# SocketCAN-spezifische Konfiguration
linux_config = {
	"can": {
		"interface": "can0",
		"baudrate": 1000000,
		"protocol": "eusama",
		"use_simulator": False  # Hardware bevorzugen
	}
}

# SocketCAN-Interface erstellen
can_interface = create_can_interface(config=linux_config)

# CAN-Interface setup (falls nicht vorhanden)
import subprocess


def setup_socketcan():
	"""SocketCAN-Interface einrichten"""
	try:
		# Virtual CAN für Testing
		subprocess.run(["sudo", "modprobe", "vcan"], check=True)
		subprocess.run(["sudo", "ip", "link", "add", "dev", "vcan0", "type", "vcan"], check=True)
		subprocess.run(["sudo", "ip", "link", "set", "up", "vcan0"], check=True)

		print("✅ Virtual CAN interface vcan0 created")

		# Real CAN (Hardware erforderlich)
		subprocess.run(["sudo", "ip", "link", "set", "can0", "type", "can", "bitrate", "1000000"], check=True)
		subprocess.run(["sudo", "ip", "link", "set", "up", "can0"], check=True)

		print("✅ Hardware CAN interface can0 configured")

	except subprocess.CalledProcessError as e:
		print(f"⚠️ CAN setup failed: {e}")
		print("🔄 Fallback to simulator mode")
		return False

	return True


# Automatisches Setup
if sys.platform == "linux" and setup_socketcan():
	can_interface = CanInterface(channel="can0", baudrate=1000000)
else:
	can_interface = create_can_interface(simulation_type="hybrid")
```

### Windows (PCAN)

```python
# Windows-spezifische CAN-Konfiguration
windows_config = {
	"can": {
		"interface": "PCAN_USBBUS1",  # PCAN-Interface
		"baudrate": 1000000,
		"use_simulator": True  # Default für Windows
	}
}

# PCAN-Hardware-Unterstützung
try:
	import can

	# PCAN-Interface (wenn Hardware verfügbar)
	pcan_interface = can.interface.Bus(
		channel="PCAN_USBBUS1",
		bustype="pcan",
		bitrate=1000000
	)

	print("✅ PCAN hardware detected")

except ImportError:
	print("⚠️ PCAN library not available")
	print("📦 Install: pip install python-can[pcan]")

except can.CanError:
	print("⚠️ PCAN hardware not connected")
	print("🔄 Using simulator instead")

# Windows-optimierter Simulator
from suspension_core.can.windows_adapter import WindowsCanInterface

windows_can = WindowsCanInterface(
	simulation_profile="eusama",
	message_interval=0.001,  # 1000 Hz
	auto_start=True
)
```

## 📊 Performance & Monitoring

### Performance-Optimierungen

```python
# Performance-optimierte CAN-Kommunikation
class HighPerformanceCanInterface:
	"""Performance-optimierte CAN-Implementierung"""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# Performance-Metriken
		self.stats = {
			'messages_sent': 0,
			'messages_received': 0,
			'errors': 0,
			'avg_latency_ms': 0.0,
			'throughput_msg_per_sec': 0.0
		}

		# Performance-Optimierungen
		self.message_buffer = []
		self.buffer_size = 100
		self.flush_interval = 0.01  # 10ms

	def send_message_buffered(self, arbitration_id, data, **kwargs):
		"""Message-Buffering für höheren Durchsatz"""
		self.message_buffer.append({
			'id': arbitration_id,
			'data': data,
			'kwargs': kwargs,
			'timestamp': time.time()
		})

		# Buffer flushes bei Größe oder Timeout
		if (len(self.message_buffer) >= self.buffer_size or
				time.time() - self.last_flush > self.flush_interval):
			self.flush_message_buffer()

	def flush_message_buffer(self):
		"""Flush message buffer"""
		start_time = time.time()

		for msg in self.message_buffer:
			success = self.send_message(
				msg['id'],
				msg['data'],
				**msg['kwargs']
			)
			if success:
				self.stats['messages_sent'] += 1
			else:
				self.stats['errors'] += 1

		# Performance-Metriken aktualisieren
		flush_time = time.time() - start_time
		message_count = len(self.message_buffer)

		if message_count > 0:
			latency = (flush_time / message_count) * 1000  # ms
			self.stats['avg_latency_ms'] = (
					self.stats['avg_latency_ms'] * 0.9 + latency * 0.1
			)

		self.message_buffer.clear()
		self.last_flush = time.time()

	def get_performance_stats(self):
		"""Performance-Statistiken abrufen"""
		uptime = time.time() - self.start_time if hasattr(self, 'start_time') else 0

		if uptime > 0:
			self.stats['throughput_msg_per_sec'] = self.stats['messages_sent'] / uptime

		return self.stats.copy()


# Verwendung
perf_can = HighPerformanceCanInterface(channel="can0")

# Burst-Messages senden
for i in range(1000):
	perf_can.send_message_buffered(
		arbitration_id=0x123,
		data=f"msg_{i:04d}".encode()[:8]
	)

# Statistiken
stats = perf_can.get_performance_stats()
print(f"📈 Throughput: {stats['throughput_msg_per_sec']:.1f} msg/s")
print(f"📊 Average latency: {stats['avg_latency_ms']:.2f} ms")
print(f"❌ Error rate: {stats['errors'] / max(1, stats['messages_sent']) * 100:.1f}%")
```

### Health Monitoring

```python
# CAN-Health-Monitoring für Production
class CanHealthMonitor:
	"""Überwacht CAN-Interface-Health"""

	def __init__(self, can_interface):
		self.can_interface = can_interface
		self.health_metrics = {
			'connection_status': 'unknown',
			'message_rate': 0.0,
			'error_rate': 0.0,
			'last_message_time': 0.0,
			'reconnect_count': 0
		}

		# Health-Check-Thread
		self.monitoring = True
		self.monitor_thread = threading.Thread(
			target=self._monitor_loop,
			daemon=True
		)
		self.monitor_thread.start()

	def _monitor_loop(self):
		"""Health-Monitoring-Loop"""
		last_message_count = 0
		last_check_time = time.time()

		while self.monitoring:
			current_time = time.time()

			# Verbindungsstatus prüfen
			if self.can_interface.connected:
				self.health_metrics['connection_status'] = 'connected'

				# Message-Rate berechnen
				current_message_count = getattr(
					self.can_interface, 'message_count', 0
				)
				time_diff = current_time - last_check_time

				if time_diff > 0:
					message_diff = current_message_count - last_message_count
					self.health_metrics['message_rate'] = message_diff / time_diff

				last_message_count = current_message_count

				# Timeout-Check
				time_since_last_msg = current_time - self.health_metrics['last_message_time']
				if time_since_last_msg > 5.0:  # 5s ohne Message
					self.health_metrics['connection_status'] = 'timeout'
					self._attempt_reconnect()

			else:
				self.health_metrics['connection_status'] = 'disconnected'
				self._attempt_reconnect()

			last_check_time = current_time
			time.sleep(1.0)  # Health-Check alle Sekunde

	def _attempt_reconnect(self):
		"""Versucht Wiederverbindung"""
		try:
			if self.can_interface.connect_with_auto_detect():
				self.health_metrics['reconnect_count'] += 1
				print(f"🔄 CAN reconnected (attempt #{self.health_metrics['reconnect_count']})")
			else:
				print("❌ CAN reconnection failed")
		except Exception as e:
			print(f"🚨 CAN reconnection error: {e}")

	def get_health_report(self):
		"""Umfassender Health-Report"""
		return {
			'status': self.health_metrics['connection_status'],
			'message_rate_per_sec': self.health_metrics['message_rate'],
			'last_message_age_sec': time.time() - self.health_metrics['last_message_time'],
			'reconnect_count': self.health_metrics['reconnect_count'],
			'interface_info': {
				'channel': self.can_interface.channel,
				'baudrate': self.can_interface.current_baudrate,
				'connected': self.can_interface.connected
			}
		}


# Health-Monitoring aktivieren
health_monitor = CanHealthMonitor(can_interface)

# Periodic Health-Reports
while True:
	health = health_monitor.get_health_report()
	if health['status'] != 'connected':
		print(f"⚠️ CAN Health Issue: {health}")
	time.sleep(30)
```

---

**Cross-Platform Support**: Linux, Windows
**Hardware Integration**: SocketCAN, PCAN, Virtual CAN  
**Simulation Support**:Low-Level, High-Level, Hybrid  
**Letzte Aktualisierung**: Juni 2025  