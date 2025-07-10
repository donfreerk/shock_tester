#!/usr/bin/env python3
"""
SimulatorApp Simulator GUI für den Fahrwerkstester.

Diese Anwendung kombiniert die Funktionalitäten des CAN-Simulators und der MQTT-Bridge
in einer einzigen Benutzeroberfläche. Sie ermöglicht die Simulation von CAN-Nachrichten,
deren Konvertierung in MQTT-Nachrichten und die Visualisierung beider Datenströme.

Die Anwendung unterstützt verschiedene vorgefertigte Testmodi:

1. Default: Verwendet die aktuell ausgewählte Dämpfungsqualität

2. Gute Dämpfung (good_damping):
   - Phasenverschiebung (φmin): 40-50°
   - Deutlich über dem EGEA-Schwellwert von 35°
   - Moderate Kraftamplitude (realistische Übertragung)
   - Reifensteifigkeit im optimalen Bereich (280 N/mm)

3. Grenzwertige Dämpfung (marginal_damping):
   - Phasenverschiebung (φmin): 35-38°
   - Knapp über dem EGEA-Schwellwert
   - Höhere Kraftamplitude (schwächere Dämpfung)
   - Niedrige, aber noch akzeptable Reifensteifigkeit (165 N/mm)

4. Schlechte Dämpfung (bad_damping):
   - Phasenverschiebung (φmin): 20-30°
   - Deutlich unter dem EGEA-Schwellwert
   - Sehr hohe Kraftamplitude (typisch für verschlissene Dämpfer)
   - Zu niedrige Reifensteifigkeit (140 N/mm)
"""

import argparse
import json
import logging

# Add the project root directory to the Python path
import os
import queue
import sys
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tkinter import Checkbutton, messagebox, scrolledtext, ttk

import self
from aiomqtt import message

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from common.suspension_core.config import settings

# Import ConfigManager from common library
from common.suspension_core.config.manager import ConfigManager

# Konfiguriere Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SimulatorApp_simulator_gui")

# Globale Queue für Thread-sichere Kommunikation
message_queue = queue.Queue()
# Neue Queue für MQTT-Nachrichten
mqtt_message_queue = queue.Queue()


