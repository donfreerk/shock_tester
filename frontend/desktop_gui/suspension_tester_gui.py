"""
Vollständige EGEA-Fahrwerkstester GUI mit intelligenter Suspension-Discovery.

Diese GUI kombiniert:
- Intelligente Suspension-spezifische MQTT-Broker-Discovery
- Topic-basierte Broker-Analyse (95% Konfidenz für 'suspension/measurements/processed')
- Live-Datenvisualisierung
- EGEA-konforme Analyse
- Interaktive Discovery-Dialoge mit Topic-Details
- Robuste MQTT-Verbindung mit Fallback-System
"""

import argparse
import queue
import time
import threading
import json
import logging
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import matplotlib

# Unicode-Zeichen-Unterstützung für Matplotlib
try:
	import matplotlib.font_manager as fm

	# Versuche verfügbare Schriftarten zu finden, die Unicode unterstützen
	available_fonts = [f.name for f in fm.fontManager.ttflist]
	unicode_fonts = ['Segoe UI Emoji', 'Noto Color Emoji', 'Apple Color Emoji', 'DejaVu Sans']

	for font in unicode_fonts:
		if font in available_fonts:
			matplotlib.rcParams['font.family'] = font
			break
	else:
		# Fallback: Standard-Schriftart verwenden (ohne Unicode-Emojis)
		matplotlib.rcParams['font.family'] = 'DejaVu Sans'
except Exception:
	pass
try:
	import matplotlib.font_manager as fm

	# Windows 11 spezifische Emoji-Unterstützung
	matplotlib.rcParams['font.family'] = ['Segoe UI Emoji', 'Segoe UI']
	matplotlib.rcParams['font.sans-serif'] = [
		'Segoe UI Emoji',  # Windows Emoji-Schriftart
		'Segoe UI',  # Windows Standard
		'Apple Color Emoji',  # macOS Fallback
		'Noto Color Emoji',  # Google Fallback
		'DejaVu Sans'  # Standard Fallback
	]

	# Cache neu laden
	fm._rebuild()

except Exception as e:
	print(f"Schriftart-Konfiguration fehlgeschlagen: {e}")
	pass

import sys
import socket
import subprocess
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor
from scipy.signal import find_peaks
import numpy as np

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

matplotlib.use("TkAgg")
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from collections import deque

# EGEA-Module aus suspension_core importieren
try:
	from common.suspension_core.egea.processors.phase_shift_processor import EGEAPhaseShiftProcessor
	from common.suspension_core.egea.models.results import (
		EGEATestResult, VehicleType, PhaseShiftResult, AxleTestResult
	)
	from common.suspension_core.egea.config.parameters import EGEAParameters
	from common.suspension_core.egea.utils.signal_processing import EGEASignalProcessor

	# Bestehende suspension_core Module
	from common.suspension_core.config.manager import ConfigManager
	from common.suspension_core.mqtt.handler import MqttHandler
	from common.suspension_core import MqttClient

	SUSPENSION_CORE_AVAILABLE = True
except ImportError as e:
	logging.warning(f"suspension_core nicht verfügbar: {e}")
	SUSPENSION_CORE_AVAILABLE = False


	# Fallback-Klassen definieren
	class EGEAParameters:
		PHASE_SHIFT_MIN = 35.0
		MIN_CALC_FREQ = 6.0
		MAX_CALC_FREQ = 25.0

# Erweiterte Abhängigkeiten
try:
	import netifaces

	NETIFACES_AVAILABLE = True
except ImportError:
	NETIFACES_AVAILABLE = False

try:
	from zeroconf import ServiceBrowser, Zeroconf, ServiceListener

	ZEROCONF_AVAILABLE = True
except ImportError:
	ZEROCONF_AVAILABLE = False

try:
	import paho.mqtt.client as mqtt

	MQTT_AVAILABLE = True
except ImportError:
	MQTT_AVAILABLE = False
	raise ImportError("paho-mqtt ist erforderlich: pip install paho-mqtt")

# Konstanten
BUFFER_SIZE = 2000
UPDATE_RATE_MS = 100  # UI-Aktualisierungsrate
MAX_POINTS_TO_DISPLAY = 500

logger = logging.getLogger(__name__)

# ================================================================
# INTELLIGENT SUSPENSION DISCOVERY - Import der neuen Discovery
# ================================================================

# Importiere die intelligente Suspension-Discovery
try:
	from smart_suspension_discovery import (
		SmartSuspensionDiscovery,
		SuspensionBrokerInfo,
		EnhancedSuspensionDiscoveryDialog
	)

	SMART_DISCOVERY_AVAILABLE = False
	logger.info("✅ Intelligente Suspension-Discovery verfügbar")
except ImportError as e:
	logger.warning(f"⚠️ Intelligente Discovery nicht verfügbar: {e}")
	SMART_DISCOVERY_AVAILABLE = False


	# Minimale Fallback-Klassen
	class SuspensionBrokerInfo:
		def __init__(self, ip: str, **kwargs):
			self.ip = ip
			self.confidence = 0.5
			self.suspension_topics = []


# ================================================================
# ENHANCED CONFIG MANAGER mit intelligenter Discovery
# ================================================================

class EnhancedConfigManager:
	"""Enhanced Config Manager mit intelligenter Suspension-Discovery."""

	def __init__(self, config_path: Optional[str] = None):
		self.logger = logging.getLogger(__name__)
		self.config_path = config_path
		self.config = self._get_default_config()

		# Intelligente Discovery (falls verfügbar)
		if SMART_DISCOVERY_AVAILABLE:
			self.smart_discovery = SmartSuspensionDiscovery(timeout=8.0, max_workers=8)
		else:
			self.smart_discovery = None

		self._discovered_brokers: List[SuspensionBrokerInfo] = []
		self._last_discovery_time = 0
		self._discovery_cache_timeout = 300  # 5 Minuten

		# MQTT-Broker-Cache
		self._mqtt_broker_cache = []

		# Konfiguration laden
		self._load_configuration()

		self.logger.info("Enhanced Config Manager mit intelligenter Discovery initialisiert")

	def _get_default_config(self) -> Dict[str, Any]:
		"""Standard-Konfiguration."""
		return {
			"mqtt": {
				"broker": "auto",
				"port": 1883,
				"username": None,
				"password": None,
				"auto_discovery": True,
				"fallback_brokers": [
					"192.168.0.249",  # Aktuelle Pi-IP
					"192.168.0.100",
					"192.168.1.100",
					"localhost"
				]
			},
			"network": {
				"discovery_timeout": 5.0,
				"cache_timeout": 300
			},
			"egea": {
				"phase_shift_threshold": 35.0,
				"min_frequency": 6.0,
				"max_frequency": 25.0
			}
		}

	def _load_configuration(self):
		"""Lädt Konfiguration aus Datei."""
		if self.config_path and Path(self.config_path).exists():
			try:
				import yaml
				with open(self.config_path, 'r') as f:
					loaded_config = yaml.safe_load(f)
					if loaded_config:
						self.config.update(loaded_config)
						self.logger.info(f"Konfiguration geladen: {self.config_path}")
			except Exception as e:
				self.logger.error(f"Fehler beim Laden der Konfiguration: {e}")

	def get_mqtt_broker(self, force_discovery: bool = False) -> str:
		"""Gibt besten verfügbaren MQTT-Broker zurück."""
		if force_discovery or not self._mqtt_broker_cache:
			self._refresh_broker_list()

		# Cache durchgehen
		for broker in self._mqtt_broker_cache:
			if self._test_mqtt_broker(broker):
				self.logger.debug(f"MQTT-Broker aktiv: {broker}")
				return broker

		# Fallback
		fallback_brokers = self.get("mqtt.fallback_brokers", ["localhost"])
		for broker in fallback_brokers:
			if self._test_mqtt_broker(broker):
				self.logger.info(f"Fallback-Broker verwendet: {broker}")
				return broker

		self.logger.warning("Kein MQTT-Broker gefunden, verwende localhost")
		return "localhost"

	def _refresh_broker_list(self):
		"""Aktualisiert Broker-Liste mit intelligenter Discovery."""
		current_time = time.time()

		if (current_time - self._last_discovery_time) < self._discovery_cache_timeout:
			if self._mqtt_broker_cache:
				return

		self.logger.info("Starte intelligente Suspension-Broker-Discovery...")

		# Intelligente Discovery wenn verfügbar
		if self.smart_discovery and SMART_DISCOVERY_AVAILABLE:
			try:
				brokers = self.smart_discovery.discover_suspension_brokers()
				self._discovered_brokers = brokers

				# Broker-Liste erstellen (sortiert nach Konfidenz)
				self._mqtt_broker_cache = [broker.ip for broker in brokers if broker.confidence > 0.3]

				self.logger.info(f"Intelligente Discovery: {len(brokers)} Suspension-Broker gefunden")
			except Exception as e:
				self.logger.warning(f"Intelligente Discovery fehlgeschlagen: {e}")
				self._mqtt_broker_cache = []
		else:
			self.logger.info("Intelligente Discovery nicht verfügbar, verwende Fallbacks")
			self._mqtt_broker_cache = []

		# Fallback-Broker hinzufügen
		for broker in self.get("mqtt.fallback_brokers", []):
			if broker not in self._mqtt_broker_cache:
				self._mqtt_broker_cache.append(broker)

		self._last_discovery_time = current_time
		self.logger.info(f"Broker-Discovery abgeschlossen: {len(self._mqtt_broker_cache)} Broker")

	def _test_mqtt_broker(self, broker: str) -> bool:
		"""Testet MQTT-Broker."""
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(2.0)
			result = sock.connect_ex((broker, self.get("mqtt.port", 1883)))
			sock.close()
			return result == 0
		except Exception:
			return False

	def get_discovered_devices(self) -> List[SuspensionBrokerInfo]:
		"""Gibt entdeckte Broker zurück."""
		return self._discovered_brokers.copy()

	def force_broker_discovery(self) -> str:
		"""Erzwingt neue Discovery."""
		self._mqtt_broker_cache.clear()
		self._last_discovery_time = 0
		return self.get_mqtt_broker(force_discovery=True)

	def add_fallback_broker(self, broker: str):
		"""Fügt Fallback-Broker hinzu."""
		fallbacks = self.get("mqtt.fallback_brokers", [])
		if broker not in fallbacks:
			fallbacks.insert(0, broker)  # An den Anfang
			self.set("mqtt.fallback_brokers", fallbacks)

	def get(self, path: str, default: Any = None) -> Any:
		"""Holt Konfigurationswert."""
		keys = path.split('.')
		current = self.config
		for key in keys:
			if isinstance(current, dict) and key in current:
				current = current[key]
			else:
				return default
		return current

	def set(self, path: str, value: Any):
		"""Setzt Konfigurationswert."""
		keys = path.split('.')
		current = self.config
		for key in keys[:-1]:
			if key not in current:
				current[key] = {}
			current = current[key]
		current[keys[-1]] = value


