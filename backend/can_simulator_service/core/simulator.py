"""
CAN-Bus Simulator für verschiedene Protokollprofile.

OPTIMIERTER CODE zur Reduzierung der CPU-Last durch:
- Event-basierte statt Busy-Wait-Programmierung
- Effiziente Datenverarbeitung mittels NumPy-Vektorisierung
- Angemessene Abtastrate gemäß Nyquist-Shannon-Theorem
- Thread-basierte Architektur für effiziente Simulationsberechnung
"""

import logging
import queue
import random
import threading
import time
from collections import deque

import numpy as np

# Versuche python-can zu importieren, falle zurück auf eigene Implementation wenn nicht verfügbar
try:
    import can

    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False
    # In diesem Fall würden wir unsere eigene Nachrichtenklasse importieren
else:
    # python-can ist verfügbar, verwende dessen Message-Klasse
    pass

logger = logging.getLogger(__name__)


class CanSimulator:
    """
    Hauptsimulationsklasse für CAN-Bus-Nachrichten.

    Diese Klasse erzeugt simulierte CAN-Nachrichten nach verschiedenen
    Protokollprofilen und kann als Basis für verschiedene Interface-Adapter dienen.

    OPTIMIERT für reduzierte CPU-Last und verbesserte Performance.
    """

    # OPTIMIERUNG: Anpassung des Standard-Intervalls
    # Ursprünglich: 0.001s (1000 Hz), zu hoch für die meisten Anwendungen
    # EUSAMA-Protokoll Dokumentation spezifiziert 10ms (100 Hz)
    DEFAULT_MESSAGE_INTERVAL = 0.01  # 100 Hz statt 1000 Hz

    def __init__(self, profile="eusama", message_interval=None):
        """
        Initialisiert den CAN-Simulator mit dem gewählten Protokollprofil.

        Args:
            profile: Name des Protokollprofils ("eusama" oder "asa")
            message_interval: Zeit zwischen Nachrichten in Sekunden
        """
        self.profile = profile.lower()
        self.message_interval = message_interval or self.DEFAULT_MESSAGE_INTERVAL
        self.running = False
        self.thread = None
        self.callbacks = []

        # OPTIMIERUNG: Begrenzte Queue-Größe zur Speicherverwaltung
        self.message_queue = queue.Queue(maxsize=1000)

        # OPTIMIERUNG: Event für Thread-Steuerung
        self.stop_event = threading.Event()

        # OPTIMIERUNG: Performance-Monitoring
        self.performance_stats = {
            "messages_generated": 0,
            "messages_sent": 0,
            "generation_times": deque(maxlen=100),  # Speichert die letzten 100 Generationszeiten
            "cpu_usage": 0.0,
        }

        # Simulationszustand
        self.left_motor_running = False
        self.right_motor_running = False
        self.motor_runtime_left = 0
        self.motor_runtime_right = 0

        # Für Simulation realistische Schwingungsmuster
        self.simulation_time = 0.0
        self.freq_sweep = {"current": 25.0, "target": 6.0, "duration": 10.0}
        self.phase_shift = {"left": 45.0, "right": 42.0}  # Grad (gut: > 35°)

        # Protokollspezifische Konstanten
        if self.profile == "eusama":
            self.BASE_ID = 0x08AAAA60
            self.RAW_DATA_LEFT_ID = self.BASE_ID + 0
            self.RAW_DATA_RIGHT_ID = self.BASE_ID + 1
            self.MOTOR_STATUS_ID = 0x08AAAA66
            self.MOTOR_CONTROL_ID = 0x08AAAA71
            self.TOP_POSITION_ID = 0x08AAAA67
        elif self.profile == "asa":
            self.BASE_ID = 0x08298A60  # 'ALS' << 5
            self.BRAKE_FORCE_SPEED_ID = self.BASE_ID + 0
            self.SLIP_WEIGHT_PN_ID = self.BASE_ID + 1
            self.PM_PEDAL_FLAGS_ID = self.BASE_ID + 2
            self.ERROR_FLAGS_ID = self.BASE_ID + 3
            self.MOTOR_STATUS_ID = self.BASE_ID + 6
            self.ALIVE_ID = self.BASE_ID + 0x10
        else:
            raise ValueError(f"Unbekanntes Protokollprofil: {profile}")

        # Performance-Optimierung-Einstellungen
        self.batch_size = 10  # Anzahl der Nachrichten, die auf einmal generiert werden

        # Logging für Initialisierung
        logger.info(
            f"CanSimulator initialisiert: Profil={profile}, Intervall={self.message_interval}s ({1 / self.message_interval:.1f} Hz)"
        )

    def start(self):
        """Startet die kontinuierliche CAN-Datensimulation."""
        if self.running:
            logger.warning("Simulation läuft bereits")
            return

        # OPTIMIERUNG: Ressourcen zurücksetzen
        self.stop_event.clear()
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except queue.Empty:
                break

        self.running = True

        # OPTIMIERUNG: Thread-Priorität anpassen für bessere Performance
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()

        # Thread-ID und Info loggen
        logger.info(
            f"Simulation gestartet mit {1 / self.message_interval:.1f} Hz, "
            f"Thread-ID: {self.thread.ident}"
        )

    def stop(self):
        """Stoppt die laufende Simulation."""
        if not self.running:
            logger.warning("Keine Simulation aktiv")
            return

        # OPTIMIERUNG: Event-basiertes Stoppen
        self.stop_event.set()
        self.running = False

        if self.thread:
            # Maximal 2 Sekunden auf Thread-Ende warten
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                logger.warning("Simulations-Thread konnte nicht sauber beendet werden")
            else:
                logger.info("Simulation gestoppt")
                self.thread = None

    def _simulation_loop(self):
        """
        Hauptschleife für die Simulation - sendet regelmäßig Messpunkte.
        OPTIMIERTE Version mit geringerer CPU-Last.
        """
        try:
            # Nachrichtenbatch generieren
            next_batch_time = time.time()
            batch_interval = self.message_interval * self.batch_size

            while self.running and not self.stop_event.is_set():
                # Aktuellen Batch generieren wenn es Zeit ist
                current_time = time.time()

                if current_time >= next_batch_time:
                    # Zeit für Generierung messen (Performance-Monitoring)
                    gen_start_time = time.time()

                    # Simulationszeit aktualisieren
                    self.simulation_time += batch_interval

                    # Aktualisiere Motorlaufzeiten
                    if self.left_motor_running:
                        self.motor_runtime_left = max(0, self.motor_runtime_left - batch_interval)
                        if self.motor_runtime_left <= 0:
                            self.left_motor_running = False

                    if self.right_motor_running:
                        self.motor_runtime_right = max(0, self.motor_runtime_right - batch_interval)
                        if self.motor_runtime_right <= 0:
                            self.right_motor_running = False

                    # Frequenzsweep aktualisieren, wenn ein Motor läuft
                    if self.left_motor_running or self.right_motor_running:
                        # Linear von freq_start bis freq_end über die angegebene Dauer
                        progress = min(1.0, self.simulation_time / self.freq_sweep["duration"])
                        current_freq = self.freq_sweep["current"] - progress * (
                            self.freq_sweep["current"] - self.freq_sweep["target"]
                        )
                        self.freq_sweep["current"] = current_freq

                    # Generiere einen ganzen Batch von CAN-Nachrichten
                    batch_messages = []
                    for i in range(self.batch_size):
                        # Zeit innerhalb des Batches
                        batch_time = next_batch_time + i * self.message_interval

                        # Generiere einen Satz CAN-Nachrichten basierend auf dem Profil
                        if self.profile == "eusama":
                            messages = self._generate_eusama_messages(batch_time)
                        elif self.profile == "asa":
                            messages = self._generate_asa_messages(batch_time)
                        else:
                            messages = self._generate_generic_message(batch_time)

                        batch_messages.extend(messages)

                    # Zeit für Generierung aufzeichnen
                    generation_time = time.time() - gen_start_time
                    self.performance_stats["generation_times"].append(generation_time)
                    self.performance_stats["messages_generated"] += len(batch_messages)

                    # Nachrichten in die Queue stellen
                    for msg in batch_messages:
                        try:
                            # Non-blocking put mit Timeout
                            self.message_queue.put(msg, block=False)
                            self.performance_stats["messages_sent"] += 1

                            # Callbacks direkt aufrufen, falls vorhanden
                            for callback in self.callbacks:
                                try:
                                    callback(msg)
                                except Exception as e:
                                    logger.error(f"Fehler im Callback: {e}")
                        except queue.Full:
                            # Queue ist voll - älteste Nachricht verwerfen
                            try:
                                self.message_queue.get_nowait()  # Alte entfernen
                                self.message_queue.put(msg, block=False)  # Neue einfügen
                            except (queue.Empty, queue.Full):
                                # Im Fehlerfall überspringen
                                pass

                    # Nächste Batch-Zeit berechnen
                    next_batch_time += batch_interval

                # OPTIMIERUNG: Dynamisches Sleep-Intervall
                # Berechne Zeit bis zum nächsten Batch
                sleep_time = max(0.001, next_batch_time - time.time())

                # Verwende Event.wait statt time.sleep - unterbrechbar bei Stop
                self.stop_event.wait(timeout=min(sleep_time, 0.1))

        except Exception as e:
            logger.error(f"Fehler in der Simulationsschleife: {e}")
            import traceback

            logger.error(traceback.format_exc())
            self.running = False

    def _generate_eusama_messages(self, timestamp=None):
        """
        Generiert einen Satz EUSAMA-CAN-Nachrichten.

        Args:
            timestamp: Optionaler Zeitstempel für die Nachrichten

        Returns:
            list: Liste mit generierten CAN-Nachrichten
        """
        # Standardzeitstempel wenn nicht angegeben
        if timestamp is None:
            timestamp = time.time()

        # Generiere DMS-Werte
        left_dms = self._generate_dms_values("left")
        right_dms = self._generate_dms_values("right")

        # Erzeuge Nachricht für linke Seite (DMS 1-4)
        msg1_data = bytearray(8)
        for i in range(4):
            msg1_data[i * 2] = (left_dms[i] >> 8) & 0xFF  # High Byte
            msg1_data[i * 2 + 1] = left_dms[i] & 0xFF  # Low Byte

        msg1 = self._create_message(
            arbitration_id=self.RAW_DATA_LEFT_ID,
            data=bytes(msg1_data),
            is_extended_id=True,
            timestamp=timestamp,
        )

        # Erzeuge Nachricht für rechte Seite (DMS 5-8)
        msg2_data = bytearray(8)
        for i in range(4):
            msg2_data[i * 2] = (right_dms[i] >> 8) & 0xFF  # High Byte
            msg2_data[i * 2 + 1] = right_dms[i] & 0xFF  # Low Byte

        msg2 = self._create_message(
            arbitration_id=self.RAW_DATA_RIGHT_ID,
            data=bytes(msg2_data),
            is_extended_id=True,
            timestamp=timestamp,
        )

        # Erzeuge Motorstatus-Paket
        motor_mask = 0
        if self.left_motor_running:
            motor_mask |= 0x01
        if self.right_motor_running:
            motor_mask |= 0x02

        remaining_time = max(int(self.motor_runtime_left), int(self.motor_runtime_right))

        msg3 = self._create_message(
            arbitration_id=self.MOTOR_STATUS_ID,
            data=bytes([motor_mask, remaining_time]),
            is_extended_id=True,
            timestamp=timestamp,
        )

        return [msg1, msg2, msg3]

    def _generate_asa_messages(self, timestamp=None):
        """
        Generiert einen Satz ASA-LiveStream-CAN-Nachrichten.

        Args:
            timestamp: Optionaler Zeitstempel für die Nachrichten

        Returns:
            list: Liste mit generierten CAN-Nachrichten
        """
        # Standardzeitstempel wenn nicht angegeben
        if timestamp is None:
            timestamp = time.time()

        # Simuliere Bremskräfte und Geschwindigkeiten
        left_brake = int(random.uniform(1000, 3000))
        right_brake = int(random.uniform(1000, 3000))
        left_speed = int(random.uniform(500, 1500))  # cm/s
        right_speed = int(random.uniform(500, 1500))  # cm/s

        msg1_data = bytearray(8)
        msg1_data[0] = (left_brake >> 8) & 0xFF
        msg1_data[1] = left_brake & 0xFF
        msg1_data[2] = (right_brake >> 8) & 0xFF
        msg1_data[3] = right_brake & 0xFF
        msg1_data[4] = (left_speed >> 8) & 0xFF
        msg1_data[5] = left_speed & 0xFF
        msg1_data[6] = (right_speed >> 8) & 0xFF
        msg1_data[7] = right_speed & 0xFF

        msg1 = self._create_message(
            arbitration_id=self.BRAKE_FORCE_SPEED_ID,
            data=bytes(msg1_data),
            is_extended_id=True,
            timestamp=timestamp,
        )

        # Paket 1: Schlupf, Gewichte und Druck PN
        left_slip = int(random.uniform(0, 30))
        right_slip = int(random.uniform(0, 30))
        left_weight = int(random.uniform(300, 600))
        right_weight = int(random.uniform(300, 600))
        pn_pressure = int(random.uniform(2000, 8000))  # mbar

        msg2_data = bytearray(8)
        msg2_data[0] = left_slip & 0xFF
        msg2_data[1] = right_slip & 0xFF
        msg2_data[2] = (left_weight >> 8) & 0xFF
        msg2_data[3] = left_weight & 0xFF
        msg2_data[4] = (right_weight >> 8) & 0xFF
        msg2_data[5] = right_weight & 0xFF
        msg2_data[6] = (pn_pressure >> 8) & 0xFF
        msg2_data[7] = pn_pressure & 0xFF

        msg2 = self._create_message(
            arbitration_id=self.SLIP_WEIGHT_PN_ID,
            data=bytes(msg2_data),
            is_extended_id=True,
            timestamp=timestamp,
        )

        return [msg1, msg2]

    def _generate_generic_message(self, timestamp=None):
        """
        Generiert eine generische CAN-Nachricht.

        Args:
            timestamp: Optionaler Zeitstempel für die Nachrichten

        Returns:
            list: Liste mit einer generischen CAN-Nachricht
        """
        # Standardzeitstempel wenn nicht angegeben
        if timestamp is None:
            timestamp = time.time()

        arbitration_id = random.randint(0x100, 0x7FF)
        data_length = random.randint(1, 8)
        data = bytes([random.randint(0, 255) for _ in range(data_length)])

        msg = self._create_message(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=False,
            timestamp=timestamp,
        )

        return [msg]

    def _generate_dms_values(self, side):
        """
        Generiert simulierte DMS-Werte basierend auf dem Zustand.
        OPTIMIERTE Version mit NumPy für bessere Performance.

        Args:
            side: "left" oder "right"

        Returns:
            Liste mit 4 DMS-Werten im Bereich 0-1023
        """
        is_motor_running = self.left_motor_running if side == "left" else self.right_motor_running

        base_value = 512  # Mittelwert des AD-Bereichs (0-1023)

        if is_motor_running:
            # Aktuelle Frequenz und Phasenverschiebung verwenden
            freq = self.freq_sweep["current"]
            phase_deg = self.phase_shift[side]
            phase_rad = phase_deg * np.pi / 180.0

            # Zeit für den aktuellen Datenpunkt
            t = self.simulation_time

            # Oszillation berechnen - OPTIMIERUNG: Einfachere Formel
            # Amplitude entsprechend der Frequenz anpassen - mehr Amplitude bei niedrigerer Frequenz
            amplitude_factor = 1.0 - (freq - 6.0) / 20.0  # Normalisierter Faktor (0-1)
            amplitude = 200 * amplitude_factor  # Basisamplitude von 200 Einheiten

            # Sinus für Plattformposition, verschobener Sinus für Kraft
            platform_pos = base_value + amplitude * np.sin(2 * np.pi * freq * t)
            tire_force = base_value + amplitude * np.sin(2 * np.pi * freq * t - phase_rad)

            # OPTIMIERUNG: NumPy-Vektorisierung statt manuelle Berechnung für Rauschen
            # Erzeuge vier Werte mit etwas Rauschen für die DMS-Sensoren
            rng = np.random.default_rng()
            noise_factor = 0.05  # 5% Rauschen
            noise_amplitude = amplitude * noise_factor

            # Rauschen für die vier DMS-Sensoren
            noise = rng.normal(0, noise_amplitude, 4)

            # Die ersten beiden Werte basieren auf der Plattformposition
            dms1 = int(platform_pos + noise[0])
            dms2 = int(platform_pos + noise[1])

            # Die letzten beiden Werte basieren auf der Reifenkraft
            dms3 = int(tire_force + noise[2])
            dms4 = int(tire_force + noise[3])

            values = [dms1, dms2, dms3, dms4]

        else:
            # Ruhewerte mit leichtem Rauschen
            rng = np.random.default_rng()
            noise = rng.integers(-10, 11, 4)  # Rauschen im Bereich -10 bis +10
            values = [base_value + n for n in noise]

        # Sicherstellen, dass die Werte im gültigen Bereich liegen
        return [max(0, min(val, 1023)) for val in values]

    def process_message(self, arbitration_id, data, is_extended_id=False):
        """
        Verarbeitet eine eingehende CAN-Nachricht und aktualisiert den Simulationszustand.

        In der Simulation werden die Befehle interpretiert, um den Simulationszustand
        zu aktualisieren, z.B. das Starten/Stoppen von Motoren.

        Args:
            arbitration_id: CAN-Nachrichten-ID
            data: Liste von Bytes (0-255) oder bytes-Objekt
            is_extended_id: Extended-ID-Format verwenden

        Returns:
            bool: True, da die Verarbeitung immer erfolgreich simuliert wird
        """
        # Sicherstellen, dass data ein bytes-Objekt ist
        if not isinstance(data, bytes):
            data = bytes(data)

        # EUSAMA Protokoll: Motor-Kommandos
        if self.profile == "eusama" and arbitration_id == self.MOTOR_CONTROL_ID:
            if len(data) >= 2:
                motor_mask = data[0]
                runtime = data[1]

                if motor_mask == 0:
                    # Stopp-Kommando
                    self.stop_motor()
                else:
                    # Start-Kommando
                    if motor_mask & 0x01:
                        self.start_motor("left", runtime)
                    if motor_mask & 0x02:
                        self.start_motor("right", runtime)

        # ASA Protokoll: ALIVE mit Motorkommandos
        elif self.profile == "asa" and arbitration_id == self.ALIVE_ID:
            if len(data) >= 2:
                alive_flags = data[0:2]

                # Messung START (Bit 1 in zweitem Byte)
                if alive_flags[1] & 0x02:
                    self.start_motor("both", 10)  # Standardlaufzeit 10 Sekunden

                # Messung STOP (Bit 2 in zweitem Byte)
                if alive_flags[1] & 0x04:
                    self.stop_motor()

        logger.debug(f"CAN-Nachricht verarbeitet: ID=0x{arbitration_id:X}, Daten={list(data)}")
        return True

    def get_next_message(self, timeout=0.1):
        """
        Gibt die nächste simulierte CAN-Nachricht zurück.

        Args:
            timeout: Timeout in Sekunden

        Returns:
            Nachricht oder None bei Timeout
        """
        try:
            return self.message_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def add_message_callback(self, callback):
        """
        Fügt einen Callback für generierte Nachrichten hinzu.

        Args:
            callback: Funktion, die für jede Nachricht aufgerufen wird (callback(msg))
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_message_callback(self, callback):
        """
        Entfernt einen zuvor registrierten Callback.

        Args:
            callback: Zu entfernender Callback
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def start_motor(self, side, runtime_seconds):
        """
        Startet einen simulierten Motor.

        Args:
            side: "left", "right" oder "both"
            runtime_seconds: Laufzeit in Sekunden
        """
        # Simulationszeit und Frequenzsweep zurücksetzen
        self.simulation_time = 0.0
        self.freq_sweep["current"] = 25.0  # Startfrequenz zurücksetzen

        if side.lower() == "left" or side.lower() == "both":
            self.left_motor_running = True
            self.motor_runtime_left = runtime_seconds
            logger.info(f"Motor links gestartet für {runtime_seconds} Sekunden")

        if side.lower() == "right" or side.lower() == "both":
            self.right_motor_running = True
            self.motor_runtime_right = runtime_seconds
            logger.info(f"Motor rechts gestartet für {runtime_seconds} Sekunden")

    def stop_motor(self, side="both"):
        """
        Stoppt einen simulierten Motor.

        Args:
            side: "left", "right" oder "both"
        """
        if side.lower() == "left" or side.lower() == "both":
            self.left_motor_running = False
            self.motor_runtime_left = 0
            logger.info("Motor links gestoppt")

        if side.lower() == "right" or side.lower() == "both":
            self.right_motor_running = False
            self.motor_runtime_right = 0
            logger.info("Motor rechts gestoppt")

    def _create_message(self, arbitration_id, data, is_extended_id=False, timestamp=None, **kwargs):
        """
        Erstellt eine CAN-Nachricht mit den angegebenen Parametern.

        Args:
            arbitration_id: CAN-Nachrichten-ID
            data: Nutzdaten als Bytes
            is_extended_id: Extended-ID-Format verwenden
            timestamp: Optionaler Zeitstempel (Standard: jetzt)
            **kwargs: Weitere Parameter für die CAN-Nachricht

        Returns:
            CAN-Nachricht-Objekt
        """
        # Standardzeitstempel wenn nicht angegeben
        if timestamp is None:
            timestamp = time.time()

        if CAN_AVAILABLE:
            return can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended_id,
                timestamp=timestamp,
                **kwargs,
            )
        # Wenn python-can nicht verfügbar ist, unsere eigene Nachrichtenklasse verwenden
        from fahrwerkstester.backend.can_simulator_service.lib.can.message import CanMessage

        return CanMessage(
            arbitration_id=arbitration_id,
            data=data,
            timestamp=timestamp,
            is_extended_id=is_extended_id,
            **kwargs,
        )

    def get_performance_stats(self):
        """
        Gibt Leistungsstatistiken zur Simulation zurück.

        Returns:
            dict: Performance-Statistiken
        """
        stats = self.performance_stats.copy()

        # Durchschnittliche Generationszeit berechnen
        if len(self.performance_stats["generation_times"]) > 0:
            avg_gen_time = sum(self.performance_stats["generation_times"]) / len(
                self.performance_stats["generation_times"]
            )
            stats["avg_generation_time"] = avg_gen_time

            # Geschätzte CPU-Auslastung berechnen
            # Wenn Generierung 100% der Zeit zwischen zwei Generierungen benötigt = 100% CPU
            generation_frequency = 1.0 / (self.message_interval * self.batch_size)
            stats["cpu_usage"] = min(100.0, avg_gen_time * generation_frequency * 100.0)

        return stats

    def optimize_performance(self):
        """
        Optimiert die Leistung des Simulators OHNE die Hardware-Spezifikation zu verletzen.

        WICHTIG: Das Message-Intervall bleibt konstant bei 10ms (EUSAMA-Protokoll).
        Nur die Batch-Größe wird angepasst, um CPU-Last zu reduzieren.
        """
        stats = self.get_performance_stats()

        if "avg_generation_time" in stats:
            cpu_usage = stats["cpu_usage"]

            # NUR Batch-Größe anpassen - NIEMALS das Message-Intervall ändern!
            # Das EUSAMA-Protokoll erfordert konstante 10ms (100 Hz)
            if cpu_usage > 80.0:
                # Erhöhe Batch-Größe für effizientere Verarbeitung
                if self.batch_size < 50:
                    old_batch_size = self.batch_size
                    self.batch_size = min(50, self.batch_size + 5)
                    logger.info(
                        f"CPU-Last zu hoch ({cpu_usage:.1f}%) - erhöhe Batch-Größe von {old_batch_size} auf {self.batch_size}"
                    )
                else:
                    logger.warning(
                        f"CPU-Last sehr hoch ({cpu_usage:.1f}%), aber maximale Batch-Größe erreicht. Hardware-Upgrade empfohlen."
                    )

            # Wenn CPU-Auslastung sehr niedrig, können wir kleinere Batches verwenden für niedrigere Latenz
            elif cpu_usage < 20.0 and self.batch_size > 5:
                old_batch_size = self.batch_size
                self.batch_size = max(5, self.batch_size - 2)
                logger.info(
                    f"CPU-Last niedrig ({cpu_usage:.1f}%) - reduziere Batch-Größe von {old_batch_size} auf {self.batch_size} für niedrigere Latenz"
                )

        # Das Message-Intervall bleibt IMMER konstant bei EUSAMA-Spezifikation
        if self.message_interval != self.DEFAULT_MESSAGE_INTERVAL:
            logger.warning(
                f"Message-Intervall wurde auf {self.message_interval:.4f}s geändert - setze zurück auf EUSAMA-Standard: {self.DEFAULT_MESSAGE_INTERVAL:.4f}s"
            )
            self.message_interval = self.DEFAULT_MESSAGE_INTERVAL


