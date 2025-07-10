#!/usr/bin/env python3
"""
Test Controller Service Phase-Shift-Processor

✅ KONSOLIDIERT: Nutzt zentrale suspension_core.egea Implementation

Dieser Service-spezifische Wrapper stellt eine angepasste API für den
Test Controller Service bereit, während er die zentrale, getestete 
EGEA-Implementation aus suspension_core verwendet.

ARCHITEKTUR:
- Wrapper um suspension_core.egea.PhaseShiftProcessor
- Service-spezifische API-Anpassungen
- Test-Controller-spezifische Validierung
- Kompatibilität zu bestehenden Test-Workflows

MIGRATION STATUS: ✅ Ersetzt redundante Implementation
"""

import logging
import time
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Zentrale EGEA-Implementation importieren
try:
    from suspension_core.egea import PhaseShiftProcessor as CentralPhaseShiftProcessor
    from suspension_core.config import ConfigManager
    EGEA_AVAILABLE = True
    logger.info("✅ Zentrale PhaseShiftProcessor erfolgreich importiert")
except ImportError as e:
    EGEA_AVAILABLE = False
    logger.error(f"❌ Zentrale PhaseShiftProcessor nicht verfügbar: {e}")


class PhaseShiftProcessor:
    """
    Test Controller Service Phase-Shift-Processor
    
    Wrapper um die zentrale suspension_core.egea.PhaseShiftProcessor
    Implementation mit Test-Controller-spezifischen Anpassungen.
    
    Features:
    - Test-Controller-kompatible API
    - Integration mit bestehenden Test-Workflows
    - Automatische Konfiguration aus Test-Parametern
    - Erweiterte Validierung für Test-Controller-Kontext
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den Test Controller Phase-Shift-Processor
        
        Args:
            config: Optional Konfiguration, sonst aus ConfigManager
        """
        if not EGEA_AVAILABLE:
            raise ImportError(
                "Zentrale PhaseShiftProcessor nicht verfügbar. "
                "Installieren Sie suspension_core oder prüfen Sie PYTHONPATH."
            )
        
        # Konfiguration laden
        if config:
            self.config = config
        else:
            config_manager = ConfigManager()
            self.config = {
                "min_freq": config_manager.get("egea.frequency_range.min", 6.0),
                "max_freq": config_manager.get("egea.frequency_range.max", 25.0),
                "phase_threshold": config_manager.get("egea.phase_threshold", 35.0),
                "delta_f": config_manager.get("egea.delta_f", 5.0),
                "rfst_fmax": config_manager.get("egea.rfst_fmax", 25.0),
                "rfst_fmin": config_manager.get("egea.rfst_fmin", 25.0)
            }
        
        # Zentrale EGEA-Implementation initialisieren
        self.egea_processor = CentralPhaseShiftProcessor()
        
        # Test-Controller-spezifische Parameter
        self.min_freq = self.config["min_freq"]
        self.max_freq = self.config["max_freq"]
        self.delta_f = self.config["delta_f"]
        self.rfst_fmax = self.config["rfst_fmax"]
        self.rfst_fmin = self.config["rfst_fmin"]
        
        logger.info("✅ Test Controller PhaseShiftProcessor initialisiert")

    def calculate_phase_shift(
        self, 
        platform_position: List[float], 
        tire_force: List[float], 
        time_array: List[float], 
        static_weight: float
    ) -> Dict[str, Any]:
        """
        Berechnet den Phasenversatz zwischen Plattformposition und Reifenkontaktkraft.
        
        KOMPATIBILITÄTS-API: Behält die ursprüngliche API des Test Controllers bei,
        delegiert aber an die zentrale EGEA-Implementation.

        Args:
            platform_position: Array der Plattformpositionen
            tire_force: Array der Reifenkontaktkräfte
            time_array: Array der Zeitwerte
            static_weight: Statisches Radgewicht (Fst)

        Returns:
            dict: Phasenverschiebungsdaten inkl. Minimalwert (Test-Controller-kompatibel)
        """
        try:
            logger.info("Starte Phase-Shift-Berechnung mit zentraler EGEA-Implementation")
            
            # Input-Validierung für Test-Controller-Kontext
            if not self._validate_test_controller_input(
                platform_position, tire_force, time_array, static_weight
            ):
                return self._create_error_result("Input-Validierung fehlgeschlagen")
            
            # Konvertierung zu NumPy für zentrale API
            platform_array = np.array(platform_position)
            force_array = np.array(tire_force)
            time_array = np.array(time_array)
            
            # Zentrale EGEA-Implementation aufrufen
            egea_result = self.egea_processor.calculate_phase_shift_advanced(
                platform_position=platform_array,
                tire_force=force_array,
                time_array=time_array,
                static_weight=static_weight
            )
            
            # Ergebnis zu Test-Controller-kompatiblem Format konvertieren
            return self._convert_to_test_controller_format(egea_result)
            
        except Exception as e:
            logger.error(f"❌ Phase-Shift-Berechnung fehlgeschlagen: {e}")
            return self._create_error_result(str(e))

    def _validate_test_controller_input(
        self, 
        platform_position: List[float], 
        tire_force: List[float], 
        time_array: List[float], 
        static_weight: float
    ) -> bool:
        """
        Test-Controller-spezifische Input-Validierung
        
        Args:
            platform_position: Plattform-Positionsdaten
            tire_force: Kraft-Daten
            time_array: Zeit-Daten
            static_weight: Statisches Gewicht
            
        Returns:
            True wenn gültig für Test-Controller
        """
        try:
            # Basis-Validierung
            if not (len(platform_position) == len(tire_force) == len(time_array)):
                logger.error("Ungleiche Array-Längen")
                return False
            
            if len(time_array) < 100:
                logger.error("Zu wenige Datenpunkte für Test-Controller")
                return False
            
            # Test-Controller-spezifische Validierung
            if static_weight <= 0 or static_weight > 5000:
                logger.error(f"Statisches Gewicht außerhalb Test-Controller-Bereich: {static_weight} N")
                return False
            
            # Datenqualität für Tests prüfen
            platform_range = max(platform_position) - min(platform_position)
            if platform_range < 1.0:  # Mindestens 1mm Amplitude
                logger.error("Platform-Amplitude zu gering für Test-Controller")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validierung fehlgeschlagen: {e}")
            return False

    def _convert_to_test_controller_format(self, egea_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Konvertiert EGEA-Ergebnis zu Test-Controller-kompatiblem Format
        
        Args:
            egea_result: Ergebnis der zentralen EGEA-Implementation
            
        Returns:
            Test-Controller-kompatibles Ergebnis-Dictionary
        """
        try:
            # Test-Controller erwartet diese spezifische Struktur
            return {
                "valid": egea_result.get("success", False),
                "min_phase_shift": egea_result.get("min_phase_shift", 0.0),
                "min_phase_freq": egea_result.get("min_phase_frequency", 0.0),
                "phase_shifts": egea_result.get("all_phase_shifts", []),
                "frequencies": egea_result.get("frequencies", []),
                
                # Erweiterte Metadaten von zentraler Implementation
                "evaluation": egea_result.get("evaluation", "unknown"),
                "processing_time": egea_result.get("processing_time", 0.0),
                "valid_periods_count": egea_result.get("valid_periods_count", 0),
                
                # Test-Controller-spezifische Flags
                "egea_compliant": True,
                "central_implementation_used": True
            }
            
        except Exception as e:
            logger.error(f"Format-Konvertierung fehlgeschlagen: {e}")
            return self._create_error_result(f"Format-Konvertierung fehlgeschlagen: {e}")

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """
        Erstellt Test-Controller-kompatibles Error-Result
        
        Args:
            error_message: Fehlernachricht
            
        Returns:
            Error-Result im Test-Controller-Format
        """
        return {
            "valid": False,
            "min_phase_shift": 0.0,
            "min_phase_freq": 0.0,
            "phase_shifts": [],
            "frequencies": [],
            "error": error_message,
            "egea_compliant": False,
            "central_implementation_used": False
        }

    @staticmethod
    def evaluate_phase_shift(phase_data: Dict[str, Any], vehicle_type: str) -> Dict[str, Any]:
        """
        Bewertet die Phasenverschiebung nach EGEA-Kriterien.
        
        KOMPATIBILITÄTS-METHODE: Behält Test-Controller-API bei.

        Args:
            phase_data: Ergebnis der Phasenverschiebungsberechnung
            vehicle_type: Fahrzeugtyp (PKW, LKW, etc.)

        Returns:
            dict: Bewertungsergebnis (Test-Controller-kompatibel)
        """
        try:
            # Wenn keine gültigen Daten vorliegen
            if not phase_data.get("valid", False):
                return {
                    "passed": False,
                    "quality_index": 0,
                    "min_phase_shift": 0,
                    "min_phase_freq": 0,
                    "error": phase_data.get("error", "Ungültige Phasenverschiebungsdaten")
                }

            # Schwellenwerte je nach Fahrzeugtyp (EGEA-konform)
            thresholds = {
                "PKW": 35.0,    # M1-Fahrzeuge
                "LKW": 30.0,    # N1-Fahrzeuge  
                "M1": 35.0,     # Alternative Bezeichnung
                "N1": 30.0,     # Alternative Bezeichnung
                "default": 35.0
            }

            threshold = thresholds.get(vehicle_type.upper(), thresholds["default"])
            min_phase_shift = phase_data.get("min_phase_shift", 0.0)
            min_phase_freq = phase_data.get("min_phase_freq", 0.0)

            # EGEA-konforme Bewertung
            passed = min_phase_shift >= threshold
            quality_index = (min_phase_shift / threshold) * 100 if threshold > 0 else 0
            quality_index = min(100, max(0, quality_index))

            return {
                "passed": passed,
                "quality_index": float(quality_index),
                "min_phase_shift": float(min_phase_shift),
                "min_phase_freq": float(min_phase_freq),
                "threshold": float(threshold),
                "vehicle_type": vehicle_type,
                "egea_compliant": True
            }
            
        except Exception as e:
            logger.error(f"Bewertung fehlgeschlagen: {e}")
            return {
                "passed": False,
                "quality_index": 0,
                "min_phase_shift": 0,
                "min_phase_freq": 0,
                "error": f"Bewertung fehlgeschlagen: {e}"
            }

    @staticmethod
    def calculate_rigidity(force_amplitude: float, platform_amplitude: float) -> float:
        """
        Berechnet die Steifigkeit aus Kraftamplitude und Plattformamplitude.
        
        KOMPATIBILITÄTS-METHODE: Behält Test-Controller-API bei.

        Args:
            force_amplitude: Amplitude der Reifenkontaktkraft in N
            platform_amplitude: Amplitude der Plattformbewegung in mm

        Returns:
            float: Steifigkeit in N/mm
        """
        if platform_amplitude <= 0:
            logger.warning("Platform-Amplitude ist 0 oder negativ")
            return 0.0

        rigidity = force_amplitude / platform_amplitude
        return float(rigidity)

    @staticmethod
    def calculate_relative_force_amplitude(
        max_force: float, 
        min_force: float, 
        static_weight: float
    ) -> float:
        """
        Berechnet die relative Kraftamplitude im Verhältnis zum statischen Gewicht.
        
        KOMPATIBILITÄTS-METHODE: Behält Test-Controller-API bei.

        Args:
            max_force: Maximale Kraft in N
            min_force: Minimale Kraft in N
            static_weight: Statisches Gewicht in N

        Returns:
            float: Relative Kraftamplitude in Prozent
        """
        if static_weight <= 0:
            logger.warning("Statisches Gewicht ist 0 oder negativ")
            return 0.0

        force_amplitude = (max_force - min_force) / 2
        relative_amplitude = (force_amplitude / static_weight) * 100

        return float(relative_amplitude)


# Für Backwards-Kompatibilität: Alias für alte Imports
TestControllerPhaseShiftProcessor = PhaseShiftProcessor


# Information bei Import
if __name__ != "__main__":
    logger.info("✅ Test Controller PhaseShiftProcessor geladen (nutzt zentrale EGEA-Implementation)")
