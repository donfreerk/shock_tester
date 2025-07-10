# EGEA Phase_Shift Method for Suspension Testing

Die EGEA (European Garage Equipment Association) phase_shift Methode stellt einen bedeutenden Fortschritt in der
Fahrzeugprüftechnik dar, der traditionelle EUSAMA-Verfahren durch erweiterte Phasenverschiebungsanalyse ergänzt. **Die
Methode misst sowohl die Kraftamplitude als auch die Phasenbeziehung zwischen der Anregung der Prüfplatte und der
resultierenden Kontaktkraft des Reifens, wodurch eine präzisere Dämpferdiagnose ermöglicht wird.** Diese innovative
Herangehensweise wurde ursprünglich von der amerikanischen SAE vorgeschlagen und wird seit 2011 erfolgreich im
belgischen GOCA-System mit 4,5 Millionen jährlich geprüften Fahrzeugen eingesetzt.

## Mathematische Grundlagen der Phase_Shift Berechnung

### Grundlegende Phasenverschiebungsformel nach EGEA

Die fundamentale Phasenverschiebungsberechnung für die Fahrwerksprüfung basiert auf der Beziehung zwischen gedämpfter
und ungedämpfter Eigenfrequenz:

**φ = arctan(ωD/ωN)**

Wobei:

- φ = Phasenverschiebungswinkel (Grad oder Radiant)
- ωD = gedämpfte Eigenfrequenz
- ωN = ungedämpfte Eigenfrequenz

Für die Frequenzbereichsanalyse wird die Phasenverschiebung zwischen Anregung und Antwort berechnet:

**φ(ω) = arctan(2ζω/ωn / (1 - (ω/ωn)²))**

Wobei:

- ζ = Dämpfungsgrad
- ω = Anregungsfrequenz
- ωn = Eigenfrequenz

### Berechnung des minimalen Phasenverschiebungswertes φmin

Der **φmin-Wert repräsentiert die minimale Phasenverschiebung zwischen der Schwingplattform-Anregung und der
Rad-Kontaktkraft-Antwort bei der Resonanzfrequenz**. Die mathematische Formulierung erfolgt über:

**φmin = minimum phase angle zwischen Anregungssignal und Kraftantwortsignal**

Bei der Resonanzfrequenz korreliert die Phasenverschiebung direkt mit der Dämpfung:
**tan(φ) = 2ζ × (ω/ωn) / (1 - (ω/ωn)²)**

### RFAmax Berechnung (Relative Force Amplitude)

Die traditionelle EUSAMA-Formel wird durch die EGEA-Methode erweitert:

**EUSAMA rate = (Fmin/Fstatic) × 100%**

Die erweiterte EGEA-Methode kombiniert EUSAMA mit Phasenverschiebungsanalyse:
**RFAmax = Maximum relative force amplitude during frequency sweep**
**RFA(ω) = |F(ω)|/Fstatic**

## Zusammenhang zwischen Phasenverschiebung und Dämpferqualität

Die Phasenverschiebung zeigt eine **nahezu lineare Beziehung zur Dämpferqualität**, was einen entscheidenden Vorteil
gegenüber herkömmlichen Methoden darstellt. Der Dämpfungsgrad wird mathematisch berechnet als:

**ζ = C/(2√(km))**

Wobei C der Dämpfungskoeffizient ist.

**Qualitätsbewertungskriterien:**

- Guter Dämpfer: φmin im spezifizierten Bereich (typisch 20°-45°)
- Schlechter Dämpfer: φmin außerhalb akzeptabler Grenzen
- Kritische Dämpfung: φ = 90° bei Resonanz

Die **lineare Monotonie der phase_shift Methode** bietet vorhersagbarere und konsistentere Ergebnisse im Vergleich zum
alleinigen EUSAMA-Koeffizienten.

## Verfügbare Python-Implementierungen und Algorithmen

### Grundlegende Bibliotheken für Signalverarbeitung

Obwohl keine spezifischen EGEA-Implementierungen öffentlich verfügbar sind, bieten mehrere Python-Bibliotheken die
notwendigen Grundlagen:

**SciPy Signal Processing für Phasenverschiebungsberechnung:**