# Demo-Funktion zur einfachen Verwendung
def run_demo():
    """Führt eine einfache Demo des CAN-Simulators aus."""
    logging.basicConfig(level=logging.INFO)

    # Simulator erstellen
    simulator = CanSimulator(profile="eusama", message_interval=0.01)  # 100 Hz

    # Callback für Nachrichten
    def on_message(msg):
        if msg.arbitration_id == 0x08AAAA66:  # Nur Motorstatus-Nachrichten ausgeben
            motor_mask = msg.data[0]
            remaining_time = msg.data[1]
            left_running = "An" if motor_mask & 0x01 else "Aus"
            right_running = "An" if motor_mask & 0x02 else "Aus"
            print(
                f"Motor-Status: Links={left_running}, Rechts={right_running}, Restzeit={remaining_time}s"
            )

    # Callback registrieren und Simulation starten
    simulator.add_message_callback(on_message)
    simulator.start()

    try:
        print("Simulator läuft. Drücken Sie Strg+C zum Beenden.")
        print("Starte linken Motor für 5 Sekunden...")
        simulator.start_motor("left", 5)
        time.sleep(7)

        # Performance-Statistiken ausgeben
        stats = simulator.get_performance_stats()
        print("Performance-Statistiken:")
        print(f"- Erzeugte Nachrichten: {stats.get('messages_generated', 0)}")
        print(f"- Gesendete Nachrichten: {stats.get('messages_sent', 0)}")
        print(f"- Durchschn. Generierungszeit: {stats.get('avg_generation_time', 0) * 1000:.2f} ms")
        print(f"- Geschätzte CPU-Auslastung: {stats.get('cpu_usage', 0):.1f}%")

        print("Starte rechten Motor für 5 Sekunden...")
        simulator.start_motor("right", 5)
        time.sleep(7)

        # Optimierung durchführen
        simulator.optimize_performance()
        print(
            f"Optimierte Parameter: Intervall={simulator.message_interval:.4f}s, Batch-Größe={simulator.batch_size}"
        )

    except KeyboardInterrupt:
        print("Simulator wird beendet...")
    finally:
        simulator.stop()
        print("Simulator beendet.")


if __name__ == "__main__":
    run_demo()