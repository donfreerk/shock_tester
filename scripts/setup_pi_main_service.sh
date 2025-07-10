#!/bin/bash
"""
🚀 Setup-Script für Pi Main Service
Installiert und konfiguriert den Pi Main Service als systemd-Service
"""

set -e

# Konfiguration
SERVICE_NAME="fahrwerkstester-pi-main"
PROJECT_DIR="/home/pi/fahrwerkstester"
PI_USER="pi"
PYTHON_ENV="/home/pi/.cargo/bin/uv"

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

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Dieses Script muss als root ausgeführt werden"
        print_status "Verwendung: sudo $0"
        exit 1
    fi
}

setup_systemd_service() {
    print_step "Erstelle systemd-Service für Pi Main..."
    
    cat << EOF > /etc/systemd/system/${SERVICE_NAME}.service
[Unit]
Description=Fahrwerkstester Pi Main Service
Documentation=https://github.com/your-repo/fahrwerkstester
After=network.target multi-user.target
Wants=network.target

[Service]
Type=simple
User=$PI_USER
Group=$PI_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=/home/pi/.cargo/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=$PROJECT_DIR/common
Environment=PYTHONUNBUFFERED=1

# Hauptservice
ExecStart=$PYTHON_ENV run python pi_main.py
ExecReload=/bin/kill -HUP \$MAINPID

# Restart-Verhalten
Restart=always
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

# Resource-Limits für Pi
MemoryMax=1G
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/log/fahrwerkstester /var/lib/fahrwerkstester /tmp
ProtectHome=false

[Install]
WantedBy=multi-user.target
EOF
    
    print_status "✓ systemd-Service erstellt"
}

setup_logging() {
    print_step "Richte Logging ein..."
    
    # Log-Verzeichnisse erstellen
    mkdir -p /var/log/fahrwerkstester
    mkdir -p /var/lib/fahrwerkstester
    mkdir -p /etc/fahrwerkstester
    
    # Berechtigungen setzen
    chown -R $PI_USER:$PI_USER /var/log/fahrwerkstester
    chown -R $PI_USER:$PI_USER /var/lib/fahrwerkstester
    chown -R $PI_USER:$PI_USER /etc/fahrwerkstester
    
    # Logrotate-Konfiguration
    cat << EOF > /etc/logrotate.d/fahrwerkstester
/var/log/fahrwerkstester/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $PI_USER $PI_USER
    postrotate
        systemctl reload ${SERVICE_NAME} > /dev/null 2>&1 || true
    endscript
}
EOF
    
    print_status "✓ Logging eingerichtet"
}

setup_can_interface() {
    print_step "Konfiguriere CAN-Interface..."
    
    # CAN-Interface-Service
    cat << EOF > /etc/systemd/system/can-interface.service
[Unit]
Description=CAN Interface Setup
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'if [ -e /sys/class/net/can0 ]; then ip link set can0 up type can bitrate 500000; fi'
ExecStop=/bin/bash -c 'if [ -e /sys/class/net/can0 ]; then ip link set can0 down; fi'
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    # Für Development: vcan0 Setup
    cat << EOF > /etc/systemd/system/vcan-interface.service
[Unit]
Description=Virtual CAN Interface Setup
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'modprobe vcan && ip link add dev vcan0 type vcan && ip link set up vcan0'
ExecStop=/bin/bash -c 'ip link set down vcan0 && ip link delete vcan0'
User=root

[Install]
WantedBy=multi-user.target
EOF
    
    print_status "✓ CAN-Interface-Services erstellt"
}

setup_mqtt_broker() {
    print_step "Prüfe MQTT-Broker..."
    
    # Prüfe ob mosquitto installiert ist
    if ! command -v mosquitto &> /dev/null; then
        print_warning "mosquitto nicht gefunden - installiere..."
        apt-get update
        apt-get install -y mosquitto mosquitto-clients
        systemctl enable mosquitto
        systemctl start mosquitto
        print_status "✓ mosquitto installiert und gestartet"
    else
        print_status "✓ mosquitto bereits installiert"
        systemctl enable mosquitto
        systemctl start mosquitto
    fi
}

