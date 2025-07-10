"""
Vollständiges Beispiel für EGEA Phase_Shift Fahrwerkstester
Demonstriert die verbesserte Implementierung mit allen EGEA-konformen Features
"""

import logging
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, Any

# Import der verbesserten EGEA-Module
from ....suspension_core.egea.config.parameters import EGEAParameters
from ....suspension_core.egea.models.results import VehicleType, EGEATestResult, AxleTestResult
from ....suspension_core.egea.processors.phase_shift_processor import EGEAPhaseShiftProcessor
from ....suspension_core.egea.utils.signal_processing import create_egea_test_signals


# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EGEATestController:
    """
    Haupt-Controller für EGEA-Fahrwerkstests
    Verwaltet komplette Testsequenzen und Achsvergleiche
    """
    
    def __init__(self):
        self.processor = EGEAPhaseShiftProcessor()
        self.params = EGEAParameters()
        
    def run_single_wheel_test(self, 
                            platform_position: np.ndarray,
                            tire_force: np.ndarray, 
                            time_array: np.ndarray,
                            static_weight: float,
                            wheel_id: str,
                            vehicle_type: VehicleType = VehicleType.M1) -> EGEATestResult:
        """
        Führt Test für ein einzelnes Rad durch
        
        Args:
            platform_position: Plattformpositionsdaten
            tire_force: Reifenkraftdaten
            time_array: Zeitarray
            static_weight: Statisches Radgewicht
            wheel_id: Rad-Identifikation (FL, FR, RL, RR)
            vehicle_type: Fahrzeugtyp
            
        Returns:
            EGEATestResult
        """
        logger.info(f"Starting EGEA test for wheel {wheel_id}")
        
        # Validierung der Eingangsdaten
        if not self._validate_input_data(platform_position, tire_force, time_array, static_weight):
            logger.error(f"Invalid input data for wheel {wheel_id}")
            return self._create_invalid_result(wheel_id, vehicle_type, static_weight)
        
        # Vollständigen Test durchführen
        result = self.processor.process_complete_test(
            platform_position=platform_position,
            tire_force=tire_force,
            time_array=time_array,
            static_weight=static_weight,
            wheel_id=wheel_id,
            vehicle_type=vehicle_type
        )
        
        # Ergebnis-Logging
        self._log_test_result(result)
        
        return result
    
    def run_axle_test(self,
                     left_platform_pos: np.ndarray, left_tire_force: np.ndarray,
                     right_platform_pos: np.ndarray, right_tire_force: np.ndarray,
                     time_array: np.ndarray,
                     left_static_weight: float, right_static_weight: float,
                     axle_id: str = "Front",
                     vehicle_type: VehicleType = VehicleType.M1) -> AxleTestResult:
        """
        Führt Test für eine komplette Achse durch
        
        Returns:
            AxleTestResult mit Unbalance-Berechnung
        """
        logger.info(f"Starting EGEA axle test for {axle_id}")
        
        # Tests für beide Räder
        left_wheel_id = f"{axle_id[0]}L"  # FL oder RL
        right_wheel_id = f"{axle_id[0]}R"  # FR oder RR
        
        left_result = self.run_single_wheel_test(
            left_platform_pos, left_tire_force, time_array,
            left_static_weight, left_wheel_id, vehicle_type
        )
        
        right_result = self.run_single_wheel_test(
            right_platform_pos, right_tire_force, time_array,
            right_static_weight, right_wheel_id, vehicle_type
        )
        
        # Achsenergebnis erstellen
        axle_result = AxleTestResult(
            axle_id=axle_id,
            left_wheel=left_result,
            right_wheel=right_result
        )
        
        # Unbalanzen berechnen
        axle_result.calculate_imbalances()
        
        # Relative Kriterien bewerten (5.6)
        axle_result.relative_rfa_max_pass = (axle_result.d_rfa_max or 0) <= self.params.RC_RFA_MAX
        axle_result.relative_phi_min_pass = (axle_result.d_phi_min or 0) <= self.params.RC_PHI_MIN
        axle_result.relative_rigidity_pass = (axle_result.d_rigidity or 0) <= self.params.RC_RIG
        
        logger.info(f"Axle test completed: {axle_result.overall_pass}")
        
        return axle_result
    
    def _validate_input_data(self, platform_pos: np.ndarray, tire_force: np.ndarray,
                           time_array: np.ndarray, static_weight: float) -> bool:
        """Validiert Eingangsdaten"""
        try:
            # Array-Längen prüfen
            if not (len(platform_pos) == len(tire_force) == len(time_array)):
                logger.error("Array length mismatch")
                return False
            
            # Mindestlänge für Analyse
            if len(time_array) < 1000:
                logger.error("Insufficient data length")
                return False
            
            # Gewichtsvalidierung
            if not self.params.validate_vehicle_weight(static_weight):
                logger.error(f"Invalid static weight: {static_weight}")
                return False
            
            # Abtastrate prüfen
            dt = time_array[1] - time_array[0]
            fs = 1.0 / dt
            if fs < self.params.MIN_SAMPLING_RATE:
                logger.error(f"Sampling rate too low: {fs}Hz")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Data validation error: {e}")
            return False
    
    def _create_invalid_result(self, wheel_id: str, vehicle_type: VehicleType, 
                             static_weight: float) -> EGEATestResult:
        """Erstellt Fallback-Ergebnis für ungültige Eingaben"""
        from ....suspension_core.egea.models.results import PhaseShiftResult, ForceAnalysisResult, RigidityResult, DynamicCalibrationResult
        
        return EGEATestResult(
            wheel_id=wheel_id,
            vehicle_type=vehicle_type,
            phase_shift_result=PhaseShiftResult(static_weight=static_weight),
            force_analysis=ForceAnalysisResult(
                fmin=0, fmax=0, fa_max=0, resonant_frequency=0,
                rfa_max=0, static_weight=static_weight
            ),
            rigidity_result=RigidityResult(rigidity=0, h25=0, platform_amplitude=3.0),
            dynamic_calibration=DynamicCalibrationResult(is_valid=False),
            error_messages=["Invalid input data"]
        )
    
    def _log_test_result(self, result: EGEATestResult) -> None:
        """Protokolliert Testergebnis"""
        summary = result.summary
        logger.info(f"Test result for {summary['wheel_id']}: "
                   f"φmin={summary['min_phase_shift']:.1f}°, "
                   f"RFAmax={summary['rfa_max']:.1f}%, "
                   f"Pass={summary['overall_pass']}")
    
    def generate_test_report(self, axle_result: AxleTestResult) -> Dict[str, Any]:
        """Generiert detaillierten Testbericht"""
        return {
            "timestamp": datetime.now().isoformat(),
            "axle_id": axle_result.axle_id,
            "overall_pass": axle_result.overall_pass,
            "axle_weight": axle_result.axle_weight,
            "left_wheel": axle_result.left_wheel.summary,
            "right_wheel": axle_result.right_wheel.summary,
            "imbalances": {
                "d_rfa_max": axle_result.d_rfa_max,
                "d_phi_min": axle_result.d_phi_min,
                "d_rigidity": axle_result.d_rigidity
            },
            "relative_criteria": {
                "rfa_max_pass": axle_result.relative_rfa_max_pass,
                "phi_min_pass": axle_result.relative_phi_min_pass,
                "rigidity_pass": axle_result.relative_rigidity_pass
            }
        }


