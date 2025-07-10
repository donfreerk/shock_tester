import logging
import numpy as np
from typing import Dict, Any, Optional, List

from common.suspension_core.config.manager import ConfigManager

logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Data Processor for the Test Controller Service.
    
    This class processes test data and calculates results based on different
    test methods, such as phase shift and resonance.
    """
    
    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the Data Processor.
        
        Args:
            config: Configuration manager (optional)
        """
        self.config = config or ConfigManager()
        
        # Load configuration parameters
        self.phase_threshold = self.config.get("test.phase_shift_threshold", 35.0)
        self.min_freq = self.config.get("test.min_freq", 6.0)
        self.max_freq = self.config.get("test.max_freq", 18.0)
        
    def process_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process test results and add additional analysis.
        
        Args:
            results: Raw test results
            
        Returns:
            Processed test results with additional analysis
        """
        # If results are not valid, return them as is
        if not results.get("valid", False):
            return results
            
        # Process based on test method
        method = results.get("method", "phase_shift")
        
        if method == "phase_shift":
            return self._process_phase_shift_results(results)
        elif method == "resonance":
            return self._process_resonance_results(results)
        else:
            logger.warning(f"Unsupported test method for processing: {method}")
            return results
            
    def _process_phase_shift_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process phase shift test results.
        
        Args:
            results: Raw phase shift test results
            
        Returns:
            Processed phase shift test results
        """
        # Create a copy of the results to avoid modifying the original
        processed = results.copy()
        
        # Add quality assessment
        min_phase = results.get("min_phase_shift", 0.0)
        
        if min_phase >= self.phase_threshold + 10:
            quality = "excellent"
        elif min_phase >= self.phase_threshold:
            quality = "good"
        elif min_phase >= self.phase_threshold - 5:
            quality = "marginal"
        else:
            quality = "poor"
            
        processed["quality"] = quality
        
        # Add percentage relative to threshold
        if self.phase_threshold > 0:
            processed["threshold_percentage"] = (min_phase / self.phase_threshold) * 100
            
        # Add interpretation text
        if processed["passed"]:
            processed["interpretation"] = f"The suspension is functioning properly with a minimum phase shift of {min_phase:.1f}° (threshold: {self.phase_threshold}°)."
        else:
            processed["interpretation"] = f"The suspension needs attention. Minimum phase shift of {min_phase:.1f}° is below the threshold of {self.phase_threshold}°."
            
        return processed
        
    def _process_resonance_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process resonance test results.
        
        Args:
            results: Raw resonance test results
            
        Returns:
            Processed resonance test results
        """
        # Create a copy of the results to avoid modifying the original
        processed = results.copy()
        
        # Add quality assessment based on effectiveness
        effectiveness = results.get("effectiveness", 0.0)
        
        if effectiveness >= 0.7:
            quality = "excellent"
        elif effectiveness >= 0.5:
            quality = "good"
        elif effectiveness >= 0.3:
            quality = "marginal"
        else:
            quality = "poor"
            
        processed["quality"] = quality
        
        # Add interpretation text
        processed["interpretation"] = f"The suspension has an effectiveness of {effectiveness:.1%}, indicating {quality} performance."
            
        return processed
        
    def analyze_time_series(self, time_array: List[float], position_array: List[float], force_array: List[float]) -> Dict[str, Any]:
        """
        Analyze time series data from a test.
        
        Args:
            time_array: Array of timestamps
            position_array: Array of platform positions
            force_array: Array of tire forces
            
        Returns:
            Dictionary with analysis results
        """
        # Convert to numpy arrays if they aren't already
        time_np = np.array(time_array)
        position_np = np.array(position_array)
        force_np = np.array(force_array)
        
        # Basic statistics
        analysis = {
            "position_mean": float(np.mean(position_np)),
            "position_std": float(np.std(position_np)),
            "position_min": float(np.min(position_np)),
            "position_max": float(np.max(position_np)),
            "force_mean": float(np.mean(force_np)),
            "force_std": float(np.std(force_np)),
            "force_min": float(np.min(force_np)),
            "force_max": float(np.max(force_np)),
            "duration": float(time_np[-1] - time_np[0]) if len(time_np) > 1 else 0.0,
            "sample_count": len(time_np)
        }
        
        # Calculate position amplitude (peak-to-peak)
        analysis["position_amplitude"] = analysis["position_max"] - analysis["position_min"]
        
        # Calculate force amplitude (peak-to-peak)
        analysis["force_amplitude"] = analysis["force_max"] - analysis["force_min"]
        
        # Calculate sampling rate
        if len(time_np) > 1:
            dt = np.diff(time_np)
            analysis["sampling_rate"] = float(1.0 / np.mean(dt))
        else:
            analysis["sampling_rate"] = 0.0
            
        return analysis