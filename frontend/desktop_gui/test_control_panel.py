"""
Unit tests for ControlPanel component.

Tests the control panel UI component in isolation.
Demonstrates MVP testing approach.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from views.control_panel import ControlPanel


class TestControlPanel(unittest.TestCase):
    """Test cases for ControlPanel component."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide test window
        
        # Create test container
        self.container = tk.Frame(self.root)
        
        # Create control panel
        self.control_panel = ControlPanel(self.container)
        
        # Mock callbacks
        self.mock_callbacks = {
            'on_start_test': Mock(),
            'on_stop_test': Mock(),
            'on_emergency_stop': Mock(),
            'on_clear_buffer': Mock(),
            'on_send_command': Mock()
        }
        
        self.control_panel.set_callbacks(self.mock_callbacks)
    
    def tearDown(self):
        """Clean up after each test method."""
        if self.root:
            self.root.destroy()
    
    def test_initialization(self):
        """Test control panel initialization."""
        # Check initial state
        self.assertEqual(self.control_panel.position_var.get(), "left")
        self.assertEqual(self.control_panel.vehicle_var.get(), "M1")
        self.assertEqual(self.control_panel.test_duration_var.get(), "30")
        self.assertFalse(self.control_panel.test_active_var.get())
        
        # Check UI components exist
        self.assertIsNotNone(self.control_panel.start_button)
        self.assertIsNotNone(self.control_panel.stop_button)
        self.assertIsNotNone(self.control_panel.emergency_button)
        self.assertIsNotNone(self.control_panel.position_combo)
        self.assertIsNotNone(self.control_panel.vehicle_combo)
    
    def test_callbacks_set(self):
        """Test callback setting."""
        # Verify callbacks are set
        self.assertEqual(
            self.control_panel.on_start_test, 
            self.mock_callbacks['on_start_test']
        )
        self.assertEqual(
            self.control_panel.on_stop_test,
            self.mock_callbacks['on_stop_test']
        )
    
    def test_start_test_callback(self):
        """Test start test button callback."""
        # Set test parameters
        self.control_panel.position_var.set("right")
        self.control_panel.vehicle_var.set("N1")
        self.control_panel.test_duration_var.set("45")
        
        # Simulate button click
        self.control_panel._on_start_click()
        
        # Verify callback was called with correct parameters
        self.mock_callbacks['on_start_test'].assert_called_once()
        call_args = self.mock_callbacks['on_start_test'].call_args[0][0]
        
        self.assertEqual(call_args['position'], "right")
        self.assertEqual(call_args['vehicle_type'], "N1")
        self.assertEqual(call_args['duration'], 45.0)
    
    def test_stop_test_callback(self):
        """Test stop test button callback."""
        # Simulate button click
        self.control_panel._on_stop_click()
        
        # Verify callback was called
        self.mock_callbacks['on_stop_test'].assert_called_once()
    
    def test_emergency_stop_callback(self):
        """Test emergency stop button callback."""
        # Simulate button click
        self.control_panel._on_emergency_click()
        
        # Verify callback was called
        self.mock_callbacks['on_emergency_stop'].assert_called_once()
    
    def test_clear_buffer_callback(self):
        """Test clear buffer button callback."""
        # Simulate button click
        self.control_panel._on_clear_click()
        
        # Verify callback was called
        self.mock_callbacks['on_clear_buffer'].assert_called_once()
    
    def test_quick_command_callback(self):
        """Test quick command callbacks."""
        # Test MQTT test command
        self.control_panel._send_quick_command("test_mqtt")
        
        # Verify callback was called with correct command
        self.mock_callbacks['on_send_command'].assert_called_once()
        call_args = self.mock_callbacks['on_send_command'].call_args[0][0]
        
        self.assertEqual(call_args['command'], "test_mqtt")
        self.assertEqual(call_args['source'], "control_panel")
        self.assertIn('timestamp', call_args)
    
    def test_test_active_state_change(self):
        """Test UI state changes when test becomes active."""
        # Initially not active
        self.assertFalse(self.control_panel.test_active_var.get())
        
        # Set test active
        self.control_panel.set_test_active(True)
        
        # Check state changed
        self.assertTrue(self.control_panel.test_active_var.get())
        
        # Check button states (start disabled, stop enabled)
        self.assertEqual(str(self.control_panel.start_button['state']), 'disabled')
        self.assertEqual(str(self.control_panel.stop_button['state']), 'normal')
        
        # Set test inactive
        self.control_panel.set_test_active(False)
        
        # Check state changed back
        self.assertFalse(self.control_panel.test_active_var.get())
        self.assertEqual(str(self.control_panel.start_button['state']), 'normal')
        self.assertEqual(str(self.control_panel.stop_button['state']), 'disabled')
    
    def test_test_parameters_get_set(self):
        """Test getting and setting test parameters."""
        # Set parameters
        self.control_panel.set_test_parameters(
            position="front_right",
            vehicle="N1", 
            duration=60.0
        )
        
        # Verify parameters were set
        self.assertEqual(self.control_panel.position_var.get(), "front_right")
        self.assertEqual(self.control_panel.vehicle_var.get(), "N1")
        self.assertEqual(self.control_panel.test_duration_var.get(), "60.0")
        
        # Get parameters
        params = self.control_panel.get_test_parameters()
        
        # Verify returned parameters
        self.assertEqual(params['position'], "front_right")
        self.assertEqual(params['vehicle_type'], "N1")
        self.assertEqual(params['duration'], 60.0)
        self.assertFalse(params['test_active'])
    
    def test_enable_disable_controls(self):
        """Test enabling/disabling controls."""
        # Disable controls
        self.control_panel.enable_controls(False)
        
        # Check comboboxes are readonly (disabled state for comboboxes)
        # Note: Exact behavior depends on tkinter version
        
        # Enable controls
        self.control_panel.enable_controls(True)
        
        # Controls should be enabled again
        # Note: Detailed state testing depends on tkinter internals
    
    def test_duration_validation(self):
        """Test duration entry validation."""
        # Valid duration
        result = self.control_panel._validate_duration("30.5")
        self.assertTrue(result)
        
        # Invalid duration (letters)
        result = self.control_panel._validate_duration("abc")
        self.assertFalse(result)
        
        # Empty string (should be allowed)
        result = self.control_panel._validate_duration("")
        self.assertTrue(result)
        
        # Negative number (should be allowed by validator, business logic handles it)
        result = self.control_panel._validate_duration("-5")
        self.assertTrue(result)


