# Konfigurationssystem für den Fahrwerkstester

Dieses Verzeichnis enthält das zentrale Konfigurationssystem für den Fahrwerkstester. Es verwendet [Pydantic](https://pydantic-docs.helpmanual.io/) für Validierung und Umgebungsvariablen-Integration.

## Überblick

Das Konfigurationssystem besteht aus zwei Hauptkomponenten:

1. **`config_model.py`**: Enthält die Pydantic-basierten Konfigurationsklassen und eine zentrale `settings`-Instanz.
2. **`settings.py`**: Stellt Rückwärtskompatibilität mit älterem Code sicher, der Konfiguration als Dictionaries erwartet.

## Verwendung

### Neue Anwendungen

Für neue Anwendungen empfehlen wir die direkte Verwendung der Pydantic-basierten Konfiguration:

```python
from suspension_core.config.config_model import settings

# MQTT-Konfiguration verwenden
mqtt_broker = settings.mqtt.broker
mqtt_port = settings.mqtt.port

# CAN-Konfiguration verwenden
can_interface = settings.can.interface
can_baudrate = settings.can.baudrate
can_protocol = settings.can.protocol

# Test-Konfiguration verwenden
test_method = settings.test.method
min_freq = settings.test.min_freq
max_freq = settings.test.max_freq
phase_threshold = settings.test.phase_shift_threshold

# Allgemeine Konfiguration
log_level = settings.log_level
```

### Bestehende Anwendungen

Bestehender Code, der die alten Konfigurationsdictionaries verwendet, funktioniert weiterhin:

```python
from suspension_core.config.settings import MQTT_CONFIG, CAN_CONFIG, TEST_PARAMETERS

# MQTT-Konfiguration verwenden
mqtt_broker = MQTT_CONFIG["BROKER"]
mqtt_port = MQTT_CONFIG["PORT"]

# CAN-Konfiguration verwenden
can_interface = CAN_CONFIG["INTERFACE"]
can_baudrate = CAN_CONFIG["DEFAULT_BAUDRATE"]
can_protocol = CAN_CONFIG["PROTOCOL"]

# Test-Konfiguration verwenden
min_freq = TEST_PARAMETERS["MIN_CALC_FREQ"]
max_freq = TEST_PARAMETERS["MAX_CALC_FREQ"]
phase_threshold = TEST_PARAMETERS["PHASE_SHIFT_MIN"]
```

## Umgebungsvariablen

Die Konfiguration kann über Umgebungsvariablen angepasst werden:

| Umgebungsvariable | Beschreibung | Standardwert |
|-------------------|--------------|--------------|
| `SUSPENSION_MQTT_BROKER` | MQTT-Broker-Adresse | `localhost` |
| `SUSPENSION_MQTT_PORT` | MQTT-Broker-Port | `1883` |
| `SUSPENSION_MQTT_USERNAME` | MQTT-Benutzername | `None` |
| `SUSPENSION_MQTT_PASSWORD` | MQTT-Passwort | `None` |
| `SUSPENSION_CAN_INTERFACE` | CAN-Interface | `can0` |
| `SUSPENSION_CAN_BAUDRATE` | CAN-Baudrate | `1000000` |
| `SUSPENSION_CAN_PROTOCOL` | CAN-Protokoll (`eusama` oder `asa`) | `eusama` |
| `SUSPENSION_TEST_METHOD` | Testmethode | `phase_shift` |
| `SUSPENSION_TEST_MIN_FREQ` | Minimale Testfrequenz | `6.0` |
| `SUSPENSION_TEST_MAX_FREQ` | Maximale Testfrequenz | `18.0` |
| `SUSPENSION_TEST_PHASE_THRESHOLD` | Phasenverschiebungsschwelle | `35.0` |
| `LOG_LEVEL` | Log-Level | `INFO` |

## Vorteile des neuen Systems

- **Typsicherheit**: Pydantic stellt sicher, dass Konfigurationswerte den richtigen Typ haben.
- **Validierung**: Ungültige Werte werden frühzeitig erkannt (z.B. ungültige Protokolle).
- **Umgebungsvariablen**: Einfache Konfiguration über Umgebungsvariablen.
- **Dotenv-Unterstützung**: Konfiguration kann auch über `.env`-Dateien erfolgen.
- **Zentrale Konfiguration**: Alle Konfigurationsparameter an einem Ort.
- **IDE-Unterstützung**: Bessere Autovervollständigung und Dokumentation in IDEs.

## Erweiterung

Um neue Konfigurationsparameter hinzuzufügen:

1. Erweitere die entsprechende Klasse in `config_model.py`.
2. Aktualisiere bei Bedarf die Dictionaries in `settings.py` für Rückwärtskompatibilität.
3. Dokumentiere die neuen Parameter in dieser README.

## Tests

Das Skript `test_config.py` kann verwendet werden, um die Konfiguration zu testen:

```bash
python -m suspension_core.config.test_config
```