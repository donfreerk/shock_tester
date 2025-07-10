"""
Datenvisualisierungs-Optionen Widget
Implementiert die fehlende dynamische Chart-Funktionalität
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Set, Protocol, Callable
from dataclasses import dataclass
from enum import Enum
import threading
import time


class DataFieldType(Enum):
	"""Typ der empfangenen Datenfelder"""
	POSITION = "position"
	FORCE = "force"
	PHASE = "phase"
	FREQUENCY = "frequency"
	ACCELERATION = "acceleration"
	VELOCITY = "velocity"
	UNKNOWN = "unknown"


@dataclass
class DataField:
	"""Repräsentiert ein erkanntes Datenfeld"""
	name: str
	field_type: DataFieldType
	unit: str
	last_value: float = 0.0
	is_active: bool = True
	sample_count: int = 0


class DataManagerProtocol(Protocol):
	"""Interface für Datenmanagement"""

	def get_available_fields(self) -> Dict[str, DataField]:
		"""Gibt verfügbare Datenfelder zurück"""
		...

	def clear_data_buffer(self) -> bool:
		"""Leert den Datenpuffer"""
		...

	def get_field_data(self, field_name: str, samples: int = 100) -> List[float]:
		"""Gibt die letzten N Samples eines Feldes zurück"""
		...

	def is_receiving_data(self) -> bool:
		"""Prüft ob Daten empfangen werden"""
		...


class DataVisualizationOptionsWidget(tk.Frame):
	"""
	Widget für Datenvisualisierungs-Optionen
	Ermöglicht dynamische Chart-Konfiguration und Datenfeld-Management
	"""

	def __init__(self, parent, data_manager: DataManagerProtocol,
	             chart_update_callback: Callable[[Dict[str, bool]], None] = None, **kwargs):
		super().__init__(parent, **kwargs)
		self.data_manager = data_manager
		self.chart_update_callback = chart_update_callback

		# Zustandsvariablen
		self.field_variables: Dict[str, tk.BooleanVar] = {}
		self.show_all_fields = tk.BooleanVar(value=False)
		self.auto_refresh = tk.BooleanVar(value=True)
		self.refresh_rate = tk.IntVar(value=1000)  # ms

		# UI-Komponenten
		self.available_fields: Dict[str, DataField] = {}
		self.field_checkboxes: Dict[str, tk.Checkbutton] = {}

		self._create_widgets()
		self._setup_layout()
		self._start_field_discovery()

	def _create_widgets(self):
		"""Erstellt alle UI-Komponenten"""
		# Hauptcontainer
		self.main_frame = ttk.LabelFrame(self, text="📊 Visualisierungs-Optionen", padding="10")

		# Globale Optionen
		self.options_frame = ttk.Frame(self.main_frame)

		self.show_all_checkbox = ttk.Checkbutton(
			self.options_frame,
			text="Alle empfangenen Datenfelder anzeigen (dynamische Charts)",
			variable=self.show_all_fields,
			command=self._toggle_show_all_fields
		)

		self.auto_refresh_checkbox = ttk.Checkbutton(
			self.options_frame,
			text="Automatische Aktualisierung",
			variable=self.auto_refresh,
			command=self._toggle_auto_refresh
		)

		# Refresh-Rate Einstellung
		self.refresh_frame = ttk.Frame(self.options_frame)
		self.refresh_label = ttk.Label(self.refresh_frame, text="Aktualisierungsrate (ms):")
		self.refresh_scale = ttk.Scale(
			self.refresh_frame,
			from_=100,
			to=5000,
			variable=self.refresh_rate,
			orient="horizontal",
			length=200,
			command=self._update_refresh_rate
		)
		self.refresh_value_label = ttk.Label(self.refresh_frame, text="1000")

		# Verfügbare Datenfelder
		self.fields_frame = ttk.LabelFrame(self.main_frame, text="Verfügbare Datenfelder", padding="5")

		# Scrollable Frame für Datenfelder
		self.canvas = tk.Canvas(self.fields_frame, height=150)
		self.scrollbar = ttk.Scrollbar(self.fields_frame, orient="vertical", command=self.canvas.yview)
		self.scrollable_frame = ttk.Frame(self.canvas)

		self.scrollable_frame.bind(
			"<Configure>",
			lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
		)

		self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
		self.canvas.configure(yscrollcommand=self.scrollbar.set)

		# Wartemeldung
		self.waiting_label = ttk.Label(
			self.scrollable_frame,
			text="Keine Datenfelder erkannt. Warten auf Daten...",
			foreground="gray",
			font=("Arial", 9, "italic")
		)

		# Status-Informationen
		self.status_frame = ttk.Frame(self.main_frame)
		self.data_count_label = ttk.Label(self.status_frame, text="Empfangene Daten: 0 Datenpunkte")
		self.last_update_label = ttk.Label(self.status_frame, text="Letzte Aktualisierung: --")

		# Aktionsbuttons
		self.action_frame = ttk.Frame(self.main_frame)

		self.clear_buffer_button = ttk.Button(
			self.action_frame,
			text="🗑️ Datenpuffer leeren",
			command=self._clear_data_buffer
		)

		self.refresh_fields_button = ttk.Button(
			self.action_frame,
			text="🔄 Felder aktualisieren",
			command=self._refresh_available_fields
		)

		self.select_all_button = ttk.Button(
			self.action_frame,
			text="✅ Alle auswählen",
			command=self._select_all_fields
		)

		self.deselect_all_button = ttk.Button(
			self.action_frame,
			text="❌ Alle abwählen",
			command=self._deselect_all_fields
		)

	def _setup_layout(self):
		"""Organisiert das Layout"""
		# Hauptframe
		self.main_frame.pack(fill="both", expand=True)

		# Globale Optionen
		self.options_frame.pack(fill="x", pady=(0, 10))

		self.show_all_checkbox.pack(anchor="w")
		self.auto_refresh_checkbox.pack(anchor="w", pady=(5, 0))

		# Refresh-Rate
		self.refresh_frame.pack(fill="x", pady=(5, 0))
		self.refresh_label.pack(side="left")
		self.refresh_scale.pack(side="left", padx=(10, 5))
		self.refresh_value_label.pack(side="left")

		# Datenfelder Frame
		self.fields_frame.pack(fill="both", expand=True, pady=(0, 10))

		# Canvas und Scrollbar
		self.canvas.pack(side="left", fill="both", expand=True)
		self.scrollbar.pack(side="right", fill="y")

		# Wartemeldung (initial)
		self.waiting_label.pack(pady=20)

		# Status
		self.status_frame.pack(fill="x", pady=(0, 10))
		self.data_count_label.pack(anchor="w")
		self.last_update_label.pack(anchor="w")

		# Aktionsbuttons
		self.action_frame.pack(fill="x")
		self.clear_buffer_button.pack(side="left", padx=(0, 5))
		self.refresh_fields_button.pack(side="left", padx=5)
		self.select_all_button.pack(side="left", padx=5)
		self.deselect_all_button.pack(side="left", padx=5)

	def _start_field_discovery(self):
		"""Startet die automatische Erkennung von Datenfeldern"""
		# Thread-safe Implementation - verwende after() statt Threading
		self._schedule_field_update()

	def _schedule_field_update(self):
		"""Plant die nächste Feldaktualisierung (thread-safe)"""
		try:
			if self.auto_refresh.get():  # ← Jetzt sicher im Main-Thread
				self._update_available_fields()

			refresh_rate = self.refresh_rate.get()
			self.after(refresh_rate, self._schedule_field_update)  # ← Tkinter-Timer

		except Exception as e:
			print(f"Fehler bei Feldaktualisierung: {e}")
			self.after(5000, self._schedule_field_update)  # Fallback

	def _update_available_fields(self):
		"""Aktualisiert die Liste der verfügbaren Datenfelder"""
		try:
			new_fields = self.data_manager.get_available_fields()

			# Prüfen ob sich Felder geändert haben
			if new_fields != self.available_fields:
				self.available_fields = new_fields
				self._rebuild_field_list()

			# Status aktualisieren
			total_samples = sum(field.sample_count for field in new_fields.values())
			self.data_count_label.config(text=f"Empfangene Daten: {total_samples} Datenpunkte")
			self.last_update_label.config(text=f"Letzte Aktualisierung: {time.strftime('%H:%M:%S')}")

		except Exception as e:
			print(f"Fehler beim Aktualisieren der Datenfelder: {e}")

	def _rebuild_field_list(self):
		"""Baut die Liste der Datenfeld-Checkboxen neu auf"""
		# Alte Checkboxen entfernen
		for widget in self.scrollable_frame.winfo_children():
			widget.destroy()

		self.field_checkboxes.clear()

		if not self.available_fields:
			# Wartemeldung anzeigen
			self.waiting_label = ttk.Label(
				self.scrollable_frame,
				text="Keine Datenfelder erkannt. Warten auf Daten...",
				foreground="gray",
				font=("Arial", 9, "italic")
			)
			self.waiting_label.pack(pady=20)
			return

		# Neue Checkboxen erstellen
		for field_name, field_info in self.available_fields.items():
			# Variable für Checkbox erstellen oder wiederverwenden
			if field_name not in self.field_variables:
				self.field_variables[field_name] = tk.BooleanVar(
					value=self.show_all_fields.get() or field_info.is_active
				)

			# Frame für Checkbox und Info
			field_frame = ttk.Frame(self.scrollable_frame)
			field_frame.pack(fill="x", padx=5, pady=2)

			# Checkbox
			checkbox = ttk.Checkbutton(
				field_frame,
				text=f"{field_name} ({field_info.unit})",
				variable=self.field_variables[field_name],
				command=lambda fn=field_name: self._field_toggled(fn)
			)
			checkbox.pack(side="left")

			# Status-Info
			status_color = "green" if field_info.sample_count > 0 else "red"
			status_text = f"📊 {field_info.sample_count} | ⚡ {field_info.last_value:.2f}"

			status_label = ttk.Label(
				field_frame,
				text=status_text,
				foreground=status_color,
				font=("Arial", 8)
			)
			status_label.pack(side="right")

			self.field_checkboxes[field_name] = checkbox

	def _field_toggled(self, field_name: str):
		"""Wird aufgerufen wenn ein Datenfeld aktiviert/deaktiviert wird"""
		if self.chart_update_callback:
			selected_fields = {
				name: var.get()
				for name, var in self.field_variables.items()
			}
			self.chart_update_callback(selected_fields)

	def _toggle_show_all_fields(self):
		"""Aktiviert/deaktiviert alle Datenfelder"""
		show_all = self.show_all_fields.get()

		for var in self.field_variables.values():
			var.set(show_all)

		if self.chart_update_callback:
			selected_fields = {
				name: show_all
				for name in self.field_variables.keys()
			}
			self.chart_update_callback(selected_fields)

	def _toggle_auto_refresh(self):
		"""Aktiviert/deaktiviert die automatische Aktualisierung"""
		pass  # Wird bereits in discovery_loop berücksichtigt

	def _update_refresh_rate(self, value):
		"""Aktualisiert die Anzeige der Refresh-Rate"""
		rate = int(float(value))
		self.refresh_value_label.config(text=f"{rate}")

	def _clear_data_buffer(self):
		"""Leert den Datenpuffer"""
		try:
			if self.data_manager.clear_data_buffer():
				self.data_count_label.config(text="Empfangene Daten: 0 Datenpunkte")
				print("Datenpuffer geleert")
		except Exception as e:
			print(f"Fehler beim Leeren des Datenpuffers: {e}")

	def _refresh_available_fields(self):
		"""Manuell Datenfelder aktualisieren"""
		self._update_available_fields()

	def _select_all_fields(self):
		"""Wählt alle verfügbaren Felder aus"""
		for var in self.field_variables.values():
			var.set(True)
		self._notify_field_changes()

	def _deselect_all_fields(self):
		"""Deaktiviert alle Datenfelder"""
		for var in self.field_variables.values():
			var.set(False)
		self._notify_field_changes()

	def _notify_field_changes(self):
		"""Benachrichtigt über Änderungen an Feldauswahl"""
		if self.chart_update_callback:
			selected_fields = {
				name: var.get()
				for name, var in self.field_variables.items()
			}
			self.chart_update_callback(selected_fields)


# Mock-Implementation für Testzwecke
class MockDataManager:
	"""Mock-Datenmanager für Demonstration"""

	def __init__(self):
		self.fields = {
			"platform_position": DataField("platform_position", DataFieldType.POSITION, "mm", 1.25, True, 150),
			"tire_force": DataField("tire_force", DataFieldType.FORCE, "N", 245.8, True, 150),
			"phase_shift": DataField("phase_shift", DataFieldType.PHASE, "°", 38.2, True, 150),
			"test_frequency": DataField("test_frequency", DataFieldType.FREQUENCY, "Hz", 15.0, True, 150),
			"acceleration_x": DataField("acceleration_x", DataFieldType.ACCELERATION, "m/s²", 0.12, False, 75),
			"velocity_z": DataField("velocity_z", DataFieldType.VELOCITY, "m/s", 0.003, False, 75),
		}
		self.data_buffer_size = 1000

	def get_available_fields(self) -> Dict[str, DataField]:
		# Simuliere sich ändernde Werte
		import random
		for field in self.fields.values():
			field.last_value += random.uniform(-0.1, 0.1)
			field.sample_count += random.randint(0, 5)
		return self.fields.copy()

	def clear_data_buffer(self) -> bool:
		for field in self.fields.values():
			field.sample_count = 0
		return True

	def get_field_data(self, field_name: str, samples: int = 100) -> List[float]:
		return [0.0] * samples  # Mock-Daten

	def is_receiving_data(self) -> bool:
		return True


# Verwendungsbeispiel
if __name__ == "__main__":
	root = tk.Tk()
	root.title("Datenvisualisierungs-Optionen")
	root.geometry("600x500")

	# Mock-Datenmanager erstellen
	data_manager = MockDataManager()


	# Callback für Chart-Updates
	def on_chart_update(selected_fields: Dict[str, bool]):
		active_fields = [name for name, selected in selected_fields.items() if selected]
		print(f"Aktive Felder: {active_fields}")


	# Widget erstellen
	viz_widget = DataVisualizationOptionsWidget(
		root,
		data_manager,
		chart_update_callback=on_chart_update
	)
	viz_widget.pack(fill="both", expand=True, padx=10, pady=10)

	root.mainloop()