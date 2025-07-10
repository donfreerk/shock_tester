#!/bin/bash
# Haupt-Start-Script für Fahrwerkstester System
# Startet alle Komponenten in der richtigen Reihenfolge

set -e

# Konfiguration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_CMD="uv run python"

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

# PID-Tracking für Services
PIDS=()
SERVICE_NAMES=()

cleanup() {
    print_status "Beende alle Services..."
    for i in "${!PIDS[@]}"; do
        if kill -0 "${PIDS[$i]}" 2>/dev/null; then
            print_status "Beende ${SERVICE_NAMES[$i]} (PID: ${PIDS[$i]})"
            kill "${PIDS[$i]}" 2>/dev/null || true
        fi
    done
    exit 0
}

# Signal-Handler für graceful shutdown
trap cleanup SIGINT SIGTERM

start_service() {
    local name="$1"
    local cmd="$2"
    local log_file="$3"
    
    print_step "Starte $name..."
    
    # Service im Hintergrund starten
    $cmd > "$log_file" 2>&1 &
    local pid=$!
    
    # PID und Name speichern
    PIDS+=($pid)
    SERVICE_NAMES+=("$name")
    
    # Kurz warten und prüfen ob Service läuft
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        print_status "✓ $name gestartet (PID: $pid)"
        return 0
    else
        print_error "✗ $name konnte nicht gestartet werden"
        print_error "Log: $log_file"
        tail -10 "$log_file"
        return 1
    fi
}

wait_for_mqtt() {
    print_step "Warte auf MQTT-Broker..."
    
    for i in {1..30}; do
        if mosquitto_pub -h localhost -t test -m "test" 2>/dev/null; then
            print_status "✓ MQTT-Broker erreichbar"
            return 0
        fi
        sleep 1
    done
    
    print_error "MQTT-Broker nicht erreichbar"
    return 1
}

check_dependencies() {
    print_step "Überprüfe Abhängigkeiten..."
    
    # uv verfügbar?
    if ! command -v uv &> /dev/null; then
        print_error "uv nicht gefunden. Bitte installieren: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    # Python-Umgebung sync
    cd "$PROJECT_DIR"
    if [ -f "pyproject.toml" ]; then
        print_status "Synchronisiere Python-Umgebung..."
        uv sync
    fi
    
    # MQTT-Broker starten falls nötig
    if ! pgrep mosquitto > /dev/null; then
        print_status "Starte MQTT-Broker..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start mosquitto || mosquitto -d || print_warning "MQTT-Broker konnte nicht gestartet werden"
        else
            mosquitto -d || print_warning "MQTT-Broker konnte nicht gestartet werden"
        fi
    fi
    
    wait_for_mqtt
    
    print_status "✓ Abhängigkeiten überprüft"
}

show_usage() {
    echo "Verwendung: $0 [MODE] [OPTIONS]"
    echo ""
    echo "Modi:"
    echo "  development  - Entwicklungsumgebung (Simulator + GUI)"
    echo "  testing      - Test-Umgebung (Hardware + Simulator + GUI)"
    echo "  production   - Produktionsumgebung (nur Hardware + Processing)"
    echo "  simulator    - Nur Simulator-Komponenten"
    echo "  demo         - Demo-Modus mit vorgefertigten Daten"
    echo ""
    echo "Optionen:"
    echo "  --no-gui     - Startet ohne GUI"
    echo "  --debug      - Debug-Modus aktivieren"
    echo "  --help       - Diese Hilfe anzeigen"
    echo ""
    echo "Beispiele:"
    echo "  $0 development"
    echo "  $0 production --no-gui"
    echo "  $0 simulator --debug"
}

