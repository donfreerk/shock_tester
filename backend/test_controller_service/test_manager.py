import logging
import time
import numpy as np
from typing import Dict, Any, Optional, List

from common.suspension_core.config.manager import ConfigManager
from backend.test_controller_service.phase_shift_processor import PhaseShiftProcessor
from backend.test_controller_service.resonance_processor import ResonanceProcessor

logger = logging.getLogger(__name__)

class TestManager:
    """
    Test Manager for the Test Controller Service.

    This class manages test execution, including starting and stopping tests,
    processing measurements, and retrieving test results.
    """

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the Test Manager.

        Args:
            config: Configuration manager (optional)
        """
        self.config = config or ConfigManager()

        # Test configuration
        self.test_config = {
            "method": self.config.get("test.method", "phase_shift"),
            "min_freq": self.config.get("test.min_freq", 6.0),
            "max_freq": self.config.get("test.max_freq", 18.0),
            "phase_threshold": self.config.get("test.phase_threshold", 35.0),
            "vehicle_type": self.config.get("test.vehicle_type", "PKW")
        }

        # Initialize processors
        self.phase_processor = PhaseShiftProcessor()
        self.resonance_processor = ResonanceProcessor()

        # Test state
        self.current_test = None
        self.measurements = {
            "platform_position": [],
            "tire_force": [],
            "timestamps": [],
            "voltage_data": [],
            "initial_voltage": 0.0
        }
        self.test_results = {}

    def start_test(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a new test with the given parameters.

        Args:
            parameters: Test parameters

        Returns:
            Dictionary with test information
        """
        # Create a new test
        self.current_test = {
            "id": f"test_{int(time.time())}",
            "start_time": time.time(),
            "parameters": parameters,
            "state": "running",
            "side": parameters.get("side", "left"),
            "method": parameters.get("method", self.test_config["method"]),
            "progress": 0.0
        }

        # Reset measurements
        self.measurements = {
            "platform_position": [],
            "tire_force": [],
            "timestamps": [],
            "voltage_data": [],
            "initial_voltage": 0.0
        }

        # Reset results
        self.test_results = {}

        logger.info(f"Started new test: {self.current_test['id']}")
        return self.current_test

    def stop_test(self) -> None:
        """Stop the current test."""
        if self.current_test:
            self.current_test["state"] = "stopped"
            self.current_test["end_time"] = time.time()
            logger.info(f"Stopped test: {self.current_test['id']}")

    def process_measurement(self, data: Dict[str, Any]) -> None:
        """
        Process a measurement data point.

        Args:
            data: Measurement data
        """
        if not self.current_test or self.current_test["state"] != "running":
            return

        # Extract data based on type
        data_type = data.get("type")

        if data_type == "position":
            self.measurements["platform_position"].append(data.get("value", 0))
            self.measurements["timestamps"].append(data.get("timestamp", time.time()))

        elif data_type == "force":
            self.measurements["tire_force"].append(data.get("value", 0))

        elif data_type == "voltage":
            # For resonance test
            self.measurements["voltage_data"].append(data.get("value", 0))
            # Store initial voltage if this is the first measurement
            if len(self.measurements["voltage_data"]) == 1:
                self.measurements["initial_voltage"] = data.get("initial_value", 0)

        # Update progress if we have frequency information
        if "frequency" in data:
            # Calculate progress based on frequency sweep
            # Assuming we sweep from max_freq to min_freq
            freq = data.get("frequency", 0)
            max_freq = self.test_config["max_freq"]
            min_freq = self.test_config["min_freq"]

            if max_freq > min_freq:
                progress = 1.0 - (freq - min_freq) / (max_freq - min_freq)
                self.current_test["progress"] = max(0.0, min(1.0, progress))

                # Check if test is complete
                if progress >= 1.0:
                    self._complete_test()

    def get_test_status(self) -> Dict[str, Any]:
        """
        Get the current test status.

        Returns:
            Dictionary with test status information
        """
        if not self.current_test:
            return {"state": "idle", "ready": True}

        return {
            "state": self.current_test["state"],
            "id": self.current_test["id"],
            "progress": self.current_test["progress"],
            "side": self.current_test["side"],
            "method": self.current_test["method"],
            "elapsed_time": time.time() - self.current_test["start_time"]
        }

    def get_test_results(self) -> Dict[str, Any]:
        """
        Get the results of the current or last test.

        Returns:
            Dictionary with test results
        """
        if not self.test_results and self.current_test and self.current_test["state"] == "completed":
            # Calculate results if not already done
            self._calculate_results()

        return self.test_results

    def configure(self, parameters: Dict[str, Any]) -> None:
        """
        Update the test configuration.

        Args:
            parameters: Configuration parameters
        """
        # Update test configuration
        for key, value in parameters.items():
            if key in self.test_config:
                self.test_config[key] = value
                logger.info(f"Updated test configuration: {key}={value}")

    def _complete_test(self) -> None:
        """Complete the current test and calculate results."""
        if not self.current_test:
            return

        self.current_test["state"] = "completed"
        self.current_test["end_time"] = time.time()
        self.current_test["duration"] = self.current_test["end_time"] - self.current_test["start_time"]

        # Calculate results
        self._calculate_results()

        logger.info(f"Completed test: {self.current_test['id']}")

    def _calculate_results(self) -> None:
        """Calculate test results from measurements."""
        if not self.current_test:
            return

        # Calculate results based on test method
        method = self.current_test["method"]

        if method == "phase_shift":
            # Basic validation for phase shift test
            if (len(self.measurements["platform_position"]) == 0 or
                len(self.measurements["tire_force"]) == 0 or
                len(self.measurements["timestamps"]) == 0):
                logger.warning("Insufficient measurement data for phase shift calculation")
                self.test_results = {
                    "test_id": self.current_test["id"],
                    "valid": False,
                    "error": "Insufficient measurement data for phase shift test"
                }
                return

            # Ensure all arrays have the same length
            min_length = min(
                len(self.measurements["platform_position"]),
                len(self.measurements["tire_force"]),
                len(self.measurements["timestamps"])
            )

            # Truncate arrays to the same length
            platform_position = self.measurements["platform_position"][:min_length]
            tire_force = self.measurements["tire_force"][:min_length]
            timestamps = self.measurements["timestamps"][:min_length]

            # Calculate phase shift results
            self._calculate_phase_shift_results(platform_position, tire_force, timestamps)

        elif method == "resonance":
            # Basic validation for resonance test
            if (len(self.measurements["voltage_data"]) == 0 or
                self.measurements["initial_voltage"] == 0.0):
                logger.warning("Insufficient measurement data for resonance calculation")
                self.test_results = {
                    "test_id": self.current_test["id"],
                    "valid": False,
                    "error": "Insufficient measurement data for resonance test"
                }
                return

            # Calculate resonance results
            self._calculate_resonance_results(
                self.measurements["voltage_data"],
                self.measurements["initial_voltage"]
            )

        else:
            logger.warning(f"Unsupported test method: {method}")
            self.test_results = {
                "test_id": self.current_test["id"],
                "valid": False,
                "error": f"Unsupported test method: {method}"
            }

    def _calculate_phase_shift_results(self, platform_position: List[float], 
                                      tire_force: List[float], 
                                      timestamps: List[float]) -> None:
        """
        Calculate phase shift test results using the PhaseShiftProcessor.

        Args:
            platform_position: List of platform position values
            tire_force: List of tire force values
            timestamps: List of timestamps
        """
        # Estimate static weight from tire force data
        static_weight = np.mean(tire_force) if tire_force else 0.0

        # Use the PhaseShiftProcessor to calculate phase shift
        phase_data = self.phase_processor.calculate_phase_shift(
            platform_position=platform_position,
            tire_force=tire_force,
            time_array=timestamps,
            static_weight=static_weight
        )

        # If calculation failed, return error
        if not phase_data["valid"]:
            self.test_results = {
                "test_id": self.current_test["id"],
                "valid": False,
                "method": "phase_shift",
                "side": self.current_test["side"],
                "error": phase_data.get("error", "Phase shift calculation failed")
            }
            logger.warning(f"Phase shift calculation failed: {phase_data.get('error', 'Unknown error')}")
            return

        # Evaluate the phase shift results
        vehicle_type = self.test_config["vehicle_type"]
        evaluation = self.phase_processor.evaluate_phase_shift(phase_data, vehicle_type)

        # Create result object
        self.test_results = {
            "test_id": self.current_test["id"],
            "valid": True,
            "method": "phase_shift",
            "side": self.current_test["side"],
            "min_phase_shift": phase_data["min_phase_shift"],
            "min_phase_freq": phase_data["min_phase_freq"],
            "phase_shifts": phase_data["phase_shifts"],
            "frequencies": phase_data["frequencies"],
            "threshold": evaluation["threshold"],
            "passed": evaluation["passed"],
            "quality_index": evaluation["quality_index"],
            "data_points": len(platform_position),
            "duration": self.current_test["duration"],
            "static_weight": static_weight
        }

        logger.info(f"Calculated phase shift results: min_phase={phase_data['min_phase_shift']}, passed={evaluation['passed']}")

    def _calculate_resonance_results(self, voltage_data: List[float], initial_voltage: float) -> None:
        """
        Calculate resonance test results using the ResonanceProcessor.

        Args:
            voltage_data: List of voltage values
            initial_voltage: Initial voltage value
        """
        # Get weight class from test parameters
        weight_class = self.current_test["parameters"].get("weight_class", 1500)

        # Use the ResonanceProcessor to process the test
        results = self.resonance_processor.process_test(
            voltage_data=voltage_data,
            initial_voltage=initial_voltage,
            weight_class=weight_class
        )

        # Evaluate the resonance results
        evaluation = self.resonance_processor.evaluate_resonance_results(results)

        # Create result object
        self.test_results = {
            "test_id": self.current_test["id"],
            "valid": True,
            "method": "resonance",
            "side": self.current_test["side"],
            "weight": results["weight"],
            "amplitude": results["amplitude"],
            "effectiveness": results["effectiveness"],
            "passed": evaluation["passed"],
            "quality_index": evaluation["quality_index"],
            "threshold": evaluation["threshold"],
            "data_points": len(voltage_data),
            "duration": self.current_test["duration"]
        }

        logger.info(f"Calculated resonance results: weight={results['weight']}, effectiveness={results['effectiveness']}, passed={evaluation['passed']}")