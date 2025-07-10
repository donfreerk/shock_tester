import numpy as np
import logging
from typing import Dict, Any, List, Optional

from common.suspension_core.config.settings import RESONANCE_PARAMETERS

logger = logging.getLogger(__name__)


class ResonanceProcessor:
    """
    Verarbeitet Ausschwingmessungen nach dem Resonanzprinzip für die Fahrwerksdiagnose.
    Berechnet Gewicht, Amplitude und Effektivität basierend auf Spannungsdaten.
    """

    def __init__(self):
        # Faktoren aus Konfiguration laden
        self.factor_weight = RESONANCE_PARAMETERS["FACTOR_WEIGHT"]
        self.factor_amplitude = RESONANCE_PARAMETERS["FACTOR_AMPLITUDE"]

    def process_test(self, voltage_data: List[float], initial_voltage: float, weight_class: int = 1500) -> Dict[str, Any]:
        """
        Verarbeitet die Ausschwingmessung nach dem Resonanzprinzip.

        Args:
            voltage_data: Zeitreihe der Spannungswerte vom Weggeber
            initial_voltage: Anfangsspannung vor der Belastung
            weight_class: Gewichtsklasse für die Kalibrierung (1500kg oder 2000kg)

        Returns:
            dict: Testergebnis mit Gewicht, Amplitude und Effektivität
        """
        try:
            # Typkonvertierung sicherstellen
            weight_class = int(weight_class)
            initial_voltage = float(initial_voltage)

            # Sicherstellen, dass voltage_data ein numerisches Array ist
            if not isinstance(voltage_data, np.ndarray):
                voltage_data = np.array(voltage_data, dtype=float)

            if len(voltage_data) == 0:
                return {"weight": 0.0, "amplitude": 0.0, "effectiveness": 0.0}

            # Kalibrierfaktor für die entsprechende Gewichtsklasse auswählen
            weight_factor = self.factor_weight.get(
                weight_class, self.factor_weight[1500]
            )

            # Radgewicht aus Spannungsdifferenz berechnen
            voltage_difference = initial_voltage - voltage_data[0]
            weight = voltage_difference * weight_factor

            # Ruhelage als Bezugspunkt für Amplitudenberechnung festlegen
            equilibrium = voltage_data[0]
            positive_peaks = []
            negative_peaks = []

            # Lokale Maxima und Minima in den Messdaten identifizieren
            for i in range(1, len(voltage_data) - 1):
                # Positiver Peak: Wert ist größer als beide Nachbarwerte
                if voltage_data[i - 1] < voltage_data[i] > voltage_data[i + 1]:
                    positive_peaks.append(voltage_data[i])
                # Negativer Peak: Wert ist kleiner als beide Nachbarwerte
                elif voltage_data[i - 1] > voltage_data[i] < voltage_data[i + 1]:
                    negative_peaks.append(voltage_data[i])

            # Frühzeitige Rückgabe bei fehlenden Extremwerten
            if not positive_peaks or not negative_peaks:
                return {"weight": weight, "amplitude": 0.0, "effectiveness": 0.0}

            # Maximale Ausschläge in beide Richtungen bestimmen
            max_positive = max(positive_peaks) - equilibrium
            max_negative = equilibrium - min(negative_peaks)
            max_amplitude = max(max_positive, max_negative)

            # Physikalische Amplitude durch Anwendung des Kalibrierfaktors berechnen
            amplitude = max_amplitude * self.factor_amplitude

            # Ideale Amplitude für das gemessene Gewicht berechnen
            ideal_amplitude = self._calculate_ideal_amplitude(weight)

            # Effektivität als Verhältnis zur idealen Amplitude berechnen
            if amplitude > 0:
                # Bei Idealamplitude wäre die Effektivität 70%
                effectiveness = (ideal_amplitude / amplitude) * 70
                # Effektivität auf sinnvollen Bereich begrenzen
                effectiveness = max(0, min(100, effectiveness))
            else:
                effectiveness = 0

            # Ergebnisse als Dictionary zurückgeben
            return {
                "weight": float(weight),  # Explizite Konvertierung zur Sicherheit
                "amplitude": float(amplitude),
                "effectiveness": float(effectiveness),
            }

        except (ValueError, TypeError, IndexError) as e:
            # Fehlerbehandlung, damit die Methode nicht komplett abbricht
            logger.error(f"Fehler bei der Resonanzanalyse: {e}")
            return {"weight": 0.0, "amplitude": 0.0, "effectiveness": 0.0}

    @staticmethod
    def _calculate_ideal_amplitude(weight: float) -> float:
        """
        Berechnet die ideale Amplitude basierend auf dem Radgewicht.

        Die ideale Amplitude entspricht einem Dämpfer mit 70% Effektivität.
        Sie dient als Referenzwert für die Beurteilung der gemessenen Werte.

        Args:
            weight: Radgewicht in kg

        Returns:
            float: Ideale Amplitude für das gegebene Gewicht
        """
        # Konstanten für die Berechnung der idealen Amplitude
        # Diese Parameter sollten basierend auf dem Anforderungsprofil kalibriert werden
        BASE_AMPLITUDE = 2.0  # Basisamplitude in mm
        LINEAR_FACTOR = 0.03  # Linearer Gewichtsfaktor
        NONLINEAR_FACTOR = 0.0001  # Nichtlinearer Faktor für größere Genauigkeit

        # Berechnung mit linearem und nichtlinearem Anteil
        # Bei geringen Gewichten dominiert der lineare Anteil,
        # bei höherem Gewicht wird der nichtlineare Anteil stärker berücksichtigt
        ideal_amplitude = (
            BASE_AMPLITUDE + (LINEAR_FACTOR * weight) - (NONLINEAR_FACTOR * weight**2)
        )

        # Begrenzung der Amplitude auf sinnvolle Werte
        MIN_AMPLITUDE = 1.0  # mm
        MAX_AMPLITUDE = 15.0  # mm
        ideal_amplitude = max(MIN_AMPLITUDE, min(ideal_amplitude, MAX_AMPLITUDE))

        return ideal_amplitude

    def evaluate_resonance_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bewertet die Ergebnisse der Resonanzmessung.

        Args:
            results: Ergebnisse der Resonanzmessung (weight, amplitude, effectiveness)

        Returns:
            dict: Bewertungsergebnis mit Bestanden/Nicht bestanden und Qualitätsindex
        """
        # Standardschwellenwert für die Effektivität
        EFFECTIVENESS_THRESHOLD = 50.0  # 50% Effektivität als Mindestwert

        # Effektivität aus den Ergebnissen extrahieren
        effectiveness = results.get("effectiveness", 0.0)
        
        # Bestanden/Nicht bestanden basierend auf Effektivitätsschwellenwert
        passed = effectiveness >= EFFECTIVENESS_THRESHOLD
        
        # Qualitätsindex berechnen (0-100%)
        quality_index = min(100.0, effectiveness)
        
        # Bewertungsergebnis zurückgeben
        return {
            "passed": passed,
            "quality_index": float(quality_index),
            "effectiveness": float(effectiveness),
            "threshold": float(EFFECTIVENESS_THRESHOLD),
            "weight": float(results.get("weight", 0.0)),
            "amplitude": float(results.get("amplitude", 0.0))
        }