```python
from scipy.signal import hilbert, correlate
import numpy as np


def calculate_phase_shift(signal1, signal2, fs):
	correlation = correlate(signal1, signal2, mode='full')
	lags = np.arange(-len(signal2) + 1, len(signal1))
	lag = lags[np.argmax(correlation)]
	phase_shift = 2 * np.pi * lag / fs
	return phase_shift


def phase_analysis(signal):
	analytic_signal = hilbert(signal)
	amplitude_envelope = np.abs(analytic_signal)
	instantaneous_phase = np.unwrap(np.angle(analytic_signal))
	return amplitude_envelope, instantaneous_phase
```

**FFT-basierte Phasenverschiebungsimplementierung:**

```python
def calculate_phase_difference_fft(signal1, signal2):
	fft1 = fft(signal1)
	fft2 = fft(signal2)

	idx1 = np.argmax(np.abs(fft1))
	idx2 = np.argmax(np.abs(fft2))

	phase_diff = np.angle(fft2[idx2]) - np.angle(fft1[idx1])
	return np.rad2deg(phase_diff)
```

### Relevante Fahrwerk-Repositories

**Verfügbare Open-Source-Implementierungen:**

- **bechrist/suspension_designer**: Fahrwerkskinematik-Simulation (Python 3.11)
- **nrsyed/half-car**: Fahrzeug-Halbwagenmodell mit Differentialgleichungslöser
- **tarikdzanic/Suspension-Dynamics-Simulator**: Umfassender Fahrwerksdynamik-Simulator

Diese Repositories bieten Grundlagen für die Implementierung von EGEA-Testalgorithmen, erfordern jedoch Anpassungen für
spezifische phase_shift-Berechnungen.

## Frequenzvariationsfunktion

Die Frequenzvariationsfunktion basiert auf dem **Quarter-Car-Modell** mit einer Transfer-Funktion:

**H(s) = (cs + k) / (ms² + cs + k)(mus² + cs + k + kt)**

Wobei:

- m = gefederte Masse
- mu = ungefederte Masse
- c = Dämpfungskoeffizient
- k = Federsteifigkeit
- kt = Reifensteifigkeit

**Frequenzantwortfunktion:**
**|H(jω)| = |Numerator(jω)| / |Denominator(jω)|**
**φ(ω) = arg[H(jω)] = arg[Numerator(jω)] - arg[Denominator(jω)]**

Die Resonanzfrequenz wird berechnet als:
**ωr = ωn√(1-2ζ²)** für untergedämpfte Systeme

## Praktische Implementierungsdetails für die Signalverarbeitung

### Signalerfassung und Vorverarbeitung

**Kernsignaltypen:**

- Verschiebungssignale von Vibrationsplattformen (Positionsrückmeldung)
- Kraftsignale von Kraftmesszellen/Transducern
- Beschleunigungssignale von Beschleunigungssensoren
- Phasenreferenzsignale für Anregungstiming

**Abtastratenanforderungen:**

- Minimum: 10x maximale Analysefrequenz (500 Hz für 50 Hz max.)
- Empfohlen: 20-50x Überabtastung für Phasengenauigkeit (1-2,5 kHz)
- Echtzeitsysteme: Bis zu 100 kHz für hochpräzise Phasenmessungen

**Filterungsanforderungen:**

- Anti-Aliasing: Butterworth- oder Bessel-Filter mit 60 dB/Oktave
- Grenzfrequenz: 30-60% der Nyquist-Frequenz
- Phasenlineare Filter bevorzugt zur Erhaltung von Phasenbeziehungen

### Hardware-Anforderungen

**Kernhardware-Komponenten:**

- Mehrkanal-Datenerfassungssysteme
- Kraftaufnehmer: Piezoelektrisch oder dehnungsmessstreifenbasiert (0,1% Genauigkeit)
- Wegaufnehmer: LVDT, Seilpotentiometer oder Encoder
- Vibrationsplattformen: Elektromagnetische oder servo-elektrische Aktoren
- 24-Bit Sigma-Delta ADCs für hohe Auflösung

**Elektromagnetische Testsysteme:**

- Lineare elektromagnetische Aktoren (LABA7 EMA-Typ)
- Kraftkapazität: 10-20 kN Spitzendynamik
- Frequenzantwort: DC bis 100 Hz
- Positionsgenauigkeit: ±0,01 mm

