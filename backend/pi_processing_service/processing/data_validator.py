"""
Data Validator für Pi Processing Service

Validiert eingehende Rohdaten auf Korrektheit, Vollständigkeit und EGEA-Konformität.
Optimiert für Pi-Hardware mit memory-effizienten Algorithmen.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Exception für Datenvalidierungs-Fehler"""
    pass


class DataValidator:
    """
    Validator für Fahrwerkstester-Rohdaten
    
    Features:
    - EGEA-konforme Datenvalidierung
    - Memory-effiziente Validierung für Pi
    - Umfassende Qualitätsprüfung
    - Detaillierte Fehlerberichte
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den Data Validator
        
        Args:
            config: Konfigurationsparameter
        """
        self.config = config or {}
        
        # Validierungs-Parameter
        self.min_data_points = self.config.get("min_data_points", 100)
        self.max_data_points = self.config.get("max_data_points", 100000)
        self.min_test_duration = self.config.get("min_test_duration", 10.0)  # Sekunden
        self.max_test_duration = self.config.get("max_test_duration", 300.0)  # Sekunden
        
        # EGEA-spezifische Parameter
        self.min_sample_rate = self.config.get("min_sample_rate", 50.0)  # Hz
        self.max_sample_rate = self.config.get("max_sample_rate", 2000.0)  # Hz
        self.min_static_weight = self.config.get("min_static_weight", 50.0)  # N
        self.max_static_weight = self.config.get("max_static_weight", 5000.0)  # N
        
        # Signalqualitäts-Parameter
        self.max_noise_ratio = self.config.get("max_noise_ratio", 0.5)
        self.min_signal_amplitude = self.config.get("min_signal_amplitude", 0.1)
        
        # Performance-Tracking
        self.validation_count = 0
        self.validation_failures = 0
        
        logger.info("DataValidator initialisiert")
    
    def validate_raw_data(self, raw_data: Dict[str, Any]) -> bool:
        """
        Hauptvalidierung für Rohdaten
        
        Args:
            raw_data: Rohdaten-Dictionary vom Hardware Bridge
            
        Returns:
            True wenn Daten gültig
            
        Raises:
            DataValidationError: Bei Validierungsfehlern
        """
        try:
            self.validation_count += 1
            logger.info(f"Starte Datenvalidierung #{self.validation_count}")
            
            # 1. Struktur-Validierung
            self._validate_data_structure(raw_data)
            
            # 2. Metadaten-Validierung
            self._validate_metadata(raw_data)
            
            # 3. Messdaten-Validierung
            measurement_data = raw_data.get("raw_data", [])
            self._validate_measurement_data(measurement_data)
            
            # 4. Signalqualitäts-Validierung
            self._validate_signal_quality(measurement_data)
            
            # 5. EGEA-Konformitäts-Validierung
            self._validate_egea_compliance(raw_data, measurement_data)
            
            logger.info("Datenvalidierung erfolgreich abgeschlossen")
            return True
            
        except DataValidationError as e:
            self.validation_failures += 1
            logger.error(f"Datenvalidierung fehlgeschlagen: {e}")
            raise
        except Exception as e:
            self.validation_failures += 1
            logger.error(f"Unerwarteter Validierungsfehler: {e}")
            raise DataValidationError(f"Unerwarteter Validierungsfehler: {e}")
    
    def _validate_data_structure(self, raw_data: Dict[str, Any]):
        """
        Validiert die grundlegende Datenstruktur
        
        Args:
            raw_data: Rohdaten-Dictionary
            
        Raises:
            DataValidationError: Bei Strukturfehlern
        """
        # Pflichtfelder prüfen
        required_fields = ["test_id", "position", "raw_data", "timestamp"]
        missing_fields = [field for field in required_fields if field not in raw_data]
        
        if missing_fields:
            raise DataValidationError(f"Fehlende Pflichtfelder: {missing_fields}")
        
        # Datentypen prüfen
        if not isinstance(raw_data["test_id"], str):
            raise DataValidationError("test_id muss string sein")
        
        if not isinstance(raw_data["position"], str):
            raise DataValidationError("position muss string sein")
        
        if not isinstance(raw_data["raw_data"], list):
            raise DataValidationError("raw_data muss list sein")
        
        if not isinstance(raw_data["timestamp"], (int, float)):
            raise DataValidationError("timestamp muss numerisch sein")
        
        # Position validieren
        valid_positions = ["front_left", "front_right", "rear_left", "rear_right"]
        if raw_data["position"] not in valid_positions:
            raise DataValidationError(f"Ungültige Position: {raw_data['position']}")
    
    def _validate_metadata(self, raw_data: Dict[str, Any]):
        """
        Validiert Metadaten
        
        Args:
            raw_data: Rohdaten-Dictionary
            
        Raises:
            DataValidationError: Bei Metadaten-Fehlern
        """
        # Zeitstempel-Validierung
        timestamp = raw_data["timestamp"]
        current_time = time.time()
        
        # Zeitstempel sollte nicht zu weit in der Zukunft oder Vergangenheit liegen
        if timestamp > current_time + 3600:  # 1 Stunde Zukunft
            raise DataValidationError("Zeitstempel liegt zu weit in der Zukunft")
        
        if timestamp < current_time - 86400:  # 1 Tag Vergangenheit
            raise DataValidationError("Zeitstempel liegt zu weit in der Vergangenheit")
        
        # Test-Duration validieren (falls vorhanden)
        if "duration" in raw_data:
            duration = raw_data["duration"]
            if not isinstance(duration, (int, float)):
                raise DataValidationError("duration muss numerisch sein")
            
            if duration < self.min_test_duration:
                raise DataValidationError(f"Test zu kurz: {duration}s < {self.min_test_duration}s")
            
            if duration > self.max_test_duration:
                raise DataValidationError(f"Test zu lang: {duration}s > {self.max_test_duration}s")
        
        # Static Weight validieren (falls vorhanden)
        if "static_weight" in raw_data:
            static_weight = raw_data["static_weight"]
            if not isinstance(static_weight, (int, float)):
                raise DataValidationError("static_weight muss numerisch sein")
            
            if static_weight < self.min_static_weight:
                raise DataValidationError(f"Static Weight zu niedrig: {static_weight}N")
            
            if static_weight > self.max_static_weight:
                raise DataValidationError(f"Static Weight zu hoch: {static_weight}N")
    
    def _validate_measurement_data(self, measurement_data: List[Dict[str, Any]]):
        """
        Validiert die eigentlichen Messdaten
        
        Args:
            measurement_data: Liste der Messpunkte
            
        Raises:
            DataValidationError: Bei Messdaten-Fehlern
        """
        # Anzahl Datenpunkte prüfen
        data_count = len(measurement_data)
        
        if data_count < self.min_data_points:
            raise DataValidationError(f"Zu wenige Datenpunkte: {data_count} < {self.min_data_points}")
        
        if data_count > self.max_data_points:
            raise DataValidationError(f"Zu viele Datenpunkte: {data_count} > {self.max_data_points}")
        
        if data_count == 0:
            raise DataValidationError("Keine Messdaten vorhanden")
        
        # Erste und letzte Messpunkte detailliert prüfen
        first_point = measurement_data[0]
        last_point = measurement_data[-1]
        
        # Pflichtfelder in Messpunkten
        required_fields = ["timestamp", "platform_position", "tire_force"]
        
        for i, point in enumerate([first_point, last_point]):
            missing_fields = [field for field in required_fields if field not in point]
            if missing_fields:
                idx_name = "ersten" if i == 0 else "letzten"
                raise DataValidationError(f"Fehlende Felder im {idx_name} Messpunkt: {missing_fields}")
        
        # Stichprobenweise Validierung (Performance-Optimierung für Pi)
        sample_indices = self._get_sample_indices(data_count)
        
        for idx in sample_indices:
            point = measurement_data[idx]
            
            # Datentypen prüfen
            for field in required_fields:
                if field not in point:
                    raise DataValidationError(f"Feld '{field}' fehlt in Messpunkt {idx}")
                
                value = point[field]
                if not isinstance(value, (int, float)):
                    raise DataValidationError(f"Feld '{field}' in Messpunkt {idx} ist nicht numerisch")
                
                # NaN/Inf-Werte prüfen
                if np.isnan(value) or np.isinf(value):
                    raise DataValidationError(f"NaN/Inf-Wert in Feld '{field}' bei Messpunkt {idx}")
        
        # Zeitreihen-Validierung
        self._validate_time_series(measurement_data, sample_indices)
    
    def _get_sample_indices(self, data_count: int) -> List[int]:
        """
        Berechnet Stichproben-Indices für effiziente Validierung
        
        Args:
            data_count: Anzahl Datenpunkte
            
        Returns:
            Liste der zu prüfenden Indices
        """
        # Pi-optimiert: Prüfe nicht alle Punkte, sondern Stichproben
        if data_count <= 100:
            # Bei wenigen Punkten: alle prüfen
            return list(range(data_count))
        elif data_count <= 1000:
            # Bei mittlerer Anzahl: jeden 10. Punkt
            return list(range(0, data_count, 10))
        else:
            # Bei vielen Punkten: 100 gleichmäßig verteilte Punkte
            step = data_count // 100
            return list(range(0, data_count, step))
    
    def _validate_time_series(self, measurement_data: List[Dict[str, Any]], sample_indices: List[int]):
        """
        Validiert Zeitreihen-spezifische Eigenschaften
        
        Args:
            measurement_data: Messdaten
            sample_indices: Zu prüfende Indices
            
        Raises:
            DataValidationError: Bei Zeitreihen-Fehlern
        """
        # Zeitstempel extrahieren (nur Stichproben)
        timestamps = []
        for idx in sample_indices:
            timestamps.append(measurement_data[idx]["timestamp"])
        
        # Monotonie prüfen (Zeit muss aufsteigend sein)
        for i in range(1, len(timestamps)):
            if timestamps[i] <= timestamps[i-1]:
                raise DataValidationError(f"Zeitstempel nicht monoton bei Index {sample_indices[i]}")
        
        # Sample Rate schätzen
        if len(timestamps) >= 2:
            time_diffs = np.diff(timestamps)
            avg_dt = np.mean(time_diffs)
            estimated_sample_rate = 1.0 / avg_dt
            
            if estimated_sample_rate < self.min_sample_rate:
                raise DataValidationError(f"Sample Rate zu niedrig: {estimated_sample_rate:.1f}Hz")
            
            if estimated_sample_rate > self.max_sample_rate:
                raise DataValidationError(f"Sample Rate zu hoch: {estimated_sample_rate:.1f}Hz")
        
        # Gesamtdauer prüfen
        if len(timestamps) >= 2:
            total_duration = timestamps[-1] - timestamps[0]
            
            if total_duration < self.min_test_duration:
                raise DataValidationError(f"Test-Duration zu kurz: {total_duration:.1f}s")
            
            if total_duration > self.max_test_duration:
                raise DataValidationError(f"Test-Duration zu lang: {total_duration:.1f}s")
    
    def _validate_signal_quality(self, measurement_data: List[Dict[str, Any]]):
        """
        Validiert Signalqualität der Messdaten
        
        Args:
            measurement_data: Messdaten
            
        Raises:
            DataValidationError: Bei Signalqualitäts-Problemen
        """
        if len(measurement_data) < 10:
            return  # Zu wenig Daten für Qualitätsprüfung
        
        # Stichprobe für Performance
        sample_size = min(1000, len(measurement_data))
        step = len(measurement_data) // sample_size
        sample_indices = list(range(0, len(measurement_data), step))[:sample_size]
        
        # Signale extrahieren
        platform_values = []
        force_values = []
        
        for idx in sample_indices:
            point = measurement_data[idx]
            platform_values.append(point.get("platform_position", 0))
            force_values.append(point.get("tire_force", 0))
        
        platform_array = np.array(platform_values)
        force_array = np.array(force_values)
        
        # Signal-Amplitude prüfen
        platform_amplitude = np.max(platform_array) - np.min(platform_array)
        force_amplitude = np.max(force_array) - np.min(force_array)
        
        if platform_amplitude < self.min_signal_amplitude:
            raise DataValidationError(f"Platform-Signal-Amplitude zu niedrig: {platform_amplitude}")
        
        if force_amplitude < self.min_signal_amplitude:
            raise DataValidationError(f"Force-Signal-Amplitude zu niedrig: {force_amplitude}")
        
        # Signalqualität prüfen (vereinfacht)
        platform_std = np.std(platform_array)
        force_std = np.std(force_array)
        
        platform_mean = np.mean(np.abs(platform_array))
        force_mean = np.mean(np.abs(force_array))
        
        # Rauschen-zu-Signal-Verhältnis (vereinfacht)
        if platform_mean > 0:
            platform_noise_ratio = platform_std / platform_mean
            if platform_noise_ratio > self.max_noise_ratio:
                logger.warning(f"Platform-Signal möglicherweise verrauscht: {platform_noise_ratio:.3f}")
        
        if force_mean > 0:
            force_noise_ratio = force_std / force_mean
            if force_noise_ratio > self.max_noise_ratio:
                logger.warning(f"Force-Signal möglicherweise verrauscht: {force_noise_ratio:.3f}")
    
    def _validate_egea_compliance(self, raw_data: Dict[str, Any], measurement_data: List[Dict[str, Any]]):
        """
        Validiert EGEA-Konformität
        
        Args:
            raw_data: Komplette Rohdaten
            measurement_data: Messdaten
            
        Raises:
            DataValidationError: Bei EGEA-Konformitäts-Problemen
        """
        # EGEA erfordert mindestens 20 Sekunden Testdauer
        if len(measurement_data) >= 2:
            first_time = measurement_data[0]["timestamp"]
            last_time = measurement_data[-1]["timestamp"]
            duration = last_time - first_time
            
            if duration < 20.0:
                logger.warning(f"Test-Duration unter EGEA-Empfehlung: {duration:.1f}s < 20s")
        
        # Prüfe ob alle für EGEA nötigen Felder vorhanden sind
        required_egea_fields = ["platform_position", "tire_force"]
        
        # Stichprobe prüfen
        sample_point = measurement_data[len(measurement_data) // 2]  # Mittelpunkt
        missing_egea_fields = [field for field in required_egea_fields if field not in sample_point]
        
        if missing_egea_fields:
            raise DataValidationError(f"Fehlende EGEA-Felder: {missing_egea_fields}")
        
        # Static Weight sollte für EGEA vorhanden sein
        if "static_weight" not in raw_data:
            logger.warning("Static Weight nicht verfügbar - EGEA-Analyse möglicherweise unvollständig")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Gibt Validierungs-Statistiken zurück
        
        Returns:
            Validierungs-Statistiken
        """
        return {
            "total_validations": self.validation_count,
            "validation_failures": self.validation_failures,
            "success_rate": (self.validation_count - self.validation_failures) / self.validation_count 
                           if self.validation_count > 0 else 0,
            "configuration": {
                "min_data_points": self.min_data_points,
                "max_data_points": self.max_data_points,
                "min_test_duration": self.min_test_duration,
                "max_test_duration": self.max_test_duration
            }
        }
    
    def reset_stats(self):
        """Setzt Validierungs-Statistiken zurück"""
        self.validation_count = 0
        self.validation_failures = 0
        logger.info("Validierungs-Statistiken zurückgesetzt")
