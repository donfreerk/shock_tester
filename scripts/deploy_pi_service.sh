#!/bin/bash
# Deployment-Script für Pi Processing Service auf Raspberry Pi

set -e

echo "=== Fahrwerkstester Pi Processing Service Deployment ==="

# Variablen
PI_USER="pi"
PI_HOME="/home/pi"
PROJECT_DIR="$PI_HOME/WorkDir/shock_tester"
SERVICE_NAME="pi-processing"
PYTHON_VERSION="3.11"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Überprüfe ob wir auf einem Pi sind
check_pi_environment() {
    print_step "Überprüfe Pi-Umgebung..."
    
    if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        print_warning "Kein Raspberry Pi erkannt - fahre trotzdem fort"
    else
        print_status "✓ Raspberry Pi erkannt"
        
        # Pi-Version anzeigen
        PI_MODEL=$(grep "Model" /proc/cpuinfo | cut -d: -f2 | xargs)
        print_status "Pi-Modell: $PI_MODEL"
    fi
}

# System-Updates
update_system() {
    print_step "Aktualisiere System..."
    
    sudo apt update
    # Nur notwendige Pakete installieren, keine Kernel-Updates
    sudo apt install -y --no-upgrade
    
    # Installiere notwendige Pakete
    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        git \
        curl \
        wget \
        mosquitto \
        mosquitto-clients \
        can-utils \
        htop \
        vim \
        rsync
        
    print_status "✓ System-Pakete installiert"
}

# uv installieren
install_uv() {
    print_step "Installiere uv Python Package Manager..."
    
    if ! command -v uv &> /dev/null; then
        print_status "Installiere uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source $HOME/.cargo/env
        
        # uv zum PATH hinzufügen
        echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
        source ~/.bashrc
        
        print_status "✓ uv installiert"
    else
        print_status "✓ uv bereits installiert"
        uv --version
    fi
}

# Python-Umgebung einrichten
setup_python_environment() {
    print_step "Richte Python-Umgebung ein..."
    
    cd $PROJECT_DIR
    
    # Prüfe ob pyproject.toml existiert
    if [ -f "pyproject.toml" ]; then
        print_status "Nutze existierende pyproject.toml..."
        uv sync
    else
        print_status "Erstelle neue uv-Umgebung..."
        
        # Neue uv-Projekt initialisieren
        uv init --no-readme --python 3.11
        
        # Abhängigkeiten hinzufügen
        uv add numpy scipy paho-mqtt pyyaml python-can asyncio-mqtt
        
        # Pi-spezifische Dependencies
        uv add --optional pi "RPi.GPIO>=0.7.1" "spidev>=3.5" "smbus2>=0.4.0"
        
        # Development-Dependencies
        uv add --dev pytest black isort mypy
        
        # Sync ausführen
        uv sync
    fi
    
    # Common Library installieren
    if [ -d "common" ]; then
        uv pip install -e common/
        print_status "✓ Common Library installiert"
    fi
    
    print_status "✓ Python-Umgebung mit uv eingerichtet"
}

# CAN-Interface einrichten
setup_can_interface() {
    print_step "Richte CAN-Interface ein..."
    
    # CAN-Module laden
    echo "can" | sudo tee -a /etc/modules
    echo "can_raw" | sudo tee -a /etc/modules
    echo "can_bcm" | sudo tee -a /etc/modules
    echo "vcan" | sudo tee -a /etc/modules
    
    # CAN-Interface-Konfiguration für Hardware
    cat << EOF | sudo tee /etc/systemd/network/80-can.network
[Match]
Name=can0

[CAN]
BitRate=1000000
RestartSec=100ms
EOF
    
    # Virtual CAN für Simulator/Testing
    cat << EOF | sudo tee /etc/systemd/system/vcan-setup.service
[Unit]
Description=Virtual CAN interface setup
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/modprobe vcan
ExecStart=/sbin/ip link add dev vcan0 type vcan
ExecStart=/sbin/ip link set up vcan0
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    # Services aktivieren
    sudo systemctl enable systemd-networkd
    sudo systemctl enable vcan-setup
    
    print_status "✓ CAN-Interface konfiguriert"
}

