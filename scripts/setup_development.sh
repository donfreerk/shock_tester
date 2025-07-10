#!/bin/bash
# Setup-Script für Fahrwerkstester Entwicklungsumgebung
# Richtet die komplette Entwicklungsumgebung auf Windows/Linux/macOS ein

set -e

# Konfiguration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Farben
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# System-Erkennung
detect_system() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        SYSTEM="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        SYSTEM="macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        SYSTEM="windows"
    else
        SYSTEM="unknown"
    fi
    
    print_status "Erkanntes System: $SYSTEM"
}

# uv installieren
install_uv() {
    print_step "Installiere uv Python Package Manager..."
    
    if command -v uv &> /dev/null; then
        print_status "✓ uv bereits installiert"
        uv --version
        return 0
    fi
    
    case $SYSTEM in
        linux|macos)
            curl -LsSf https://astral.sh/uv/install.sh | sh
            source $HOME/.cargo/env
            ;;
        windows)
            powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
            ;;
        *)
            print_error "Unbekanntes System - bitte uv manuell installieren"
            exit 1
            ;;
    esac
    
    print_status "✓ uv installiert"
}

# Python-Umgebung einrichten
setup_python_environment() {
    print_step "Richte Python-Umgebung ein..."
    
    cd "$PROJECT_DIR"
    
    # uv Projekt initialisieren falls nötig
    if [ ! -f "pyproject.toml" ]; then
        print_status "Initialisiere uv-Projekt..."
        uv init --no-readme --python 3.8
    fi
    
    # Dependencies installieren
    print_status "Installiere Dependencies..."
    uv sync
    
    # Development Dependencies
    print_status "Installiere Development Dependencies..."
    uv add --dev pytest pytest-asyncio pytest-cov black isort mypy flake8 pre-commit
    
    # GUI Dependencies (falls System unterstützt)
    if [ "$SYSTEM" != "linux" ] || [ -n "$DISPLAY" ]; then
        print_status "Installiere GUI Dependencies..."
        uv add --optional gui matplotlib pillow
    fi
    
    # Common Library als editable installieren
    if [ -d "common" ]; then
        print_status "Installiere Common Library..."
        uv pip install -e common/
    fi
    
    print_status "✓ Python-Umgebung eingerichtet"
}

# MQTT-Broker installieren (für lokale Entwicklung)
install_mqtt_broker() {
    print_step "Installiere MQTT-Broker für lokale Entwicklung..."
    
    case $SYSTEM in
        linux)
            if command -v apt &> /dev/null; then
                sudo apt update
                sudo apt install -y mosquitto mosquitto-clients
            elif command -v yum &> /dev/null; then
                sudo yum install -y mosquitto mosquitto-clients
            elif command -v pacman &> /dev/null; then
                sudo pacman -S mosquitto
            else
                print_warning "Unbekannter Package Manager - bitte Mosquitto manuell installieren"
            fi
            ;;
        macos)
            if command -v brew &> /dev/null; then
                brew install mosquitto
            else
                print_warning "Homebrew nicht gefunden - bitte Mosquitto manuell installieren"
            fi
            ;;
        windows)
            print_warning "Windows: Bitte Mosquitto von https://mosquitto.org/download/ herunterladen"
            ;;
    esac
    
    print_status "✓ MQTT-Broker installiert"
}

# CAN-Utils installieren (Linux)
install_can_utils() {
    if [ "$SYSTEM" != "linux" ]; then
        print_warning "CAN-Utils nur unter Linux verfügbar"
        return 0
    fi
    
    print_step "Installiere CAN-Utils..."
    
    if command -v apt &> /dev/null; then
        sudo apt install -y can-utils
    elif command -v yum &> /dev/null; then
        sudo yum install -y can-utils
    elif command -v pacman &> /dev/null; then
        sudo pacman -S can-utils
    fi
    
    # Virtual CAN einrichten
    print_status "Richte Virtual CAN ein..."
    
    # Module laden (falls noch nicht geladen)
    sudo modprobe vcan 2>/dev/null || true
    
    # Virtual CAN Interface erstellen
    if ! ip link show vcan0 >/dev/null 2>&1; then
        sudo ip link add dev vcan0 type vcan
        sudo ip link set up vcan0
        print_status "✓ Virtual CAN Interface (vcan0) erstellt"
    else
        print_status "✓ Virtual CAN Interface bereits vorhanden"
    fi
}

