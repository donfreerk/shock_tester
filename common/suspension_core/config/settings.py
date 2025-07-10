"""
Konfigurationseinstellungen für den Fahrwerkstester

Diese Datei stellt Kompatibilität mit älterem Code sicher, der die Konfiguration
als Dictionaries erwartet. Neue Code sollte die Pydantic-basierte Konfiguration verwenden:

from suspension_core.config.config_model import settings

Beispiel:
    mqtt_broker = settings.mqtt.broker
    can_interface = settings.can.interface
"""
from .config_model import settings

# MQTT-Konfiguration
MQTT_CONFIG = {
    "BROKER": settings.mqtt.broker,
    "PORT": settings.mqtt.port,
    "CLIENT_ID": "suspension_tester",
    "USERNAME": settings.mqtt.username or "admin",
    "PASSWORD": settings.mqtt.password or "",
    "TOPICS": {
        "TEST_RESULTS": "suspension/results",
        "TEST_STATUS": "suspension/status",
        "SYSTEM_STATUS": "suspension/system",
        "COMMANDS": "suspension/commands",
        "can_data": "suspension/can_data",
    },
}

# MQTT-Namespace-Konfiguration
MQTT_TOPICS = {
    # Gemeinsame Topics für beide Anwendungen
    "STATUS": "suspension/status",
    "MEASUREMENTS": "suspension/measurements/processed",
    "TEST_RESULTS": "suspension/test/result",
    # Spezifische Topics für die suspension_tester_gui
    "GUI_COMMAND": "suspension/gui/command",
    # Spezifische Topics für den SimulatorApp_simulator
    "SIMULATOR_COMMAND": "suspension/simulator/command",
    # Topics für den realen Tester
    "TESTER_COMMAND": "suspension/tester/command",
    "TESTER_STATUS": "suspension/tester/status",
    # System-Topics
    "SYSTEM_STATUS": "suspension/system/status",
    "SYSTEM_HEARTBEAT": "suspension/system/heartbeat",
}
# REST-API Konfiguration
API_CONFIG = {
    "BASE_URL": "http://localhost:8080/api",
    "API_KEY": "test_api_key",
    "TIMEOUT": 10,  # Sekunden
    "RETRY_ATTEMPTS": 3,
}

# Hardware-Konfiguration
HARDWARE_CONFIG = {
    "SENSOR_PORTS": {
        "WEIGHT": "/dev/ttyUSB0",
        "POSITION": "/dev/ttyUSB1",
    },
    "CAN_INTERFACE": "can0",
    "CAN_BAUDRATE": 250000,
    "MOTION_SYSTEM": {
        "MAX_FREQUENCY": 25,  # Hz
        "MIN_FREQUENCY": 2,  # Hz
        "AMPLITUDE": 6.0,  # mm
    },
}

# Servicekonfiguration
SERVICE_CONFIG = {
    "POLLING_INTERVAL": 0.1,  # Sekunden
    "STATUS_UPDATE_INTERVAL": 5.0,  # Sekunden
    "AUTO_RETRY": True,
    "MAX_RETRIES": 3,
}

# Parameter für Phase-Shift-Methode (EGEA)
TEST_PARAMETERS = {
    "MIN_CALC_FREQ": settings.test.min_freq,  # Hz - Minimale Frequenz für Berechnungen
    "MAX_CALC_FREQ": settings.test.max_freq,  # Hz - Maximale Frequenz für Berechnungen
    "DELTA_F": 5,  # Hz - Frequenzbereich für minimale Phasenverschiebungserkennung
    "STATIC_WEIGHT_LIMIT": 25,  # daN - Maximale Gewichtsdifferenz vor/nach Test
    "PHASE_SHIFT_MIN": settings.test.phase_shift_threshold,  # Grad - Minimale akzeptable Phasenverschiebung
    "RFST_FMAX": 25.0,  # % - Bereich für Fup-Erkennung (oben)
    "RFST_FMIN": 25.0,  # % - Bereich für Fdn-Erkennung (unten)
    "PLATFORM_AMPLITUDE": 6.0,  # mm - Peak-to-Peak Amplitude
    "UNDER_LIM_PERC": 1.0,  # % - Prozentsatz für Untergrenze der Kraft
    "METHOD": settings.test.method,  # Testmethode aus Pydantic-Konfiguration
}

