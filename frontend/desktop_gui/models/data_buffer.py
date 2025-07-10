"""
Memory-Optimized Data Buffer for EGEA Suspension Tester.

Responsibility: Efficient data storage and EGEA analysis with memory optimization.
Features: Ring buffers, memory pooling, background processing integration.
"""

import threading
import time
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from dataclasses import dataclass
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from processing.background_processor import BackgroundProcessor

logger = logging.getLogger(__name__)


@dataclass
class EGEAParameters:
    """EGEA test parameters and thresholds."""
    PHASE_SHIFT_MIN: float = 35.0
    MIN_CALC_FREQ: float = 6.0
    MAX_CALC_FREQ: float = 25.0
    MIN_CYCLE_COUNT: int = 5
    MIN_DATA_POINTS: int = 50


class MemoryPool:
    """
    Memory pool for efficient array allocation.
    Reduces garbage collection overhead.
    """
    
    def __init__(self, pool_size: int = 50, array_size: int = 1000):
        self.pool_size = pool_size
        self.array_size = array_size
        self.available_arrays = deque()
        self.lock = threading.Lock()
        
        # Pre-allocate arrays
        self._populate_pool()
        
        logger.debug(f"Memory pool initialized: {pool_size} arrays of size {array_size}")
    
    def _populate_pool(self):
        """Pre-allocate arrays for the pool."""
        for _ in range(self.pool_size):
            array = np.zeros(self.array_size, dtype=np.float64)
            self.available_arrays.append(array)
    
    def get_array(self) -> np.ndarray:
        """Get an array from the pool."""
        with self.lock:
            if self.available_arrays:
                array = self.available_arrays.popleft()
                array.fill(0)  # Reset array
                return array
            else:
                # Pool exhausted, create new array
                logger.debug("Memory pool exhausted, creating new array")
                return np.zeros(self.array_size, dtype=np.float64)
    
    def return_array(self, array: np.ndarray):
        """Return an array to the pool."""
        with self.lock:
            if len(self.available_arrays) < self.pool_size:
                self.available_arrays.append(array)
            # If pool is full, let array be garbage collected
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory pool statistics."""
        with self.lock:
            return {
                'pool_size': self.pool_size,
                'available_arrays': len(self.available_arrays),
                'arrays_in_use': self.pool_size - len(self.available_arrays),
                'array_size': self.array_size
            }


class RingBuffer:
    """
    High-performance ring buffer for time-series data.
    Memory-efficient with pre-allocated arrays.
    """
    
    def __init__(self, capacity: int, dtype=np.float64):
        self.capacity = capacity
        self.dtype = dtype
        
        # Pre-allocated arrays
        self.time_data = np.zeros(capacity, dtype=dtype)
        self.platform_data = np.zeros(capacity, dtype=dtype)
        self.force_data = np.zeros(capacity, dtype=dtype)
        self.frequency_data = np.zeros(capacity, dtype=dtype)
        self.phase_data = np.zeros(capacity, dtype=dtype)
        
        # Ring buffer state
        self.write_index = 0
        self.size = 0
        self.lock = threading.RLock()
        
        # Performance tracking
        self.total_writes = 0
        self.total_reads = 0
        
        logger.debug(f"RingBuffer initialized: capacity={capacity}, dtype={dtype}")
    
    def append(self, time_val: float, platform_val: float, force_val: float,
              frequency_val: float = 0.0, phase_val: float = 0.0):
        """Append data point to ring buffer."""
        with self.lock:
            idx = self.write_index
            
            # Write data
            self.time_data[idx] = time_val
            self.platform_data[idx] = platform_val
            self.force_data[idx] = force_val
            self.frequency_data[idx] = frequency_val
            self.phase_data[idx] = phase_val
            
            # Update indices
            self.write_index = (self.write_index + 1) % self.capacity
            self.size = min(self.size + 1, self.capacity)
            self.total_writes += 1
    
    def get_data(self, max_points: Optional[int] = None) -> Dict[str, np.ndarray]:
        """Get data from ring buffer with memory-efficient copying."""
        with self.lock:
            if self.size == 0:
                return self._empty_result()
            
            # Determine number of points to return
            n_points = self.size
            if max_points and max_points < n_points:
                # Use decimation for memory efficiency
                step = n_points // max_points
                indices = np.arange(0, n_points, step)[:max_points]
            else:
                indices = np.arange(n_points)
            
            # Handle ring buffer wraparound
            if self.size < self.capacity:
                # Buffer not full yet
                actual_indices = indices
            else:
                # Buffer is full, need to handle wraparound
                start_idx = self.write_index
                actual_indices = (start_idx + indices) % self.capacity
            
            # Extract data (memory views, not copies where possible)
            result = {
                'time': self.time_data[actual_indices].copy(),
                'platform_position': self.platform_data[actual_indices].copy(),
                'tire_force': self.force_data[actual_indices].copy(),
                'frequency': self.frequency_data[actual_indices].copy(),
                'phase_shift': self.phase_data[actual_indices].copy()
            }
            
            self.total_reads += 1
            return result
    
    def get_recent_data(self, n_points: int) -> Dict[str, np.ndarray]:
        """Get most recent n points efficiently."""
        with self.lock:
            if self.size == 0:
                return self._empty_result()
            
            # Get actual number of points available
            actual_n = min(n_points, self.size)
            
            if self.size < self.capacity:
                # Buffer not full, simple slice
                start_idx = max(0, self.size - actual_n)
                result = {
                    'time': self.time_data[start_idx:self.size].copy(),
                    'platform_position': self.platform_data[start_idx:self.size].copy(),
                    'tire_force': self.force_data[start_idx:self.size].copy(),
                    'frequency': self.frequency_data[start_idx:self.size].copy(),
                    'phase_shift': self.phase_data[start_idx:self.size].copy()
                }
            else:
                # Buffer full, handle wraparound
                if actual_n >= self.capacity:
                    # Want all data
                    start_idx = self.write_index
                    indices = (start_idx + np.arange(self.capacity)) % self.capacity
                else:
                    # Want recent subset
                    end_idx = (self.write_index - 1) % self.capacity
                    start_idx = (end_idx - actual_n + 1) % self.capacity
                    
                    if start_idx <= end_idx:
                        indices = np.arange(start_idx, end_idx + 1)
                    else:
                        # Wraparound case
                        indices = np.concatenate([
                            np.arange(start_idx, self.capacity),
                            np.arange(0, end_idx + 1)
                        ])
                
                result = {
                    'time': self.time_data[indices].copy(),
                    'platform_position': self.platform_data[indices].copy(),
                    'tire_force': self.force_data[indices].copy(),
                    'frequency': self.frequency_data[indices].copy(),
                    'phase_shift': self.phase_data[indices].copy()
                }
            
            return result
    
    def _empty_result(self) -> Dict[str, np.ndarray]:
        """Return empty result structure."""
        return {
            'time': np.array([]),
            'platform_position': np.array([]),
            'tire_force': np.array([]),
            'frequency': np.array([]),
            'phase_shift': np.array([])
        }
    
    def clear(self):
        """Clear the ring buffer."""
        with self.lock:
            self.write_index = 0
            self.size = 0
            # Don't need to zero arrays, just reset indices
    
    def get_stats(self) -> Dict[str, Any]:
        """Get ring buffer statistics."""
        with self.lock:
            return {
                'capacity': self.capacity,
                'size': self.size,
                'usage_percent': (self.size / self.capacity) * 100,
                'total_writes': self.total_writes,
                'total_reads': self.total_reads,
                'memory_usage_mb': (self.capacity * 5 * 8) / (1024 * 1024)  # 5 arrays * 8 bytes per float64
            }


class OptimizedDataBuffer:
    """
    Memory-optimized data buffer with background processing.
    
    Features:
    - Ring buffer for efficient memory usage
    - Memory pool for array allocation
    - Background EGEA processing
    - Performance monitoring
    """
    
    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        
        # Memory-optimized storage
        self.ring_buffer = RingBuffer(max_size)
        self.memory_pool = MemoryPool(pool_size=20, array_size=1000)
        
        # Background processing
        self.background_processor = BackgroundProcessor(num_workers=2)
        self.processing_enabled = True
        
        # EGEA parameters and state
        self.egea_params = EGEAParameters()
        self.current_egea_status = {
            "min_phase_shift": None,
            "min_phase_freq": None,
            "quality_index": 0.0,
            "passing": False,
            "evaluation": "insufficient_data",
            "cycle_count": 0
        }
        
        # Test state
        self.test_active = False
        self.test_start_time = None
        self.position = None
        self.vehicle_type = None
        self.static_weight = None
        
        # Performance monitoring
        self.performance_stats = {
            'data_points_added': 0,
            'egea_calculations': 0,
            'background_tasks': 0,
            'memory_usage_mb': 0.0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Start background processing
        self.background_processor.start()
        
        logger.info(f"OptimizedDataBuffer initialized: max_size={max_size}")
    
    def start_test(self, position: str, vehicle_type: str = "M1"):
        """Start a new EGEA test."""
        with self.lock:
            self.clear()
            self.test_active = True
            self.test_start_time = time.time()
            self.position = position
            self.vehicle_type = vehicle_type
            
            # Reset EGEA status
            self.current_egea_status = {
                "min_phase_shift": None,
                "min_phase_freq": None,
                "quality_index": 0.0,
                "passing": False,
                "evaluation": "starting_test",
                "cycle_count": 0
            }
        
        logger.info(f"EGEA test started: position={position}, vehicle={vehicle_type}")
    
    def stop_test(self):
        """Stop the current test."""
        with self.lock:
            self.test_active = False
            
            # Perform final EGEA analysis
            if self.ring_buffer.size >= self.egea_params.MIN_DATA_POINTS:
                self._trigger_final_egea_analysis()
        
        logger.info("EGEA test stopped")
    
    def add_data(self, data: Dict[str, Any]) -> bool:
        """Add data point with memory optimization."""
        try:
            # Extract values with defaults
            timestamp = data.get('timestamp', time.time())
            platform_pos = float(data.get('platform_position', 0))
            tire_force = float(data.get('tire_force', 0))
            frequency = float(data.get('frequency', 0))
            phase_shift = float(data.get('phase_shift', 0))
            
            # Set static weight if provided
            if 'static_weight' in data and data['static_weight'] is not None:
                self.static_weight = float(data['static_weight'])
            
            # Add to ring buffer
            self.ring_buffer.append(timestamp, platform_pos, tire_force, frequency, phase_shift)
            
            # Update performance stats
            self.performance_stats['data_points_added'] += 1
            
            # Trigger background EGEA analysis periodically
            if (self.test_active and self.processing_enabled and 
                self.performance_stats['data_points_added'] % 50 == 0):  # Every 50 points
                self._trigger_background_egea_analysis()
            
            return True
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error adding data point: {e}")
            return False
    
    def _trigger_background_egea_analysis(self):
        """Trigger EGEA analysis in background."""
        # Get recent data for analysis
        recent_data = self.ring_buffer.get_recent_data(500)
        
        if len(recent_data['time']) < self.egea_params.MIN_DATA_POINTS:
            return
        
        # Submit to background processor
        task_id = self.background_processor.submit_phase_shift_calculation(
            platform_data=recent_data['platform_position'],
            force_data=recent_data['tire_force'],
            time_data=recent_data['time'],
            static_weight=self.static_weight or 512.0,
            callback=self._on_egea_result
        )
        
        self.performance_stats['background_tasks'] += 1
        logger.debug(f"Background EGEA analysis triggered: {task_id}")
    
    def _trigger_final_egea_analysis(self):
        """Trigger final EGEA analysis for complete dataset."""
        all_data = self.ring_buffer.get_data()
        
        if len(all_data['time']) < self.egea_params.MIN_DATA_POINTS:
            return
        
        # Submit to background processor with high priority
        task_id = self.background_processor.submit_phase_shift_calculation(
            platform_data=all_data['platform_position'],
            force_data=all_data['tire_force'],
            time_data=all_data['time'],
            static_weight=self.static_weight or 512.0,
            callback=self._on_final_egea_result
        )
        
        logger.info(f"Final EGEA analysis triggered: {task_id}")
    
    def _on_egea_result(self, result):
        """Handle EGEA analysis result from background processing."""
        try:
            if result.success and result.result.get('success'):
                with self.lock:
                    # Update EGEA status
                    egea_data = result.result
                    self.current_egea_status.update({
                        "min_phase_shift": egea_data.get('min_phase_shift'),
                        "quality_index": egea_data.get('quality_index', 0.0),
                        "passing": egea_data.get('passing', False),
                        "evaluation": egea_data.get('evaluation', 'unknown'),
                        "cycle_count": egea_data.get('cycle_count', 0)
                    })
                    
                    self.performance_stats['egea_calculations'] += 1
                    
                logger.debug(f"EGEA analysis complete: φmin={egea_data.get('min_phase_shift'):.1f}°")
            else:
                logger.warning(f"EGEA analysis failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Error processing EGEA result: {e}")
    
    def _on_final_egea_result(self, result):
        """Handle final EGEA analysis result."""
        self._on_egea_result(result)
        
        if result.success:
            logger.info(f"Final EGEA result: {self.current_egea_status}")
    
    def get_data(self, max_points: Optional[int] = None) -> Dict[str, Any]:
        """Get data with EGEA status."""
        data = self.ring_buffer.get_data(max_points)
        
        # Add EGEA status
        data['egea_status'] = self.current_egea_status.copy()
        data['test_active'] = self.test_active
        data['position'] = self.position
        data['vehicle_type'] = self.vehicle_type
        
        return data
    
    def get_recent_data(self, n_points: int) -> Dict[str, Any]:
        """Get recent data efficiently."""
        data = self.ring_buffer.get_recent_data(n_points)
        
        # Add metadata
        data['egea_status'] = self.current_egea_status.copy()
        data['test_active'] = self.test_active
        
        return data
    
    def get_egea_status(self) -> Dict[str, Any]:
        """Get current EGEA status."""
        with self.lock:
            return self.current_egea_status.copy()
    
    def get_data_count(self) -> int:
        """Get current data count."""
        return self.ring_buffer.size
    
    def is_test_active(self) -> bool:
        """Check if test is active."""
        return self.test_active
    
    def clear(self):
        """Clear all data."""
        with self.lock:
            self.ring_buffer.clear()
            self.test_active = False
            self.test_start_time = None
            self.position = None
            self.static_weight = None
            
            # Reset EGEA status
            self.current_egea_status = {
                "min_phase_shift": None,
                "min_phase_freq": None,
                "quality_index": 0.0,
                "passing": False,
                "evaluation": "insufficient_data",
                "cycle_count": 0
            }
        
        logger.info("Data buffer cleared")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        # Get component stats
        ring_stats = self.ring_buffer.get_stats()
        memory_stats = self.memory_pool.get_stats()
        bg_stats = self.background_processor.get_status()
        
        # Calculate memory usage
        total_memory_mb = (
            ring_stats['memory_usage_mb'] +
            (memory_stats['pool_size'] * memory_stats['array_size'] * 8) / (1024 * 1024)
        )
        
        return {
            'data_buffer': {
                'data_points': ring_stats['size'],
                'capacity': ring_stats['capacity'],
                'usage_percent': ring_stats['usage_percent'],
                'total_operations': ring_stats['total_writes'] + ring_stats['total_reads']
            },
            'memory_pool': memory_stats,
            'background_processing': bg_stats,
            'performance': {
                **self.performance_stats,
                'memory_usage_mb': total_memory_mb
            },
            'egea': {
                'current_status': self.current_egea_status,
                'test_active': self.test_active,
                'calculations_performed': self.performance_stats['egea_calculations']
            }
        }
    
    def configure_performance(self, processing_enabled: bool = None, 
                            egea_analysis_interval: int = None):
        """Configure performance settings."""
        if processing_enabled is not None:
            self.processing_enabled = processing_enabled
            
        # Could add more configuration options here
        
        logger.info(f"Performance configured: processing={self.processing_enabled}")
    
    def shutdown(self):
        """Shutdown the data buffer and background processing."""
        logger.info("Shutting down OptimizedDataBuffer...")
        
        # Stop background processor
        self.background_processor.stop()
        
        # Clear data
        self.clear()
        
        logger.info("OptimizedDataBuffer shutdown complete")


# Legacy alias for compatibility
DataBuffer = OptimizedDataBuffer