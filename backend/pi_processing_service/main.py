#!/usr/bin/env python3
"""
Pi Processing Service - Hauptmodul
Hauptservice für Post-Processing der Fahrwerkstester-Messdaten

Funktionalitäten:
- Empfang kompletter Messdaten über MQTT
- Phase-Shift-Berechnung nach Testende
- Sinuskurven-Generierung für GUI
- Robuste Queue-basierte Verarbeitung
"""

import asyncio
import logging
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import numpy as np

# Füge das Common-Library-Verzeichnis zum Python-Pfad hinzu
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

# Zentrale suspension_core Imports (KORRIGIERT)
from suspension_core.mqtt import MqttHandler
from suspension_core.mqtt.service import MqttServiceBase, MqttTopics
from suspension_core.config import ConfigManager

# Lokale Imports (KORRIGIERT)
from .processing.phase_shift_calculator import PhaseShiftCalculator
from .processing.data_validator import DataValidator
from .utils.signal_processing import SignalProcessor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingTask:
    """Container für Processing-Aufgaben"""

    task_id: str
    position: str  # front_left, front_right, etc.
    raw_data: Dict[str, Any]
    timestamp: float
    priority: int = 0  # 0 = höchste Priorität

    def __lt__(self, other):
        """Für Priority-Queue-Sortierung"""
        return self.priority < other.priority


@dataclass
class ProcessingResult:
    """Container für Processing-Ergebnisse"""

    task_id: str
    position: str
    success: bool
    results: Dict[str, Any]
    processing_time: float
    timestamp: float
    error_message: Optional[str] = None


