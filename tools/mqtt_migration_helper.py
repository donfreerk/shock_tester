#!/usr/bin/env python3
"""
MQTT Migration Helper

Dieses Tool hilft bei der Migration bestehender Services zur einheitlichen MQTT-Integration.
Es kann Import-Pfade korrigieren, Service-Templates generieren und Migrations-Validierung durchführen.

Usage:
    python tools/mqtt_migration_helper.py --check-imports
    python tools/mqtt_migration_helper.py --fix-imports
    python tools/mqtt_migration_helper.py --generate-template my_service
    python tools/mqtt_migration_helper.py --validate-service backend/my_service/main.py
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))


class MqttMigrationHelper:
    """
    Helper-Klasse für MQTT-Migration
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.service_directories = [
            "backend/can_simulator_service",
            "backend/pi_processing_service", 
            "backend/hardware_bridge_service",
            "backend/test_controller_service"
        ]
        
        # Import-Patterns die korrigiert werden müssen
        self.old_import_patterns = [
            # Alte Patterns
            r'from common\.suspension_core\.mqtt\.handler import MqttHandler',
            r'from common\.suspension_core\.mqtt import MqttHandler',
            r'import common\.suspension_core\.mqtt\.handler',
            # Inkonsistente Patterns
            r'from suspension_core\.mqtt\.handler import MqttHandler',
        ]
        
        # Neues standardisiertes Pattern
        self.new_import_pattern = 'from suspension_core.mqtt import MqttHandler, MqttServiceBase, MqttTopics'
    
    def check_imports(self) -> Dict[str, List[str]]:
        """
        Prüft alle Python-Dateien auf problematische MQTT-Imports
        
        Returns:
            Dictionary mit Dateien und gefundenen Problemen
        """
        print("🔍 Überprüfe MQTT-Imports in allen Services...")
        
        issues = {}
        
        for service_dir in self.service_directories:
            service_path = self.project_root / service_dir
            if not service_path.exists():
                continue
                
            print(f"  📁 {service_dir}")
            
            # Finde alle Python-Dateien
            python_files = list(service_path.rglob("*.py"))
            
            for py_file in python_files:
                file_issues = self._check_file_imports(py_file)
                if file_issues:
                    relative_path = py_file.relative_to(self.project_root)
                    issues[str(relative_path)] = file_issues
                    print(f"    ❌ {relative_path}: {len(file_issues)} Probleme")
                else:
                    relative_path = py_file.relative_to(self.project_root)
                    print(f"    ✅ {relative_path}: OK")
        
        return issues
    
    def _check_file_imports(self, file_path: Path) -> List[str]:
        """
        Prüft eine einzelne Datei auf Import-Probleme
        
        Args:
            file_path: Pfad zur Python-Datei
            
        Returns:
            Liste der gefundenen Probleme
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for line_num, line in enumerate(content.split('\n'), 1):
                for pattern in self.old_import_patterns:
                    if re.search(pattern, line):
                        issues.append(f"Line {line_num}: {line.strip()}")
                        
        except Exception as e:
            issues.append(f"Error reading file: {e}")
        
        return issues
    
    def fix_imports(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Korrigiert Import-Statements in allen Services
        
        Args:
            dry_run: Wenn True, werden keine Änderungen geschrieben
            
        Returns:
            Dictionary mit Anzahl der Korrekturen pro Datei
        """
        print("🔧 Korrigiere MQTT-Imports...")
        
        corrections = {}
        
        for service_dir in self.service_directories:
            service_path = self.project_root / service_dir
            if not service_path.exists():
                continue
                
            print(f"  📁 {service_dir}")
            
            python_files = list(service_path.rglob("*.py"))
            
            for py_file in python_files:
                file_corrections = self._fix_file_imports(py_file, dry_run)
                if file_corrections > 0:
                    relative_path = py_file.relative_to(self.project_root)
                    corrections[str(relative_path)] = file_corrections
                    status = "🔍 [DRY RUN]" if dry_run else "✅ [FIXED]"
                    print(f"    {status} {relative_path}: {file_corrections} Korrekturen")
        
        return corrections
    
    def _fix_file_imports(self, file_path: Path, dry_run: bool) -> int:
        """
        Korrigiert Imports in einer einzelnen Datei
        
        Args:
            file_path: Pfad zur Python-Datei
            dry_run: Wenn True, keine Änderungen schreiben
            
        Returns:
            Anzahl der vorgenommenen Korrekturen
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            corrections = 0
            
            # Import-Korrekturen
            for pattern in self.old_import_patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, self.new_import_pattern, content)
                    corrections += 1
            
            # Schreibe korrigierte Datei (falls nicht dry_run)
            if not dry_run and corrections > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return corrections
            
        except Exception as e:
            print(f"    ❌ Error fixing {file_path}: {e}")
            return 0
    
    def generate_service_template(self, service_name: str) -> str:
        """
        Generiert Service-Template für neue MQTT-Integration
        
        Args:
            service_name: Name des Services
            
        Returns:
            Python-Code für Service-Template
        """
        template = f'''#!/usr/bin/env python3
"""
{service_name.title()} Service mit einheitlicher MQTT-Integration

