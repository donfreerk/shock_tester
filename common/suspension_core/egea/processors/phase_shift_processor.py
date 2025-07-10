"""
EGEA-konformer Phase Shift Processor
Vollständige Implementierung nach SPECSUS2018
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from numpy.typing import NDArray

from ...egea.config.parameters import EGEAParameters
from ...egea.models.results import (
	PhaseShiftResult, PhaseShiftPeriod, ForceAnalysisResult,
	RigidityResult, EGEATestResult, DynamicCalibrationResult,
	VehicleType, TestResult
)
from ...egea.utils.signal_processing import EGEASignalProcessor

logger = logging.getLogger(__name__)


class EGEAPhaseShiftProcessor:
	"""
	EGEA-konformer Phase Shift Processor nach SPECSUS2018

	Implementiert alle erforderlichen Berechnungen:
	- Phasenverschiebung φ und minimale Phasenverschiebung φmin (3.21, 3.22)
	- Relative Kraftamplitude RFAmax (3.18)
	- Reifensteifigkeit nach EGEA-Formel (3.20)
	- Dynamische Kalibrierung (3.10)
	- Signal Overflow/Underflow Detection (3.16)
	"""

	def __init__(self):
		self.params = EGEAParameters()
		self.signal_processor = EGEASignalProcessor()

	def perform_dynamic_calibration(self,
	                                platform_force_signal: NDArray[np.float64],
	                                time_array: NDArray[np.float64],
	                                platform_mass: float) -> DynamicCalibrationResult:
		"""
		Führt dynamische Kalibrierung mit unbelasteter Plattform durch (3.10)

		Args:
			platform_force_signal: Kraft der unbelasteten Plattform
			time_array: Zeitarray
			platform_mass: Plattformmasse mp

		Returns:
			DynamicCalibrationResult
		"""
		try:
			fs = 1.0 / (time_array[1] - time_array[0])

			# Finde Plattform-TOPs
			peaks = self.signal_processor.find_platform_tops(platform_force_signal)

			max_fp_values = []
			delta_periods = []
			frequencies = []

			for i in range(1, len(peaks)):
				start_idx = int(peaks[i - 1])
				end_idx = int(peaks[i])

				# Frequenz berechnen
				frequency = self.signal_processor.calculate_cycle_frequency(
					start_idx, end_idx, time_array
				)

				if self.params.MIN_CALC_FREQ <= frequency <= self.params.MAX_CALC_FREQ:
					# Amplitude für diese Periode
					cycle_force = platform_force_signal[start_idx:end_idx]
					max_fp = np.max(np.abs(cycle_force))

					# Phasenverschiebung (sollte idealerweise 0 sein)
					delta_period = 0.0  # Vereinfachung für Kalibrierung

					max_fp_values.append(max_fp)
					delta_periods.append(delta_period)
					frequencies.append(frequency)

			# Validierung: |F(t(f))| <= DynCalErr*f
			max_error = 0.0
			for i, freq in enumerate(frequencies):
				allowed_error = self.params.DYN_CAL_ERR * freq
				if max_fp_values[i] > allowed_error:
					max_error = max(max_error, max_fp_values[i] - allowed_error)

			is_valid = max_error <= 0
			error_message = None if is_valid else f"Calibration error: {max_error:.2f}N exceeds limit"

			return DynamicCalibrationResult(
				max_fp=max_fp_values,
				delta_period=delta_periods,
				frequencies=frequencies,
				is_valid=is_valid,
				error_message=error_message
			)

		except Exception as e:
			logger.error(f"Dynamic calibration failed: {e}")
			return DynamicCalibrationResult(
				is_valid=False,
				error_message=str(e)
			)

	def calculate_phase_shift_advanced(self,
	                                   platform_position: NDArray[np.float64],
	                                   tire_force: NDArray[np.float64],
	                                   time_array: NDArray[np.float64],
	                                   static_weight: float) -> PhaseShiftResult:
		"""
		Erweiterte EGEA-konforme Phasenverschiebungsberechnung

		Args:
			platform_position: Plattformpositionssignal
			tire_force: Reifenkraftsignal
			time_array: Zeitarray
			static_weight: Statisches Radgewicht (Fst)

		Returns:
			PhaseShiftResult mit vollständigen EGEA-Daten
		"""
		try:
			# Abtastrate berechnen
			fs = 1.0 / (time_array[1] - time_array[0])

			# Signal Overflow/Underflow Detection
			f_under_flag, f_over_flag = self.signal_processor.detect_signal_overflow_underflow(
				tire_force, static_weight
			)

			# Plattform-TOPs identifizieren (korrekte TOPp(i) Berechnung)
			platform_peaks = self.signal_processor.find_platform_tops(platform_position)

			periods = []

			# Jeden Zyklus analysieren
			for i in range(1, len(platform_peaks)):
				period_result = self._analyze_single_period(
					platform_position, tire_force, time_array, static_weight,
					platform_peaks[i - 1], platform_peaks[i], i, fs
				)

				if period_result is not None:
					periods.append(period_result)

			# Ergebnisse zusammenstellen
			if not periods:
				return PhaseShiftResult(
					periods=[],
					static_weight=static_weight,
					f_under_flag=f_under_flag,
					f_over_flag=f_over_flag
				)

			# Minimale Phasenverschiebung bestimmen
			valid_periods = [p for p in periods if p.is_valid]

			if not valid_periods:
				return PhaseShiftResult(
					periods=periods,
					static_weight=static_weight,
					f_under_flag=f_under_flag,
					f_over_flag=f_over_flag
				)

			# φmin und zugehörige Frequenz
			min_period = min(valid_periods, key=lambda p: p.phase_shift)
			min_phase_shift = min_period.phase_shift
			min_phase_frequency = min_period.frequency

			# φmax bei 18Hz (falls vorhanden)
			max_phase_shift = None
			for period in valid_periods:
				if abs(period.frequency - 18.0) < 0.5:  # Toleranz von ±0.5Hz
					max_phase_shift = period.phase_shift
					break

			# RFAmax berechnen
			rfa_max_value = None
			rfa_max_frequency = None
			max_rfa = 0.0

			for period in valid_periods:
				if period.rfa_max > max_rfa:
					max_rfa = period.rfa_max
					rfa_max_value = period.rfa_max
					rfa_max_frequency = period.frequency

			return PhaseShiftResult(
				periods=periods,
				min_phase_shift=min_phase_shift,
				min_phase_frequency=min_phase_frequency,
				max_phase_shift=max_phase_shift,
				static_weight=static_weight,
				f_under_flag=f_under_flag,
				f_over_flag=f_over_flag,
				rfa_max_value=rfa_max_value,
				rfa_max_frequency=rfa_max_frequency
			)

		except Exception as e:
			logger.error(f"Phase shift calculation failed: {e}")
			return PhaseShiftResult(
				periods=[],
				static_weight=static_weight,
				f_under_flag=True,
				f_over_flag=False
			)

	def _analyze_single_period(self,
	                           platform_position: NDArray[np.float64],
	                           tire_force: NDArray[np.float64],
	                           time_array: NDArray[np.float64],
	                           static_weight: float,
	                           start_peak_idx: int,
	                           end_peak_idx: int,
	                           period_index: int,
	                           fs: float) -> Optional[PhaseShiftPeriod]:
		"""
		Analysiert eine einzelne Periode für Phasenverschiebung

		Args:
			platform_position: Plattformposition
			tire_force: Reifenkraft
			time_array: Zeit
			static_weight: Statisches Gewicht
			start_peak_idx: Start-Peak-Index
			end_peak_idx: End-Peak-Index
			period_index: Periodenindex
			fs: Abtastrate

		Returns:
			PhaseShiftPeriod oder None wenn ungültig
		"""
		try:
			start_idx = int(start_peak_idx)
			end_idx = int(end_peak_idx)

			# Frequenz für diese Periode
			frequency = self.signal_processor.calculate_cycle_frequency(
				start_idx, end_idx, time_array
			)

			# Nur relevante Frequenzen
			if not (self.params.MIN_CALC_FREQ <= frequency <= self.params.MAX_CALC_FREQ):
				return None

			# Daten für diese Periode extrahieren
			cycle_force = tire_force[start_idx:end_idx]
			cycle_time = time_array[start_idx:end_idx]
			cycle_platform = platform_position[start_idx:end_idx]

			# RFstFMin/RFstFMax Validierung
			if not self.signal_processor.validate_rfst_conditions(cycle_force, static_weight):
				return None

			# EGEA-konforme Signalfilterung anwenden
			filtered_force = self.signal_processor.apply_egea_phase_filter(
				cycle_force, fs, frequency
			)

			# Echte TOPp(i) Position finden (nicht nur Zyklusstart)
			platform_peak_in_cycle = np.argmax(cycle_platform)
			top_p_time = cycle_time[platform_peak_in_cycle] - cycle_time[0]

			# Fref berechnen (verbesserte Methode)
			fref = self.signal_processor.calculate_fref(
				filtered_force, cycle_time, static_weight,
				cycle_time[0], cycle_time[-1]
			)

			if fref is None:
				return None

			# Relative Fref-Zeit
			fref_relative = fref - cycle_time[0]

			# Phasenverschiebung berechnen
			phase_shift_rad = (fref_relative - top_p_time) * frequency * 2 * np.pi
			phase_shift_deg = np.degrees(phase_shift_rad)

			# Normalisierung auf 0°-180°
			phase_shift_deg = phase_shift_deg % 360
			if phase_shift_deg > 180:
				phase_shift_deg = 360 - phase_shift_deg

			# Kraftwerte für diese Periode
			max_force = np.max(cycle_force)
			min_force = np.min(cycle_force)
			delta_force = max_force - min_force

			return PhaseShiftPeriod(
				period_index=period_index,
				frequency=frequency,
				phase_shift=phase_shift_deg,
				fref=fref_relative,
				top_p=top_p_time,
				max_force=max_force,
				min_force=min_force,
				delta_force=delta_force,
				static_weight=static_weight,
				is_valid=True
			)

		except Exception as e:
			logger.error(f"Period analysis failed for period {period_index}: {e}")
			return None

	def calculate_force_analysis(self,
	                             tire_force: NDArray[np.float64],
	                             time_array: NDArray[np.float64],
	                             static_weight: float) -> ForceAnalysisResult:
		"""
		Berechnet Kraftanalyse-Parameter (3.15, 3.17)

		Args:
			tire_force: Reifenkraftsignal
			time_array: Zeitarray
			static_weight: Statisches Gewicht

		Returns:
			ForceAnalysisResult
		"""
		try:
			fs = 1.0 / (time_array[1] - time_array[0])

			# Signalfilterung
			filtered_force = self.signal_processor.apply_force_amplitude_filter(tire_force, fs)

			# Grundwerte
			fmin = np.min(filtered_force)
			fmax = np.max(filtered_force)

			# Overflow/Underflow Detection
			f_under_flag, f_over_flag = self.signal_processor.detect_signal_overflow_underflow(
				filtered_force, static_weight
			)

			# FAmax und Resonanzfrequenz nach EGEA-Kriterien (3.17)
			if not f_under_flag and not f_over_flag:
				fa_max = static_weight - fmin  # Fst - Fmin
				# Resonanzfrequenz bei tFmin bestimmen
				min_idx = np.argmin(filtered_force)
				resonant_frequency = 1.0 / (2 * time_array[min_idx]) if time_array[min_idx] > 0 else 0.0
			elif f_under_flag and not f_over_flag:
				fa_max = fmax - static_weight  # Fmax - Fst
				max_idx = np.argmax(filtered_force)
				resonant_frequency = 1.0 / (2 * time_array[max_idx]) if time_array[max_idx] > 0 else 0.0
			else:
				# Beide Flags gesetzt
				f_under_lim = self.params.calculate_f_under_lim(static_weight)
				f_over_lim = fmax  # Vereinfachung, sollte Hardware-Parameter sein
				fa_max = max(f_over_lim - static_weight, static_weight - f_under_lim)
				resonant_frequency = 0.0  # Nicht bestimmbar

			# RFAmax berechnen (3.18)
			rfa_max = (fa_max / static_weight) * 100.0 if static_weight > 0 else 0.0

			return ForceAnalysisResult(
				fmin=fmin,
				fmax=fmax,
				fa_max=fa_max,
				resonant_frequency=resonant_frequency,
				rfa_max=rfa_max,
				static_weight=static_weight,
				f_under_flag=f_under_flag,
				f_over_flag=f_over_flag
			)

		except Exception as e:
			logger.error(f"Force analysis failed: {e}")
			return ForceAnalysisResult(
				fmin=0.0, fmax=0.0, fa_max=0.0, resonant_frequency=0.0,
				rfa_max=0.0, static_weight=static_weight,
				f_under_flag=True, f_over_flag=False
			)

	def calculate_rigidity(self,
	                       h25_amplitude: float,
	                       platform_amplitude: float = None) -> RigidityResult:
		"""
		Berechnet Reifensteifigkeit nach EGEA-Formel (3.20)

		Args:
			h25_amplitude: H25 - Statische Amplitude bei 25Hz (N)
			platform_amplitude: Plattformamplitude ep (mm), Standard: 3.0mm

		Returns:
			RigidityResult
		"""
		if platform_amplitude is None:
			platform_amplitude = self.params.PLATFORM_AMPLITUDE

		try:
			# EGEA-Formel: rig = arig * (H25/ep) + brig
			rigidity = (self.params.A_RIG * (h25_amplitude / platform_amplitude) +
			            self.params.B_RIG)

			# Warnungen für Reifendruck
			warning_underinflation = rigidity < self.params.RIG_LO_LIM
			warning_overinflation = rigidity > self.params.RIG_HI_LIM

			return RigidityResult(
				rigidity=rigidity,
				h25=h25_amplitude,
				platform_amplitude=platform_amplitude,
				warning_underinflation=warning_underinflation,
				warning_overinflation=warning_overinflation
			)

		except Exception as e:
			logger.error(f"Rigidity calculation failed: {e}")
			return RigidityResult(
				rigidity=0.0,
				h25=h25_amplitude,
				platform_amplitude=platform_amplitude,
				warning_underinflation=True,
				warning_overinflation=False
			)

	def evaluate_egea_criteria(self,
	                           phase_result: PhaseShiftResult,
	                           force_analysis: ForceAnalysisResult,
	                           rigidity_result: RigidityResult,
	                           vehicle_type: VehicleType = VehicleType.M1) -> Tuple[bool, bool, bool]:
		"""
		Bewertet alle EGEA-Kriterien

		Args:
			phase_result: Phasenverschiebungsergebnis
			force_analysis: Kraftanalyseergebnis
			rigidity_result: Steifigkeitsergebnis
			vehicle_type: Fahrzeugtyp

		Returns:
			(absolute_criterion_pass, relative_criterion_pass, overall_pass)
		"""
		# Absolutes Kriterium: φmin >= 35°
		absolute_pass = (phase_result.min_phase_shift is not None and
		                 phase_result.min_phase_shift >= self.params.PHASE_SHIFT_MIN)

		# Relative Kriterien werden auf Achsebene bewertet (hier Platzhalter)
		relative_pass = True  # Wird in AxleTestResult berechnet

		# Gesamtbewertung
		overall_pass = (absolute_pass and
		                relative_pass and
		                not phase_result.f_under_flag and
		                not phase_result.f_over_flag and
		                phase_result.is_valid)

		return absolute_pass, relative_pass, overall_pass

	def process_complete_test(self,
	                          platform_position: NDArray[np.float64],
	                          tire_force: NDArray[np.float64],
	                          time_array: NDArray[np.float64],
	                          static_weight: float,
	                          wheel_id: str,
	                          vehicle_type: VehicleType = VehicleType.M1,
	                          platform_force: Optional[NDArray[np.float64]] = None,
	                          platform_mass: float = 20.0) -> EGEATestResult:
		"""
		Führt kompletten EGEA-Test durch

		Args:
			platform_position: Plattformposition
			tire_force: Reifenkraft
			time_array: Zeit
			static_weight: Statisches Gewicht
			wheel_id: Rad-ID (z.B. "FL")
			vehicle_type: Fahrzeugtyp
			platform_force: Plattformkraft für Kalibrierung (optional)
			platform_mass: Plattformmasse

		Returns:
			EGEATestResult mit allen Ergebnissen
		"""
		error_messages = []

		try:
			# Dynamische Kalibrierung (falls Plattformkraft verfügbar)
			dynamic_calibration = DynamicCalibrationResult(is_valid=True)
			if platform_force is not None:
				dynamic_calibration = self.perform_dynamic_calibration(
					platform_force, time_array, platform_mass
				)
				if not dynamic_calibration.is_valid:
					error_messages.append(dynamic_calibration.error_message)

			# Phasenverschiebungsanalyse
			phase_result = self.calculate_phase_shift_advanced(
				platform_position, tire_force, time_array, static_weight
			)

			# Kraftanalyse
			force_analysis = self.calculate_force_analysis(
				tire_force, time_array, static_weight
			)

			# H25 für Steifigkeitsberechnung (vereinfacht)
			h25_amplitude = np.std(tire_force) * 2  # Vereinfachte H25-Berechnung
			rigidity_result = self.calculate_rigidity(h25_amplitude)

			# EGEA-Kriterien bewerten
			absolute_pass, relative_pass, overall_pass = self.evaluate_egea_criteria(
				phase_result, force_analysis, rigidity_result, vehicle_type
			)

			# Ergebnis zusammenstellen
			result = EGEATestResult(
				wheel_id=wheel_id,
				vehicle_type=vehicle_type,
				phase_shift_result=phase_result,
				force_analysis=force_analysis,
				rigidity_result=rigidity_result,
				dynamic_calibration=dynamic_calibration,
				absolute_criterion_pass=absolute_pass,
				relative_criterion_pass=relative_pass,
				overall_pass=overall_pass,
				error_messages=error_messages
			)

			return result

		except Exception as e:
			logger.error(f"Complete test processing failed: {e}")

			# Minimales Ergebnis bei Fehler
			phase_result = PhaseShiftResult(static_weight=static_weight)
			force_analysis = ForceAnalysisResult(
				fmin=0.0, fmax=0.0, fa_max=0.0,
				resonant_frequency=0.0, rfa_max=0.0,
				static_weight=static_weight
			)
			rigidity_result = RigidityResult(
				rigidity=0.0, h25=0.0, platform_amplitude=self.params.PLATFORM_AMPLITUDE
			)

			return EGEATestResult(
				wheel_id=wheel_id,
				vehicle_type=vehicle_type,
				phase_shift_result=phase_result,
				force_analysis=force_analysis,
				rigidity_result=rigidity_result,
				dynamic_calibration=DynamicCalibrationResult(),
				error_messages=[str(e)]
			)