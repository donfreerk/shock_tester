# 🚀 Pi Main Service - Intelligente Fahrwerkstester-Steuerung

## 📖 Übersicht

Der **Pi Main Service** ist eine intelligente Hauptsteuerung für den Raspberry Pi, die automatisch zwischen echter
CAN-Hardware und Simulator umschaltet. Er orchestriert alle Services und sorgt für einen reibungslosen Betrieb.

## ✨ Features

- **🔍 Auto-Detection**: Erkennt automatisch CAN-Hardware vs. Simulator
- **🔧 Service-Orchestrierung**: Startet Hardware Bridge + Pi Processing + MQTT koordiniert
- **🛡️ Robuste Fehlerbehandlung**: Graceful Shutdown und Error Recovery
- **📊 System-Monitoring**: Comprehensive Logging und Health-Checks
- **🎯 Pi-Optimiert**: Resource-Management für Raspberry Pi
- **🔄 Systemd-Integration**: Automatischer Start beim Boot

## 🏗️ Architektur

```
Pi Main Service
├── Hardware Detection
│   ├── CAN-Interface-Erkennung
│   └── Fallback zu Simulator
├── Service Management
│   ├── Hardware Bridge Service
│   ├── Pi Processing Service
│   └── CAN Simulator Service
├── MQTT-Kommunikation
│   ├── System-Status
│   ├── Health-Monitoring
│   └── Error-Reporting
└── System-Monitoring
    ├── Resource-Überwachung
    ├── Service-Health-Checks
    └── Automatic Recovery
```

## 📋 Modi

### 🔧 CAN-Hardware-Modus

- **Aktiviert wenn**: CAN-Interface (can0) erkannt wird
- **Services**: Hardware Bridge + Pi Processing
- **Verwendung**: Produktionsbetrieb mit echter Hardware

### 🎮 Simulator-Modus

- **Aktiviert wenn**: Keine CAN-Hardware verfügbar
- **Services**: CAN Simulator + Pi Processing
- **Verwendung**: Development, Testing, Demo

### 🔄 Mixed-Modus

- **Aktiviert wenn**: Beide Modi verfügbar
- **Services**: Alle Services (für spezielle Anwendungsfälle)

## 🚀 Installation

### 1. Automatische Installation (Empfohlen)

```bash
# Repository klonen
git clone https://github.com/your-repo/fahrwerkstester.git
cd fahrwerkstester

# Automatisches Setup ausführen
sudo bash scripts/setup_pi_main_service.sh
```

### 2. Manuelle Installation

```bash
# Abhängigkeiten installieren
sudo apt-get update
sudo apt-get install -y can-utils mosquitto mosquitto-clients python3-dev

# uv installieren (falls nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python-Abhängigkeiten
uv sync

# Konfiguration kopieren
cp config/pi_main_config.yaml /etc/fahrwerkstester/

# Service manuell einrichten
sudo systemctl enable fahrwerkstester-pi-main
```

## 🔧 Konfiguration

### Standard-Konfiguration

```yaml
# config/pi_main_config.yaml
system:
  heartbeat_interval: 30.0

mqtt:
  broker: "localhost"
  port: 1883

can:
  interface: "can0"
  bitrate: 500000

logging:
  level: "INFO"
  path: "/var/log/fahrwerkstester/pi_main.log"
```

### Erweiterte Konfiguration

Vollständige Konfiguration siehe [`config/pi_main_config.yaml`](config/pi_main_config.yaml)

## 🎯 Verwendung

### Direkter Start

```bash
# Auto-Detection (empfohlen)
python pi_main.py

# Simulator erzwingen
python pi_main.py --force-simulator

# CAN-Hardware erzwingen  
python pi_main.py --force-can

# Debug-Modus
python pi_main.py --debug --log-level DEBUG

# Mit spezifischer Konfiguration
python pi_main.py --config /path/to/config.yaml
```

### Systemd-Service

