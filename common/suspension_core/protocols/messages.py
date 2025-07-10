"""
Standardized Message Formats for Fahrwerkstester Communication

This module defines standardized message formats for communication between
different components of the Fahrwerkstester system. These formats ensure
consistent data exchange between the GUI, simulator, and hardware bridge.
"""

import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MessageType(Enum):
    """Enumeration of message types used in the system."""
    COMMAND = "command"
    STATUS = "status"
    MEASUREMENT = "measurement"
    RAW_DATA = "raw_data"
    MOTOR_STATUS = "motor_status"
    GUI_COMMAND = "gui_command"
    ERROR = "error"
    CONFIG = "config"


class TestState(Enum):
    """Enumeration of test states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CALIBRATING = "calibrating"


class Position(Enum):
    """Enumeration of suspension positions."""
    FRONT_LEFT = "front_left"
    FRONT_RIGHT = "front_right"
    REAR_LEFT = "rear_left"
    REAR_RIGHT = "rear_right"
    ALL = "all"


class TestMethod(Enum):
    """Enumeration of test methods."""
    PHASE_SHIFT = "phase_shift"
    FREQUENCY_SWEEP = "frequency_sweep"
    AMPLITUDE_SWEEP = "amplitude_sweep"
    STATIC = "static"
    CUSTOM = "custom"


def create_message(message_type: Union[MessageType, str], **kwargs) -> Dict[str, Any]:
    """
    Create a standardized message with common fields.
    
    Args:
        message_type: Type of the message
        **kwargs: Additional fields to include in the message
        
    Returns:
        A dictionary containing the message
    """
    if isinstance(message_type, MessageType):
        message_type = message_type.value
        
    message = {
        "type": message_type,
        "timestamp": time.time(),
        "version": "1.0"
    }
    
    # Add additional fields
    message.update(kwargs)
    
    return message


def create_command_message(
    command: str,
    position: Union[Position, str] = Position.ALL,
    method: Union[TestMethod, str] = TestMethod.PHASE_SHIFT,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a command message.
    
    Args:
        command: Command to execute (e.g., "start", "stop", "pause")
        position: Position to apply the command to
        method: Test method to use
        parameters: Additional parameters for the command
        
    Returns:
        A dictionary containing the command message
    """
    if isinstance(position, Position):
        position = position.value
        
    if isinstance(method, TestMethod):
        method = method.value
        
    if parameters is None:
        parameters = {}
        
    return create_message(
        MessageType.COMMAND,
        command=command,
        position=position,
        method=method,
        parameters=parameters
    )


def create_status_message(
    state: Union[TestState, str],
    test_status: Optional[Union[TestState, str]] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a status message.
    
    Args:
        state: Current state of the system
        test_status: Status of the current test
        details: Additional details about the status
        
    Returns:
        A dictionary containing the status message
    """
    if isinstance(state, TestState):
        state = state.value
        
    if isinstance(test_status, TestState):
        test_status = test_status.value
        
    if details is None:
        details = {}
        
    return create_message(
        MessageType.STATUS,
        state=state,
        test_status=test_status,
        details=details
    )


def create_measurement_message(
    position: Union[Position, str],
    platform_position: float,
    tire_force: float,
    frequency: float,
    phase_shift: float,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a measurement message.
    
    Args:
        position: Position where the measurement was taken
        platform_position: Position of the platform (mm)
        tire_force: Force on the tire (N)
        frequency: Current frequency (Hz)
        phase_shift: Phase shift between platform and tire (degrees)
        **kwargs: Additional measurement data
        
    Returns:
        A dictionary containing the measurement message
    """
    if isinstance(position, Position):
        position = position.value
        
    return create_message(
        MessageType.MEASUREMENT,
        position=position,
        platform_position=platform_position,
        tire_force=tire_force,
        frequency=frequency,
        phase_shift=phase_shift,
        **kwargs
    )


def create_raw_data_message(
    position: Union[Position, str],
    timestamp: float,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a raw data message.
    
    Args:
        position: Position where the data was collected
        timestamp: Timestamp when the data was collected
        data: Raw data values
        
    Returns:
        A dictionary containing the raw data message
    """
    if isinstance(position, Position):
        position = position.value
        
    return create_message(
        MessageType.RAW_DATA,
        position=position,
        data_timestamp=timestamp,
        data=data
    )


def create_motor_status_message(
    position: Union[Position, str],
    status: str,
    current_position: float,
    target_position: float,
    speed: float,
    error_code: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a motor status message.
    
    Args:
        position: Position of the motor
        status: Status of the motor (e.g., "running", "stopped", "error")
        current_position: Current position of the motor
        target_position: Target position of the motor
        speed: Current speed of the motor
        error_code: Error code if the motor is in error state
        **kwargs: Additional status information
        
    Returns:
        A dictionary containing the motor status message
    """
    if isinstance(position, Position):
        position = position.value
        
    return create_message(
        MessageType.MOTOR_STATUS,
        position=position,
        status=status,
        current_position=current_position,
        target_position=target_position,
        speed=speed,
        error_code=error_code,
        **kwargs
    )


def create_gui_command_message(
    command: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a GUI command message.
    
    Args:
        command: Command to execute (e.g., "refresh", "show_plot")
        parameters: Additional parameters for the command
        
    Returns:
        A dictionary containing the GUI command message
    """
    if parameters is None:
        parameters = {}
        
    return create_message(
        MessageType.GUI_COMMAND,
        command=command,
        parameters=parameters
    )


def create_error_message(
    error_code: int,
    error_message: str,
    source: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create an error message.
    
    Args:
        error_code: Error code
        error_message: Human-readable error message
        source: Source of the error (e.g., "hardware", "simulator")
        details: Additional details about the error
        
    Returns:
        A dictionary containing the error message
    """
    if details is None:
        details = {}
        
    return create_message(
        MessageType.ERROR,
        error_code=error_code,
        error_message=error_message,
        source=source,
        details=details
    )


def create_config_message(
    config: Dict[str, Any],
    source: str
) -> Dict[str, Any]:
    """
    Create a configuration message.
    
    Args:
        config: Configuration data
        source: Source of the configuration (e.g., "gui", "hardware")
        
    Returns:
        A dictionary containing the configuration message
    """
    return create_message(
        MessageType.CONFIG,
        config=config,
        source=source
    )


def parse_message(message: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse a message from JSON string or dictionary.
    
    Args:
        message: Message to parse
        
    Returns:
        A dictionary containing the parsed message
        
    Raises:
        ValueError: If the message is invalid
    """
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON message: {e}")
    
    if not isinstance(message, dict):
        raise ValueError(f"Message must be a dictionary, got {type(message)}")
    
    if "type" not in message:
        raise ValueError("Message must have a 'type' field")
    
    return message


def message_to_json(message: Dict[str, Any]) -> str:
    """
    Convert a message to JSON string.
    
    Args:
        message: Message to convert
        
    Returns:
        JSON string representation of the message
    """
    return json.dumps(message)