# ================================================================
# NETWORK DISCOVERY DIALOG (Fallback)
# ================================================================

class NetworkDiscoveryDialog:
	"""Dialog für interaktive Pi-Discovery (Fallback)."""

	def __init__(self, parent):
		self.parent = parent
		self.result = None
		self.discovery_running = False

		# Dialog erstellen
		self.dialog = tk.Toplevel(parent)
		self.dialog.title("🔍 Fallback: Pi-Geräte im Netzwerk suchen")
		self.dialog.geometry("700x500")
		self.dialog.transient(parent)
		self.dialog.grab_set()

		self._setup_dialog()
		self._center_dialog()

	def _setup_dialog(self):
		"""Erstellt Dialog-UI."""
		main_frame = ttk.Frame(self.dialog, padding="15")
		main_frame.pack(fill=tk.BOTH, expand=True)

		# Header
		header_frame = ttk.Frame(main_frame)
		header_frame.pack(fill=tk.X, pady=(0, 15))

		title_label = ttk.Label(header_frame, text="Fallback: Raspberry Pi mit MQTT-Broker suchen",
		                        font=("TkDefaultFont", 12, "bold"))
		title_label.pack()

		info_label = ttk.Label(header_frame,
		                       text="Einfache Suche nach Geräten mit aktivem MQTT-Broker (Port 1883)")
		info_label.pack(pady=(5, 0))

		# Manuelle Eingabe
		manual_frame = ttk.LabelFrame(main_frame, text="✏️ Manuelle IP-Eingabe", padding="10")
		manual_frame.pack(fill=tk.X)

		manual_grid = ttk.Frame(manual_frame)
		manual_grid.pack(fill=tk.X)

		ttk.Label(manual_grid, text="IP-Adresse:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

		self.manual_ip_var = tk.StringVar(value="192.168.0.249")
		self.manual_ip_entry = ttk.Entry(manual_grid, textvariable=self.manual_ip_var, width=15)
		self.manual_ip_entry.grid(row=0, column=1, padx=(0, 10))

		ttk.Button(manual_grid, text="🧪 Testen", command=self._test_manual_ip).grid(row=0, column=2, padx=(0, 10))
		ttk.Button(manual_grid, text="✅ Verwenden", command=self._use_manual_ip).grid(row=0, column=3)

		self.manual_status_var = tk.StringVar(value="")
		ttk.Label(manual_grid, textvariable=self.manual_status_var).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))

		# Buttons
		button_frame = ttk.Frame(main_frame)
		button_frame.pack(fill=tk.X, pady=(20, 10))

		ttk.Button(button_frame, text="❌ Abbrechen", command=self._cancel).pack(side=tk.RIGHT)

	def _center_dialog(self):
		"""Zentriert Dialog."""
		self.dialog.update_idletasks()
		x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
		y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
		self.dialog.geometry(f"+{x}+{y}")

	def _test_manual_ip(self):
		"""Testet manuelle IP."""
		ip = self.manual_ip_var.get().strip()
		if not ip:
			self.manual_status_var.set("❌ Bitte IP-Adresse eingeben")
			return

		try:
			# IP-Format validieren
			parts = ip.split('.')
			if len(parts) != 4 or not all(0 <= int(p) <= 255 for p in parts):
				self.manual_status_var.set("❌ Ungültiges IP-Format")
				return

			# MQTT-Port testen
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(3.0)
			result = sock.connect_ex((ip, 1883))
			sock.close()

			if result == 0:
				self.manual_status_var.set("✅ MQTT-Broker erreichbar")
			else:
				self.manual_status_var.set("❌ MQTT-Broker nicht erreichbar")

		except Exception as e:
			self.manual_status_var.set(f"❌ Test fehlgeschlagen: {e}")

	def _use_manual_ip(self):
		"""Verwendet manuelle IP."""
		ip = self.manual_ip_var.get().strip()
		if not ip:
			messagebox.showwarning("Keine IP", "Bitte geben Sie eine IP-Adresse ein.")
			return

		# Testen
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(3.0)
			result = sock.connect_ex((ip, 1883))
			sock.close()

			if result == 0:
				self.result = {'ip': ip, 'hostname': f"manual-{ip}", 'method': 'manual'}
				self.dialog.destroy()
			else:
				messagebox.showerror("Verbindungstest fehlgeschlagen",
				                     f"Kann keine Verbindung zu {ip}:1883 herstellen.\n"
				                     "Prüfen Sie die IP-Adresse und MQTT-Broker-Status.")
		except Exception as e:
			messagebox.showerror("Verbindungstest fehlgeschlagen", f"Fehler beim Testen: {e}")

	def _cancel(self):
		"""Bricht Dialog ab."""
		self.result = None
		self.dialog.destroy()

	def show(self) -> Optional[dict]:
		"""Zeigt Dialog modal."""
		self.dialog.wait_window()
		return self.result


# ================================================================
# SIMPLIFIED MQTT CLIENT
# ================================================================

class SimpleMqttClient:
	"""Vereinfachter MQTT-Client für das Discovery-System."""

	def __init__(self, broker: str, port: int = 1883, client_id: Optional[str] = None):
		self.broker = broker
		self.port = port
		self.client_id = client_id or f"suspension_gui_{int(time.time())}"

		self.client = mqtt.Client(client_id=self.client_id)
		self.connected = False
		self.message_callback = None

		# Callbacks setzen
		self.client.on_connect = self._on_connect
		self.client.on_disconnect = self._on_disconnect
		self.client.on_message = self._on_message

		logger.info(f"MQTT-Client erstellt: {self.client_id}")

	def _on_connect(self, client, userdata, flags, rc):
		"""MQTT-Verbindung hergestellt."""
		if rc == 0:
			self.connected = True
			logger.info(f"MQTT verbunden: {self.broker}:{self.port}")
		else:
			logger.error(f"MQTT-Verbindung fehlgeschlagen: Code {rc}")

	def _on_disconnect(self, client, userdata, rc):
		"""MQTT-Verbindung getrennt."""
		self.connected = False
		if rc != 0:
			logger.warning(f"MQTT-Verbindung unerwartet getrennt: Code {rc}")
		else:
			logger.info("MQTT-Verbindung getrennt")

	def _on_message(self, client, userdata, msg):
		"""MQTT-Nachricht empfangen."""
		try:
			topic = msg.topic
			payload = msg.payload.decode('utf-8')

			# JSON parsen wenn möglich
			try:
				data = json.loads(payload)
			except json.JSONDecodeError:
				data = payload

			if self.message_callback:
				self.message_callback(topic, data)

		except Exception as e:
			logger.error(f"Fehler bei MQTT-Nachrichtenverarbeitung: {e}")

	def connect(self, timeout: float = 10.0) -> bool:
		"""Verbindet mit MQTT-Broker."""
		try:
			self.client.connect(self.broker, self.port, 60)
			self.client.loop_start()

			# Warten auf Verbindung
			start_time = time.time()
			while not self.connected and (time.time() - start_time) < timeout:
				time.sleep(0.1)

			return self.connected
		except Exception as e:
			logger.error(f"MQTT-Verbindung fehlgeschlagen: {e}")
			return False

	def disconnect(self):
		"""Trennt MQTT-Verbindung."""
		try:
			self.client.loop_stop()
			self.client.disconnect()
		except Exception as e:
			logger.error(f"Fehler beim MQTT-Trennen: {e}")

	def subscribe(self, topic: str, callback: Optional[callable] = None) -> bool:
		"""Abonniert MQTT-Topic."""
		try:
			if callback:
				self.message_callback = callback

			result = self.client.subscribe(topic)
			success = result[0] == mqtt.MQTT_ERR_SUCCESS
			if success:
				logger.debug(f"Topic abonniert: {topic}")
			else:
				logger.warning(f"Topic-Abonnement fehlgeschlagen: {topic}")
			return success
		except Exception as e:
			logger.error(f"Fehler beim Topic-Abonnement: {e}")
			return False

	def publish(self, topic: str, payload: Any) -> bool:
		"""Veröffentlicht MQTT-Nachricht."""
		try:
			if isinstance(payload, dict):
				payload = json.dumps(payload)

			result = self.client.publish(topic, payload)
			success = result.rc == mqtt.MQTT_ERR_SUCCESS
			if success:
				logger.debug(f"Nachricht veröffentlicht: {topic}")
			else:
				logger.warning(f"Veröffentlichung fehlgeschlagen: {topic}")
			return success
		except Exception as e:
			logger.error(f"Fehler beim Veröffentlichen: {e}")
			return False

	def is_connected(self) -> bool:
		"""Prüft Verbindungsstatus."""
		return self.connected


