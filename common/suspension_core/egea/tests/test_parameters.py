"""
Unit Tests für EGEA Parameter
Testet alle Parameter gegen bekannte Referenzwerte
"""

import unittest
import numpy as np

# Import der zu testenden Module
from ...egea.config.parameters import EGEAParameters


class TestEGEAParameters(unittest.TestCase):
    """Test EGEA Parameter Klasse"""
    
    def setUp(self):
        self.params = EGEAParameters()
    
    def test_frequency_parameters(self):
        """Test Frequenz-Parameter"""
        self.assertEqual(self.params.MIN_CALC_FREQ, 6.0)
        self.assertEqual(self.params.MAX_CALC_FREQ, 18.0)
        self.assertEqual(self.params.DELTA_F, 5.0)
    
    def test_phase_shift_parameters(self):
        """Test Phasenverschiebungs-Parameter"""
        self.assertEqual(self.params.PHASE_SHIFT_MIN, 35.0)
        self.assertEqual(self.params.PHASE_SHIFT_MAX, 180.0)
    
    def test_rigidity_calculation(self):
        """Test Reifensteifigkeits-Parameter"""
        self.assertAlmostEqual(self.params.A_RIG, 0.571, places=3)
        self.assertAlmostEqual(self.params.B_RIG, 46.0, places=1)
    
    def test_weight_validation(self):
        """Test Gewichtsvalidierung"""
        self.assertTrue(self.params.validate_vehicle_weight(500.0))
        self.assertFalse(self.params.validate_vehicle_weight(50.0))  # Zu niedrig
        self.assertFalse(self.params.validate_vehicle_weight(1500.0))  # Zu hoch
    
    def test_delta_t25_calculation(self):
        """Test ΔT25 Berechnung"""
        static_weight = 500.0  # N
        expected = static_weight * 0.16 + 1200.0
        actual = self.params.calculate_delta_t25(static_weight)
        self.assertAlmostEqual(actual, expected, places=1)


if __name__ == "__main__":
    unittest.main()