```bash
# Service starten
sudo systemctl start fahrwerkstester-pi-main

# Service stoppen
sudo systemctl stop fahrwerkstester-pi-main

# Service-Status
sudo systemctl status fahrwerkstester-pi-main

# Logs anzeigen
sudo journalctl -u fahrwerkstester-pi-main -f
```

### Kontroll-Scripts

Nach der Installation stehen einfache Kontroll-Scripts zur Verfügung:

```bash
# Service starten
pi-main-start

# Service stoppen
pi-main-stop

# Service neu starten
pi-main-restart

# Service-Status anzeigen
pi-main-status

# Live-Logs anzeigen
pi-main-logs
```

## 📊 Monitoring

### System-Status über MQTT

```bash
# System-Status abonnieren
mosquitto_sub -h localhost -t "suspension/system/pi_status"

# Beispiel-Nachricht:
{
  "mode": "simulator",
  "can_available": false,
  "mqtt_connected": true,
  "services_running": {
    "can_simulator": true,
    "pi_processing": true,
    "monitoring": true
  },
  "uptime": 3600.0,
  "errors": [],
  "warnings": []
}
```

### Log-Dateien

```bash
# Haupt-Log
tail -f /var/log/fahrwerkstester/pi_main.log

# Systemd-Journal
journalctl -u fahrwerkstester-pi-main --since "1 hour ago"

# Alle Fahrwerkstester-Logs
find /var/log/fahrwerkstester/ -name "*.log" -exec tail -f {} +
```

## 🧪 Testing

### Automatische Tests

```bash
# Vollständige Test-Suite
python scripts/test_pi_main.py

# Einzelne Tests
python scripts/test_pi_main.py --test can_detection
python scripts/test_pi_main.py --test mqtt_broker
python scripts/test_pi_main.py --test startup_simulator
```

### Manuelle Tests

```bash
# Test 1: CAN-Hardware-Erkennung
ip link show type can

# Test 2: MQTT-Broker
mosquitto_pub -h localhost -t test -m "hello"

# Test 3: Virtual CAN (für Development)
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

# Test 4: Service-Konfiguration
python -c "from pi_main import PiSystemManager; print('✅ Import OK')"
```

## 🔧 Troubleshooting

### Häufige Probleme

#### 1. CAN-Interface nicht erkannt

```bash
# CAN-Module laden
sudo modprobe can
sudo modprobe can_raw
sudo modprobe mcp251x

# Interface manuell konfigurieren
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0

# Status prüfen
ip link show can0
```

#### 2. MQTT-Verbindung fehlschlägt

```bash
# Mosquitto-Status prüfen
sudo systemctl status mosquitto

# Mosquitto neu starten
sudo systemctl restart mosquitto

# Firewall prüfen
sudo ufw status
```

#### 3. Service startet nicht

```bash
# Detaillierte Logs
journalctl -u fahrwerkstester-pi-main --no-pager

# Abhängigkeiten prüfen
python scripts/test_pi_main.py

# Konfiguration validieren
python -c "import yaml; yaml.safe_load(open('config/pi_main_config.yaml'))"
```

#### 4. Performance-Probleme

```bash
# CPU-Auslastung prüfen
htop

# Memory-Verbrauch
free -h

# Disk-Space
df -h

# Service-Ressourcen
systemctl show fahrwerkstester-pi-main --property=MemoryCurrent
```

### Debug-Modus

```bash
# Ausführlicher Debug-Modus
python pi_main.py --debug --log-level DEBUG

# Profiling aktivieren
python pi_main.py --debug --profile

# Trace-Modus
python pi_main.py --debug --trace
```

## 🔄 Update & Wartung

### Updates

```bash
# Code-Update
cd /home/pi/fahrwerkstester
git pull origin main

# Abhängigkeiten aktualisieren
uv sync

# Service neu starten
sudo systemctl restart fahrwerkstester-pi-main
```

### Wartung

