"""
EGEA-konforme Datenmodelle für Testergebnisse
Basiert auf SPECSUS2018 Spezifikation
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
from numpy.typing import NDArray


class VehicleType(Enum):
    """Fahrzeugtypen nach EGEA-Spezifikation"""
    M1 = "M1"  # Personenkraftwagen
    N1 = "N1"  # Leichte Nutzfahrzeuge


class TestResult(Enum):
    """Testergebnisse"""
    PASS = "PASS"
    FAIL = "FAIL"
    INVALID = "INVALID"


@dataclass
class DynamicCalibrationResult:
    """
    Ergebnis der dynamischen Kalibrierung (3.10)
    """
    max_fp: List[float] = field(default_factory=list)  # maxFp(i) - Amplitude pro Periode
    delta_period: List[float] = field(default_factory=list)  # ΔPeriod(i) - Phasenverschiebung
    frequencies: List[float] = field(default_factory=list)  # Frequenzen
    is_valid: bool = False
    error_message: Optional[str] = None
    
    @property
    def calibration_error(self) -> float:
        """Berechnet maximalen Kalibrierungsfehler"""
        if not self.max_fp:
            return float('inf')
        return max(abs(fp) for fp in self.max_fp)


@dataclass
class PhaseShiftPeriod:
    """
    Einzelne Periode der Phasenverschiebungsmessung
    """
    period_index: int
    frequency: float  # Hz
    phase_shift: float  # Grad (0-180°)
    fref: float  # Referenzposition des Reifenkraftsignals
    top_p: float  # Top-Position der Plattform
    max_force: float  # Maximum der Periode
    min_force: float  # Minimum der Periode
    delta_force: float  # Peak-to-Peak Amplitude
    static_weight: float  # Statisches Gewicht
    is_valid: bool  # Gültige Messung nach EGEA-Kriterien
    
    @property
    def rfa_max(self) -> float:
        """Relative Kraftamplitude für diese Periode"""
        if self.static_weight == 0:
            return 0.0
        amplitude = max(abs(self.max_force - self.static_weight), 
                       abs(self.min_force - self.static_weight))
        return (amplitude / self.static_weight) * 100.0


@dataclass
class PhaseShiftResult:
    """
    Vollständiges Ergebnis der Phasenverschiebungsanalyse (3.21, 3.22)
    """
    periods: List[PhaseShiftPeriod] = field(default_factory=list)
    min_phase_shift: Optional[float] = None  # φmin
    min_phase_frequency: Optional[float] = None  # fφmin
    max_phase_shift: Optional[float] = None  # φmax bei 18Hz
    static_weight: float = 0.0  # Fst
    
    # EGEA-spezifische Flags
    f_under_flag: bool = False  # Signal Unterflow
    f_over_flag: bool = False   # Signal Overflow
    
    # Berechnete Werte
    rfa_max_value: Optional[float] = None  # Maximum RFAmax
    rfa_max_frequency: Optional[float] = None
    
    @property
    def is_valid(self) -> bool:
        """Prüft ob gültige Messdaten vorliegen"""
        return (self.min_phase_shift is not None and 
                len(self.periods) > 0 and
                not self.f_under_flag)
    
    @property
    def integer_min_phase(self) -> Optional[int]:
        """iφmin - Abgerundeter Minimalwert für Anzeige (6.2.1)"""
        return int(self.min_phase_shift) if self.min_phase_shift is not None else None
    
    @property
    def phase_shifts(self) -> List[float]:
        """Alle Phasenverschiebungen als Liste"""
        return [p.phase_shift for p in self.periods if p.is_valid]
    
    @property
    def frequencies(self) -> List[float]:
        """Alle Frequenzen als Liste"""
        return [p.frequency for p in self.periods if p.is_valid]


@dataclass
class RigidityResult:
    """
    Reifensteifigkeitsergebnis (3.20)
    """
    rigidity: float  # N/mm
    h25: float  # Statische Amplitude bei 25Hz
    platform_amplitude: float  # Plattformamplitude (ep)
    warning_underinflation: bool = False  # rig < rigLoLim
    warning_overinflation: bool = False   # rig > rigHiLim
    
    @property
    def is_valid_pressure(self) -> bool:
        """Prüft ob Reifendruck im akzeptablen Bereich"""
        return not (self.warning_underinflation or self.warning_overinflation)


@dataclass
class ForceAnalysisResult:
    """
    Kraftanalyse-Ergebnis (3.15, 3.17)
    """
    fmin: float  # Minimum der F(t) Signal
    fmax: float  # Maximum der F(t) Signal
    fa_max: float  # Maximale Amplitude
    resonant_frequency: float  # fres
    rfa_max: float  # Relative maximale Amplitude (3.18)
    static_weight: float  # Fst
    
    # Overflow/Underflow Flags (3.16)
    f_under_flag: bool = False
    f_over_flag: bool = False


@dataclass
class EGEATestResult:
    """
    Vollständiges EGEA-Testergebnis für ein Rad
    """
    # Grundlegende Identifikation
    wheel_id: str  # z.B. "FL", "FR", "RL", "RR"
    vehicle_type: VehicleType
    
    # Hauptergebnisse
    phase_shift_result: PhaseShiftResult
    force_analysis: ForceAnalysisResult
    rigidity_result: RigidityResult
    dynamic_calibration: DynamicCalibrationResult
    
    # Bewertung
    absolute_criterion_pass: bool = False  # φmin >= 35°
    relative_criterion_pass: bool = False  # Vergleich zwischen Rädern
    overall_pass: bool = False
    
    # Zusätzliche Informationen
    test_timestamp: Optional[str] = None
    error_messages: List[str] = field(default_factory=list)
    
    @property
    def summary(self) -> Dict[str, Any]:
        """Zusammenfassung für Anzeige/Bericht"""
        return {
            "wheel_id": self.wheel_id,
            "min_phase_shift": self.phase_shift_result.min_phase_shift,
            "integer_min_phase": self.phase_shift_result.integer_min_phase,
            "rfa_max": self.force_analysis.rfa_max,
            "rigidity": self.rigidity_result.rigidity,
            "absolute_pass": self.absolute_criterion_pass,
            "overall_pass": self.overall_pass,
            "static_weight": self.phase_shift_result.static_weight
        }


@dataclass
class AxleTestResult:
    """
    Testergebnis für eine komplette Achse (5.3)
    """
    axle_id: str  # "Front" oder "Rear"
    left_wheel: EGEATestResult
    right_wheel: EGEATestResult
    
    # Achsgewicht (AFsti)
    axle_weight: float = 0.0
    
    # Unbalanzen (5.3)
    d_rfa_max: Optional[float] = None  # DRFAmaxi
    d_phi_min: Optional[float] = None  # Dφmini  
    d_i_phi_min: Optional[float] = None  # Diφmini
    d_rigidity: Optional[float] = None  # Drigi
    
    # Relative Kriterien (5.6)
    relative_rfa_max_pass: bool = False  # <= 30%
    relative_phi_min_pass: bool = False  # <= 30%
    relative_rigidity_pass: bool = False  # <= 35%
    
    def calculate_imbalances(self) -> None:
        """Berechnet alle Unbalanzen zwischen linkem und rechtem Rad"""
        if (self.left_wheel.phase_shift_result.is_valid and 
            self.right_wheel.phase_shift_result.is_valid):
            
            # RFAmax Unbalance
            left_rfa = self.left_wheel.force_analysis.rfa_max
            right_rfa = self.right_wheel.force_analysis.rfa_max
            self.d_rfa_max = self._calculate_imbalance(left_rfa, right_rfa)
            
            # φmin Unbalance
            left_phi = self.left_wheel.phase_shift_result.min_phase_shift
            right_phi = self.right_wheel.phase_shift_result.min_phase_shift
            if left_phi is not None and right_phi is not None:
                self.d_phi_min = self._calculate_imbalance(left_phi, right_phi)
            
            # iφmin Unbalance (für Anzeige)
            left_iphi = self.left_wheel.phase_shift_result.integer_min_phase
            right_iphi = self.right_wheel.phase_shift_result.integer_min_phase
            if left_iphi is not None and right_iphi is not None:
                self.d_i_phi_min = self._calculate_imbalance(float(left_iphi), float(right_iphi))
            
            # Rigidity Unbalance
            left_rig = self.left_wheel.rigidity_result.rigidity
            right_rig = self.right_wheel.rigidity_result.rigidity
            self.d_rigidity = self._calculate_imbalance(left_rig, right_rig)
            
            # Achsgewicht
            self.axle_weight = (self.left_wheel.phase_shift_result.static_weight + 
                              self.right_wheel.phase_shift_result.static_weight)
    
    @staticmethod
    def _calculate_imbalance(val1: float, val2: float) -> float:
        """
        Berechnet Unbalance nach EGEA-Formel (5.3):
        DVal = |Val1 - Val2| / max(Val1, Val2) * 100
        """
        if max(val1, val2) == 0:
            return 0.0
        return abs(val1 - val2) / max(val1, val2) * 100.0
    
    @property
    def overall_pass(self) -> bool:
        """Gesamtbewertung der Achse"""
        return (self.left_wheel.overall_pass and 
                self.right_wheel.overall_pass and
                self.relative_rfa_max_pass and 
                self.relative_phi_min_pass and
                self.relative_rigidity_pass)