"""
High-Level-Simulator für den Fahrwerkstester.

Dieser Simulator stellt direkt interpretierte Daten bereit, ohne den CAN-Bus
zu simulieren, was die Anwendungsentwicklung und Tests vereinfacht.
"""

import logging
import queue
import random
import threading
import time
from typing import Any, Callable, Dict

import numpy as np


# Dummy-Klasse zum Nachbilden der can.Message Schnittstelle bei Bedarf
class DummyMessage:
    """
    Ersatz für can.Message, um kompatibel mit bestehenden Callbacks zu sein.

    Enthält die interpretierten Daten in der Eigenschaft 'interpreted_data',
    während die standardmäßigen CAN-Eigenschaften mit Pseudo-Werten gefüllt sind.
    """

    def __init__(self, interpreted_data: Dict[str, Any]):
        # Standard-CAN-Nachrichteneigenschaften für Kompatibilität
        self.arbitration_id = 0x700  # Dummy-ID
        self.data = b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Dummy-Daten
        self.timestamp = time.time()
        self.is_extended_id = True
        self.dlc = 8

        # Hinzufügen der interpretierten Daten für High-Level-Zugriff
        self.interpreted_data = interpreted_data


class DataSimulator:
    """
    Stellt direkt interpretierte Daten für den Fahrwerkstester bereit.

    Diese Klasse implementiert die gleiche Schnittstelle wie andere CAN-Interfaces,
    arbeitet aber auf einer höheren Abstraktionsebene mit bereits interpretierten
    Daten statt mit rohen CAN-Frames.
    """

    def __init__(self):
        """Initialisiert den High-Level-Simulator."""
        self.vehicle_present = False
        self.test_running = False
        self.test_side = None
        self.test_method = "phase_shift"  # "phase_shift" oder "resonance"
        self.message_callbacks = []
        self.connected = True  # Immer verbunden im Simulationsmodus
        self.current_baudrate = 1000000  # Dummy-Baudrate
        self.message_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.receive_thread = None
        self.data_generator_thread = None

        # Parameter für die Fahrzeugsimulation
        self.vehicle_info = {
            "make": "VW",
            "model": "Golf",
            "year": random.randint(2010, 2024),
            "type": "M1",  # Personenkraftwagen
            "licence_plate": "AB-CD 123",
            "spring_constant": random.uniform(15000, 25000),  # N/m
            "damping_constant": random.uniform(1200, 1800),  # Ns/m
        }

        # Parameter für die Phasenverschiebungs-Simulation
        self.damping_quality = random.choice(["good", "bad", "marginal"])
        if self.damping_quality == "good":
            self.phase_shift_value = random.uniform(45, 55)  # Grad
        elif self.damping_quality == "marginal":
            self.phase_shift_value = random.uniform(33, 38)  # Grad
        else:  # bad
            self.phase_shift_value = random.uniform(20, 30)  # Grad

        # Logger konfigurieren
        self.logger = logging.getLogger(__name__)
        self.logger.info("High-Level-Simulator initialisiert")

        # Empfangs-Thread starten
        self.start_receiver()

    def connect(self, baudrate=None):
        """
        Simuliert eine Verbindung zum CAN-Bus.

        Args:
                baudrate: Ignoriert, nur für Kompatibilität

        Returns:
                bool: Immer True, da die Verbindung im Simulationsmodus immer gelingt
        """
        self.connected = True
        self.logger.info("High-Level-Simulator verbunden")
        return True

    def send_message(self, arbitration_id, data, is_extended_id=False, **kwargs):
        """
        Verarbeitet eine CAN-Nachricht und löst entsprechende Simulationsaktionen aus.

        Diese Methode interpretiert die gesendete Nachricht als Steuerbefehl und
        löst entsprechende Simulationsaktionen aus (z.B. Starten/Stoppen eines Tests).

        Args:
                arbitration_id: CAN-ID des Steuerbefehls
                data: Daten des Steuerbefehls
                is_extended_id: Wird ignoriert
                **kwargs: Weitere Parameter werden ignoriert

        Returns:
                bool: True bei erfolgreicher Verarbeitung
        """
        # Motor-Steuerbefehl (EUSAMA) oder ALIVE-Nachricht (ASA) simulieren
        if arbitration_id == 0x08AAAA71:  # EUSAMA Motor Control
            motor_mask = data[0] if hasattr(data, "__getitem__") else 0
            runtime = data[1] if len(data) > 1 else 0

            if motor_mask == 0:  # Stop
                self.stop_test()
            elif motor_mask & 0x01:  # Linker Motor
                self.start_test("left", runtime)
            elif motor_mask & 0x02:  # Rechter Motor
                self.start_test("right", runtime)

            return True

        # Andere Befehle verarbeiten, falls nötig
        return True

    def recv_message(self, timeout=0.1):
        """
        Empfängt eine simulierte Nachricht, aber keine leeren Dummy-Messages.

        Args:
                timeout: Wartezeit in Sekunden

        Returns:
                DummyMessage: Empfangene Nachricht oder None bei Timeout
        """
        try:
            # Low-Level CAN-Messages haben Vorrang
            if hasattr(self, "generate_low_level") and self.generate_low_level:
                try:
                    msg = self.low_level_queue.get(block=True, timeout=timeout)
                    # Prüfe ob es eine echte Nachricht ist
                    if msg and (msg.arbitration_id != 0x700 or any(b != 0 for b in msg.data)):
                        return msg
                except queue.Empty:
                    pass

            # High-Level-Messages nur wenn sie Inhalt haben
            msg = super().recv_message(timeout)
            if msg and hasattr(msg, "interpreted_data") and msg.interpreted_data:
                return msg

            return None  # Keine valide Nachricht verfügbar

        except Exception as e:
            self.logger.error(f"Fehler beim Empfangen einer Nachricht: {e}")
            return None

    def add_message_callback(self, callback: Callable):
        """
        Fügt einen Callback für empfangene Nachrichten hinzu.

        Args:
                callback: Funktion, die für jede Nachricht aufgerufen wird
        """
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)

    def remove_message_callback(self, callback: Callable):
        """
        Entfernt einen Callback.

        Args:
                callback: Zu entfernender Callback
        """
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)

    def shutdown(self):
        """Fährt den Simulator herunter und gibt Ressourcen frei."""
        self.stop_event.set()
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)
        if self.data_generator_thread and self.data_generator_thread.is_alive():
            self.data_generator_thread.join(timeout=2)
        self.connected = False
        self.logger.info("High-Level-Simulator heruntergefahren")

    # --- Simulationsspezifische Methoden ---

    def set_vehicle_present(self, present: bool):
        """
        Simuliert das Auf-/Abfahren eines Fahrzeugs.

        Args:
                present: True wenn ein Fahrzeug vorhanden sein soll
        """
        self.vehicle_present = present
        if present:
            # Fahrzeug mit zufälligen Gewichten simulieren
            base_weight = random.uniform(300, 450)  # kg pro Ecke
            weights = {
                "front_left": base_weight * random.uniform(0.9, 1.1),
                "front_right": base_weight * random.uniform(0.9, 1.1),
                "rear_left": base_weight * 0.8 * random.uniform(0.9, 1.1),
                "rear_right": base_weight * 0.8 * random.uniform(0.9, 1.1),
            }

            data = {
                "event": "vehicle_detected",
                "weights": weights,
                "timestamp": time.time(),
                "vehicle_info": self.vehicle_info,
            }

            self.logger.info(f"Fahrzeug erkannt: Gesamtgewicht={sum(weights.values()):.1f}kg")
        else:
            # Kein Fahrzeug (leere Plattform)
            data = {
                "event": "vehicle_exited",
                "weights": {
                    "front_left": random.uniform(0, 10),
                    "front_right": random.uniform(0, 10),
                    "rear_left": random.uniform(0, 10),
                    "rear_right": random.uniform(0, 10),
                },
                "timestamp": time.time(),
            }
            self.logger.info("Fahrzeug hat Plattform verlassen")

        # Nachricht erzeugen und verarbeiten
        message = DummyMessage(interpreted_data=data)
        self._process_message(message)

    def start_test(self, side, runtime_seconds=30):
        """
        Startet einen Test für die angegebene Seite.

        Args:
            side: "left", "right" oder "both"
            runtime_seconds: Laufzeit des Tests in Sekunden
        """
        # Logging hinzufügen für verbesserte Diagnostik
        self.logger.info(
            f"start_test aufgerufen für Seite '{side}' mit Laufzeit {runtime_seconds}s"
        )

        # Wichtig: Teste, ob test_running bereits gesetzt ist
        if self.test_running:
            self.logger.warning("Test läuft bereits, stoppe vorherigen Test")
            self.stop_test()

        # Sicherstellen, dass running und test_running beide gesetzt sind
        self.running = True  # <-- Prüfen, ob dieser Wert richtig gesetzt ist
        self.test_running = True

        # Testseite und -dauer speichern
        self.test_side = side
        self.test_runtime = runtime_seconds

        # Thread für Testdatengenerierung starten
        # WICHTIG: Stelle sicher, dass der Thread als Daemon-Thread läuft und nicht blockiert
        test_thread = threading.Thread(
            target=self._generate_test_data, args=(side, runtime_seconds), daemon=True
        )
        test_thread.start()

        # Zusätzliches Logging nach dem Thread-Start
        self.logger.info(f"Testdaten-Thread gestartet für {side}")

        # Motorstatusnachricht simulieren (wichtig für GUI-Feedback)
        motor_mask = 0x01 if side == "left" else 0x02
        if side == "both":
            motor_mask = 0x03

        return True

    def stop_test(self):
        """Stoppt einen laufenden Test und alle zugehörigen Threads."""
        if not self.test_running:
            self.logger.info("Test läuft nicht, nichts zu stoppen")
            return

        # Test als gestoppt markieren
        self.test_running = False

        # Generator-Thread stoppen
        if hasattr(self, "stop_generator"):
            self.stop_generator.set()

        # Warten bis Generator-Thread beendet ist
        if (
            hasattr(self, "generator_thread")
            and self.generator_thread
            and self.generator_thread.is_alive()
        ):
            self.generator_thread.join(timeout=2.0)
            if self.generator_thread.is_alive():
                self.logger.warning("Generator-Thread konnte nicht gestoppt werden")

        # WICHTIG: Message-Queue leeren nach Testende
        try:
            while not self.message_queue.empty():
                self.message_queue.get_nowait()
        except queue.Empty:
            pass

        # Teststopp-Nachricht nur EINMAL senden
        data = {
            "event": "test_stopped",
            "side": self.test_side,
            "method": self.test_method,
            "timestamp": time.time(),
        }
        message = DummyMessage(interpreted_data=data)
        self._process_message(message)

        self.logger.info("Test gestoppt - alle Threads beendet")

    def set_test_method(self, method):
        """
        Setzt die Testmethode.

        Args:
                method: "phase_shift" oder "resonance"
        """
        if method in ["phase_shift", "resonance"]:
            self.test_method = method
            self.logger.info(f"Testmethode geändert: {method}")
        else:
            self.logger.warning(f"Ungültige Testmethode: {method}")

    def set_damping_quality(self, quality):
        """
        Setzt die Dämpfungsqualität für die Simulation.

        Args:
                quality: "good", "marginal" oder "bad"
        """
        if quality not in ["good", "marginal", "bad"]:
            self.logger.warning(f"Ungültige Dämpfungsqualität: {quality}")
            return

        self.damping_quality = quality

        # Phasenverschiebungswerte entsprechend anpassen
        if quality == "good":
            self.phase_shift_value = random.uniform(45, 55)  # Grad
        elif quality == "marginal":
            self.phase_shift_value = random.uniform(33, 38)  # Grad
        else:  # bad
            self.phase_shift_value = random.uniform(20, 30)  # Grad

        self.logger.info(f"Dämpfungsqualität geändert: {quality} (φ={self.phase_shift_value:.1f}°)")

    # --- Interne Hilfsmethoden ---

    def start_receiver(self):
        """Startet den Empfangs-Thread."""
        self.stop_event.clear()
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()

    def _receive_loop(self):
        """Interne Empfangsschleife für Callbacks."""
        while not self.stop_event.is_set() and self.connected:
            try:
                # NUR verarbeiten wenn Test tatsächlich läuft
                if not self.test_running:
                    time.sleep(0.1)  # Kurze Pause wenn kein Test läuft
                    continue

                msg = self.recv_message(timeout=0.1)
                if msg:
                    # Prüfen ob es eine echte Nachricht mit Inhalt ist
                    if hasattr(msg, "interpreted_data") and msg.interpreted_data:
                        for callback in self.message_callbacks:
                            try:
                                callback(msg)
                            except Exception as e:
                                self.logger.error(f"Fehler im Nachricht-Callback: {e}")
                    # Leere Dummy-Messages NICHT weiterleiten
                    elif msg.arbitration_id == 0x700 and all(b == 0 for b in msg.data):
                        continue  # Ignoriere leere Dummy-Messages
                    else:
                        # Echte CAN-Messages weiterleiten
                        for callback in self.message_callbacks:
                            try:
                                callback(msg)
                            except Exception as e:
                                self.logger.error(f"Fehler im Nachricht-Callback: {e}")
            except Exception as e:
                self.logger.error(f"Fehler in der Empfangsschleife: {e}")
                time.sleep(0.1)

    def _process_message(self, message):
        """
        Verarbeitet eine Nachricht und leitet sie weiter.

        Args:
                message: Zu verarbeitende Nachricht (DummyMessage oder can.Message)
        """
        # In Queue stellen für recv_message
        self.message_queue.put(message)

        # Direkt an alle Callbacks senden
        for callback in self.message_callbacks:
            try:
                callback(message)
            except Exception as e:
                self.logger.error(f"Fehler im Callback: {e}")

    def _generate_test_data(self, side, runtime):
        """Generiert Testdaten für einen laufenden Test."""
        self.logger.info(f"_generate_test_data aufgerufen für Seite {side}, Laufzeit {runtime}s")

        try:
            # ... Testdaten-Generierung ...

            # Nach Abschluss: NUR EINMAL Ergebnis senden, dann STOPPEN
            if not self.stop_generator.is_set() and self.test_running:
                self._send_test_results(side)

                # Test-Completion EINMAL senden
                completion_data = {
                    "event": "test_completed",
                    "side": side,
                    "method": "phase_shift",
                    "timestamp": time.time(),
                    "min_phase_shift": self.current_min_phase,
                    "min_phase_freq": self.min_phase_frequency,
                    "duration": runtime,
                }
                message = DummyMessage(interpreted_data=completion_data)
                self._process_message(message)

                # Test als beendet markieren
                self.test_running = False

                # Generator stoppen
                self.stop_generator.set()

                self.logger.info(
                    f"Phase-Shift-Test für {side} VOLLSTÄNDIG abgeschlossen - Generator gestoppt"
                )

        except Exception as e:
            self.logger.error(f"Fehler bei der Datengenerierung: {e}")
            self.test_running = False
            self.stop_generator.set()

    def _generate_phase_shift_data(self, side, runtime, start_time, sample_interval):
        """
        Generiert Daten für einen Phase-Shift-Test.

        Args:
                side: Getestete Seite
                runtime: Laufzeit in Sekunden
                start_time: Startzeit des Tests
                sample_interval: Zeit zwischen Datenpunkten
        """
        """
            Generiert Daten für einen Phase-Shift-Test mit realistischem Frequenzsweep.
            """
        # Zusätzliches Debug-Logging
        self.logger.info(
            f"_generate_phase_shift_data aufgerufen: side={side}, runtime={runtime}, start_time={start_time}"
        )

        # Parameter für den Frequenzsweep (EGEA-konform)
        freq_start = 25.0  # Hz - Startfrequenz
        freq_end = 6.0  # Hz - Endfrequenz
        platform_amplitude = 3.0  # mm - Standardamplitude der Plattform

        # Debug-Info ausgeben
        self.logger.info(f"Starte Frequenzsweep {freq_start}Hz → {freq_end}Hz über {runtime}s")

        # Ausgangsfrequenz und -amplitude
        freq_start = 25.0  # Hz
        freq_end = 6.0  # Hz
        amplitude = 3.0  # mm (Plattformamplitude)

        # Simuliere Frequenzsweep von hoch nach niedrig
        elapsed = 0
        n_samples = int(runtime / sample_interval)

        while elapsed < runtime and self.test_running:
            # Aktuelle Frequenz berechnen (linearer Sweep)
            progress = elapsed / runtime
            current_freq = freq_start - progress * (freq_start - freq_end)

            # Zeit für den aktuellen Datenpunkt
            t = elapsed

            # Plattformbewegung simulieren (Sinuswelle)
            platform_pos = amplitude * np.sin(2 * np.pi * current_freq * t)

            # Reifenkraft simulieren (mit Phasenverschiebung)
            phase_rad = np.radians(self.phase_shift_value)
            force_amplitude = 500 + 300 * (
                1.0 - (current_freq - 6.0) / 20.0
            )  # Höhere Amplitude bei Resonanz
            tire_force = force_amplitude * np.sin(2 * np.pi * current_freq * t - phase_rad)

            # Test-Daten-Nachricht
            data = {
                "event": "test_data",
                "type": "phase_shift",
                "side": side,
                "timestamp": time.time(),
                "elapsed": elapsed,
                "frequency": current_freq,
                "platform_position": platform_pos,
                "tire_force": tire_force,
                "static_weight": 400.0,  # Konstantes Gewicht als Referenz
                "phase_shift": self.phase_shift_value,
            }

            # Als Nachricht versenden
            message = DummyMessage(interpreted_data=data)
            self._process_message(message)

            # Fortschritt
            elapsed += sample_interval

            # Warten bis zum nächsten Sample
            next_sample_time = start_time + elapsed
            sleep_time = max(0, next_sample_time - time.time())
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _generate_resonance_data(self, side, runtime, start_time, sample_interval):
        """
        Generiert Daten für einen Resonanztest.

        Args:
                side: Getestete Seite
                runtime: Laufzeit in Sekunden
                start_time: Startzeit des Tests
                sample_interval: Zeit zwischen Datenpunkten
        """
        # Parameter für die Ausschwingkurve
        natural_freq = 1.5  # Hz (Eigenfrequenz)
        damping_ratio = 0.2 if self.damping_quality == "good" else 0.1  # Dämpfungsverhältnis
        initial_amplitude = 10.0  # mm

        # Simuliere Ausschwingvorgang
        elapsed = 0

        while elapsed < runtime and self.test_running:
            # Zeit für den aktuellen Datenpunkt
            t = elapsed

            # Gedämpfte Schwingung simulieren
            damped_factor = np.exp(-damping_ratio * 2 * np.pi * natural_freq * t)
            oscillation = initial_amplitude * damped_factor * np.cos(2 * np.pi * natural_freq * t)

            # Test-Daten-Nachricht
            data = {
                "event": "test_data",
                "type": "resonance",
                "side": side,
                "timestamp": time.time(),
                "elapsed": elapsed,
                "oscillation": oscillation,
                "damping_ratio": damping_ratio,
                "natural_frequency": natural_freq,
            }

            # Als Nachricht versenden
            message = DummyMessage(interpreted_data=data)
            self._process_message(message)

            # Fortschritt
            elapsed += sample_interval

            # Warten bis zum nächsten Sample
            next_sample_time = start_time + elapsed
            sleep_time = max(0, next_sample_time - time.time())
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _send_test_result(self, side):
        """
        Sendet das Testergebnis nach Abschluss eines Tests.

        Args:
                side: Getestete Seite
        """
        # Minimale Phasenverschiebung und andere Ergebnisdaten
        if self.test_method == "phase_shift":
            # Leichte Variation um den konfigurierten Wert
            min_phase = self.phase_shift_value * random.uniform(0.95, 1.05)

            # Ergebnis berechnen
            result = {
                "event": "test_result",
                "type": "phase_shift",
                "side": side,
                "timestamp": time.time(),
                "min_phase_shift": min_phase,
                "min_phase_freq": random.uniform(12, 14),  # Hz
                "static_weight": 400.0,
                "rigidity": random.uniform(160, 400)
                if self.damping_quality != "bad"
                else random.uniform(80, 150),
                "damping_ratio": min_phase / 90.0,  # Vereinfachte Berechnung
                "pass": min_phase >= 35.0,  # EGEA-Kriterium: φmin ≥ 35°
                "quality": self.damping_quality,
            }
        else:  # resonance
            effectiveness = (
                80.0
                if self.damping_quality == "good"
                else 60.0
                if self.damping_quality == "marginal"
                else 40.0
            )

            result = {
                "event": "test_result",
                "type": "resonance",
                "side": side,
                "timestamp": time.time(),
                "effectiveness": effectiveness,
                "amplitude": random.uniform(5, 15),  # mm
                "weight": 400.0,
                "natural_frequency": 1.5,  # Hz
                "damping_ratio": 0.2 if self.damping_quality == "good" else 0.1,
                "pass": effectiveness >= 65.0,  # Bestandsgrenze
                "quality": self.damping_quality,
            }

        # Als Nachricht versenden
        message = DummyMessage(interpreted_data=result)
        self._process_message(message)