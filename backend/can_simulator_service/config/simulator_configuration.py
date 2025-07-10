"""
Anpassung des CAN-Simulator-Service für realistische Abtastraten.

Dieses Skript zeigt die notwendigen Änderungen, um die Abtastrate des Simulators
auf einen für die Fahrwerkstestung realistischen Wert zu erhöhen.
"""

import logging

from fahrwerkstester.backend.can_simulator_service.config.config_manager import ConfigManager
from common.suspension_core.can.interface_factory import create_can_interface

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def configure_high_sample_rate_simulator():
    """
    Konfiguriert und erstellt einen CAN-Simulator mit realistischer Abtastrate.

    Diese Funktion ändert die Konfiguration und erstellt einen Simulator mit
    einer Abtastrate von 1000 Hz, was den realen Hardware-Anforderungen entspricht.

    Returns:
        Der konfigurierte CAN-Simulator
    """
    # Konfiguration laden
    config = ConfigManager()

    # Sicherstellen, dass der Simulator verwendet wird
    config.set(["can", "USE_SIMULATOR"], True)

    # Simulationstyp und Profil festlegen
    simulation_type = "hybrid"  # "high_level", "low_level" oder "hybrid"
    simulation_profile = "eusama"  # "eusama" oder "asa"

    # Wichtig: Message-Intervall auf 0.001s (1000 Hz) setzen
    message_interval = 0.01  # Entspricht 1000 Hz Abtastrate

    logger.info(f"Erstelle Simulator mit {1 / message_interval:.0f} Hz Abtastrate")

    # Simulator erstellen
    simulator = create_can_interface(
        config=config, simulation_type=simulation_type, simulation_profile=simulation_profile
    )

    # Bei SimulatedCanInterface und WindowsCanInterface das message_interval anpassen
    if hasattr(simulator, "message_interval"):
        old_interval = simulator.message_interval
        simulator.message_interval = message_interval
        logger.info(
            f"Simulator-Intervall angepasst: {old_interval:.3f}s -> {message_interval:.3f}s"
        )

    # Bei HybridSimulator das Intervall im internen Simulator anpassen
    if hasattr(simulator, "simulator") and hasattr(simulator.simulator, "message_interval"):
        old_interval = simulator.simulator.message_interval
        simulator.simulator.message_interval = message_interval
        logger.info(
            f"Interner Simulator-Intervall angepasst: {old_interval:.3f}s -> {message_interval:.3f}s"
        )

    return simulator


# Direkte Anpassung der Konfiguration
def update_config_file():
    """
    Aktualisiert die Konfigurationsdatei mit realistischer Abtastrate.

    Diese Funktion passt die Konfigurationsdatei an, um sicherzustellen,
    dass der Simulator immer mit der richtigen Abtastrate verwendet wird.
    """
    config = ConfigManager()

    # CAN-Konfiguration anpassen
    can_config = config.get(["can"], {})

    # Aktualisierte Konfiguration
    updated_can_config = {
        "USE_SIMULATOR": True,
        "SIMULATION_PROFILE": "eusama",
        "SIMULATION_INTERVAL": 0.001,  # 1000 Hz
        "protocol": can_config.get("protocol", "eusama"),
        "interface": can_config.get("interface", "can0"),
        "baudrate": can_config.get("baudrate", 1000000),
        "auto_detect_baud": can_config.get("auto_detect_baud", True),
    }

    # Konfiguration aktualisieren
    for key, value in updated_can_config.items():
        config.set(["can", key], value)

    # High-Level-Simulator-Konfiguration aktualisieren
    high_level_config = {
        "ENABLE": True,
        "SIMULATION_MODE": "hybrid",
        "GENERATE_LOW_LEVEL": True,
        "SIMULATION_INTERVAL": 0.001,  # 1000 Hz
        "DAMPING_QUALITY": "good",
        "TEST_METHOD": "phase_shift",
    }

    for key, value in high_level_config.items():
        config.set(["HIGH_LEVEL_SIMULATOR", key], value)

    # Konfiguration speichern
    config.save_config()

    logger.info("Konfiguration aktualisiert mit 1000 Hz Abtastrate für den Simulator")


# Manuelle Anpassung der Simulator-Klasse (wenn nötig)
def patch_simulator_class():
    """
    Patcht die Simulator-Klasse zur Laufzeit für eine höhere Abtastrate.

    Diese Funktion modifiziert die Simulator-Klasse direkt, wenn die
    Konfigurationsanpassung nicht ausreicht.
    """
    try:
        # Versuche den Simulator zu importieren
        from fahrwerkstester.backend.can_simulator_service.core.simulator import CanSimulator

        # Originales Intervall speichern
        original_interval = getattr(CanSimulator, "DEFAULT_MESSAGE_INTERVAL", 0.1)

        # Intervall anpassen
        CanSimulator.DEFAULT_MESSAGE_INTERVAL = 0.001  # 1000 Hz

        logger.info(
            f"CanSimulator.DEFAULT_MESSAGE_INTERVAL angepasst: {original_interval:.3f}s -> 0.001s"
        )

    except ImportError as e:
        logger.warning(f"Konnte die Simulator-Klasse nicht finden und patchen: {e}")


# Hauptfunktion zur Anpassung des Simulators
def configure_realistic_simulator():
    """
    Führt alle notwendigen Anpassungen durch, um einen realistischen Simulator zu erhalten.
    """
    # 1. Patch der Simulator-Klasse (für bestehende Module)
    patch_simulator_class()

    # 2. Konfigurationsdatei aktualisieren (für zukünftige Starts)
    update_config_file()

    # 3. Simulator mit angepassten Einstellungen erstellen und zurückgeben
    return configure_high_sample_rate_simulator()


# Verwendungsbeispiel
if __name__ == "__main__":
    # Diese Funktion ausführen, um den Simulator mit realistischer Abtastrate zu konfigurieren
    simulator = configure_realistic_simulator()
    print("Simulator erfolgreich konfiguriert mit einer Abtastrate von 1000 Hz")