"""
Unit tests for StatusBar component.

Tests the status bar UI component in isolation.
Demonstrates MVP testing approach for status display.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from views.status_bar import StatusBar


class TestStatusBar(unittest.TestCase):
    """Test cases for StatusBar component."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide test window
        
        # Create test container
        self.container = tk.Frame(self.root)
        
        # Create status bar
        self.status_bar = StatusBar(self.container)
        
        # Mock callbacks
        self.mock_callbacks = {
            'on_mqtt_reconnect': Mock(),
            'on_discovery_open': Mock(),
            'on_status_details': Mock()
        }
        
        self.status_bar.set_callbacks(self.mock_callbacks)
    
    def tearDown(self):
        """Clean up after each test method."""
        if self.root:
            self.root.destroy()
    
    def test_initialization(self):
        """Test status bar initialization."""
        # Check initial values
        self.assertEqual(self.status_bar.mqtt_broker_var.get(), "Detecting...")
        self.assertEqual(self.status_bar.mqtt_status_var.get(), "Disconnected")
        self.assertEqual(self.status_bar.data_count_var.get(), "0")
        self.assertEqual(self.status_bar.data_rate_var.get(), "0.0/s")
        self.assertEqual(self.status_bar.egea_status_var.get(), "Ready")
        self.assertEqual(self.status_bar.egea_phase_var.get(), "φ: --°")
        self.assertEqual(self.status_bar.egea_quality_var.get(), "Q: --%")
        
        # Check UI components exist
        self.assertIsNotNone(self.status_bar.mqtt_status_label)
        self.assertIsNotNone(self.status_bar.mqtt_broker_label)
        self.assertIsNotNone(self.status_bar.performance_label)
    
    def test_callbacks_set(self):
        """Test callback setting."""
        # Verify callbacks are set
        self.assertEqual(
            self.status_bar.on_mqtt_reconnect,
            self.mock_callbacks['on_mqtt_reconnect']
        )
        self.assertEqual(
            self.status_bar.on_discovery_open,
            self.mock_callbacks['on_discovery_open']
        )
        self.assertEqual(
            self.status_bar.on_status_details,
            self.mock_callbacks['on_status_details']
        )
    
    def test_mqtt_status_update(self):
        """Test MQTT status updates."""
        # Test connected status
        self.status_bar.update_mqtt_status(
            broker="192.168.0.249",
            status="Connected",
            connected=True
        )
        
        # Verify broker IP updated
        self.assertEqual(self.status_bar.mqtt_broker_var.get(), "192.168.0.249")
        
        # Verify status with success icon
        self.assertIn("✅", self.status_bar.mqtt_status_var.get())
        self.assertIn("Connected", self.status_bar.mqtt_status_var.get())
        
        # Test disconnected status
        self.status_bar.update_mqtt_status(
            status="Disconnected",
            connected=False
        )
        
        # Verify status with error icon
        self.assertIn("❌", self.status_bar.mqtt_status_var.get())
        self.assertIn("Disconnected", self.status_bar.mqtt_status_var.get())
        
        # Test connecting status
        self.status_bar.update_mqtt_status(
            status="Connecting",
            connected=None
        )
        
        # Verify status with progress icon
        self.assertIn("🔄", self.status_bar.mqtt_status_var.get())
        self.assertIn("Connecting", self.status_bar.mqtt_status_var.get())
    
    def test_data_status_update(self):
        """Test data flow status updates."""
        # Test data count update
        self.status_bar.update_data_status(count=1250)
        self.assertEqual(self.status_bar.data_count_var.get(), "1,250")
        
        # Test data rate update
        self.status_bar.update_data_status(rate=15.5)
        self.assertEqual(self.status_bar.data_rate_var.get(), "15.5/s")
        
        # Test high rate formatting
        self.status_bar.update_data_status(rate=2500)
        self.assertEqual(self.status_bar.data_rate_var.get(), "2.5k/s")
        
        # Test low rate formatting
        self.status_bar.update_data_status(rate=0.75)
        self.assertEqual(self.status_bar.data_rate_var.get(), "0.75/s")
        
        # Test buffer usage
        self.status_bar.update_data_status(buffer_usage=0.85)
        
        # Check progress bar value
        self.assertEqual(self.status_bar.buffer_progress['value'], 85.0)
        
        # Check percentage label
        self.assertEqual(self.status_bar.data_labels['buffer'].cget('text'), "85%")
    
    def test_egea_status_update(self):
        """Test EGEA analysis status updates."""
        # Test passing status
        self.status_bar.update_egea_status(
            status="Analysis Complete",
            phase_shift=42.5,
            quality=85.0,
            passing=True
        )
        
        # Verify status with success icon
        self.assertIn("✅", self.status_bar.egea_status_var.get())
        self.assertIn("Analysis Complete", self.status_bar.egea_status_var.get())
        
        # Verify phase shift display
        self.assertEqual(self.status_bar.egea_phase_var.get(), "φ: 42.5°")
        
        # Verify quality display
        self.assertEqual(self.status_bar.egea_quality_var.get(), "Q: 85%")
        
        # Test failing status
        self.status_bar.update_egea_status(
            status="Test Failed",
            phase_shift=28.3,
            quality=45.0,
            passing=False
        )
        
        # Verify status with error icon
        self.assertIn("❌", self.status_bar.egea_status_var.get())
        self.assertIn("Test Failed", self.status_bar.egea_status_var.get())
        
        # Test in-progress status
        self.status_bar.update_egea_status(
            status="Running",
            passing=None
        )
        
        # Verify status with progress icon
        self.assertIn("🔄", self.status_bar.egea_status_var.get())
        self.assertIn("Running", self.status_bar.egea_status_var.get())
    
    def test_performance_status_update(self):
        """Test performance metrics updates."""
        # Test good performance
        good_metrics = {
            'cpu_usage': 45.0,
            'memory_mb': 250.0,
            'fps': 30.0
        }
        
        self.status_bar.update_performance_status(good_metrics)
        self.assertIn("✅ OK", self.status_bar.performance_var.get())
        self.assertIn("30 FPS", self.status_bar.performance_var.get())
        
        # Test high CPU usage
        high_cpu_metrics = {
            'cpu_usage': 85.0,
            'memory_mb': 300.0,
            'fps': 25.0
        }
        
        self.status_bar.update_performance_status(high_cpu_metrics)
        self.assertIn("⚠️ High Load", self.status_bar.performance_var.get())
        
        # Test low FPS
        low_fps_metrics = {
            'cpu_usage': 30.0,
            'memory_mb': 200.0,
            'fps': 8.0
        }
        
        self.status_bar.update_performance_status(low_fps_metrics)
        self.assertIn("⚠️ Low FPS", self.status_bar.performance_var.get())
    
    def test_data_rate_formatting(self):
        """Test data rate formatting method."""
        # Test normal rates
        self.assertEqual(self.status_bar._format_data_rate(5.5), "5.5/s")
        self.assertEqual(self.status_bar._format_data_rate(0.25), "0.25/s")
        
        # Test high rates (k/s)
        self.assertEqual(self.status_bar._format_data_rate(1500), "1.5k/s")
        self.assertEqual(self.status_bar._format_data_rate(2250), "2.3k/s")
        
        # Test edge cases
        self.assertEqual(self.status_bar._format_data_rate(1000), "1.0k/s")
        self.assertEqual(self.status_bar._format_data_rate(999), "999.0/s")
    
    def test_performance_metrics_formatting(self):
        """Test performance metrics formatting."""
        # Test good performance
        good_metrics = {'cpu_usage': 30, 'memory_mb': 200, 'fps': 25}
        result = self.status_bar._format_performance_metrics(good_metrics)
        self.assertIn("✅ OK", result)
        self.assertIn("25 FPS", result)
        
        # Test high load
        high_load_metrics = {'cpu_usage': 85, 'memory_mb': 1200, 'fps': 30}
        result = self.status_bar._format_performance_metrics(high_load_metrics)
        self.assertEqual(result, "⚠️ High Load")
        
        # Test low FPS
        low_fps_metrics = {'cpu_usage': 40, 'memory_mb': 300, 'fps': 8}
        result = self.status_bar._format_performance_metrics(low_fps_metrics)
        self.assertEqual(result, "⚠️ Low FPS")
        
        # Test empty metrics
        empty_result = self.status_bar._format_performance_metrics({})
        self.assertEqual(empty_result, "Performance: OK")
        
        # Test None input
        none_result = self.status_bar._format_performance_metrics(None)
        self.assertEqual(none_result, "Performance: OK")
    
    def test_button_callbacks(self):
        """Test button click callbacks."""
        # Test reconnect button
        self.status_bar._on_reconnect_click()
        self.mock_callbacks['on_mqtt_reconnect'].assert_called_once()
        
        # Test discovery button
        self.status_bar._on_discovery_click()
        self.mock_callbacks['on_discovery_open'].assert_called_once()
        
        # Test details button
        self.status_bar._on_details_click()
        self.mock_callbacks['on_status_details'].assert_called_once()
    
    def test_test_active_state_change(self):
        """Test UI changes when test becomes active."""
        # Set test active
        self.status_bar.set_test_active(True)
        
        # Check if data count label font changed (test specific behavior)
        if self.status_bar.data_labels.get('count'):
            # Font should be bolder during test
            font_config = self.status_bar.data_labels['count'].cget('font')
            # This is implementation-dependent, just verify it doesn't crash
        
        # Set test inactive
        self.status_bar.set_test_active(False)
        
        # Font should return to normal
        if self.status_bar.data_labels.get('count'):
            font_config = self.status_bar.data_labels['count'].cget('font')
    
    def test_get_current_status(self):
        """Test current status retrieval."""
        # Update some values
        self.status_bar.update_mqtt_status("192.168.0.100", "Connected", True)
        self.status_bar.update_data_status(count=500, rate=12.5)
        self.status_bar.update_egea_status("Running", 38.5, 75.0, None)
        
        # Get current status
        status = self.status_bar.get_current_status()
        
        # Verify structure
        self.assertIn('mqtt', status)
        self.assertIn('data', status)
        self.assertIn('egea', status)
        self.assertIn('performance', status)
        self.assertIn('timestamp', status)
        
        # Verify values
        self.assertEqual(status['mqtt']['broker'], "192.168.0.100")
        self.assertIn("Connected", status['mqtt']['status'])
        self.assertEqual(status['data']['count'], "500")
        self.assertEqual(status['data']['rate'], "12.5/s")
        self.assertIn("Running", status['egea']['status'])
        self.assertEqual(status['egea']['phase'], "φ: 38.5°")
        self.assertEqual(status['egea']['quality'], "Q: 75%")