start_development_mode() {
    local no_gui="$1"
    local debug="$2"
    
    print_status "🔧 Starte Entwicklungsumgebung..."
    
    cd "$PROJECT_DIR"
    
    # Log-Verzeichnis erstellen
    mkdir -p logs
    
    # Debug-Flags setzen
    local debug_flags=""
    if [ "$debug" = "true" ]; then
        debug_flags="--debug"
    fi
    
    # 1. Pi Processing Service
    start_service "Pi Processing Service" \
        "$PYTHON_CMD backend/pi_processing_service/main.py $debug_flags" \
        "logs/pi_processing.log"
    
    # 2. Enhanced Hardware Bridge (Simulator-Modus)
    start_service "Hardware Bridge (Simulator)" \
        "$PYTHON_CMD hardware/enhanced_hardware_bridge.py --mode simulator $debug_flags" \
        "logs/hardware_bridge.log"
    
    # 3. CAN Simulator
    start_service "CAN Simulator" \
        "$PYTHON_CMD backend/can_simulator_service/main.py $debug_flags" \
        "logs/can_simulator.log"
    
    # 4. GUI (falls gewünscht)
    if [ "$no_gui" != "true" ]; then
        start_service "Simplified GUI" \
            "$PYTHON_CMD frontend/desktop_gui/simplified_gui.py $debug_flags" \
            "logs/gui.log"
    fi
    
    print_status "🎉 Entwicklungsumgebung gestartet!"
}

start_testing_mode() {
    local no_gui="$1"
    local debug="$2"
    
    print_status "🧪 Starte Test-Umgebung..."
    
    cd "$PROJECT_DIR"
    mkdir -p logs
    
    local debug_flags=""
    if [ "$debug" = "true" ]; then
        debug_flags="--debug"
    fi
    
    # 1. Pi Processing Service
    start_service "Pi Processing Service" \
        "$PYTHON_CMD backend/pi_processing_service/main.py $debug_flags" \
        "logs/pi_processing.log"
    
    # 2. Enhanced Hardware Bridge (Hybrid-Modus)
    start_service "Hardware Bridge (Hybrid)" \
        "$PYTHON_CMD hardware/enhanced_hardware_bridge.py --mode hybrid $debug_flags" \
        "logs/hardware_bridge.log"
    
    # 3. CAN Simulator für Vergleichstests
    start_service "CAN Simulator" \
        "$PYTHON_CMD backend/can_simulator_service/main.py $debug_flags" \
        "logs/can_simulator.log"
    
    # 4. GUI für Monitoring
    if [ "$no_gui" != "true" ]; then
        start_service "Simplified GUI" \
            "$PYTHON_CMD frontend/desktop_gui/simplified_gui.py $debug_flags" \
            "logs/gui.log"
    fi
    
    print_status "🧪 Test-Umgebung gestartet!"
}

start_production_mode() {
    local no_gui="$1"
    local debug="$2"
    
    print_status "🏭 Starte Produktionsumgebung..."
    
    cd "$PROJECT_DIR"
    mkdir -p logs
    
    local debug_flags=""
    if [ "$debug" = "true" ]; then
        debug_flags="--debug"
    fi
    
    # 1. Pi Processing Service
    start_service "Pi Processing Service" \
        "$PYTHON_CMD backend/pi_processing_service/main.py $debug_flags" \
        "logs/pi_processing.log"
    
    # 2. Enhanced Hardware Bridge (Hardware-Modus)
    start_service "Hardware Bridge (Hardware)" \
        "$PYTHON_CMD hardware/enhanced_hardware_bridge.py --mode hardware $debug_flags" \
        "logs/hardware_bridge.log"
    
    # 3. GUI nur für Monitoring (falls gewünscht)
    if [ "$no_gui" != "true" ]; then
        start_service "Monitor GUI" \
            "$PYTHON_CMD frontend/desktop_gui/simplified_gui.py $debug_flags" \
            "logs/gui.log"
    fi
    
    print_status "🏭 Produktionsumgebung gestartet!"
}

start_simulator_mode() {
    local no_gui="$1"
    local debug="$2"
    
    print_status "🎮 Starte Simulator-Modus..."
    
    cd "$PROJECT_DIR"
    mkdir -p logs
    
    local debug_flags=""
    if [ "$debug" = "true" ]; then
        debug_flags="--debug"
    fi
    
    # 1. CAN Simulator mit GUI
    start_service "CAN Simulator GUI" \
        "$PYTHON_CMD frontend/desktop_gui/simulator_gui.py $debug_flags" \
        "logs/simulator_gui.log"
    
    # 2. Pi Processing Service (für Demo)
    start_service "Pi Processing Service" \
        "$PYTHON_CMD backend/pi_processing_service/main.py $debug_flags" \
        "logs/pi_processing.log"
    
    # 3. Enhanced Hardware Bridge (Simulator-Modus)
    start_service "Hardware Bridge (Simulator)" \
        "$PYTHON_CMD hardware/enhanced_hardware_bridge.py --mode simulator $debug_flags" \
        "logs/hardware_bridge.log"
    
    print_status "🎮 Simulator-Modus gestartet!"
}