## Vergleich mit traditionellen EUSAMA-Methoden

### Traditionelle EUSAMA-Methode

**Kernmethodik:**

- Frequenzbereich: Test bei 25Hz mit vorgeschriebener Amplitude von 6mm
- Messparameter: EUSAMA-Koeffizient (WE) = (minimale dynamische Belastung / statische Belastung) × 100%
- Bewertungskriterien: 0-20% schlecht, 21-40% akzeptabel, >40% gut

**Einschränkungen:**

- Begrenzte Diagnosefähigkeiten
- Anfällig für Reifendruckschwankungen
- Hohe Anregungsamplitude entspricht nicht modernen Straßenprofilen
- Falsch-negative Ergebnisse bei leichten Fahrzeugen

### EGEA Phase_Shift Vorteile

**Technische Verbesserungen:**

- **Verbesserte Diagnosegenauigkeit**: Reduzierte falsch-negative Ergebnisse
- **Bessere Korrelation**: Mit realer Fahrwerksleistung
- **Lineare Beziehung**: Phasenwinkel-Methode zeigt nahezu lineare Korrelation mit Dämpfungskoeffizient
- **Moderne Fahrzeugkompatibilität**: Besser geeignet für zeitgemäße Fahrzeugkonstruktionen

**Belgiens Erfolgsimplementierung:**

- Betriebsbereit seit 2011 unter GOCA
- Testet 4,5 Millionen Fahrzeuge jährlich
- Nachgewiesene Erfolgsbilanz über 13+ Jahre Betrieb

### Ausrüstungsanforderungen im Vergleich

**EUSAMA-Ausrüstung:**

- Nockenmechanismus mit 6mm Amplitudenfähigkeit
- Präzise 25Hz-Generierung
- Dehnungsmessstreifen-Kraftmesszellen
- Grundlegende Frequenzsteuerung

**EGEA Phase_Shift Ausrüstung:**

- Erweiterte Vibrationssteuerung: Präzise Amplituden- und Frequenzsteuerung
- Doppelmessung: Kraft- und Phasenwinkel-Detektionssysteme
- Signalverarbeitung: Digitale Signalverarbeitung für Phasenanalyse
- Erweiterte Algorithmen für Zweiparam

**Kostentechnischer Vergleich:**

- EUSAMA: Niedrigere Anfangsinvestition, etablierte Technologie
- EGEA Phase_Shift: Höhere Anfangsinvestition, aber überlegene Diagnosefähigkeiten und reduzierte Fehlmessungen
  rechtfertigen zusätzliche Kosten

## Praktische Implementierungsempfehlungen

### Kalibrierungsverfahren

**Kalibrierungsstandards:**

- DAkkS/ISO 17025 akkreditierte Kalibrierung erforderlich
- Kalibrierintervalle: 12-24 Monate für kritische Messungen
- Rückverfolgbarkeit zu nationalen Standards (PTB, NIST)
- Dynamische Kalibrierung für frequenzabhängige Messungen

### Systemintegration

**Software-Architektur:**

- Modulares Design mit Plugin-basierten Erweiterungen
- Echtzeit-Datenvisualisierung und -analyse
- Automatisierte Testsequenzausführung
- Berichtsgenerierung mit standardisierten Formaten

**Datenbankintegration:**

- SQL-Datenbanken für Testergebnisspeicherung
- Cloud-basierte Datenanalyseplattformen
- Integration mit Fahrzeugverwaltungssystemen

Die EGEA phase_shift Methode repräsentiert eine bedeutende technologische Weiterentwicklung in der Fahrwerksprüfung. *
*Durch die Kombination traditioneller Kraftmessungen mit fortschrittlicher Phasenverschiebungsanalyse bietet sie
erheblich verbesserte Diagnosegenauigkeit und Zuverlässigkeit.** Die erfolgreiche belgische Implementierung mit 4,5
Millionen jährlich geprüften Fahrzeugen demonstriert die praktische Machbarkeit und Überlegenheit gegenüber
herkömmlichen EUSAMA-Methoden, besonders bei modernen Fahrzeugen mit steifen Reifen, die zu irreführenden
EUSAMA-Ergebnissen führen können.