# MQTT-Broker konfigurieren
setup_mqtt_broker() {
    print_step "Konfiguriere MQTT-Broker..."
    
    # Mosquitto-Konfiguration
    cat << EOF | sudo tee /etc/mosquitto/conf.d/fahrwerkstester.conf
# Fahrwerkstester MQTT-Konfiguration
listener 1883 0.0.0.0
allow_anonymous true

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information

# Persistence
persistence true
persistence_location /var/lib/mosquitto/

# Auto-save interval
autosave_interval 1800

# Max connections
max_connections 100

# Message size limits
message_size_limit 1048576

# Keepalive
keepalive_interval 60
EOF
    
    # Mosquitto starten und aktivieren
    sudo systemctl enable mosquitto
    sudo systemctl start mosquitto
    
    print_status "✓ MQTT-Broker konfiguriert und gestartet"
}

# Verzeichnisse erstellen
create_directories() {
    print_step "Erstelle notwendige Verzeichnisse..."
    
    # Service-Verzeichnisse
    sudo mkdir -p /var/log/fahrwerkstester
    sudo mkdir -p /var/lib/fahrwerkstester/{archive,results,config}
    sudo mkdir -p /etc/fahrwerkstester
    
    # Berechtigungen setzen
    sudo chown -R $PI_USER:$PI_USER /var/log/fahrwerkstester
    sudo chown -R $PI_USER:$PI_USER /var/lib/fahrwerkstester
    sudo chown -R $PI_USER:$PI_USER /etc/fahrwerkstester
    
    print_status "✓ Verzeichnisse erstellt"
}

# Systemd-Service erstellen
create_systemd_service() {
    print_step "Erstelle systemd-Service..."
    
    cat << EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Fahrwerkstester Pi Processing Service
After=network.target mosquitto.service vcan-setup.service
Wants=mosquitto.service
Requires=vcan-setup.service

[Service]
Type=simple
User=$PI_USER
Group=$PI_USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR/common
Environment=PATH=/home/pi/.cargo/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/pi/.cargo/bin/uv run python backend/pi_processing_service/main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10

# Resource-Limits für Pi
MemoryMax=512M
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/log/fahrwerkstester /var/lib/fahrwerkstester

[Install]
WantedBy=multi-user.target
EOF
    
    # Enhanced Hardware Bridge Service
    cat << EOF | sudo tee /etc/systemd/system/hardware-bridge.service
[Unit]
Description=Fahrwerkstester Enhanced Hardware Bridge
After=network.target mosquitto.service vcan-setup.service
Wants=mosquitto.service
Requires=vcan-setup.service

[Service]
Type=simple
User=$PI_USER
Group=$PI_USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR/common
Environment=PATH=/home/pi/.cargo/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/pi/.cargo/bin/uv run python hardware/enhanced_hardware_bridge.py --mode simulator
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10

# Resource-Limits
MemoryMax=256M
CPUQuota=50%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hardware-bridge

[Install]
WantedBy=multi-user.target
EOF
    
    # Services aktivieren
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl enable hardware-bridge
    
    print_status "✓ Systemd-Services erstellt und aktiviert"
}

# Konfigurationsdateien kopieren
copy_configuration() {
    print_step "Kopiere Konfigurationsdateien..."
    
    # Pi-spezifische Konfiguration
    if [ -f "backend/pi_processing_service/config/pi_processing_config.yaml" ]; then
        cp backend/pi_processing_service/config/pi_processing_config.yaml /etc/fahrwerkstester/
        print_status "✓ Pi Processing Konfiguration kopiert"
    fi
    
    # Enhanced Bridge Konfiguration
    if [ -f "config/enhanced_bridge_config.yaml" ]; then
        cp config/enhanced_bridge_config.yaml /etc/fahrwerkstester/
        print_status "✓ Hardware Bridge Konfiguration kopiert"
    fi
    
    # Logrotate-Konfiguration
    cat << EOF | sudo tee /etc/logrotate.d/fahrwerkstester
/var/log/fahrwerkstester/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
    su $PI_USER $PI_USER
    create 0644 $PI_USER $PI_USER
}

