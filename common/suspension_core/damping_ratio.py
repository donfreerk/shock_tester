"""
Modul zur Berechnung von Dämpfungswerten aus Testsignalen.

Dieses Modul implementiert Funktionen zur Berechnung des Dämpfungsverhältnisses
und verwandter Parameter aus Ausschwingkurven und Resonanzsignalen.
"""

import numpy as np
from scipy.signal import find_peaks
from typing import Dict, Any, List, Optional, Union

from suspension_core.config.settings import VEHICLE_TYPES


def calculate_damping_ratio(vehicle_type: str, weight: float, spring_constant: float, damping_constant: float) -> float:
    """
    Berechnet das Dämpfungsverhältnis aus den mechanischen Parametern des Fahrwerks.

    Args:
        vehicle_type: Fahrzeugtyp (M1 oder N1)
        weight: Radgewicht in kg
        spring_constant: Federsteifigkeit in N/m
        damping_constant: Dämpfungskonstante in Ns/m

    Returns:
        float: Dämpfungsverhältnis (dimensionslos)
    """
    # Ungefederte Masse basierend auf Fahrzeugtyp bestimmen
    unsprung_mass = VEHICLE_TYPES[vehicle_type]["UNSPRUNG_MASS"]

    # Gefederte Masse berechnen (Radgewicht abzüglich der ungefederten Masse)
    sprung_mass = weight - unsprung_mass

    # Dämpfungsverhältnis nach Formel: ζ = c / (2 * sqrt(k * m))
    # wobei c = Dämpfungskonstante, k = Federsteifigkeit, m = gefederte Masse
    damping_ratio = damping_constant / (2 * np.sqrt(spring_constant * sprung_mass))

    return float(damping_ratio)


def calculate_damping_from_phase_shift(phase_shift_deg: float) -> float:
    """
    Berechnet das Dämpfungsverhältnis aus dem gemessenen Phasenwinkel.

    Args:
        phase_shift_deg: Phasenverschiebung in Grad

    Returns:
        float: Dämpfungsverhältnis (dimensionslos)
    """
    # Umrechnung von Grad in Radianten
    phase_shift_rad = np.radians(phase_shift_deg)

    # EGEA-Formel für die Umrechnung von Phasenwinkel in Dämpfungsverhältnis
    # Bei φ = 90° ist ζ ≈ 0.5 (kritische Dämpfung)
    damping_ratio = np.sin(phase_shift_rad) / 2

    return float(damping_ratio)


def calculate_damping_from_decay(time_array: List[float], amplitude_array: List[float]) -> Optional[float]:
    """
    Berechnet das Dämpfungsverhältnis aus einer Ausschwingkurve.

    Args:
        time_array: Array der Zeitwerte
        amplitude_array: Array der Amplitudenwerte

    Returns:
        float: Dämpfungsverhältnis (dimensionslos) oder None bei Fehler
    """
    # Konvertiere Listen zu NumPy-Arrays für effizientere Berechnungen
    if not isinstance(amplitude_array, np.ndarray):
        amplitude_array = np.array(amplitude_array, dtype=float)

    # Sicherstellen, dass amplitude_array eindimensional ist
    if amplitude_array.ndim > 1:
        amplitude_array = amplitude_array.flatten()

    # Finde lokale Maxima (Spitzenwerte) der Schwingung
    # Minimaldistanz sicherstellen (mindestens 1)
    min_distance = max(1, int(len(amplitude_array) * 0.1))
    peaks, _ = find_peaks(amplitude_array, distance=min_distance)

    if len(peaks) < 2:
        return None  # Zu wenige Peaks für die Berechnung

    # Amplituden der gefundenen Peaks
    peak_amplitudes = amplitude_array[peaks]

    # Logarithmisches Dekrement berechnen
    log_decrements = []
    for i in range(len(peak_amplitudes) - 1):
        if peak_amplitudes[i + 1] <= 0 or peak_amplitudes[i] <= 0:
            continue
        log_dec = np.log(peak_amplitudes[i] / peak_amplitudes[i + 1])
        log_decrements.append(log_dec)

    if not log_decrements:
        return None

    # Mittleres logarithmisches Dekrement
    mean_log_dec = np.mean(log_decrements)

    # Dämpfungsverhältnis aus logarithmischem Dekrement
    # Mit numerischer Stabilität
    denominator = 2 * np.pi * np.sqrt(1 + (mean_log_dec / (2 * np.pi)) ** 2)

    # Vermeiden von Division durch 0
    if np.isclose(denominator, 0):
        return None

    damping_ratio = mean_log_dec / denominator

    return float(damping_ratio)


def phase_shift_to_quality_rating(phase_shift_deg: float, threshold: float = 35.0) -> Dict[str, Any]:
    """
    Bewertet die Dämpfungsqualität anhand des Phasenwinkels nach EGEA-Kriterien.

    Args:
        phase_shift_deg: Phasenverschiebung in Grad
        threshold: Schwellenwert für die Bewertung (Standard: 35.0°)

    Returns:
        dict: Bewertungsergebnis mit Status und Qualitätsindex
    """
    # Qualitätsbewertung auf Basis des Phasenwinkels
    # EGEA-Spezifikation: φmin ≥ 35° gilt als bestanden
    quality_index = (phase_shift_deg / threshold) * 100 if threshold > 0 else 0

    return {
        "pass": phase_shift_deg >= threshold,
        "quality_index": min(100, float(quality_index)),  # Auf 100% begrenzen
        "damping_ratio": calculate_damping_from_phase_shift(phase_shift_deg),
    }


def convert_damping_units(
    damping_ratio: float, 
    sprung_mass: float, 
    spring_constant: Optional[float] = None, 
    natural_frequency: Optional[float] = None
) -> Dict[str, float]:
    """
    Konvertiert das Dämpfungsverhältnis in andere Dämpfungseinheiten.

    Args:
        damping_ratio: Dämpfungsverhältnis (dimensionslos)
        sprung_mass: Gefederte Masse in kg
        spring_constant: Federsteifigkeit in N/m (optional, wenn natural_frequency gegeben)
        natural_frequency: Eigenfrequenz in Hz (optional, wenn spring_constant gegeben)

    Returns:
        dict: Verschiedene Dämpfungseinheiten
    """
    if spring_constant is None and natural_frequency is None:
        raise ValueError(
            "Entweder spring_constant oder natural_frequency muss angegeben werden"
        )

    # Eigenfrequenz berechnen (falls nicht angegeben)
    if natural_frequency is None:
        natural_frequency = (1 / (2 * np.pi)) * np.sqrt(spring_constant / sprung_mass)

    # Kritische Dämpfung berechnen
    critical_damping = 2 * sprung_mass * 2 * np.pi * natural_frequency

    # Dämpfungskonstante berechnen
    damping_constant = damping_ratio * critical_damping

    return {
        "damping_ratio": float(damping_ratio),  # Dimensionslos
        "damping_constant": float(damping_constant),  # Ns/m
        "critical_damping": float(critical_damping),  # Ns/m
        "relative_damping": float(damping_ratio * 100),  # Prozent
    }