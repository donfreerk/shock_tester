# Suspension Tester - Technical Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Measurement Methods](#measurement-methods)
    - [Phase-Shift Method (EGEA)](#phase-shift-method-egea)
    - [Resonance Principle](#resonance-principle)
3. [Architecture and Module Structure](#architecture-and-module-structure)
    - [Overview](#overview)
    - [Core Libraries](#core-libraries)
    - [Service Layer](#service-layer)
    - [Protocol Abstraction](#protocol-abstraction)
    - [Configuration Management](#configuration-management)
4. [Communication Protocols](#communication-protocols)
    - [EUSAMA Protocol](#eusama-protocol)
    - [ASA-Livestream Protocol](#asa-livestream-protocol)
5. [Mathematical Calculations and Algorithms](#mathematical-calculations-and-algorithms)
    - [Phase Shift Calculation](#phase-shift-calculation)
    - [Resonance Analysis](#resonance-analysis)
    - [Damping Ratio](#damping-ratio)
    - [Tire Rigidity](#tire-rigidity)
    - [Imbalance Calculation](#imbalance-calculation)
6. [Sensors and Signal Processing](#sensors-and-signal-processing)
7. [Evaluation Criteria](#evaluation-criteria)
8. [Test Execution](#test-execution)
9. [Diagnostic Functions](#diagnostic-functions)

## Introduction

The suspension tester is used to evaluate the damping behavior of vehicle suspensions. It enables non-intrusive assessment of shock absorber function without requiring disassembly of the vehicle. This document describes the technical details, mathematical calculations, and functionality of the implemented system.

The system supports two different measurement methods:

1. The classic resonance principle
2. The modern phase-shift method according to EGEA specifications

## Measurement Methods

### Phase-Shift Method (EGEA)

The phase-shift method is based on measuring the phase shift between platform movement and tire contact force. This method is standardized according to the EGEA specification (SPECSUS2018).

#### Functional Principle

- Continuous excitation of the suspension through a frequency-variable oscillation (25 Hz to 5 Hz)
- Measurement of the phase shift (φ) between platform movement and vertical tire contact force
- Determination of the minimum phase angle (φmin) in the range of axle mass resonance

The implementation of this method can be found in the `PhaseShiftProcessor` class in
`/suspension_tester/test_methods/phase_shift/processor.py`.

#### Measured Parameters

- Minimum phase angle φmin (main criterion for damper effectiveness)
- Maximum relative force amplitude (RFAmax)
- Tire rigidity (rig)
- Resonance frequency (fres)

### Resonance Principle

The resonance principle is based on exciting the suspension and analyzing the free decay behavior.

#### Functional Principle

- Excitation of the suspension via an eccentric drive to a nominal frequency of approx. 25 Hz
- Shutting off the motor and observing the free decay behavior
- Evaluation of amplitudes and damping during the decay process

The implementation of this method can be found in the `ResonanceProcessor` class in
`/suspension_tester/test_methods/resonance/processor.py`.

#### Measured Parameters

- Amplitude: Maximum oscillation amplitude
- Effectiveness: Damping effect of the shock absorber (approx. 70% for intact dampers)

## Architecture and Module Structure

### Overview

The software has a modular design to maximize reusability and maintainability. The architecture is based on a clear separation of core components (core libraries), application logic (service layer), protocol implementations, and configuration management.

```
suspension_tester/
├── protocols/              # Protocol implementations
│   ├── base_protocol.py    # Abstract base class for protocols
│   ├── eusama_protocol.py  # EUSAMA protocol implementation
│   ├── asa_protocol.py     # ASA livestream protocol implementation
│   └── protocol_factory.py # Factory for protocol instances
│
├── lib/                    # Reusable core libraries
│   ├── can/                # CAN communication
│   └── mqtt/               # MQTT communication
├── service/                # Application logic
├── config/                 # Configuration management
└── ...                     # Other modules
```

### Core Libraries

The core libraries in the `lib` directory are designed to be usable independently from the rest of the project:

1. **CAN Module (`lib/can/`)**:
    - `can_interface.py`: Provides the central `CanInterface` class for CAN communication
    - Features:
        - Automatic baud rate detection
        - Message validation and processing
        - Callback-based event processing
        - Thread-safe implementation

2. **MQTT Module (`lib/mqtt/`)**:
    - `mqtt_client.py`: Contains the enhanced `MqttClient` class
    - Features:
        - Robust connection handling with automatic reconnection
        - Topic-specific callbacks
        - JSON conversion and validation
        - Support for QoS and Retain flags

### Service Layer

The service layer in `service/suspension_service.py` encapsulates the main business logic:

- `SuspensionTesterService`: Coordinates the entire test process
    - Hardware communication
    - Test execution
    - Result analysis and reporting
    - System status management

### Protocol Abstraction

The new protocol abstraction in `protocols/` provides a SimulatorApp interface for different CAN protocols:

1. **Base Protocol (`base_protocol.py`)**:
   - Defines the common interface for all protocol implementations
   - Abstract methods for motor control, callbacks, etc.

2. **EUSAMA Protocol (`eusama_protocol.py`)**:
   - Implements the EUSAMA protocol for the suspension tester
   - 1 Mbit/s bitrate, Extended IDs with 'EUS' base
   - Supports motor control, lamp control, and display functions

3. **ASA Protocol (`asa_protocol.py`)**:
   - Implements the ASA Livestream protocol (for compatibility)
   - 250/125 kBit/s bitrate, Extended IDs with 'ALS' base

4. **Protocol Factory (`protocol_factory.py`)**:
   - Creates the appropriate protocol instance based on configuration
   - Simplifies switching between different protocols

This abstraction allows the business logic to remain independent of the specific communication protocol used.

### Configuration Management

The configuration management in `config/config_manager.py` provides:

- Hierarchical configuration model
- Multiple configuration sources (default values, files, environment variables)
- Validation and type checking
- Central access point for all configuration parameters

The `ConfigManager` class is implemented as a singleton and enables consistent access to configuration parameters throughout the system.

## Communication Protocols

### EUSAMA Protocol

The EUSAMA protocol is the primary communication protocol for the suspension tester. It defines CAN communication via Extended IDs (29-bit) based on the ASCII code 'EUS'.

#### CAN Bitrate

- 1 Mbit/s (high resolution for precise measurements)

#### CAN ID Structure

Extended IDs (29-bit) consisting of:
- 24-bit Application ID: ASCII 'EUS' (0x414e53)
- 5-bit Subcode: Identifies the message type

ID ranges:
- 0x08AAAA60 - 0x08AAAA6F: Messages from cabinet to external devices
- 0x08AAAA70 - 0x08AAAA7F: Messages from external devices to cabinet

#### Important Message Types

1. **Raw Data (IDs 0x08AAAA60, 0x08AAAA61)**:
   - Transmit DMS values (strain gauge sensors)
   - 8 values split into 2 messages (left/right)
   - DMS values have range 0-1023

2. **Motor Control (ID 0x08AAAA71)**:
   - Controls start/stop of test motors
   - First byte: Motor mask (0x01=left, 0x02=right, 0x00=stop)
   - Second byte: Runtime in seconds

3. **Display Control (ID 0x08AAAA72)**:
   - Controls 3 displays (left, right, difference)
   - For showing test results and status information

4. **Lamp Control (ID 0x08AAAA73)**:
   - Controls lamps on the suspension tester
   - Bitmask for different lamps (left, drive-in, right)

5. **Top Position (ID 0x08AAAA67)**:
   - Signals when the upper position of the plate is reached
   - Important for synchronizing test cycles

#### Implementation

The EUSAMA protocol implementation can be found in `protocols/eusama_protocol.py`. It provides methods for:
- Sending motor commands
- Controlling lamps and displays
- Processing received sensor data
- Callback-based event handling

### ASA-Livestream Protocol

The ASA-Livestream protocol is an alternative protocol used for roller and plate testers. It is included in this project as a compatibility option.

#### CAN Bitrate

- 250 kBit/s for passenger car testers
- 125 kBit/s for truck testers

#### CAN ID Structure

Extended IDs (29-bit) consisting of:
- 24-bit Application ID: ASCII 'ALS' (0x414c53)
- 5-bit Subcode: Identifies the message type

#### Important Message Types

1. **Measurement Points (IDs 0-3)**:
   - Transmit brake force, speed, slip, etc.
   - Distributed across multiple CAN packets

2. **ALIVE Messages (ID 6)**:
   - Status messages and control information
   - Contains flags for various functions (traffic light, motor, etc.)

#### Differences from EUSAMA

- Lower bitrate (250/125 kBit/s vs. 1 Mbit/s)
- Different data representation (brake force vs. DMS values)
- Indirect motor control via status flags
- Different display and lamp functionality

## Mathematical Calculations and Algorithms

### Phase Shift Calculation

The phase shift is calculated in the `PhaseShiftProcessor` class in the `calculate_phase_shift()` method. The calculation is performed through the following steps:

1. **Frequency Determination**: For each cycle, the frequency is determined by `frequency = 1.0 / cycle_time`, where `cycle_time` is the time between two consecutive peaks of the platform position.

2. **Intersection Determination**: For each cycle, the intersections of the force signal with the static weight (Fst) are identified:
   ```python
   # Find intersections with static weight (Fup, Fdn)
   for j in range(1, len(cycle_force)):
       if (cycle_force[j - 1] < static_weight < cycle_force[j]) or (
           cycle_force[j - 1] > static_weight > cycle_force[j]
       ):
           # Linear interpolation to find more precise crossing point
           frac = (static_weight - cycle_force[j - 1]) / (
               cycle_force[j] - cycle_force[j - 1]
           )
           cross_time = cycle_time_rel[j - 1] + frac * (
               cycle_time_rel[j] - cycle_time_rel[j - 1]
           )
           crossings.append(cross_time)
   ```

3. **RFstF Condition Check**: The intersections are only considered if they are within valid ranges:
   ```python
   # Check RFstFMin and RFstFMax conditions
   if len(crossings) >= 2:
       delta_f = max(cycle_force) - min(cycle_force)
       f_min_limit = min(cycle_force) + delta_f * self.rfst_fmin / 100
       f_max_limit = max(cycle_force) - delta_f * self.rfst_fmax / 100

       # Check if crossings are within valid ranges
       if f_min_limit < static_weight < f_max_limit:
            # Further calculation...
   ```

4. **Phase Shift Calculation**: The phase shift is calculated from the reference point and cycle duration:
   ```python
   # Calculate Fref as midpoint between Down and Up
   fref = (crossings[0] + crossings[1]) / 2.0

   # Calculate the phase shift (in degrees)
   top_p_time = cycle_time_rel[0]  # TOPp(i) is start of cycle
   phase_shift = (fref - top_p_time) * frequency * 360

   # Normalize between 0° and 180°
   phase_shift = phase_shift % 360
   if phase_shift > 180:
       phase_shift = 360 - phase_shift
   ```

5. **Minimum Detection**: The minimum of the calculated phase shifts is determined:
   ```python
   min_idx = np.argmin(phase_shifts)
   min_phase = phase_shifts[min_idx]
   min_phase_freq = frequencies[min_idx]
   ```

The phase shift is expressed in degrees and should be greater than 35° for a well-functioning damper (EGEA criterion).

### Resonance Analysis

The resonance analysis is performed in the `ResonanceProcessor` class in the `process_test()` method. The algorithm includes:

1. **Weight Calculation**: The weight is calculated from the voltage difference:
   ```python
   voltage_difference = initial_voltage - voltage_data[0]
   weight = voltage_difference * weight_factor
   ```

2. **Amplitude Determination**: The maximum amplitude is determined from positive and negative peaks:
   ```python
   max_positive = max(positive_peaks) - equilibrium
   max_negative = equilibrium - min(negative_peaks)
   max_amplitude = max(max_positive, max_negative)
   ```

3. **Effectiveness Calculation**: The effectiveness is calculated as the ratio to the ideal amplitude:
   ```python
   ideal_amplitude = self._calculate_ideal_amplitude(weight)
   if amplitude > 0:
       effectiveness = (ideal_amplitude / amplitude) * 70  # 70% for ideal curve
       # Limit effectiveness to 0-100%
       effectiveness = max(0, min(100, effectiveness))
   else:
       effectiveness = 0
   ```

The ideal amplitude is determined based on the wheel weight, using a linear model: `ideal_amplitude = weight * 0.05`.

### Damping Ratio

The damping ratio is calculated in `processing/damping_ratio.py`. The calculation follows the physically correct formula:

```python
def calculate_damping_ratio(vehicle_type, weight, spring_constant, damping_constant):
    # Determine unsprung mass based on vehicle type
    unsprung_mass = VEHICLE_TYPES[vehicle_type]["UNSPRUNG_MASS"]

    # Calculate sprung mass
    sprung_mass = weight - unsprung_mass

    # Calculate damping ratio
    damping_ratio = damping_constant / (2 * np.sqrt(spring_constant * sprung_mass))

    return damping_ratio
```

This formula corresponds to the definition ζ = c / (2 * √(k * m)), where c is the damping constant, k is the spring stiffness, and m is the sprung mass.

Additionally, the damping ratio can also be calculated from the phase shift:

```python
def calculate_damping_from_phase_shift(phase_shift_deg):
    # Convert from degrees to radians
    phase_shift_rad = np.radians(phase_shift_deg)

    # EGEA formula for converting phase angle to damping ratio
    damping_ratio = np.sin(phase_shift_rad) / 2

    return damping_ratio
```

### Tire Rigidity

The tire rigidity (rig) is calculated according to the EGEA specification. The implementation can be found in the `PhaseShiftProcessor` class:

```python
def calculate_rigidity(self, force_amplitude, platform_amplitude):
    a_rig = 0.571
    b_rig = 46.0
    rigidity = a_rig * (force_amplitude / platform_amplitude) + b_rig

    return rigidity
```

This formula uses the parameters a_rig = 0.571 and b_rig = 46.0, as specified in the EGEA specifications.

### Imbalance Calculation

The imbalance between left and right wheels is calculated for various parameters to detect asymmetries in the suspension. The calculation can be found in the `SuspensionTestController` class:

```python
def _calculate_difference_percent(self, val1, val2):
    if val1 == 0 and val2 == 0:
        return 0

    max_val = max(abs(val1), abs(val2))
    if max_val == 0:
        return 0

    return abs(val1 - val2) / max_val * 100
```

This calculation is used for:
- Minimum phase shift (φmin)
- Maximum relative force amplitude (RFAmax)
- Tire rigidity (rig)

## Sensors and Signal Processing

### Weight Sensors

The weight sensors are implemented by the `WeightSensor` class in `hardware/sensors/weight_sensor.py`. The sensor measures the static and dynamic tire contact force with the following specifications:

- Measurement range: 100-1100 daN per wheel (static), up to 2200 daN (dynamic)
- Accuracy: ±6 daN (0-300 daN), ±2% of measured value (300-1100 daN)

The class implements methods for static weight measurement (`get_weights()`) and zero calibration (`zero_calibration()`).

### Position Sensors

The position sensors are implemented by the `PositionSensor` class in `hardware/sensors/position_sensor.py`. These non-contact displacement sensors measure the vertical platform position and have the following characteristics:

- Measurement range: 0-10 VDC
- Sampling rate: sufficient for frequencies up to 25 Hz (typically ≥ 1000 Hz)

The class provides methods for position measurement (`get_position()`) and waveform acquisition (`acquire_waveform()`).

### Signal Filtering

Signal filtering is performed according to the EGEA specifications, particularly for phase calculation. Dynamic calibration of the platform is performed to ensure accurate measurements.

For phase calculation, special low-pass filters following the Kaiser-Reed method (Nearly equal ripple approximation) are used. The filter properties are:

- PassMulPh = 2
- StopMulPh = 4
- ε = 0.01

To ensure measurement accuracy, dynamic calibration is performed, determining and compensating for the platform's natural frequency. The maximum allowable error margin is 4 N/Hz in the measurement range of 6-18 Hz.

## Evaluation Criteria

### Absolute Criteria

The absolute evaluation criteria are based on fixed thresholds:

1. **Minimum Phase Angle (φmin)**:
    - Good: φmin ≥ 35° (corresponds to damping ratio ≥ 0.1)
    - Poor: φmin < 35° (corresponds to damping ratio < 0.1)

   The implementation can be found in the `evaluate_phase_shift()` method of the `PhaseShiftProcessor` class:
   ```python
   def evaluate_phase_shift(self, phase_data, vehicle_type):
       min_phase = phase_data["min_phase_shift"]
       if min_phase is None:
           return {
               "pass": False,
               "reason": "No valid phase shift measured",
           }

       # Absolute criterion (AC_φmin = 35°)
       absolute_threshold = TEST_PARAMETERS["PHASE_SHIFT_MIN"]
       absolute_pass = min_phase >= absolute_threshold

       return {
           "pass": absolute_pass,
           "min_phase": min_phase,
           "threshold": absolute_threshold,
           "integer_min_phase": int(min_phase),  # iφmin (rounded down)
       }
   ```

2. **Tire Rigidity (rig)**:
    - Optimal range: 160-400 N/mm
    - Too low (< 160 N/mm): Warning (tire under-inflated)
    - Too high (> 400 N/mm): Warning (tire over-inflated)

### Relative Criteria

The relative criteria compare the measured values between left and right wheels of an axle:

1. **Phase Angle Imbalance**:
    - Maximum difference between left and right: 30%
    - Formula: Dφmin = (|φmin,left - φmin,right| / max(φmin,left, φmin,right)) * 100%

2. **Force Amplitude Imbalance**:
    - Maximum difference between left and right: 30%

3. **Tire Rigidity Imbalance**:
    - Maximum difference between left and right: 35%

The calculation of these imbalances is performed in the `SuspensionTestController` class using the `_calculate_difference_percent()` method.

## Test Execution

The test process is coordinated by the `SuspensionTesterService` class in `service/suspension_service.py`. This class is responsible for the entire lifecycle of the test:

1. **Initialization**: Set up hardware and communication
2. **Vehicle Detection**: Wait for a vehicle on the test platform
3. **Test Execution**: Perform the configured test method
4. **Result Analysis**: Evaluate the measurement results
5. **Reporting**: Transmit results via MQTT
6. **Completion**: Wait until the vehicle leaves the platform

The test process can be customized via configuration by setting the appropriate parameters in the `ConfigManager`.

The test sequence is coordinated by the `SuspensionTestController` class in `processing/suspension_test.py`. A typical test sequence includes:

### Phase-Shift Method

1. **Static Weight Measurement**: Measuring the wheel loads in the resting state
2. **Excitation at 25 Hz**: Determining tire rigidity
3. **Frequency Variation**: Continuous frequency decrease from 18 Hz to 6 Hz (duration at least 7.5 seconds)
4. **Signal Measurement**: Recording tire contact force and platform position
5. **Phase Shift Calculation**: Determining the minimum phase angle
6. **Evaluation**: Comparison with absolute and relative criteria

### Resonance Method

1. **Static Weight Measurement**: Measuring the wheel loads in the resting state
2. **Excitation**: Motor start and excitation of the suspension at approx. 25 Hz
3. **Decay Process**: Motor shutdown and observation of free decay behavior
4. **Amplitude Determination**: Measuring the maximum oscillation amplitude
5. **Effectiveness Calculation**: Calculating the damping effect
6. **Evaluation**: Comparison between left and right wheels

## Diagnostic Functions

The system offers additional diagnostic functions, particularly noise search, which is implemented in the `NoiseSearchController` class in `features/noise_search.py`.

### Noise Search

The noise search enables manual control of the excitation frequency to identify noise sources in the vehicle:

1. **Simple Noise Search**: Excitation of one side at 25 Hz
2. **Frequency-Controlled Noise Search**: Manual control of frequency via buttons

The implementation includes methods for starting the left/right side, increasing/decreasing the frequency, and stopping the noise search.