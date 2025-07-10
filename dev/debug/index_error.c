//---------------------------------------------------------------------------
// XC8 Array Index-Error Debugging
// Zeigt korrekte Array-Handling-Methoden für PIC18F248
//
// DEBUG-ZWECK: Lösung für Array-Index-Probleme in EUSAMA-Code
//---------------------------------------------------------------------------
#include <xc.h>
#include <stdint.h>
#include <string.h>

// Define crystal frequency for delay functions
#define _XTAL_FREQ 16000000  // 16 MHz crystal

typedef struct {
    uint16_t    adv;        // AD-Value
    uint16_t    weight;     // zugehöriges Gewicht in kg
} AD2WEIGHT; // sizeof(AD2WEIGHT) == 4

/*
PROBLEM IDENTIFIZIERT:
Der ursprüngliche Code hatte Array-Index-Überläufe bei:
- scaleAd2weight[8*4] Array-Zugriff
- Pointer-Arithmetik mit geber_nummer * 4

LÖSUNGSANSÄTZE:

1. SICHER: 2D-Array verwenden
   AD2WEIGHT scaleAd2weight[8][4];
   scaleAd2weight[geber_nummer][scale_index] = value;

2. DEFENSIVE: Bounds-Checking
   if(geber_nummer < 8 && scale_index < 4) { ... }

3. POINTER-ARITHMETIK: Vorsichtige Berechnung
   AD2WEIGHT *a2w = &scaleAd2weight[geber_nummer * 4 + scale_index];
   if((geber_nummer * 4 + scale_index) < (8*4)) { ... }
*/

// XC8 kann mehrdimensionale Arrays UND verwaltet Memory automatisch
AD2WEIGHT  scaleAd2weight[8][4];      // SICHERE 2D-Array-Version

void InitVars(void)
{
    // XC8 Alternative zu clearRAM() 
    memset(scaleAd2weight, 0, sizeof(scaleAd2weight));
}

void ScalesFromCAN_SAFE(void)
{
    uint8_t  geber_nummer = 2;          // Beispiel-Werte für Test
    uint8_t  scale_index = 1;
    uint16_t ad_wert = 512, gew_wert = 75;
    
    // SICHERE VERSION mit Bounds-Checking
    if(geber_nummer < 8 && scale_index < 4) {
        scaleAd2weight[geber_nummer][scale_index].adv = ad_wert;
        scaleAd2weight[geber_nummer][scale_index].weight = gew_wert;
        
        // DEBUG: Status anzeigen (in echtem Code über CAN senden)
        // printf("Geber %d[%d] = AD:%d, Gewicht:%d\n", 
        //        geber_nummer, scale_index, ad_wert, gew_wert);
    }
}

void ScalesFromCAN_POINTER(void)
{
    uint8_t  geber_nummer = 2;
    uint8_t  scale_index = 1;
    uint16_t ad_wert = 512, gew_wert = 75;
    
    // POINTER-VERSION mit Index-Validierung
    uint8_t linear_index = geber_nummer * 4 + scale_index;
    
    if(linear_index < (8*4)) {
        // Sichere Pointer-Berechnung
        AD2WEIGHT *a2w = (AD2WEIGHT*)scaleAd2weight + linear_index;
        a2w->adv = ad_wert;
        a2w->weight = gew_wert;
    }
}

void TestArrayAccess(void)
{
    /*
    TEST-CASES für Array-Zugriff:
    
    GÜLTIG:
    - geber_nummer: 0-7
    - scale_index: 0-3
    - linear_index: 0-31
    
    UNGÜLTIG (verursachen Index-Error):
    - geber_nummer: 8, 9, 255 (Overflow)
    - scale_index: 4, 5, 255 (Overflow)
    - linear_index: 32+ (Array-Grenze überschritten)
    */
    
    // Test verschiedene Zugriffsmuster
    for(uint8_t geber = 0; geber < 8; geber++) {
        for(uint8_t index = 0; index < 4; index++) {
            // SICHER: 2D-Array
            scaleAd2weight[geber][index].adv = geber * 100 + index;
            scaleAd2weight[geber][index].weight = geber * 10 + index;
        }
    }
}

/*
INTEGRATION IN PYTHON-CODE:

Diese C-Debug-Erkenntnisse helfen bei der Python-Implementierung:

1. backend/can_simulator_service/core/egea_simulator.py:
   - Verwende Listen statt mehrdimensionale Arrays
   - Prüfe Array-Grenzen vor Zugriff
   - scale_data = [[None]*4 for _ in range(8)]

2. common/suspension_core/protocols/eusama.py:
   - Validiere geber_nummer (0-7) und scale_index (0-3)
   - Werfe IndexError bei ungültigen Werten
   - Logge Array-Zugriffe für Debugging

3. hardware/eusama_interface.py:
   - Defensive Programmierung bei CAN-Datenverarbeitung
   - Bounds-Checking für alle Array-Operationen
*/

void main(void)    // XC8: void main(void) statt main()
{
    InitVars();
    
    // Teste verschiedene Array-Zugriffsmethoden
    TestArrayAccess();
    ScalesFromCAN_SAFE();
    ScalesFromCAN_POINTER();
    
    for(;;) {
        // Hauptloop - in echtem Code würde hier die CAN-Verarbeitung laufen
    }
}
