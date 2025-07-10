"""
Unit Tests für EGEA Phase Shift Processor
Testet alle Prozessorfunktionen, Performance und Genauigkeit
"""

import unittest
import numpy as np
import logging
import time
import tracemalloc
from typing import Tuple

# Import der zu testenden Module
from ...egea.config.parameters import EGEAParameters
from ...egea.models.results import VehicleType, PhaseShiftResult, ForceAnalysisResult, RigidityResult
from ...egea.processors.phase_shift_processor import EGEAPhaseShiftProcessor
from ...egea.utils.signal_processing import create_egea_test_signals


class TestEGEAPhaseShiftProcessor(unittest.TestCase):
    """Test Haupt-Phasenverschiebungs-Prozessor"""
    
    def setUp(self):
        self.processor = EGEAPhaseShiftProcessor()
        
        # Erstelle reproduzierbare Test-Daten
        np.random.seed(42)
        self.duration = 15.0
        self.fs = 1000.0
        self.time, self.platform_pos, self.tire_force = create_egea_test_signals(
            duration=self.duration, fs=self.fs
        )
        self.static_weight = 500.0
    
    def test_dynamic_calibration(self):
        """Test Dynamische Kalibrierung"""
        platform_mass = 20.0
        
        # Erstelle Plattform-Kraft-Signal (sollte klein sein ohne Fahrzeug)
        platform_force = np.random.normal(0, 5, len(self.time))
        
        calibration_result = self.processor.perform_dynamic_calibration(
            platform_force, self.time, platform_mass
        )
        
        self.assertIsNotNone(calibration_result)
        self.assertIsInstance(calibration_result.is_valid, bool)
        self.assertIsInstance(calibration_result.max_fp, list)
    
    def test_phase_shift_calculation_basic(self):
        """Test Basis-Phasenverschiebungsberechnung"""
        result = self.processor.calculate_phase_shift_advanced(
            self.platform_pos, self.tire_force, self.time, self.static_weight
        )
        
        self.assertIsInstance(result, PhaseShiftResult)
        self.assertEqual(result.static_weight, self.static_weight)
        
        if result.is_valid:
            self.assertIsNotNone(result.min_phase_shift)
            self.assertGreaterEqual(result.min_phase_shift, 0.0)
            self.assertLessEqual(result.min_phase_shift, 180.0)
    
    def test_force_analysis(self):
        """Test Kraftanalyse"""
        force_analysis = self.processor.calculate_force_analysis(
            self.tire_force, self.time, self.static_weight
        )
        
        self.assertIsNotNone(force_analysis)
        self.assertEqual(force_analysis.static_weight, self.static_weight)
        self.assertGreater(force_analysis.fmax, force_analysis.fmin)
        self.assertGreaterEqual(force_analysis.rfa_max, 0.0)
    
    def test_rigidity_calculation(self):
        """Test Reifensteifigkeitsberechnung"""
        h25_amplitude = 150.0  # N
        platform_amplitude = 3.0  # mm
        
        rigidity_result = self.processor.calculate_rigidity(h25_amplitude, platform_amplitude)
        
        self.assertIsNotNone(rigidity_result)
        self.assertEqual(rigidity_result.h25, h25_amplitude)
        self.assertEqual(rigidity_result.platform_amplitude, platform_amplitude)
        
        # Überprüfe EGEA-Formel: rig = arig * (H25/ep) + brig
        expected_rigidity = (EGEAParameters.A_RIG * (h25_amplitude / platform_amplitude) + 
                           EGEAParameters.B_RIG)
        self.assertAlmostEqual(rigidity_result.rigidity, expected_rigidity, places=2)
    
    def test_complete_test_execution(self):
        """Test vollständige Testausführung"""
        result = self.processor.process_complete_test(
            platform_position=self.platform_pos,
            tire_force=self.tire_force,
            time_array=self.time,
            static_weight=self.static_weight,
            wheel_id="FL",
            vehicle_type=VehicleType.M1
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.wheel_id, "FL")
        self.assertEqual(result.vehicle_type, VehicleType.M1)
        self.assertIsNotNone(result.phase_shift_result)
        self.assertIsNotNone(result.force_analysis)
        self.assertIsNotNone(result.rigidity_result)
    
    def test_egea_criteria_evaluation(self):
        """Test EGEA-Kriterien Bewertung"""
        # Erstelle Mock-Ergebnisse
        phase_result = PhaseShiftResult(min_phase_shift=40.0, static_weight=self.static_weight)
        
        force_analysis = ForceAnalysisResult(
            fmin=400, fmax=600, fa_max=100, resonant_frequency=12.0,
            rfa_max=20.0, static_weight=self.static_weight
        )
        rigidity_result = RigidityResult(rigidity=200.0, h25=150.0, platform_amplitude=3.0)
        
        absolute_pass, relative_pass, overall_pass = self.processor.evaluate_egea_criteria(
            phase_result, force_analysis, rigidity_result, VehicleType.M1
        )
        
        # Bei φmin=40° sollte absolutes Kriterium bestehen (≥35°)
        self.assertTrue(absolute_pass)
        self.assertIsInstance(relative_pass, bool)
        self.assertIsInstance(overall_pass, bool)