create_control_scripts() {
    print_step "Erstelle Kontroll-Scripts..."
    
    # Start-Script
    cat << 'EOF' > /usr/local/bin/pi-main-start
#!/bin/bash
systemctl start fahrwerkstester-pi-main
systemctl status fahrwerkstester-pi-main --no-pager
EOF
    
    # Stop-Script
    cat << 'EOF' > /usr/local/bin/pi-main-stop
#!/bin/bash
systemctl stop fahrwerkstester-pi-main
EOF
    
    # Status-Script
    cat << 'EOF' > /usr/local/bin/pi-main-status
#!/bin/bash
echo "=== Pi Main Service Status ==="
systemctl status fahrwerkstester-pi-main --no-pager
echo ""
echo "=== Recent Logs ==="
journalctl -u fahrwerkstester-pi-main --no-pager -n 20
EOF
    
    # Logs-Script
    cat << 'EOF' > /usr/local/bin/pi-main-logs
#!/bin/bash
journalctl -u fahrwerkstester-pi-main -f
EOF
    
    # Restart-Script
    cat << 'EOF' > /usr/local/bin/pi-main-restart
#!/bin/bash
systemctl restart fahrwerkstester-pi-main
systemctl status fahrwerkstester-pi-main --no-pager
EOF
    
    # Permissions
    chmod +x /usr/local/bin/pi-main-*
    
    print_status "✓ Kontroll-Scripts erstellt"
}

setup_autostart() {
    print_step "Konfiguriere Autostart..."
    
    # Services aktivieren
    systemctl enable mosquitto
    systemctl enable can-interface
    systemctl enable vcan-interface
    systemctl enable ${SERVICE_NAME}
    
    # systemd daemon reload
    systemctl daemon-reload
    
    print_status "✓ Autostart konfiguriert"
}

install_dependencies() {
    print_step "Installiere System-Abhängigkeiten..."
    
    # System-Pakete
    apt-get update
    apt-get install -y \
        can-utils \
        iproute2 \
        mosquitto \
        mosquitto-clients \
        python3-dev \
        python3-pip \
        git
    
    # Prüfe ob uv installiert ist
    if ! command -v uv &> /dev/null; then
        print_warning "uv nicht gefunden - installiere..."
        sudo -u $PI_USER curl -LsSf https://astral.sh/uv/install.sh | sudo -u $PI_USER sh
        print_status "✓ uv installiert"
    else
        print_status "✓ uv bereits installiert"
    fi
    
    # Python-Abhängigkeiten installieren
    cd $PROJECT_DIR
    sudo -u $PI_USER /home/pi/.cargo/bin/uv sync
    
    print_status "✓ Abhängigkeiten installiert"
}

show_final_info() {
    print_status "🎉 Pi Main Service Setup abgeschlossen!"
    echo ""
    echo "📋 Verfügbare Kommandos:"
    echo "  pi-main-start      - Service starten"
    echo "  pi-main-stop       - Service stoppen"
    echo "  pi-main-restart    - Service neu starten"
    echo "  pi-main-status     - Service-Status anzeigen"
    echo "  pi-main-logs       - Live-Logs anzeigen"
    echo ""
    echo "📊 Service-Status:"
    systemctl status ${SERVICE_NAME} --no-pager || true
    echo ""
    echo "🚀 Service starten:"
    echo "  sudo systemctl start ${SERVICE_NAME}"
    echo ""
    echo "📱 Auto-Start beim Boot:"
    echo "  ✅ Aktiviert - Service startet automatisch beim Boot"
    echo ""
    echo "🔧 Konfiguration:"
    echo "  Service-Datei: /etc/systemd/system/${SERVICE_NAME}.service"
    echo "  Logs: /var/log/fahrwerkstester/"
    echo "  Daten: /var/lib/fahrwerkstester/"
    echo ""
    echo "🎯 Test-Kommandos:"
    echo "  # Hardware-Modus (falls CAN verfügbar)"
    echo "  python pi_main.py --force-can"
    echo ""
    echo "  # Simulator-Modus"
    echo "  python pi_main.py --force-simulator"
    echo ""
    echo "  # Debug-Modus"
    echo "  python pi_main.py --debug"
}

main() {
    echo "🚀 Fahrwerkstester Pi Main Service Setup"
    echo "======================================="
    
    check_root
    
    print_step "Prüfe Projekt-Verzeichnis..."
    if [ ! -d "$PROJECT_DIR" ]; then
        print_error "Projekt-Verzeichnis $PROJECT_DIR nicht gefunden!"
        exit 1
    fi
    
    if [ ! -f "$PROJECT_DIR/pi_main.py" ]; then
        print_error "pi_main.py nicht gefunden in $PROJECT_DIR!"
        exit 1
    fi
    
    print_status "✓ Projekt-Verzeichnis gefunden"
    
    # Setup-Schritte
    install_dependencies
    setup_logging
    setup_can_interface
    setup_mqtt_broker
    setup_systemd_service
    create_control_scripts
    setup_autostart
    
    show_final_info
}

# Script ausführen
main "$@"