class PiProcessingService(MqttServiceBase):
    """
    Modernisierter Pi Processing Service mit einheitlicher MQTT-Integration

    Architekturprinzipien:
    - Event-driven durch MQTT mit MqttServiceBase
    - Asynchrone Verarbeitung mit Queues
    - Robuste Fehlerbehandlung
    - Vollständige Datensammlung vor Processing
    - Saubere Async/Sync-Bridge ohne Event-Loop-Probleme
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialisiert den Pi Processing Service

        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        # Konfiguration laden und MqttServiceBase initialisieren
        config = ConfigManager(config_path)
        super().__init__("pi_processing", config)

        # Prozessoren initialisieren
        self.phase_shift_calculator = PhaseShiftCalculator()
        self.data_validator = DataValidator()
        self.signal_processor = SignalProcessor()

        # Queue für asynchrone Verarbeitung
        self.processing_queue = asyncio.PriorityQueue()
        self.result_callbacks: Dict[str, Callable] = {}

        # Test-Daten-Sammlung für Post-Processing
        self.active_tests: Dict[str, Dict[str, Any]] = {}  # test_id -> gesammelte Daten
        self.test_timeouts: Dict[str, float] = {}  # test_id -> timeout timestamp

        # Service-Status
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.service_start_time = None

        # Graceful Shutdown Handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Pi Processing Service initialisiert")

    async def setup_mqtt_subscriptions(self):
        """MQTT-Subscriptions für Pi Processing mit standardisierten Topics"""
        # Test-Lifecycle
        self.register_topic_handler(MqttTopics.TEST_STATUS, self.handle_test_status)
        self.register_topic_handler(MqttTopics.TEST_COMPLETED, self.handle_test_completed)

        # Data Input - verschiedene Datenquellen
        self.register_topic_handler(MqttTopics.MEASUREMENT_PROCESSED, self.handle_measurement_data)
        self.register_topic_handler(MqttTopics.RAW_DATA_COMPLETE, self.handle_raw_data)

        # Commands
        self.register_topic_handler(MqttTopics.PI_PROCESSING_COMMAND, self.handle_command)

        logger.info("MQTT-Subscriptions eingerichtet:")
        logger.info("   - suspension/test/status (für Test-Start/Stop)")
        logger.info("   - suspension/test/completed (für Test-Completion)")
        logger.info("   - suspension/measurements/processed (für Live-Daten)")
        logger.info("   - suspension/raw_data/complete (für Rohdaten)")
        logger.info("   - suspension/processing/command (für Service-Commands)")

    def _signal_handler(self, signum, frame):
        """Behandelt Shutdown-Signale"""
        logger.info(f"Signal {signum} empfangen, beende Service graceful...")
        self._running = False

    async def start(self):
        """Startet den Processing Service mit neuer MqttServiceBase"""
        logger.info("Starte Pi Processing Service...")
        self.service_start_time = time.time()

        try:
            # MQTT-Integration starten (ersetzt manuelle Verbindung)
            if not await self.start_mqtt():
                logger.error("MQTT-Verbindung fehlgeschlagen")
                return False

            # Status senden
            await self.publish_status("ready", {"message": "Pi Processing Service ready"})

            # Haupt-Service-Loop starten (Heartbeat wird automatisch von MqttServiceBase gehandhabt)
            await self._processing_loop()

            logger.info("Pi Processing Service gestartet")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Starten des Services: {e}")
            await self.stop()
            return False

    async def stop(self):
        """Stoppt den Processing Service"""
        logger.info("Stoppe Pi Processing Service...")

        # Status senden
        await self.publish_status("stopping", {"message": "Pi Processing Service stopping"})

        # MQTT-Integration stoppen (ersetzt manuelle Trennung)
        await self.stop_mqtt()

        logger.info("Pi Processing Service gestoppt")


    async def handle_test_status(self, topic: str, payload: Dict[str, Any]):
        """
        Verarbeitet Test-Status-Updates für Datensammlung

        Args:
            topic: MQTT-Topic
            payload: Status-Payload
        """
        try:
            status = payload.get("status")
            test_id = payload.get("test_id")

            if not test_id:
                return

            if status == "started":
                # Neuen Test initialisieren
                self._start_test_data_collection(test_id, payload)

            elif status in ["completed", "stopped"]:
                # Test beenden und Processing starten
                await self._finalize_test_data_collection(test_id)

            elif status == "error":
                # Test-Fehler
                self._cleanup_test_data(test_id)

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten des Test-Status: {e}")

    def _start_test_data_collection(self, test_id: str, test_info: Dict[str, Any]):
        """
        Startet Datensammlung für einen neuen Test

        Args:
            test_id: Test-ID
            test_info: Test-Informationen
        """
        logger.info(f"Starte Datensammlung für Test: {test_id}")

        self.active_tests[test_id] = {
            "test_id": test_id,
            "position": test_info.get("position", "unknown"),
            "start_time": time.time(),
            "data_points": [],
            "metadata": test_info,
        }

        # Timeout setzen (falls Test nicht ordnungsgemäß beendet wird)
        timeout_duration = test_info.get("duration", 60) + 30  # 30s Puffer
        self.test_timeouts[test_id] = time.time() + timeout_duration

    async def _finalize_test_data_collection(self, test_id: str):
        """
        Beendet Datensammlung und startet Processing

        Args:
            test_id: Test-ID
        """
        if test_id not in self.active_tests:
            logger.warning(f"Test {test_id} nicht in aktiven Tests gefunden")
            return

        test_data = self.active_tests[test_id]
        logger.info(
            f"Beende Datensammlung für Test: {test_id} mit {len(test_data['data_points'])} Datenpunkten"
        )

        # Alle gesammelten Daten zu einem Processing-Task zusammenfassen
        if len(test_data["data_points"]) > 0:
            # Erstelle Processing-Task mit allen gesammelten Daten
            combined_data = self._combine_test_data_points(test_data)

            task = ProcessingTask(
                task_id=test_id,
                position=test_data["position"],
                raw_data=combined_data,
                timestamp=time.time(),
                priority=0,
            )

            # Task in Queue einreihen
            await self.processing_queue.put((task.priority, task))

            logger.info(f"Post-Processing-Task erstellt: {test_id}")
        else:
            logger.warning(f"Keine Daten für Test {test_id} gesammelt")

        # Test-Daten aufräumen
        self._cleanup_test_data(test_id)

    def _combine_test_data_points(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kombiniert alle Datenpunkte eines Tests zu einem einzigen Dataset

        Args:
            test_data: Gesammelte Test-Daten

        Returns:
            Kombiniertes Dataset für Processing
        """
        data_points = test_data["data_points"]

        if not data_points:
            return {}

        # Listen für alle Zeitreihen-Daten
        time_series = []
        platform_positions = []
        tire_forces = []
        frequencies = []
        phase_shifts = []
        dms_values_series = []

        # Alle Datenpunkte zusammenfassen
        for point in data_points:
            time_series.append(point.get("elapsed", 0))
            platform_positions.append(point.get("platform_position", 0))
            tire_forces.append(point.get("tire_force", 0))
            frequencies.append(point.get("frequency", 0))
            phase_shifts.append(point.get("phase_shift", 0))

            if "dms_values" in point:
                dms_values_series.append(point["dms_values"])

        # Kombiniertes Dataset
        combined_data = {
            "test_id": test_data["test_id"],
            "position": test_data["position"],
            "start_time": test_data["start_time"],
            "end_time": time.time(),
            "duration": time.time() - test_data["start_time"],
            # Zeitreihen-Daten
            "time_data": time_series,
            "platform_position_data": platform_positions,
            "tire_force_data": tire_forces,
            "frequency_data": frequencies,
            "phase_shift_data": phase_shifts,
            "dms_data": dms_values_series,
            # Metadaten
            "sample_count": len(time_series),
            "static_weight": data_points[0].get("static_weight", 512)
            if data_points
            else 512,
            "metadata": test_data["metadata"],
        }

        logger.info(
            f"Kombinierte {len(data_points)} Datenpunkte zu Dataset mit {len(time_series)} Samples"
        )

        return combined_data

    def _cleanup_test_data(self, test_id: str):
        """
        Räumt Test-Daten auf

        Args:
            test_id: Test-ID
        """
        if test_id in self.active_tests:
            del self.active_tests[test_id]

        if test_id in self.test_timeouts:
            del self.test_timeouts[test_id]

    async def handle_raw_data(self, topic: str, payload: Dict[str, Any]):
        """
        Sammelt eingehende Live-Messdaten während Test läuft

        Args:
            topic: MQTT-Topic
            payload: Live-Messdaten-Payload
        """
        try:
            # WICHTIG: Diese Funktion sammelt Live-Daten während Test läuft

            # Extrahiere Test-Informationen aus Payload
            test_id = payload.get("test_id")
            position = payload.get("position")

            # Falls kein test_id, versuche aus anderen Feldern zu rekonstruieren
            if not test_id:
                # Fallback: generiere test_id aus timestamp und position
                timestamp = payload.get("timestamp", time.time())
                test_id = f"auto_{position}_{int(timestamp)}"

                # Automatisch Test starten falls noch nicht vorhanden
                if test_id not in self.active_tests:
                    logger.info(f"Auto-Start Datensammlung fuer Test: {test_id}")
                    self._start_test_data_collection(
                        test_id,
                        {
                            "position": position,
                            "duration": 60,  # Default-Dauer
                            "auto_started": True,
                        },
                    )

            # Prüfe ob Test aktiv ist
            if test_id in self.active_tests:
                # Datenpunkt zur Sammlung hinzufügen
                self.active_tests[test_id]["data_points"].append(payload)

                # Debug-Log alle 25 Datenpunkte
                point_count = len(self.active_tests[test_id]["data_points"])
                if point_count % 25 == 0:
                    logger.info(f"Test {test_id}: {point_count} Datenpunkte gesammelt")
            else:
                # Kein aktiver Test - Log als Debug
                logger.debug(f"Datenpunkt fuer inaktiven Test ignoriert: {test_id}")

        except Exception as e:
            logger.error(f"Fehler beim Sammeln der Messdaten: {e}")

    async def _handle_test_completion(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Test-Abschluss-Signale

        Args:
            topic: MQTT-Topic
            payload: Test-Completion-Payload
        """
        logger.info(f"Test abgeschlossen: {payload}")

    async def handle_command(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Service-Commands

        Args:
            topic: MQTT-Topic
            payload: Command-Payload
        """
        command = payload.get("command")

        if command == "status":
            await self.publish_status("running", self.get_service_status())
        elif command == "stop":
            await self.stop()
        elif command == "clear_queue":
            await self._clear_processing_queue()
        else:
            logger.warning(f"Unbekanntes Command: {command}")

    async def handle_test_completed(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt Test-Completion-Events

        Args:
            topic: MQTT-Topic
            payload: Completion-Payload
        """
        try:
            test_id = payload.get("test_id")
            if test_id:
                await self._finalize_test_data_collection(test_id)
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der Test-Completion: {e}")

    async def handle_measurement_data(self, topic: str, payload: Dict[str, Any]):
        """
        Behandelt verarbeitete Messdaten

        Args:
            topic: MQTT-Topic
            payload: Measurement-Payload
        """
        # Weiterleitung an handle_raw_data für einheitliche Behandlung
        await self.handle_raw_data(topic, payload)

    def get_service_status(self) -> Dict[str, Any]:
        """Gibt aktuellen Service-Status zurück"""
        return {
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed,
            "active_tests": len(self.active_tests),
            "processing_queue_size": self.processing_queue.qsize(),
            "uptime": time.time() - self.service_start_time if self.service_start_time else 0
        }

    async def _processing_loop(self):
        """Haupt-Processing-Loop"""
        logger.info("Processing-Loop gestartet")

        while self._running:
            try:
                # Warte auf Processing-Task mit Timeout
                try:
                    priority, task = await asyncio.wait_for(
                        self.processing_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Führe Processing durch
                result = await self._process_test_data(task)

                # Publiziere Ergebnisse
                await self._publish_results(result)

                # Statistiken aktualisieren
                if result.success:
                    self.tasks_processed += 1
                else:
                    self.tasks_failed += 1

                # Task als erledigt markieren
                self.processing_queue.task_done()

            except Exception as e:
                logger.error(f"Fehler in Processing-Loop: {e}")
                self.tasks_failed += 1

        logger.info("Processing-Loop beendet")

    async def _process_test_data(self, task: ProcessingTask) -> ProcessingResult:
        """
        Führt komplette Post-Processing-Analyse durch

        Args:
            task: Processing-Task mit vollständigen Test-Daten

        Returns:
            ProcessingResult mit vollständigen Sinuskurven
        """
        start_time = time.perf_counter()

        try:
            logger.info(
                f"Starte Post-Processing für Test: {task.task_id}, Position: {task.position}"
            )

            # 1. Vollständige Testdaten extrahieren
            raw_data = task.raw_data

            # Zeitreihen-Daten extrahieren
            time_data = np.array(raw_data.get("time_data", []))
            platform_data = np.array(raw_data.get("platform_position_data", []))
            force_data = np.array(raw_data.get("tire_force_data", []))
            frequency_data = np.array(raw_data.get("frequency_data", []))
            phase_shift_data = np.array(raw_data.get("phase_shift_data", []))

            if len(time_data) == 0:
                raise ValueError("Keine Zeitreihen-Daten vorhanden")

            logger.info(
                f"Verarbeite {len(time_data)} Datenpunkte über {time_data[-1] - time_data[0]:.1f}s"
            )

            # 2. Datenvalidierung
            if not self._validate_time_series_data(
                time_data, platform_data, force_data
            ):
                raise ValueError("Zeitreihen-Datenvalidierung fehlgeschlagen")

            # 3. Signal-Preprocessing für bessere Sinuskurven
            processed_platform = self._preprocess_signal(platform_data)
            processed_force = self._preprocess_signal(force_data)

            # 4. Phase-Shift-Analyse über Frequenzbereich
            phase_analysis = self._analyze_phase_shift_vs_frequency(
                time_data,
                processed_platform,
                processed_force,
                frequency_data,
                phase_shift_data,
            )

            # 5. Sinuskurven für vollständige Anzeige generieren
            sine_curves = {
                "time": time_data.tolist(),
                "platform_position": processed_platform.tolist(),
                "tire_force": processed_force.tolist(),
                "duration": float(time_data[-1] - time_data[0])
                if len(time_data) > 1
                else 0,
            }

            # 6. Frequenzanalyse für Spektrum-Plot
            frequency_analysis = self._perform_frequency_analysis(
                time_data, processed_platform, processed_force
            )

            # 7. EGEA-konforme Bewertung
            min_phase_shift = phase_analysis.get("min_phase_shift", 0)
            egea_evaluation = self._evaluate_egea_result(min_phase_shift)

            # 8. Vollständiges Ergebnis zusammenstellen
            results = {
                "phase_shift_result": phase_analysis,
                "sine_curves": sine_curves,
                "frequency_analysis": frequency_analysis,
                "evaluation": egea_evaluation,
                "min_phase_shift": min_phase_shift,
                "test_metadata": {
                    "position": task.position,
                    "duration": sine_curves["duration"],
                    "sample_count": len(time_data),
                    "static_weight": raw_data.get("static_weight", 512),
                    "sample_rate": len(time_data) / sine_curves["duration"]
                    if sine_curves["duration"] > 0
                    else 0,
                },
            }

            processing_time = time.perf_counter() - start_time

            logger.info(
                f"Post-Processing erfolgreich: {task.task_id} - φmin={min_phase_shift:.1f}° - {egea_evaluation} in {processing_time:.3f}s"
            )

            return ProcessingResult(
                task_id=task.task_id,
                position=task.position,
                success=True,
                results=results,
                processing_time=processing_time,
                timestamp=time.time(),
            )

        except Exception as e:
            processing_time = time.perf_counter() - start_time
            error_msg = f"Post-Processing-Fehler für Test {task.task_id}: {e}"
            logger.error(error_msg)

            return ProcessingResult(
                task_id=task.task_id,
                position=task.position,
                success=False,
                results={},
                processing_time=processing_time,
                timestamp=time.time(),
                error_message=str(e),
            )

    def _validate_time_series_data(
        self, time_data: np.ndarray, platform_data: np.ndarray, force_data: np.ndarray
    ) -> bool:
        """Validiert Zeitreihen-Daten"""
        if len(time_data) != len(platform_data) or len(time_data) != len(force_data):
            logger.error("Zeitreihen haben unterschiedliche Längen")
            return False

        if len(time_data) < 10:
            logger.error("Zu wenige Datenpunkte für sinnvolle Analyse")
            return False

        return True

    def _preprocess_signal(self, signal_data: np.ndarray) -> np.ndarray:
        """Preprocessed Signal für bessere Sinuskurven"""
        try:
            # Einfache Glättung um Rauschen zu reduzieren
            from scipy import signal

            # Butterworth-Filter für Glättung
            b, a = signal.butter(4, 0.1, btype="low")
            filtered = signal.filtfilt(b, a, signal_data)
            return filtered
        except ImportError:
            # Fallback: Einfacher gleitender Durchschnitt
            window_size = min(5, len(signal_data) // 10)
            if window_size < 2:
                return signal_data

            smoothed = np.convolve(
                signal_data, np.ones(window_size) / window_size, mode="same"
            )
            return smoothed
        except Exception as e:
            logger.warning(f"Signal-Preprocessing fehlgeschlagen: {e}")
            return signal_data

    def _analyze_phase_shift_vs_frequency(
        self,
        time_data: np.ndarray,
        platform_data: np.ndarray,
        force_data: np.ndarray,
        frequency_data: np.ndarray,
        phase_shift_data: np.ndarray,
    ) -> Dict[str, Any]:
        """Analysiert Phasenverschiebung über Frequenzbereich"""
        try:
            # Finde minimale Phasenverschiebung
            if len(phase_shift_data) > 0:
                min_phase_shift = float(np.min(phase_shift_data))
                min_phase_freq = (
                    float(frequency_data[np.argmin(phase_shift_data)])
                    if len(frequency_data) > 0
                    else 0
                )
            else:
                min_phase_shift = 0
                min_phase_freq = 0

            return {
                "min_phase_shift": min_phase_shift,
                "min_phase_frequency": min_phase_freq,
                "phase_shifts": phase_shift_data.tolist()
                if len(phase_shift_data) > 0
                else [],
                "frequencies": frequency_data.tolist()
                if len(frequency_data) > 0
                else [],
                "phase_shift_range": [
                    float(np.min(phase_shift_data)),
                    float(np.max(phase_shift_data)),
                ]
                if len(phase_shift_data) > 0
                else [0, 0],
            }
        except Exception as e:
            logger.error(f"Phase-Shift-Analyse fehlgeschlagen: {e}")
            return {"min_phase_shift": 0, "error": str(e)}

    def _perform_frequency_analysis(
        self, time_data: np.ndarray, platform_data: np.ndarray, force_data: np.ndarray
    ) -> Dict[str, Any]:
        """Führt Frequenzanalyse für Spektrum-Plot durch"""
        try:
            if len(time_data) < 2:
                return {}

            # Sample-Rate berechnen
            dt = np.mean(np.diff(time_data))
            sample_rate = 1.0 / dt if dt > 0 else 1.0

            # FFT für beide Signale
            platform_fft = np.fft.fft(platform_data)
            force_fft = np.fft.fft(force_data)

            # Frequenz-Array
            frequencies = np.fft.fftfreq(len(time_data), dt)

            # Nur positive Frequenzen
            pos_freq_idx = frequencies > 0
            frequencies = frequencies[pos_freq_idx]
            platform_magnitude = np.abs(platform_fft[pos_freq_idx])
            force_magnitude = np.abs(force_fft[pos_freq_idx])

            # Begrenze auf relevanten Bereich (0-30 Hz)
            relevant_idx = frequencies <= 30.0
            frequencies = frequencies[relevant_idx]
            platform_magnitude = platform_magnitude[relevant_idx]
            force_magnitude = force_magnitude[relevant_idx]

            return {
                "sample_rate": sample_rate,
                "spectral_data": {
                    "frequencies": frequencies.tolist(),
                    "platform_magnitude": platform_magnitude.tolist(),
                    "force_magnitude": force_magnitude.tolist(),
                },
            }

        except Exception as e:
            logger.error(f"Frequenzanalyse fehlgeschlagen: {e}")
            return {"error": str(e)}

    async def _publish_results(self, result: ProcessingResult):
        """
        Publiziert Processing-Ergebnisse über MQTT

        Args:
            result: Processing-Ergebnis
        """
        try:
            if result.success:
                # 1. Finale Sinuskurven für Post-Processing GUI
                await self._publish_final_sine_curves(result)

                # 2. Legacy-Format für bestehende Systeme
                await self._publish_legacy_results(result)
            else:
                # Nur Fehler-Nachricht
                await self._publish_error_result(result)

            logger.info(f"Ergebnisse publiziert für Task: {result.task_id}")

        except Exception as e:
            logger.error(f"Fehler beim Publizieren der Ergebnisse: {e}")

    async def _publish_final_sine_curves(self, result: ProcessingResult):
        """
        Publiziert vollständige Sinuskurven für Post-Processing GUI

        Args:
            result: Processing-Ergebnis mit Sinuskurven-Daten
        """
        try:
            # Daten aus Ergebnis extrahieren
            phase_result = result.results.get("phase_shift_result", {})
            sine_curves = result.results.get("sine_curves", {})
            frequency_analysis = result.results.get("frequency_analysis", {})
            metadata = result.results.get("test_metadata", {})

            # EGEA-Bewertung bestimmen
            min_phase_shift = phase_result.get("min_phase_shift", 0)
            evaluation = self._evaluate_egea_result(min_phase_shift)

            # Vollständige finale Ergebnisse für GUI
            final_result = {
                "test_id": result.task_id,
                "position": result.position,
                "timestamp": result.timestamp,
                "success": result.success,
                "evaluation": evaluation,
                "min_phase_shift": min_phase_shift,
                # Vollständige Sinuskurven-Daten
                "time_data": sine_curves.get("time", []),
                "platform_position": sine_curves.get("platform_position", []),
                "tire_force": sine_curves.get("tire_force", []),
                # Phase-Shift-Analyse
                "phase_shifts": phase_result.get("phase_shifts", []),
                "frequencies": phase_result.get("frequencies", []),
                # Zusätzliche Ergebnisse
                "static_weight": metadata.get("static_weight", 0),
                "duration": metadata.get("duration", 0),
                "sample_count": metadata.get("sample_count", 0),
                # Frequenzanalyse für erweiterte Plots
                "frequency_analysis": frequency_analysis,
                # Metadaten
                "processing_time": result.processing_time,
                "source": "pi_processing_service",
            }

            # Auf finales Topic publizieren
            await self._publish_mqtt("suspension/test/final_result", final_result)

            logger.info(
                f"Finale Sinuskurven publiziert: {result.task_id} - {evaluation}"
            )

        except Exception as e:
            logger.error(f"Fehler beim Publizieren der finalen Sinuskurven: {e}")

    async def _publish_legacy_results(self, result: ProcessingResult):
        """
        Publiziert Ergebnisse im Legacy-Format

        Args:
            result: Processing-Ergebnis
        """
        try:
            # Legacy-Format für Rückwärtskompatibilität
            legacy_result = {
                "test_id": result.task_id,
                "position": result.position,
                "timestamp": result.timestamp,
                "success": result.success,
                "processing_time": result.processing_time,
                "results": result.results,
            }

            await self._publish_mqtt("suspension/results/processed", legacy_result)

        except Exception as e:
            logger.error(f"Fehler beim Publizieren der Legacy-Ergebnisse: {e}")

    async def _publish_error_result(self, result: ProcessingResult):
        """
        Publiziert Fehler-Ergebnis

        Args:
            result: Fehlerhaftes Processing-Ergebnis
        """
        try:
            error_result = {
                "test_id": result.task_id,
                "position": result.position,
                "timestamp": result.timestamp,
                "success": False,
                "error": result.error_message,
                "evaluation": "ERROR",
                "processing_time": result.processing_time,
            }

            # Sowohl auf final als auch legacy Topic
            await self._publish_mqtt("suspension/test/final_result", error_result)
            await self._publish_mqtt("suspension/results/processed", error_result)

        except Exception as e:
            logger.error(f"Fehler beim Publizieren des Fehler-Ergebnisses: {e}")

    def _evaluate_egea_result(self, min_phase_shift: float) -> str:
        """
        Bewertet das EGEA-Ergebnis basierend auf Phasenverschiebung

        Args:
            min_phase_shift: Minimale Phasenverschiebung in Grad

        Returns:
            EGEA-Bewertung als String
        """
        if min_phase_shift >= 40:
            return "EXCELLENT"
        elif min_phase_shift >= 35:
            return "GOOD"
        elif min_phase_shift >= 25:
            return "ACCEPTABLE"
        elif min_phase_shift >= 15:
            return "POOR"
        else:
            return "VERY_POOR"



    async def _check_test_timeouts(self):
        """Prüft und behandelt Test-Timeouts"""
        current_time = time.time()
        timeout_tests = []

        for test_id, timeout_time in self.test_timeouts.items():
            if current_time > timeout_time:
                timeout_tests.append(test_id)

        for test_id in timeout_tests:
            logger.warning(f"Test-Timeout für {test_id} - starte Force-Processing")
            await self._finalize_test_data_collection(test_id)


    async def _clear_processing_queue(self):
        """Leert die Processing-Queue"""
        cleared_count = 0
        while not self.processing_queue.empty():
            try:
                self.processing_queue.get_nowait()
                self.processing_queue.task_done()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Processing-Queue geleert: {cleared_count} Tasks entfernt")


async def main():
    """Hauptfunktion"""
    # Logging konfigurieren
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("pi_processing_service.log"),
        ],
    )

    logger.info("Starte Pi Processing Service...")

    # Service erstellen und starten
    service = PiProcessingService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Service durch Benutzer unterbrochen")
    except Exception as e:
        logger.error(f"Service-Fehler: {e}")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
