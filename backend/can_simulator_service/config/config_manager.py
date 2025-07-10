"""
Einheitliches Konfigurationsmanagement für den CAN-Simulator-Service.

Dieses Modul bietet eine zentrale Verwaltung aller Konfigurationsparameter mit
Unterstützung für mehrere Quellen (Dateien, Umgebungsvariablen) und Validierung.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Zentrale Konfigurationsverwaltung für den CAN-Simulator-Service.

    Diese Klasse bietet:
    - Laden von Konfigurationen aus verschiedenen Quellen
    - Standardwerte für alle Parameter
    - Validierung der Parameter
    - Hierarchische Speicherung und Zugriff
    - Speichern von Änderungen

    Attributes:
        config (dict): Die aktuelle Konfiguration
        config_path (Path): Pfad zur Konfigurationsdatei
        _instance (ConfigManager): Singleton-Instanz
    """

    _instance = None  # Singleton-Instanz

    def __new__(cls, *args, **kwargs):
        """Singleton-Implementierung"""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialisiert den Konfigurationsmanager.

        Args:
            config_path: Pfad zur Konfigurationsdatei (optional)
        """
        # Nur einmal initialisieren (Singleton)
        if getattr(self, "_initialized", False):
            return

        # Standardpfad für Konfigurationsdateien
        if not config_path:
            config_dir = os.environ.get(
                "CAN_SIMULATOR_SERVICE_CONFIG_DIR",
                os.path.join(str(Path.home()), ".can_simulator_service"),
            )
            self.config_path = Path(config_dir) / "config.yaml"
        else:
            self.config_path = Path(config_path)

        # Konfigurationsverzeichnis erstellen, falls nicht vorhanden
        os.makedirs(self.config_path.parent, exist_ok=True)

        # Standardkonfiguration
        self.config = self._get_default_config()

        # Konfiguration aus Datei laden
        self._load_config()

        # Konfiguration aus Umgebungsvariablen überschreiben
        self._load_env_vars()

        # Konfiguration validieren
        self._validate_config()

        # Als initialisiert markieren
        self._initialized = True

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Liefert die Standardkonfiguration.

        Returns:
            dict: Standardkonfiguration
        """
        return {
            "mqtt": {
                "broker": "192.168.0.249",
                "port": 1883,
                "client_id": "can_simulator_service",
                "username": "",
                "password": "",
                "topics": {
                    "test_results": "suspension/results",
                    "test_status": "suspension/status",
                    "system_status": "suspension/system",
                    "commands": "suspension/commands",
                    "can_data": "suspension/can_data",
                },
            },
            "can": {
                "interface": "can0",
                "baudrate": 1000000,  # 1 Mbit/s für EUSAMA
                "alternative_baudrates": [250000, 125000],
                "auto_detect_baud": True,
                "protocol": "eusama",  # Standardprotokoll
                "use_simulator": True,  # Immer True für den Simulator
                "simulation_profile": "eusama",  # "eusama" oder "asa"
                "simulation_interval": 0.001,  # 1000 Hz
            },
            "simulator": {
                "update_interval": 0.05,  # 50ms (20 Hz) für UI-Updates
                "queue_check_interval": 0.01,  # 10ms für Queue-Checks
                "max_queue_items_per_cycle": 10,  # Maximale Anzahl von Queue-Items pro Zyklus
                "auto_connect_mqtt": True,  # Automatisch mit MQTT verbinden beim Start
                "auto_start_bridge": True,  # Automatisch Bridge starten beim Start
                "auto_start_simulator": True,  # Automatisch Simulator starten beim Start
                "generate_low_level": True,  # Low-Level-CAN-Frames generieren
                "damping_quality": "good",  # Standarddämpfungsqualität
                "test_method": "phase_shift",  # Standardtestmethode
            },
            "test": {
                "phase_shift": {
                    "min_calc_freq": 6,  # Hz
                    "max_calc_freq": 18,  # Hz
                    "delta_f": 5,  # Hz
                    "static_weight_limit": 25,  # daN
                    "phase_shift_min": 35.0,  # Grad
                    "platform_amplitude": 6.0,  # mm
                },
                "evaluation": {
                    "absolute_criteria": {
                        "phase_shift_min": 35.0,  # Grad
                        "rigidity_low": 160,  # N/mm
                        "rigidity_high": 400,  # N/mm
                    },
                    "relative_criteria": {
                        "amplitude_imbalance": 30.0,  # %
                        "phase_shift_imbalance": 30.0,  # %
                        "rigidity_imbalance": 35.0,  # %
                    },
                },
            },
            "logging": {
                "level": "INFO",
                "file": "can_simulator_service.log",
                "console": True,
                "max_size": 10485760,  # 10 MB
                "backup_count": 5,
            },
        }

    def _load_config(self):
        """Lädt die Konfiguration aus der Konfigurationsdatei."""
        if not self.config_path.exists():
            logger.info(
                f"Keine Konfigurationsdatei gefunden unter {self.config_path}, verwende Standardwerte"
            )
            # Standardkonfiguration speichern für zukünftige Verwendung
            self.save_config()
            return

        try:
            # Dateiformat basierend auf Erweiterung bestimmen
            if self.config_path.suffix.lower() in [".yaml", ".yml"]:
                with open(self.config_path) as f:
                    loaded_config = yaml.safe_load(f)
            elif self.config_path.suffix.lower() == ".json":
                with open(self.config_path) as f:
                    loaded_config = json.load(f)
            else:
                logger.warning(f"Unbekanntes Konfigurationsformat: {self.config_path.suffix}")
                return

            # Geladene Konfiguration mit Standardwerten zusammenführen
            if loaded_config:
                self._update_nested_dict(self.config, loaded_config)
                logger.info(f"Konfiguration geladen aus {self.config_path}")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration aus {self.config_path}: {e}")

    def _load_env_vars(self):
        """Lädt Konfigurationswerte aus Umgebungsvariablen."""
        # Mapping von Umgebungsvariablen zu Konfigurationsschlüsseln
        env_mapping = {
            "CAN_SIMULATOR_SERVICE_MQTT_BROKER": ["mqtt", "broker"],
            "CAN_SIMULATOR_SERVICE_MQTT_PORT": ["mqtt", "port"],
            "CAN_SIMULATOR_SERVICE_MQTT_USERNAME": ["mqtt", "username"],
            "CAN_SIMULATOR_SERVICE_MQTT_PASSWORD": ["mqtt", "password"],
            "CAN_SIMULATOR_SERVICE_CAN_INTERFACE": ["can", "interface"],
            "CAN_SIMULATOR_SERVICE_CAN_BAUDRATE": ["can", "baudrate"],
            "CAN_SIMULATOR_SERVICE_LOG_LEVEL": ["logging", "level"],
            "CAN_SIMULATOR_SERVICE_UPDATE_INTERVAL": ["simulator", "update_interval"],
            "CAN_SIMULATOR_SERVICE_QUEUE_CHECK_INTERVAL": ["simulator", "queue_check_interval"],
        }

        # Umgebungsvariablen verarbeiten
        for env_var, config_path in env_mapping.items():
            if env_var in os.environ:
                # Wert aus Umgebungsvariable holen
                value = os.environ[env_var]

                # Typ konvertieren, wenn nötig
                current_value = self.get(config_path)
                if isinstance(current_value, int):
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(
                            f"Umgebungsvariable {env_var} konnte nicht in Integer konvertiert werden: {value}"
                        )
                        continue
                elif isinstance(current_value, float):
                    try:
                        value = float(value)
                    except ValueError:
                        logger.warning(
                            f"Umgebungsvariable {env_var} konnte nicht in Float konvertiert werden: {value}"
                        )
                        continue
                elif isinstance(current_value, bool):
                    value = value.lower() in ("true", "yes", "1", "y")

                # Wert in Konfiguration setzen
                self.set(config_path, value)
                logger.debug(
                    f"Konfiguration aus Umgebungsvariable überschrieben: {env_var} -> {config_path}"
                )

    def _validate_config(self):
        """Validiert die Konfiguration."""
        # Basis-Validierungen für kritische Werte

        # MQTT-Port muss im gültigen Bereich sein
        mqtt_port = self.get(["mqtt", "port"])
        if not (1 <= mqtt_port <= 65535):
            logger.warning(f"Ungültiger MQTT-Port: {mqtt_port}, setze auf Standard 1883")
            self.set(["mqtt", "port"], 1883)

        # CAN-Baudrate muss ein gültiger Wert sein
        valid_baudrates = [9600, 125000, 250000, 500000, 1000000]
        config_baudrate = self.get(["can", "baudrate"])
        if config_baudrate not in valid_baudrates:
            logger.warning(f"Ungültige CAN-Baudrate: {config_baudrate}, setze auf Standard 1000000")
            self.set(["can", "baudrate"], 1000000)

        # Logging-Level validieren
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = self.get(["logging", "level"])
        if log_level not in valid_log_levels:
            logger.warning(f"Ungültiges Logging-Level: {log_level}, setze auf Standard INFO")
            self.set(["logging", "level"], "INFO")

        # Simulator-Update-Intervall validieren
        update_interval = self.get(["simulator", "update_interval"])
        if not (0.001 <= update_interval <= 1.0):
            logger.warning(
                f"Ungültiges Update-Intervall: {update_interval}, setze auf Standard 0.05"
            )
            self.set(["simulator", "update_interval"], 0.05)

    def get(self, path: Union[str, list], default: Any = None) -> Any:
        """
        Gibt einen Konfigurationswert zurück.

        Args:
            path: Pfad zum Konfigurationswert (als Liste oder durch Punkte getrennte Zeichenkette)
            default: Standardwert, wenn der Pfad nicht existiert

        Returns:
            Der Konfigurationswert oder der Standardwert
        """
        # Pfad normalisieren
        if isinstance(path, str):
            path = path.split(".")

        # In Konfiguration navigieren
        current = self.config
        try:
            for key in path:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, path: Union[str, list], value: Any, save: bool = False):
        """
        Setzt einen Konfigurationswert.

        Args:
            path: Pfad zum Konfigurationswert (als Liste oder durch Punkte getrennte Zeichenkette)
            value: Neuer Wert
            save: Konfiguration nach dem Setzen speichern (default: False)
        """
        # Pfad normalisieren
        if isinstance(path, str):
            path = path.split(".")

        # In Konfiguration navigieren und Wert setzen
        current = self.config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[path[-1]] = value

        # Konfiguration speichern, wenn gewünscht
        if save:
            self.save_config()

    def save_config(self):
        """Speichert die aktuelle Konfiguration in die Konfigurationsdatei."""
        try:
            # Dateiformat basierend auf Erweiterung bestimmen
            if self.config_path.suffix.lower() in [".yaml", ".yml"]:
                with open(self.config_path, "w") as f:
                    yaml.dump(self.config, f, default_flow_style=False)
            elif self.config_path.suffix.lower() == ".json":
                with open(self.config_path, "w") as f:
                    json.dump(self.config, f, indent=2)
            else:
                # Standardmäßig YAML verwenden
                yaml_path = self.config_path.with_suffix(".yaml")
                with open(yaml_path, "w") as f:
                    yaml.dump(self.config, f, default_flow_style=False)
                self.config_path = yaml_path

            logger.info(f"Konfiguration gespeichert unter {self.config_path}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration unter {self.config_path}: {e}")

    def _update_nested_dict(self, d: dict, u: dict) -> dict:
        """
        Aktualisiert ein verschachteltes Dictionary rekursiv.

        Args:
            d: Ziel-Dictionary
            u: Quell-Dictionary

        Returns:
            Das aktualisierte Dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._update_nested_dict(d[k], v)
            else:
                d[k] = v
        return d

    def to_dict(self) -> dict:
        """
        Gibt die gesamte Konfiguration als Dictionary zurück.

        Returns:
            dict: Die aktuelle Konfiguration
        """
        return self.config.copy()

    def reset_to_defaults(self, save: bool = False):
        """
        Setzt die Konfiguration auf Standardwerte zurück.

        Args:
            save: Ob die Standardkonfiguration gespeichert werden soll
        """
        self.config = self._get_default_config()
        if save:
            self.save_config()


# Beispiel für die Verwendung
if __name__ == "__main__":
    # Konfigurationsmanager initialisieren
    config = ConfigManager()

    # Einige Werte abrufen
    mqtt_broker = config.get(["mqtt", "broker"])
    can_baudrate = config.get(["can", "baudrate"])
    update_interval = config.get(["simulator", "update_interval"])

    print(f"MQTT-Broker: {mqtt_broker}")
    print(f"CAN-Baudrate: {can_baudrate}")
    print(f"UI-Update-Intervall: {update_interval}")

    # Einen Wert ändern
    config.set(["mqtt", "broker"], "192.168.1.100", save=True)

    # Gesamte Konfiguration ausgeben
    import pprint

    pprint.pprint(config.to_dict())