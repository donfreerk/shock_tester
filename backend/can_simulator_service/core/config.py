# backend/can_simulator_service/core/config.py
"""
Konfigurationsklassen für EGEA-Simulator
Trennt Konfiguration von Domain-Logik
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TestConfiguration:
	"""
	Konfiguration für EGEA-Testsimulation

	Definiert alle einstellbaren Parameter für die Simulation
	nach EGEA-Standard (European Group of EUSAMA Associates)
	"""

	# Frequenz-Parameter
	freq_start: float = 25.0  # Startfrequenz in Hz
	freq_end: float = 2.0  # Endfrequenz in Hz

	# Bewegungs-Parameter
	platform_amplitude: float = 6.0  # Plattformamplitude in mm

	# System-Parameter
	sample_rate: float = 100.0  # Samples pro Sekunde

	# Test-Parameter
	default_duration: float = 30.0  # Standard-Testdauer in Sekunden

	def __post_init__(self):
		"""Validiert Konfigurationsparameter"""
		if self.freq_start <= self.freq_end:
			raise ValueError(f"freq_start ({self.freq_start}) muss größer als freq_end ({self.freq_end}) sein")

		if self.platform_amplitude <= 0:
			raise ValueError(f"platform_amplitude muss positiv sein: {self.platform_amplitude}")

		if self.sample_rate <= 0:
			raise ValueError(f"sample_rate muss positiv sein: {self.sample_rate}")

		if self.default_duration <= 0:
			raise ValueError(f"default_duration muss positiv sein: {self.default_duration}")

	@classmethod
	def create_eusama_standard(cls) -> 'TestConfiguration':
		"""
		Erstellt EUSAMA-Standard-Konfiguration

		Returns:
			TestConfiguration mit EUSAMA-Standardwerten
		"""
		return cls(
			freq_start=25.0,  # EUSAMA Standard
			freq_end=2.0,  # EUSAMA Standard
			platform_amplitude=6.0,  # EUSAMA Standard
			sample_rate=100.0,
			default_duration=30.0
		)

	@classmethod
	def create_asa_standard(cls) -> 'TestConfiguration':
		"""
		Erstellt ASA-Standard-Konfiguration

		Returns:
			TestConfiguration mit ASA-Standardwerten
		"""
		return cls(
			freq_start=30.0,  # ASA Standard
			freq_end=1.5,  # ASA Standard
			platform_amplitude=8.0,  # ASA Standard
			sample_rate=120.0,
			default_duration=25.0
		)

	@classmethod
	def create_custom(cls,
	                  freq_range: tuple[float, float],
	                  amplitude: float,
	                  sample_rate: Optional[float] = None) -> 'TestConfiguration':
		"""
		Erstellt benutzerdefinierte Konfiguration

		Args:
			freq_range: (start_hz, end_hz)
			amplitude: Plattformamplitude in mm
			sample_rate: Optionale Sample-Rate

		Returns:
			TestConfiguration mit benutzerdefinierten Werten
		"""
		return cls(
			freq_start=freq_range[0],
			freq_end=freq_range[1],
			platform_amplitude=amplitude,
			sample_rate=sample_rate or 100.0
		)


@dataclass
class SimulatorConfiguration:
	"""
	Erweiterte Simulator-Konfiguration

	Enthält alle Einstellungen für das Simulator-Verhalten
	"""

	# Test-Konfiguration
	test_config: TestConfiguration

	# Output-Konfiguration
	generate_can_frames: bool = True
	generate_high_level: bool = True
	publish_to_mqtt: bool = True

	# Logging-Konfiguration
	log_level: str = "INFO"
	log_to_file: bool = True
	log_file_path: str = "egea_simulator.log"

	# Performance-Konfiguration
	max_message_queue_size: int = 1000
	heartbeat_interval: float = 5.0  # Sekunden

	def __post_init__(self):
		"""Validiert Simulator-Konfiguration"""
		valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
		if self.log_level not in valid_log_levels:
			raise ValueError(f"log_level muss einer von {valid_log_levels} sein")

		if self.heartbeat_interval <= 0:
			raise ValueError(f"heartbeat_interval muss positiv sein: {self.heartbeat_interval}")