# Git Hooks einrichten
setup_git_hooks() {
    print_step "Richte Git Hooks ein..."
    
    cd "$PROJECT_DIR"
    
    # Pre-commit installieren
    if command -v uv &> /dev/null; then
        uv run pre-commit install
        print_status "✓ Pre-commit hooks installiert"
    fi
    
    # Git-Konfiguration für bessere Python-Entwicklung
    git config --local core.autocrlf input
    git config --local pull.rebase false
    
    print_status "✓ Git-Konfiguration angepasst"
}

# Development-Konfiguration erstellen
create_dev_config() {
    print_step "Erstelle Development-Konfiguration..."
    
    cd "$PROJECT_DIR"
    
    # Development-Config für Pi Processing Service
    mkdir -p config/development
    cat << EOF > config/development/pi_processing_config.yaml
# Development-Konfiguration für Pi Processing Service

mqtt:
  broker: "localhost"
  port: 1883
  username: ""
  password: ""

processing:
  heartbeat_interval: 10.0  # Häufiger für Development
  phase_shift:
    min_calc_freq: 6.0
    max_calc_freq: 18.0
    phase_threshold: 35.0

logging:
  level: "DEBUG"
  log_to_file: true
  log_file: "logs/pi_processing_dev.log"

hardware:
  use_multiprocessing: false
  max_workers: 1

service:
  name: "pi_processing_service_dev"
  description: "Pi Processing Service - Development"
EOF
    
    # Enhanced Bridge Config
    cat << EOF > config/development/enhanced_bridge_config.yaml
# Development-Konfiguration für Enhanced Hardware Bridge

hardware_bridge:
  mode: "simulator"  # Simulator für Development
  buffer_size: 1000
  auto_save_interval: 10.0

mqtt:
  broker: "localhost"
  port: 1883

can:
  simulator:
    interface: "vcan0"
    baudrate: 1000000
    protocol: "eusama"

logging:
  level: "DEBUG"
  log_file: "logs/hardware_bridge_dev.log"
EOF
    
    # GUI Config
    cat << EOF > config/development/gui_config.yaml
# Development-Konfiguration für GUI

mqtt:
  broker: "localhost"
  port: 1883

gui:
  update_interval: 50  # Schnellere Updates für Development
  max_history: 100
  debug_mode: true

logging:
  level: "DEBUG"
EOF
    
    print_status "✓ Development-Konfiguration erstellt"
}