# Parameter für Resonanzmethode
RESONANCE_PARAMETERS = {
    "FACTOR_WEIGHT": {
        1500: 0.2345,  # Faktor für 1500kg Gewichtsklasse
        2000: 0.3456,  # Faktor für 2000kg Gewichtsklasse
    },
    "FACTOR_AMPLITUDE": 1.234,  # Faktor für Amplitudenumrechnung
    "TIMER_VALUES": {
        "IDLE_TIME": 3,  # Sek. - Ruhezeit für Waage
        "STARTUP_TIMER": 5,  # Sek. - Countdown vor Motorstart
        "MOTOR_RUNTIME": 8,  # Sek. - Motorlaufzeit
        "AMPLITUDE_DISPLAY": 3,  # Sek. - Anzeigezeit Amplitude
        "EFFECTIVENESS_DISPLAY": 3,  # Sek. - Anzeigezeit Effektivität
    },
}

# Fahrzeugtypen
VEHICLE_TYPES = {
    "M1": {  # Personenkraftwagen
        "SPRING_CONST_RANGE": (10000, 30000),  # N/m
        "DAMPING_CONST_RANGE": (1000, 2000),  # Ns/m
        "UNSPRUNG_MASS": 32.5,  # kg (Durchschnitt)
    },
    "N1": {  # Leichte Nutzfahrzeuge
        "SPRING_CONST_RANGE": (20000, 45000),  # N/m
        "DAMPING_CONST_RANGE": (1500, 3000),  # Ns/m
        "UNSPRUNG_MASS": 47.5,  # kg (Durchschnitt)
    },
}

# Bewertungskriterien
EVALUATION = {
    "ABSOLUTE_CRITERIA": {
        "PHASE_SHIFT_MIN": 35.0,  # Grad - Absolutes Minimum der Phasenverschiebung
        "RIGIDITY_LOW": 160,  # N/mm - Minimale akzeptable Reifensteifigkeit
        "RIGIDITY_HIGH": 400,  # N/mm - Maximale akzeptable Reifensteifigkeit
    },
    "RELATIVE_CRITERIA": {
        "MAX_AMPLITUDE_IMBALANCE": 30.0,  # % - Maximale relative Amplitudenunwucht
        "PHASE_SHIFT_IMBALANCE": 30.0,  # % - Maximale Phasenverschiebungsunwucht
        "RIGIDITY_IMBALANCE": 35.0,  # % - Maximale Reifensteifigkeitsunwucht
    },
}

# CAN-Konfiguration
CAN_CONFIG = {
    "DEFAULT_BAUDRATE": settings.can.baudrate,  # Aus Pydantic-Konfiguration
    "ALTERNATIVE_BAUDRATE": 250000,  # Fallback auf ASA-Baudrate
    "AUTO_DETECT_BAUD": True,
    "ALIVE_MESSAGE_INTERVAL": 3.0,  # Sekunden
    "PROTOCOL": settings.can.protocol,  # Aus Pydantic-Konfiguration
    "USE_SIMULATOR": True,  # False für echten CAN-Bus, True für Simulator
    "SIMULATION_PROFILE": settings.can.protocol,  # Aus Pydantic-Konfiguration
    "SIMULATION_INTERVAL": 0.001,  # 1000 Hz
    "INTERFACE": settings.can.interface,  # Aus Pydantic-Konfiguration
}

# EUSAMA-Konfiguration
EUSAMA_CONFIG = {
    "BITRATE": 1000000,  # 1 Mbit/s für EUSAMA
    "BASE_ID": 0x08AAAA60,  # 'EUS'-Basis (ASCII EUS << 5)
    "MOTOR_CONTROL_ID": 0x08AAAA71,
    "DISPLAY_CONTROL_ID": 0x08AAAA72,
    "LAMP_CONTROL_ID": 0x08AAAA73,
}