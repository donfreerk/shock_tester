#!/usr/bin/env python3
"""
Test-Skript für Import-Überprüfung
Angepasst für dev/tests/ Verzeichnis
"""

import sys
from pathlib import Path

# Project root zum Pfad hinzufügen (angepasst für dev/tests/ Pfad)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Test-Imports einzeln
test_imports = [
    "backend.can_simulator_service.core.egea_simulator",
    "common.suspension_core.mqtt.handler", 
    "common.suspension_core.config",  # Package mit ConfigManager
    "backend.can_simulator_service.mqtt.simulator_adapter",
]

print("🔍 Teste Import-Pfade einzeln...")
print("=" * 50)

failed_imports = []

for module_path in test_imports:
    try:
        module = __import__(module_path, fromlist=[''])
        print(f"✅ {module_path} OK")
        
        # Für simulator_adapter auch die Klasse testen
        if module_path == "backend.can_simulator_service.mqtt.simulator_adapter":
            try:
                from backend.can_simulator_service.mqtt.simulator_adapter import SimulatorMqttAdapter
                print(f"✅ SimulatorMqttAdapter Klasse gefunden")
            except ImportError as class_error:
                print(f"❌ SimulatorMqttAdapter Klasse FEHLER: {class_error}")
                failed_imports.append((f"{module_path}.SimulatorMqttAdapter", str(class_error)))
        
    except ImportError as e:
        failed_imports.append((module_path, str(e)))
        print(f"❌ {module_path} FEHLER: {e}")

print("=" * 50)

# Zusätzlich: Teste die spezifischen Imports aus command_controlled_main.py
print("\n🔍 Teste spezifische Klassen-Imports...")
specific_imports = [
    ("backend.can_simulator_service.core.egea_simulator", "EGEASimulator"),
    ("backend.can_simulator_service.mqtt.simulator_adapter", "SimulatorMqttAdapter"),
    ("common.suspension_core.mqtt.handler", "MqttHandler"),
    ("common.suspension_core.config", "ConfigManager"),  # Aus config package
]

for module_path, class_name in specific_imports:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        print(f"✅ {class_name} aus {module_path}")
    except ImportError as e:
        print(f"❌ Import-Fehler {module_path}.{class_name}: {e}")
        failed_imports.append((f"{module_path}.{class_name}", str(e)))
    except AttributeError as e:
        print(f"❌ Klasse {class_name} nicht gefunden in {module_path}: {e}")
        failed_imports.append((f"{module_path}.{class_name}", str(e)))

print("=" * 50)

if failed_imports:
    print(f"❌ {len(failed_imports)} Imports fehlgeschlagen")
    print("\nFehlgeschlagene Imports:")
    for import_name, error in failed_imports:
        print(f"  - {import_name}: {error}")
    
    print("\n🔧 Debugging-Informationen:")
    
    # Überprüfe Datei-Existenz
    files_to_check = [
        "backend/can_simulator_service/core/egea_simulator.py",
        "backend/can_simulator_service/mqtt/simulator_adapter.py", 
        "common/suspension_core/mqtt/handler.py",
        "common/suspension_core/config/manager.py",  # Korrekte Datei
    ]
    
    print("1. Datei-Existenz:")
    for file_path in files_to_check:
        exists = (project_root / file_path).exists()
        print(f"   {'✅' if exists else '❌'} {file_path}")
    
    # Überprüfe __init__.py Dateien
    init_files = [
        "backend/__init__.py",
        "backend/can_simulator_service/__init__.py",
        "backend/can_simulator_service/core/__init__.py",
        "backend/can_simulator_service/mqtt/__init__.py",
        "common/__init__.py",
        "common/suspension_core/__init__.py",
        "common/suspension_core/mqtt/__init__.py",
        "common/suspension_core/config/__init__.py",
    ]
    
    print("2. __init__.py Dateien:")
    for init_file in init_files:
        exists = (project_root / init_file).exists()
        print(f"   {'✅' if exists else '❌'} {init_file}")
    
    sys.exit(1)
else:
    print(f"✅ Alle Imports erfolgreich!")
    print("🚀 command_controlled_main.py sollte jetzt funktionieren")
