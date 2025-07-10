"""
Unit Tests für EGEA Signal Processing
Testet alle Signalverarbeitungsfunktionen
"""

import unittest
import numpy as np

# Import der zu testenden Module
from ...egea.utils.signal_processing import EGEASignalProcessor, create_egea_test_signals


class TestEGEASignalProcessor(unittest.TestCase):
    """Test Signal Processing Funktionen"""
    
    def setUp(self):
        self.processor = EGEASignalProcessor()
        
        # Test-Signal erstellen
        self.duration = 10.0
        self.fs = 1000.0
        self.time, self.platform_pos, self.tire_force = create_egea_test_signals(
            duration=self.duration, fs=self.fs
        )
    
    def test_signal_creation(self):
        """Test Test-Signal Erstellung"""
        expected_length = int(self.duration * self.fs)
        self.assertEqual(len(self.time), expected_length)
        self.assertEqual(len(self.platform_pos), expected_length)
        self.assertEqual(len(self.tire_force), expected_length)
    
    def test_platform_tops_detection(self):
        """Test Platform TOP Erkennung"""
        tops = self.processor.find_platform_tops(self.platform_pos)
        
        # Sollte mehrere TOPs finden
        self.assertGreater(len(tops), 5)
        
        # TOPs sollten lokale Maxima sein
        for top_idx in tops:
            if top_idx > 10 and top_idx < len(self.platform_pos) - 10:
                # Prüfe dass es ein lokales Maximum ist
                local_max = np.max(self.platform_pos[top_idx-5:top_idx+5])
                self.assertAlmostEqual(self.platform_pos[top_idx], local_max, places=5)
    
    def test_static_weight_crossings(self):
        """Test Kreuzungserkennung mit statischem Gewicht"""
        static_weight = 500.0
        crossings = self.processor.find_static_weight_crossings(
            self.tire_force[:1000], self.time[:1000], static_weight
        )
        
        # Sollte mehrere Kreuzungen finden
        self.assertGreater(len(crossings), 2)
        
        # Jede Kreuzung sollte Zeit und Richtung haben
        for crossing_time, direction in crossings:
            self.assertIsInstance(crossing_time, float)
            self.assertIn(direction, ['up', 'down'])
    
    def test_rfst_validation(self):
        """Test RFstFMin/RFstFMax Validierung"""
        # Test mit gültigem Signal
        force_segment = self.tire_force[1000:2000]
        static_weight = np.mean(force_segment)
        
        is_valid = self.processor.validate_rfst_conditions(force_segment, static_weight)
        self.assertTrue(is_valid)
        
        # Test mit ungültigem Signal (statisches Gewicht zu weit außerhalb)
        invalid_static_weight = np.max(force_segment) + 100
        is_invalid = self.processor.validate_rfst_conditions(force_segment, invalid_static_weight)
        self.assertFalse(is_invalid)
    
    def test_egea_phase_filter(self):
        """Test EGEA Phasenfilter"""
        test_signal = np.random.normal(0, 1, 1000)
        frequency_step = 10.0
        
        filtered = self.processor.apply_egea_phase_filter(test_signal, self.fs, frequency_step)
        
        # Gefiltertes Signal sollte glatter sein
        original_variance = np.var(test_signal)
        filtered_variance = np.var(filtered)
        self.assertLess(filtered_variance, original_variance)
    
    def test_overflow_underflow_detection(self):
        """Test Signal Overflow/Underflow Erkennung"""
        static_weight = 500.0
        
        # Normales Signal
        f_under, f_over = self.processor.detect_signal_overflow_underflow(
            self.tire_force, static_weight
        )
        
        # Sollte normalerweise keine Flags setzen
        self.assertIsInstance(f_under, bool)
        self.assertIsInstance(f_over, bool)
        
        # Test mit Underflow-Signal
        underflow_signal = np.full(100, static_weight * 0.005)  # Sehr niedrig
        f_under_test, _ = self.processor.detect_signal_overflow_underflow(
            underflow_signal, static_weight
        )
        self.assertTrue(f_under_test)


if __name__ == "__main__":
    unittest.main()