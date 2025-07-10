"""
EGEA-konforme Signalverarbeitung
Basiert auf SPECSUS2018 Annex 1 und Kaiser-Reed Filter
"""

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, filtfilt, find_peaks, hilbert
from scipy.interpolate import interp1d
from typing import List, Tuple, Optional, Dict
import logging

from ...egea.config.parameters import EGEAParameters


logger = logging.getLogger(__name__)


class EGEASignalProcessor:
    """
    EGEA-konforme Signalverarbeitung nach SPECSUS2018
    Implementiert Kaiser-Reed Filter (Annex 1)
    """
    
    def __init__(self):
        self.params = EGEAParameters()
    
    def apply_egea_phase_filter(self, 
                               signal: NDArray[np.float64], 
                               fs: float, 
                               frequency_step: float) -> NDArray[np.float64]:
        """
        Implementiert EGEA-konforme Filterung für Phasenanalyse (Annex 1)
        
        Filter für F(t) Signal - raw phase shift φr(i) calculation
        Für jeden Frequenzschritt fstep von 1 Hz im Bereich 18-5 Hz wird ein
        einzigartiger Filter nach Kaiser-Reed erstellt.
        
        Args:
            signal: Eingangssignal
            fs: Abtastrate
            frequency_step: Aktuelle Frequenz (18, 17, ..., 6 Hz)
            
        Returns:
            Gefiltertes Signal
        """
        try:
            # EGEA Parameter (Annex 1)
            pass_mul_ph = self.params.PASS_MUL_PH  # 2
            stop_mul_ph = self.params.STOP_MUL_PH  # 4
            eps_ph = self.params.EPS_PH  # 0.01
            
            # Frequenzbereiche berechnen
            pass_freq = frequency_step * pass_mul_ph  # 0 - fstep*2 Hz
            stop_freq = frequency_step * stop_mul_ph  # fstep*4 Hz aufwärts
            
            # Nyquist-Frequenz
            nyquist = fs / 2.0
            
            # Normalisierte Frequenzen
            low_pass = min(pass_freq / nyquist, 0.99)
            
            # Nearly equal ripple approximation filter (Kaiser-Reed Method 1)
            # Butterworth-Filter als Approximation
            order = 3  # Empirisch bestimmt für eps=0.01
            
            b, a = butter(order, low_pass, btype='low')
            filtered_signal = filtfilt(b, a, signal)
            
            logger.debug(f"Applied EGEA filter for {frequency_step}Hz: "
                        f"pass={pass_freq}Hz, stop={stop_freq}Hz")
            
            return filtered_signal
            
        except Exception as e:
            logger.error(f"Filter error for frequency {frequency_step}Hz: {e}")
            return signal  # Return unfiltered on error
    
    def apply_force_amplitude_filter(self, 
                                   signal: NDArray[np.float64], 
                                   fs: float) -> NDArray[np.float64]:
        """
        Filter für F(t), Fp(t) und relative force maximum amplitude (Annex 1)
        Whole signal, ε = 0.01, pass band 0-50 Hz, stop band 130 Hz up
        """
        try:
            nyquist = fs / 2.0
            pass_freq = 50.0 / nyquist
            stop_freq = 130.0 / nyquist
            
            # Prüfe Frequenzgrenzen
            if pass_freq >= 1.0:
                logger.warning("Pass frequency exceeds Nyquist, using 0.8*Nyquist")
                pass_freq = 0.8
            
            order = 4  # Höhere Ordnung für steilere Flanken
            b, a = butter(order, pass_freq, btype='low')
            
            return filtfilt(b, a, signal)
            
        except Exception as e:
            logger.error(f"Force amplitude filter error: {e}")
            return signal
    
    def find_platform_tops(self, 
                          platform_position: NDArray[np.float64], 
                          min_distance: Optional[int] = None) -> NDArray[np.int64]:
        """
        Findet TOP-Positionen der Plattform (3.11)
        
        Args:
            platform_position: Plattformpositionssignal
            min_distance: Minimaler Abstand zwischen Peaks
            
        Returns:
            Indices der TOP-Positionen
        """
        if min_distance is None:
            # Mindestabstand basierend auf minimaler Frequenz
            min_distance = int(len(platform_position) / (self.params.MAX_CALC_FREQ * 2))
        
        peaks, properties = find_peaks(
            platform_position,
            distance=min_distance,
            prominence=np.std(platform_position) * 0.1
        )
        
        return peaks.astype(np.int64)
    
    def find_static_weight_crossings(self, 
                                   force_signal: NDArray[np.float64],
                                   time_array: NDArray[np.float64], 
                                   static_weight: float) -> List[Tuple[float, str]]:
        """
        Findet alle Kreuzungen der Reifenkraft mit dem statischen Gewicht
        
        Args:
            force_signal: Kraftsignal
            time_array: Zeitarray  
            static_weight: Statisches Gewicht (Fst)
            
        Returns:
            Liste von (time, direction) Tupeln, direction = 'up'|'down'
        """
        crossings = []
        
        for i in range(1, len(force_signal)):
            prev_force = force_signal[i-1]
            curr_force = force_signal[i]
            
            # Prüfe auf Kreuzung
            if ((prev_force < static_weight < curr_force) or 
                (prev_force > static_weight > curr_force)):
                
                # Lineare Interpolation für genauen Zeitpunkt
                fraction = (static_weight - prev_force) / (curr_force - prev_force)
                crossing_time = time_array[i-1] + fraction * (time_array[i] - time_array[i-1])
                
                # Bestimme Richtung
                direction = 'up' if curr_force > prev_force else 'down'
                
                crossings.append((crossing_time, direction))
        
        return crossings
    
    def calculate_fref(self, 
                      force_signal: NDArray[np.float64],
                      time_array: NDArray[np.float64],
                      static_weight: float,
                      cycle_start_time: float,
                      cycle_end_time: float) -> Optional[float]:
        """
        Berechnet Fref als Mittelpunkt zwischen down- und up-Kreuzungen (3.7)
        
        Args:
            force_signal: Kraftsignal für den Zyklus
            time_array: Zeitarray für den Zyklus  
            static_weight: Statisches Gewicht
            cycle_start_time: Zyklusstart
            cycle_end_time: Zyklusende
            
        Returns:
            Fref-Zeit oder None wenn nicht berechenbar
        """
        # Finde alle Kreuzungen im Zyklus
        crossings = self.find_static_weight_crossings(force_signal, time_array, static_weight)
        
        if len(crossings) < 2:
            return None
        
        # Separiere up und down crossings
        down_crossings = [t for t, direction in crossings if direction == 'down']
        up_crossings = [t for t, direction in crossings if direction == 'up']
        
        if not down_crossings or not up_crossings:
            # Fallback: Verwende erste zwei Kreuzungen
            return (crossings[0][0] + crossings[1][0]) / 2.0
        
        # Verwende erste down- und up-Kreuzung
        return (down_crossings[0] + up_crossings[0]) / 2.0
    
    def validate_rfst_conditions(self, 
                                force_signal: NDArray[np.float64],
                                static_weight: float) -> bool:
        """
        Validiert RFstFMin und RFstFMax Bedingungen (3.21)
        
        Args:
            force_signal: Kraftsignal für den Zyklus
            static_weight: Statisches Gewicht
            
        Returns:
            True wenn Bedingungen erfüllt sind
        """
        max_force = np.max(force_signal)
        min_force = np.min(force_signal)
        delta_force = max_force - min_force
        
        # Berechne Grenzen (25% Toleranz)
        rfst_fmax_perc = self.params.RFST_FMAX / 100.0
        rfst_fmin_perc = self.params.RFST_FMIN / 100.0
        
        f_max_limit = max_force - delta_force * rfst_fmax_perc
        f_min_limit = min_force + delta_force * rfst_fmin_perc
        
        # Prüfe ob statisches Gewicht im gültigen Bereich liegt
        return f_min_limit < static_weight < f_max_limit
    
    def calculate_cycle_frequency(self, 
                                cycle_start_idx: int, 
                                cycle_end_idx: int,
                                time_array: NDArray[np.float64]) -> float:
        """
        Berechnet Frequenz für einen Zyklus
        
        Args:
            cycle_start_idx: Start-Index des Zyklus
            cycle_end_idx: End-Index des Zyklus  
            time_array: Zeitarray
            
        Returns:
            Frequenz in Hz
        """
        cycle_duration = time_array[cycle_end_idx] - time_array[cycle_start_idx]
        return 1.0 / cycle_duration if cycle_duration > 0 else 0.0
    
    def detect_signal_overflow_underflow(self, 
                                       signal: NDArray[np.float64],
                                       static_weight: float,
                                       f_over_lim: Optional[float] = None) -> Tuple[bool, bool]:
        """
        Erkennt Signal Overflow und Underflow (3.16)
        
        Args:
            signal: Kraftsignal
            static_weight: Statisches Gewicht
            f_over_lim: Overflow-Grenze (optional)
            
        Returns:
            (f_under_flag, f_over_flag)
        """
        f_min = np.min(signal)
        f_max = np.max(signal)
        
        # Underflow Detection
        f_under_lim = self.params.calculate_f_under_lim(static_weight)
        f_under_flag = f_min < f_under_lim
        
        # Overflow Detection  
        f_over_flag = False
        if f_over_lim is not None:
            f_over_flag = f_max > f_over_lim
        
        return f_under_flag, f_over_flag
    
    def resample_to_equidistant_frequency(self, 
                                        phase_shifts: List[float],
                                        frequencies: List[float],
                                        freq_step: float = 0.1) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Resampling für äquidistante Frequenzverteilung (Annex 1)
        
        Args:
            phase_shifts: Phasenverschiebungen
            frequencies: Zugehörige Frequenzen
            freq_step: Frequenzschritt (0.1 Hz)
            
        Returns:
            (resampled_frequencies, resampled_phase_shifts)
        """
        if len(phase_shifts) < 2:
            return np.array(frequencies), np.array(phase_shifts)
        
        # Sortiere nach Frequenz
        sorted_indices = np.argsort(frequencies)
        sorted_freqs = np.array(frequencies)[sorted_indices]
        sorted_phases = np.array(phase_shifts)[sorted_indices]
        
        # Erstelle äquidistante Frequenz-Achse
        freq_min = max(sorted_freqs[0], self.params.MIN_CALC_FREQ)
        freq_max = min(sorted_freqs[-1], self.params.MAX_CALC_FREQ)
        
        if freq_max <= freq_min:
            return sorted_freqs, sorted_phases
        
        equidistant_freqs = np.arange(freq_min, freq_max + freq_step, freq_step)
        
        # Interpolation
        try:
            interpolator = interp1d(sorted_freqs, sorted_phases, 
                                  kind='linear', bounds_error=False, fill_value='extrapolate')
            resampled_phases = interpolator(equidistant_freqs)
            
            return equidistant_freqs, resampled_phases
            
        except Exception as e:
            logger.error(f"Resampling error: {e}")
            return sorted_freqs, sorted_phases
    
    def apply_gaussian_smoothing(self, 
                               phase_shifts: NDArray[np.float64],
                               filter_order: int = 20) -> NDArray[np.float64]:
        """
        Anwendung des Gaussian Filters (Annex 1)
        
        Args:
            phase_shifts: Phasenverschiebungen
            filter_order: Filter-Ordnung (Standard: 20)
            
        Returns:
            Geglättete Phasenverschiebungen
        """
        from scipy.ndimage import gaussian_filter1d
        
        # Standardabweichung basierend auf Filter-Ordnung
        sigma = filter_order / 6.0  # Empirisch
        
        return gaussian_filter1d(phase_shifts, sigma)


def create_egea_test_signals(duration: float = 15.0, 
                           fs: float = 1000.0,
                           start_freq: float = 25.0,
                           end_freq: float = 5.0) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """
    Erstellt EGEA-konforme Testsignale
    
    Args:
        duration: Testdauer in Sekunden
        fs: Abtastrate in Hz
        start_freq: Startfrequenz
        end_freq: Endfrequenz
        
    Returns:
        (time_array, platform_position, tire_force)
    """
    t = np.linspace(0, duration, int(duration * fs))
    
    # Frequenzverlauf (linear von start_freq zu end_freq)
    freq_slope = (end_freq - start_freq) / duration
    instantaneous_freq = start_freq + freq_slope * t
    
    # Phasenintegral
    phase = 2 * np.pi * np.cumsum(instantaneous_freq) / fs
    
    # Plattformposition (sinusförmig)
    platform_amplitude = EGEAParameters.PLATFORM_AMPLITUDE / 1000.0  # mm -> m
    platform_position = platform_amplitude * np.sin(phase)
    
    # Reifenkraft (mit Phasenverschiebung und Dämpfung)
    static_weight = 500.0  # N
    force_amplitude = 200.0  # N
    
    # Simuliere Phasenverschiebung (frequenzabhängig)
    phase_shift = np.pi / 6 * (1 + 0.5 * np.sin(0.1 * phase))  # Variable Phasenverschiebung
    
    tire_force = (static_weight + 
                  force_amplitude * np.sin(phase + phase_shift) * 
                  np.exp(-0.1 * t))  # Exponentieller Abfall
    
    # Rauschen hinzufügen
    noise_level = 5.0  # N
    tire_force += np.random.normal(0, noise_level, len(tire_force))
    
    return t, platform_position, tire_force