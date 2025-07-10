"""
Konfigurationserweiterung für den High-Level-Simulator und Hybrid-Simulator.

Diese Datei enthält zusätzliche Konfigurationsparameter für den High-Level-Simulator
und den Hybrid-Simulator des Fahrwerkstesters.
"""

# Konfiguration für den High-Level-Simulator
HIGH_LEVEL_SIMULATOR_CONFIG = {
    "ENABLE": False,  # Auf True setzen, um den High-Level-Simulator zu verwenden
    "SIMULATION_MODE": "hybrid",  # "high_level", "hybrid" oder "low_level"
    "GENERATE_LOW_LEVEL": True,  # Low-Level-CAN-Frames im Hybrid-Modus generieren
    "DAMPING_QUALITY": "good",  # "good", "marginal" oder "bad"
    "TEST_METHOD": "phase_shift",  # "phase_shift" oder "resonance"
    "VEHICLE_DEFAULTS": {
        "MAKE": "VW",
        "MODEL": "Golf",
        "YEAR": 2023,
        "TYPE": "M1",
        "SPRING_CONSTANT": 20000,  # N/m
        "DAMPING_CONSTANT": 1500,  # Ns/m
    },
    "PHASE_SHIFT": {
        "GOOD_RANGE": (40, 60),  # Grad
        "MARGINAL_RANGE": (33, 38),  # Grad
        "BAD_RANGE": (15, 30),  # Grad
    },
    "RESONANCE": {
        "GOOD_EFFECTIVENESS": (75, 95),  # %
        "MARGINAL_EFFECTIVENESS": (55, 70),  # %
        "BAD_EFFECTIVENESS": (30, 50),  # %
    },
    "AUTO_SIMULATE_VEHICLE": False,  # Automatisch ein Fahrzeug simulieren beim Start
    "AUTO_START_TEST": False,  # Automatisch einen Test starten, wenn ein Fahrzeug erkannt wird
}