Dieses Service-Template wurde automatisch generiert und zeigt die 
standardisierte Verwendung der MqttServiceBase-Klasse.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project path
sys.path.append(str(Path(__file__).parent.parent.parent))

from suspension_core.mqtt import MqttServiceBase, MqttTopics
from suspension_core.config import ConfigManager

logger = logging.getLogger(__name__)


class {service_name.title().replace('_', '')}Service(MqttServiceBase):
    """
    {service_name.title()} Service mit einheitlicher MQTT-Integration
    
    Funktionalitäten:
    - Standardisierte MQTT-Kommunikation
    - Robuste async/sync Callback-Bridge
    - Einheitliche Status- und Heartbeat-Publishing
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialisiert {service_name.title()} Service
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        config = ConfigManager(config_path)
        super().__init__("{service_name}", config)
        
        # Service-spezifische Initialisierung hier
        self.service_data = {{}}
        
        logger.info(f"{service_name.title()} Service initialized")
    
    async def setup_mqtt_subscriptions(self):
        """Service-spezifische MQTT-Subscriptions einrichten"""
        
        # Standard-Commands abonnieren
        command_topic = MqttTopics.service_command(self.service_name)
        self.register_topic_handler(command_topic, self.handle_command)
        
        # Test-Lifecycle abonnieren (falls relevant)
        self.register_topic_handler(MqttTopics.TEST_STATUS, self.handle_test_status)
        
        # Daten-Topics abonnieren (anpassen nach Bedarf)
        self.register_topic_handler(MqttTopics.MEASUREMENT_RAW_DATA, self.handle_measurement_data)
        
        logger.info("MQTT subscriptions configured")
    
    async def handle_command(self, topic: str, message: Dict[str, Any]):
        """
        Command-Handler für Service-spezifische Commands
        
        Args:
            topic: MQTT-Topic
            message: Command-Message
        """
        try:
            command = message.get("command")
            
            if command == "start":
                await self.start_operation(message.get("parameters", {{}}))
            elif command == "stop":
                await self.stop_operation()
            elif command == "status":
                await self.publish_detailed_status()
            elif command == "configure":
                await self.configure_service(message.get("parameters", {{}}))
            else:
                logger.warning(f"Unknown command: {{command}}")
                
        except Exception as e:
            logger.error(f"Error handling command: {{e}}")
            await self.publish_status("error", {{"error": str(e)}})
    
    async def handle_test_status(self, topic: str, message: Dict[str, Any]):
        """
        Test-Status-Handler
        
        Args:
            topic: MQTT-Topic
            message: Test-Status-Message
        """
        try:
            status = message.get("status")
            test_id = message.get("test_id")
            
            if status == "started":
                await self.on_test_started(test_id, message)
            elif status == "completed":
                await self.on_test_completed(test_id, message)
            elif status == "error":
                await self.on_test_error(test_id, message)
                
        except Exception as e:
            logger.error(f"Error handling test status: {{e}}")
    
    async def handle_measurement_data(self, topic: str, message: Dict[str, Any]):
        """
        Measurement-Data-Handler
        
        Args:
            topic: MQTT-Topic
            message: Measurement-Data-Message
        """
        try:
            # Process measurement data
            processed_data = await self.process_measurement_data(message)
            
            # Publish processed results
            if processed_data:
                await self.publish(MqttTopics.MEASUREMENT_PROCESSED, processed_data)
                
        except Exception as e:
            logger.error(f"Error handling measurement data: {{e}}")
    
    async def start_operation(self, parameters: Dict[str, Any]):
        """
        Startet Service-Operation
        
        Args:
            parameters: Operation-Parameter
        """
        try:
            logger.info(f"Starting operation with parameters: {{parameters}}")
            
            # Service-spezifische Start-Logik hier
            
            await self.publish_status("running", {{"operation": "started"}})
            
        except Exception as e:
            logger.error(f"Error starting operation: {{e}}")
            await self.publish_status("error", {{"error": str(e)}})
    
    async def stop_operation(self):
        """Stoppt Service-Operation"""
        try:
            logger.info("Stopping operation")
            
            # Service-spezifische Stop-Logik hier
            
            await self.publish_status("ready", {{"operation": "stopped"}})
            
        except Exception as e:
            logger.error(f"Error stopping operation: {{e}}")
    
    async def configure_service(self, parameters: Dict[str, Any]):
        """
        Konfiguriert Service
        
        Args:
            parameters: Konfiguration-Parameter
        """
        try:
            logger.info(f"Configuring service with: {{parameters}}")
            
            # Service-spezifische Konfiguration hier
            
            await self.publish_status("configured", {{"config": parameters}})
            
        except Exception as e:
            logger.error(f"Error configuring service: {{e}}")
    
    async def on_test_started(self, test_id: str, message: Dict[str, Any]):
        """Wird aufgerufen wenn Test startet"""
        logger.info(f"Test started: {{test_id}}")
        # Service-spezifische Test-Start-Logik
    
    async def on_test_completed(self, test_id: str, message: Dict[str, Any]):
        """Wird aufgerufen wenn Test abgeschlossen ist"""
        logger.info(f"Test completed: {{test_id}}")
        # Service-spezifische Test-End-Logik
    
    async def on_test_error(self, test_id: str, message: Dict[str, Any]):
        """Wird aufgerufen bei Test-Fehler"""
        logger.error(f"Test error: {{test_id}}")
        # Service-spezifische Error-Handling
    
    async def process_measurement_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Verarbeitet Measurement-Daten
        
        Args:
            data: Rohe Measurement-Daten
            
        Returns:
            Verarbeitete Daten oder None
        """
        # Service-spezifische Datenverarbeitung hier
        return data
    
    async def publish_detailed_status(self):
        """Publiziert detaillierten Service-Status"""
        detailed_status = self.get_status()
        detailed_status.update({{
            "service_data": self.service_data,
            # Weitere service-spezifische Status-Informationen
        }})
        
        await self.publish_status("running", detailed_status)
    
    async def start(self):
        """
        Startet den {service_name.title()} Service
        """
        try:
            logger.info("Starting {{}} Service...".format(self.service_name))
            
            # MQTT-Integration starten
            if not await self.start_mqtt():
                logger.error("Failed to start MQTT integration")
                return False
            
            # Service-spezifische Initialisierung
            await self.initialize_service()
            
            # Status als "ready" setzen
            await self.publish_status("ready", {{"initialized": True}})
            
            logger.info("{} Service started successfully".format(self.service_name.title()))
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service: {{e}}")
            return False
    
    async def stop(self):
        """
        Stoppt den {service_name.title()} Service
        """
        try:
            logger.info("Stopping {{}} Service...".format(self.service_name))
            
            # Service-spezifisches Cleanup
            await self.cleanup_service()
            
            # MQTT-Integration stoppen
            await self.stop_mqtt()
            
            logger.info("{} Service stopped".format(self.service_name.title()))
            
        except Exception as e:
            logger.error(f"Error stopping service: {{e}}")
    
    async def initialize_service(self):
        """Service-spezifische Initialisierung"""
        # Hier service-spezifische Initialisierung implementieren
        pass
    
    async def cleanup_service(self):
        """Service-spezifisches Cleanup"""
        # Hier service-spezifisches Cleanup implementieren
        pass


