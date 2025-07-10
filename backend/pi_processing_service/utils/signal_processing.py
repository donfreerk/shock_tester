"""
Signal Processing Utilities für Pi Processing Service

Enthält alle Funktionen für:
- Datenvorverarbeitung
- Sinuskurven-Generierung für GUI
- Frequenzanalyse
- Signal-Filterung

Optimiert für Pi-Hardware mit memory-effizienten Algorithmen.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


class SignalProcessor:
    """
    Signal Processing Utilities für Fahrwerkstester
    
    Features:
    - Memory-effiziente Algorithmen für Pi
    - Frequenzanalyse mit FFT
    - Sinuskurven-Generierung für GUI
    - Adaptive Filterung
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den Signal Processor
        
        Args:
            config: Konfigurationsparameter
        """
        self.config = config or {}
        
        # Filter-Konfiguration
        self.filter_enabled = self.config.get("filter_enabled", True)
        self.lowpass_cutoff = self.config.get("lowpass_cutoff", 30.0)  # Hz
        self.highpass_cutoff = self.config.get("highpass_cutoff", 1.0)  # Hz
        
        # Memory-Optimierung für Pi
        self.use_memory_efficient_mode = True
        self.max_fft_length = 16384  # Begrenzt FFT-Größe für Pi
        
        logger.info("SignalProcessor initialisiert")
    
    def preprocess_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vorverarbeitung der Rohdaten für Phase-Shift-Berechnung
        
        Args:
            raw_data: Rohdaten vom Hardware Bridge
            
        Returns:
            Vorverarbeitete Daten für Phase-Shift-Calculator
        """
        try:
            logger.info("Starte Datenvorverarbeitung")
            
            # Messdaten extrahieren
            measurement_data = raw_data.get("raw_data", [])
            
            if not measurement_data:
                raise ValueError("Keine Messdaten vorhanden")
            
            # Arrays erstellen
            time_data = []
            platform_data = []
            force_data = []
            
            for point in measurement_data:
                time_data.append(point.get("timestamp", 0))
                platform_data.append(point.get("platform_position", 0))
                force_data.append(point.get("tire_force", 0))
            
            # Zu NumPy-Arrays konvertieren
            time_array = np.array(time_data)
            platform_array = np.array(platform_data)
            force_array = np.array(force_data)
            
            # Zeit normalisieren (beginne bei 0)
            time_array = time_array - time_array[0]
            
            # Sample Rate berechnen
            dt = np.mean(np.diff(time_array)) if len(time_array) > 1 else 0.01
            sample_rate = 1.0 / dt
            
            # Filterung anwenden falls aktiviert
            if self.filter_enabled:
                platform_array = self._apply_filter(platform_array, sample_rate)
                force_array = self._apply_filter(force_array, sample_rate)
            
            # Static Weight extrahieren
            static_weight = raw_data.get("static_weight", self._estimate_static_weight(force_array))
            
            return {
                "time_data": time_array,
                "platform_data": platform_array,
                "force_data": force_array,
                "static_weight": static_weight,
                "sample_rate": sample_rate,
                "duration": time_array[-1] if len(time_array) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Datenvorverarbeitung: {e}")
            raise
    
    def _apply_filter(self, data: np.ndarray, sample_rate: float) -> np.ndarray:
        """
        Wendet adaptive Filterung auf Signaldaten an
        
        Args:
            data: Input-Signaldaten
            sample_rate: Sample-Rate in Hz
            
        Returns:
            Gefilterte Signaldaten
        """
        try:
            if len(data) < 10:
                return data  # Zu wenig Daten für Filterung
            
            # Nyquist-Frequenz
            nyquist = sample_rate / 2.0
            
            # Filter-Parameter anpassen an Sample-Rate
            low_cutoff = min(self.lowpass_cutoff, nyquist * 0.8)
            high_cutoff = max(self.highpass_cutoff, 0.1)
            
            filtered_data = data.copy()
            
            # Hochpass-Filter (entfernt DC-Offset)
            if high_cutoff < nyquist:
                try:
                    sos_high = signal.butter(2, high_cutoff / nyquist, 
                                           btype='high', output='sos')
                    filtered_data = signal.sosfilt(sos_high, filtered_data)
                except Exception as e:
                    logger.warning(f"Hochpass-Filter fehlgeschlagen: {e}")
            
            # Tiefpass-Filter (entfernt hochfrequentes Rauschen)
            if low_cutoff < nyquist:
                try:
                    sos_low = signal.butter(2, low_cutoff / nyquist, 
                                          btype='low', output='sos')
                    filtered_data = signal.sosfilt(sos_low, filtered_data)
                except Exception as e:
                    logger.warning(f"Tiefpass-Filter fehlgeschlagen: {e}")
            
            return filtered_data
            
        except Exception as e:
            logger.warning(f"Filter-Anwendung fehlgeschlagen: {e}")
            return data  # Gib ungefilterte Daten zurück
    
    def _estimate_static_weight(self, force_data: np.ndarray) -> float:
        """
        Schätzt statisches Gewicht aus Kraftdaten
        
        Args:
            force_data: Kraft-Messdaten
            
        Returns:
            Geschätztes statisches Gewicht
        """
        try:
            # Verwende Median für robuste Schätzung
            estimated_weight = np.median(force_data)
            
            # Plausibilitätsprüfung
            if estimated_weight < 50 or estimated_weight > 5000:
                logger.warning(f"Unplausibles geschätztes Gewicht: {estimated_weight}N")
                return 500.0  # Fallback-Wert
            
            return float(estimated_weight)
            
        except Exception as e:
            logger.warning(f"Static Weight Schätzung fehlgeschlagen: {e}")
            return 500.0  # Fallback-Wert
    
    def generate_sine_curves(self, platform_data: np.ndarray, 
                           force_data: np.ndarray, 
                           time_data: np.ndarray) -> Dict[str, Any]:
        """
        Generiert vollständige Sinuskurven für GUI-Anzeige
        
        Args:
            platform_data: Plattform-Positionsdaten
            force_data: Reifenkraft-Daten
            time_data: Zeitdaten
            
        Returns:
            Sinuskurven-Daten für GUI
        """
        try:
            logger.info("Generiere Sinuskurven für GUI")
            
            # Sample-Rate berechnen
            dt = np.mean(np.diff(time_data)) if len(time_data) > 1 else 0.01
            sample_rate = 1.0 / dt
            duration = time_data[-1] - time_data[0] if len(time_data) > 0 else 0
            
            # Für Pi: Memory-effiziente Konvertierung zu Listen
            if self.use_memory_efficient_mode:
                # Reduziere Datenpunkte falls zu viele (für GUI-Performance)
                max_gui_points = 10000
                if len(time_data) > max_gui_points:
                    # Gleichmäßiges Downsampling
                    step = len(time_data) // max_gui_points
                    indices = np.arange(0, len(time_data), step)
                    
                    time_gui = time_data[indices]
                    platform_gui = platform_data[indices]
                    force_gui = force_data[indices]
                else:
                    time_gui = time_data
                    platform_gui = platform_data
                    force_gui = force_data
            else:
                time_gui = time_data
                platform_gui = platform_data
                force_gui = force_data
            
            return {
                "time": time_gui.tolist(),
                "platform_position": platform_gui.tolist(),
                "tire_force": force_gui.tolist(),
                "sample_rate": sample_rate,
                "duration": duration,
                "data_points": len(time_gui),
                "downsampled": len(time_gui) != len(time_data)
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Sinuskurven-Generierung: {e}")
            return {
                "time": [],
                "platform_position": [],
                "tire_force": [],
                "sample_rate": 0,
                "duration": 0,
                "error": str(e)
            }
    
    def analyze_frequency_content(self, platform_data: np.ndarray, 
                                force_data: np.ndarray, 
                                time_data: np.ndarray) -> Dict[str, Any]:
        """
        Führt umfassende Frequenzanalyse durch
        
        Args:
            platform_data: Plattform-Positionsdaten
            force_data: Reifenkraft-Daten
            time_data: Zeitdaten
            
        Returns:
            Frequenzanalyse-Ergebnisse
        """
        try:
            logger.info("Starte Frequenzanalyse")
            
            # Sample-Rate berechnen
            dt = np.mean(np.diff(time_data)) if len(time_data) > 1 else 0.01
            sample_rate = 1.0 / dt
            
            # FFT-Länge für Pi optimieren
            fft_length = min(len(platform_data), self.max_fft_length)
            
            # Daten für FFT vorbereiten (nur ersten fft_length Punkte)
            platform_fft_data = platform_data[:fft_length]
            force_fft_data = force_data[:fft_length]
            
            # FFT berechnen
            platform_fft = np.fft.rfft(platform_fft_data)
            force_fft = np.fft.rfft(force_fft_data)
            frequencies = np.fft.rfftfreq(fft_length, dt)
            
            # Amplituden berechnen
            platform_magnitude = np.abs(platform_fft)
            force_magnitude = np.abs(force_fft)
            
            # Peak-Frequenzen finden
            platform_peaks = self._find_frequency_peaks(frequencies, platform_magnitude)
            force_peaks = self._find_frequency_peaks(frequencies, force_magnitude)
            
            # Dominante Frequenzen ermitteln
            platform_peak_freq = platform_peaks[0] if platform_peaks else 0
            force_peak_freq = force_peaks[0] if force_peaks else 0
            
            # Spektraldaten für GUI (reduziert für Pi)
            spectral_data = self._prepare_spectral_data_for_gui(
                frequencies, platform_magnitude, force_magnitude
            )
            
            # Frequenzbänder analysieren
            frequency_bands = self._analyze_frequency_bands(frequencies, platform_magnitude, force_magnitude)
            
            return {
                "sample_rate": sample_rate,
                "platform_peak_freq": float(platform_peak_freq),
                "force_peak_freq": float(force_peak_freq),
                "platform_peaks": [float(f) for f in platform_peaks[:5]],  # Top 5
                "force_peaks": [float(f) for f in force_peaks[:5]],  # Top 5
                "frequency_range": [float(frequencies[1]), float(frequencies[-1])],
                "spectral_data": spectral_data,
                "frequency_bands": frequency_bands,
                "fft_length": fft_length,
                "analysis_timestamp": time_data[0] if len(time_data) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Frequenzanalyse: {e}")
            return {
                "error": str(e),
                "sample_rate": 0,
                "platform_peak_freq": 0,
                "force_peak_freq": 0
            }
    
    def _find_frequency_peaks(self, frequencies: np.ndarray, magnitude: np.ndarray) -> List[float]:
        """
        Findet dominante Frequenz-Peaks
        
        Args:
            frequencies: Frequenz-Array
            magnitude: Amplituden-Array
            
        Returns:
            Liste der Peak-Frequenzen (sortiert nach Amplitude)
        """
        try:
            # Ignoriere DC-Komponente
            freq_start_idx = 1 if len(frequencies) > 1 else 0
            
            # Peaks finden (minimale Höhe und Abstand)
            min_height = np.max(magnitude[freq_start_idx:]) * 0.1  # 10% der maximalen Amplitude
            min_distance = max(1, len(magnitude) // 100)  # Mindestabstand zwischen Peaks
            
            peak_indices, peak_properties = signal.find_peaks(
                magnitude[freq_start_idx:], 
                height=min_height,
                distance=min_distance
            )
            
            # Korrigiere Indices (wegen freq_start_idx)
            peak_indices = peak_indices + freq_start_idx
            
            # Sortiere Peaks nach Amplitude (absteigend)
            peak_amplitudes = magnitude[peak_indices]
            sorted_indices = np.argsort(peak_amplitudes)[::-1]
            
            # Gib entsprechende Frequenzen zurück
            peak_frequencies = frequencies[peak_indices[sorted_indices]]
            
            return peak_frequencies.tolist()
            
        except Exception as e:
            logger.warning(f"Peak-Erkennung fehlgeschlagen: {e}")
            return []
    
    def _prepare_spectral_data_for_gui(self, frequencies: np.ndarray, 
                                     platform_magnitude: np.ndarray, 
                                     force_magnitude: np.ndarray) -> Dict[str, List]:
        """
        Bereitet Spektraldaten für GUI vor (Pi-optimiert)
        
        Args:
            frequencies: Frequenz-Array
            platform_magnitude: Platform-Amplituden
            force_magnitude: Force-Amplituden
            
        Returns:
            GUI-optimierte Spektraldaten
        """
        try:
            # Reduziere Datenpunkte für GUI-Performance
            max_spectral_points = 1000
            
            if len(frequencies) > max_spectral_points:
                # Gleichmäßiges Downsampling
                step = len(frequencies) // max_spectral_points
                indices = np.arange(0, len(frequencies), step)
                
                freq_gui = frequencies[indices]
                platform_gui = platform_magnitude[indices]
                force_gui = force_magnitude[indices]
            else:
                freq_gui = frequencies
                platform_gui = platform_magnitude
                force_gui = force_magnitude
            
            # Fokus auf relevanten Frequenzbereich (0-50 Hz für Fahrwerk)
            freq_mask = freq_gui <= 50.0
            
            return {
                "frequencies": freq_gui[freq_mask].tolist(),
                "platform_magnitude": platform_gui[freq_mask].tolist(),
                "force_magnitude": force_gui[freq_mask].tolist(),
                "downsampled": len(freq_gui) != len(frequencies)
            }
            
        except Exception as e:
            logger.warning(f"Spektraldaten-Vorbereitung fehlgeschlagen: {e}")
            return {
                "frequencies": [],
                "platform_magnitude": [],
                "force_magnitude": [],
                "error": str(e)
            }
    
    def _analyze_frequency_bands(self, frequencies: np.ndarray, 
                               platform_magnitude: np.ndarray, 
                               force_magnitude: np.ndarray) -> Dict[str, Any]:
        """
        Analysiert spezifische Frequenzbänder für Fahrwerk
        
        Args:
            frequencies: Frequenz-Array
            platform_magnitude: Platform-Amplituden
            force_magnitude: Force-Amplituden
            
        Returns:
            Frequenzband-Analyse
        """
        try:
            # EGEA-relevante Frequenzbänder
            bands = {
                "low_freq": (1.0, 5.0),      # Niederfrequent
                "egea_min": (6.0, 18.0),     # EGEA-Minimum-Bereich
                "working": (8.0, 25.0),      # Arbeitsbereich
                "high_freq": (25.0, 50.0)    # Hochfrequent
            }
            
            band_analysis = {}
            
            for band_name, (f_min, f_max) in bands.items():
                # Frequenzbereich-Maske
                band_mask = (frequencies >= f_min) & (frequencies <= f_max)
                
                if np.any(band_mask):
                    # Durchschnittliche Amplitude in diesem Band
                    platform_avg = np.mean(platform_magnitude[band_mask])
                    force_avg = np.mean(force_magnitude[band_mask])
                    
                    # Maximale Amplitude in diesem Band
                    platform_max = np.max(platform_magnitude[band_mask])
                    force_max = np.max(force_magnitude[band_mask])
                    
                    # Frequenz der maximalen Amplitude
                    platform_max_freq = frequencies[band_mask][np.argmax(platform_magnitude[band_mask])]
                    force_max_freq = frequencies[band_mask][np.argmax(force_magnitude[band_mask])]
                    
                    band_analysis[band_name] = {
                        "freq_range": [f_min, f_max],
                        "platform_avg_amplitude": float(platform_avg),
                        "force_avg_amplitude": float(force_avg),
                        "platform_max_amplitude": float(platform_max),
                        "force_max_amplitude": float(force_max),
                        "platform_max_freq": float(platform_max_freq),
                        "force_max_freq": float(force_max_freq)
                    }
                else:
                    band_analysis[band_name] = {
                        "freq_range": [f_min, f_max],
                        "no_data": True
                    }
            
            return band_analysis
            
        except Exception as e:
            logger.warning(f"Frequenzband-Analyse fehlgeschlagen: {e}")
            return {"error": str(e)}
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Gibt Signal-Processing-Statistiken zurück
        
        Returns:
            Processing-Statistiken
        """
        return {
            "filter_enabled": self.filter_enabled,
            "lowpass_cutoff": self.lowpass_cutoff,
            "highpass_cutoff": self.highpass_cutoff,
            "memory_efficient_mode": self.use_memory_efficient_mode,
            "max_fft_length": self.max_fft_length
        }