def create_demo_vehicle_data() -> Dict[str, np.ndarray]:
    """
    Erstellt Demo-Fahrzeugdaten für verschiedene Szenarien
    """
    logger.info("Creating demo vehicle data")
    
    # Guter Dämpfer (links)
    time_good, platform_pos_good, tire_force_good = create_egea_test_signals(
        duration=15.0, fs=1000.0, start_freq=25.0, end_freq=5.0
    )
    
    # Schlechter Dämpfer (rechts) - höhere Phasenverschiebung
    time_bad, platform_pos_bad, tire_force_bad = create_egea_test_signals(
        duration=15.0, fs=1000.0, start_freq=25.0, end_freq=5.0
    )
    
    # Verschlechtere rechten Dämpfer durch zusätzliche Phasenverschiebung
    phase_degradation = np.linspace(0, np.pi/3, len(tire_force_bad))
    tire_force_bad = tire_force_bad * 0.8 + 100 * np.sin(phase_degradation)
    
    return {
        "time": time_good,
        "left_platform": platform_pos_good,
        "left_force": tire_force_good,
        "right_platform": platform_pos_bad, 
        "right_force": tire_force_bad
    }


def plot_test_results(axle_result: AxleTestResult, demo_data: Dict[str, np.ndarray]) -> None:
    """
    Visualisiert Testergebnisse
    """
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'EGEA Phase_Shift Test Results - {axle_result.axle_id} Axle', fontsize=16)
    
    time = demo_data["time"][:5000]  # Erste 5 Sekunden anzeigen
    
    # Linkes Rad - Kraftsignal
    axes[0, 0].plot(time, demo_data["left_force"][:5000], 'b-', label='Tire Force')
    axes[0, 0].axhline(y=axle_result.left_wheel.phase_shift_result.static_weight, 
                      color='r', linestyle='--', label='Static Weight')
    axes[0, 0].set_title(f'Left Wheel ({axle_result.left_wheel.wheel_id})')
    axes[0, 0].set_xlabel('Time [s]')
    axes[0, 0].set_ylabel('Force [N]')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Rechtes Rad - Kraftsignal
    axes[0, 1].plot(time, demo_data["right_force"][:5000], 'g-', label='Tire Force')
    axes[0, 1].axhline(y=axle_result.right_wheel.phase_shift_result.static_weight,
                      color='r', linestyle='--', label='Static Weight')
    axes[0, 1].set_title(f'Right Wheel ({axle_result.right_wheel.wheel_id})')
    axes[0, 1].set_xlabel('Time [s]')
    axes[0, 1].set_ylabel('Force [N]')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Phasenverschiebung vs. Frequenz (links)
    left_phases = axle_result.left_wheel.phase_shift_result.phase_shifts
    left_freqs = axle_result.left_wheel.phase_shift_result.frequencies
    if left_phases:
        axes[1, 0].scatter(left_freqs, left_phases, c='blue', alpha=0.7)
        axes[1, 0].axhline(y=EGEAParameters.PHASE_SHIFT_MIN, color='r', 
                          linestyle='--', label='35° Limit')
        axes[1, 0].set_title(f'Phase Shift - Left (φmin={axle_result.left_wheel.phase_shift_result.min_phase_shift:.1f}°)')
    axes[1, 0].set_xlabel('Frequency [Hz]')
    axes[1, 0].set_ylabel('Phase Shift [°]')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    # Phasenverschiebung vs. Frequenz (rechts)
    right_phases = axle_result.right_wheel.phase_shift_result.phase_shifts
    right_freqs = axle_result.right_wheel.phase_shift_result.frequencies
    if right_phases:
        axes[1, 1].scatter(right_freqs, right_phases, c='green', alpha=0.7)
        axes[1, 1].axhline(y=EGEAParameters.PHASE_SHIFT_MIN, color='r',
                          linestyle='--', label='35° Limit')
        axes[1, 1].set_title(f'Phase Shift - Right (φmin={axle_result.right_wheel.phase_shift_result.min_phase_shift:.1f}°)')
    axes[1, 1].set_xlabel('Frequency [Hz]')
    axes[1, 1].set_ylabel('Phase Shift [°]')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


