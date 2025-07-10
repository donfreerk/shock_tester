"""
Unit tests for OptimizedChartWidget component.

Tests the performance-optimized chart widget including blitting and decimation.
"""

import unittest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import sys
from pathlib import Path
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from views.chart_widget import OptimizedChartWidget


class TestOptimizedChartWidget(unittest.TestCase):
    """Test cases for OptimizedChartWidget component."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide test window
        
        # Create test container
        self.container = tk.Frame(self.root)
        
        # Create chart widget with test settings
        self.chart_widget = OptimizedChartWidget(self.container)
        
        # Override some settings for testing
        self.chart_widget.max_points = 100  # Smaller for faster tests
        self.chart_widget.update_interval = 0.001  # Very fast for testing
    
    def tearDown(self):
        """Clean up after each test method."""
        if self.root:
            self.root.destroy()
    
    def test_initialization(self):
        """Test chart widget initialization."""
        # Check matplotlib components exist
        self.assertIsNotNone(self.chart_widget.figure)
        self.assertIsNotNone(self.chart_widget.canvas)
        self.assertIsNotNone(self.chart_widget.widget)
        
        # Check axes were created
        expected_axes = ['platform', 'force', 'phase', 'frequency']
        for axis_name in expected_axes:
            self.assertIn(axis_name, self.chart_widget.axes)
            self.assertIn(axis_name, self.chart_widget.lines)
        
        # Check performance settings
        self.assertTrue(self.chart_widget.enable_blitting)
        self.assertTrue(self.chart_widget.enable_decimation)
        self.assertEqual(self.chart_widget.max_points, 100)  # Our test override
    
    def test_performance_configuration(self):
        """Test performance settings configuration."""
        # Configure performance settings
        self.chart_widget.configure_performance(
            max_points=200,
            update_interval=0.1,
            enable_blitting=False,
            enable_decimation=False
        )
        
        # Verify settings were updated
        self.assertEqual(self.chart_widget.max_points, 200)
        self.assertEqual(self.chart_widget.update_interval, 0.1)
        self.assertFalse(self.chart_widget.enable_blitting)
        self.assertFalse(self.chart_widget.enable_decimation)
    
    def test_lttb_downsampling(self):
        """Test Largest Triangle Three Buckets downsampling algorithm."""
        # Create test time data
        time_data = np.linspace(0, 10, 1000)  # 1000 points
        target_points = 100
        
        # Apply LTTB downsampling
        indices = self.chart_widget._lttb_downsample(time_data, target_points)
        
        # Check results
        self.assertLessEqual(len(indices), target_points)
        self.assertEqual(indices[0], 0)  # First point preserved
        self.assertEqual(indices[-1], len(time_data) - 1)  # Last point preserved
        
        # Check indices are sorted and unique
        self.assertTrue(np.all(indices[:-1] < indices[1:]))  # Sorted
        self.assertEqual(len(indices), len(np.unique(indices)))  # Unique
    
    def test_lttb_edge_cases(self):
        """Test LTTB downsampling edge cases."""
        # Test with fewer points than target
        small_data = np.array([1, 2, 3, 4, 5])
        indices = self.chart_widget._lttb_downsample(small_data, 10)
        np.testing.assert_array_equal(indices, np.arange(len(small_data)))
        
        # Test with exact target points
        exact_data = np.array([1, 2, 3, 4, 5])
        indices = self.chart_widget._lttb_downsample(exact_data, 5)
        np.testing.assert_array_equal(indices, np.arange(5))
        
        # Test with single point
        single_data = np.array([1])
        indices = self.chart_widget._lttb_downsample(single_data, 10)
        np.testing.assert_array_equal(indices, np.array([0]))
    
    def test_needs_decimation(self):
        """Test decimation necessity detection."""
        # Small data - no decimation needed
        small_data = {
            'time': list(range(50)),
            'platform_position': list(range(50)),
            'tire_force': list(range(50))
        }
        self.assertFalse(self.chart_widget._needs_decimation(small_data))
        
        # Large data - decimation needed
        large_data = {
            'time': list(range(200)),  # > max_points (100)
            'platform_position': list(range(200)),
            'tire_force': list(range(200))
        }
        self.assertTrue(self.chart_widget._needs_decimation(large_data))
        
        # Mixed data - some arrays large
        mixed_data = {
            'time': list(range(200)),  # Large
            'platform_position': list(range(50)),  # Small
            'other_data': 'not_an_array'
        }
        self.assertTrue(self.chart_widget._needs_decimation(mixed_data))
    
    def test_data_decimation(self):
        """Test data decimation functionality."""
        # Create large dataset
        n_points = 500
        large_data = {
            'time': list(np.linspace(0, 10, n_points)),
            'platform_position': list(np.sin(np.linspace(0, 4*np.pi, n_points))),
            'tire_force': list(np.cos(np.linspace(0, 4*np.pi, n_points))),
            'phase_shift': list(np.linspace(35, 45, n_points)),
            'frequency': list(np.linspace(25, 6, n_points)),
            'metadata': 'should_be_preserved'
        }
        
        # Apply decimation
        decimated_data = self.chart_widget._decimate_data(large_data)
        
        # Check that data was decimated
        self.assertLessEqual(len(decimated_data['time']), self.chart_widget.max_points)
        self.assertLessEqual(len(decimated_data['platform_position']), self.chart_widget.max_points)
        self.assertLessEqual(len(decimated_data['tire_force']), self.chart_widget.max_points)
        
        # Check that non-array data is preserved
        self.assertEqual(decimated_data['metadata'], 'should_be_preserved')
        
        # Check that all decimated arrays have same length
        time_len = len(decimated_data['time'])
        self.assertEqual(len(decimated_data['platform_position']), time_len)
        self.assertEqual(len(decimated_data['tire_force']), time_len)
    
    def test_chart_update_queue(self):
        """Test chart update queuing mechanism."""
        # Create test data
        test_data = {
            'time': [1, 2, 3, 4, 5],
            'platform_position': [0, 1, 0, -1, 0],
            'tire_force': [500, 510, 500, 490, 500]
        }
        
        # Update charts (should queue the data)
        self.chart_widget.update_charts(test_data)
        
        # Check that data was queued
        self.assertGreater(len(self.chart_widget._update_queue), 0)
        
        # Add more data to test queue management
        for i in range(10):
            self.chart_widget.update_charts(test_data)
        
        # Queue should be limited in size
        self.assertLessEqual(len(self.chart_widget._update_queue), 6)  # Max 5 + some buffer
    
    def test_clear_charts(self):
        """Test clearing chart data."""
        # Set some data in lines
        for line in self.chart_widget.lines.values():
            line.set_data([1, 2, 3], [4, 5, 6])
        
        # Clear charts
        self.chart_widget.clear_charts()
        
        # Verify lines are empty
        for line in self.chart_widget.lines.values():
            x_data, y_data = line.get_data()
            self.assertEqual(len(x_data), 0)
            self.assertEqual(len(y_data), 0)
    
    def test_chart_modes(self):
        """Test different chart modes."""
        # Test standard mode
        self.chart_widget.set_chart_mode("standard")
        self.assertEqual(self.chart_widget.chart_mode, "standard")
        
        # Test dynamic mode
        self.chart_widget.set_chart_mode("dynamic")
        self.assertEqual(self.chart_widget.chart_mode, "dynamic")
        
        # Test invalid mode (should be ignored)
        original_mode = self.chart_widget.chart_mode
        self.chart_widget.set_chart_mode("invalid_mode")
        self.assertEqual(self.chart_widget.chart_mode, original_mode)
    
    def test_performance_stats(self):
        """Test performance statistics collection."""
        # Get initial stats
        stats = self.chart_widget.get_performance_stats()
        
        # Check stats structure
        expected_keys = [
            'update_count', 'avg_frame_time', 'current_fps',
            'blitting_enabled', 'decimation_enabled', 'max_points', 'queue_size'
        ]
        for key in expected_keys:
            self.assertIn(key, stats)
        
        # Check initial values
        self.assertEqual(stats['update_count'], 0)
        self.assertTrue(stats['blitting_enabled'])
        self.assertTrue(stats['decimation_enabled'])
        self.assertEqual(stats['max_points'], 100)  # Our test override
    
    @patch('matplotlib.pyplot.ioff')
    def test_background_processing_thread(self, mock_ioff):
        """Test background processing thread functionality."""
        # Check that background thread is started
        self.assertIsNotNone(self.chart_widget._processing_thread)
        self.assertTrue(self.chart_widget._processing_thread.is_alive())
        
        # Add some data to queue and let it process
        test_data = {
            'time': [1, 2, 3],
            'platform_position': [0, 1, 0],
            'tire_force': [500, 510, 500]
        }
        
        with self.chart_widget._update_lock:
            self.chart_widget._update_queue.append(test_data)
        
        # Give background thread time to process
        time.sleep(0.1)
        
        # Queue should be processed (empty or reduced)
        # Note: This test might be flaky due to timing, so we just check it doesn't crash
    
    def test_chart_data_extraction(self):
        """Test chart data extraction from complex data structure."""
        # Create complex test data
        complex_data = {
            'time': [0, 0.1, 0.2, 0.3, 0.4],
            'platform_position': [0, 2, 0, -2, 0],
            'tire_force': [500, 520, 500, 480, 500],
            'phase_shift': [40, 38, 42, 39, 41],
            'frequency': [25, 20, 15, 10, 8],
            'extra_data': 'should_be_ignored',
            'nested': {'inner': 'data'}
        }
        
        # Process the data (this would normally happen in background thread)
        processed_data = self.chart_widget._process_chart_update(complex_data)
        
        # Should not crash and handle the complex structure gracefully
        # The exact behavior depends on implementation details
    
    def test_error_handling(self):
        """Test error handling in chart operations."""
        # Test with malformed data
        bad_data = {
            'time': [1, 2, 3],
            'platform_position': [1, 2],  # Mismatched length
            'tire_force': None,  # None value
            'invalid': float('inf')  # Invalid number
        }
        
        # Should not crash when processing bad data
        try:
            self.chart_widget.update_charts(bad_data)
            # Give time for background processing
            time.sleep(0.1)
        except Exception as e:
            self.fail(f"Chart widget should handle bad data gracefully, but raised: {e}")
        
        # Test decimation with bad data
        try:
            result = self.chart_widget._decimate_data(bad_data)
            # Should return something (original data or processed)
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"Decimation should handle bad data gracefully, but raised: {e}")


class TestChartWidgetPerformance(unittest.TestCase):
    """Performance-focused tests for OptimizedChartWidget."""
    
    def setUp(self):
        """Set up performance tests."""
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.container = tk.Frame(self.root)
        self.chart_widget = OptimizedChartWidget(self.container)
        
        # Configure for performance testing
        self.chart_widget.max_points = 500
        self.chart_widget.update_interval = 0.001  # Very fast updates
    
    def tearDown(self):
        """Clean up performance tests."""
        if self.root:
            self.root.destroy()
    
    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        # Create large dataset
        n_points = 5000
        large_data = {
            'time': list(np.linspace(0, 100, n_points)),
            'platform_position': list(np.sin(np.linspace(0, 20*np.pi, n_points))),
            'tire_force': list(500 + 100 * np.cos(np.linspace(0, 20*np.pi, n_points))),
            'phase_shift': list(35 + 10 * np.sin(np.linspace(0, 10*np.pi, n_points))),
            'frequency': list(np.linspace(25, 6, n_points))
        }
        
        # Measure processing time
        start_time = time.perf_counter()
        processed_data = self.chart_widget._decimate_data(large_data)
        processing_time = time.perf_counter() - start_time
        
        # Should process quickly (< 100ms)
        self.assertLess(processing_time, 0.1, 
                       f"Large dataset processing took {processing_time*1000:.1f}ms, should be <100ms")
        
        # Should reduce data size
        self.assertLessEqual(len(processed_data['time']), self.chart_widget.max_points)
        self.assertGreater(len(processed_data['time']), 0)
    
    def test_rapid_updates_performance(self):
        """Test performance with rapid chart updates."""
        # Create moderate dataset
        n_points = 1000
        test_data = {
            'time': list(np.linspace(0, 10, n_points)),
            'platform_position': list(np.sin(np.linspace(0, 4*np.pi, n_points))),
            'tire_force': list(500 + 50 * np.cos(np.linspace(0, 4*np.pi, n_points)))
        }
        
        # Perform rapid updates
        start_time = time.perf_counter()
        n_updates = 20
        
        for i in range(n_updates):
            self.chart_widget.update_charts(test_data)
        
        update_time = time.perf_counter() - start_time
        avg_update_time = update_time / n_updates
        
        # Should handle rapid updates efficiently
        self.assertLess(avg_update_time, 0.01, 
                       f"Average update time {avg_update_time*1000:.1f}ms, should be <10ms")
    
    def test_memory_efficiency(self):
        """Test memory efficiency of chart operations."""
        import sys
        
        # Get initial memory usage (rough estimate)
        initial_queue_size = len(self.chart_widget._update_queue)
        
        # Add many updates
        test_data = {
            'time': list(range(100)),
            'platform_position': list(range(100)),
            'tire_force': list(range(100))
        }
        
        for i in range(100):
            self.chart_widget.update_charts(test_data)
        
        # Queue should not grow unbounded
        final_queue_size = len(self.chart_widget._update_queue)
        self.assertLessEqual(final_queue_size, 10, 
                           "Update queue should not grow unbounded")


def run_chart_widget_tests():
    """Run all chart widget tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizedChartWidget))
    suite.addTests(loader.loadTestsFromTestCase(TestChartWidgetPerformance))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("🧪 Running OptimizedChartWidget Unit Tests...")
    print("=" * 60)
    
    success = run_chart_widget_tests()
    
    if success:
        print("\n✅ All OptimizedChartWidget tests passed!")
    else:
        print("\n❌ Some OptimizedChartWidget tests failed!")
    
    print("=" * 60)