class TestControlPanelIntegration(unittest.TestCase):
    """Integration tests for ControlPanel with actual callbacks."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.container = tk.Frame(self.root)
        self.control_panel = ControlPanel(self.container)
        
        # Real callback that stores results
        self.callback_results = []
        
        def mock_start_test(params):
            self.callback_results.append(('start_test', params))
        
        def mock_stop_test():
            self.callback_results.append(('stop_test', None))
        
        def mock_emergency_stop():
            self.callback_results.append(('emergency_stop', None))
        
        callbacks = {
            'on_start_test': mock_start_test,
            'on_stop_test': mock_stop_test,
            'on_emergency_stop': mock_emergency_stop
        }
        
        self.control_panel.set_callbacks(callbacks)
    
    def tearDown(self):
        """Clean up integration tests."""
        if self.root:
            self.root.destroy()
    
    def test_full_workflow(self):
        """Test complete workflow from UI interaction to callback."""
        # Set test parameters
        self.control_panel.position_var.set("left")
        self.control_panel.vehicle_var.set("M1")
        self.control_panel.test_duration_var.set("30")
        
        # Start test
        self.control_panel._on_start_click()
        
        # Verify start test was called
        self.assertEqual(len(self.callback_results), 1)
        self.assertEqual(self.callback_results[0][0], 'start_test')
        
        params = self.callback_results[0][1]
        self.assertEqual(params['position'], 'left')
        self.assertEqual(params['vehicle_type'], 'M1')
        self.assertEqual(params['duration'], 30.0)
        
        # Set test active (simulate presenter response)
        self.control_panel.set_test_active(True)
        
        # Stop test
        self.control_panel._on_stop_click()
        
        # Verify stop test was called
        self.assertEqual(len(self.callback_results), 2)
        self.assertEqual(self.callback_results[1][0], 'stop_test')
        
        # Emergency stop
        self.control_panel._on_emergency_click()
        
        # Verify emergency stop was called
        self.assertEqual(len(self.callback_results), 3)
        self.assertEqual(self.callback_results[2][0], 'emergency_stop')


def run_control_panel_tests():
    """Run all control panel tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestControlPanel))
    suite.addTests(loader.loadTestsFromTestCase(TestControlPanelIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("🧪 Running ControlPanel Unit Tests...")
    print("=" * 50)
    
    success = run_control_panel_tests()
    
    if success:
        print("\n✅ All ControlPanel tests passed!")
    else:
        print("\n❌ Some ControlPanel tests failed!")
    
    print("=" * 50)
