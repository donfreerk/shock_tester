#!/usr/bin/env python3
"""
Integration-Test für Phase-Shift-Konsolidierung

Testet, dass alle Services die zentrale suspension_core.egea Implementation verwenden
und die Migration erfolgreich war.
"""

import sys
import traceback
import numpy as np
from pathlib import Path

# Sicherstellen, dass common im PYTHONPATH ist
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "common"))

def test_central_egea_import():
    """Test: Zentrale EGEA-Implementation kann importiert werden"""
    print("🧪 Test 1: Zentrale EGEA-Implementation importieren...")
    
    try:
        from suspension_core.egea import EGEAPhaseShiftProcessor, PhaseShiftProcessor
        print("  ✅ suspension_core.egea.EGEAPhaseShiftProcessor")
        print("  ✅ suspension_core.egea.PhaseShiftProcessor (Alias)")
        
        # Processor initialisieren
        processor = EGEAPhaseShiftProcessor()
        print("  ✅ EGEAPhaseShiftProcessor erfolgreich initialisiert")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def test_test_controller_wrapper():
    """Test: Test Controller Service nutzt zentrale Implementation"""
    print("\n🧪 Test 2: Test Controller Service Wrapper...")
    
    try:
        from backend.test_controller_service.phase_shift_processor import PhaseShiftProcessor
        print("  ✅ Test Controller PhaseShiftProcessor importiert")
        
        # Initialisieren
        processor = PhaseShiftProcessor()
        print("  ✅ Test Controller PhaseShiftProcessor initialisiert")
        
        # Prüfen, ob zentrale Implementation verwendet wird
        if hasattr(processor, 'egea_processor'):
            print("  ✅ Nutzt zentrale EGEA-Implementation (egea_processor gefunden)")
            return True
        else:
            print("  ❌ Keine zentrale Implementation gefunden")
            return False
            
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def test_frontend_background_processor():
    """Test: Frontend Background Processor nutzt zentrale Implementation"""
    print("\n🧪 Test 3: Frontend Background Processor...")
    
    try:
        from frontend.desktop_gui.processing.background_processor import PhaseShiftProcessor
        print("  ✅ Frontend PhaseShiftProcessor importiert")
        
        # Initialisieren
        processor = PhaseShiftProcessor()
        print("  ✅ Frontend PhaseShiftProcessor initialisiert")
        
        # Prüfen, ob zentrale Implementation verwendet wird
        if hasattr(processor, 'egea_processor'):
            print("  ✅ Nutzt zentrale EGEA-Implementation (egea_processor gefunden)")
            return True
        else:
            print("  ❌ Keine zentrale Implementation gefunden")
            return False
            
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def test_pi_processing_service():
    """Test: Pi Processing Service nutzt zentrale Implementation"""
    print("\n🧪 Test 4: Pi Processing Service...")
    
    try:
        from backend.pi_processing_service.main import PiProcessingService
        print("  ✅ PiProcessingService importiert")
        
        # Prüfen, ob legacy Service noch existiert
        try:
            from backend.pi_processing_service import pi_processing_service_old
            print("  ⚠️  Legacy pi_processing_service noch importierbar")
            return False
        except ImportError:
            print("  ✅ Legacy pi_processing_service erfolgreich entfernt")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def test_functional_calculation():
    """Test: Funktionaler Test der Phase-Shift-Berechnung"""
    print("\n🧪 Test 5: Funktionale Phase-Shift-Berechnung...")
    
    try:
        # Zentrale Implementation
        from suspension_core.egea import EGEAPhaseShiftProcessor
        processor = EGEAPhaseShiftProcessor()
        
        # Test-Daten generieren
        time_array = np.linspace(0, 2.0, 1000)
        platform_position = 3.0 * np.sin(2 * np.pi * 10 * time_array)  # 10 Hz, 3mm Amplitude
        tire_force = 500 + 100 * np.sin(2 * np.pi * 10 * time_array + np.pi/6)  # 500N static, 30° phase
        static_weight = 500.0
        
        print(f"  📊 Test-Daten: {len(time_array)} Punkte, 10Hz, 30° Phase")
        
        # Berechnung durchführen
        result = processor.calculate_phase_shift_advanced(
            platform_position=platform_position,
            tire_force=tire_force,
            time_array=time_array,
            static_weight=static_weight
        )
        
        print(f"  📈 Ergebnis: Valid={result.is_valid}")
        
        if result.is_valid and result.min_phase_shift is not None:
            print(f"  ✅ Min. Phasenverschiebung: {result.min_phase_shift:.1f}°")
            print(f"  ✅ Frequenz: {result.min_phase_frequency:.1f} Hz")
            print(f"  ✅ Perioden analysiert: {len(result.periods) if result.periods else 0}")
            return True
        else:
            print(f"  ❌ Ungültiges Ergebnis")
            return False
            
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def test_wrapper_compatibility():
    """Test: Frontend und Test Controller Wrapper sind kompatibel"""
    print("\n🧪 Test 6: Wrapper-Kompatibilität...")
    
    try:
        # Frontend Wrapper
        from frontend.desktop_gui.processing.background_processor import PhaseShiftProcessor as FrontendProcessor
        # Test Controller Wrapper  
        from backend.test_controller_service.phase_shift_processor import PhaseShiftProcessor as TestControllerProcessor
        
        # Test-Daten
        time_data = np.linspace(0, 1.0, 500)
        platform_data = 3.0 * np.sin(2 * np.pi * 12 * time_data)
        force_data = 600 + 80 * np.sin(2 * np.pi * 12 * time_data + np.pi/4)
        static_weight = 600.0
        
        # Frontend-Berechnung
        frontend_proc = FrontendProcessor()
        frontend_result = frontend_proc.calculate_phase_shift(
            platform_data, force_data, time_data, static_weight
        )
        
        # Test Controller-Berechnung
        test_proc = TestControllerProcessor()
        test_result = test_proc.calculate_phase_shift(
            platform_data.tolist(), force_data.tolist(), time_data.tolist(), static_weight
        )
        
        print(f"  📊 Frontend Result: Success={frontend_result.get('success', False)}")
        print(f"  📊 Test Controller Result: Valid={test_result.get('valid', False)}")
        
        if (frontend_result.get('success', False) and test_result.get('valid', False)):
            frontend_phase = frontend_result.get('min_phase_shift', 0)
            test_phase = test_result.get('min_phase_shift', 0)
            
            print(f"  🔍 Frontend Phase: {frontend_phase:.1f}°")
            print(f"  🔍 Test Controller Phase: {test_phase:.1f}°")
            
            # Phasen sollten ähnlich sein (Toleranz 5°)
            if abs(frontend_phase - test_phase) < 5.0:
                print(f"  ✅ Wrapper-Ergebnisse konsistent (Δ={abs(frontend_phase - test_phase):.1f}°)")
                return True
            else:
                print(f"  ❌ Wrapper-Ergebnisse inkonsistent (Δ={abs(frontend_phase - test_phase):.1f}°)")
                return False
        else:
            print(f"  ❌ Ein oder beide Wrapper sind fehlgeschlagen")
            return False
            
    except Exception as e:
        print(f"  ❌ Fehler: {e}")
        traceback.print_exc()
        return False

def main():
    """Führt alle Konsolidierungs-Tests durch"""
    print("🎯 Fahrwerkstester Phase-Shift-Konsolidierung Validation")
    print("=" * 60)
    
    tests = [
        test_central_egea_import,
        test_test_controller_wrapper, 
        test_frontend_background_processor,
        test_pi_processing_service,
        test_functional_calculation,
        test_wrapper_compatibility
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Test-Fehler: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"🎯 Test-Ergebnisse: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALLE TESTS BESTANDEN - Konsolidierung erfolgreich!")
        print("\n✅ Phase-Shift-Implementierungen sind erfolgreich konsolidiert")
        print("✅ Alle Services nutzen die zentrale suspension_core.egea Implementation")
        print("✅ Wrapper sind kompatibel und funktional")
        return True
    else:
        print("🚨 EINIGE TESTS FEHLGESCHLAGEN - Konsolidierung unvollständig")
        print(f"\n❌ {failed} von {len(tests)} Tests fehlgeschlagen")
        print("❌ Bitte prüfen Sie die obigen Fehlermeldungen")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
