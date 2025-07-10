# Fahrwerkstester - Technische Dokumentation

## Inhaltsverzeichnis

1. [Einführung](#einführung)
2. [Messverfahren](#messverfahren)
    - [Phase-Shift-Methode (EGEA)](#phase-shift-methode-egea)
    - [Resonanzprinzip](#resonanzprinzip)
3. [Architektur und Modulstruktur](#architektur-und-modulstruktur)
    - [Übersicht](#übersicht)
    - [Core-Bibliotheken](#core-bibliotheken)
    - [Service-Layer](#service-layer)
    - [Protokollabstraktion](#protokollabstraktion)
    - [Konfigurationsmanagement](#konfigurationsmanagement)
4. [Kommunikationsprotokolle](#kommunikationsprotokolle)
    - [EUSAMA-Protokoll](#eusama-protokoll)
    - [ASA-Livestream-Protokoll](#asa-livestream-protokoll)
5. [Mathematische Berechnungen und Algorithmen](#mathematische-berechnungen-und-algorithmen)
    - [Phasenverschiebungsberechnung](#phasenverschiebungsberechnung)
    - [Resonanzauswertung](#resonanzauswertung)
    - [Dämpfungsverhältnis](#dämpfungsverhältnis)
    - [Reifensteifigkeit](#reifensteifigkeit)
    - [Unwuchtberechnung](#unwuchtberechnung)
6. [Sensoren und Signalverarbeitung](#sensoren-und-signalverarbeitung)
7. [Bewertungskriterien](#bewertungskriterien)
8. [Testdurchführung](#testdurchführung)
9. [Diagnosefunktionen](#diagnosefunktionen)

## Einführung

Der Fahrwerkstester dient zur Prüfung des Dämpfungsverhaltens von Fahrzeugfederungen. Er ermöglicht eine nicht-intrusive
Überprüfung der Stoßdämpferfunktion ohne Demontage am Fahrzeug. Dieses Dokument beschreibt die technischen Details,
mathematischen Berechnungen und Funktionsweisen des implementierten Systems.

Das System unterstützt zwei unterschiedliche Messverfahren:

1. Das klassische Resonanzprinzip
2. Die modernere Phase-Shift-Methode nach EGEA-Spezifikation

## Messverfahren

### Phase-Shift-Methode (EGEA)

Die Phase-Shift-Methode basiert auf der Messung der Phasenverschiebung zwischen Plattformbewegung und
Reifenaufstandskraft. Diese Methode ist standardisiert nach der EGEA-Spezifikation (SPECSUS2018).

#### Funktionsprinzip

- Kontinuierliche Anregung des Fahrwerks durch eine frequenzvariable Schwingung (25 Hz bis 5 Hz)
- Messung der Phasenverschiebung (φ) zwischen Plattformbewegung und vertikaler Reifenaufstandskraft
- Bestimmung des minimalen Phasenwinkels (φmin) im Bereich der Achsmassenresonanz

Die Implementierung dieser Methode ist in der Klasse `PhaseShiftProcessor` in
`/suspension_tester/test_methods/phase_shift/processor.py` zu finden.

#### Gemessene Parameter

- Minimaler Phasenwinkel φmin (Hauptkriterium für Dämpferwirkung)
- Maximale relative Kraftamplitude (RFAmax)
- Reifensteifigkeit (rig)
- Resonanzfrequenz (fres)

### Resonanzprinzip

Das Resonanzprinzip basiert auf der Anregung des Fahrwerks und der Auswertung des freien Ausschwingverhaltens.

#### Funktionsprinzip

- Anregung des Fahrwerks durch einen Exzenterantrieb auf eine Nennfrequenz von ca. 25 Hz
- Abschalten des Motors und Beobachtung des freien Ausschwingverhaltens
- Auswertung der Amplituden und der Dämpfung während des Ausschwingvorgangs

Die Implementierung dieser Methode ist in der Klasse `ResonanceProcessor` in
`/suspension_tester/test_methods/resonance/processor.py` zu finden.

#### Gemessene Parameter

- Amplitude: Maximaler Schwingungsausschlag
- Effektivität: Dämpfungswirkung des Stoßdämpfers (ca. 70% bei intaktem Dämpfer)

## Architektur und Modulstruktur

### Übersicht

Die Software ist modular aufgebaut, um Wiederverwendbarkeit und Wartbarkeit zu maximieren. Die Architektur basiert
auf einer klaren Trennung von Kernkomponenten (Core-Bibliotheken), Anwendungslogik (Service-Layer), 
Protokollimplementierungen und Konfigurationsmanagement.

```
suspension_tester/
├── protocols/              # Protokollimplementierungen
│   ├── base_protocol.py    # Abstrakte Basisklasse für Protokolle
│   ├── eusama_protocol.py  # EUSAMA-Protokollimplementierung
│   ├── asa_protocol.py     # ASA-Livestream-Protokollimplementierung
│   └── protocol_factory.py # Factory für Protokollinstanzen
│
├── lib/                    # Wiederverwendbare Kernbibliotheken
│   ├── can/                # CAN-Kommunikation
│   └── mqtt/               # MQTT-Kommunikation
├── service/                # Anwendungslogik
├── config/                 # Konfigurationsmanagement
└── ...                     # Weitere Module
```

### Core-Bibliotheken

Die Core-Bibliotheken im `lib`-Verzeichnis sind so konzipiert, dass sie unabhängig vom Rest des Projekts verwendet
werden können:

1. **CAN-Modul (`lib/can/`)**:
    - `can_interface.py`: Bietet die zentrale `CanInterface`-Klasse für die CAN-Kommunikation
    - Funktionen:
        - Automatische Baudratenerkennung
        - Nachrichtenvalidierung und -verarbeitung
        - Callback-basierte Event-Verarbeitung
        - Thread-sichere Implementierung

2. **MQTT-Modul (`lib/mqtt/`)**:
    - `mqtt_client.py`: Enthält die verbesserte `MqttClient`-Klasse
    - Funktionen:
        - Robuste Verbindungsbehandlung mit automatischer Wiederverbindung
        - Topic-spezifische Callbacks
        - JSON-Konvertierung und -Validierung
        - Unterstützung für QoS und Retain-Flags

### Service-Layer

Die Service-Layer in `service/suspension_service.py` kapselt die Hauptgeschäftslogik:

- `SuspensionTesterService`: Koordiniert den gesamten Testablauf
    - Hardwarekommunikation
    - Testdurchführung
    - Ergebnisanalyse und -berichterstattung
    - System-Status-Management

### Protokollabstraktion

Die neue Protokollabstraktion in `protocols/` bietet eine einheitliche Schnittstelle für verschiedene CAN-Protokolle:

1. **Basisprotokoll (`base_protocol.py`)**:
   - Definiert die gemeinsame Schnittstelle für alle Protokollimplementierungen
   - Abstrakte Methoden für Motorsteuerung, Callbacks, etc.

2. **EUSAMA-Protokoll (`eusama_protocol.py`)**:
   - Implementiert das EUSAMA-Protokoll für den Fahrwerkstester
   - 1 Mbit/s Bitrate, Extended-IDs mit 'EUS'-Basis
   - Unterstützt Motorsteuerung, Lampensteuerung und Display-Anzeige

3. **ASA-Protokoll (`asa_protocol.py`)**:
   - Implementiert das ASA-Livestream-Protokoll (für Kompatibilität)
   - 250/125 kBit/s Bitrate, Extended-IDs mit 'ALS'-Basis

4. **Protokoll-Factory (`protocol_factory.py`)**:
   - Erzeugt die richtige Protokollinstanz basierend auf der Konfiguration
   - Vereinfacht den Wechsel zwischen verschiedenen Protokollen

Diese Abstraktion ermöglicht es, die Business-Logik unabhängig vom verwendeten Kommunikationsprotokoll zu halten.

### Konfigurationsmanagement

Das Konfigurationsmanagement in `config/config_manager.py` bietet:

- Hierarchisches Konfigurationsmodell
- Multiple Konfigurationsquellen (Standardwerte, Dateien, Umgebungsvariablen)
- Validierung und Typprüfung
- Zentralen Zugangspunkt für alle Konfigurationsparameter

Die `ConfigManager`-Klasse ist als Singleton implementiert und ermöglicht den konsistenten Zugriff auf
Konfigurationsparameter im gesamten System.

## Kommunikationsprotokolle

### EUSAMA-Protokoll

Das EUSAMA-Protokoll ist das primäre Kommunikationsprotokoll für den Fahrwerkstester. Es definiert die CAN-Kommunikation 
über Extended-IDs (29-Bit) basierend auf dem ASCII-Code 'EUS'.

#### CAN-Bitrate

- 1 Mbit/s (hochauflösend für präzise Messungen)

#### CAN-ID-Struktur

Extended-IDs (29-Bit) bestehend aus:
- 24-Bit Anwendungs-ID: ASCII 'EUS' (0x414e53)
- 5-Bit Subcode: Identifiziert den Nachrichtentyp

ID-Bereiche:
- 0x08AAAA60 - 0x08AAAA6F: Nachrichten vom Schrank an externe Geräte
- 0x08AAAA70 - 0x08AAAA7F: Nachrichten von externen Geräten an den Schrank

#### Wichtige Nachrichtentypen

1. **Rohdaten (IDs 0x08AAAA60, 0x08AAAA61)**:
   - Übertragen DMS-Werte (Dehnungsmessstreifen)
   - 8 Werte aufgeteilt in 2 Nachrichten (links/rechts)
   - DMS-Werte haben Bereich 0-1023

2. **Motor-Steuerung (ID 0x08AAAA71)**:
   - Kontrolliert den Start/Stop der Testmotoren
   - Erste Byte: Motor-Maske (0x01=links, 0x02=rechts, 0x00=stop)
   - Zweite Byte: Laufzeit in Sekunden

3. **Display-Steuerung (ID 0x08AAAA72)**:
   - Steuert 3 Displays (links, rechts, Differenz)
   - Für Anzeige von Testergebnissen und Statusinformationen

4. **Lampen-Steuerung (ID 0x08AAAA73)**:
   - Kontrolle der Lampen am Fahrwerkstester
   - Bitmaske für verschiedene Lampen (links, Einfahrt, rechts)

5. **Top-Position (ID 0x08AAAA67)**:
   - Signalisiert, wenn obere Position der Platte erreicht wurde
   - Wichtig für Synchronisation der Testzyklen

#### Implementierung

Die EUSAMA-Protokollimplementierung findet sich in `protocols/eusama_protocol.py`. Sie bietet Methoden für:
- Senden von Motorkommandos
- Steuern der Lampen und Displays
- Verarbeiten von empfangenen Sensordaten
- Callback-basierte Ereignisbehandlung

## Mathematische Berechnungen und Algorithmen

### Phasenverschiebungsberechnung

Die Phasenverschiebung wird in der Klasse `PhaseShiftProcessor` in der Methode `calculate_phase_shift()` berechnet. Die Berechnung erfolgt durch folgende Schritte:

1. **Frequenzbestimmung**: Für jeden Zyklus wird die Frequenz bestimmt durch `frequency = 1.0 / cycle_time`, wobei `cycle_time` die Zeit zwischen zwei aufeinanderfolgenden Maxima der Plattformposition ist.

2. **Schnittpunktbestimmung**: Für jeden Zyklus werden die Schnittpunkte des Kraftsignals mit dem statischen Gewicht (Fst) identifiziert:
   ```python
   # Schnittpunkte mit dem statischen Gewicht finden (Fup, Fdn)
   for j in range(1, len(cycle_force)):
       if (cycle_force[j - 1] < static_weight < cycle_force[j]) or (
           cycle_force[j - 1] > static_weight > cycle_force[j]
       ):
           # Lineares Interpolieren, um genaueren Kreuzungspunkt zu finden
           frac = (static_weight - cycle_force[j - 1]) / (
               cycle_force[j] - cycle_force[j - 1]
           )
           cross_time = cycle_time_rel[j - 1] + frac * (
               cycle_time_rel[j] - cycle_time_rel[j - 1]
           )
           crossings.append(cross_time)
   ```

3. **Prüfung der RFstF-Bedingungen**: Die Schnittpunkte werden nur berücksichtigt, wenn sie innerhalb der gültigen
   Bereiche liegen:
   ```python
   # Prüfe RFstFMin und RFstFMax Bedingungen
   if len(crossings) >= 2:
       delta_f = max(cycle_force) - min(cycle_force)
       f_min_limit = min(cycle_force) + delta_f * self.rfst_fmin / 100
       f_max_limit = max(cycle_force) - delta_f * self.rfst_fmax / 100

       # Prüfe, ob Kreuzungspunkte in gültigen Bereichen liegen
       if f_min_limit < static_weight < f_max_limit:
            # Weitere Berechnung...
   ```

4. **Berechnung der Phasenverschiebung**: Die Phasenverschiebung wird aus dem Referenzpunkt und der Zyklusdauer
   berechnet:
   ```python
   # Berechne Fref als Mittelpunkt zwischen Down und Up
   fref = (crossings[0] + crossings[1]) / 2.0

   # Berechne die Phasenverschiebung (in Grad)
   top_p_time = cycle_time_rel[0]  # TOPp(i) ist Start des Zyklus
   phase_shift = (fref - top_p_time) * frequency * 360

   # Normalisiere zwischen 0° und 180°
   phase_shift = phase_shift % 360
   if phase_shift > 180:
       phase_shift = 360 - phase_shift
   ```

5. **Minimum-Detektion**: Es wird das Minimum der berechneten Phasenverschiebungen bestimmt:
   ```python
   min_idx = np.argmin(phase_shifts)
   min_phase = phase_shifts[min_idx]
   min_phase_freq = frequencies[min_idx]
   ```

Die Phasenverschiebung wird in Grad angegeben und sollte für einen gut funktionierenden Dämpfer über 35° liegen (
EGEA-Kriterium).

### Resonanzauswertung

Die Resonanzauswertung erfolgt in der Klasse `ResonanceProcessor` in der Methode `process_test()`. Der Algorithmus umfasst:

1. **Gewichtsberechnung**: Aus der Spannungsdifferenz wird das Gewicht berechnet:
   ```python
   voltage_difference = initial_voltage - voltage_data[0]
   weight = voltage_difference * weight_factor
   ```

2. **Amplitudenbestimmung**: Die maximale Amplitude wird aus den positiven und negativen Ausschlägen ermittelt:
   ```python
   max_positive = max(positive_peaks) - equilibrium
   max_negative = equilibrium - min(negative_peaks)
   max_amplitude = max(max_positive, max_negative)
   ```

3. **Effektivitätsberechnung**: Die Effektivität wird als Verhältnis zur idealen Amplitude berechnet:
   ```python
   ideal_amplitude = self._calculate_ideal_amplitude(weight)
   if amplitude > 0:
       effectiveness = (ideal_amplitude / amplitude) * 70  # 70% bei Idealkurve
       # Effektivität auf 0-100% begrenzen
       effectiveness = max(0, min(100, effectiveness))
   else:
       effectiveness = 0
   ```

Die ideale Amplitude wird basierend auf dem Radgewicht ermittelt, wobei ein lineares Modell verwendet wird: `ideal_amplitude = weight * 0.05`.

### Dämpfungsverhältnis

Das Dämpfungsverhältnis wird in `processing/damping_ratio.py` berechnet. Die Berechnung erfolgt nach der physikalisch korrekten Formel:

```python
def calculate_damping_ratio(vehicle_type, weight, spring_constant, damping_constant):
    # Ungefederte Masse basierend auf Fahrzeugtyp bestimmen
    unsprung_mass = VEHICLE_TYPES[vehicle_type]["UNSPRUNG_MASS"]

    # Gefederte Masse berechnen
    sprung_mass = weight - unsprung_mass

    # Dämpfungsverhältnis berechnen
    damping_ratio = damping_constant / (2 * np.sqrt(spring_constant * sprung_mass))

    return damping_ratio
```

Diese Formel entspricht der Definition ζ = c / (2 * √(k * m)), wobei c die Dämpfungskonstante, k die Federsteifigkeit und m die gefederte Masse ist.

Zusätzlich kann das Dämpfungsverhältnis auch aus der Phasenverschiebung berechnet werden:

```python
def calculate_damping_from_phase_shift(phase_shift_deg):
	# Umrechnung von Grad in Radianten
	phase_shift_rad = np.radians(phase_shift_deg)

	# EGEA-Formel für die Umrechnung von Phasenwinkel in Dämpfungsverhältnis
	damping_ratio = np.sin(phase_shift_rad) / 2

	return damping_ratio
```

### Reifensteifigkeit

Die Reifensteifigkeit (rig) wird nach der EGEA-Spezifikation berechnet. Die Implementierung findet sich in der `PhaseShiftProcessor`-Klasse:

```python
def calculate_rigidity(self, force_amplitude, platform_amplitude):
    a_rig = 0.571
    b_rig = 46.0
    rigidity = a_rig * (force_amplitude / platform_amplitude) + b_rig

    return rigidity
```

Diese Formel verwendet die Parameter a_rig = 0.571 und b_rig = 46.0, wie in den EGEA-Spezifikationen vorgegeben.

### Unwuchtberechnung

Die Unwucht zwischen linkem und rechtem Rad wird für verschiedene Parameter berechnet, um Asymmetrien im Fahrwerk zu erkennen. Die Berechnung findet sich in der `SuspensionTestController`-Klasse:

```python
def _calculate_difference_percent(self, val1, val2):
    if val1 == 0 and val2 == 0:
        return 0

    max_val = max(abs(val1), abs(val2))
    if max_val == 0:
        return 0

    return abs(val1 - val2) / max_val * 100
```

Diese Berechnung wird für:
- Minimale Phasenverschiebung (φmin)
- Maximale relative Kraftamplitude (RFAmax)
- Reifensteifigkeit (rig)

verwendet.

## Sensoren und Signalverarbeitung

### Gewichtssensoren

Die Gewichtssensoren werden durch die Klasse `WeightSensor` in `hardware/sensors/weight_sensor.py` implementiert. Der
Sensor misst die statische und dynamische Reifenaufstandskraft mit folgenden Spezifikationen:

- Messbereich: 100-1100 daN pro Rad (statisch), bis zu 2200 daN (dynamisch)
- Genauigkeit: ±6 daN (0-300 daN), ±2% vom Messwert (300-1100 daN)

Die Klasse implementiert Methoden zur statischen Gewichtsmessung (`get_weights()`) und Nullkalibrierung (
`zero_calibration()`).

### Positionssensoren

Die Positionssensoren werden durch die Klasse `PositionSensor` in `hardware/sensors/position_sensor.py` implementiert.
Diese berührungslosen Weggeber messen die vertikale Plattformposition und haben folgende Eigenschaften:

- Messbereich: 0-10 VDC
- Abtastrate: ausreichend für Frequenzen bis 25 Hz (typisch ≥ 1000 Hz)

Die Klasse bietet Methoden zur Positionsmessung (`get_position()`) und zur Aufnahme von Wellenformen (
`acquire_waveform()`).

### Signalfilterung

Die Signalfilterung erfolgt gemäß den EGEA-Spezifikationen, insbesondere für die Phasenberechnung. Die dynamische
Kalibrierung der Plattform erfolgt, um genaue Messungen zu gewährleisten.

Für die Phasenberechnung werden spezielle Tiefpassfilter nach der Kaiser-Reed-Methode (Nearly equal ripple
approximation) verwendet. Die Filtereigenschaften sind:

- PassMulPh = 2
- StopMulPh = 4
- ε = 0.01

Zur Sicherstellung der Messgenauigkeit wird eine dynamische Kalibrierung durchgeführt, bei der die
Plattformeigenfrequenz bestimmt und kompensiert wird. Die maximal zulässige Fehlergrenze beträgt 4 N/Hz im Messbereich
6-18 Hz.

## Bewertungskriterien

### Absolute Kriterien

Die absoluten Bewertungskriterien basieren auf festen Schwellenwerten:

1. **Minimaler Phasenwinkel (φmin)**:
    - Gut: φmin ≥ 35° (entspricht Dämpfungsgrad ≥ 0.1)
    - Schlecht: φmin < 35° (entspricht Dämpfungsgrad < 0.1)

   Die Implementierung findet sich in der Methode `evaluate_phase_shift()` der `PhaseShiftProcessor`-Klasse:
   ```python
   def evaluate_phase_shift(self, phase_data, vehicle_type):
       min_phase = phase_data["min_phase_shift"]
       if min_phase is None:
           return {
               "pass": False,
               "reason": "Keine gültige Phasenverschiebung gemessen",
           }

       # Absolutes Kriterium (AC_φmin = 35°)
       absolute_threshold = TEST_PARAMETERS["PHASE_SHIFT_MIN"]
       absolute_pass = min_phase >= absolute_threshold

       return {
           "pass": absolute_pass,
           "min_phase": min_phase,
           "threshold": absolute_threshold,
           "integer_min_phase": int(min_phase),  # iφmin (abgerundet)
       }
   ```

2. **Reifensteifigkeit (rig)**:
    - Optimaler Bereich: 160-400 N/mm
    - Zu niedrig (< 160 N/mm): Warnung (Reifen zu wenig aufgepumpt)
    - Zu hoch (> 400 N/mm): Warnung (Reifen zu stark aufgepumpt)

### Relative Kriterien

Die relativen Kriterien vergleichen die Messwerte zwischen linkem und rechtem Rad einer Achse:

1. **Phasenwinkel-Ungleichgewicht**:
    - Maximale Differenz zwischen links und rechts: 30%
    - Formel: Dφmin = (|φmin,links - φmin,rechts| / max(φmin,links, φmin,rechts)) * 100%

2. **Kraftamplituden-Ungleichgewicht**:
    - Maximale Differenz zwischen links und rechts: 30%

3. **Reifensteifigkeits-Ungleichgewicht**:
    - Maximale Differenz zwischen links und rechts: 35%

Die Berechnung dieser Ungleichgewichte erfolgt in der `SuspensionTestController`-Klasse mit der Methode
`_calculate_difference_percent()`.

## Testdurchführung

Der Testablauf wird durch die `SuspensionTesterService`-Klasse in `service/suspension_service.py` koordiniert. Diese
Klasse ist für den gesamten Lebenszyklus des Tests verantwortlich:

1. **Initialisierung**: Hardware und Kommunikation einrichten
2. **Fahrzeugerkennung**: Warten auf ein Fahrzeug auf der Testplattform
3. **Testdurchführung**: Ausführen des konfigurierten Testverfahrens
4. **Ergebnisanalyse**: Bewertung der Messergebnisse
5. **Berichterstattung**: Übermittlung der Ergebnisse über MQTT
6. **Abschluss**: Warten, bis das Fahrzeug die Plattform verlässt

Die Testdurchführung kann über die Konfiguration angepasst werden, indem die entsprechenden Parameter im `ConfigManager`
gesetzt werden.

Der Testablauf wird durch die Klasse `SuspensionTestController` in `processing/suspension_test.py` koordiniert. Ein
typischer Testablauf umfasst:

### Phase-Shift-Methode

1. **Statische Gewichtsmessung**: Messung der Radlasten im Ruhezustand
2. **Anregung bei 25 Hz**: Bestimmung der Reifensteifigkeit
3. **Frequenzvariation**: Kontinuierlicher Frequenzabfall von 18 Hz auf 6 Hz (Dauer mindestens 7,5 Sekunden)
4. **Messung der Signale**: Erfassung von Reifenaufstandskraft und Plattformposition
5. **Berechnung der Phasenverschiebung**: Bestimmung des minimalen Phasenwinkels
6. **Auswertung**: Vergleich mit den absoluten und relativen Kriterien

### Resonanzmethode

1. **Statische Gewichtsmessung**: Messung der Radlasten im Ruhezustand
2. **Anregung**: Motorstart und Anregung des Fahrwerks mit ca. 25 Hz
3. **Ausschwingvorgang**: Motorabschaltung und Beobachtung des freien Ausschwingverhaltens
4. **Amplitudenbestimmung**: Messung des maximalen Schwingungsausschlags
5. **Effektivitätsberechnung**: Berechnung der Dämpfungswirkung
6. **Auswertung**: Vergleich zwischen linkem und rechtem Rad

## Diagnosefunktionen

Das System bietet zusätzliche Diagnosefunktionen, insbesondere die Geräuschsuche, die in der Klasse
`NoiseSearchController` in `features/noise_search.py` implementiert ist.

### Geräuschsuche

Die Geräuschsuche ermöglicht das manuelle Steuern der Anregungsfrequenz, um Geräuschquellen im Fahrzeug zu
identifizieren:

1. **Einfache Geräuschsuche**: Anregung einer Seite mit 25 Hz
2. **Frequenzgesteuerte Geräuschsuche**: Manuelle Steuerung der Frequenz über Tasten

Die Implementierung umfasst Methoden zum Starten der linken/rechten Seite, zum Erhöhen/Verringern der Frequenz und zum
Stoppen der Geräuschsuche.