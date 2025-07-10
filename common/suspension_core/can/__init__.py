"""
CAN Package for Fahrwerkstester Common Library

This package provides CAN interface implementations and utilities for the Fahrwerkstester system.
"""

from common.suspension_core.can.can_interface import CanInterface
from common.suspension_core.can.interface_factory import create_can_interface

__all__ = ["CanInterface", "create_can_interface"]