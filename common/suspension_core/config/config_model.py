"""
Zentrale Konfigurationsklasse für den Fahrwerkstester.

Verwendet Pydantic für Validierung und manuelle Umgebungsvariablen-Integration.
"""
import os
from typing import Optional, Dict, Any, Callable
from pydantic import BaseModel, Field, validator, model_validator


def get_env_value(env_name: str, default: Any = None) -> Any:
	"""Holt einen Wert aus den Umgebungsvariablen"""
	return os.environ.get(env_name, default)


class MQTTSettings(BaseModel):
	broker: str = "localhost"
	port: int = 1883
	username: Optional[str] = None
	password: Optional[str] = None

	@model_validator(mode='before')
	@classmethod
	def load_from_env(cls, values: Dict[str, Any]) -> Dict[str, Any]:
		prefix = "SUSPENSION_MQTT_"
		values = values or {}

		if "broker" not in values:
			values["broker"] = get_env_value(prefix + "BROKER", "localhost")
		if "port" not in values:
			port_value = get_env_value(prefix + "PORT", "1883")
			values["port"] = int(port_value) if port_value.isdigit() else 1883
		if "username" not in values:
			values["username"] = get_env_value(prefix + "USERNAME", None)
		if "password" not in values:
			values["password"] = get_env_value(prefix + "PASSWORD", None)

		return values


class CANSettings(BaseModel):
	interface: str = "can0"
	baudrate: int = 1000000
	protocol: str = "eusama"

	@validator('protocol')
	def validate_protocol(cls, v):
		if v not in ['eusama', 'asa']:
			raise ValueError(f"Invalid protocol: {v}")
		return v

	@model_validator(mode='before')
	@classmethod
	def load_from_env(cls, values: Dict[str, Any]) -> Dict[str, Any]:
		prefix = "SUSPENSION_CAN_"
		values = values or {}

		if "interface" not in values:
			values["interface"] = get_env_value(prefix + "INTERFACE", "can0")
		if "baudrate" not in values:
			baudrate_value = get_env_value(prefix + "BAUDRATE", "1000000")
			values["baudrate"] = int(baudrate_value) if baudrate_value.isdigit() else 1000000
		if "protocol" not in values:
			values["protocol"] = get_env_value(prefix + "PROTOCOL", "eusama")

		return values


class TestSettings(BaseModel):
	method: str = "phase_shift"
	min_freq: float = 6.0
	max_freq: float = 18.0
	phase_shift_threshold: float = 35.0

	@model_validator(mode='before')
	@classmethod
	def load_from_env(cls, values: Dict[str, Any]) -> Dict[str, Any]:
		prefix = "SUSPENSION_TEST_"
		values = values or {}

		if "method" not in values:
			values["method"] = get_env_value(prefix + "METHOD", "phase_shift")
		if "min_freq" not in values:
			min_freq_value = get_env_value(prefix + "MIN_FREQ", "6.0")
			try:
				values["min_freq"] = float(min_freq_value)
			except ValueError:
				values["min_freq"] = 6.0
		if "max_freq" not in values:
			max_freq_value = get_env_value(prefix + "MAX_FREQ", "18.0")
			try:
				values["max_freq"] = float(max_freq_value)
			except ValueError:
				values["max_freq"] = 18.0
		if "phase_shift_threshold" not in values:
			threshold_value = get_env_value(prefix + "PHASE_THRESHOLD", "35.0")
			try:
				values["phase_shift_threshold"] = float(threshold_value)
			except ValueError:
				values["phase_shift_threshold"] = 35.0

		return values


class Settings(BaseModel):
	mqtt: MQTTSettings = Field(default_factory=MQTTSettings)
	can: CANSettings = Field(default_factory=CANSettings)
	test: TestSettings = Field(default_factory=TestSettings)
	log_level: str = "INFO"

	@model_validator(mode='before')
	@classmethod
	def load_from_env(cls, values: Dict[str, Any]) -> Dict[str, Any]:
		values = values or {}

		# Load .env file if it exists
		env_file = ".env"
		if os.path.isfile(env_file):
			with open(env_file, "r", encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if line and not line.startswith("#"):
						key, value = line.split("=", 1)
						os.environ[key.strip()] = value.strip()

		if "log_level" not in values:
			values["log_level"] = get_env_value("SUSPENSION_LOG_LEVEL", "INFO")

		return values


# Singleton-Instanz der Konfiguration
settings = Settings()
"""
Zentrale Konfigurationsinstanz.
Importiere diese Variable, um auf die Konfiguration zuzugreifen:
from suspension_core.config.config_model import settings
"""