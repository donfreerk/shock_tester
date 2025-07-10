"""
HybridSimulator Refactoring - Nach raspi_can_simulator Vorbild
Eliminiert das Problem der leeren 0x700 Messages

ARCHITEKTUR-VERBESSERUNGEN:
1. Saubere Test-Kontrolle wie im raspi_can_simulator
2. Eliminierung der problematischen DummyMessage-Klasse
3. Explizite Message-Generierung ohne Background-Threads
4. Kombiniert echte CAN-Messages mit interpretierten Daten
"""

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

try:
    import can

    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

logger = logging.getLogger(__name__)


class HybridSimulator:
    """
    Sauberer Hybrid-Simulator basierend auf raspi_can_simulator Architektur.

    KEINE leeren Messages mehr!
    Kombiniert Low-Level CAN-Frames mit High-Level interpretierten Daten.
    """

    # EUSAMA CAN-IDs (wie im raspi_can_simulator)
    RAW_DATA_LEFT_ID = 0x08AAAA60
    RAW_DATA_RIGHT_ID = 0x08AAAA61
    MOTOR_STATUS_ID = 0x08AAAA66

    def __init__(self):
        """Initialisiert den sauberen Hybrid-Simulator."""
        # Test-Zustand (saubere Kontrolle)
        self.test_active = False  # ← Wie im raspi_can_simulator
        self.current_side = "left"
        self.test_start_time = 0
        self.test_duration = 30.0
        self.simulation_time = 0.0

        # Simulator-Einstellungen
        self.damping_quality = "good"
        self.generate_low_level = True
        self.simulation_profile = "eusama"

        # Callbacks für Messages
        self.message_callbacks = []

        # Verbindungsstatus (für GUI-Kompatibilität)
        self.connected = True
        self.current_baudrate = 1000000

        # Performance-optimierte Queues
        self.low_level_queue = queue.Queue(maxsize=1000)
        self.high_level_queue = queue.Queue(maxsize=1000)

        # EGEA-Parameter
        self.freq_start = 25.0  # Hz
        self.freq_end = 6.0  # Hz
        self.platform_amplitude = 3.0  # mm

        # Dämpfungsparameter
        self.damping_params = {
            "good": {"min_phase": 38.0, "resonance_freq": 13.5},
            "marginal": {"min_phase": 32.0, "resonance_freq": 12.8},
            "bad": {"min_phase": 25.0, "resonance_freq": 12.0},
        }

        logger.info("Sauberer HybridSimulator initialisiert - KEINE leeren Messages!")

    def connect(self, baudrate=None):
        """Simuliert Verbindung (GUI-Kompatibilität)."""
        self.connected = True
        return True

    def add_message_callback(self, callback: Callable):
        """Fügt Callback für Messages hinzu."""
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)

    def remove_message_callback(self, callback: Callable):
        """Entfernt Callback."""
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)

    def set_damping_quality(self, quality: str):
        """Setzt Dämpfungsqualität."""
        if quality in self.damping_params:
            self.damping_quality = quality
            logger.info(f"Dämpfungsqualität: {quality}")

    def set_generate_low_level(self, enable: bool):
        """Aktiviert/deaktiviert Low-Level CAN-Frame Generierung."""
        self.generate_low_level = enable

    def set_simulation_profile(self, profile: str):
        """Setzt Simulationsprofil."""
        if profile in ["eusama", "asa"]:
            self.simulation_profile = profile

    def send_message(self, arbitration_id, data, is_extended_id=False, **kwargs):
        """Verarbeitet CAN-Befehle (GUI-Kompatibilität)."""
        # EUSAMA Motor Control
        if arbitration_id == 0x08AAAA71:  # Motor Control
            if len(data) >= 2:
                motor_mask = data[0]
                runtime = data[1]

                if motor_mask == 0:
                    self.stop_test()
                elif motor_mask & 0x01:
                    self.start_test("left", runtime)
                elif motor_mask & 0x02:
                    self.start_test("right", runtime)

        return True

    def start_test(self, side: str, duration: float):
        """Startet Test - SAUBERE Implementierung."""
        # Vorherigen Test stoppen
        if self.test_active:
            self.stop_test()

        # Test-Parameter setzen
        self.current_side = side
        self.test_duration = duration
        self.test_start_time = time.time()
        self.simulation_time = 0.0
        self.test_active = True  # ← Saubere Kontrolle

        logger.info(f"Test gestartet: {side}, {duration}s")

        # Test-Thread starten (selbst-beendend)
        test_thread = threading.Thread(
            target=self._run_test_cycle, args=(side, duration), daemon=True
        )
        test_thread.start()

    def stop_test(self):
        """Stoppt Test - SAUBERE Implementierung."""
        if self.test_active:
            self.test_active = False  # ← Stoppt Message-Generierung sofort
            logger.info("Test gestoppt")

    def _run_test_cycle(self, side: str, duration: float):
        """
        Führt Testzyklus durch - NACH raspi_can_simulator VORBILD.
        Selbst-beendend, KEINE kontinuierlichen Background-Threads.
        """
        try:
            start_time = time.time()
            last_message_time = 0
            message_interval = 0.05  # 20 Hz für GUI-Updates

            while self.test_active and (time.time() - start_time) < duration:
                current_time = time.time()

                # Messages in Intervallen generieren
                if current_time - last_message_time >= message_interval:
                    # SAUBERE Message-Generierung
                    messages = self._generate_messages()

                    # Messages verarbeiten und senden
                    for msg_data in messages:
                        self._process_and_send_message(msg_data)

                    last_message_time = current_time

                # Kurze Pause
                time.sleep(0.01)

            # Test automatisch beenden
            self.test_active = False

            # EINMALIGE Abschluss-Nachricht
            self._send_test_completion(side, duration)

            logger.info(f"Testzyklus für {side} SAUBER beendet")

        except Exception as e:
            logger.error(f"Fehler im Testzyklus: {e}")
            self.test_active = False

    def _generate_messages(self) -> List[Dict[str, Any]]:
        """
        Generiert Messages - NUR wenn Test aktiv.
        NACH raspi_can_simulator VORBILD.
        """
        if not self.test_active:
            return []  # ← SAUBER: Keine Messages wenn Test nicht aktiv

        current_time = time.time()
        elapsed = current_time - self.test_start_time

        # Test beenden wenn Dauer erreicht
        if elapsed >= self.test_duration:
            self.test_active = False
            return []  # ← SAUBER: Keine Messages nach Testende

        # Aktuelle Frequenz berechnen
        progress = elapsed / self.test_duration
        frequency = self.freq_start - progress * (self.freq_start - self.freq_end)

        # Phasenverschiebung berechnen
        damping = self.damping_params[self.damping_quality]
        resonance_freq = damping["resonance_freq"]
        min_phase = damping["min_phase"]

        freq_factor = abs(frequency - resonance_freq) / 10.0
        phase_shift = min_phase + 15.0 * np.exp(-2 * freq_factor)
        phase_rad = np.radians(phase_shift)

        # Signale berechnen
        platform_pos = self.platform_amplitude * np.sin(2 * np.pi * frequency * elapsed)
        static_weight = 512
        force_amplitude = 100 * (1.0 + 0.5 * np.exp(-freq_factor))
        tire_force = static_weight + force_amplitude * np.sin(
            2 * np.pi * frequency * elapsed - phase_rad
        )

        messages = []

        # 1. HIGH-LEVEL Message (für GUI)
        high_level_data = {
            "type": "high_level",
            "event": "test_data",
            "method": "phase_shift",
            "side": self.current_side,
            "position": "front_left" if self.current_side == "left" else "front_right",
            "timestamp": current_time,
            "elapsed": elapsed,
            "frequency": frequency,
            "platform_position": platform_pos,
            "tire_force": tire_force,
            "static_weight": static_weight,
            "phase_shift": phase_shift,
        }
        messages.append(high_level_data)

        # 2. LOW-LEVEL CAN Messages (wenn aktiviert)
        if self.generate_low_level:
            # DMS-Werte generieren
            dms1 = int(max(0, min(1023, static_weight + platform_pos * 20)))
            dms2 = int(max(0, min(1023, static_weight + platform_pos * 18)))
            dms3 = int(max(0, min(1023, tire_force)))
            dms4 = int(max(0, min(1023, tire_force * 0.95)))

            # CAN-Message für DMS-Daten
            can_id = (
                self.RAW_DATA_LEFT_ID if self.current_side == "left" else self.RAW_DATA_RIGHT_ID
            )
            dms_data = bytearray(8)
            dms_values = [dms1, dms2, dms3, dms4]
            for i, dms in enumerate(dms_values):
                dms_data[i * 2] = (dms >> 8) & 0xFF
                dms_data[i * 2 + 1] = dms & 0xFF

            can_message_data = {
                "type": "low_level",
                "id": can_id,
                "data": bytes(dms_data),
                "extended": True,
                "timestamp": current_time,
            }
            messages.append(can_message_data)

            # Motorstatus-Message
            motor_mask = 0x01 if self.current_side == "left" else 0x02
            remaining_time = max(0, int(self.test_duration - elapsed))
            motor_data = bytes([motor_mask, min(255, remaining_time), 0, 0, 0, 0, 0, 0])

            motor_message_data = {
                "type": "low_level",
                "id": self.MOTOR_STATUS_ID,
                "data": motor_data,
                "extended": True,
                "timestamp": current_time,
            }
            messages.append(motor_message_data)

        return messages

    def _process_and_send_message(self, msg_data: Dict[str, Any]):
        """Verarbeitet und sendet Messages an Callbacks."""
        try:
            if msg_data["type"] == "high_level":
                # High-Level Message für GUI
                for callback in self.message_callbacks:
                    try:
                        # Erstelle kompatibles Message-Objekt
                        msg = SimpleMessage(msg_data)
                        callback(msg)
                    except Exception as e:
                        logger.error(f"Fehler im High-Level Callback: {e}")

            elif msg_data["type"] == "low_level":
                # Low-Level CAN Message
                if CAN_AVAILABLE:
                    can_msg = can.Message(
                        arbitration_id=msg_data["id"],
                        data=msg_data["data"],
                        is_extended_id=msg_data["extended"],
                        timestamp=msg_data["timestamp"],
                    )

                    # In Queue für recv_message()
                    try:
                        self.low_level_queue.put_nowait(can_msg)
                    except queue.Full:
                        # Älteste entfernen, neue hinzufügen
                        try:
                            self.low_level_queue.get_nowait()
                            self.low_level_queue.put_nowait(can_msg)
                        except queue.Empty:
                            pass

                    # An Callbacks senden
                    for callback in self.message_callbacks:
                        try:
                            callback(can_msg)
                        except Exception as e:
                            logger.error(f"Fehler im Low-Level Callback: {e}")

        except Exception as e:
            logger.error(f"Fehler beim Message-Processing: {e}")

    def _send_test_completion(self, side: str, duration: float):
        """Sendet EINMALIGE Abschluss-Nachricht."""
        completion_data = {
            "type": "high_level",
            "event": "test_completed",
            "side": side,
            "method": "phase_shift",
            "duration": duration,
            "timestamp": time.time(),
        }

        self._process_and_send_message(completion_data)
        logger.info(f"Test-Completion für {side} gesendet")

    def recv_message(self, timeout=0.1):
        """
        Empfängt Messages - SAUBERE Implementierung.
        KEINE leeren Messages mehr!
        """
        try:
            # Priorisiere Low-Level CAN Messages
            if self.generate_low_level:
                try:
                    return self.low_level_queue.get(timeout=timeout / 2)
                except queue.Empty:
                    pass

            # High-Level Messages
            try:
                return self.high_level_queue.get(timeout=timeout / 2)
            except queue.Empty:
                pass

            return None  # Kein Timeout, einfach None

        except Exception as e:
            logger.error(f"Fehler beim recv_message: {e}")
            return None

    def shutdown(self):
        """Sauberes Herunterfahren."""
        self.stop_test()
        self.connected = False

        # Queues leeren
        while not self.low_level_queue.empty():
            try:
                self.low_level_queue.get_nowait()
            except queue.Empty:
                break

        while not self.high_level_queue.empty():
            try:
                self.high_level_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Sauberer HybridSimulator heruntergefahren")


class SimpleMessage:
    """
    Einfache Message-Klasse für High-Level Daten.
    ERSETZT die problematische DummyMessage.
    """

    def __init__(self, data: Dict[str, Any]):
        # Kompatibilität zu can.Message
        self.arbitration_id = 0x8AAAA70  # ← NEUE ID für High-Level
        self.data = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        self.timestamp = data.get("timestamp", time.time())
        self.is_extended_id = True
        self.dlc = 8

        # Interpretierte Daten
        self.interpreted_data = data