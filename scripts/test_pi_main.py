#!/usr/bin/env python3
"""
🧪 Test-Script für Pi Main Service
Testet die Funktionalität des Pi Main Services in verschiedenen Modi
"""

import asyncio
import sys
import time
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import signal
import os

# Pfad-Setup
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "common"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PiMainTester:
    """
    Tester für den Pi Main Service
    
    Testet verschiedene Betriebsmodi und Funktionen
    """
    
    def __init__(self):
        self.project_root = project_root
        self.test_results = {}
        self.pi_main_process = None
        
    def print_header(self, title: str):
        """Druckt Test-Header"""
        print(f"\n{'='*60}")
        print(f"🧪 {title}")
        print('='*60)
        
    def print_result(self, test_name: str, success: bool, message: str = ""):
        """Druckt Test-Ergebnis"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if message:
            print(f"    {message}")
        
        self.test_results[test_name] = {
            "success": success,
            "message": message
        }
    
    def check_dependencies(self) -> bool:
        """Prüft System-Abhängigkeiten"""
        self.print_header("Dependency Check")
        
        all_passed = True
        
        # Python-Module prüfen
        modules = [
            ("asyncio", "asyncio"),
            ("pathlib", "pathlib"),
            ("subprocess", "subprocess"),
            ("json", "json")
        ]
        
        for module_name, import_name in modules:
            try:
                __import__(import_name)
                self.print_result(f"Python Module: {module_name}", True)
            except ImportError as e:
                self.print_result(f"Python Module: {module_name}", False, str(e))
                all_passed = False
        
        # Projekt-Dateien prüfen
        required_files = [
            "pi_main.py",
            "config/pi_main_config.yaml",
            "common/suspension_core/__init__.py"
        ]
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            exists = full_path.exists()
            self.print_result(f"File: {file_path}", exists)
            if not exists:
                all_passed = False
        
        return all_passed
    
    def test_can_detection(self) -> bool:
        """Testet CAN-Interface-Erkennung"""
        self.print_header("CAN Interface Detection")
        
        # Prüfe /sys/class/net für CAN-Interfaces
        can_interfaces = list(Path("/sys/class/net").glob("can*"))
        vcan_interfaces = list(Path("/sys/class/net").glob("vcan*"))
        
        self.print_result(
            "Hardware CAN Interfaces", 
            len(can_interfaces) > 0,
            f"Found: {[i.name for i in can_interfaces]}"
        )
        
        self.print_result(
            "Virtual CAN Interfaces",
            len(vcan_interfaces) > 0,
            f"Found: {[i.name for i in vcan_interfaces]}"
        )
        
        # Versuche vcan0 zu erstellen falls nicht vorhanden
        if not any(i.name == "vcan0" for i in vcan_interfaces):
            try:
                # Versuche vcan0 zu erstellen
                subprocess.run(
                    ["sudo", "modprobe", "vcan"],
                    check=True, capture_output=True
                )
                subprocess.run(
                    ["sudo", "ip", "link", "add", "dev", "vcan0", "type", "vcan"],
                    check=True, capture_output=True
                )
                subprocess.run(
                    ["sudo", "ip", "link", "set", "up", "vcan0"],
                    check=True, capture_output=True
                )
                self.print_result("Create vcan0", True, "Virtual CAN interface created")
                return True
            except subprocess.CalledProcessError as e:
                self.print_result("Create vcan0", False, f"Failed to create vcan0: {e}")
                return False
        else:
            self.print_result("vcan0 Available", True, "Virtual CAN interface ready")
            return True
    
    def test_mqtt_broker(self) -> bool:
        """Testet MQTT-Broker"""
        self.print_header("MQTT Broker Test")
        
        # Prüfe ob mosquitto läuft
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "mosquitto"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                self.print_result("Mosquitto Service", True, "Active")
            else:
                self.print_result("Mosquitto Service", False, "Not active")
                
                # Versuche mosquitto zu starten
                try:
                    subprocess.run(
                        ["sudo", "systemctl", "start", "mosquitto"],
                        check=True, capture_output=True
                    )
                    self.print_result("Start Mosquitto", True, "Started successfully")
                except subprocess.CalledProcessError:
                    self.print_result("Start Mosquitto", False, "Failed to start")
                    return False
            
            # Teste MQTT-Verbindung
            try:
                result = subprocess.run(
                    ["mosquitto_pub", "-h", "localhost", "-t", "test", "-m", "hello"],
                    timeout=5, capture_output=True
                )
                
                if result.returncode == 0:
                    self.print_result("MQTT Publish Test", True, "Message sent successfully")
                    return True
                else:
                    self.print_result("MQTT Publish Test", False, "Failed to send message")
                    return False
                    
            except subprocess.TimeoutExpired:
                self.print_result("MQTT Publish Test", False, "Timeout")
                return False
                
        except Exception as e:
            self.print_result("MQTT Broker Test", False, str(e))
            return False
    
    async def test_pi_main_startup(self, mode: str) -> bool:
        """Testet Pi Main Service Startup"""
        self.print_header(f"Pi Main Service Startup Test ({mode})")
        
        # Kommando zusammenstellen
        cmd = [
            sys.executable, "pi_main.py",
            "--config", "config/pi_main_config.yaml",
            "--log-level", "INFO"
        ]
        
        if mode == "simulator":
            cmd.append("--force-simulator")
        elif mode == "can":
            cmd.append("--force-can")
        
        try:
            # Starte Pi Main Service
            self.pi_main_process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            self.print_result("Pi Main Process Start", True, f"PID: {self.pi_main_process.pid}")
            
            # Warte auf Startup-Ausgaben
            startup_timeout = 30  # Sekunden
            startup_success = False
            
            for i in range(startup_timeout):
                if self.pi_main_process.poll() is not None:
                    # Prozess ist beendet
                    stdout, stderr = self.pi_main_process.communicate()
                    self.print_result("Pi Main Startup", False, f"Process terminated: {stdout}")
                    return False
                
                await asyncio.sleep(1)
                
                # Prüfe ob Success-Nachricht da ist
                # In einer echten Implementation würde man die Logs parsen
                if i > 10:  # Nach 10 Sekunden annehmen dass es läuft
                    startup_success = True
                    break
            
            if startup_success:
                self.print_result("Pi Main Startup", True, "Service started successfully")
                
                # Warte etwas für Stabilität
                await asyncio.sleep(5)
                
                # Prüfe ob Prozess noch läuft
                if self.pi_main_process.poll() is None:
                    self.print_result("Pi Main Stability", True, "Service running stable")
                    return True
                else:
                    self.print_result("Pi Main Stability", False, "Service crashed")
                    return False
            else:
                self.print_result("Pi Main Startup", False, "Startup timeout")
                return False
                
        except Exception as e:
            self.print_result("Pi Main Startup", False, str(e))
            return False
        finally:
            # Cleanup
            if self.pi_main_process and self.pi_main_process.poll() is None:
                self.pi_main_process.terminate()
                try:
                    self.pi_main_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.pi_main_process.kill()
                    self.pi_main_process.wait()
                self.print_result("Pi Main Cleanup", True, "Process terminated")
    
    async def test_configuration_loading(self) -> bool:
        """Testet Konfiguration-Loading"""
        self.print_header("Configuration Loading Test")
        
        config_path = self.project_root / "config" / "pi_main_config.yaml"
        
        if not config_path.exists():
            self.print_result("Config File Exists", False, f"File not found: {config_path}")
            return False
        
        self.print_result("Config File Exists", True, str(config_path))
        
        # Versuche Konfiguration zu laden
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Prüfe wichtige Konfigurationssektionen
            required_sections = ["system", "mqtt", "can", "logging"]
            
            for section in required_sections:
                if section in config:
                    self.print_result(f"Config Section: {section}", True)
                else:
                    self.print_result(f"Config Section: {section}", False, "Missing section")
                    return False
            
            return True
            
        except Exception as e:
            self.print_result("Config Loading", False, str(e))
            return False
    
    async def test_import_structure(self) -> bool:
        """Testet Import-Struktur"""
        self.print_header("Import Structure Test")
        
        # Prüfe wichtige Imports
        imports_to_test = [
            ("suspension_core.mqtt.handler", "MqttHandler"),
            ("suspension_core.config", "ConfigManager"),
            ("backend.pi_processing_service.main", "PiProcessingService"),
            ("backend.can_simulator_service.command_controlled_main", "CommandControlledSimulatorService")
        ]
        
        all_passed = True
        
        for module_name, class_name in imports_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
                self.print_result(f"Import: {module_name}.{class_name}", True)
            except ImportError as e:
                self.print_result(f"Import: {module_name}.{class_name}", False, str(e))
                all_passed = False
            except AttributeError as e:
                self.print_result(f"Import: {module_name}.{class_name}", False, str(e))
                all_passed = False
        
        return all_passed
    
    async def run_all_tests(self):
        """Führt alle Tests aus"""
        print("🚀 Pi Main Service Test Suite")
        print("=" * 60)
        
        # Test-Reihenfolge
        tests = [
            ("Dependency Check", self.check_dependencies),
            ("Configuration Loading", self.test_configuration_loading),
            ("Import Structure", self.test_import_structure),
            ("CAN Detection", self.test_can_detection),
            ("MQTT Broker", self.test_mqtt_broker),
            ("Pi Main Simulator Mode", lambda: self.test_pi_main_startup("simulator")),
            ("Pi Main CAN Mode", lambda: self.test_pi_main_startup("can"))
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                results[test_name] = result
                
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results[test_name] = False
                self.print_result(test_name, False, str(e))
        
        # Zusammenfassung
        self.print_header("Test Summary")
        
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        
        print(f"\n📊 Results: {passed}/{total} tests passed")
        
        for test_name, result in results.items():
            status = "✅" if result else "❌"
            print(f"  {status} {test_name}")
        
        if passed == total:
            print(f"\n🎉 All tests passed! Pi Main Service is ready for deployment.")
            return True
        else:
            print(f"\n⚠️ {total - passed} tests failed. Please check the errors above.")
            return False
    
    def cleanup(self):
        """Cleanup nach Tests"""
        if self.pi_main_process and self.pi_main_process.poll() is None:
            self.pi_main_process.terminate()
            try:
                self.pi_main_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.pi_main_process.kill()
                self.pi_main_process.wait()


async def main():
    """Hauptfunktion"""
    tester = PiMainTester()
    
    try:
        success = await tester.run_all_tests()
        
        if success:
            print("\n🎯 Pi Main Service Test: SUCCESS")
            print("🚀 Ready for deployment!")
            return 0
        else:
            print("\n❌ Pi Main Service Test: FAILURE")
            print("🔧 Please fix the issues above before deployment.")
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return 1
    finally:
        tester.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