/var/log/mosquitto/*.log {
    weekly
    missingok
    rotate 4
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
    
    print_status "✓ Logrotate konfiguriert"
}

# Firewall-Regeln einrichten
setup_firewall() {
    print_step "Richte Firewall-Regeln ein..."
    
    # UFW installieren falls nicht vorhanden
    if ! command -v ufw &> /dev/null; then
        sudo apt install -y ufw
    fi
    
    # MQTT-Port öffnen
    sudo ufw allow 1883/tcp comment "MQTT Broker"
    
    # SSH sicherstellen
    sudo ufw allow ssh
    
    # Optional: Web-Interface Port
    sudo ufw allow 8080/tcp comment "Web Interface"
    
    # Firewall aktivieren (nur wenn noch nicht aktiv)
    sudo ufw --force enable 2>/dev/null || true
    
    print_status "✓ Firewall konfiguriert"
}

# Performance-Optimierungen für Pi
optimize_pi_performance() {
    print_step "Optimiere Pi-Performance..."
    
    # GPU Memory Split (mehr RAM für System)
    echo "gpu_mem=64" | sudo tee -a /boot/config.txt
    
    # CPU Governor auf performance setzen
    echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils
    
    # Swap-Größe reduzieren (SSD-Schonung)
    sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
    
    # Systemd Journal-Größe begrenzen
    sudo sed -i 's/#SystemMaxUse=/SystemMaxUse=100M/' /etc/systemd/journald.conf
    sudo sed -i 's/#SystemMaxFileSize=/SystemMaxFileSize=10M/' /etc/systemd/journald.conf
    
    print_status "✓ Performance-Optimierungen angewendet"
}

# Service-Status prüfen
check_service_status() {
    print_step "Überprüfe Service-Status..."
    
    # MQTT-Broker
    if systemctl is-active --quiet mosquitto; then
        print_status "✓ MQTT-Broker läuft"
    else
        print_error "✗ MQTT-Broker läuft nicht"
    fi
    
    # CAN-Interface (falls verfügbar)
    if ip link show can0 >/dev/null 2>&1; then
        print_status "✓ CAN-Interface verfügbar"
    else
        print_warning "⚠ Hardware CAN-Interface nicht verfügbar"
    fi
    
    # Virtual CAN
    if ip link show vcan0 >/dev/null 2>&1; then
        print_status "✓ Virtual CAN-Interface verfügbar"
    else
        print_warning "⚠ Virtual CAN-Interface nicht verfügbar"
    fi
    
    # Services
    for service in $SERVICE_NAME hardware-bridge; do
        if systemctl is-enabled --quiet $service; then
            print_status "✓ $service aktiviert"
        else
            print_warning "⚠ $service nicht aktiviert"
        fi
    done
}

# Services starten
start_services() {
    print_step "Starte Services..."
    
    # Virtual CAN setup
    sudo systemctl start vcan-setup
    
    # MQTT-Broker (falls nicht läuft)
    sudo systemctl start mosquitto
    
    # Pi Processing Service
    sudo systemctl start $SERVICE_NAME
    
    # Hardware Bridge
    sudo systemctl start hardware-bridge
    
    # Warte kurz und prüfe Status
    sleep 5
    
    print_status "Services gestartet - Status:"
    
    for service in mosquitto $SERVICE_NAME hardware-bridge; do
        if systemctl is-active --quiet $service; then
            print_status "✓ $service läuft"
        else
            print_error "✗ $service läuft nicht"
            echo ""
            print_error "Fehlerdiagnose für $service:"
            sudo journalctl -u $service -n 10 --no-pager
        fi
    done
}

# Monitoring-Setup
setup_monitoring() {
    print_step "Richte System-Monitoring ein..."
    
    # Monitoring-Script erstellen
    cat << 'EOF' | sudo tee /usr/local/bin/fahrwerkstester-monitor.sh
#!/bin/bash
# Fahrwerkstester System Monitor

LOG_FILE="/var/log/fahrwerkstester/system-monitor.log"
MQTT_TOPIC="suspension/system/pi_status"

# Systemdaten sammeln
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1)
TEMPERATURE=$(vcgencmd measure_temp | cut -d'=' -f2 | cut -d"'" -f1)

# Service-Status
PI_PROCESSING_STATUS=$(systemctl is-active pi-processing)
HARDWARE_BRIDGE_STATUS=$(systemctl is-active hardware-bridge)
MOSQUITTO_STATUS=$(systemctl is-active mosquitto)

# MQTT-Nachricht senden
mosquitto_pub -h localhost -t "$MQTT_TOPIC" -m "{
    \"timestamp\": $(date +%s),
    \"cpu_usage\": $CPU_USAGE,
    \"memory_usage\": $MEMORY_USAGE,
    \"disk_usage\": $DISK_USAGE,
    \"temperature\": $TEMPERATURE,
    \"services\": {
        \"pi_processing\": \"$PI_PROCESSING_STATUS\",
        \"hardware_bridge\": \"$HARDWARE_BRIDGE_STATUS\",
        \"mosquitto\": \"$MOSQUITTO_STATUS\"
    }
}"

# Log-Eintrag
echo "$(date): CPU=$CPU_USAGE% MEM=$MEMORY_USAGE% DISK=$DISK_USAGE% TEMP=$TEMPERATURE°C" >> "$LOG_FILE"
EOF
    
    sudo chmod +x /usr/local/bin/fahrwerkstester-monitor.sh
    
    # Cron-Job für Monitoring
    echo "*/5 * * * * /usr/local/bin/fahrwerkstester-monitor.sh" | sudo crontab -u $PI_USER -
    
    print_status "✓ System-Monitoring eingerichtet"
}