# ================================================================
# ENHANCED DATA BUFFER
# ================================================================

class EnhancedDataBuffer:
	"""Erweiterter Datenpuffer mit EGEA-Analyse und automatischer Feldererkennung."""

	def __init__(self, max_size: int = 2000):
		self.max_size = max_size
		self.lock = threading.RLock()

		# Datenpuffer
		self.data_buffer = deque(maxlen=max_size)
		self.detected_fields = set()

		# Test-Status
		self.test_active = False
		self.test_position = None
		self.test_start_time = None

		# EGEA-Parameter (Fallback falls suspension_core nicht verfügbar)
		self.egea_params = EGEAParameters() if SUSPENSION_CORE_AVAILABLE else type('EGEAParams', (), {
			'PHASE_SHIFT_MIN': 35.0,
			'MIN_CALC_FREQ': 6.0,
			'MAX_CALC_FREQ': 25.0
		})()

		# EGEA-Status
		self.current_egea_status = {
			"min_phase_shift": None,
			"min_phase_freq": None,
			"quality_index": 0.0,
			"passing": False,
			"evaluation": "insufficient_data",
			"data_count": 0
		}

		logger.info("Enhanced Data Buffer initialisiert")

	def add_data(self, data: Dict[str, Any]):
		"""Fügt Daten zum Puffer hinzu."""
		with self.lock:
			# Zeitstempel hinzufügen
			if 'timestamp' not in data:
				data['timestamp'] = time.time()

			# Datenfelder erkennen
			for key, value in data.items():
				if isinstance(value, (int, float)) and key != 'timestamp':
					self.detected_fields.add(key)

			# Zu Puffer hinzufügen
			self.data_buffer.append(data)

			# EGEA-Analyse wenn Test aktiv
			if self.test_active and self._is_measurement_data(data):
				self._perform_simple_egea_analysis()

	def _is_measurement_data(self, data: Dict[str, Any]) -> bool:
		"""Prüft ob Daten Messdaten sind."""
		position_fields = ['platform_position', 'platform_pos', 'position']
		force_fields = ['tire_force', 'force', 'tire_contact_force']

		has_position = any(field in data for field in position_fields)
		has_force = any(field in data for field in force_fields)

		return has_position and has_force

	def _perform_simple_egea_analysis(self):
		"""Vereinfachte EGEA-Analyse."""
		try:
			if len(self.data_buffer) < 20:
				return

			# Letzte 50 Datenpunkte analysieren
			recent_data = list(self.data_buffer)[-50:]

			# Daten extrahieren
			positions = []
			forces = []
			frequencies = []

			for d in recent_data:
				# Flexible Feldnamen
				pos = (d.get('platform_position') or d.get('platform_pos') or
				       d.get('position', 0))
				force = (d.get('tire_force') or d.get('force') or
				         d.get('tire_contact_force', 0))
				freq = d.get('frequency', 0)

				positions.append(float(pos))
				forces.append(float(force))
				frequencies.append(float(freq))

			if len(positions) >= 20:
				# Einfache Phasenverschiebungsberechnung
				pos_array = np.array(positions)
				force_array = np.array(forces)

				# Kreuzkorrelation für Phasenverschiebung
				correlation = np.correlate(pos_array, force_array, mode='full')
				max_corr_idx = np.argmax(correlation)

				# Phasenverschiebung in Grad
				phase_shift = abs((max_corr_idx - len(force_array)) * 360 / len(force_array)) % 180

				# Frequenz
				current_freq = np.mean([f for f in frequencies if f > 0]) if any(f > 0 for f in frequencies) else 0

				# EGEA-Bewertung
				threshold = self.egea_params.PHASE_SHIFT_MIN
				quality_index = min(100.0, (phase_shift / threshold) * 100) if threshold > 0 else 0

				# Status aktualisieren
				self.current_egea_status.update({
					"min_phase_shift": phase_shift,
					"min_phase_freq": current_freq,
					"quality_index": quality_index,
					"passing": phase_shift >= threshold,
					"evaluation": "passing" if phase_shift >= threshold else "failing",
					"data_count": len(self.data_buffer)
				})

				logger.debug(f"EGEA-Analyse: φ={phase_shift:.1f}°, Q={quality_index:.1f}%")

		except Exception as e:
			logger.error(f"Fehler bei EGEA-Analyse: {e}")

	def get_recent_data(self, max_points: int = 500) -> List[Dict[str, Any]]:
		"""Gibt letzte Datenpunkte zurück."""
		with self.lock:
			return list(self.data_buffer)[-max_points:]

	def get_detected_fields(self) -> List[str]:
		"""Gibt erkannte Datenfelder zurück."""
		with self.lock:
			return sorted(list(self.detected_fields))

	def start_test(self, position: str):
		"""Startet einen Test."""
		with self.lock:
			self.test_active = True
			self.test_position = position
			self.test_start_time = time.time()
			# EGEA-Status zurücksetzen
			self.current_egea_status = {
				"min_phase_shift": None,
				"min_phase_freq": None,
				"quality_index": 0.0,
				"passing": False,
				"evaluation": "starting_test",
				"data_count": 0
			}
			logger.info(f"Test gestartet: {position}")

	def stop_test(self):
		"""Stoppt den Test."""
		with self.lock:
			self.test_active = False
			logger.info("Test gestoppt")

	def clear(self):
		"""Leert den Puffer."""
		with self.lock:
			self.data_buffer.clear()
			self.detected_fields.clear()
			logger.info("Datenpuffer geleert")


# ================================================================
# COMPLETE AUTO-DISCOVERY GUI
# ================================================================

