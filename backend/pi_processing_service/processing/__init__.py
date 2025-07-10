"""
Processing Package für Pi Processing Service

Enthält alle Module für die Datenverarbeitung:
- phase_shift_calculator: EGEA-konforme Phase-Shift-Berechnung
- data_validator: Validierung eingehender Rohdaten
"""

from .phase_shift_calculator import PhaseShiftCalculator
from .data_validator import DataValidator

__version__ = "1.0.0"

# Public API
__all__ = [
    "PhaseShiftCalculator",
    "DataValidator"
]