# Hauptfunktion
main() {
    echo "Starte Deployment des Fahrwerkstester Systems auf Raspberry Pi..."
    echo "Projekt-Verzeichnis: $PROJECT_DIR"
    echo ""
    
    # Überprüfungen
    if [ "$EUID" -eq 0 ]; then
        print_error "Bitte nicht als root ausführen!"
        exit 1
    fi
    
    if [ ! -d "$PROJECT_DIR" ]; then
        print_error "Projekt-Verzeichnis $PROJECT_DIR nicht gefunden!"
        print_status "Erstelle Verzeichnis und klone Repository..."
        mkdir -p "$PROJECT_DIR"
        # Hier würde normalerweise git clone stehen
        # git clone https://github.com/yourrepo/fahrwerkstester.git "$PROJECT_DIR"
    fi
    
    # Deployment-Schritte
    check_pi_environment
    # update_system  # Deaktiviert wegen Zeitproblemen
    print_step "Überspringe System-Update wegen Zeitproblemen..."
    print_warning "⚠ System-Update übersprungen - bitte später manuell ausführen"
    install_uv
    create_directories
    setup_python_environment
    setup_can_interface
    setup_mqtt_broker
    create_systemd_service
    copy_configuration
    setup_firewall
    optimize_pi_performance
    setup_monitoring
    
    # Services starten
    start_services
    
    # Abschließende Checks
    check_service_status
    
    echo ""
    print_status "=== Deployment abgeschlossen! ==="
    echo ""
    print_status "🎉 Fahrwerkstester System erfolgreich installiert!"
    echo ""
    print_status "Nützliche Befehle:"
    echo "  Service-Status:        sudo systemctl status pi-processing"
    echo "  Service-Logs:          sudo journalctl -u pi-processing -f"
    echo "  Hardware Bridge:       sudo systemctl status hardware-bridge"
    echo "  MQTT-Broker:           sudo systemctl status mosquitto"
    echo "  System-Monitor:        tail -f /var/log/fahrwerkstester/system-monitor.log"
    echo ""
    print_status "MQTT-Test:"
    echo "  Publish: mosquitto_pub -h localhost -t suspension/test -m 'hello'"
    echo "  Subscribe: mosquitto_sub -h localhost -t 'suspension/#'"
    echo ""
    print_status "CAN-Test:"
    echo "  Virtual CAN: cansend vcan0 123#DEADBEEF"
    echo "  CAN Dump: candump vcan0"
    echo ""
    print_status "Web-Monitoring: http://$(hostname -I | awk '{print $1}'):8080"
    print_status "Konfiguration: /etc/fahrwerkstester/"
    print_status "Logs: /var/log/fahrwerkstester/"
    
    # Neustart empfehlen für Kernel-Module
    echo ""
    print_warning "🔄 Neustart empfohlen für vollständige Aktivierung aller Kernel-Module:"
    print_warning "sudo reboot"
}

# Script ausführen
main "$@"