async def main():
    """Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description="{service_name.title()} Service")
    parser.add_argument("--config", help="Pfad zur Konfigurationsdatei")
    parser.add_argument("--log-level", default="INFO", help="Log-Level")
    
    args = parser.parse_args()
    
    # Logging konfigurieren
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Service erstellen und starten
    service = {service_name.title().replace('_', '')}Service(args.config)
    
    try:
        # Service starten
        if await service.start():
            # Hauptloop - Service läuft bis Interrupt
            while True:
                await asyncio.sleep(1.0)
        else:
            logger.error("Failed to start service")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service error: {{e}}")
        sys.exit(1)
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
'''
        return template
    
    def validate_service(self, service_file: Path) -> Dict[str, List[str]]:
        """
        Validiert Service-Implementierung gegen MQTT-Standards
        
        Args:
            service_file: Pfad zur Service-Datei
            
        Returns:
            Dictionary mit Validierungs-Ergebnissen
        """
        print(f"🔍 Validiere Service: {service_file}")
        
        results = {
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        try:
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check 1: Verwendet neue MQTT-Integration?
            if "MqttServiceBase" not in content:
                results["warnings"].append("Service verwendet nicht die neue MqttServiceBase-Klasse")
            
            # Check 2: Korrekte Imports?
            if "from suspension_core.mqtt import" not in content:
                results["errors"].append("Service verwendet nicht den standardisierten Import-Pfad")
            
            # Check 3: Verwendet MqttTopics?
            if "MqttTopics" not in content:
                results["suggestions"].append("Service sollte MqttTopics für konsistente Topic-Namen verwenden")
            
            # Check 4: Async-Handler?
            if re.search(r'def.*handle.*\(.*topic.*message.*\):', content):
                results["warnings"].append("Service sollte async Handler verwenden: async def handle_...")
            
            # Check 5: Error-Handling in Handlers?
            handler_functions = re.findall(r'async def (handle_\w+)', content)
            for handler in handler_functions:
                handler_block = self._extract_function_block(content, handler)
                if "try:" not in handler_block or "except:" not in handler_block:
                    results["warnings"].append(f"Handler {handler} sollte try/except Error-Handling haben")
            
            # Check 6: Status-Publishing?
            if "publish_status" not in content:
                results["suggestions"].append("Service sollte publish_status() für Status-Updates verwenden")
            
            # Check 7: Heartbeat?
            if "publish_heartbeat" not in content:
                results["suggestions"].append("Service sollte regelmäßige Heartbeats senden")
                
        except Exception as e:
            results["errors"].append(f"Error reading service file: {e}")
        
        return results
    
    def _extract_function_block(self, content: str, function_name: str) -> str:
        """Extrahiert Funktions-Block aus Code"""
        lines = content.split('\n')
        in_function = False
        function_lines = []
        indent_level = None
        
        for line in lines:
            if f"async def {function_name}" in line or f"def {function_name}" in line:
                in_function = True
                indent_level = len(line) - len(line.lstrip())
                function_lines.append(line)
            elif in_function:
                current_indent = len(line) - len(line.lstrip())
                if line.strip() and current_indent <= indent_level and not line.startswith(' '):
                    break
                function_lines.append(line)
        
        return '\n'.join(function_lines)
    
    def migration_summary(self) -> Dict[str, Any]:
        """
        Erstellt Migrations-Zusammenfassung für alle Services
        
        Returns:
            Zusammenfassung des Migrations-Status
        """
        print("📊 Erstelle MQTT-Migrations-Zusammenfassung...")
        
        # Check Imports
        import_issues = self.check_imports()
        
        # Validate Services
        validation_results = {}
        for service_dir in self.service_directories:
            main_file = self.project_root / service_dir / "main.py"
            if main_file.exists():
                validation_results[service_dir] = self.validate_service(main_file)
        
        summary = {
            "import_issues": import_issues,
            "validation_results": validation_results,
            "migration_recommendations": self._generate_migration_recommendations(import_issues, validation_results)
        }
        
        return summary
    
    def _generate_migration_recommendations(self, import_issues: Dict, validation_results: Dict) -> List[str]:
        """Generiert Migrations-Empfehlungen"""
        recommendations = []
        
        if import_issues:
            recommendations.append("🔧 Führe Import-Korrektur aus: python tools/mqtt_migration_helper.py --fix-imports")
        
        for service, results in validation_results.items():
            if results["errors"]:
                recommendations.append(f"❌ {service}: Kritische Probleme müssen behoben werden")
            elif results["warnings"]:
                recommendations.append(f"⚠️ {service}: Empfohlene Verbesserungen verfügbar")
            else:
                recommendations.append(f"✅ {service}: MQTT-Integration ist auf dem neuesten Stand")
        
        return recommendations


def main():
    """Hauptfunktion für CLI"""
    parser = argparse.ArgumentParser(description="MQTT Migration Helper für Fahrwerkstester")
    parser.add_argument("--check-imports", action="store_true", help="Überprüfe Import-Pfade")
    parser.add_argument("--fix-imports", action="store_true", help="Korrigiere Import-Pfade")
    parser.add_argument("--dry-run", action="store_true", help="Zeige nur was geändert würde")
    parser.add_argument("--generate-template", help="Generiere Service-Template")
    parser.add_argument("--validate-service", help="Validiere Service-Implementierung")
    parser.add_argument("--summary", action="store_true", help="Zeige Migrations-Zusammenfassung")
    
    args = parser.parse_args()
    
    helper = MqttMigrationHelper(project_root)
    
    if args.check_imports:
        issues = helper.check_imports()
        if issues:
            print(f"\n❌ Import-Probleme gefunden in {len(issues)} Dateien:")
            for file_path, file_issues in issues.items():
                print(f"\n📄 {file_path}:")
                for issue in file_issues:
                    print(f"  - {issue}")
        else:
            print("\n✅ Keine Import-Probleme gefunden!")
    
    elif args.fix_imports:
        corrections = helper.fix_imports(args.dry_run)
        if corrections:
            status = "🔍 [DRY RUN] " if args.dry_run else "✅ [FIXED] "
            print(f"\n{status}Import-Korrekturen in {len(corrections)} Dateien:")
            for file_path, count in corrections.items():
                print(f"  - {file_path}: {count} Korrekturen")
            
            if args.dry_run:
                print("\n🔧 Führe ohne --dry-run aus um Änderungen zu schreiben")
        else:
            print("\n✅ Keine Import-Korrekturen erforderlich!")
    
    elif args.generate_template:
        template_code = helper.generate_service_template(args.generate_template)
        template_file = project_root / f"tools/{args.generate_template}_service_template.py"
        
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_code)
        
        print(f"✅ Service-Template generiert: {template_file}")
        print(f"📝 Verwende das Template als Basis für {args.generate_template}")
    
    elif args.validate_service:
        service_file = Path(args.validate_service)
        if not service_file.exists():
            print(f"❌ Service-Datei nicht gefunden: {service_file}")
            return
        
        results = helper.validate_service(service_file)
        
        print(f"\n📊 Validierungs-Ergebnisse für {service_file}:")
        
        if results["errors"]:
            print("\n❌ Fehler:")
            for error in results["errors"]:
                print(f"  - {error}")
        
        if results["warnings"]:
            print("\n⚠️ Warnungen:")
            for warning in results["warnings"]:
                print(f"  - {warning}")
        
        if results["suggestions"]:
            print("\n💡 Vorschläge:")
            for suggestion in results["suggestions"]:
                print(f"  - {suggestion}")
        
        if not any([results["errors"], results["warnings"], results["suggestions"]]):
            print("\n✅ Service erfüllt alle MQTT-Standards!")
    
    elif args.summary:
        summary = helper.migration_summary()
        
        print("\n📊 MQTT-Migrations-Zusammenfassung:")
        print("=" * 50)
        
        # Import-Issues
        if summary["import_issues"]:
            print(f"\n❌ Import-Probleme: {len(summary['import_issues'])} Dateien")
            for file_path in summary["import_issues"].keys():
                print(f"  - {file_path}")
        else:
            print("\n✅ Keine Import-Probleme gefunden")
        
        # Validation Results
        print(f"\n📋 Service-Validierung:")
        for service, results in summary["validation_results"].items():
            error_count = len(results.get("errors", []))
            warning_count = len(results.get("warnings", []))
            
            if error_count > 0:
                print(f"  ❌ {service}: {error_count} Fehler, {warning_count} Warnungen")
            elif warning_count > 0:
                print(f"  ⚠️ {service}: {warning_count} Warnungen")
            else:
                print(f"  ✅ {service}: Alle Standards erfüllt")
        
        # Recommendations
        print(f"\n🎯 Empfehlungen:")
        for recommendation in summary["migration_recommendations"]:
            print(f"  {recommendation}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