start_demo_mode() {
    local no_gui="$1"
    local debug="$2"
    
    print_status "🎪 Starte Demo-Modus..."
    
    cd "$PROJECT_DIR"
    mkdir -p logs
    
    local debug_flags=""
    if [ "$debug" = "true" ]; then
        debug_flags="--debug"
    fi
    
    # Demo-spezifische Konfiguration
    export DEMO_MODE=true
    export DEMO_DATA_PATH="$PROJECT_DIR/demo_data"
    
    # 1. Pi Processing Service (Demo-Daten)
    start_service "Pi Processing Service (Demo)" \
        "$PYTHON_CMD backend/pi_processing_service/main.py $debug_flags --demo" \
        "logs/pi_processing_demo.log"
    
    # 2. Demo-Simulator
    start_service "Demo Simulator" \
        "$PYTHON_CMD backend/can_simulator_service/main.py --demo $debug_flags" \
        "logs/demo_simulator.log"
    
    # 3. GUI mit Demo-Daten
    if [ "$no_gui" != "true" ]; then
        start_service "Demo GUI" \
            "$PYTHON_CMD frontend/desktop_gui/simplified_gui.py --demo $debug_flags" \
            "logs/demo_gui.log"
    fi
    
    print_status "🎪 Demo-Modus gestartet!"
}

monitor_services() {
    print_status "📊 Service-Monitoring gestartet..."
    print_status "Drücke Ctrl+C zum Beenden"
    print_status ""
    print_status "Aktive Services:"
    for i in "${!SERVICE_NAMES[@]}"; do
        echo "  ${SERVICE_NAMES[$i]} (PID: ${PIDS[$i]})"
    done
    print_status ""
    print_status "Logs verfügbar in: $PROJECT_DIR/logs/"
    print_status "MQTT-Monitor: mosquitto_sub -h localhost -t 'suspension/#'"
    print_status ""
    
    # Service-Status überwachen
    while true; do
        for i in "${!PIDS[@]}"; do
            if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
                print_error "Service ${SERVICE_NAMES[$i]} ist beendet! (PID: ${PIDS[$i]})"
                # Service aus Arrays entfernen
                unset PIDS[$i]
                unset SERVICE_NAMES[$i]
            fi
        done
        
        # Wenn keine Services mehr laufen, beenden
        if [ ${#PIDS[@]} -eq 0 ]; then
            print_error "Alle Services beendet"
            break
        fi
        
        sleep 10
    done
}

# Hauptlogik
main() {
    local mode="$1"
    local no_gui="false"
    local debug="false"
    
    # Parameter parsen
    shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-gui)
                no_gui="true"
                shift
                ;;
            --debug)
                debug="true"
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unbekannte Option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    echo "🎯 Fahrwerkstester System Starter"
    echo "================================="
    echo ""
    
    # Abhängigkeiten prüfen
    check_dependencies
    
    # Modus ausführen
    case "$mode" in
        development|dev)
            start_development_mode "$no_gui" "$debug"
            ;;
        testing|test)
            start_testing_mode "$no_gui" "$debug"
            ;;
        production|prod)
            start_production_mode "$no_gui" "$debug"
            ;;
        simulator|sim)
            start_simulator_mode "$no_gui" "$debug"
            ;;
        demo)
            start_demo_mode "$no_gui" "$debug"
            ;;
        "")
            print_error "Modus erforderlich"
            show_usage
            exit 1
            ;;
        *)
            print_error "Unbekannter Modus: $mode"
            show_usage
            exit 1
            ;;
    esac
    
    # Service-Monitoring
    monitor_services
}

# Script ausführen
main "$@"
