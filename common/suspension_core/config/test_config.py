"""
Test-Skript für die Pydantic-basierte Konfiguration.

Dieses Skript testet, ob die Konfiguration korrekt geladen wird und
ob Umgebungsvariablen die Standardwerte überschreiben können.
"""
import os
import sys
from pathlib import Path

# Füge das Projektverzeichnis zum Python-Pfad hinzu, falls nötig
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Importiere die Konfiguration
from suspension_core.config.config_model import settings

def test_default_values():
    """Testet, ob die Standardwerte korrekt geladen werden."""
    print("=== Test der Standardwerte ===")
    print(f"MQTT Broker: {settings.mqtt.broker}")
    print(f"MQTT Port: {settings.mqtt.port}")
    print(f"CAN Interface: {settings.can.interface}")
    print(f"CAN Baudrate: {settings.can.baudrate}")
    print(f"CAN Protokoll: {settings.can.protocol}")
    print(f"Test Methode: {settings.test.method}")
    print(f"Test Min. Frequenz: {settings.test.min_freq}")
    print(f"Test Max. Frequenz: {settings.test.max_freq}")
    print(f"Test Phasenverschiebungsschwelle: {settings.test.phase_shift_threshold}")
    print(f"Log Level: {settings.log_level}")
    print()

def test_environment_variables():
    """Testet, ob Umgebungsvariablen die Standardwerte überschreiben."""
    print("=== Test der Umgebungsvariablen ===")
    
    # Setze einige Umgebungsvariablen
    os.environ["SUSPENSION_MQTT_BROKER"] = "test-broker.example.com"
    os.environ["SUSPENSION_CAN_INTERFACE"] = "vcan0"
    os.environ["SUSPENSION_TEST_MIN_FREQ"] = "5.5"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Lade die Konfiguration neu
    from importlib import reload
    import suspension_core.config.config_model
    reload(suspension_core.config.config_model)
    from suspension_core.config.config_model import settings as new_settings
    
    # Überprüfe, ob die Umgebungsvariablen die Standardwerte überschrieben haben
    print(f"MQTT Broker (erwartet: test-broker.example.com): {new_settings.mqtt.broker}")
    print(f"CAN Interface (erwartet: vcan0): {new_settings.can.interface}")
    print(f"Test Min. Frequenz (erwartet: 5.5): {new_settings.test.min_freq}")
    print(f"Log Level (erwartet: DEBUG): {new_settings.log_level}")
    print()
    
    # Setze die Umgebungsvariablen zurück
    del os.environ["SUSPENSION_MQTT_BROKER"]
    del os.environ["SUSPENSION_CAN_INTERFACE"]
    del os.environ["SUSPENSION_TEST_MIN_FREQ"]
    del os.environ["LOG_LEVEL"]

def test_validation():
    """Testet die Validierung der Konfigurationswerte."""
    print("=== Test der Validierung ===")
    
    # Teste die Protokollvalidierung
    os.environ["SUSPENSION_CAN_PROTOCOL"] = "invalid_protocol"
    
    try:
        # Lade die Konfiguration neu
        from importlib import reload
        import suspension_core.config.config_model
        reload(suspension_core.config.config_model)
        from suspension_core.config.config_model import settings as new_settings
        print("FEHLER: Validierung hat ungültiges Protokoll nicht erkannt!")
    except ValueError as e:
        print(f"Validierung erfolgreich: {e}")
    
    # Setze die Umgebungsvariable zurück
    del os.environ["SUSPENSION_CAN_PROTOCOL"]
    print()

def test_backward_compatibility():
    """Testet die Rückwärtskompatibilität mit dem alten Konfigurationssystem."""
    print("=== Test der Rückwärtskompatibilität ===")
    
    # Importiere die alten Konfigurationsdictionaries
    from suspension_core.config.settings import MQTT_CONFIG, CAN_CONFIG, TEST_PARAMETERS
    
    # Überprüfe, ob die Werte korrekt übernommen wurden
    print(f"MQTT_CONFIG['BROKER'] (erwartet: {settings.mqtt.broker}): {MQTT_CONFIG['BROKER']}")
    print(f"MQTT_CONFIG['PORT'] (erwartet: {settings.mqtt.port}): {MQTT_CONFIG['PORT']}")
    print(f"CAN_CONFIG['INTERFACE'] (erwartet: {settings.can.interface}): {CAN_CONFIG['INTERFACE']}")
    print(f"CAN_CONFIG['DEFAULT_BAUDRATE'] (erwartet: {settings.can.baudrate}): {CAN_CONFIG['DEFAULT_BAUDRATE']}")
    print(f"CAN_CONFIG['PROTOCOL'] (erwartet: {settings.can.protocol}): {CAN_CONFIG['PROTOCOL']}")
    print(f"TEST_PARAMETERS['MIN_CALC_FREQ'] (erwartet: {settings.test.min_freq}): {TEST_PARAMETERS['MIN_CALC_FREQ']}")
    print(f"TEST_PARAMETERS['MAX_CALC_FREQ'] (erwartet: {settings.test.max_freq}): {TEST_PARAMETERS['MAX_CALC_FREQ']}")
    print(f"TEST_PARAMETERS['PHASE_SHIFT_MIN'] (erwartet: {settings.test.phase_shift_threshold}): {TEST_PARAMETERS['PHASE_SHIFT_MIN']}")
    print()

if __name__ == "__main__":
    test_default_values()
    test_environment_variables()
    test_validation()
    test_backward_compatibility()
    
    print("Alle Tests abgeschlossen.")