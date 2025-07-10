from typing import Dict, List, Any, Optional
import time
import logging
from .data_buffer import DataBuffer
from views.data_visualization_options import DataField, DataFieldType

logger = logging.getLogger(__name__)


class DataFieldManager:
	"""
	Adapter class that extends DataBuffer functionality to support
	dynamic field discovery and management for visualization
	"""

	def __init__(self, data_buffer: DataBuffer):
		self.data_buffer = data_buffer
		self.detected_fields: Dict[str, DataField] = {
			# Default EGEA fields
			"platform_position": DataField("platform_position", DataFieldType.POSITION, "mm"),
			"tire_force": DataField("tire_force", DataFieldType.FORCE, "N"),
			"phase_shift": DataField("phase_shift", DataFieldType.PHASE, "°"),
			"frequency": DataField("frequency", DataFieldType.FREQUENCY, "Hz")
		}
		self.last_data_count = 0
		self.last_update_time = time.time()

	def get_available_fields(self) -> Dict[str, DataField]:
		"""Returns available data fields with updated statistics"""
		# Get recent data to check for new fields and update values
		recent_data = self.data_buffer.get_recent_data(100)
		current_count = self.data_buffer.get_data_count()

		# Update existing fields with latest values
		for field_name, field in self.detected_fields.items():
			if field_name in recent_data and len(recent_data[field_name]) > 0:
				field.last_value = recent_data[field_name][-1]
				field.sample_count = current_count

		# Detect new fields
		for key in recent_data.keys():
			if key not in self.detected_fields and key not in ['time', 'egea_status', 'test_active']:
				# Determine field type and unit
				field_type = DataFieldType.UNKNOWN
				unit = ""

				if "position" in key:
					field_type = DataFieldType.POSITION
					unit = "mm"
				elif "force" in key or "weight" in key:
					field_type = DataFieldType.FORCE
					unit = "N"
				elif "phase" in key:
					field_type = DataFieldType.PHASE
					unit = "°"
				elif "freq" in key:
					field_type = DataFieldType.FREQUENCY
					unit = "Hz"
				elif "accel" in key:
					field_type = DataFieldType.ACCELERATION
					unit = "m/s²"
				elif "vel" in key or "speed" in key:
					field_type = DataFieldType.VELOCITY
					unit = "m/s"

				# Create new field
				self.detected_fields[key] = DataField(
					name=key,
					field_type=field_type,
					unit=unit,
					last_value=recent_data[key][-1] if len(recent_data[key]) > 0 else 0.0,
					sample_count=current_count
				)

				logger.info(f"New data field detected: {key} ({unit})")

		self.last_data_count = current_count
		self.last_update_time = time.time()

		return self.detected_fields

	def clear_data_buffer(self) -> bool:
		"""Clears the data buffer"""
		try:
			self.data_buffer.clear()
			# Reset sample counts
			for field in self.detected_fields.values():
				field.sample_count = 0
			return True
		except Exception as e:
			logger.error(f"Error clearing data buffer: {e}")
			return False

	def get_field_data(self, field_name: str, samples: int = 100) -> List[float]:
		"""Returns the last N samples of a field"""
		try:
			recent_data = self.data_buffer.get_recent_data(samples)
			if field_name in recent_data:
				return recent_data[field_name]
			return []
		except Exception as e:
			logger.error(f"Error getting field data: {e}")
			return []

	def is_receiving_data(self) -> bool:
		"""Checks if data is being received"""
		current_count = self.data_buffer.get_data_count()
		return current_count > self.last_data_count