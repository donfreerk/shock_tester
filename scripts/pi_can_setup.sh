# 1. Deployment-Skript für automatisches Setup ausführen
chmod +x scripts/deploy_pi_service.sh
./scripts/deploy_pi_service.sh

# 2. Manueller Start der Services (falls noch nicht automatisch gestartet)
sudo systemctl start pi-processing
sudo systemctl start hardware-bridge
sudo systemctl start mosquitto

# 3. Service-Status überprüfen
sudo systemctl status pi-processing
sudo systemctl status hardware-bridge
sudo systemctl status mosquitto

# 4. CAN-Interface manuell überprüfen/einrichten
# Für echtes CAN (Hardware)
sudo ip link set can0 type can bitrate 1000000
sudo ip link set up can0

# Für Virtual CAN (Testing)
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

# 5. CAN-Interface Status prüfen
ip link show can0
ip link show vcan0

# 6. Logs in Echtzeit verfolgen
sudo journalctl -u pi-processing -f
sudo journalctl -u hardware-bridge -f

# 7. MQTT-Nachrichten überwachen
mosquitto_sub -h localhost -t "suspension/#" -v

# 8. CAN-Nachrichten direkt überwachen (falls can-utils installiert)
candump can0
# oder für virtual CAN
candump vcan0