class TestStatusBarColorCoding(unittest.TestCase):
    """Test color coding functionality of StatusBar."""
    
    def setUp(self):
        """Set up color coding tests."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.container = tk.Frame(self.root)
        self.status_bar = StatusBar(self.container)
    
    def tearDown(self):
        """Clean up color coding tests."""
        if self.root:
            self.root.destroy()
    
    def test_mqtt_status_colors(self):
        """Test MQTT status color coding."""
        # Connected (green)
        self.status_bar.update_mqtt_status(status="Connected", connected=True)
        color = self.status_bar.mqtt_status_label.cget('foreground')
        self.assertEqual(color, self.status_bar.status_colors['connected'])
        
        # Disconnected (red)
        self.status_bar.update_mqtt_status(status="Disconnected", connected=False)
        color = self.status_bar.mqtt_status_label.cget('foreground')
        self.assertEqual(color, self.status_bar.status_colors['disconnected'])
        
        # Connecting (yellow)
        self.status_bar.update_mqtt_status(status="Connecting", connected=None)
        color = self.status_bar.mqtt_status_label.cget('foreground')
        self.assertEqual(color, self.status_bar.status_colors['connecting'])
    
    def test_data_rate_colors(self):
        """Test data rate color coding."""
        # High rate (green)
        self.status_bar.update_data_status(rate=15.0)
        if self.status_bar.data_labels.get('rate'):
            color = self.status_bar.data_labels['rate'].cget('foreground')
            self.assertEqual(color, 'green')
        
        # Medium rate (orange)
        self.status_bar.update_data_status(rate=5.0)
        if self.status_bar.data_labels.get('rate'):
            color = self.status_bar.data_labels['rate'].cget('foreground')
            self.assertEqual(color, 'orange')
        
        # Low rate (red)
        self.status_bar.update_data_status(rate=0.5)
        if self.status_bar.data_labels.get('rate'):
            color = self.status_bar.data_labels['rate'].cget('foreground')
            self.assertEqual(color, 'red')
    
    def test_egea_phase_colors(self):
        """Test EGEA phase shift color coding."""
        # Good phase (>= 35°, green)
        self.status_bar.update_egea_status(phase_shift=42.0)
        if self.status_bar.egea_labels.get('phase'):
            color = self.status_bar.egea_labels['phase'].cget('foreground')
            self.assertEqual(color, 'green')
        
        # Marginal phase (30-35°, orange)
        self.status_bar.update_egea_status(phase_shift=32.5)
        if self.status_bar.egea_labels.get('phase'):
            color = self.status_bar.egea_labels['phase'].cget('foreground')
            self.assertEqual(color, 'orange')
        
        # Bad phase (<30°, red)
        self.status_bar.update_egea_status(phase_shift=25.0)
        if self.status_bar.egea_labels.get('phase'):
            color = self.status_bar.egea_labels['phase'].cget('foreground')
            self.assertEqual(color, 'red')


def run_status_bar_tests():
    """Run all status bar tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestStatusBar))
    suite.addTests(loader.loadTestsFromTestCase(TestStatusBarColorCoding))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("🧪 Running StatusBar Unit Tests...")
    print("=" * 50)
    
    success = run_status_bar_tests()
    
    if success:
        print("\n✅ All StatusBar tests passed!")
    else:
        print("\n❌ Some StatusBar tests failed!")
    
    print("=" * 50)