# VS Code Konfiguration
setup_vscode() {
    print_step "Richte VS Code Konfiguration ein..."
    
    cd "$PROJECT_DIR"
    
    mkdir -p .vscode
    
    # Settings
    cat << EOF > .vscode/settings.json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.analysis.extraPaths": ["./common"],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile", "black"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".mypy_cache": true,
        ".pytest_cache": true,
        "htmlcov": true
    }
}
EOF
    
    # Launch Configuration
    cat << EOF > .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Pi Processing Service",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/backend/pi_processing_service/main.py",
            "console": "integratedTerminal",
            "cwd": "\${workspaceFolder}",
            "env": {
                "PYTHONPATH": "\${workspaceFolder}/common"
            },
            "args": ["--debug"]
        },
        {
            "name": "Hardware Bridge",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/hardware/enhanced_hardware_bridge.py",
            "console": "integratedTerminal",
            "cwd": "\${workspaceFolder}",
            "env": {
                "PYTHONPATH": "\${workspaceFolder}/common"
            },
            "args": ["--mode", "simulator", "--debug"]
        },
        {
            "name": "Simplified GUI",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/frontend/desktop_gui/simplified_gui.py",
            "console": "integratedTerminal",
            "cwd": "\${workspaceFolder}",
            "env": {
                "PYTHONPATH": "\${workspaceFolder}/common"
            },
            "args": ["--debug"]
        },
        {
            "name": "CAN Simulator",
            "type": "python",
            "request": "launch",
            "program": "\${workspaceFolder}/backend/can_simulator_service/main.py",
            "console": "integratedTerminal",
            "cwd": "\${workspaceFolder}",
            "env": {
                "PYTHONPATH": "\${workspaceFolder}/common"
            },
            "args": ["--debug"]
        }
    ]
}
EOF
    
    # Tasks
    cat << EOF > .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Run Tests",
            "type": "shell",
            "command": "uv run pytest",
            "group": "test",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        },
        {
            "label": "Format Code",
            "type": "shell",
            "command": "uv run black .",
            "group": "build"
        },
        {
            "label": "Lint Code",
            "type": "shell",
            "command": "uv run flake8 .",
            "group": "build"
        },
        {
            "label": "Start Development Environment",
            "type": "shell",
            "command": "./scripts/start_system.sh development",
            "group": "build",
            "isBackground": true
        }
    ]
}
EOF
    
    print_status "✓ VS Code Konfiguration erstellt"
}

