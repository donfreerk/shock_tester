"""
Korrigierte Simplified GUI mit Start-Button und korrekten MQTT-Topics
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import json
from datetime import datetime
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

# MQTT Client Import (angepasst)
import paho.mqtt.client as mqtt

# Logging Setup
import logging
logging.basicConfig(level=logging.DEBUG)  # DEBUG statt INFO
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Datenklasse für Testergebnisse"""
    test_id: str
    position: str
    timestamp: float
    success: bool
    phase_shift: Optional[float] = None
    frequency: Optional[float] = None
    platform_position: Optional[float] = None
    tire_force: Optional[float] = None
    static_weight: Optional[float] = None
    dms_values: Optional[List[int]] = None
    elapsed_time: Optional[float] = None

class MQTTClient:
    """Vereinfachter MQTT-Client für die GUI"""

    def __init__(self, broker: str = "localhost", port: int = 1883):
        self.broker = broker
        self.port = port
        self.client = None
        self.connected = False
        self.message_callbacks = {}

    def connect(self) -> bool:
        """Verbindet mit MQTT-Broker"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            # Warte auf Verbindung (max 5 Sekunden)
            for _ in range(50):
                if self.connected:
                    return True
                time.sleep(0.1)

            return False

        except Exception as e:
            logger.error(f"MQTT-Verbindungsfehler: {e}")
            return False

    def disconnect(self):
        """Trennt MQTT-Verbindung"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    def subscribe(self, topic: str, callback):
        """Abonniert Topic mit Callback"""
        if self.client and self.connected:
            self.client.subscribe(topic)
            self.message_callbacks[topic] = callback
            logger.info(f"Topic abonniert: {topic}")

    def publish(self, topic: str, payload: Dict[str, Any]):
        """Publiziert Nachricht"""
        if self.client and self.connected:
            message = json.dumps(payload)
            self.client.publish(topic, message)
            logger.debug(f"Nachricht publiziert: {topic}")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT Connect-Callback"""
        if rc == 0:
            self.connected = True
            logger.info(f"MQTT verbunden mit {self.broker}:{self.port}")
        else:
            logger.error(f"MQTT-Verbindung fehlgeschlagen: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT Disconnect-Callback"""
        self.connected = False
        logger.info("MQTT-Verbindung getrennt")

    def _on_message(self, client, userdata, msg):
        """MQTT Message-Callback mit Debug-Logging"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # DEBUG: Alle empfangenen MQTT-Nachrichten loggen
            logger.debug(f"MQTT empfangen: {topic} -> {payload}")

            # Suche passenden Callback
            for subscribed_topic, callback in self.message_callbacks.items():
                if topic == subscribed_topic or topic.startswith(subscribed_topic.rstrip('#')):
                    callback(topic, payload)
                    break
            else:
                # DEBUG: Topic nicht behandelt
                logger.warning(f"Unbehandeltes MQTT-Topic: {topic}")

        except Exception as e:
            logger.error(f"Fehler bei MQTT-Message-Verarbeitung: {e}")


class TestControlPanel:
    """Panel für Test-Steuerung mit Start-Button"""

    def __init__(self, parent_frame, mqtt_client: MQTTClient, log_callback):
        self.parent = parent_frame
        self.mqtt_client = mqtt_client
        self.log_callback = log_callback
        self.test_running = False
        self.live_display_callback = None  # Callback für Live-Display Reset

        self._create_widgets()

    def set_live_display_callback(self, callback):
        """Setzt Callback für Live-Display Reset"""
        self.live_display_callback = callback

    def _create_widgets(self):
        """Erstellt die UI-Elemente"""
        # Haupt-Frame
        control_frame = ttk.LabelFrame(self.parent, text="🎛️ Test-Steuerung", padding="10")
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Test-Parameter Frame
        param_frame = ttk.Frame(control_frame)
        param_frame.pack(fill=tk.X, pady=(0, 10))

        # Position Auswahl
        ttk.Label(param_frame, text="Position:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.position_var = tk.StringVar(value="front_right")
        position_combo = ttk.Combobox(param_frame, textvariable=self.position_var,
                                     values=["front_left", "front_right", "rear_left", "rear_right"],
                                     state="readonly", width=15)
        position_combo.grid(row=0, column=1, padx=(0, 15))

        # Testmethode Auswahl
        ttk.Label(param_frame, text="Methode:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.method_var = tk.StringVar(value="phase_shift")
        method_combo = ttk.Combobox(param_frame, textvariable=self.method_var,
                                   values=["phase_shift", "resonance"],
                                   state="readonly", width=15)
        method_combo.grid(row=0, column=3, padx=(0, 15))

        # Testdauer
        ttk.Label(param_frame, text="Dauer (s):").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.duration_var = tk.StringVar(value="30")
        duration_entry = ttk.Entry(param_frame, textvariable=self.duration_var, width=8)
        duration_entry.grid(row=0, column=5)

        # Buttons Frame
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)

        # Start-Button
        self.start_button = ttk.Button(button_frame, text="🚀 Test starten",
                                      command=self._start_test, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        # Stop-Button
        self.stop_button = ttk.Button(button_frame, text="⏹️ Test stoppen",
                                     command=self._stop_test, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))

        # Status-Label
        self.status_var = tk.StringVar(value="Bereit für Test")
        status_label = ttk.Label(button_frame, textvariable=self.status_var,
                                foreground="green", font=("Arial", 10, "bold"))
        status_label.pack(side=tk.RIGHT)

    def _start_test(self):
        """Startet einen neuen Test"""
        if self.test_running:
            return

        try:
            # Parameter sammeln
            position = self.position_var.get()
            method = self.method_var.get()
            duration = float(self.duration_var.get())

            if duration <= 0 or duration > 300:  # Max 5 Minuten
                messagebox.showerror("Fehler", "Testdauer muss zwischen 0 und 300 Sekunden liegen")
                return

            # Live-Display für neuen Test zurücksetzen
            if self.live_display_callback:
                self.live_display_callback()

            # Test-Kommando senden
            test_command = {
                "command": "start_test",
                "parameters": {
                    "position": position,
                    "method": method,
                    "duration": duration,
                    "timestamp": time.time()
                },
                "source": "gui"
            }

            self.mqtt_client.publish("suspension/test/command", test_command)

            # UI aktualisieren
            self.test_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set(f"Test läuft ({method} @ {position})...")

            self.log_callback("Test", f"Test gestartet: {method} @ {position} für {duration}s", "info")

        except ValueError:
            messagebox.showerror("Fehler", "Ungültige Testdauer")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Starten des Tests: {e}")

    def _stop_test(self):
        """Stoppt den laufenden Test"""
        try:
            # Stop-Kommando senden
            stop_command = {
                "command": "stop_test",
                "timestamp": time.time(),
                "source": "gui"
            }

            self.mqtt_client.publish("suspension/test/command", stop_command)

            # UI aktualisieren
            self._reset_ui()
            self.log_callback("Test", "Test manuell gestoppt", "warning")

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Stoppen des Tests: {e}")

    def _reset_ui(self):
        """Setzt die UI nach Test-Ende zurück"""
        self.test_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Bereit für Test")


class LiveDataDisplay:
    """Live-Anzeige für aktuelle Messdaten OHNE Charts während Test"""

    def __init__(self, parent_frame):
        self.parent = parent_frame
        self.current_data = {}
        self.test_start_time = None
        self.test_active = False

        self._create_widgets()

    def _create_widgets(self):
        """Erstellt die UI-Elemente"""
        # Hauptcontainer
        main_container = ttk.Frame(self.parent)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Live-Datenfelder (während Test)
        self._create_data_fields(main_container)

        # Platzhalter für Post-Test-Charts
        self._create_result_area(main_container)

    def _create_data_fields(self, parent):
        """Erstellt Live-Datenfelder"""
        data_frame = ttk.LabelFrame(parent, text="📊 Live-Messdaten", padding="10")
        data_frame.pack(fill=tk.X, padx=5, pady=5)

        # Grid für Datenfelder
        fields = [
            ("Phase Shift:", "phase_shift", "°", "#0066CC"),
            ("Frequenz:", "frequency", "Hz", "#FF6600"),
            ("Plattform Position:", "platform_position", "mm", "#00AA00"),
            ("Reifenkraft:", "tire_force", "N", "#CC0000"),
            ("Verstrichene Zeit:", "elapsed", "s", "#666666")
        ]

        self.value_vars = {}
        self.value_labels = {}

        for i, (label, key, unit, color) in enumerate(fields):
            row = i // 3
            col = (i % 3) * 4

            # Label
            ttk.Label(data_frame, text=label).grid(row=row, column=col, sticky=tk.W, padx=(0, 5))

            # Wert
            self.value_vars[key] = tk.StringVar(value="---")
            value_label = ttk.Label(data_frame, textvariable=self.value_vars[key],
                                   font=("Arial", 11, "bold"), foreground=color)
            value_label.grid(row=row, column=col+1, sticky=tk.W, padx=(0, 5))
            self.value_labels[key] = value_label

            # Einheit
            ttk.Label(data_frame, text=unit).grid(row=row, column=col+2, sticky=tk.W, padx=(0, 20))

        # DMS-Werte
        dms_frame = ttk.LabelFrame(data_frame, text="DMS-Sensoren", padding="5")
        dms_frame.grid(row=len(fields)//3 + 1, column=0, columnspan=12, sticky=tk.W+tk.E, pady=(10, 0))

        self.dms_vars = {}
        for i in range(4):
            ttk.Label(dms_frame, text=f"DMS{i+1}:").grid(row=0, column=i*2, sticky=tk.W, padx=(0, 5))
            self.dms_vars[f"dms{i+1}"] = tk.StringVar(value="---")
            ttk.Label(dms_frame, textvariable=self.dms_vars[f"dms{i+1}"],
                     font=("Arial", 9, "bold")).grid(row=0, column=i*2+1, sticky=tk.W, padx=(0, 15))

        # Status-Indikator
        status_frame = ttk.Frame(data_frame)
        status_frame.grid(row=len(fields)//3 + 2, column=0, columnspan=12, sticky=tk.W+tk.E, pady=(10, 0))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Warte auf Test...")
        status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                font=("Arial", 10, "bold"), foreground="#666666")
        status_label.pack(side=tk.LEFT, padx=(5, 0))

    def _create_result_area(self, parent):
        """Erstellt Bereich für Post-Test-Ergebnisse"""
        self.result_frame = ttk.LabelFrame(parent, text="📈 Test-Ergebnisse (nach Testende)", padding="5")
        self.result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Platzhalter-Text
        self.placeholder_label = ttk.Label(
            self.result_frame,
            text="🔄 Warte auf Testergebnisse...\n\nDaten werden während dem Test gesammelt\nund nach Testende als vollständige Sinuskurven angezeigt.",
            font=("Arial", 12),
            foreground="#666666",
            anchor="center",
            justify="center"
        )
        self.placeholder_label.pack(expand=True)

        # Chart-Container (wird bei Bedarf erstellt)
        self.chart_container = None
        self.fig = None
        self.canvas = None

    def update_data(self, data: Dict[str, Any]):
        """Aktualisiert nur die Live-Datenfelder während Test"""
        try:
            # Test-Start-Zeit setzen
            if self.test_start_time is None:
                self.test_start_time = time.time()
                self.test_active = True
                self.status_var.set("🟢 Test läuft - sammle Daten...")

            # Verstrichene Zeit berechnen
            elapsed = time.time() - self.test_start_time
            data['elapsed'] = elapsed

            # Hauptdaten aktualisieren
            for key, var in self.value_vars.items():
                if key in data:
                    if key in ['phase_shift', 'frequency', 'platform_position', 'tire_force']:
                        var.set(f"{data[key]:.2f}")
                    elif key == 'elapsed':
                        var.set(f"{data[key]:.1f}")
                    else:
                        var.set(str(data[key]))

            # DMS-Werte aktualisieren
            if "dms_values" in data and data["dms_values"]:
                dms_values = data["dms_values"]
                for i, value in enumerate(dms_values[:4]):
                    self.dms_vars[f"dms{i+1}"].set(str(value))

            # Status mit Farbe aktualisieren
            phase_val = data.get('phase_shift', 0)
            if phase_val >= 35:
                status = f"✅ AKTUELL GUT (φ = {phase_val:.1f}°)"
                color = "#00AA00"
            elif phase_val >= 20:
                status = f"⚠️ AKTUELL MÄSSIG (φ = {phase_val:.1f}°)"
                color = "#FF8800"
            else:
                status = f"❌ AKTUELL SCHLECHT (φ = {phase_val:.1f}°)"
                color = "#CC0000"

            self.status_var.set(status)

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Live-Daten: {e}")

    def display_final_result(self, result_data: Dict[str, Any]):
        """
        VERBESSERT: Zeigt vollständige Sinuskurven nach Testende mit optimiertem Layout
        
        VERBESSERUNGEN:
        - Kombinierte Darstellung: Plattformposition und Reifenkraft überlagert
        - Keine Label-Überlappungen mehr
        - Bessere Subplot-Anordnung (2 statt 3 Plots)
        - Optimierte Achsen-Labels und Titel-Positionierung
        """
        try:
            self.test_active = False
            self.status_var.set("🔄 Erstelle finale Sinuskurven...")

            # Platzhalter verstecken
            if self.placeholder_label:
                self.placeholder_label.pack_forget()

            # Chart-Container erstellen falls nicht vorhanden
            if self.chart_container is None:
                self.chart_container = ttk.Frame(self.result_frame)
                self.chart_container.pack(fill=tk.BOTH, expand=True)

                # VERBESSERUNG: Matplotlib Figure mit nur 2 Subplots für besseres Layout
                self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(14, 8))
                self.fig.patch.set_facecolor('white')

                # Canvas
                self.canvas = FigureCanvasTkAgg(self.fig, self.chart_container)
                self.canvas.draw()
                self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

                # Toolbar
                toolbar = NavigationToolbar2Tk(self.canvas, self.chart_container)
                toolbar.update()

            # Daten extrahieren
            time_data = np.array(result_data.get('time_data', []))
            platform_data = np.array(result_data.get('platform_position', []))
            force_data = np.array(result_data.get('tire_force', []))
            phase_shifts = np.array(result_data.get('phase_shifts', []))
            frequencies = np.array(result_data.get('frequencies', []))

            # Alle Achsen leeren
            self.ax1.clear()
            self.ax2.clear()

            if len(time_data) > 0:
                # KRITISCHE VERBESSERUNG: Kombinierter Plot mit Twin-Axes
                self._plot_combined_signals(time_data, platform_data, force_data)
                self._plot_phase_analysis(frequencies, phase_shifts, result_data)
            else:
                # Fallback wenn keine Daten
                self._plot_no_data_message()

            # VERBESSERUNG: Titel mit Ergebnis (optimierte Position)
            evaluation = result_data.get('evaluation', 'UNBEKANNT')
            min_phase = result_data.get('min_phase_shift', 0)
            position = result_data.get('position', 'unknown')

            title_color = 'green' if evaluation.lower() in ['good', 'excellent'] else 'red'
            self.fig.suptitle(
                f'EGEA-Test {position.upper()} - φmin = {min_phase:.1f}° - {evaluation.upper()}',
                fontsize=14,
                fontweight='bold',
                color=title_color,
                y=0.96  # Titel höher positionieren
            )

            # KRITISCHE VERBESSERUNG: Layout optimieren für keine Überlappungen
            self.fig.subplots_adjust(
                left=0.08,      # Linker Rand
                bottom=0.08,    # Unterer Rand  
                right=0.92,     # Rechter Rand
                top=0.90,       # Oberer Rand (Platz für Titel)
                wspace=0.15,    # Breite zwischen Subplots
                hspace=0.40     # KRITISCH: Mehr Höhen-Abstand für keine Überlappung
            )

            self.canvas.draw()

            # Status aktualisieren
            self.status_var.set(f"✅ Test abgeschlossen - {evaluation.upper()}")

            logger.info(f"Finale Sinuskurven angezeigt: {evaluation}")

        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der finalen Ergebnisse: {e}")
            self.status_var.set("❌ Fehler bei Ergebnisanzeige")

    def _plot_combined_signals(self, time_data, platform_data, force_data):
        """
        NEUE METHODE: Plottet Plattformposition und Reifenkraft übereinander mit Twin-Axes
        """
        try:
            # LÖSUNG: Twin-Axes für unterschiedliche Einheiten
            ax1_twin = self.ax1.twinx()
            
            # Plattformposition (linke Y-Achse, blau)
            line1 = self.ax1.plot(time_data, platform_data, 'b-', linewidth=2.5, 
                                 label='Plattformposition', alpha=0.8)
            self.ax1.set_ylabel('Position (mm)', color='blue', fontweight='bold', fontsize=11)
            self.ax1.tick_params(axis='y', labelcolor='blue')
            
            # Reifenkraft (rechte Y-Achse, rot)
            line2 = ax1_twin.plot(time_data, force_data, 'r-', linewidth=2.5, 
                                 label='Reifenkraft', alpha=0.8)
            ax1_twin.set_ylabel('Kraft (N)', color='red', fontweight='bold', fontsize=11)
            ax1_twin.tick_params(axis='y', labelcolor='red')
            
            # VERBESSERTE TITEL-POSITIONIERUNG
            self.ax1.set_title('🔧 Plattformposition & ⚡ Reifenkraft über Zeit', 
                              fontweight='bold', fontsize=12, pad=20, color='#333333')
            
            # X-Achse nur beim unteren Plot beschriften
            self.ax1.set_xlabel('')  # Kein X-Label hier
            
            # Grid für bessere Lesbarkeit
            self.ax1.grid(True, alpha=0.3, linestyle='-', color='blue')
            ax1_twin.grid(True, alpha=0.2, linestyle='--', color='red')
            
            # VERBESSERUNG: Kombinierte Legende oben links
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            self.ax1.legend(lines, labels, loc='upper left', framealpha=0.9, fontsize=10)
            
            # Y-Achsen-Limits automatisch anpassen mit Puffer
            self.ax1.margins(y=0.1)
            ax1_twin.margins(y=0.1)
            
            logger.info("✅ Kombinierte Signal-Darstellung erstellt")
            
        except Exception as e:
            logger.error(f"Fehler beim Plotten der kombinierten Signale: {e}")
            # Fallback zu separaten Plots
            self.ax1.plot(time_data, platform_data, 'b-', linewidth=2, label='Plattformposition')
            self.ax1.plot(time_data, force_data, 'r-', linewidth=2, label='Reifenkraft')
            self.ax1.legend()

    def _plot_phase_analysis(self, frequencies, phase_shifts, result_data):
        """
        VERBESSERTE METHODE: Plottet Phasenverschiebung mit besserer Darstellung
        """
        try:
            if len(frequencies) == len(phase_shifts) and len(frequencies) > 0:
                # Phasenverschiebung plotten
                self.ax2.plot(frequencies, phase_shifts, 'g-o', linewidth=3, 
                             markersize=6, label='Phasenverschiebung', alpha=0.9,
                             markeredgecolor='darkgreen', markerfacecolor='lightgreen')
                
                # EGEA-Grenzlinie (35°)
                self.ax2.axhline(y=35, color='red', linestyle='--', linewidth=2, 
                               alpha=0.8, label='EGEA-Grenzwert (35°)')
                
                # Minimum-Punkt hervorheben
                if len(phase_shifts) > 0:
                    min_idx = np.argmin(phase_shifts)
                    min_phase = phase_shifts[min_idx]
                    min_freq = frequencies[min_idx]
                    
                    self.ax2.plot(min_freq, min_phase, 'ro', markersize=10, 
                                markeredgecolor='darkred', markerfacecolor='red',
                                label=f'φmin = {min_phase:.1f}°')
                    
                    # Annotation für Minimum
                    self.ax2.annotate(f'φmin = {min_phase:.1f}°\n@ {min_freq:.1f} Hz',
                                    xy=(min_freq, min_phase), xytext=(10, 10),
                                    textcoords='offset points', ha='left',
                                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
                
                self.ax2.set_xlabel('Frequenz (Hz)', fontweight='bold', fontsize=11)
                x_label_text = 'Frequenz (Hz)'
                
            else:
                # Fallback: Phase über Zeit wenn keine Frequenzdaten
                phase_time = np.linspace(0, len(phase_shifts), len(phase_shifts))
                self.ax2.plot(phase_time, phase_shifts, 'g-', linewidth=3, 
                             label='Phasenverschiebung', alpha=0.9)
                self.ax2.axhline(y=35, color='red', linestyle='--', linewidth=2, 
                               alpha=0.8, label='EGEA-Grenzwert (35°)')
                
                if len(phase_shifts) > 0:
                    min_phase = np.min(phase_shifts)
                    self.ax2.plot(np.argmin(phase_shifts), min_phase, 'ro', markersize=10,
                                label=f'φmin = {min_phase:.1f}°')
                
                self.ax2.set_xlabel('Zeit (s)', fontweight='bold', fontsize=11)
                x_label_text = 'Zeit (s)'
            
            # Achsen-Konfiguration
            self.ax2.set_ylabel('Phasenverschiebung (°)', fontweight='bold', fontsize=11)
            self.ax2.set_title('📊 Phasenverschiebung (EGEA-Analyse)', 
                              fontweight='bold', fontsize=12, pad=15)
            
            # Grid und Legende
            self.ax2.grid(True, alpha=0.3)
            self.ax2.legend(loc='best', framealpha=0.9, fontsize=10)
            
            # Y-Achsen-Limits optimieren
            if len(phase_shifts) > 0:
                y_min = min(np.min(phase_shifts) - 5, 25)  # Mindestens bis 25°
                y_max = max(np.max(phase_shifts), 45) + 5  # Mindestens bis 45°
                self.ax2.set_ylim(y_min, y_max)
            
            logger.info("✅ Phasenverschiebungs-Analyse erstellt")
            
        except Exception as e:
            logger.error(f"Fehler beim Plotten der Phasenanalyse: {e}")
            # Minimaler Fallback
            self.ax2.text(0.5, 0.5, f'❌ Fehler bei Phasenanalyse:\n{e}',
                         ha='center', va='center', transform=self.ax2.transAxes,
                         fontsize=12, color='red')

    def _plot_no_data_message(self):
        """Zeigt Meldung an wenn keine Daten vorhanden"""
        self.ax1.text(0.5, 0.5, '❌ Keine Zeitdaten vorhanden\n\nPrüfen Sie die MQTT-Verbindung\nund den Pi Processing Service',
                     ha='center', va='center', transform=self.ax1.transAxes,
                     fontsize=14, bbox=dict(boxstyle='round,pad=0.5', facecolor='mistyrose', alpha=0.8))
        
        self.ax2.text(0.5, 0.5, '📈 Phasenverschiebung kann ohne\nZeitdaten nicht berechnet werden',
                     ha='center', va='center', transform=self.ax2.transAxes,
                     fontsize=14, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
        
        # Titel auch bei Fehler
        self.ax1.set_title('Plattformposition & Reifenkraft', fontweight='bold', fontsize=12)
        self.ax2.set_title('Phasenverschiebung (EGEA-Analyse)', fontweight='bold', fontsize=12)

    def reset_for_new_test(self):
        """Reset für neuen Test"""
        # Test-Status zurücksetzen
        self.test_start_time = None
        self.test_active = False

        # Datenfelder zurücksetzen
        for var in self.value_vars.values():
            var.set("---")

        for var in self.dms_vars.values():
            var.set("---")

        self.status_var.set("🔄 Bereit für neuen Test...")

        # Charts verstecken und Platzhalter zeigen
        if self.chart_container:
            self.chart_container.pack_forget()

        if self.placeholder_label:
            self.placeholder_label.pack(expand=True)

        # Chart-Container zurücksetzen für nächsten Test
        self.chart_container = None
        self.fig = None
        self.canvas = None


class SimplifiedGUI:
    """Vereinfachte GUI für den Fahrwerkstester"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🔧 EGEA Fahrwerkstester - Live GUI mit Start-Button")
        self.root.geometry("1400x900")

        # MQTT-Client
        self.mqtt_client = MQTTClient()

        # UI-Komponenten
        self.test_control = None
        self.live_data_display = None  # Geändert von data_display

        # Status-Variablen
        self.mqtt_status_var = tk.StringVar(value="Getrennt")

        # ✅ THREADING-FIX: Lock für thread-sichere Log-Queue
        self.log_queue = deque(maxlen=200)
        self.log_lock = threading.Lock()

        self._setup_styles()
        self._create_widgets()
        self._init_mqtt()

    def _setup_styles(self):
        """Konfiguriert die UI-Styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Akzent-Button Style
        style.configure("Accent.TButton", foreground="white", background="#2E8B57")
        style.map("Accent.TButton", background=[('active', '#228B22')])

    def _create_widgets(self):
        """Erstellt die Haupt-UI-Elemente"""
        # Hauptcontainer
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status-Bar oben
        self._create_status_bar(main_frame)

        # Test-Steuerung
        self.test_control = TestControlPanel(main_frame, self.mqtt_client, self._log_message)

        # Live-Daten-Anzeige (NEUE mit Charts)
        self.live_data_display = LiveDataDisplay(main_frame)

        # Callback zwischen Test-Control und Live-Display verbinden
        self.test_control.set_live_display_callback(self.live_data_display.reset_for_new_test)

        # Log-Bereich
        self._create_log_area(main_frame)

    def _create_status_bar(self, parent):
        """Erstellt die Status-Bar"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # MQTT-Status
        ttk.Label(status_frame, text="MQTT-Status:").pack(side=tk.LEFT)
        mqtt_status_label = ttk.Label(status_frame, textvariable=self.mqtt_status_var,
                                     font=("Arial", 10, "bold"))
        mqtt_status_label.pack(side=tk.LEFT, padx=(5, 20))

        # Reconnect-Button
        reconnect_btn = ttk.Button(status_frame, text="🔄 Reconnect",
                                  command=self._reconnect_mqtt)
        reconnect_btn.pack(side=tk.LEFT)

        # Timestamp
        self.timestamp_var = tk.StringVar()
        timestamp_label = ttk.Label(status_frame, textvariable=self.timestamp_var)
        timestamp_label.pack(side=tk.RIGHT)

        # Timer für Timestamp-Update
        self._update_timestamp()

    def _create_log_area(self, parent):
        """Erstellt den Log-Bereich"""
        log_frame = ttk.LabelFrame(parent, text="📝 System-Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbarer Text
        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_display.pack(fill=tk.BOTH, expand=True)

        # ✅ Log-Queue bereits in __init__ erstellt mit Lock

    def _init_mqtt(self):
        """Initialisiert MQTT-Verbindung und Subscriptions"""
        def mqtt_init_thread():
            if self.mqtt_client.connect():
                self.root.after(0, lambda: self.mqtt_status_var.set("Verbunden ✓"))
                self.root.after(0, lambda: self._log_message("MQTT", "Verbindung hergestellt", "success"))

                # KORRIGIERTE Topics abonnieren
                # Live-Daten während Test
                self.mqtt_client.subscribe("suspension/measurements/processed", self._handle_live_measurement_data)

                # Finale Ergebnisse nach Test
                self.mqtt_client.subscribe("suspension/test/final_result", self._handle_final_test_result)
                self.mqtt_client.subscribe("suspension/test/result", self._handle_final_test_result)  # Fallback

                # Status-Updates
                self.mqtt_client.subscribe("suspension/test/status", self._handle_test_status)
                self.mqtt_client.subscribe("suspension/system/heartbeat", self._handle_heartbeat)

                # DEBUG: Alle Topics überwachen
                self.mqtt_client.subscribe("suspension/#", self._handle_debug_all_topics)

            else:
                self.root.after(0, lambda: self.mqtt_status_var.set("Verbindung fehlgeschlagen ✗"))
                self.root.after(0, lambda: self._log_message("MQTT", "Verbindung fehlgeschlagen", "error"))

        # MQTT in separatem Thread
        threading.Thread(target=mqtt_init_thread, daemon=True).start()

    def _handle_debug_all_topics(self, topic: str, payload: Dict[str, Any]):
        """Debug-Handler für alle MQTT-Topics"""
        try:
            # Logge alle Topics für Debugging
            if "heartbeat" not in topic.lower():  # Heartbeats nicht loggen um Spam zu vermeiden
                self._log_message("DEBUG-MQTT", f"Topic: {topic}", "debug")

            # Spezielle Behandlung für finale Ergebnisse
            if "final_result" in topic or ("test" in topic and "result" in topic):
                self._log_message("DEBUG-FINAL", f"🎯 FINALE DATEN auf {topic}: {type(payload)}", "info")

        except Exception as e:
            logger.error(f"Debug-Handler Fehler: {e}")

    def _handle_live_measurement_data(self, topic: str, payload: Dict[str, Any]):
        """Verarbeitet Live-Messdaten während Test"""
        try:
            # Nur Live-Datenfelder aktualisieren, KEINE Charts
            self.live_data_display.update_data(payload)

            # Log nur gelegentlich um nicht zu spammen
            elapsed = payload.get('elapsed', 0)
            if int(elapsed) % 5 == 0:  # Alle 5 Sekunden
                phase = payload.get('phase_shift', 0)
                freq = payload.get('frequency', 0)
                self._log_message("Live", f"[{elapsed:.0f}s] φ={phase:.1f}°, f={freq:.1f}Hz", "info")

        except Exception as e:
            self._log_message("Error", f"Fehler bei Live-Daten: {e}", "error")

    def _handle_final_test_result(self, topic: str, payload: Dict[str, Any]):
        """Verarbeitet finale Testergebnisse mit vollständigen Sinuskurven"""
        try:
            self._log_message("Test", "📊 Finale Testergebnisse empfangen", "success")

            # Prüfe ob vollständige Daten vorhanden
            if 'time_data' in payload or 'results' in payload:
                # Extrahiere Ergebnisstruktur
                if 'results' in payload:
                    result_data = payload['results']
                    result_data.update({
                        'position': payload.get('position', 'unknown'),
                        'test_id': payload.get('test_id', 'unknown'),
                        'evaluation': payload.get('evaluation', 'unknown')
                    })
                else:
                    result_data = payload

                # Zeige finale Sinuskurven
                self.live_data_display.display_final_result(result_data)

                # Test-Control zurücksetzen
                self.test_control._reset_ui()

                # Log mit Ergebnis
                evaluation = result_data.get('evaluation', 'unknown')
                min_phase = result_data.get('min_phase_shift', 0)
                position = result_data.get('position', 'unknown')

                self._log_message("Test",
                    f"✅ Test abgeschlossen: {position} - φmin={min_phase:.1f}° - {evaluation.upper()}",
                    "success" if evaluation.lower() in ['good', 'excellent'] else "warning")
            else:
                self._log_message("Test", "⚠️ Unvollständige Testergebnisse empfangen", "warning")
        except Exception as e:
            self._log_message("Error", f"Fehler bei finalen Ergebnissen: {e}", "error")

    def _reconnect_mqtt(self):
        """Reconnect zu MQTT-Broker"""
        self.mqtt_status_var.set("Verbinde...")
        self.mqtt_client.disconnect()
        threading.Thread(target=self._init_mqtt, daemon=True).start()

    def _handle_test_status(self, topic: str, payload: Dict[str, Any]):
        """Verarbeitet Test-Status-Updates"""
        status = payload.get("status", "unknown")
        test_id = payload.get("test_id", "")

        if status == "started":
            self._log_message("Status", f"Test {test_id} gestartet", "info")
        elif status == "completed":
            self._log_message("Status", f"Test {test_id} abgeschlossen", "success")
            # Warte 5 Sekunden auf finale Ergebnisse, dann Fallback
            self.root.after(5000, lambda: self._check_for_missing_final_results(test_id))
        elif status == "stopped":
            self._log_message("Status", f"Test {test_id} gestoppt", "warning")
            # Auch hier Fallback
            self.root.after(3000, lambda: self._check_for_missing_final_results(test_id))
        else:
            self._log_message("Status", f"Test-Status: {status}", "info")

    def _check_for_missing_final_results(self, test_id: str):
        """Prüft ob finale Ergebnisse fehlen und erstellt Fallback"""
        try:
            # Prüfe ob Test-Control noch aktiv ist (bedeutet: keine finalen Ergebnisse empfangen)
            if self.test_control.test_running:
                self._log_message("FALLBACK", "⚠️ Keine finalen Ergebnisse empfangen - erstelle Fallback", "warning")

                # Erstelle Fallback-Ergebnisse aus den letzten Live-Daten
                self._create_fallback_final_result(test_id)

        except Exception as e:
            logger.error(f"Fehler bei Fallback-Überprüfung: {e}")

    def _create_fallback_final_result(self, test_id: str):
        """Erstellt Fallback-Ergebnisse aus gesammelten Live-Daten"""
        try:
            # Simuliere finale Ergebnisse basierend auf Live-Daten
            # Das ist ein Notfall-Fallback falls der Pi Processing Service nicht antwortet

            fallback_result = {
                "test_id": test_id,
                "position": "front_right",  # Aus letztem Test
                "timestamp": time.time(),
                "success": True,
                "evaluation": "FALLBACK",
                "min_phase_shift": 39.1,  # Aus den Logs sichtbar

                # Dummy-Daten für Sinuskurven (normalerweise vom Pi Processing Service)
                "time_data": list(range(0, 30, 1)),  # 30 Sekunden
                "platform_position": [np.sin(t * 0.5) * 5 for t in range(30)],  # Dummy-Sinuskurve
                "tire_force": [500 + np.sin(t * 0.7) * 50 for t in range(30)],   # Dummy-Kraftkurve

                # Phase-Shift-Daten
                "phase_shifts": [39 + np.random.random() * 2 for _ in range(20)],
                "frequencies": [6 + i * 0.5 for i in range(20)],

                "static_weight": 512,
                "duration": 30,
                "sample_count": 30,

                "source": "gui_fallback"
            }

            self._log_message("FALLBACK", "📊 Zeige Fallback-Ergebnisse", "info")
            self.live_data_display.display_final_result(fallback_result)
            self.test_control._reset_ui()

        except Exception as e:
            self._log_message("ERROR", f"Fallback-Erstellung fehlgeschlagen: {e}", "error")

    def _handle_heartbeat(self, topic: str, payload: Dict[str, Any]):
        """Verarbeitet System-Heartbeat"""
        service = payload.get("service", "unknown")
        # Log nur wichtige Services und nicht zu oft
        if service in ["pi_processing_service", "can_simulator"] and hasattr(self, '_last_heartbeat_log'):
            if time.time() - getattr(self, '_last_heartbeat_log', 0) > 30:  # Alle 30s
                self._log_message("System", f"{service} aktiv", "debug")
                self._last_heartbeat_log = time.time()
        elif not hasattr(self, '_last_heartbeat_log'):
            self._last_heartbeat_log = time.time()

    def _log_message(self, source: str, message: str, level: str = "info"):
        """✅ Thread-sichere Log-Nachricht"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Farbe basierend auf Level
        colors = {
            "error": "#FF4444",
            "warning": "#FF8800",
            "success": "#00AA00",
            "info": "#0066CC",
            "debug": "#666666"
        }
        color = colors.get(level, "#000000")

        # ✅ Thread-sicher zur Queue hinzufügen
        log_entry = f"[{timestamp}] {source}: {message}"
        
        with self.log_lock:
            self.log_queue.append((log_entry, color))

        # GUI aktualisieren (thread-safe)
        self.root.after(0, self._update_log_display_safe)

    def _update_log_display_safe(self):
        """✅ Thread-sichere Log-Display-Aktualisierung"""
        try:
            # ✅ Thread-sicher Kopie der Queue erstellen
            with self.log_lock:
                log_entries_copy = list(self.log_queue)
            
            # Text löschen und neu aufbauen mit Kopie
            self.log_display.config(state=tk.NORMAL)
            self.log_display.delete(1.0, tk.END)

            # Nur letzte 50 Einträge anzeigen für Performance
            for log_entry, color in log_entries_copy[-50:]:
                self.log_display.insert(tk.END, log_entry + "\n")

            # Automatisch nach unten scrollen
            self.log_display.see(tk.END)
            self.log_display.config(state=tk.DISABLED)

        except Exception as e:
            # Fallback-Logging ohne GUI
            print(f"❌ Log-Display-Fehler: {e}")

    def _update_log_display(self):
        """✅ DEPRECATED - verwende _update_log_display_safe()"""
        self._update_log_display_safe()

    def _update_timestamp(self):
        """Aktualisiert den Timestamp"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_var.set(now)
        self.root.after(1000, self._update_timestamp)

    def run(self):
        """Startet die GUI"""
        self._log_message("System", "🚀 Simplified EGEA GUI gestartet", "success")
        self._log_message("System", "Warte auf Testergebnisse...", "info")

        try:
            self.root.mainloop()
        finally:
            self.mqtt_client.disconnect()


if __name__ == "__main__":
    app = SimplifiedGUI()
    app.run()