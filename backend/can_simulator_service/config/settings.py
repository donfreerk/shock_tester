"""
Konfigurationseinstellungen für den CAN-Simulator-Service
"""

# MQTT-Konfiguration
MQTT_CONFIG = {
    "BROKER": "localhost",
    "PORT": 1883,
    "CLIENT_ID": "can_simulator_service",
    "USERNAME": "admin",
    "PASSWORD": "",
    "TOPICS": {
        "TEST_RESULTS": "suspension/results",
        "TEST_STATUS": "suspension/status",
        "SYSTEM_STATUS": "suspension/system",
        "COMMANDS": "suspension/commands",
        "can_data": "suspension/can_data",
    },
}

# Direkte Konstanten für die alte API-Kompatibilität
MQTT_BROKER_HOST = MQTT_CONFIG["BROKER"]
MQTT_BROKER_PORT = MQTT_CONFIG["PORT"]
MQTT_CLIENT_ID = MQTT_CONFIG["CLIENT_ID"]

# MQTT-Namespace-Konfiguration
MQTT_TOPICS = {
    # Gemeinsame Topics für beide Anwendungen
    "STATUS": "suspension/status",
    "MEASUREMENTS": "suspension/measurements/processed",
    "TEST_RESULTS": "suspension/test/result",
    # Spezifische Topics für die suspension_tester_gui
    "GUI_COMMAND": "suspension/gui/command",
    # Spezifische Topics für den CAN-Simulator-Service
    "SIMULATOR_COMMAND": "suspension/simulator/command",
    # Topics für den realen Tester
    "TESTER_COMMAND": "suspension/tester/command",
    "TESTER_STATUS": "suspension/tester/status",
    # System-Topics
    "SYSTEM_STATUS": "suspension/system/status",
    "SYSTEM_HEARTBEAT": "suspension/system/heartbeat",
}

# Parameter für Phase-Shift-Methode (EGEA)
TEST_PARAMETERS = {
    "MIN_CALC_FREQ": 6,  # Hz - Minimale Frequenz für Berechnungen
    "MAX_CALC_FREQ": 18,  # Hz - Maximale Frequenz für Berechnungen
    "DELTA_F": 5,  # Hz - Frequenzbereich für minimale Phasenverschiebungserkennung
    "STATIC_WEIGHT_LIMIT": 25,  # daN - Maximale Gewichtsdifferenz vor/nach Test
    "PHASE_SHIFT_MIN": 35.0,  # Grad - Minimale akzeptable Phasenverschiebung
    "RFST_FMAX": 25.0,  # % - Bereich für Fup-Erkennung (oben)
    "RFST_FMIN": 25.0,  # % - Bereich für Fdn-Erkennung (unten)
    "PLATFORM_AMPLITUDE": 6.0,  # mm - Peak-to-Peak Amplitude
    "UNDER_LIM_PERC": 1.0,  # % - Prozentsatz für Untergrenze der Kraft
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
    "DEFAULT_BAUDRATE": 1000000,  # Ändern auf 1 Mbit/s für EUSAMA
    "ALTERNATIVE_BAUDRATE": 250000,  # Fallback auf ASA-Baudrate
    "AUTO_DETECT_BAUD": True,
    "ALIVE_MESSAGE_INTERVAL": 3.0,  # Sekunden
    "PROTOCOL": "eusama",  # Festlegung des Standardprotokolls
    "USE_SIMULATOR": True,  # Immer True für den Simulator
    "SIMULATION_PROFILE": "eusama",  # "eusama" oder "asa"
    "SIMULATION_INTERVAL": 0.001,  # 1000 Hz
}

# EUSAMA-Konfiguration
EUSAMA_CONFIG = {
    "BITRATE": 1000000,  # 1 Mbit/s für EUSAMA
    "BASE_ID": 0x08AAAA60,  # 'EUS'-Basis (ASCII EUS << 5)
    "MOTOR_CONTROL_ID": 0x08AAAA71,
    "DISPLAY_CONTROL_ID": 0x08AAAA72,
    "LAMP_CONTROL_ID": 0x08AAAA73,
}

# Simulator-spezifische Konfiguration
SIMULATOR_CONFIG = {
    "UPDATE_INTERVAL": 0.05,  # 50ms (20 Hz) für UI-Updates
    "QUEUE_CHECK_INTERVAL": 0.01,  # 10ms für Queue-Checks
    "MAX_QUEUE_ITEMS_PER_CYCLE": 10,  # Maximale Anzahl von Queue-Items pro Zyklus
    "AUTO_CONNECT_MQTT": True,  # Automatisch mit MQTT verbinden beim Start
    "AUTO_START_BRIDGE": True,  # Automatisch Bridge starten beim Start
    "AUTO_START_SIMULATOR": True,  # Automatisch Simulator starten beim Start
}