# Test-Verzeichnis einrichten
setup_test_environment() {
    print_step "Richte Test-Umgebung ein..."
    
    cd "$PROJECT_DIR"
    
    # Test-Verzeichnisse erstellen
    mkdir -p tests/{unit,integration,e2e}
    mkdir -p tests/fixtures
    
    # Basis Test-Konfiguration
    cat << EOF > tests/conftest.py
"""
Pytest-Konfiguration für Fahrwerkstester Tests
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path

# Test-Fixtures
@pytest.fixture
def temp_config_dir():
    """Temporäres Verzeichnis für Test-Konfigurationen"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def mock_mqtt_broker():
    """Mock MQTT-Broker für Tests"""
    # Hier würde eine Mock-MQTT-Implementierung stehen
    pass

@pytest.fixture
def sample_test_data():
    """Beispiel-Testdaten für Phase-Shift-Tests"""
    import numpy as np
    
    # Generiere Beispieldaten
    time_data = np.linspace(0, 30, 3000)  # 30s, 100Hz
    platform_data = 3.0 * np.sin(2 * np.pi * 10 * time_data)  # 10Hz, 3mm Amplitude
    force_data = 500 + 100 * np.sin(2 * np.pi * 10 * time_data + np.pi/4)  # 45° Phase-Shift
    
    return {
        "time": time_data,
        "platform_position": platform_data,
        "tire_force": force_data,
        "static_weight": 500.0
    }

# Async Test Support
@pytest.fixture(scope="session")
def event_loop():
    """Event loop für async Tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
EOF
    
    # Beispiel Unit-Test
    cat << EOF > tests/unit/test_phase_shift_calculator.py
"""
Unit-Tests für Phase-Shift-Calculator
"""
import pytest
import numpy as np
from backend.pi_processing_service.processing.phase_shift_calculator import PhaseShiftCalculator

class TestPhaseShiftCalculator:
    """Test-Klasse für PhaseShiftCalculator"""
    
    def setup_method(self):
        """Setup für jeden Test"""
        self.calculator = PhaseShiftCalculator()
    
    @pytest.mark.asyncio
    async def test_calculate_with_good_damping(self, sample_test_data):
        """Test mit guter Dämpfung (45° Phase-Shift)"""
        result = await self.calculator.calculate(
            platform_data=sample_test_data["platform_position"],
            force_data=sample_test_data["tire_force"],
            time_data=sample_test_data["time"],
            static_weight=sample_test_data["static_weight"]
        )
        
        assert result["success"] is True
        assert result["min_phase_shift"] is not None
        assert abs(result["min_phase_shift"]) >= 35.0  # EGEA-Kriterium
        assert result["evaluation"] in ["good", "excellent"]
    
    def test_input_validation(self):
        """Test Input-Validierung"""
        # Leere Arrays sollten Fehler werfen
        platform_empty = np.array([])
        force_empty = np.array([])
        time_empty = np.array([])
        
        is_valid = self.calculator._validate_input_data(
            platform_empty, force_empty, time_empty, 500.0
        )
        
        assert is_valid is False
EOF
    
    print_status "✓ Test-Umgebung eingerichtet"
}

# Dokumentation generieren
setup_documentation() {
    print_step "Richte Dokumentation ein..."
    
    cd "$PROJECT_DIR"
    
    # README für Development
    cat << EOF > README_DEVELOPMENT.md
# Fahrwerkstester - Development Setup

## Quick Start

\`\`\`bash
# Setup ausführen
./scripts/setup_development.sh

# Entwicklungsumgebung starten
./scripts/start_system.sh development

# Tests ausführen
uv run pytest

# Code formatieren
uv run black .
uv run isort .
\`\`\`

## Entwicklung

### Architektur

- **backend/pi_processing_service/**: Post-Processing auf dem Pi
- **hardware/enhanced_hardware_bridge.py**: CAN ↔ MQTT Bridge
- **frontend/desktop_gui/simplified_gui.py**: Vereinfachte GUI
- **common/suspension_core/**: Gemeinsame Bibliotheken

### Debugging

#### VS Code
1. Öffne das Projekt in VS Code
2. Wähle Python-Interpreter: \`.venv/bin/python\`
3. Starte Services über Debug-Konfiguration

#### Logs
- **Pi Processing**: \`logs/pi_processing.log\`
- **Hardware Bridge**: \`logs/hardware_bridge.log\`
- **GUI**: \`logs/gui.log\`

#### MQTT-Monitoring
\`\`\`bash
# Alle Topics überwachen
mosquitto_sub -h localhost -t 'suspension/#'

# Test-Nachricht senden
mosquitto_pub -h localhost -t 'suspension/test' -m 'hello'
\`\`\`

### Testing

\`\`\`bash
# Alle Tests
uv run pytest

# Unit Tests
uv run pytest tests/unit/

# Integration Tests
uv run pytest tests/integration/

# Mit Coverage
uv run pytest --cov
\`\`\`

### Code Quality

\`\`\`bash
# Formatierung
uv run black .
uv run isort .

# Linting
uv run flake8 .
uv run mypy .

# Pre-commit Hooks
uv run pre-commit run --all-files
\`\`\`
EOF
    
    print_status "✓ Dokumentation erstellt"
}

# Hauptfunktion
main() {
    echo "🚀 Fahrwerkstester Development Setup"
    echo "==================================="
    echo ""
    
    detect_system
    
    print_status "Starte Setup für $SYSTEM..."
    echo ""
    
    # Setup-Schritte
    install_uv
    setup_python_environment
    install_mqtt_broker
    install_can_utils
    setup_git_hooks
    create_dev_config
    setup_vscode
    setup_test_environment
    setup_documentation
    
    echo ""
    print_status "🎉 Development-Setup abgeschlossen!"
    echo ""
    print_status "Nächste Schritte:"
    echo "  1. ./scripts/start_system.sh development"
    echo "  2. Öffne http://localhost:1883 für MQTT"
    echo "  3. Tests ausführen: uv run pytest"
    echo ""
    print_status "Entwicklung:"
    echo "  - VS Code öffnen und Python-Interpreter wählen"
    echo "  - Debug-Konfigurationen verwenden"
    echo "  - Pre-commit hooks sind aktiv"
    echo ""
    print_status "Dokumentation: README_DEVELOPMENT.md"
}

# Script ausführen
main "$@"