```bash
# Logs archivieren
sudo logrotate -f /etc/logrotate.d/fahrwerkstester

# Temporary-Dateien bereinigen
sudo systemctl clean fahrwerkstester-pi-main

# Konfiguration sichern
sudo cp /etc/fahrwerkstester/pi_main_config.yaml /backup/

# System-Check
python scripts/test_pi_main.py
```

## 🛡️ Sicherheit

### Netzwerk-Sicherheit

```bash
# Firewall-Regeln
sudo ufw allow 1883/tcp  # MQTT
sudo ufw enable

# SSH-Zugang beschränken
sudo nano /etc/ssh/sshd_config
```

### Service-Sicherheit

```yaml
# Service läuft als pi-User (nicht root)
User=pi
Group=pi

  # Eingeschränkte Berechtigungen
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
```

## 📈 Performance-Optimierung

### Pi-spezifische Optimierungen

```bash
# GPU-Memory für Headless-Betrieb
echo "gpu_mem=16" >> /boot/config.txt

# CPU-Governor
echo "performance" | sudo tee /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# I/O-Scheduler für SD-Karten
echo "deadline" | sudo tee /sys/block/mmcblk0/queue/scheduler
```

### Service-Optimierungen

```yaml
# config/pi_main_config.yaml
system:
  resource_limits:
    max_memory_mb: 512
    max_cpu_percent: 70

pi_processing:
  performance:
    enable_vectorized_processing: true
    enable_caching: true
    parallel_processing: true
```

## 🤝 Integration

### GUI-Integration

```python
# Frontend kann Pi Main Service steuern
import paho.mqtt.client as mqtt

client = mqtt.Client()
client.connect("localhost", 1883, 60)

# Test starten
client.publish("suspension/test/start", json.dumps({
	"command": "start_test",
	"position": "front_left",
	"method": "phase_shift"
}))
```

### API-Integration

```python
# Direkter Import für erweiterte Integration
from pi_main import PiSystemManager

manager = PiSystemManager()
await manager.start_system()
```

## 📚 Weitere Dokumentation

- [EGEA-Spezifikation](docs/EGEA_Suspension_Tester_Specifications_FINAL.pdf)
- [Hardware-Setup](hardware/README.md)
- [Service-Architektur](docs/Service-Architecture.md)
- [Deployment-Guide](scripts/README.md)

## 💡 Tipps & Tricks

### Development-Workflow

```bash
# 1. Lokale Entwicklung mit Simulator
python pi_main.py --force-simulator --debug

# 2. Hardware-Test mit echtem CAN
python pi_main.py --force-can --debug

# 3. Production-Deployment
sudo systemctl start fahrwerkstester-pi-main
```

### Monitoring-Dashboard

```bash
# Einfaches Monitoring mit watch
watch -n 5 'pi-main-status'

# MQTT-Dashboard
mosquitto_sub -h localhost -t "suspension/system/+" -v
```

### Backup-Strategie

```bash
# Automatisches Backup-Script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /backup/fahrwerkstester_$DATE.tar.gz \
  /home/pi/fahrwerkstester/config/ \
  /var/log/fahrwerkstester/ \
  /etc/fahrwerkstester/
```

## 🎉 Fazit

Der Pi Main Service bietet eine robuste, intelligente Lösung für die Steuerung des Fahrwerkstester-Systems auf dem
Raspberry Pi. Mit automatischer Hardware-Erkennung, Service-Orchestrierung und umfassendem Monitoring ist er die ideale
Lösung für sowohl Development als auch Production.

**🚀 Ready for Production!**

---

**📧 Support**: Bei Problemen oder Fragen erstellen Sie ein Issue im Repository oder kontaktieren Sie das
Development-Team.

**🔄 Updates**: Regelmäßige Updates und neue Features werden über das Git-Repository bereitgestellt.

**📖 Documentation**: Vollständige Dokumentation finden Sie im `docs/`-Verzeichnis.
