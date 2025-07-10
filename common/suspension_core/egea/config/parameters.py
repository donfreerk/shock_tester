"""
EGEA SPECSUS2018 konforme Parameter und Konstanten
Alle Parameter basieren auf der offiziellen EGEA-Spezifikation
"""

from typing import Dict, Any

# =============================================================================
# EGEA SPECSUS2018 PARAMETER (Section 9 - Abbreviations, symbols and parameters)
# =============================================================================

class EGEAParameters:
    """EGEA-konforme Parameter gemäß SPECSUS2018"""
    
    # Frequenzbereich Parameter (3.22, 5.4)
    MIN_CALC_FREQ: float = 6.0  # Hz - MinCalcFreq
    MAX_CALC_FREQ: float = 18.0  # Hz - MaxCalcFreq  
    DELTA_F: float = 5.0  # Hz - Frequency below minimum adhesion frequency
    
    # Phasenverschiebung Parameter (3.22, 5.5)
    PHASE_SHIFT_MIN: float = 35.0  # Grad - ACφmin (absolutes Kriterium)
    PHASE_SHIFT_MAX: float = 180.0  # Grad - Maximaler erlaubter Wert
    
    # Statisches Gewicht Validierung (3.21)
    RFST_FMAX: float = 25.0  # % - RFstFMax
    RFST_FMIN: float = 25.0  # % - RFstFMin
    
    # Reifensteifigkeit Parameter (3.20)
    A_RIG: float = 0.571  # arig - Steigungskoeffizient
    B_RIG: float = 46.0  # brig - Y-Achsenabschnitt
    RIG_LO_LIM: float = 160.0  # N/mm - rigLoLim (Unterinflation)
    RIG_HI_LIM: float = 400.0  # N/mm - rigHiLim (Überinflation)
    
    # Dynamische Kalibrierung (3.10)
    DYN_CAL_ERR: float = 4.0  # N/Hz - Maximum erlaubter dynamischer Kalibrierungsfehler
    
    # Plattform Parameter (5.1)
    PLATFORM_AMPLITUDE: float = 3.0  # mm - ep (±3mm Amplitude)
    PLATFORM_TOLERANCE: float = 0.3  # mm - Toleranz für Plattformamplitude
    
    # Frequenzvariationsfunktion (5.4)
    FREQUENCY_START: float = 25.0  # Hz - Startfrequenz
    DELTA_T25_BASE: float = 1200.0  # ms - Basisdauer bei 25Hz
    DELTA_T25_FACTOR: float = 0.16  # ms/N - Gewichtsfaktor
    DELTA_T_MEAS: float = 7.5  # s - Mindestmesszeit
    DELTA_TF_LIN_ERR: float = 2.0  # Hz - Linearitätsfehler
    DELTA_TF_MAX_SLOPE: float = 3.0  # Hz/s - Maximale Steigung
    
    # Signalverarbeitung (Annex 1)
    PASS_MUL_PH: int = 2  # PassMulPh - Durchlassbereich Multiplikator
    STOP_MUL_PH: int = 4  # StopMulPh - Sperrbereich Multiplikator  
    EPS_PH: float = 0.01  # EpsPh - Filter Epsilon
    
    # Relative Kriterien (5.6)
    RC_RFA_MAX: float = 30.0  # % - Relatives Kriterium für RFAmax
    RC_PHI_MIN: float = 30.0  # % - Relatives Kriterium für φmin
    RC_RIG: float = 35.0  # % - Relatives Kriterium für Reifensteifigkeit
    
    # Unterflow/Overflow Parameter (3.16)
    F_UNDER_LIM_PERC: float = 1.0  # % - FUnderLimPerc
    
    # Abtastrate und Zeitparameter
    MIN_SAMPLING_RATE: float = 1000.0  # Hz - Minimum für Phasenmessungen
    MEASUREMENT_CYCLE_TIME: float = 0.01  # s - 10ms Zyklus (100 Punkte/Sekunde)
    
    # Gewichtsbereiche (6.1.2.3)
    MIN_WEIGHT: float = 100.0  # daN - Minimum Radgewicht
    MAX_WEIGHT: float = 1100.0  # daN - Maximum Radgewicht
    STAT_W_LIM: float = 25.0  # daN - Gewichtsschwankung vor/nach Test
    
    @classmethod
    def get_all_parameters(cls) -> Dict[str, Any]:
        """Gibt alle EGEA-Parameter als Dictionary zurück"""
        return {
            name: getattr(cls, name)
            for name in dir(cls)
            if not name.startswith('_') and not callable(getattr(cls, name))
        }
    
    @classmethod
    def validate_vehicle_weight(cls, weight: float) -> bool:
        """Validiert Fahrzeuggewicht gegen EGEA-Grenzen"""
        return cls.MIN_WEIGHT <= weight <= cls.MAX_WEIGHT
    
    @classmethod
    def calculate_delta_t25(cls, static_weight: float) -> float:
        """
        Berechnet minimale Dauer bei 25Hz vor Messbeginn (5.4)
        ΔT25 = Fst * 0.16 + 1200 [ms]
        """
        return static_weight * cls.DELTA_T25_FACTOR + cls.DELTA_T25_BASE
    
    @classmethod
    def calculate_f_under_lim(cls, static_weight: float) -> float:
        """
        Berechnet Unterflow-Grenze (3.16)
        FUnderLim = Fst * FUnderLimPerc/100
        """
        return static_weight * cls.F_UNDER_LIM_PERC / 100.0


# Legacy-Kompatibilität für bestehenden Code
TEST_PARAMETERS = {
    "MIN_CALC_FREQ": EGEAParameters.MIN_CALC_FREQ,
    "MAX_CALC_FREQ": EGEAParameters.MAX_CALC_FREQ,
    "DELTA_F": EGEAParameters.DELTA_F,
    "PHASE_SHIFT_MIN": EGEAParameters.PHASE_SHIFT_MIN,
    "RFST_FMAX": EGEAParameters.RFST_FMAX,
    "RFST_FMIN": EGEAParameters.RFST_FMIN,
}