# Suspension Tester

## Overview

This project implements a modern suspension tester for analyzing the damping properties of vehicle suspensions. The software supports two different measurement methods: the classic resonance method and the modern phase-shift method according to EGEA specifications.

## Features

- **Two Testing Methods**:
  - **Phase-Shift Method**: EGEA-compliant measurement of the phase shift between platform movement and tire contact force
  - **Resonance Method**: Classic method evaluating the suspension's decay behavior

- **Supported Protocols**:
  - **EUSAMA Protocol**: Main protocol for the suspension tester with 1 Mbit/s bitrate
  - **ASA-Livestream**: Alternative for roller and plate testers (125/250 kBit/s)

- **Comprehensive Analysis**:
  - Minimum phase angle (φmin)
  - Tire rigidity (Rig)
  - Damping ratio
  - Axle weights
  - Imbalance calculation (left/right comparison)

- **MQTT Integration**:
  - Real-time communication via MQTT for remote access and integration into existing systems
  - Publish/subscribe model for test results, status, and commands

- **CAN-Bus Integration**:
  - Robust communication with CAN bus systems
  - Automatic baud rate detection
  - Callback-based message processing

- **Central Configuration Management**:
  - Flexible configuration via YAML/JSON files
  - Support for environment variables
  - Configuration value validation

## Technical Details

### Supported Vehicle Types

- Passenger cars (M1)
- Light commercial vehicles (N1)

### Measurement Range

- Frequency range: 5-25 Hz
- Maximum axle load: 2200 kg
- Platform amplitude: 6 mm ±0.3 mm

### Evaluation Criteria

- Absolute: Phase-shift ≥ 35° considered "good" (corresponds to damping ratio ≥ 0.1)
- Relative: max. 30% difference between left/right for phase shift and force amplitude
- Tire rigidity: Optimal range 160-400 N/mm, max. 35% difference left/right

### Communication Protocols

#### EUSAMA Protocol (Main Protocol)
- Extended IDs with ASCII code 'EUS' as base (0x08AAAA60)
- 1 Mbit/s bitrate
- DMS-based sensor data
- Motor control with duration specification
- Lamp and display control

#### ASA-Livestream Protocol (Alternative Protocol)
- Extended IDs with ASCII code 'ALS' as base (0x08298A60)
- 250 kBit/s (passenger cars) or 125 kBit/s (trucks) bitrate
- Status displays and ALIVE messages

## Project Structure

```
suspension_tester/
├── config/                 # Configuration management
│   ├── __init__.py
│   ├── config_manager.py   # Central configuration management
│   └── settings.py         # Configuration settings
│
├── protocols/              # Protocol implementations
│   ├── __init__.py
│   ├── base_protocol.py    # Abstract base class for protocols
│   ├── eusama_protocol.py  # EUSAMA protocol implementation
│   ├── asa_protocol.py     # ASA livestream protocol implementation
│   └── protocol_factory.py # Factory for protocol instances
│
├── lib/                    # Reusable libraries
│   ├── can/                # CAN communication
│   │   ├── can_interface.py  # SimulatorApp CAN interface
│   │   └── ...
│   └── mqtt/               # MQTT communication
│       ├── mqtt_client.py  # MQTT client class
│       └── ...
│
├── service/                # Main services
│   ├── __init__.py
│   └── suspension_service.py  # Main service for the suspension tester
│
├── hardware/               # Hardware interfaces
│   ├── can/                # CAN-specific hardware
│   └── sensors/            # Sensors for weight and position
│
├── test_methods/           # Implementation of test methods
│   ├── phase_shift/        # EGEA-compliant phase-shift method
│   └── resonance/          # Classic resonance method
│
├── processing/             # Signal processing modules
│
├── utils/                  # General utility functions
│
└── main.py                 # Main entry point
```

## Installation

```shell
# Clone the repository
git clone https://github.com/username/suspension_tester.git
cd suspension_tester

# Install dependencies
pip install -e .
```

## Configuration

Configuration is handled through the central ConfigManager, which supports multiple sources:

1. **Default Configuration**: Predefined default values for all parameters
2. **Configuration File**: YAML or JSON file (defaults to `~/.suspension_tester/config.yaml`)
3. **Environment Variables**: Override settings with the prefix `SUSPENSION_`

Example configuration file with EUSAMA protocol:

```yaml
can:
  interface: can0
  baudrate: 1000000  # 1 Mbit/s for EUSAMA
  auto_detect_baud: true
  protocol: eusama

hardware:
  sensor_ports:
    weight: /dev/ttyUSB0
    position: /dev/ttyUSB1
```

## Usage

### Basic Usage

```bash
# Run as installed package
suspension-tester

# Or run directly
python -m suspension_tester.main
```

### Programmatic Usage

```python
from suspension_tester.config import ConfigManager
from suspension_tester.service.suspension_service import SuspensionTesterService
from suspension_tester.lib.can.can_interface import CanInterface
from suspension_tester.protocols.eusama_protocol import EusamaProtocol

# Load configuration
config = ConfigManager()

# Use CAN interface
can_interface = CanInterface(
    channel=config.get(["can", "interface"]),
    baudrates=[1000000],  # 1 Mbit/s for EUSAMA
    auto_detect_baud=True
)

# Initialize EUSAMA protocol
eusama_protocol = EusamaProtocol(can_interface)
eusama_protocol.register_callbacks()

# Motor control
eusama_protocol.send_motor_command("left", 8)  # Start left motor for 8 seconds

# Lamp control
eusama_protocol.send_lamp_command(left=False, drive_in=True, right=False)  # Turn on drive-in lamp

# Display control
eusama_protocol.send_display_command(25, 345, 356)  # Diff: 25, Left: 345, Right: 356
```

## Development

### Dependencies

- Python >= 3.8
- paho-mqtt >= 2.0.0
- python-can >= 4.0.0
- numpy
- scipy
- PyYAML (for configuration management)

### Running Tests

```bash
pytest
```

## Documentation

For more detailed information about the measurement methods and the functionality of the suspension tester, see the [technical documentation](docs/Suspension_Tester-Technical_Documentation.md).