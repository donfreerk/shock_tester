"""
Phase-Shift-Calculator für Pi Processing Service

✅ KONSOLIDIERT: Diese Datei ist ein Wrapper um die zentrale suspension_core.egea Implementation.

EGEA-konforme Phase-Shift-Berechnung optimiert für Pi-Hardware.
Wrapper um den bestehenden PhaseShiftProcessor aus suspension_core mit zusätzlichen
Pi-spezifischen Optimierungen.

ARCHITEKTUR:
- Nutzt zentrale suspension_core.egea.PhaseShiftProcessor Implementation
- Fügt Pi-spezifische Performance-Optimierungen hinzu  
- Bietet Fallback-Implementation für Entwicklungsumgebungen
- Asynchrone API für bessere Integration in Pi Processing Service

MIGRATION STATUS: ✅ Imports korrigiert, nutzt zentrale Implementation
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Import des bestehenden Processors aus suspension_core
try:
    from suspension_core.egea import PhaseShiftProcessor
    EGEA_PROCESSOR_AVAILABLE = True
    logger.info("✅ Zentrale PhaseShiftProcessor erfolgreich importiert")
except ImportError as e:
    EGEA_PROCESSOR_AVAILABLE = False
    logger.warning(f"⚠️ Zentrale PhaseShiftProcessor nicht verfügbar: {e} - verwende Fallback-Implementierung")


class PhaseShiftCalculator:
    """
    Pi-optimierter Phase-Shift-Calculator
    
    Features:
    - Asynchrone Verarbeitung für bessere Performance
    - Memory-effiziente Algorithmen für Pi-Hardware
    - EGEA-konforme Berechnungen
    - Robuste Fehlerbehandlung
    - Performance-Monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den Phase-Shift-Calculator
        
        Args:
            config: Konfigurationsparameter
        """
        self.config = config or {}
        
        # EGEA-Parameter aus Konfiguration
        self.min_calc_freq = self.config.get("min_calc_freq", 6.0)
        self.max_calc_freq = self.config.get("max_calc_freq", 18.0)
        self.phase_threshold = self.config.get("phase_threshold", 35.0)
        self.delta_f = self.config.get("delta_f", 5.0)
        
        # Performance-Parameter für Pi
        self.use_optimized_algorithms = True
        self.memory_efficient_mode = True
        
        # Bestehenden EGEA-Processor initialisieren falls verfügbar
        if EGEA_PROCESSOR_AVAILABLE:
            self.egea_processor = PhaseShiftProcessor()
            logger.info("✅ Zentrale PhaseShiftProcessor-Implementierung wird verwendet")
        else:
            self.egea_processor = None
            logger.info("⚠️ PhaseShiftProcessor nicht verfügbar - verwende Fallback")
        
        # Performance-Tracking
        self.calculation_times = []
        self.calculations_count = 0
        
        logger.info("PhaseShiftCalculator initialisiert")
    
    async def calculate(self, 
                       platform_data: np.ndarray, 
                       force_data: np.ndarray, 
                       time_data: np.ndarray, 
                       static_weight: float) -> Dict[str, Any]:
        """
        Hauptfunktion für Phase-Shift-Berechnung
        
        Args:
            platform_data: Plattform-Positionsdaten
            force_data: Reifenkraft-Daten
            time_data: Zeitdaten
            static_weight: Statisches Gewicht
            
        Returns:
            Phase-Shift-Ergebnisse
        """
        start_time = time.perf_counter()
        
        try:
            logger.info("Starte Phase-Shift-Berechnung")
            
            # Input-Validierung
            if not self._validate_input_data(platform_data, force_data, time_data, static_weight):
                raise ValueError("Input-Datenvalidierung fehlgeschlagen")
            
            # Daten für Pi-optimierte Verarbeitung vorbereiten
            prepared_data = await self._prepare_data_for_processing(
                platform_data, force_data, time_data
            )
            
            # Phase-Shift-Berechnung durchführen
            if self.egea_processor:
                # Verwende bestehenden EGEA-Processor
                result = await self._calculate_with_egea_processor(
                    prepared_data["platform"], 
                    prepared_data["force"], 
                    prepared_data["time"], 
                    static_weight
                )
            else:
                # Fallback-Implementierung
                result = await self._calculate_fallback(
                    prepared_data["platform"], 
                    prepared_data["force"], 
                    prepared_data["time"], 
                    static_weight
                )
            
            # Post-Processing und Validierung
            validated_result = self._validate_and_enhance_result(result)
            
            # Performance-Tracking
            calculation_time = time.perf_counter() - start_time
            self.calculation_times.append(calculation_time)
            self.calculations_count += 1
            
            # Performance-Statistiken begrenzen (Memory-Optimierung)
            if len(self.calculation_times) > 100:
                self.calculation_times = self.calculation_times[-50:]
            
            logger.info(f"Phase-Shift-Berechnung abgeschlossen in {calculation_time:.3f}s")
            
            return validated_result
            
        except Exception as e:
            calculation_time = time.perf_counter() - start_time
            logger.error(f"Phase-Shift-Berechnungsfehler nach {calculation_time:.3f}s: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "min_phase_shift": None,
                "phase_shifts": [],
                "evaluation": "error",
                "processing_time": calculation_time
            }
    
    def _validate_input_data(self, platform_data: np.ndarray, force_data: np.ndarray, 
                           time_data: np.ndarray, static_weight: float) -> bool:
        """
        Validiert Input-Daten für Phase-Shift-Berechnung
        
        Args:
            platform_data: Plattform-Daten
            force_data: Kraft-Daten  
            time_data: Zeit-Daten
            static_weight: Statisches Gewicht
            
        Returns:
            True wenn Daten gültig
        """
        try:
            # Längen-Validierung
            if not (len(platform_data) == len(force_data) == len(time_data)):
                logger.error("Daten-Arrays haben unterschiedliche Längen")
                return False
            
            # Mindestanzahl Datenpunkte
            if len(time_data) < 100:
                logger.error(f"Zu wenige Datenpunkte: {len(time_data)} < 100")
                return False
            
            # Zeitdaten-Validierung
            if not np.all(np.diff(time_data) > 0):
                logger.error("Zeit-Array ist nicht monoton steigend")
                return False
            
            # Statisches Gewicht validieren
            if static_weight <= 0 or static_weight > 5000:  # 5000 N als Obergrenze
                logger.error(f"Ungültiges statisches Gewicht: {static_weight} N")
                return False
            
            # NaN/Inf-Werte prüfen
            for name, data in [("platform", platform_data), ("force", force_data), ("time", time_data)]:
                if np.any(np.isnan(data)) or np.any(np.isinf(data)):
                    logger.error(f"NaN/Inf-Werte in {name}-Daten gefunden")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler bei Input-Validierung: {e}")
            return False
    
    async def _prepare_data_for_processing(self, platform_data: np.ndarray, 
                                         force_data: np.ndarray, 
                                         time_data: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Bereitet Daten für Pi-optimierte Verarbeitung vor
        
        Args:
            platform_data: Rohe Plattform-Daten
            force_data: Rohe Kraft-Daten
            time_data: Rohe Zeit-Daten
            
        Returns:
            Vorbereitete Daten
        """
        try:
            # Async-Processing für bessere Responsiveness
            await asyncio.sleep(0)  # Yield control
            
            # Memory-effiziente Kopien erstellen
            platform = platform_data.copy() if self.memory_efficient_mode else platform_data
            force = force_data.copy() if self.memory_efficient_mode else force_data
            time = time_data.copy() if self.memory_efficient_mode else time_data
            
            # Zeit-Normalisierung (beginne bei 0)
            time = time - time[0]
            
            # Basis-Filterung für Rauschen-Reduzierung (Pi-optimiert)
            if self.use_optimized_algorithms:
                platform = self._apply_lightweight_filter(platform)
                force = self._apply_lightweight_filter(force)
            
            return {
                "platform": platform,
                "force": force, 
                "time": time
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Daten-Vorbereitung: {e}")
            raise
    
    def _apply_lightweight_filter(self, data: np.ndarray) -> np.ndarray:
        """
        Wendet leichtgewichtigen Filter für Pi-Hardware an
        
        Args:
            data: Input-Daten
            
        Returns:
            Gefilterte Daten
        """
        try:
            # Einfacher Moving-Average für Rauschen-Reduzierung
            # Optimiert für Pi (wenig Memory/CPU)
            window_size = min(5, len(data) // 20)  # Adaptive Fenstergröße
            
            if window_size >= 3:
                # Konvolution für Moving Average
                kernel = np.ones(window_size) / window_size
                filtered = np.convolve(data, kernel, mode='same')
                return filtered
            else:
                return data
                
        except Exception as e:
            logger.warning(f"Filter-Anwendung fehlgeschlagen: {e}")
            return data
    
    async def _calculate_with_egea_processor(self, platform_data: np.ndarray, 
                                           force_data: np.ndarray, 
                                           time_data: np.ndarray, 
                                           static_weight: float) -> Dict[str, Any]:
        """
        Berechnung mit bestehendem EGEA-Processor
        
        Args:
            platform_data: Plattform-Daten
            force_data: Kraft-Daten
            time_data: Zeit-Daten
            static_weight: Statisches Gewicht
            
        Returns:
            EGEA-Berechnungsresultat
        """
        try:
            # Async-Wrapper um synchronen EGEA-Processor
            await asyncio.sleep(0)  # Yield control
            
            # Bestehenden Processor aufrufen mit neuer API
            result = self.egea_processor.calculate_phase_shift_advanced(
                platform_position=platform_data,
                tire_force=force_data,
                time_array=time_data,
                static_weight=static_weight
            )
            
            return result
            
        except Exception as e:
            logger.error(f"EGEA-Processor-Fehler: {e}")
            raise
    
    async def _calculate_fallback(self, platform_data: np.ndarray, 
                                force_data: np.ndarray, 
                                time_data: np.ndarray, 
                                static_weight: float) -> Dict[str, Any]:
        """
        Fallback-Implementierung für Phase-Shift-Berechnung
        
        Args:
            platform_data: Plattform-Daten
            force_data: Kraft-Daten
            time_data: Zeit-Daten
            static_weight: Statisches Gewicht
            
        Returns:
            Fallback-Berechnungsresultat
        """
        try:
            logger.info("Verwende Fallback-Implementierung für Phase-Shift-Berechnung")
            
            # Vereinfachte Phase-Shift-Berechnung
            # (Für Produktionsumgebung sollte der EGEA-Processor verfügbar sein)
            
            # Sample Rate berechnen
            dt = np.mean(np.diff(time_data))
            sample_rate = 1.0 / dt
            
            # FFT für beide Signale
            platform_fft = np.fft.rfft(platform_data)
            force_fft = np.fft.rfft(force_data)
            frequencies = np.fft.rfftfreq(len(platform_data), dt)
            
            # Phase-Differenz berechnen
            phase_diff = np.angle(force_fft) - np.angle(platform_fft)
            
            # Phasen-Shift in Grad umwandeln
            phase_shifts_deg = np.degrees(phase_diff)
            
            # EGEA-relevanten Frequenzbereich filtern
            freq_mask = (frequencies >= self.min_calc_freq) & (frequencies <= self.max_calc_freq)
            relevant_phases = phase_shifts_deg[freq_mask]
            relevant_freqs = frequencies[freq_mask]
            
            # Minimale Phasenverschiebung finden
            if len(relevant_phases) > 0:
                min_phase_idx = np.argmin(np.abs(relevant_phases))
                min_phase_shift = relevant_phases[min_phase_idx]
                min_phase_freq = relevant_freqs[min_phase_idx]
            else:
                min_phase_shift = None
                min_phase_freq = None
            
            # Bewertung nach EGEA-Kriterien
            if min_phase_shift is not None:
                if abs(min_phase_shift) >= self.phase_threshold:
                    evaluation = "good"
                elif abs(min_phase_shift) >= 25.0:
                    evaluation = "acceptable"
                else:
                    evaluation = "poor"
            else:
                evaluation = "error"
            
            return {
                "success": True,
                "min_phase_shift": min_phase_shift,
                "min_phase_freq": min_phase_freq,
                "phase_shifts": relevant_phases.tolist() if len(relevant_phases) > 0 else [],
                "frequencies": relevant_freqs.tolist() if len(relevant_freqs) > 0 else [],
                "evaluation": evaluation,
                "passing": evaluation in ["good", "acceptable"],
                "sample_rate": sample_rate,
                "fallback_used": True
            }
            
        except Exception as e:
            logger.error(f"Fallback-Berechnungsfehler: {e}")
            raise
    
    def _validate_and_enhance_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validiert und erweitert Berechnungsresultat
        
        Args:
            result: Rohes Berechnungsresultat
            
        Returns:
            Validiertes und erweitertes Resultat
        """
        try:
            # Basis-Validierung
            if not isinstance(result, dict):
                raise ValueError("Resultat ist kein Dictionary")
            
            # Erweitere Resultat um zusätzliche Metadaten
            enhanced_result = result.copy()
            enhanced_result.update({
                "calculator_version": "1.0.0",
                "calculation_timestamp": time.time(),
                "egea_compliant": True,
                "pi_optimized": True
            })
            
            # Performance-Statistiken hinzufügen
            if self.calculation_times:
                enhanced_result["performance_stats"] = {
                    "avg_calculation_time": np.mean(self.calculation_times),
                    "total_calculations": self.calculations_count,
                    "last_calculation_time": self.calculation_times[-1] if self.calculation_times else None
                }
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Resultat-Validierung fehlgeschlagen: {e}")
            # Gib Minimal-Resultat zurück
            return {
                "success": False,
                "error": f"Resultat-Validierung fehlgeschlagen: {e}",
                "min_phase_shift": None,
                "evaluation": "error"
            }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Gibt Performance-Statistiken zurück
        
        Returns:
            Performance-Statistiken
        """
        if not self.calculation_times:
            return {"no_data": True}
        
        return {
            "total_calculations": self.calculations_count,
            "avg_time": np.mean(self.calculation_times),
            "min_time": np.min(self.calculation_times),
            "max_time": np.max(self.calculation_times),
            "last_time": self.calculation_times[-1],
            "egea_processor_available": EGEA_PROCESSOR_AVAILABLE
        }
    
    def reset_performance_stats(self):
        """Setzt Performance-Statistiken zurück"""
        self.calculation_times.clear()
        self.calculations_count = 0
        logger.info("Performance-Statistiken zurückgesetzt")
