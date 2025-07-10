@echo off
REM Windows-Test-Setup für Fahrwerkstester
REM Startet alle Services für lokales Testing

echo ===================================================
echo     Windows-Test-Setup für Fahrwerkstester
echo ===================================================

REM Console-Encoding setzen
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

echo.
echo 1. Prüfe System-Voraussetzungen...
python scripts/windows_test_fix.py

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] System-Prüfung fehlgeschlagen
    pause
    exit /b 1
)

echo.
echo 2. Starte Services...
echo    - CAN Simulator
echo    - Hardware Bridge  
echo    - GUI

REM CAN Simulator in neuem Terminal
start "CAN Simulator" cmd /k "python -m backend.can_simulator_service.main --endless"

REM Kurz warten
timeout /t 3 > nul

REM Hardware Bridge in neuem Terminal
start "Hardware Bridge" cmd /k "python hardware/hardware_bridge.py --mode simulator"

REM Kurz warten
timeout /t 3 > nul

REM GUI in neuem Terminal
start "Simplified GUI" cmd /k "python frontend/desktop_gui/simplified_gui.py"

echo.
echo ✅ Alle Services gestartet!
echo.
echo 💡 Tipps:
echo    - Daten sollten in der GUI erscheinen
echo    - Bei Problemen: Logs in den Terminal-Fenstern prüfen
echo    - Beenden: Ctrl+C in allen Terminal-Fenstern
echo.
echo 🔍 MQTT-Monitoring (optional):
echo    mosquitto_sub -h localhost -t "suspension/#"
echo.
pause