class CompleteAutoDiscoveryGUI:
	"""
	Vollständige EGEA-GUI mit intelligenter Suspension-Discovery und Live-Visualisierung.

	Features:
	- Intelligente Suspension-spezifische MQTT-Broker-Discovery
	- Topic-basierte Broker-Analyse (suspension/measurements/processed = 95% Konfidenz)
	- Live-Datenvisualisierung
	- EGEA-konforme Analyse
	- Interaktive Discovery-Dialoge mit Topic-Details
	- Robuste MQTT-Verbindung mit Fallback-System
	"""

	def __init__(self, root, config_path: Optional[str] = None):
		self.root = root
		self.root.title("🎯 EGEA-Fahrwerkstester mit intelligenter Suspension-Discovery")
		self.root.geometry("1500x1000")
		self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

		# Enhanced Config Manager
		self.config = EnhancedConfigManager(config_path)

		# EGEA-Parameter
		self.egea_params = EGEAParameters() if SUSPENSION_CORE_AVAILABLE else type('EGEAParams', (), {
			'PHASE_SHIFT_MIN': 35.0
		})()

		# Datenpuffer
		self.data_buffer = EnhancedDataBuffer()

		# MQTT-Client
		self.mqtt_client = None

		# UI-Variablen
		self.broker_status_var = tk.StringVar(value="Nicht verbunden")
		self.broker_ip_var = tk.StringVar(value="Ermittle...")
		self.data_count_var = tk.StringVar(value="0 Datenpunkte")
		self.egea_status_var = tk.StringVar(value="Bereit")
		self.egea_phase_var = tk.StringVar(value="φ: - °")
		self.egea_quality_var = tk.StringVar(value="Q: -%")

		# Visualisierungsoptionen
		self.show_all_data = tk.BooleanVar(value=False)
		self.selected_fields = {}  # Checkbox-Variablen

		# Chart-Komponenten
		self.fig = None
		self.canvas = None
		self.charts = {}

		# Test-Log
		self.test_log = None

		# UI aufbauen
		self._setup_ui()

		# MQTT-Verbindung mit Auto-Discovery
		self._init_auto_mqtt()

		# Update-Loop starten
		self.root.after(UPDATE_RATE_MS, self._update_loop)

		logger.info("Vollständige GUI mit intelligenter Suspension-Discovery initialisiert")

	def _setup_ui(self):
		"""Erstellt die vollständige UI."""
		# Hauptcontainer mit Grid
		self.root.grid_rowconfigure(0, weight=1)
		self.root.grid_columnconfigure(0, weight=1)

		main_container = ttk.Frame(self.root)
		main_container.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
		main_container.grid_rowconfigure(2, weight=1)  # Chart-Bereich erweiterbat
		main_container.grid_columnconfigure(0, weight=1)

		# Status-Bereich (Zeile 0)
		self._setup_enhanced_status_frame(main_container)

		# Visualisierungs-Optionen (Zeile 1)
		self._setup_visualization_options(main_container)

		# Chart-Bereich (Zeile 2, expandiert)
		self._setup_chart_frame(main_container)

		# Control-Bereich (Zeile 3)
		self._setup_enhanced_control_frame(main_container)

		# Test-Log (Zeile 4)
		self._setup_test_log(main_container)

	def _setup_enhanced_status_frame(self, parent):
		"""Erweiterte Status-Anzeige mit Auto-Discovery."""
		status_frame = ttk.LabelFrame(parent, text="🎯 System-Status & Intelligente Suspension-Discovery", padding="15")
		status_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))

		# Grid für bessere Kontrolle
		status_grid = ttk.Frame(status_frame)
		status_grid.pack(fill=tk.X)

		# Zeile 1: MQTT-Status
		ttk.Label(status_grid, text="MQTT-Broker:", font=("TkDefaultFont", 10, "bold")).grid(
			row=0, column=0, sticky=tk.W, padx=(0, 10))

		broker_label = ttk.Label(status_grid, textvariable=self.broker_ip_var,
		                         font=("TkDefaultFont", 10, "bold"), foreground='blue')
		broker_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

		ttk.Label(status_grid, text="Status:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
		self.status_label = ttk.Label(status_grid, textvariable=self.broker_status_var)
		self.status_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))

		# Discovery-Buttons
		discovery_frame = ttk.Frame(status_grid)
		discovery_frame.grid(row=0, column=4, sticky=tk.E)

		ttk.Button(discovery_frame, text="🎯 Intelligente Suche",
		           command=self._open_discovery_dialog, width=15).pack(side=tk.LEFT, padx=2)

		ttk.Button(discovery_frame, text="🔄 Neusuche",
		           command=self._force_rediscovery, width=12).pack(side=tk.LEFT, padx=2)

		ttk.Button(discovery_frame, text="ℹ️ Info",
		           command=self._show_discovery_info, width=8).pack(side=tk.LEFT, padx=2)

		# Zeile 2: Daten & EGEA-Status
		ttk.Label(status_grid, text="Empfangene Daten:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
		ttk.Label(status_grid, textvariable=self.data_count_var).grid(row=1, column=1, sticky=tk.W, pady=(10, 0))

		ttk.Label(status_grid, text="EGEA-Status:").grid(row=1, column=2, sticky=tk.W, pady=(10, 0), padx=(20, 10))
		self.egea_status_label = ttk.Label(status_grid, textvariable=self.egea_status_var,
		                                   font=("TkDefaultFont", 10, "bold"))
		self.egea_status_label.grid(row=1, column=3, sticky=tk.W, pady=(10, 0))

		# Zeile 3: EGEA-Details
		egea_details = ttk.Frame(status_grid)
		egea_details.grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=(5, 0))

		ttk.Label(egea_details, textvariable=self.egea_phase_var).pack(side=tk.LEFT, padx=(0, 20))
		ttk.Label(egea_details, textvariable=self.egea_quality_var).pack(side=tk.LEFT, padx=(0, 20))
		ttk.Label(egea_details, text=f"Grenzwert: {self.egea_params.PHASE_SHIFT_MIN}°").pack(side=tk.LEFT)

	def _setup_visualization_options(self, parent):
		"""Visualisierungs-Optionen."""
		vis_frame = ttk.LabelFrame(parent, text="📊 Visualisierungs-Optionen", padding="10")
		vis_frame.grid(row=1, column=0, sticky='ew', pady=(0, 10))

		options_grid = ttk.Frame(vis_frame)
		options_grid.pack(fill=tk.X)

		# Haupt-Checkbox
		self.show_all_check = ttk.Checkbutton(
			options_grid,
			text="🔍 Alle empfangenen Datenfelder anzeigen (dynamische Charts)",
			variable=self.show_all_data,
			command=self._toggle_show_all_data
		)
		self.show_all_check.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

		# Container für dynamische Feld-Checkboxen
		self.fields_frame = ttk.LabelFrame(options_grid, text="Verfügbare Datenfelder:")
		self.fields_frame.grid(row=1, column=0, sticky='ew')

		# Info-Label
		self.fields_info_var = tk.StringVar(value="Keine Datenfelder erkannt. Warten auf Daten...")
		ttk.Label(self.fields_frame, textvariable=self.fields_info_var).pack(pady=5)

	def _setup_chart_frame(self, parent):
		"""Chart-Bereich mit dynamischer Anpassung."""
		chart_frame = ttk.LabelFrame(parent, text="📈 Live-Datenvisualisierung", padding="5")
		chart_frame.grid(row=2, column=0, sticky='nsew', pady=(0, 10))

		# Matplotlib-Setup
		self.fig = plt.figure(figsize=(16, 10))
		self.fig.patch.set_facecolor('white')

		# Canvas
		self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
		self.canvas.draw()
		self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

		# Toolbar
		self.toolbar = NavigationToolbar2Tk(self.canvas, chart_frame)
		self.toolbar.update()

		# Standard-Charts erstellen
		self._create_standard_charts()

	def _create_standard_charts(self):
		"""Erstellt Standard-EGEA-Charts."""
		self.fig.clear()

		# 2x2 Grid für EGEA-Standard-Daten
		self.charts = {
			'platform_position': self.fig.add_subplot(2, 2, 1),
			'tire_force': self.fig.add_subplot(2, 2, 2),
			'phase_shift': self.fig.add_subplot(2, 2, 3),
			'frequency': self.fig.add_subplot(2, 2, 4)
		}

		# Chart-Konfiguration
		self.charts['platform_position'].set_title('🔧 Plattformposition', fontsize=12, fontweight='bold')
		self.charts['platform_position'].set_ylabel('Position (mm)')
		self.charts['platform_position'].grid(True, alpha=0.3)

		self.charts['tire_force'].set_title('⚡ Reifenkraft', fontsize=12, fontweight='bold')
		self.charts['tire_force'].set_ylabel('Kraft (N)')
		self.charts['tire_force'].grid(True, alpha=0.3)

		self.charts['phase_shift'].set_title('📊 Phasenverschiebung (EGEA)', fontsize=12, fontweight='bold')
		self.charts['phase_shift'].set_ylabel('Phase (°)')
		self.charts['phase_shift'].grid(True, alpha=0.3)

		self.charts['frequency'].set_title('🌊 Frequenz', fontsize=12, fontweight='bold')
		self.charts['frequency'].set_ylabel('Frequenz (Hz)')
		self.charts['frequency'].grid(True, alpha=0.3)

		self.fig.tight_layout(pad=3.0)
		self.canvas.draw()

	def _setup_enhanced_control_frame(self, parent):
		"""Erweiterte Control-Optionen."""
		control_frame = ttk.LabelFrame(parent, text="🎛️ Test-Steuerung & Konfiguration", padding="15")
		control_frame.grid(row=3, column=0, sticky='ew', pady=(0, 10))

		# Test-Controls
		test_frame = ttk.LabelFrame(control_frame, text="EGEA-Test", padding="10")
		test_frame.pack(fill=tk.X, pady=(0, 10))

		test_grid = ttk.Frame(test_frame)
		test_grid.pack(fill=tk.X)

		# Position
		ttk.Label(test_grid, text="Position:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
		self.position_combo = ttk.Combobox(test_grid, values=[
			"front_left", "front_right", "rear_left", "rear_right"
		], state="readonly", width=12)
		self.position_combo.set("front_left")
		self.position_combo.grid(row=0, column=1, padx=(0, 20))

		# Fahrzeugtyp
		ttk.Label(test_grid, text="Fahrzeugtyp:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
		self.vehicle_combo = ttk.Combobox(test_grid, values=["M1", "N1"], state="readonly", width=5)
		self.vehicle_combo.set("M1")
		self.vehicle_combo.grid(row=0, column=3, padx=(0, 20))

		# Test-Buttons
		self.start_button = ttk.Button(test_grid, text="🚀 EGEA-Test starten",
		                               command=self._start_test, width=20)
		self.start_button.grid(row=0, column=4, padx=(20, 10))

		self.stop_button = ttk.Button(test_grid, text="⏹ Test stoppen",
		                              command=self._stop_test, state='disabled', width=15)
		self.stop_button.grid(row=0, column=5, padx=(0, 10))

		self.emergency_button = ttk.Button(test_grid, text="🚨 NOTAUS",
		                                   command=self._emergency_stop, width=12)
		self.emergency_button.grid(row=0, column=6)

		# MQTT & System Controls
		mqtt_frame = ttk.LabelFrame(control_frame, text="MQTT & System", padding="10")
		mqtt_frame.pack(fill=tk.X, pady=(0, 10))

		mqtt_grid = ttk.Frame(mqtt_frame)
		mqtt_grid.pack(fill=tk.X)

		ttk.Button(mqtt_grid, text="🔄 MQTT neu verbinden",
		           command=self._reconnect_mqtt, width=20).grid(row=0, column=0, padx=(0, 10))

		ttk.Button(mqtt_grid, text="🗑 Datenpuffer leeren",
		           command=self._clear_buffer, width=18).grid(row=0, column=1, padx=(0, 10))

		ttk.Button(mqtt_grid, text="📡 Test-Kommando senden",
		           command=self._send_test_command, width=20).grid(row=0, column=2, padx=(0, 10))

		ttk.Button(mqtt_grid, text="💾 Konfiguration speichern",
		           command=self._save_config, width=20).grid(row=0, column=3)

	def _setup_test_log(self, parent):
		"""Test-Log mit Filteroptionen."""
		log_frame = ttk.LabelFrame(parent, text="📋 System-Log", padding="5")
		log_frame.grid(row=4, column=0, sticky='ew')

		# Log-Controls
		log_controls = ttk.Frame(log_frame)
		log_controls.pack(fill=tk.X, pady=(0, 5))

		ttk.Button(log_controls, text="🗑 Log leeren",
		           command=self._clear_log).pack(side=tk.LEFT, padx=(0, 10))

		ttk.Button(log_controls, text="💾 Log speichern",
		           command=self._save_log).pack(side=tk.LEFT)

		# ScrolledText für Log
		self.test_log = scrolledtext.ScrolledText(log_frame, height=8, state=tk.DISABLED,
		                                          font=("Courier", 9))
		self.test_log.pack(fill=tk.BOTH, expand=True)

		# Tag-Konfiguration für farbige Nachrichten
		self.test_log.tag_config("error", foreground="red", font=("Courier", 9, "bold"))
		self.test_log.tag_config("success", foreground="green", font=("Courier", 9, "bold"))
		self.test_log.tag_config("warning", foreground="orange", font=("Courier", 9, "bold"))
		self.test_log.tag_config("info", foreground="blue")

	def _init_auto_mqtt(self):
		"""Initialisiert MQTT mit automatischer Discovery."""
		try:
			self._log_message("🔍 MQTT", "Starte automatische Broker-Erkennung...", "info")

			# Besten Broker ermitteln
			broker = self.config.get_mqtt_broker()
			self.broker_ip_var.set(broker)

			self._log_message("🌐 Discovery", f"Bester Broker gefunden: {broker}", "success")

			# MQTT-Client erstellen
			self.mqtt_client = SimpleMqttClient(
				broker=broker,
				port=self.config.get('mqtt.port', 1883),
				client_id=f"egea_gui_{int(time.time())}"
			)

			# Verbindung mit Fallback-Mechanismus
			max_retries = 3
			for attempt in range(max_retries):
				if self.mqtt_client.connect(timeout=10.0):
					self.broker_status_var.set("Verbunden ✅")
					self.status_label.configure(foreground='green')

					# Standard-Topics abonnieren
					self._subscribe_standard_topics()

					self._log_message("✅ MQTT", f"Erfolgreich verbunden mit {broker}", "success")
					return True
				else:
					self._log_message("⚠️ MQTT", f"Verbindungsversuch {attempt + 1} fehlgeschlagen", "warning")
					if attempt < max_retries - 1:
						# Nächsten Broker versuchen
						broker = self.config.get_mqtt_broker(force_discovery=True)
						self.broker_ip_var.set(broker)
						self.mqtt_client.broker = broker

			# Alle Versuche fehlgeschlagen
			self.broker_status_var.set("Alle Broker offline ❌")
			self.status_label.configure(foreground='red')
			self._log_message("❌ MQTT", "Alle MQTT-Broker-Versuche fehlgeschlagen", "error")
			return False

		except Exception as e:
			self.broker_status_var.set("Initialisierungsfehler ❌")
			self.status_label.configure(foreground='red')
			self._log_message("❌ MQTT", f"Initialisierung fehlgeschlagen: {e}", "error")
			return False

	def _subscribe_standard_topics(self):
		"""Abonniert Standard-MQTT-Topics."""
		if not self.mqtt_client or not self.mqtt_client.is_connected():
			return

		# Standard-Topics für vereinfachte Architektur
		topics = [
			"suspension/measurements/processed",
			"suspension/test/result",
			"suspension/status",
			"suspension/commands"
		]

		success_count = 0
		for topic in topics:
			if self.mqtt_client.subscribe(topic, self._on_mqtt_message):
				success_count += 1
				self._log_message("📡 MQTT", f"Topic abonniert: {topic}")

		self._log_message("📡 MQTT", f"{success_count}/{len(topics)} Topics abonniert",
		                  "success" if success_count > 0 else "warning")

		# Test-Nachricht senden
		test_msg = {
			"source": "egea_auto_discovery_gui",
			"message": "GUI bereit für Datenempfang",
			"timestamp": time.time(),
			"discovery_info": {
				"broker_used": self.mqtt_client.broker,
				"discovered_devices": len(self.config.get_discovered_devices())
			}
		}
		self.mqtt_client.publish("suspension/status", test_msg)

	def _on_mqtt_message(self, topic: str, data: Any):
		"""Verarbeitet eingehende MQTT-Nachrichten."""
		try:
			logger.debug(f"MQTT-Nachricht: {topic}")

			if topic == "suspension/measurements/processed":
				self._process_measurement_data(data)
			elif topic == "suspension/test/result":
				self._process_test_result(data)
			elif topic == "suspension/status":
				self._process_status_update(data)
			else:
				self._log_message("📨 MQTT", f"Unbekanntes Topic: {topic}")

		except Exception as e:
			logger.error(f"Fehler bei MQTT-Nachrichtenverarbeitung: {e}")
			self._log_message("❌ MQTT", f"Nachrichtenverarbeitung fehlgeschlagen: {e}", "error")

	def _process_measurement_data(self, data: Dict[str, Any]):
		"""Verarbeitet Messdaten."""
		try:
			# Daten zum Puffer hinzufügen
			self.data_buffer.add_data(data)

			# UI-Updates
			data_count = len(self.data_buffer.data_buffer)
			self.data_count_var.set(f"{data_count} Datenpunkte")

			# Dynamische Feld-Updates
			self._update_dynamic_fields()

			# Log nur alle 100 Nachrichten
			if data_count % 100 == 0:
				self._log_message("📊 Daten", f"{data_count} Datenpunkte empfangen")

		except Exception as e:
			logger.error(f"Fehler bei Messdatenverarbeitung: {e}")

	def _process_test_result(self, data: Dict[str, Any]):
		"""Verarbeitet Testergebnisse."""
		try:
			if 'egea_result' in data:
				result = data['egea_result']
				passing = result.get('passing', False)
				phase_shift = result.get('min_phase_shift', 0)

				result_text = "BESTANDEN ✅" if passing else "NICHT BESTANDEN ❌"
				self._log_message("🏁 Test", f"EGEA-Ergebnis: {result_text} (φ={phase_shift:.1f}°)",
				                  "success" if passing else "warning")
		except Exception as e:
			logger.error(f"Fehler bei Testergebnis-Verarbeitung: {e}")

	def _process_status_update(self, data: Dict[str, Any]):
		"""Verarbeitet Status-Updates."""
		try:
			source = data.get('source', 'System')
			message = data.get('message', data.get('status', 'Update'))

			self._log_message(f"📡 {source}", message)
		except Exception as e:
			logger.error(f"Fehler bei Status-Update: {e}")

	def _update_dynamic_fields(self):
		"""Aktualisiert dynamische Datenfeld-Anzeige."""
		try:
			detected_fields = self.data_buffer.get_detected_fields()

			if detected_fields:
				self.fields_info_var.set(f"Erkannte Felder: {', '.join(detected_fields[:10])}" +
				                         ("..." if len(detected_fields) > 10 else ""))

				# Neue Felder zu Checkboxen hinzufügen
				if self.show_all_data.get():
					self._update_field_checkboxes(detected_fields)
		except Exception as e:
			logger.error(f"Fehler bei dynamischer Feld-Aktualisierung: {e}")

	def _update_field_checkboxes(self, fields: List[str]):
		"""Aktualisiert Feld-Checkboxen."""
		# Bestehende Checkboxen entfernen
		for widget in self.fields_frame.winfo_children():
			if isinstance(widget, ttk.Checkbutton):
				widget.destroy()

		# Neue Checkboxes erstellen
		row, col = 0, 0
		for field in fields:
			if field not in self.selected_fields:
				var = tk.BooleanVar(value=True)
				self.selected_fields[field] = var

			checkbox = ttk.Checkbutton(
				self.fields_frame,
				text=field.replace('_', ' ').title(),
				variable=self.selected_fields[field],
				command=self._update_dynamic_charts
			)
			checkbox.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)

			col += 1
			if col >= 6:  # 6 Spalten
				col = 0
				row += 1

	def _toggle_show_all_data(self):
		"""Schaltet zwischen Standard- und dynamischer Ansicht um."""
		if self.show_all_data.get():
			self._log_message("📊 Visualisierung", "Dynamische Datenfeld-Anzeige aktiviert", "info")
			self._update_dynamic_fields()
		else:
			self._log_message("📊 Visualisierung", "Standard EGEA-Ansicht aktiviert", "info")
			self._create_standard_charts()

	def _update_dynamic_charts(self):
		"""Erstellt Charts basierend auf ausgewählten Feldern."""
		if not self.show_all_data.get():
			return

		# Aktive Felder ermitteln
		active_fields = [field for field, var in self.selected_fields.items() if var.get()]

		if not active_fields:
			return

		# Charts neu erstellen
		self.fig.clear()
		self.charts = {}

		# Grid-Layout berechnen
		n_fields = len(active_fields)
		rows = int(np.ceil(np.sqrt(n_fields)))
		cols = int(np.ceil(n_fields / rows))

		for i, field in enumerate(active_fields):
			ax = self.fig.add_subplot(rows, cols, i + 1)
			ax.set_title(field.replace('_', ' ').title(), fontsize=10, fontweight='bold')
			ax.set_ylabel(field)
			ax.grid(True, alpha=0.3)
			self.charts[field] = ax

		self.fig.tight_layout(pad=2.0)
		self.canvas.draw()

	def _update_charts(self):
		"""Aktualisiert alle Charts mit aktuellen Daten."""
		try:
			recent_data = self.data_buffer.get_recent_data(MAX_POINTS_TO_DISPLAY)

			if not recent_data or not self.charts:
				return

			# Zeit-Array erstellen
			timestamps = [d.get('timestamp', 0) for d in recent_data]
			if not timestamps:
				return

			start_time = timestamps[0]
			times = [(t - start_time) for t in timestamps]

			# Charts aktualisieren
			for field, ax in self.charts.items():
				try:
					# Daten extrahieren
					values = []
					for d in recent_data:
						value = d.get(field, 0)
						try:
							values.append(float(value))
						except (ValueError, TypeError):
							values.append(0)

					if values and any(v != 0 for v in values):
						ax.clear()
						ax.plot(times, values, linewidth=1.5, alpha=0.8, color='blue')
						ax.set_title(field.replace('_', ' ').title(), fontsize=10, fontweight='bold')
						ax.set_ylabel(field)
						ax.grid(True, alpha=0.3)

						# EGEA-spezifische Anzeigen
						if field == 'phase_shift':
							ax.axhline(y=self.egea_params.PHASE_SHIFT_MIN,
							           color='red', linestyle='--', alpha=0.7,
							           label=f'EGEA-Grenze ({self.egea_params.PHASE_SHIFT_MIN}°)')
							ax.legend(fontsize=8)

				except Exception as e:
					logger.debug(f"Fehler beim Chart-Update für {field}: {e}")

			self.fig.tight_layout(pad=2.0)
			self.canvas.draw_idle()

		except Exception as e:
			logger.error(f"Fehler beim Chart-Update: {e}")

	def _update_egea_status(self):
		"""Aktualisiert EGEA-Status-Anzeige."""
		try:
			egea_status = self.data_buffer.current_egea_status

			# Status-Text
			evaluation = egea_status.get("evaluation", "insufficient_data")
			status_map = {
				"passing": "BESTANDEN ✅",
				"failing": "NICHT BESTANDEN ❌",
				"starting_test": "Test startet...",
				"insufficient_data": "Warte auf Daten..."
			}

			status_text = status_map.get(evaluation, "Unbekannt")
			self.egea_status_var.set(status_text)

			# Farbe basierend auf Status
			if evaluation == "passing":
				self.egea_status_label.configure(foreground='green')
			elif evaluation == "failing":
				self.egea_status_label.configure(foreground='red')
			else:
				self.egea_status_label.configure(foreground='blue')

			# Phasenverschiebung
			min_phase = egea_status.get("min_phase_shift")
			if min_phase is not None:
				self.egea_phase_var.set(f"φmin: {min_phase:.1f}°")
			else:
				self.egea_phase_var.set("φmin: -")

			# Qualitätsindex
			quality = egea_status.get("quality_index", 0)
			self.egea_quality_var.set(f"Q: {quality:.0f}%")

		except Exception as e:
			logger.error(f"Fehler beim EGEA-Status-Update: {e}")

	def _start_test(self):
		"""Startet EGEA-Test."""
		try:
			position = self.position_combo.get()
			vehicle_type = self.vehicle_combo.get()

			# Test im Datenpuffer starten
			self.data_buffer.start_test(position)

			# Test-Kommando über MQTT senden
			if self.mqtt_client and self.mqtt_client.is_connected():
				command = {
					"command": "start_test",
					"position": position,
					"vehicle_type": vehicle_type,
					"test_method": "egea_phase_shift",
					"duration": 30,
					"timestamp": time.time(),
					"source": "egea_auto_discovery_gui"
				}

				self.mqtt_client.publish("suspension/commands", command)

			# UI aktualisieren
			self.start_button.config(state='disabled')
			self.stop_button.config(state='normal')
			self.position_combo.config(state='disabled')
			self.vehicle_combo.config(state='disabled')

			self._log_message("🚀 Test", f"EGEA-Test gestartet: {position} ({vehicle_type})", "success")

		except Exception as e:
			logger.error(f"Fehler beim Test-Start: {e}")
			self._log_message("❌ Test", f"Test-Start fehlgeschlagen: {e}", "error")

	def _stop_test(self):
		"""Stoppt EGEA-Test."""
		try:
			# Test im Datenpuffer stoppen
			self.data_buffer.stop_test()

			# Stop-Kommando senden
			if self.mqtt_client and self.mqtt_client.is_connected():
				command = {
					"command": "stop_test",
					"timestamp": time.time(),
					"source": "egea_auto_discovery_gui"
				}
				self.mqtt_client.publish("suspension/commands", command)

			# UI zurücksetzen
			self.start_button.config(state='normal')
			self.stop_button.config(state='disabled')
			self.position_combo.config(state='readonly')
			self.vehicle_combo.config(state='readonly')

			self._log_message("⏹ Test", "EGEA-Test gestoppt", "info")

		except Exception as e:
			logger.error(f"Fehler beim Test-Stopp: {e}")
			self._log_message("❌ Test", f"Test-Stopp fehlgeschlagen: {e}", "error")

	def _emergency_stop(self):
		"""NOT-STOP."""
		try:
			# Sofort stoppen
			if self.data_buffer.test_active:
				self._stop_test()

			# Emergency-Kommando senden
			if self.mqtt_client and self.mqtt_client.is_connected():
				emergency_cmd = {
					"command": "emergency_stop",
					"timestamp": time.time(),
					"source": "egea_auto_discovery_gui",
					"reason": "user_initiated"
				}
				self.mqtt_client.publish("suspension/commands", emergency_cmd)

			self._log_message("🚨 NOTAUS", "NOT-STOP ausgelöst!", "error")
			messagebox.showwarning("NOT-STOP", "NOT-STOP wurde ausgelöst!\nAlle Tests wurden gestoppt.")

		except Exception as e:
			logger.error(f"Fehler beim NOT-STOP: {e}")
			self._log_message("❌ NOTAUS", f"NOT-STOP fehlgeschlagen: {e}", "error")

	def _open_discovery_dialog(self):
		"""Öffnet intelligente Suspension-Discovery-Dialog."""
		try:
			# Import der intelligenten Discovery
			from smart_suspension_discovery import EnhancedSuspensionDiscoveryDialog

			dialog = EnhancedSuspensionDiscoveryDialog(self.root)
			result = dialog.show()

			if result:
				ip = result['ip']
				method = result['method']
				confidence = result.get('confidence', 0) * 100
				suspension_topics = result.get('suspension_topics', [])

				# Neue IP zur Konfiguration hinzufügen
				self.config.add_fallback_broker(ip)

				# MQTT neu verbinden mit neuer IP
				self.broker_ip_var.set(ip)
				self._reconnect_mqtt()

				# Erfolgsmeldung mit Details
				topic_info = f" ({len(suspension_topics)} Suspension-Topics)" if suspension_topics else ""
				self._log_message("🎯 Discovery",
				                  f"Intelligenter Broker ausgewählt: {ip} (Konfidenz: {confidence:.0f}%{topic_info})",
				                  "success")

				messagebox.showinfo("Suspension-Broker konfiguriert",
				                    f"MQTT-Broker {ip} wurde analysiert und konfiguriert.\n"
				                    f"Konfidenz: {confidence:.0f}%\n"
				                    f"Gefundene Suspension-Topics: {len(suspension_topics)}\n"
				                    f"Methode: {method}")

		except ImportError as e:
			logger.error(f"Intelligente Discovery nicht verfügbar: {e}")
			self._log_message("❌ Discovery", f"Intelligente Discovery fehlt: {e}", "error")

			# Fallback auf einfache Discovery falls neue nicht verfügbar
			try:
				if SMART_DISCOVERY_AVAILABLE:
					self._log_message("❌ Discovery", "Intelligente Discovery verfügbar aber Dialog fehlgeschlagen", "error")
				else:
					dialog = NetworkDiscoveryDialog(self.root)
					result = dialog.show()
					if result:
						ip = result['ip']
						self.config.add_fallback_broker(ip)
						self.broker_ip_var.set(ip)
						self._reconnect_mqtt()
						self._log_message("🔍 Discovery", f"Fallback-Broker konfiguriert: {ip}", "success")
			except Exception as fe:
				logger.error(f"Auch Fallback-Discovery fehlgeschlagen: {fe}")
				self._log_message("❌ Discovery", f"Alle Discovery-Methoden fehlgeschlagen: {fe}", "error")

		except Exception as e:
			logger.error(f"Discovery-Dialog fehlgeschlagen: {e}")
			self._log_message("❌ Discovery", f"Discovery-Dialog fehlgeschlagen: {e}", "error")

	def _force_rediscovery(self):
		"""Erzwingt neue Discovery."""
		try:
			self._log_message("🔄 Discovery", "Starte neue Broker-Suche...", "info")

			def run_discovery():
				try:
					new_broker = self.config.force_broker_discovery()
					self.root.after(0, self._rediscovery_complete, new_broker)
				except Exception as e:
					self.root.after(0, self._rediscovery_error, str(e))

			threading.Thread(target=run_discovery, daemon=True).start()

		except Exception as e:
			logger.error(f"Rediscovery fehlgeschlagen: {e}")

	def _rediscovery_complete(self, new_broker: str):
		"""Callback für abgeschlossene Rediscovery."""
		self.broker_ip_var.set(new_broker)
		self._log_message("✅ Discovery", f"Neue Broker-Suche abgeschlossen: {new_broker}", "success")

		# Automatisch neu verbinden wenn anderer Broker gefunden
		if new_broker != self.mqtt_client.broker:
			self._reconnect_mqtt()

	def _rediscovery_error(self, error: str):
		"""Callback für Rediscovery-Fehler."""
		self._log_message("❌ Discovery", f"Broker-Suche fehlgeschlagen: {error}", "error")

	def _show_discovery_info(self):
		"""Zeigt Discovery-Informationen."""
		try:
			devices = self.config.get_discovered_devices()

			info_text = f"[DISCOVERY] Intelligente Suspension-Discovery-Informationen\n\n"
			info_text += f"Diese Discovery analysiert MQTT-Broker auf Suspension-Topics!\n"
			info_text += f"Der goldene Topic 'suspension/measurements/processed' = 95% Konfidenz!\n\n"

			info_text += f"Aktueller MQTT-Broker: {self.broker_ip_var.get()}\n"
			info_text += f"Verbindungsstatus: {self.broker_status_var.get()}\n\n"

			if SMART_DISCOVERY_AVAILABLE:
				info_text += "[SEARCH] Entdeckte Suspension-Broker:\n"
				if devices:
					for i, broker in enumerate(devices, 1):
						status = "[ACTIVE]" if broker.ip == self.broker_ip_var.get() else "[AVAILABLE]"
						info_text += f"  {i}. {status} {broker.ip} ({broker.hostname})\n"
						info_text += f"     Konfidenz: {broker.confidence * 100:.0f}%\n"
						info_text += f"     Suspension-Topics: {len(broker.suspension_topics)}\n"

						# Goldener Topic hervorheben
						from smart_suspension_discovery import SuspensionTopicAnalyzer
						has_golden = SuspensionTopicAnalyzer.GOLDEN_TOPIC in broker.suspension_topics
						info_text += f"     Goldener Topic: {'[YES]' if has_golden else '[NO]'}\n\n"
				else:
					info_text += "  Keine Suspension-Broker gefunden\n\n"
			else:
				info_text += "⚠️ Intelligente Discovery nicht verfügbar\n"
				info_text += "Installieren Sie die smart_suspension_discovery.py für bessere Ergebnisse\n\n"

			# Kritische Suspension-Topics
			info_text += "🎯 Der goldene Topic für die GUI:\n"
			info_text += "  🥇 suspension/measurements/processed (DAS reicht!)\n\n"

			info_text += "🔧 Zusätzliche Suspension-Topics:\n"
			additional_topics = [
				"suspension/test/result",
				"suspension/commands",
				"suspension/status",
				"suspension/heartbeat"
			]
			for topic in additional_topics:
				info_text += f"  • {topic}\n"
			info_text += "\n"

			# Fallback-Broker
			fallbacks = self.config.get("mqtt.fallback_brokers", [])
			info_text += "🔄 Fallback-Broker-Liste:\n"
			for i, broker in enumerate(fallbacks, 1):
				status = "✅ Aktiv" if broker == self.broker_ip_var.get() else "⚪ Verfügbar"
				info_text += f"  {i}. {status} {broker}\n"

			info_text += "\n💡 Tipp: Die intelligente Suche findet Broker mit 95% Konfidenz!"

			# Info-Dialog
			self._show_info_dialog("🎯 Intelligente Discovery-Informationen", info_text)

		except Exception as e:
			logger.error(f"Fehler bei Discovery-Info: {e}")
			self._log_message("❌ Info", f"Discovery-Info fehlgeschlagen: {e}", "error")

	def _show_info_dialog(self, title: str, text: str):
		"""Zeigt Info-Dialog."""
		dialog = tk.Toplevel(self.root)
		dialog.title(title)
		dialog.geometry("600x500")
		dialog.transient(self.root)

		text_frame = ttk.Frame(dialog)
		text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

		text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Courier", 10))
		scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
		text_widget.configure(yscrollcommand=scrollbar.set)

		text_widget.insert('1.0', text)
		text_widget.config(state=tk.DISABLED)

		text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

		ttk.Button(dialog, text="Schließen", command=dialog.destroy).pack(pady=5)

	def _reconnect_mqtt(self):
		"""Verbindet MQTT neu."""
		try:
			self._log_message("🔄 MQTT", "Verbindung wird neu hergestellt...", "info")

			# Alte Verbindung trennen
			if self.mqtt_client:
				self.mqtt_client.disconnect()

			# Neue Verbindung initialisieren
			success = self._init_auto_mqtt()

			if success:
				self._log_message("✅ MQTT", "Neuverbindung erfolgreich", "success")
			else:
				self._log_message("❌ MQTT", "Neuverbindung fehlgeschlagen", "error")

		except Exception as e:
			logger.error(f"MQTT-Neuverbindung fehlgeschlagen: {e}")
			self._log_message("❌ MQTT", f"Neuverbindung fehlgeschlagen: {e}", "error")

	def _clear_buffer(self):
		"""Leert Datenpuffer."""
		try:
			self.data_buffer.clear()
			self.data_count_var.set("0 Datenpunkte")

			# Charts leeren
			for ax in self.charts.values():
				ax.clear()
				ax.grid(True, alpha=0.3)
			self.canvas.draw()

			self._log_message("🗑 System", "Datenpuffer geleert", "info")

		except Exception as e:
			logger.error(f"Fehler beim Puffer-Leeren: {e}")

	def _send_test_command(self):
		"""Sendet Test-Kommando."""
		try:
			if not self.mqtt_client or not self.mqtt_client.is_connected():
				messagebox.showwarning("Keine MQTT-Verbindung", "MQTT-Verbindung erforderlich.")
				return

			test_cmd = {
				"command": "pi_test",
				"duration": 10,
				"damping_quality": "good",
				"timestamp": time.time(),
				"source": "egea_auto_discovery_gui"
			}

			success = self.mqtt_client.publish("suspension/commands", test_cmd)
			if success:
				self._log_message("📡 Test", "Test-Kommando gesendet", "success")
			else:
				self._log_message("❌ Test", "Test-Kommando fehlgeschlagen", "error")

		except Exception as e:
			logger.error(f"Fehler beim Test-Kommando: {e}")

	def _save_config(self):
		"""Speichert Konfiguration."""
		try:
			# Aktuelle Broker-Info zur Config hinzufügen
			if self.mqtt_client:
				self.config.add_fallback_broker(self.mqtt_client.broker)

			self._log_message("💾 Config", "Konfiguration gespeichert", "success")
			messagebox.showinfo("Konfiguration", "Konfiguration wurde gespeichert.")

		except Exception as e:
			logger.error(f"Fehler beim Speichern der Konfiguration: {e}")
			self._log_message("❌ Config", f"Speichern fehlgeschlagen: {e}", "error")

	def _clear_log(self):
		"""Leert Test-Log."""
		self.test_log.config(state=tk.NORMAL)
		self.test_log.delete(1.0, tk.END)
		self.test_log.config(state=tk.DISABLED)

	def _save_log(self):
		"""Speichert Test-Log."""
		try:
			from tkinter import filedialog
			filename = filedialog.asksaveasfilename(
				defaultextension=".txt",
				filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
			)

			if filename:
				with open(filename, 'w') as f:
					f.write(self.test_log.get(1.0, tk.END))

				self._log_message("💾 Log", f"Log gespeichert: {filename}", "success")

		except Exception as e:
			logger.error(f"Fehler beim Log-Speichern: {e}")

	def _update_loop(self):
		"""Haupt-Update-Loop."""
		try:
			# Charts aktualisieren
			self._update_charts()

			# EGEA-Status aktualisieren
			self._update_egea_status()

		except Exception as e:
			logger.debug(f"Update-Loop Fehler: {e}")

		# Nächstes Update planen
		self.root.after(UPDATE_RATE_MS, self._update_loop)

	def _log_message(self, category: str, message: str, level: str = "normal"):
		"""Fügt Nachricht zum Test-Log hinzu."""
		try:
			if not self.test_log:
				return

			timestamp = time.strftime("%H:%M:%S")
			formatted_message = f"[{timestamp}] {category}: {message}\n"

			self.test_log.config(state=tk.NORMAL)
			self.test_log.insert(tk.END, formatted_message, level)
			self.test_log.see(tk.END)
			self.test_log.config(state=tk.DISABLED)

			# Auch ins System-Log
			if level == "error":
				logger.error(f"[{category}] {message}")
			elif level == "warning":
				logger.warning(f"[{category}] {message}")
			elif level == "success":
				logger.info(f"[{category}] {message}")
			else:
				logger.debug(f"[{category}] {message}")

		except Exception as e:
			logger.error(f"Fehler beim Loggen: {e}")

	def on_closing(self):
		"""Wird beim Schließen der Anwendung aufgerufen."""
		try:
			if messagebox.askokcancel("Anwendung beenden",
			                          "EGEA-Fahrwerkstester wirklich beenden?\n"
			                          "Aktive Tests werden gestoppt."):

				# Test stoppen falls aktiv
				if self.data_buffer.test_active:
					self._stop_test()

				# MQTT-Verbindung trennen
				if self.mqtt_client:
					try:
						self.mqtt_client.disconnect()
						self._log_message("🔌 System", "MQTT-Verbindung getrennt", "info")
					except Exception as e:
						logger.error(f"Fehler beim MQTT-Trennen: {e}")

				# Config-Manager aufräumen
				if hasattr(self.config, 'stop_monitoring'):
					self.config.stop_monitoring()

				self._log_message("👋 System", "EGEA-Fahrwerkstester beendet", "info")
				self.root.destroy()

		except Exception as e:
			logger.error(f"Fehler beim Schließen: {e}")
			self.root.destroy()


def create_sample_config(path: str = "egea_config.yaml"):
	"""
	Erstellt eine Beispiel-Konfigurationsdatei für die Auto-Discovery GUI.

	Args:
		path: Pfad zur Konfigurationsdatei
	"""
	config = {
		"mqtt": {
			"broker": "auto",  # Automatische Erkennung
			"port": 1883,
			"auto_discovery": True,
			"discovery_timeout": 5.0,
			"fallback_brokers": [
				"192.168.0.249",  # Aktuelle Pi-IP
				"192.168.0.100",
				"192.168.1.100",
				"localhost"
			]
		},
		"network": {
			"discovery_timeout": 5.0,
			"cache_timeout": 300,
			"ping_timeout": 1.0
		},
		"egea": {
			"phase_shift_threshold": 35.0,
			"min_frequency": 6.0,
			"max_frequency": 25.0,
			"test_duration": 30.0
		},
		"logging": {
			"level": "INFO",
			"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
		}
	}

	try:
		import yaml
		with open(path, 'w') as f:
			yaml.dump(config, f, default_flow_style=False, indent=2)
		print(f"✅ Konfigurationsdatei erstellt: {path}")
		return True
	except Exception as e:
		print(f"❌ Fehler beim Erstellen der Konfigurationsdatei: {e}")
		return False


def main():
	"""Hauptfunktion zum Starten der vollständigen Auto-Discovery GUI."""
	parser = argparse.ArgumentParser(description="EGEA-Fahrwerkstester mit intelligenter Suspension-Discovery")
	parser.add_argument("--config", help="Pfad zur Konfigurationsdatei")
	parser.add_argument("--debug", action="store_true", help="Debug-Modus aktivieren")
	parser.add_argument("--create-config", action="store_true", help="Beispiel-Konfiguration erstellen")
	parser.add_argument("--test-discovery", action="store_true", help="Nur Discovery testen")
	args = parser.parse_args()

	# Logging konfigurieren
	log_level = logging.DEBUG if args.debug else logging.INFO
	logging.basicConfig(
		level=log_level,
		format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
		handlers=[
			logging.StreamHandler(),
			logging.FileHandler("egea_gui.log") if args.debug else logging.NullHandler()
		]
	)

	# Beispiel-Konfiguration erstellen
	if args.create_config:
		config_path = args.config or "egea_config.yaml"
		create_sample_config(config_path)
		print(f"Beispiel-Konfiguration erstellt: {config_path}")
		print("Starten Sie die GUI mit: python script.py --config egea_config.yaml")
		return

	# Nur Discovery testen
	if args.test_discovery:
		print("🔍 Teste intelligente Suspension-Discovery...")

		if SMART_DISCOVERY_AVAILABLE:
			from smart_suspension_discovery import SmartSuspensionDiscovery
			discovery = SmartSuspensionDiscovery(timeout=8.0)
			devices = discovery.discover_suspension_brokers()

			print(f"\n✅ Intelligente Discovery abgeschlossen: {len(devices)} Suspension-Broker gefunden")
			for i, broker in enumerate(devices, 1):
				print(f"  {i}. {broker.ip} ({broker.hostname})")
				print(f"     Konfidenz: {broker.confidence * 100:.0f}%")
				print(f"     Suspension-Topics: {len(broker.suspension_topics)}")
				print(f"     Response: {broker.response_time * 1000:.0f}ms")

			if devices:
				print(f"\n🎯 Bester Suspension-Broker: {devices[0].ip}")
				print(f"   Konfidenz: {devices[0].confidence * 100:.0f}%")
				if devices[0].suspension_topics:
					print("   Topics:")
					for topic in devices[0].suspension_topics:
						print(f"     • {topic}")
			else:
				print("\n⚠️ Keine Suspension-Broker gefunden")
		else:
			print("❌ Intelligente Discovery nicht verfügbar")
			print("Erstellen Sie zuerst die smart_suspension_discovery.py")
		return

	# Abhängigkeiten prüfen
	missing_deps = []
	if not MQTT_AVAILABLE:
		missing_deps.append("paho-mqtt")

	if missing_deps:
		print(f"❌ Fehlende Abhängigkeiten: {', '.join(missing_deps)}")
		print(f"Installieren mit: pip install {' '.join(missing_deps)}")
		return

	# Optionale Abhängigkeiten prüfen
	if not NETIFACES_AVAILABLE:
		print("⚠️ netifaces nicht verfügbar - eingeschränkte Netzwerk-Discovery")
		print("Installieren mit: pip install netifaces")

	if not ZEROCONF_AVAILABLE:
		print("⚠️ zeroconf nicht verfügbar - kein mDNS-Discovery")
		print("Installieren mit: pip install zeroconf")

	if not SUSPENSION_CORE_AVAILABLE:
		print("⚠️ suspension_core nicht verfügbar - vereinfachte EGEA-Analyse")

	# GUI erstellen und starten
	root = tk.Tk()

	try:
		app = CompleteAutoDiscoveryGUI(root, config_path=args.config)

		print("🚀 EGEA-Fahrwerkstester GUI mit intelligenter Discovery gestartet")
		print("💡 Features:")
		print("   - Intelligente Suspension-spezifische MQTT-Broker-Discovery")
		print("   - Topic-basierte Broker-Analyse (95% Konfidenz für goldenen Topic)")
		print("   - Live-Datenvisualisierung")
		print("   - EGEA-konforme Phasenverschiebungsanalyse")
		print("   - Interaktive Discovery-Dialoge mit Topic-Details")
		print("   - Robuste MQTT-Verbindung mit Fallback")
		print("\n🎯 Verwenden Sie 'Intelligente Suche' um Suspension-Broker zu finden")
		print("📊 Aktivieren Sie 'Alle Datenfelder anzeigen' für dynamische Charts")

		root.mainloop()

	except KeyboardInterrupt:
		print("\n👋 Anwendung durch Benutzer beendet")
	except Exception as e:
		print(f"❌ Unerwarteter Fehler: {e}")
		logger.error(f"GUI-Fehler: {e}", exc_info=True)
	finally:
		try:
			if 'app' in locals():
				app.on_closing()
		except:
			pass


if __name__ == "__main__":
	main()