def main():
    """
    Hauptfunktion - Demonstriert vollständige EGEA-Implementierung
    """
    print("=" * 60)
    print("EGEA Phase_Shift Fahrwerkstester - Verbesserte Implementierung")
    print("=" * 60)
    
    # Test-Controller initialisieren
    controller = EGEATestController()
    
    # Demo-Daten generieren
    demo_data = create_demo_vehicle_data()
    
    # Statische Gewichte definieren
    left_static_weight = 500.0  # N
    right_static_weight = 480.0  # N (leicht unterschiedlich)
    
    print(f"\nStarting Front Axle Test...")
    print(f"Left wheel static weight: {left_static_weight}N")
    print(f"Right wheel static weight: {right_static_weight}N")
    
    # Vorderachsen-Test durchführen
    axle_result = controller.run_axle_test(
        left_platform_pos=demo_data["left_platform"],
        left_tire_force=demo_data["left_force"],
        right_platform_pos=demo_data["right_platform"], 
        right_tire_force=demo_data["right_force"],
        time_array=demo_data["time"],
        left_static_weight=left_static_weight,
        right_static_weight=right_static_weight,
        axle_id="Front",
        vehicle_type=VehicleType.M1
    )
    
    # Ergebnisse anzeigen
    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    
    # Linkes Rad
    left_summary = axle_result.left_wheel.summary
    print(f"\nLeft Wheel (FL):")
    print(f"  φmin: {left_summary['min_phase_shift']:.1f}° (iφmin: {left_summary['integer_min_phase']}°)")
    print(f"  RFAmax: {left_summary['rfa_max']:.1f}%")
    print(f"  Rigidity: {axle_result.left_wheel.rigidity_result.rigidity:.1f} N/mm")
    print(f"  Absolute Criterion: {'PASS' if left_summary['absolute_pass'] else 'FAIL'}")
    print(f"  Overall Result: {'PASS' if left_summary['overall_pass'] else 'FAIL'}")
    
    # Rechtes Rad
    right_summary = axle_result.right_wheel.summary
    print(f"\nRight Wheel (FR):")
    print(f"  φmin: {right_summary['min_phase_shift']:.1f}° (iφmin: {right_summary['integer_min_phase']}°)")
    print(f"  RFAmax: {right_summary['rfa_max']:.1f}%")
    print(f"  Rigidity: {axle_result.right_wheel.rigidity_result.rigidity:.1f} N/mm")
    print(f"  Absolute Criterion: {'PASS' if right_summary['absolute_pass'] else 'FAIL'}")
    print(f"  Overall Result: {'PASS' if right_summary['overall_pass'] else 'FAIL'}")
    
    # Achsen-Unbalanzen
    print(f"\nAxle Imbalances:")
    print(f"  DRFAmax: {axle_result.d_rfa_max:.1f}% (Limit: {EGEAParameters.RC_RFA_MAX}%)")
    print(f"  Dφmin: {axle_result.d_phi_min:.1f}% (Limit: {EGEAParameters.RC_PHI_MIN}%)")
    print(f"  DRigidity: {axle_result.d_rigidity:.1f}% (Limit: {EGEAParameters.RC_RIG}%)")
    
    # Relative Kriterien
    print(f"\nRelative Criteria:")
    print(f"  RFAmax Balance: {'PASS' if axle_result.relative_rfa_max_pass else 'FAIL'}")
    print(f"  φmin Balance: {'PASS' if axle_result.relative_phi_min_pass else 'FAIL'}")
    print(f"  Rigidity Balance: {'PASS' if axle_result.relative_rigidity_pass else 'FAIL'}")
    
    # Gesamtergebnis
    print(f"\nOVERALL AXLE RESULT: {'PASS' if axle_result.overall_pass else 'FAIL'}")
    
    # Detaillierter Bericht generieren
    detailed_report = controller.generate_test_report(axle_result)
    
    print(f"\nDetailed report generated at: {detailed_report['timestamp']}")
    
    # Visualisierung (optional)
    try:
        plot_test_results(axle_result, demo_data)
    except ImportError:
        print("Matplotlib not available - skipping visualization")
    except Exception as e:
        print(f"Visualization error: {e}")
    
    print("\n" + "=" * 60)
    print("EGEA Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()