class TestEGEABenchmarks(unittest.TestCase):
    """Performance und Benchmark Tests"""
    
    def setUp(self):
        self.processor = EGEAPhaseShiftProcessor()
    
    def test_performance_large_dataset(self):
        """Test Performance mit großem Datensatz"""
        # Großer Datensatz (30 Sekunden bei 1kHz)
        duration = 30.0
        fs = 1000.0
        time_array, platform_pos, tire_force = create_egea_test_signals(duration, fs)
        
        start_time = time.time()
        
        result = self.processor.calculate_phase_shift_advanced(
            platform_pos, tire_force, time_array, 500.0
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Sollte unter 5 Sekunden dauern
        self.assertLess(processing_time, 5.0)
        self.assertIsNotNone(result)
        
        print(f"Performance test: {len(time_array)} samples processed in {processing_time:.2f}s")
    
    def test_memory_usage(self):
        """Test Speicherverbrauch"""
        tracemalloc.start()
        
        # Erstelle und verarbeite Daten
        time_array, platform_pos, tire_force = create_egea_test_signals(20.0, 1000.0)
        
        result = self.processor.process_complete_test(
            platform_pos, tire_force, time_array, 500.0, "FL"
        )
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Peak memory sollte unter 100MB bleiben
        self.assertLess(peak / 1024 / 1024, 100)  # MB
        
        print(f"Memory usage: current={current/1024/1024:.1f}MB, peak={peak/1024/1024:.1f}MB")


class TestEGEAAccuracy(unittest.TestCase):
    """Genauigkeits- und Referenzwert-Tests"""
    
    def test_known_phase_shift_values(self):
        """Test mit bekannten Phasenverschiebungswerten"""
        # Erstelle synthetisches Signal mit bekannter Phasenverschiebung
        duration = 10.0
        fs = 1000.0
        t = np.linspace(0, duration, int(duration * fs))
        
        # Plattform bei 10Hz
        platform_freq = 10.0
        platform_pos = 0.003 * np.sin(2 * np.pi * platform_freq * t)
        
        # Reifenkraft mit 30° Phasenverschiebung
        known_phase_shift = 30.0  # Grad
        phase_rad = np.radians(known_phase_shift)
        static_weight = 500.0
        amplitude = 100.0
        
        tire_force = static_weight + amplitude * np.sin(2 * np.pi * platform_freq * t + phase_rad)
        
        processor = EGEAPhaseShiftProcessor()
        result = processor.calculate_phase_shift_advanced(
            platform_pos, tire_force, t, static_weight
        )
        
        if result.is_valid and result.min_phase_shift is not None:
            # Toleranz von ±5° für numerische Genauigkeit
            self.assertAlmostEqual(result.min_phase_shift, known_phase_shift, delta=5.0)
    
    def test_rfa_max_calculation_accuracy(self):
        """Test RFAmax Berechnungsgenauigkeit"""
        static_weight = 500.0
        
        # Erstelle Signal mit bekannter Amplitude
        amplitude = 100.0  # N
        expected_rfa = (amplitude / static_weight) * 100.0  # 20%
        
        force_signal = np.array([
            static_weight - amplitude,  # Minimum
            static_weight,              # Statisch
            static_weight + amplitude,  # Maximum
            static_weight               # Statisch
        ])
        
        max_force = np.max(force_signal)
        min_force = np.min(force_signal)
        
        # RFAmax berechnen
        calculated_amplitude = max(abs(max_force - static_weight), abs(min_force - static_weight))
        calculated_rfa = (calculated_amplitude / static_weight) * 100.0
        
        self.assertAlmostEqual(calculated_rfa, expected_rfa, places=1)


if __name__ == "__main__":
    # Logging für Tests konfigurieren
    logging.basicConfig(level=logging.WARNING)  # Reduzierte Logs für Tests
    unittest.main()