"""
EGEA Suspension Testing Module

This module provides implementations of the EGEA suspension testing standards
for phase shift analysis and related signal processing.
"""

# Export the main classes for easy importing
from .processors.phase_shift_processor import EGEAPhaseShiftProcessor

# Alias for backwards compatibility and cleaner imports
PhaseShiftProcessor = EGEAPhaseShiftProcessor

__all__ = [
    'EGEAPhaseShiftProcessor',
    'PhaseShiftProcessor',
]