class SimulatorApp:
    """Hauptklasse für die SimulatorApp Simulator GUI-Anwendung."""

    def __init__(self, root):
        """Initialisiert die GUI-Anwendung.

        Args:
                        root: tkinter Root-Widget
        """
        self.main_frame = None
        self.root = root
        self.root.title("SimulatorApp Simulator für Fahrwerkstester")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Statusvariablen
        self.simulator_running = False
        self.bridge_running = False
        self.left_motor_running = False
        self.right_motor_running = False
        self.protocol = tk.StringVar(value="eusama")
        self.damping_quality = tk.StringVar(value="good")
        self.test_method = tk.StringVar(value="phase_shift")
        self.test_mode = tk.StringVar(value="default")  # Neuer Modus für vorgefertigte Tests
        self.low_level_enabled = tk.BooleanVar(value=True)
        self.message_filter = tk.StringVar(value="")
        self.auto_scroll = tk.BooleanVar(value=True)
        self.show_timestamps = tk.BooleanVar(value=True)
        self.vehicle_present = tk.BooleanVar(value=False)

        # Simulationsvariablen
        self.current_frequency = 25.0  # Standardfrequenz für Messungen

        # MQTT-Konfiguration aus ConfigManager
        config = ConfigManager()
        self.mqtt_broker = tk.StringVar(value=config.get(["mqtt", "broker"], "localhost"))
        self.mqtt_port = tk.IntVar(value=config.get(["mqtt", "port"], 1883))
        self.mqtt_connected = False
        self.mqtt_client = None

        # Simulator-Instanz (wird später initialisiert)
        self.simulator = None
        self.can_converter = None

        # UI-Komponenten
        self.can_log = None
        self.mqtt_log = None
        self.status_label = None
        self.simulator_button = None
        self.bridge_button = None
        self.left_motor_button = None
        self.right_motor_button = None
        self.mqtt_button = None
        self.protocol_dropdown = None
        self.damping_dropdown = None
        self.test_method_dropdown = None
        self.test_mode_dropdown = None  # Neues Dropdown für Testmodi
        self.filter_entry = None
        self.auto_scroll_check = None
        self.show_timestamps_check = None
        self.vehicle_present_check = None
        self.low_level_check = None

        # Volltestmodus-Variablen
        self.full_test_frame = None
        self.full_test_running = False
        self.left_test_result = None
        self.right_test_result = None
        self.full_test_status_label = None
        self.full_test_progress = None
        self.full_test_button = None

        # UI erstellen
        self.create_ui()

        # Simulator initialisieren
        self.init_simulator()

        # MQTT-Client initialisieren
        self.init_mqtt_client()

        # CAN-Konverter initialisieren
        self.init_can_converter()

        # Prozess-Queue-Timer starten
        self.root.after(100, self.process_queue)
        # Automatische Initialisierung nach kurzer Verzögerung
        self.root.after(1000, lambda: initialize_app(self))
        # Protokoll beim Schließen des Fensters
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.adaptive_update = True
        self.current_load = 0.0
        self.base_update_interval = 250  # 4 Hz base rate

        # Python 3.13.3 Optimierungen
        if sys.version_info >= (3, 13):
            # Thread-Pool für schwere Operations
            self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="SimApp")

            # Optimierte Queue-Größen
            self.message_queue = queue.Queue(maxsize=500)  # Begrenzt für Memory
            self.mqtt_message_queue = queue.Queue(maxsize=500)

        # Reduzierte Update-Rate für bessere Performance
        self.update_interval_ms = 250  # 4 Hz statt 10 Hz

        def _process_heavy_operation_async(self, operation, *args):
            """Führt schwere Operations in separatem Thread aus."""
            if hasattr(self, "thread_pool"):
                future = self.thread_pool.submit(operation, *args)
                return future
            # Fallback für ältere Python-Versionen
            return operation(*args)

        def cleanup(self):
            """Cleanup mit Python 3.13.3 Optimierungen."""
            try:
                # ... existing cleanup code ...

                # Thread-Pool cleanup
                if hasattr(self, "thread_pool"):
                    self.thread_pool.shutdown(wait=True, cancel_futures=True)

            except Exception as e:
                self.logger.error(f"Cleanup-Fehler: {e}")

    def _adaptive_update_scheduler(self):
        """Passt Update-Rate basierend auf System-Load an."""
        if not self.adaptive_update:
            return self.base_update_interval
        # Einfache Load-Messung basierend auf Queue-Größe
        can_queue_load = self.message_queue.qsize() / self.message_queue.maxsize
        mqtt_queue_load = self.mqtt_message_queue.qsize() / self.mqtt_message_queue.maxsize
        avg_load = (can_queue_load + mqtt_queue_load) / 2
        # Update-Intervall anpassen (zwischen 100ms und 1000ms)
        if avg_load > 0.8:
            interval = 1000  # 1 Hz bei hoher Last
        elif avg_load > 0.5:
            interval = 500  # 2 Hz bei mittlerer Last
        else:
            interval = self.base_update_interval  # 4 Hz bei niedriger Last
        return interval

    def create_full_test_ui(self):
        """Erstellt die UI-Komponenten für den Volltest-Modus."""
        # Frame für den Volltest-Modus
        self.full_test_frame = ttk.LabelFrame(
            self.main_frame, text="Volltest-Modus", padding=(10, 5)
        )
        self.full_test_frame.pack(fill=tk.X, padx=10, pady=5)

        # Obere Zeile: Status und Fortschritt
        status_frame = ttk.Frame(self.full_test_frame)
        status_frame.pack(fill=tk.X, pady=5)

        # Status-Label
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0, 5))
        self.full_test_status_label = ttk.Label(
            status_frame, text="Bereit", font=("TkDefaultFont", 10, "bold")
        )
        self.full_test_status_label.pack(side=tk.LEFT, padx=(0, 10))

        # Fortschrittsbalken
        self.full_test_progress = ttk.Progressbar(
            status_frame, orient=tk.HORIZONTAL, length=300, mode="determinate"
        )
        self.full_test_progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Untere Zeile: Start-Button und Ergebnisse
        control_frame = ttk.Frame(self.full_test_frame)
        control_frame.pack(fill=tk.X, pady=5)

        # Start-Button
        self.full_test_button = ttk.Button(
            control_frame,
            text="Volltest starten",
            command=self.start_full_test,
            style="Accent.TButton",
        )
        self.full_test_button.pack(side=tk.LEFT, padx=(0, 10))

        # Ergebnis-Labels
        result_frame = ttk.Frame(control_frame)
        result_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(result_frame, text="Links:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.left_test_result = ttk.Label(result_frame, text="Nicht getestet")
        self.left_test_result.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        ttk.Label(result_frame, text="Rechts:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.right_test_result = ttk.Label(result_frame, text="Nicht getestet")
        self.right_test_result.grid(row=0, column=3, sticky=tk.W)

    def start_full_test(self):
        """Startet den Volltest-Modus."""
        if self.full_test_running:
            messagebox.showinfo("Test läuft", "Ein Volltest läuft bereits.")
            return

        # Prüfen, ob ein Fahrzeug vorhanden ist
        if not self.vehicle_present.get():
            messagebox.showerror(
                "Fehler",
                "Kein Fahrzeug vorhanden. Bitte stellen Sie sicher, dass ein Fahrzeug auf der Plattform steht.",
            )
            return

        # Prüfen, ob die Bridge gestartet ist
        if not self.bridge_running:
            messagebox.showerror(
                "Fehler", "Bridge nicht gestartet. Bitte starten Sie zuerst die Bridge."
            )
            return

        # Bestätigung vom Benutzer einholen
        if not messagebox.askyesno(
            "Volltest starten",
            "Möchten Sie einen vollständigen Test beider Seiten durchführen?\n\n"
            "Dies wird automatisch folgende Schritte ausführen:\n"
            "1. Linke Seite testen\n"
            "2. Rechte Seite testen\n"
            "3. Ergebnisse auswerten\n\n"
            "Stellen Sie sicher, dass das Fahrzeug korrekt positioniert ist.",
        ):
            return

        # Test-Status zurücksetzen
        self.full_test_running = True
        self.left_test_result.config(text="Wird getestet...")
        self.right_test_result.config(text="Warten...")
        self.full_test_status_label.config(text="Test läuft - Linke Seite")
        self.full_test_progress["value"] = 0
        self.full_test_button.config(state=tk.DISABLED)

        # Linke Seite zuerst testen
        self.root.after(1000, self._start_test_sequence_left)

    def _start_test_sequence_left(self):
        """Startet die Testsequenz für die linke Seite."""
        # Fortschritt aktualisieren
        self.full_test_progress["value"] = 10
        self.full_test_status_label.config(text="Test läuft - Linke Seite")

        # Kommando zum Starten des Tests senden
        command = {
            "action": "start_test",
            "position": "left",
            "test_method": self.test_method.get(),
            "damping_quality": self.damping_quality.get(),
        }
        mqtt_message_queue.put(("command", command))

    def _start_test_sequence_right(self):
        """Startet die Testsequenz für die rechte Seite."""
        # Fortschritt aktualisieren
        self.full_test_progress["value"] = 50
        self.full_test_status_label.config(text="Test läuft - Rechte Seite")
        self.left_test_result.config(text="Abgeschlossen")
        self.right_test_result.config(text="Wird getestet...")

        # Kommando zum Starten des Tests senden
        command = {
            "action": "start_test",
            "position": "right",
            "test_method": self.test_method.get(),
            "damping_quality": self.damping_quality.get(),
        }
        mqtt_message_queue.put(("command", command))

    def _start_test(self, side, duration):
        """Startet einen Test für die angegebene Seite.

        Args:
                side: Seite des Tests ("left", "right", "all")
                duration: Dauer des Tests in Sekunden
        """
        try:
            # Prüfen, ob ein Fahrzeug vorhanden ist
            if not self.vehicle_present.get():
                self.log("Test kann nicht gestartet werden: Kein Fahrzeug vorhanden", "ERROR")
                return

            # Prüfen, ob die Bridge gestartet ist
            if not self.bridge_running:
                self.log("Test kann nicht gestartet werden: Bridge nicht gestartet", "ERROR")
                return

            # Motor starten
            if side == "left" and not self.left_motor_running:
                self.toggle_left_motor()
            elif side == "right" and not self.right_motor_running:
                self.toggle_right_motor()
            elif side == "all":
                if not self.left_motor_running:
                    self.toggle_left_motor()
                if not self.right_motor_running:
                    self.toggle_right_motor()

            # Simulator-Test starten
            if self.simulator and hasattr(self.simulator, "start_test"):
                self.simulator.start_test(side, duration)
                self.log(f"Test gestartet für Seite: {side}, Dauer: {duration}s", "INFO")
            else:
                self.log("Simulator nicht verfügbar für Teststart", "ERROR")

        except Exception as e:
            self.log(f"Fehler beim Starten des Tests: {e}", "ERROR")

    def _stop_test(self):
        """Stoppt den laufenden Test."""
        try:
            # Simulator-Test stoppen
            if self.simulator and hasattr(self.simulator, "stop_test"):
                self.simulator.stop_test()
                self.log("Test gestoppt", "INFO")
            else:
                self.log("Simulator nicht verfügbar für Teststopp", "ERROR")

        except Exception as e:
            self.log(f"Fehler beim Stoppen des Tests: {e}", "ERROR")

    def _emergency_stop(self):
        """Führt einen Notfall-Stopp durch."""
        try:
            # Alle Motoren stoppen
            if self.left_motor_running:
                self.toggle_left_motor()
            if self.right_motor_running:
                self.toggle_right_motor()

            # Test stoppen
            self._stop_test()

            self.log("NOT-STOP durchgeführt", "WARNING")

        except Exception as e:
            self.log(f"Fehler beim NOT-STOP: {e}", "ERROR")

    def create_ui(self):
        """Erstellt die Benutzeroberfläche der Anwendung."""
        # Hauptframe
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Oberer Bereich: Steuerung
        control_frame = ttk.LabelFrame(self.main_frame, text="Steuerung", padding=(10, 5))
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Erste Zeile: Simulator, Bridge, MQTT
        row1 = ttk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=5)

        # Simulator-Button
        self.simulator_button = ttk.Button(
            row1, text="Simulator starten", command=self.toggle_simulator
        )
        self.simulator_button.pack(side=tk.LEFT, padx=(0, 5))

        # Bridge-Button
        self.bridge_button = ttk.Button(row1, text="Bridge starten", command=self.toggle_bridge)
        self.bridge_button.pack(side=tk.LEFT, padx=5)

        # MQTT-Button
        self.mqtt_button = ttk.Button(
            row1, text="MQTT verbinden", command=self.toggle_mqtt_connection
        )
        self.mqtt_button.pack(side=tk.LEFT, padx=5)

        # MQTT-Broker-Einstellungen
        mqtt_frame = ttk.Frame(row1)
        mqtt_frame.pack(side=tk.LEFT, padx=10)

        ttk.Label(mqtt_frame, text="Broker:").pack(side=tk.LEFT)
        ttk.Entry(mqtt_frame, textvariable=self.mqtt_broker, width=15).pack(
            side=tk.LEFT, padx=(5, 10)
        )

        ttk.Label(mqtt_frame, text="Port:").pack(side=tk.LEFT)
        ttk.Entry(mqtt_frame, textvariable=self.mqtt_port, width=5).pack(side=tk.LEFT, padx=5)

        # Zweite Zeile: Motor-Steuerung
        row2 = ttk.Frame(control_frame)
        row2.pack(fill=tk.X, pady=5)

        # Linker Motor-Button
        self.left_motor_button = ttk.Button(
            row2, text="Linker Motor starten", command=self.toggle_left_motor
        )
        self.left_motor_button.pack(side=tk.LEFT, padx=(0, 5))

        # Rechter Motor-Button
        self.right_motor_button = ttk.Button(
            row2, text="Rechter Motor starten", command=self.toggle_right_motor
        )
        self.right_motor_button.pack(side=tk.LEFT, padx=5)

        # Protokoll-Dropdown
        ttk.Label(row2, text="Protokoll:").pack(side=tk.LEFT, padx=(20, 5))
        self.protocol_dropdown = ttk.Combobox(
            row2,
            textvariable=self.protocol,
            values=["eusama", "asa"],
            width=10,
            state="readonly",
        )
        self.protocol_dropdown.pack(side=tk.LEFT, padx=5)
        self.protocol_dropdown.bind("<<ComboboxSelected>>", self.on_protocol_change)

        # Dämpfungsqualität-Dropdown
        ttk.Label(row2, text="Dämpfung:").pack(side=tk.LEFT, padx=(20, 5))
        self.damping_dropdown = ttk.Combobox(
            row2,
            textvariable=self.damping_quality,
            values=["good", "marginal", "bad"],
            width=10,
            state="readonly",
        )
        self.damping_dropdown.pack(side=tk.LEFT, padx=5)
        self.damping_dropdown.bind("<<ComboboxSelected>>", self.on_damping_change)

        # Testmethode-Dropdown
        ttk.Label(row2, text="Testmethode:").pack(side=tk.LEFT, padx=(20, 5))
        self.test_method_dropdown = ttk.Combobox(
            row2,
            textvariable=self.test_method,
            values=["phase_shift", "resonance"],
            width=12,
            state="readonly",
        )
        self.test_method_dropdown.pack(side=tk.LEFT, padx=5)
        self.test_method_dropdown.bind("<<ComboboxSelected>>", self.on_test_method_change)

        # Dritte Zeile: Testmodus und Optionen
        row3 = ttk.Frame(control_frame)
        row3.pack(fill=tk.X, pady=5)

        # Testmodus-Dropdown
        ttk.Label(row3, text="Testmodus:").pack(side=tk.LEFT, padx=(0, 5))
        self.test_mode_dropdown = ttk.Combobox(
            row3,
            textvariable=self.test_mode,
            values=["default", "good_damping", "marginal_damping", "bad_damping"],
            width=15,
            state="readonly",
        )
        self.test_mode_dropdown.pack(side=tk.LEFT, padx=5)
        self.test_mode_dropdown.bind("<<ComboboxSelected>>", self.on_test_mode_change)

        # Low-Level-Checkbox
        self.low_level_check = ttk.Checkbutton(
            row3,
            text="Low-Level CAN",
            variable=self.low_level_enabled,
            command=self.toggle_low_level,
        )
        self.low_level_check.pack(side=tk.LEFT, padx=(20, 5))

        # Fahrzeug-Checkbox
        self.vehicle_present_check = ttk.Checkbutton(
            row3,
            text="Fahrzeug vorhanden",
            variable=self.vehicle_present,
            command=self.toggle_vehicle,
        )
        self.vehicle_present_check.pack(side=tk.LEFT, padx=(20, 5))

        # Auto-Scroll-Checkbox
        self.auto_scroll_check = ttk.Checkbutton(
            row3, text="Auto-Scroll", variable=self.auto_scroll
        )
        self.auto_scroll_check.pack(side=tk.LEFT, padx=(20, 5))

        # Zeitstempel-Checkbox
        self.show_timestamps_check = ttk.Checkbutton(
            row3, text="Zeitstempel", variable=self.show_timestamps
        )
        self.show_timestamps_check.pack(side=tk.LEFT, padx=(20, 5))

        # Volltest-UI erstellen
        self.create_full_test_ui()

        # Mittlerer Bereich: Logs
        log_frame = ttk.Frame(self.main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # CAN-Log
        can_frame = ttk.LabelFrame(log_frame, text="CAN-Nachrichten", padding=(5, 5))
        can_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Filter für CAN-Nachrichten
        filter_frame = ttk.Frame(can_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.message_filter)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(filter_frame, text="Anwenden", command=self.apply_filter).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(filter_frame, text="Zurücksetzen", command=self.reset_filter).pack(side=tk.LEFT)

        # CAN-Log-Textfeld
        self.can_log = scrolledtext.ScrolledText(can_frame, wrap=tk.WORD)
        self.can_log.pack(fill=tk.BOTH, expand=True)
        self.can_log.tag_configure("timestamp", foreground="gray")
        self.can_log.tag_configure("id", foreground="blue")
        self.can_log.tag_configure("data", foreground="green")
        self.can_log.tag_configure("error", foreground="red")

        # MQTT-Log
        mqtt_frame = ttk.LabelFrame(log_frame, text="MQTT-Nachrichten", padding=(5, 5))
        mqtt_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # MQTT-Log-Textfeld
        self.mqtt_log = scrolledtext.ScrolledText(mqtt_frame, wrap=tk.WORD)
        self.mqtt_log.pack(fill=tk.BOTH, expand=True)
        self.mqtt_log.tag_configure("timestamp", foreground="gray")
        self.mqtt_log.tag_configure("topic", foreground="blue")
        self.mqtt_log.tag_configure("payload", foreground="green")
        self.mqtt_log.tag_configure("error", foreground="red")

        # Unterer Bereich: Statusleiste
        status_frame = ttk.Frame(self.main_frame, relief=tk.SUNKEN, padding=(5, 2))
        status_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        self.status_label = ttk.Label(status_frame, text="Bereit")
        self.status_label.pack(side=tk.LEFT)

    def init_simulator(self):
        """Initialisiert den CAN-Simulator."""
        try:
            # Import hier, um zirkuläre Abhängigkeiten zu vermeiden
            from common.suspension_core.can.interface_factory import create_can_interface

            # Simulator mit Hybrid-Modus erstellen (Low-Level und High-Level)
            self.simulator = create_can_interface(
                simulation_type="hybrid", simulation_profile=self.protocol.get()
            )

            # KRITISCH: Simulator verbinden BEVOR Callbacks registriert werden
            if hasattr(self.simulator, "connect"):
                if not self.simulator.connect():
                    self.log("Simulator-Verbindung fehlgeschlagen", "ERROR")
                    return False
            else:
                self.log("Simulator hat keine connect() Methode", "ERROR")
                return False

            #  add_message_callback statt add_message_listener
            if hasattr(self.simulator, "add_message_callback"):
                self.simulator.add_message_callback(self.can_message_handler)
                self.log("CAN-Message-Callback erfolgreich registriert", "INFO")
            else:
                self.log("Simulator unterstützt keine Message-Callbacks", "WARNING")

            #  Fahrzeug standardmäßig als vorhanden setzen für Datengenerierung
            if hasattr(self.simulator, "set_vehicle_present"):
                self.simulator.set_vehicle_present(True)  # GEÄNDERT: True statt False
                self.vehicle_present.set(True)  # GUI synchronisieren
                self.log("Fahrzeug für Datengenerierung aktiviert", "INFO")

            #  Automatisch einen Test starten für kontinuierliche Daten
            # if hasattr(self.simulator, "start_test"):
            # # Starte einen kontinuierlichen Test für Datengenerierung
            # self.simulator.start_test("left", 30)  # 30 Sekunden Laufzeit
            # self.log("Kontinuierlicher Test für Datengenerierung gestartet", "INFO")

            self.log("Simulator erfolgreich initialisiert", "INFO")
            return True

        except Exception as e:
            self.log(f"Fehler beim Initialisieren des Simulators: {e}", "ERROR")
            return False

    def init_mqtt_client(self):
        """Initialisiert den MQTT-Client."""
        try:
            # Import hier, um zirkuläre Abhängigkeiten zu vermeiden
            from common.suspension_core.mqtt.handler import MqttHandler

            # Funktion zum Hinzufügen von Nachrichten zur Queue
            def queue_mqtt_message(category, message):
                mqtt_message_queue.put((category, message))

            # MQTT-Client erstellen
            client_id = f"simulator_gui_{int(time.time())}"
            self.mqtt_client = MqttHandler(
                client_id=client_id,
                host=self.mqtt_broker.get(),
                port=self.mqtt_port.get(),
                on_message=self.mqtt_message_handler,
            )

            self.log("MQTT-Client initialisiert", "INFO")
        except Exception as e:
            self.log(f"Fehler beim Initialisieren des MQTT-Clients: {e}", "ERROR")

    def init_can_converter(self):
        """Initialisiert den CAN-zu-MQTT-Konverter."""
        try:
            # Import hier, um zirkuläre Abhängigkeiten zu vermeiden
            from common.suspension_core.can.converters.json_converter import (
                CanMessageConverter,
            )

            # Konverter erstellen
            self.can_converter = CanMessageConverter()

            self.log("CAN-Konverter initialisiert", "INFO")
        except Exception as e:
            self.log(f"Fehler beim Initialisieren des CAN-Konverters: {e}", "ERROR")

    def toggle_mqtt_connection(self):
        """Stellt eine Verbindung zum MQTT-Broker her oder trennt sie."""
        if not self.mqtt_connected:
            try:
                # MQTT-Client neu initialisieren mit aktuellen Einstellungen
                from common.suspension_core.mqtt.handler import MqttHandler

                client_id = f"simulator_gui_{int(time.time())}"
                self.mqtt_client = MqttHandler(
                    client_id=client_id,
                    host=self.mqtt_broker.get(),
                    port=self.mqtt_port.get(),
                    on_message=self.mqtt_message_handler,
                )

                # Verbindung herstellen
                self.mqtt_client.connect()
                self.mqtt_connected = True
                self.mqtt_button.config(text="MQTT trennen")
                self.log(
                    f"MQTT-Verbindung hergestellt zu {self.mqtt_broker.get()}:{self.mqtt_port.get()}",
                    "INFO",
                )

                # Topics abonnieren
                self.subscribe_to_mqtt_topics()

            except Exception as e:
                self.log(f"Fehler beim Verbinden mit MQTT-Broker: {e}", "ERROR")
        else:
            try:
                # Verbindung trennen
                if self.mqtt_client:
                    self.mqtt_client.disconnect()
                self.mqtt_connected = False
                self.mqtt_button.config(text="MQTT verbinden")
                self.log("MQTT-Verbindung getrennt", "INFO")
            except Exception as e:
                self.log(f"Fehler beim Trennen der MQTT-Verbindung: {e}", "ERROR")

    def subscribe_to_mqtt_topics(self):
        """Abonniert die relevanten MQTT-Topics."""
        if not self.mqtt_connected or not self.mqtt_client:
            return

        try:
            # Kommando-Topics abonnieren
            self.mqtt_client.subscribe("suspension/command/#")
            self.log("MQTT-Topic 'suspension/command/#' abonniert", "INFO")

            # Status-Topics abonnieren
            self.mqtt_client.subscribe("suspension/status/#")
            self.log("MQTT-Topic 'suspension/status/#' abonniert", "INFO")

            # Messdaten-Topics abonnieren
            self.mqtt_client.subscribe("suspension/measurement/#")
            self.log("MQTT-Topic 'suspension/measurement/#' abonniert", "INFO")

            # Testergebnis-Topics abonnieren
            self.mqtt_client.subscribe("suspension/test_result/#")
            self.log("MQTT-Topic 'suspension/test_result/#' abonniert", "INFO")

            # Spezielle Topics für den Simulator
            self.mqtt_client.subscribe("suspension/simulator/#")
            self.log("MQTT-Topic 'suspension/simulator/#' abonniert", "INFO")

            # GUI-Kommando-Topic abonnieren
            self.mqtt_client.subscribe("suspension/gui/command")
            self.log("MQTT-Topic 'suspension/gui/command' abonniert", "INFO")

        except Exception as e:
            self.log(f"Fehler beim Abonnieren der MQTT-Topics: {e}", "ERROR")

    def mqtt_message_handler(self, topic, message):
        """Callback für eingehende MQTT-Nachrichten.

        Args:
                topic: MQTT-Topic
                message: Nachrichteninhalt
        """
        try:
            # Nachricht ins Log schreiben
            timestamp = (
                f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "
                if self.show_timestamps.get()
                else ""
            )

            # Nachricht formatieren
            formatted_message = f"{timestamp}Topic: {topic}\nPayload: {message}\n\n"

            # Nachricht zur Queue hinzufügen
            message_queue.put(("mqtt_log", formatted_message))

            # Spezielle Behandlung für bestimmte Topics - KORRIGIERT mit suspension/ Präfix
            if topic.startswith("suspension/command/") or topic == "suspension/command":
                # Kommando verarbeiten
                try:
                    if isinstance(message, dict):
                        command_data = message
                    else:
                        command_data = json.loads(message)
                    self.handle_gui_command(command_data)
                except json.JSONDecodeError:
                    self.log(f"Ungültiges JSON-Format in Kommando: {message}", "ERROR")
            elif topic == "suspension/gui/command":
                # GUI-Kommando verarbeiten
                try:
                    if isinstance(message, dict):
                        command_data = message
                    else:
                        command_data = json.loads(message)
                    self.handle_gui_command(command_data)
                except json.JSONDecodeError:
                    self.log(f"Ungültiges JSON-Format in GUI-Kommando: {message}", "ERROR")
            elif topic.startswith("suspension/simulator/"):
                # Simulator-Kommando verarbeiten
                try:
                    if isinstance(message, dict):
                        command_data = message
                    else:
                        command_data = json.loads(message)
                    self.handle_simulator_command(command_data)
                except json.JSONDecodeError:
                    self.log(f"Ungültiges JSON-Format in Simulator-Kommando: {message}", "ERROR")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung der MQTT-Nachricht: {e}", "ERROR")

    def can_message_handler(self, msg):
        """Callback für eingehende CAN-Nachrichten."""
        try:
            # Debug-Log für ersten Nachweis, dass Nachrichten ankommen
            if not hasattr(self, "_first_can_message_logged"):
                self.log("Erste CAN-Nachricht empfangen! Handler funktioniert.", "INFO")
                self._first_can_message_logged = True

            # Nachricht ins Log schreiben, wenn sie den Filter passiert
            filter_text = self.message_filter.get().lower()

            # Nachricht formatieren
            if hasattr(msg, "arbitration_id") and hasattr(msg, "data"):
                # Standard CAN-Nachricht
                msg_str = f"ID: {hex(msg.arbitration_id)} Data: {' '.join([f'{b:02X}' for b in msg.data])}"
            elif hasattr(msg, "interpreted_data"):
                # High-Level interpretierte Daten
                msg_str = f"High-Level: {msg.interpreted_data}"
            else:
                # Fallback für andere Nachrichtenformate
                msg_str = str(msg)

            # Filter anwenden
            if not filter_text or filter_text in msg_str.lower():
                timestamp = (
                    f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "
                    if self.show_timestamps.get()
                    else ""
                )

                formatted_message = f"{timestamp}{msg_str}\n"

                # Nachricht zur Queue hinzufügen
                message_queue.put(("can_log", formatted_message))

            # Wenn Bridge aktiv ist, Nachricht konvertieren und über MQTT senden
            if self.bridge_running and self.mqtt_connected and self.mqtt_client:
                try:
                    # Für High-Level-Daten (interpretierte Daten)
                    if hasattr(msg, "interpreted_data"):
                        data = msg.interpreted_data

                        # Prüfe auf test_data Event - wichtig für suspension_tester_gui
                        if data.get("event") == "test_data" and data.get("type") == "phase_shift":
                            # Sende in dem Format, das suspension_tester_gui erwartet
                            measurement_data = {
                                "platform_position": data.get("platform_position", 0),
                                "tire_force": data.get("tire_force", 0),
                                "frequency": data.get("frequency", 0),
                                "phase_shift": data.get("phase_shift", 0),
                                "position": data.get("position", "unknown"),
                                "timestamp": data.get("timestamp", time.time()),
                                "static_weight": data.get("static_weight", None),
                            }

                            # An mehrere Topics senden für maximale Kompatibilität
                            topics = [
                                "suspension/measurements/processed",
                                "suspension/can/interpreted",
                                "suspension/test/data",
                            ]

                            for topic in topics:
                                self.mqtt_client.publish(topic, measurement_data)
                        else:
                            # Andere Daten normal senden
                            topic = "suspension/can/interpreted"
                            self.mqtt_client.publish(topic, data)

                    # Für Low-Level CAN-Frames
                    elif hasattr(msg, "arbitration_id") and hasattr(msg, "data"):
                        mqtt_data = {
                            "can_id": hex(msg.arbitration_id),
                            "data": list(msg.data),
                            "timestamp": getattr(msg, "timestamp", time.time()),
                            "source": "simulator",
                        }
                        topic = "suspension/can/raw"
                        payload = json.dumps(mqtt_data)
                        self.mqtt_client.publish(topic, payload)

                        # Debug für erste MQTT-Nachricht
                        if not hasattr(self, "_first_mqtt_sent_logged"):
                            self.log("Erste CAN→MQTT Konvertierung erfolgreich!", "INFO")
                            self._first_mqtt_sent_logged = True

                except Exception as e:
                    self.log(f"Fehler bei der CAN→MQTT-Konvertierung: {e}", "ERROR")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung der CAN-Nachricht: {e}", "ERROR")

    def toggle_bridge(self):
        """Startet oder stoppt die CAN-zu-MQTT-Bridge."""
        if not self.bridge_running:
            try:
                # Bridge starten
                self.bridge_running = True
                self.bridge_button.config(text="Bridge stoppen")
                self.log("CAN-zu-MQTT-Bridge gestartet", "INFO")

                # Status-Nachricht über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "bridge_started",
                        "timestamp": time.time(),
                    }
                    self.mqtt_client.publish("status/bridge", status_message)

            except Exception as e:
                self.log(f"Fehler beim Starten der Bridge: {e}", "ERROR")
        else:
            try:
                # Bridge stoppen
                self.bridge_running = False
                self.bridge_button.config(text="Bridge starten")
                self.log("CAN-zu-MQTT-Bridge gestoppt", "INFO")

                # Status-Nachricht über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "bridge_stopped",
                        "timestamp": time.time(),
                    }
                    self.mqtt_client.publish("status/bridge", status_message)

            except Exception as e:
                self.log(f"Fehler beim Stoppen der Bridge: {e}", "ERROR")

    def toggle_left_motor(self):
        """Startet oder stoppt den linken Motor."""
        if not self.left_motor_running:
            try:
                # Prüfen, ob ein Fahrzeug vorhanden ist
                if not self.vehicle_present.get():
                    self.log("Motor kann nicht gestartet werden: Kein Fahrzeug vorhanden", "ERROR")
                    return

                # Prüfen, ob die Bridge gestartet ist
                if not self.bridge_running:
                    self.log("Motor kann nicht gestartet werden: Bridge nicht gestartet", "ERROR")
                    return

                # Motor starten
                self.left_motor_running = True
                self.left_motor_button.config(text="Linker Motor stoppen")
                self.log("Linker Motor gestartet", "INFO")

                # Kommando über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    command = {
                        "action": "start_motor",
                        "position": "left",
                        "duration": 10,  # 10 Sekunden Testdauer
                        "test_method": self.test_method.get(),
                    }
                    self.mqtt_client.publish("command/motor", command)

                # Simulator-Einstellungen anpassen
                if self.simulator and hasattr(self.simulator, "start_test"):
                    self.simulator.start_test("left", 10)  # 10 Sekunden Testdauer

                # Timer für automatisches Stoppen nach 10 Sekunden
                self.root.after(10000, self._auto_stop_left_motor)

            except Exception as e:
                self.log(f"Fehler beim Starten des linken Motors: {e}", "ERROR")
        else:
            try:
                # Motor stoppen
                self.left_motor_running = False
                self.left_motor_button.config(text="Linker Motor starten")
                self.log("Linker Motor gestoppt", "INFO")

                # Kommando über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    command = {
                        "action": "stop_motor",
                        "position": "left",
                    }
                    self.mqtt_client.publish("command/motor", command)

                # Simulator-Einstellungen anpassen
                if self.simulator and hasattr(self.simulator, "stop_test"):
                    self.simulator.stop_test()

            except Exception as e:
                self.log(f"Fehler beim Stoppen des linken Motors: {e}", "ERROR")

    def _auto_stop_left_motor(self):
        """Stoppt den linken Motor automatisch nach Ablauf der Zeit."""
        if self.left_motor_running:
            self.toggle_left_motor()
            self.log("Linker Motor automatisch gestoppt (Zeitlimit erreicht)", "INFO")

    def toggle_right_motor(self):
        """Startet oder stoppt den rechten Motor."""
        if not self.right_motor_running:
            try:
                # Prüfen, ob ein Fahrzeug vorhanden ist
                if not self.vehicle_present.get():
                    self.log("Motor kann nicht gestartet werden: Kein Fahrzeug vorhanden", "ERROR")
                    return

                # Prüfen, ob die Bridge gestartet ist
                if not self.bridge_running:
                    self.log("Motor kann nicht gestartet werden: Bridge nicht gestartet", "ERROR")
                    return

                # Motor starten
                self.right_motor_running = True
                self.right_motor_button.config(text="Rechter Motor stoppen")
                self.log("Rechter Motor gestartet", "INFO")

                # Kommando über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    command = {
                        "action": "start_motor",
                        "position": "right",
                        "duration": 10,  # 10 Sekunden Testdauer
                        "test_method": self.test_method.get(),
                    }
                    self.mqtt_client.publish("command/motor", command)

                # Simulator-Einstellungen anpassen
                if self.simulator and hasattr(self.simulator, "start_test"):
                    self.simulator.start_test("right", 10)  # 10 Sekunden Testdauer

                # Timer für automatisches Stoppen nach 10 Sekunden
                self.root.after(10000, self._auto_stop_right_motor)

            except Exception as e:
                self.log(f"Fehler beim Starten des rechten Motors: {e}", "ERROR")
        else:
            try:
                # Motor stoppen
                self.right_motor_running = False
                self.right_motor_button.config(text="Rechter Motor starten")
                self.log("Rechter Motor gestoppt", "INFO")

                # Kommando über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    command = {
                        "action": "stop_motor",
                        "position": "right",
                    }
                    self.mqtt_client.publish("command/motor", command)

                # Simulator-Einstellungen anpassen
                if self.simulator and hasattr(self.simulator, "stop_test"):
                    self.simulator.stop_test()

            except Exception as e:
                self.log(f"Fehler beim Stoppen des rechten Motors: {e}", "ERROR")

    def _auto_stop_right_motor(self):
        """Stoppt den rechten Motor automatisch nach Ablauf der Zeit."""
        if self.right_motor_running:
            self.toggle_right_motor()
            self.log("Rechter Motor automatisch gestoppt (Zeitlimit erreicht)", "INFO")

    def can_message_handler(self, msg):
        """Callback für eingehende CAN-Nachrichten."""
        try:
            #  Explizite Debug-Ausgabe für ersten Nachweis
            if not hasattr(self, "_debug_message_count"):
                self._debug_message_count = 0

            self._debug_message_count += 1

            # Jede 100. Nachricht loggen für Performance
            if self._debug_message_count % 100 == 1:
                self.log(
                    f"CAN-Handler aktiv: {self._debug_message_count} Nachrichten verarbeitet",
                    "INFO",
                )

            # Debug-Log für erste Nachricht
            if self._debug_message_count == 1:
                self.log("ERSTE CAN-NACHRICHT EMPFANGEN! Handler funktioniert.", "INFO")
                self.log(f"Nachrichtentyp: {type(msg)}", "INFO")
                if hasattr(msg, "arbitration_id"):
                    self.log(f"CAN-ID: {hex(msg.arbitration_id)}", "INFO")
                if hasattr(msg, "interpreted_data"):
                    self.log(f"Interpretierte Daten: {msg.interpreted_data}", "INFO")

            # Nachricht ins Log schreiben, wenn sie den Filter passiert
            filter_text = self.message_filter.get().lower()

            # Nachricht formatieren
            if hasattr(msg, "arbitration_id") and hasattr(msg, "data"):
                # Standard CAN-Nachricht
                msg_str = f"ID: {hex(msg.arbitration_id)} Data: {' '.join([f'{b:02X}' for b in msg.data])}"
            elif hasattr(msg, "interpreted_data"):
                # High-Level interpretierte Daten
                msg_str = f"High-Level: {msg.interpreted_data}"
            else:
                # Fallback für andere Nachrichtenformate
                msg_str = str(msg)

            # Filter anwenden
            if not filter_text or filter_text in msg_str.lower():
                timestamp = (
                    f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] "
                    if self.show_timestamps.get()
                    else ""
                )

                formatted_message = f"{timestamp}{msg_str}\n"

                # Nachricht zur Queue hinzufügen
                message_queue.put(("can_log", formatted_message))

            #  Bridge-Funktionalität verbessern
            if self.bridge_running and self.mqtt_connected and self.mqtt_client:
                try:
                    # Für High-Level-Daten (interpretierte Daten)
                    if hasattr(msg, "interpreted_data"):
                        topic = "suspension/can/interpreted"
                        payload = msg.interpreted_data  # Dictionary direkt verwenden
                        self.mqtt_client.publish(topic, payload)

                        # Debug für erste MQTT-Nachricht
                        if not hasattr(self, "_first_mqtt_sent_logged"):
                            self.log(
                                "Erste CAN→MQTT Konvertierung (High-Level) erfolgreich!", "INFO"
                            )
                            self._first_mqtt_sent_logged = True

                    # Für Low-Level CAN-Frames
                    elif hasattr(msg, "arbitration_id") and hasattr(msg, "data"):
                        mqtt_data = {
                            "can_id": hex(msg.arbitration_id),
                            "data": list(msg.data),
                            "timestamp": getattr(msg, "timestamp", time.time()),
                            "source": "simulator",
                        }
                        topic = "suspension/can/raw"
                        payload = mqtt_data  # Dictionary direkt verwenden
                        self.mqtt_client.publish(topic, payload)

                        # Debug für erste Low-Level MQTT-Nachricht
                        if not hasattr(self, "_first_low_level_mqtt_logged"):
                            self.log(
                                "Erste CAN→MQTT Konvertierung (Low-Level) erfolgreich!", "INFO"
                            )
                            self._first_low_level_mqtt_logged = True

                except Exception as e:
                    self.log(f"Fehler bei der CAN→MQTT-Konvertierung: {e}", "ERROR")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung der CAN-Nachricht: {e}", "ERROR")

    def _handle_test_result(self, data):
        """Verarbeitet ein Testergebnis.

        Args:
                        data: Testergebnis-Daten
        """
        try:
            # Position des Tests ermitteln
            position = self._determine_side_from_data(data)

            # Wenn Volltest läuft, Ergebnis speichern
            if self.full_test_running:
                if position == "left":
                    self.left_test_result.config(text=f"Bestanden: {data.get('passed', False)}")
                    # Nach kurzer Verzögerung rechte Seite testen
                    self.root.after(2000, self._start_test_sequence_right)
                elif position == "right":
                    self.right_test_result.config(text=f"Bestanden: {data.get('passed', False)}")
                    # Nach kurzer Verzögerung Gesamtergebnis auswerten
                    self.root.after(2000, self._evaluate_full_test)

            # Log-Eintrag
            self.log(f"Testergebnis für {position}: {data}", "INFO")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung des Testergebnisses: {e}", "ERROR")

    def _handle_test_completed(self, data):
        """Verarbeitet die Benachrichtigung über einen abgeschlossenen Test.

        Args:
                        data: Daten zum Testabschluss
        """
        try:
            # Position des Tests ermitteln
            position = data.get("position", self._determine_side_from_data(data))

            # Log-Eintrag
            self.log(f"Test für {position} abgeschlossen", "INFO")

            # Motorstatus aktualisieren
            if position == "left":
                if self.left_motor_running:
                    self.left_motor_running = False
                    self.left_motor_button.config(text="Linker Motor starten")
            elif position == "right":
                if self.right_motor_running:
                    self.right_motor_running = False
                    self.right_motor_button.config(text="Rechter Motor starten")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung des Testabschlusses: {e}", "ERROR")

    def _evaluate_full_test(self):
        """Wertet die Ergebnisse des Volltests aus."""
        try:
            # Fortschritt aktualisieren
            self.full_test_progress["value"] = 90
            self.full_test_status_label.config(text="Auswertung läuft...")

            # Ergebnisse auslesen (hier vereinfacht)
            left_result_text = self.left_test_result.cget("text")
            right_result_text = self.right_test_result.cget("text")

            left_passed = "Bestanden: True" in left_result_text
            right_passed = "Bestanden: True" in right_result_text

            # Gesamtergebnis bestimmen
            overall_passed = left_passed and right_passed

            # Detaillierte Auswertung
            if overall_passed:
                status = "Beide Seiten bestanden - Fahrzeug in Ordnung"
                self._finish_full_test(True, status)
            elif left_passed and not right_passed:
                status = "Nur linke Seite bestanden - Rechter Dämpfer defekt"
                self._finish_full_test(False, status)
            elif not left_passed and right_passed:
                status = "Nur rechte Seite bestanden - Linker Dämpfer defekt"
                self._finish_full_test(False, status)
            else:
                status = "Beide Seiten nicht bestanden - Beide Dämpfer defekt"
                self._finish_full_test(False, status)

            # Ergebnis über MQTT veröffentlichen
            if self.mqtt_connected and self.mqtt_client:
                result_data = {
                    "test_type": "full_test",
                    "timestamp": time.time(),
                    "left_passed": left_passed,
                    "right_passed": right_passed,
                    "overall_passed": overall_passed,
                    "status": status,
                }
                self.mqtt_client.publish("test_result/full_test", result_data)

        except Exception as e:
            self.log(f"Fehler bei der Auswertung des Volltests: {e}", "ERROR")
            self._finish_full_test(False, f"Fehler bei der Auswertung: {e}")

    def _finish_full_test(self, passed, status):
        """Schließt den Volltest ab.

        Args:
                        passed: True, wenn der Test bestanden wurde
                        status: Statustext
        """
        # Fortschritt aktualisieren
        self.full_test_progress["value"] = 100
        self.full_test_status_label.config(text=status, foreground="green" if passed else "red")

        # Test-Status zurücksetzen
        self.full_test_running = False
        self.full_test_button.config(state=tk.NORMAL)

        # Log-Eintrag
        self.log(f"Volltest abgeschlossen: {status}", "INFO")

        # Nachricht anzeigen
        messagebox.showinfo(
            "Volltest abgeschlossen",
            f"Ergebnis: {'Bestanden' if passed else 'Nicht bestanden'}\n\n{status}",
        )

    def _determine_side_from_data(self, data):
        """Ermittelt die Seite (links/rechts) aus den Daten.

        Args:
                        data: Daten mit Positionsinformation

        Returns:
                        "left", "right" oder "unknown"
        """
        position = data.get("position", "").lower()
        if "left" in position or "links" in position:
            return "left"
        if "right" in position or "rechts" in position:
            return "right"
        return "unknown"

    def toggle_low_level(self):
        """Schaltet die Low-Level-CAN-Generierung ein oder aus."""
        try:
            # Simulator-Einstellungen anpassen
            if self.simulator and hasattr(self.simulator, "set_generate_low_level"):
                self.simulator.set_generate_low_level(self.low_level_enabled.get())
                self.log(
                    f"Low-Level-CAN-Generierung {'aktiviert' if self.low_level_enabled.get() else 'deaktiviert'}",
                    "INFO",
                )

                # Status-Nachricht über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "low_level_changed",
                        "enabled": self.low_level_enabled.get(),
                        "timestamp": time.time(),
                    }
                    self.mqtt_client.publish("status/simulator", status_message)
        except Exception as e:
            self.log(f"Fehler beim Ändern der Low-Level-Einstellung: {e}", "ERROR")

    def toggle_vehicle(self):
        """Schaltet die Fahrzeug-Präsenz ein oder aus."""
        try:
            # Simulator-Einstellungen anpassen
            if self.simulator and hasattr(self.simulator, "set_vehicle_present"):
                self.simulator.set_vehicle_present(self.vehicle_present.get())
                self.log(
                    f"Fahrzeug {'vorhanden' if self.vehicle_present.get() else 'nicht vorhanden'}",
                    "INFO",
                )
        except Exception as e:
            self.log(f"Fehler beim Ändern der Fahrzeug-Präsenz: {e}", "ERROR")

    def toggle_simulator(self):
        """Startet oder stoppt den CAN-Simulator."""
        if not self.simulator_running:
            try:
                #  Simulator über connect() starten
                if hasattr(self.simulator, "connect"):
                    success = self.simulator.connect()
                    if not success:
                        self.log("Simulator-Verbindung fehlgeschlagen", "ERROR")
                        return

                self.simulator_running = True
                self.simulator_button.config(text="Simulator stoppen")
                self.log("Simulator gestartet", "INFO")

                #  MQTT-Nachricht als Dictionary (nicht JSON-String)
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "simulator_started",
                        "timestamp": time.time(),
                        "protocol": self.protocol.get(),
                        "damping_quality": self.damping_quality.get(),
                    }
                    self.mqtt_client.publish("status/simulator", status_message)

                # Simulationsparameter setzen
                if hasattr(self.simulator, "set_simulation_profile"):
                    self.simulator.set_simulation_profile(self.protocol.get())

                if hasattr(self.simulator, "set_damping_quality"):
                    self.simulator.set_damping_quality(self.damping_quality.get())

                if hasattr(self.simulator, "set_test_method"):
                    self.simulator.set_test_method(self.test_method.get())

                if hasattr(self.simulator, "set_generate_low_level"):
                    self.simulator.set_generate_low_level(self.low_level_enabled.get())

                if hasattr(self.simulator, "set_vehicle_present"):
                    self.simulator.set_vehicle_present(self.vehicle_present.get())

            except Exception as e:
                self.log(f"Fehler beim Starten des Simulators: {e}", "ERROR")
        else:
            try:
                #  Simulator über shutdown() stoppen
                if hasattr(self.simulator, "shutdown"):
                    self.simulator.shutdown()

                self.simulator_running = False
                self.simulator_button.config(text="Simulator starten")
                self.log("Simulator gestoppt", "INFO")

                #  MQTT-Nachricht als Dictionary
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "simulator_stopped",
                        "timestamp": time.time(),
                    }
                    self.mqtt_client.publish("status/simulator", status_message)

            except Exception as e:
                self.log(f"Fehler beim Stoppen des Simulators: {e}", "ERROR")

    def on_protocol_change(self, event=None):
        """Wird aufgerufen, wenn das Protokoll geändert wird."""
        try:
            # Simulator-Einstellungen anpassen
            if self.simulator and hasattr(self.simulator, "set_simulation_profile"):
                self.simulator.set_simulation_profile(self.protocol.get())
                self.log(f"Protokoll geändert auf: {self.protocol.get()}", "INFO")

                # Status-Nachricht über MQTT senden, wenn verbunden
                if self.mqtt_connected and self.mqtt_client:
                    status_message = {
                        "status": "protocol_changed",
                        "protocol": self.protocol.get(),
                        "timestamp": time.time(),
                    }
                    self.mqtt_client.publish("status/simulator", status_message)
        except Exception as e:
            self.log(f"Fehler beim Ändern des Protokolls: {e}", "ERROR")

    def on_damping_change(self, event=None):
        """Wird aufgerufen, wenn die Dämpfungsqualität geändert wird."""
        try:
            # Simulator-Einstellungen anpassen
            if self.simulator and hasattr(self.simulator, "set_damping_quality"):
                self.simulator.set_damping_quality(self.damping_quality.get())
                self.log(f"Dämpfungsqualität geändert auf: {self.damping_quality.get()}", "INFO")
        except Exception as e:
            self.log(f"Fehler beim Ändern der Dämpfungsqualität: {e}", "ERROR")

    def on_test_method_change(self, event=None):
        """Wird aufgerufen, wenn die Testmethode geändert wird."""
        try:
            # Simulator-Einstellungen anpassen
            if self.simulator and hasattr(self.simulator, "set_test_method"):
                self.simulator.set_test_method(self.test_method.get())
                self.log(f"Testmethode geändert auf: {self.test_method.get()}", "INFO")
        except Exception as e:
            self.log(f"Fehler beim Ändern der Testmethode: {e}", "ERROR")

    def on_test_mode_change(self, event=None):
        """Wird aufgerufen, wenn der Testmodus geändert wird."""
        try:
            # Vorgefertigte Einstellungen basierend auf dem Testmodus
            mode = self.test_mode.get()
            if mode == "good_damping":
                self.damping_quality.set("good")
                self.log("Testmodus: Gute Dämpfung aktiviert", "INFO")
            elif mode == "marginal_damping":
                self.damping_quality.set("marginal")
                self.log("Testmodus: Grenzwertige Dämpfung aktiviert", "INFO")
            elif mode == "bad_damping":
                self.damping_quality.set("bad")
                self.log("Testmodus: Schlechte Dämpfung aktiviert", "INFO")
            else:
                self.log("Testmodus: Standard (aktuelle Einstellungen)", "INFO")

            # Simulator-Einstellungen anpassen
            if self.simulator:
                if hasattr(self.simulator, "set_damping_quality"):
                    self.simulator.set_damping_quality(self.damping_quality.get())
                if hasattr(self.simulator, "set_test_mode"):
                    self.simulator.set_test_mode(mode)
        except Exception as e:
            self.log(f"Fehler beim Ändern des Testmodus: {e}", "ERROR")

    def _on_mqtt_message(self, topic, data):
        """Callback für eingehende MQTT-Nachrichten"""
        try:
            # Logging für Debug
            timestamp = time.strftime("%H:%M:%S.%f")[:-3]
            self.log(f"[{timestamp}] Topic: {topic}", "INFO")

            # Payload-Ausgabe
            if isinstance(data, dict):
                payload_str = json.dumps(data, indent=2)
            else:
                payload_str = str(data)
            self.log(f"Payload: {payload_str}", "INFO")

            # Kommandos verarbeiten
            if "command" in topic.lower() and isinstance(data, dict):
                action = data.get("action", "")

                if action == "start_test":
                    # Test-Parameter extrahieren
                    position = data.get("position", "front_left")
                    parameters = data.get("parameters", {})
                    duration = parameters.get("duration", 30)

                    # Position in Seite umwandeln
                    if position in ["front_left", "rear_left"]:
                        side = "left"
                    elif position in ["front_right", "rear_right"]:
                        side = "right"
                    else:
                        side = "left"  # Default

                    self.log(f"MQTT-Befehl: Test starten für {side} ({duration}s)", "INFO")

                    # Test starten
                    self._start_test(side, duration)

                elif action == "stop_test":
                    self.log("MQTT-Befehl: Test stoppen", "INFO")
                    self._stop_test()

                elif action == "emergency_stop":
                    self.log("MQTT-Befehl: NOT-STOP", "ERROR")
                    self._emergency_stop()

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der MQTT-Nachricht: {e}")
            self.log(f"MQTT-Fehler: {e}", "ERROR")

    def apply_filter(self):
        """Wendet den Filter auf die CAN-Nachrichten an."""
        self.log(f"Filter angewendet: {self.message_filter.get()}", "INFO")

    def reset_filter(self):
        """Setzt den Filter zurück."""
        self.message_filter.set("")
        self.log("Filter zurückgesetzt", "INFO")

    def log(self, message, level="INFO"):
        """Fügt eine Nachricht zum Log hinzu.

        Args:
                        message: Nachrichtentext
                        level: Log-Level (INFO, WARNING, ERROR)
        """
        # Zeitstempel
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Log-Nachricht formatieren
        formatted_message = f"[{timestamp}] [{level}] {message}\n"

        # Nachricht zur Queue hinzufügen
        message_queue.put(("status", formatted_message))

        # Auch ins Python-Logging schreiben
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    def handle_gui_command(self, message):
        """Verarbeitet Kommandos für die GUI.

        Args:
                        message: Kommando-Nachricht
        """
        try:
            action = message.get("action", "")

            if action == "start_simulator":
                if not self.simulator_running:
                    self.toggle_simulator()
            elif action == "stop_simulator":
                if self.simulator_running:
                    self.toggle_simulator()
            elif action == "start_bridge":
                if not self.bridge_running:
                    self.toggle_bridge()
            elif action == "stop_bridge":
                if self.bridge_running:
                    self.toggle_bridge()
            elif action == "start_motor":
                position = message.get("position", "")
                if position == "left" and not self.left_motor_running:
                    self.toggle_left_motor()
                elif position == "right" and not self.right_motor_running:
                    self.toggle_right_motor()
                elif position == "all":
                    if not self.left_motor_running:
                        self.toggle_left_motor()
                    if not self.right_motor_running:
                        self.toggle_right_motor()
            elif action == "stop_motor":
                position = message.get("position", "")
                if position == "left" and self.left_motor_running:
                    self.toggle_left_motor()
                elif position == "right" and self.right_motor_running:
                    self.toggle_right_motor()
                elif position == "all":
                    if self.left_motor_running:
                        self.toggle_left_motor()
                    if self.right_motor_running:
                        self.toggle_right_motor()
            elif action == "set_protocol":
                protocol = message.get("protocol", "")
                if protocol in ["eusama", "asa"]:
                    self.protocol.set(protocol)
                    self.on_protocol_change()
            elif action == "set_damping_quality":
                quality = message.get("quality", "")
                if quality in ["good", "marginal", "bad"]:
                    self.damping_quality.set(quality)
                    self.on_damping_change()
            elif action == "set_test_method":
                method = message.get("method", "")
                if method in ["phase_shift", "resonance"]:
                    self.test_method.set(method)
                    self.on_test_method_change()
            elif action == "set_test_mode":
                mode = message.get("mode", "")
                if mode in ["default", "good_damping", "marginal_damping", "bad_damping"]:
                    self.test_mode.set(mode)
                    self.on_test_mode_change()
            elif action == "start_test":
                self._process_start_command(message)
            elif action == "clear_logs":
                self.can_log.delete(1.0, tk.END)
                self.mqtt_log.delete(1.0, tk.END)
                self.log("Logs gelöscht", "INFO")
            else:
                self.log(f"Unbekanntes GUI-Kommando: {action}", "WARNING")

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung des GUI-Kommandos: {e}", "ERROR")

    def handle_tester_command(self, message):
        """Verarbeitet Kommandos für den Tester.

        Args:
                        message: Kommando-Nachricht
        """
        try:
            action = message.get("action", "")
            self.log(f"Tester-Kommando empfangen: {action}", "INFO")

        # Hier könnten spezifische Kommandos für den Tester verarbeitet werden
        # Beispiel: Konfiguration ändern, Tests starten, etc.

        except Exception as e:
            self.log(f"Fehler bei der Verarbeitung des Tester-Kommandos: {e}", "ERROR")

    def handle_simulator_command(self, command_data):
        """Verarbeitet MQTT-Befehle für den Simulator."""
        try:
            action = command_data.get("action")

            if action == "start_test":
                # CAN-Datenerzeugung starten
                side = command_data.get("side", "left")
                duration = command_data.get("duration", 30)

                if self.simulator and hasattr(self.simulator, "start_test"):
                    self.simulator.start_test(side, duration)
                    self.log(f"Test gestartet: Seite={side}, Dauer={duration}s", "INFO")
                else:
                    self.log("Simulator nicht verfügbar für Teststart", "ERROR")

            elif action == "stop_test":
                # CAN-Datenerzeugung stoppen
                if self.simulator and hasattr(self.simulator, "stop_test"):
                    self.simulator.stop_test()
                    self.log("Test gestoppt", "INFO")
                else:
                    self.log("Simulator nicht verfügbar für Teststopp", "ERROR")

            elif action == "set_vehicle_present":
                # Fahrzeug-Status setzen
                present = command_data.get("present", False)

                if self.simulator and hasattr(self.simulator, "set_vehicle_present"):
                    self.simulator.set_vehicle_present(present)
                    self.vehicle_present.set(present)
                    status = "aktiviert" if present else "deaktiviert"
                    self.log(f"Fahrzeug für Datengenerierung {status}", "INFO")
                else:
                    self.log("Simulator nicht verfügbar für Fahrzeug-Status", "ERROR")

            elif action == "start_simulator":
                # Simulator starten (falls nicht bereits läuft)
                if not self.simulator_running:
                    self.toggle_simulator()
                    self.log("Simulator auf Befehl gestartet", "INFO")
                else:
                    self.log("Simulator läuft bereits", "INFO")

            elif action == "stop_simulator":
                # Simulator stoppen
                if self.simulator_running:
                    self.toggle_simulator()
                    self.log("Simulator auf Befehl gestoppt", "INFO")
                else:
                    self.log("Simulator ist bereits gestoppt", "INFO")

            else:
                self.log(f"Unbekannter Simulator-Befehl: {action}", "WARNING")

        except Exception as e:
            self.log(f"Fehler bei Simulator-Befehlsverarbeitung: {e}", "ERROR")

    def _process_start_command(self, message):
        """Verarbeitet ein Start-Kommando.

        Args:
                        message: Kommando-Nachricht
        """
        try:
            # Prüfen, ob ein Fahrzeug vorhanden ist
            if not self.vehicle_present.get():
                self.log("Test kann nicht gestartet werden: Kein Fahrzeug vorhanden", "ERROR")
                return

            # Prüfen, ob die Bridge gestartet ist
            if not self.bridge_running:
                self.log("Test kann nicht gestartet werden: Bridge nicht gestartet", "ERROR")
                return

            position = message.get("position", "left")
            test_method = message.get("test_method", self.test_method.get())
            damping_quality = message.get("damping_quality", self.damping_quality.get())
            parameters = message.get("parameters", {})
            duration = parameters.get("duration", 30)

            # Testmethode und Dämpfungsqualität setzen
            self.test_method.set(test_method)
            self.damping_quality.set(damping_quality)
            self.on_test_method_change()
            self.on_damping_change()

            # Motor starten
            if position == "left" and not self.left_motor_running:
                self.toggle_left_motor()
            elif position == "right" and not self.right_motor_running:
                self.toggle_right_motor()
            elif position == "all":
                if not self.left_motor_running:
                    self.toggle_left_motor()
                if not self.right_motor_running:
                    self.toggle_right_motor()

            # Simulator-Test starten
            if self.simulator and hasattr(self.simulator, "start_test"):
                # Konvertiere position zu side für den Simulator
                side = position
                if position in ["front_left", "rear_left"]:
                    side = "left"
                elif position in ["front_right", "rear_right"]:
                    side = "right"

                self.simulator.start_test(side, duration)
                self.log(f"Simulator-Test gestartet: Seite={side}, Dauer={duration}s", "INFO")
            else:
                self.log("Simulator nicht verfügbar für Teststart", "ERROR")

            self.log(f"Test gestartet für Position: {position}", "INFO")

        except Exception as e:
            self.log(f"Fehler beim Starten des Tests: {e}", "ERROR")

    def process_queue(self):
        """Verarbeitet die Nachrichten-Queue."""
        try:
            # Nachrichten aus der Queue verarbeiten
            while not message_queue.empty():
                message_type, message = message_queue.get_nowait()
                if message_type == "can_log":
                    # CAN-Nachricht ins Log schreiben
                    self.can_log.insert(tk.END, message)
                    if self.auto_scroll.get():
                        self.can_log.see(tk.END)
                elif message_type == "mqtt_log":
                    # MQTT-Nachricht ins Log schreiben
                    self.mqtt_log.insert(tk.END, message)
                    if self.auto_scroll.get():
                        self.mqtt_log.see(tk.END)
                elif message_type == "status":
                    # Status-Nachricht in die Statusleiste schreiben
                    self.status_label.config(text=message.strip())
            # MQTT-Nachrichten aus der Queue verarbeiten
            while not mqtt_message_queue.empty():
                topic, message = mqtt_message_queue.get_nowait()
                if self.mqtt_connected and self.mqtt_client:
                    try:
                        self.mqtt_client.publish(topic, message)
                    except Exception as e:
                        self.log(f"Fehler beim Senden der MQTT-Nachricht: {e}", "ERROR")
            # Simulator-Status aktualisieren
            if self.simulator_running:
                # Hier könnten regelmäßige Updates für den Simulator erfolgen
                pass
            # Bridge-Status aktualisieren
            if self.bridge_running:
                # Hier könnten regelmäßige Updates für die Bridge erfolgen
                pass
            # Motorstatus aktualisieren
            if self.left_motor_running:
                # Hier könnten regelmäßige Updates für den linken Motor erfolgen
                pass
            if self.right_motor_running:
                # Hier könnten regelmäßige Updates für den rechten Motor erfolgen
                pass
            # Volltest-Status aktualisieren
            if self.full_test_running:
                # Hier könnten regelmäßige Updates für den Volltest erfolgen
                pass
        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung der Queue: {e}")
        # Timer für nächste Verarbeitung setzen
        self.root.after(100, self.process_queue)

    def on_closing(self):
        """Wird aufgerufen, wenn das Fenster geschlossen wird."""
        try:
            # Bestätigungsdialog anzeigen
            if messagebox.askokcancel("Beenden", "Möchten Sie die Anwendung wirklich beenden?"):
                # Aufräumen
                self.cleanup()
                # Fenster schließen
                self.root.destroy()
        except Exception as e:
            logger.error(f"Fehler beim Schließen der Anwendung: {e}")
            # Im Fehlerfall trotzdem versuchen, das Fenster zu schließen
            self.root.destroy()

    def cleanup(self):
        """Räumt auf und gibt Ressourcen frei."""
        try:
            # Simulator stoppen
            if self.simulator_running:
                if hasattr(self.simulator, "stop"):
                    self.simulator.stop()
                elif hasattr(self.simulator, "set_auto_generate"):
                    self.simulator.set_auto_generate(False)
                self.simulator_running = False
            # Motoren stoppen
            if self.left_motor_running:
                if hasattr(self.simulator, "stop_motor"):
                    self.simulator.stop_motor("left")
                elif hasattr(self.simulator, "set_motor_running"):
                    self.simulator.set_motor_running("left", False)
                self.left_motor_running = False
            if self.right_motor_running:
                if hasattr(self.simulator, "stop_motor"):
                    self.simulator.stop_motor("right")
                elif hasattr(self.simulator, "set_motor_running"):
                    self.simulator.set_motor_running("right", False)
                self.right_motor_running = False
            # MQTT-Verbindung trennen
            if self.mqtt_connected and self.mqtt_client:
                self.mqtt_client.disconnect()
                self.mqtt_connected = False
            # Weitere Aufräumarbeiten hier...
            logger.info("Anwendung ordnungsgemäß beendet")
        except Exception as e:
            logger.error(f"Fehler beim Aufräumen: {e}")

    def debug_simulator_state(self):
        """Debug-Funktion um Simulator-Zustand zu prüfen."""
        try:
            self.log("=== SIMULATOR DEBUG ===", "INFO")

            if not self.simulator:
                self.log("❌ Simulator ist None", "ERROR")
                return

            # Verfügbare Methoden prüfen
            methods = [attr for attr in dir(self.simulator) if not attr.startswith("_")]
            self.log(f"Verfügbare Methoden: {methods[:10]}...", "INFO")

            # Zustandsprüfung
            if hasattr(self.simulator, "test_running"):
                self.log(f"Test läuft: {self.simulator.test_running}", "INFO")
            if hasattr(self.simulator, "connected"):
                self.log(f"Verbunden: {self.simulator.connected}", "INFO")
            if hasattr(self.simulator, "vehicle_present"):
                self.log(f"Fahrzeug vorhanden: {self.simulator.vehicle_present}", "INFO")

            self.log("=== DEBUG ENDE ===", "INFO")

        except Exception as e:
            self.log(f"Debug-Fehler: {e}", "ERROR")


