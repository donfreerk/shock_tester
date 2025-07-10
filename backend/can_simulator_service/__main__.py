# backend/can_simulator_service/__main__.py
"""
Ermöglicht die Ausführung des Simulator-Service als Python-Package

Verwendung:
    python -m backend.can_simulator_service
    python backend/can_simulator_service/

Weiterleitung zur main.py
"""

import sys
from pathlib import Path

# Project root zum Pfad hinzufügen
sys.path.append(str(Path(__file__).parent.parent.parent))

# Main-Funktion importieren und ausführen
if __name__ == "__main__":
	from backend.can_simulator_service.main import main
	import asyncio

	print("Starte EGEA-Simulator Service über Package-Import...")
	asyncio.run(main())