def main():
    """Hauptfunktion zum Starten der Anwendung."""
    # Kommandozeilenargumente parsen
    parser = argparse.ArgumentParser(description="SimulatorApp Simulator GUI")
    parser.add_argument("--debug", action="store_true", help="Debug-Modus aktivieren")
    args = parser.parse_args()

    # Logging-Level setzen
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug-Modus aktiviert")

    # Tkinter-Root erstellen
    root = tk.Tk()

    # Anwendung erstellen
    app = SimulatorApp(root)

    # Anwendung initialisieren
    initialize_app(app)

    # Hauptloop starten
    root.mainloop()


def initialize_app(app):
    """Initialisiert die Anwendung mit Standardwerten."""
    try:
        #  Fahrzeug ZUERST als vorhanden setzen
        app.vehicle_present.set(True)  # KRITISCH für Datengenerierung
        app.log("Fahrzeug für Datengenerierung aktiviert", "INFO")

        # Simulator automatisch starten, wenn erfolgreich initialisiert
        # if app.simulator and not app.simulator_running:
        # app.log("Starte Simulator automatisch...", "INFO")
        # app.toggle_simulator()

        # MQTT automatisch verbinden
        if not app.mqtt_connected:
            app.log("Verbinde automatisch mit MQTT...", "INFO")
            app.toggle_mqtt_connection()

        # Protokoll auf EUSAMA setzen
        app.protocol.set("eusama")
        app.on_protocol_change()

        # Dämpfungsqualität auf "gut" setzen
        app.damping_quality.set("good")
        app.on_damping_change()

        # Testmethode auf "Phasenverschiebung" setzen
        app.test_method.set("phase_shift")
        app.on_test_method_change()

        # Testmodus auf "Standard" setzen
        app.test_mode.set("default")
        app.on_test_mode_change()

        # Low-Level-CAN aktivieren
        app.low_level_enabled.set(True)
        app.toggle_low_level()

        #  Bridge automatisch starten
        if not app.bridge_running:
            app.log("Starte Bridge automatisch...", "INFO")
            app.toggle_bridge()

        # Willkommensnachricht ins Log schreiben
        app.log("SimulatorApp Simulator GUI erfolgreich gestartet", "INFO")
        app.log("Simulator läuft - CAN-Daten werden generiert", "INFO")
        app.log("Bridge aktiv - CAN→MQTT Konvertierung läuft", "INFO")

    except Exception as e:
        logger.error(f"Fehler bei der Initialisierung der Anwendung: {e}")


if __name__ == "__main__":
    main()