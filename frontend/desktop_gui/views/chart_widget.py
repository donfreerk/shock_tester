"""
Chart Widget für Live-Datenvisualisierung - NumPy Array Support

PROBLEM BEHOBEN: Die MQTT-Daten kommen als NumPy Arrays an, nicht als Skalare.
Diese Version kann sowohl Skalare als auch NumPy Arrays verarbeiten.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any
import numpy as np
import matplotlib
import logging
import time
import threading
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

matplotlib.use("TkAgg")

logger = logging.getLogger(__name__)


class ChartWidget:
    """
    Chart-Widget mit NumPy Array Support für MQTT-Daten

    KRITISCHE KORREKTUR:
    - Kann NumPy Arrays verarbeiten (nimmt letzten/aktuellen Wert)
    - Fallback für verschiedene Datentypen
    - Robuste Datenextraktion
    """

    def __init__(self, parent_container: tk.Widget, debug_enabled: bool = True):
        self.parent = parent_container
        self.debug_enabled = debug_enabled

        # Performance-Einstellungen
        self.time_window = 10.0
        self.max_points = 1000
        self.update_interval = 50

        # Rolling-Window Datenstrukturen
        self.time_data = deque(maxlen=self.max_points)
        self.platform_data = deque(maxlen=self.max_points)
        self.force_data = deque(maxlen=self.max_points)
        self.phase_data = deque(maxlen=self.max_points)
        self.frequency_data = deque(maxlen=self.max_points)

        # Chart-Komponenten
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self.axes = {}
        self.lines = {}

        # DEBUG: NumPy Array Handling
        self.numpy_conversion_stats = {
            "arrays_received": 0,
            "arrays_converted": 0,
            "scalars_received": 0,
            "conversion_failures": 0,
        }

        # Performance-Tracking
        self.update_count = 0
        self.last_update_time = time.time()
        self.start_time = None

        # Threading-Kontrolle
        self.update_lock = threading.Lock()
        self.is_updating = False

        self._setup_matplotlib()
        self._create_standard_charts()
        self._start_update_cycle()

        logger.info("ChartWidget initialized with NumPy Array support")

    def _setup_matplotlib(self):
        """Setup matplotlib figure und canvas."""
        self.figure = Figure(figsize=(16, 10), dpi=80, facecolor="white")
        self.figure.patch.set_facecolor("white")

        self.canvas = FigureCanvasTkAgg(self.figure, self.parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.parent)
        self.toolbar.update()

    def _setup_matplotlib_figure(self):
        """Erstellt optimierte Matplotlib-Figure"""

        # Figure mit besserem Layout erstellen
        self.fig = Figure(figsize=(14, 8), dpi=100, facecolor="white")
        self.fig.patch.set_facecolor("white")

        # VERBESSERUNG: 2 Subplots statt 3 für bessere Übersicht
        # Subplot 1: Plattformposition UND Reifenkraft (übereinander)
        # Subplot 2: Phasenverschiebung

        self.ax1 = self.fig.add_subplot(2, 1, 1)  # Oberer Plot
        self.ax2 = self.fig.add_subplot(2, 1, 2)  # Unterer Plot

        # Canvas erstellen
        self.canvas = FigureCanvasTkAgg(self.fig, self.parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Toolbar hinzufügen
        toolbar = NavigationToolbar2Tk(self.canvas, self.parent)
        toolbar.update()

        logger.info("Verbesserte Chart-Darstellung initialisiert")

    def _create_standard_charts(self):
        """Erstellt Standard EGEA-Charts."""
        self.figure.clear()
        self.axes.clear()
        self.lines.clear()

        # 2x2 Subplot-Layout
        self.axes = {
            "platform": self.figure.add_subplot(2, 2, 1),
            "force": self.figure.add_subplot(2, 2, 2),
            "phase": self.figure.add_subplot(2, 2, 3),
            "frequency": self.figure.add_subplot(2, 2, 4),
        }

        # Chart-Konfiguration
        self._configure_chart(
            self.axes["platform"], "Platform Position", "Position [mm]", "blue"
        )
        self._configure_chart(self.axes["force"], "Tire Force", "Force [N]", "green")
        self._configure_chart(
            self.axes["phase"], "Phase Shift (EGEA)", "Phase [°]", "red"
        )
        self._configure_chart(
            self.axes["frequency"], "Test Frequency", "Frequency [Hz]", "purple"
        )

        # EGEA-Grenzlinie
        self.axes["phase"].axhline(
            y=35, color="red", linestyle="--", alpha=0.7, label="EGEA Limit (35°)"
        )
        self.axes["phase"].legend(fontsize=8)

        # Line-Objekte erstellen
        self.lines = {
            "platform": self.axes["platform"].plot([], [], "b-", linewidth=1.5)[0],
            "force": self.axes["force"].plot([], [], "g-", linewidth=1.5)[0],
            "phase": self.axes["phase"].plot([], [], "r-", linewidth=2)[0],
            "frequency": self.axes["frequency"].plot([], [], "m-", linewidth=1.5)[0],
        }

        self.figure.tight_layout(pad=2.0)
        self.canvas.draw()

    def _configure_chart(self, ax, title: str, ylabel: str, color: str):
        """Konfiguriert einzelnen Chart."""
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Time [s]")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, self.time_window)

    def update_charts(self, result_data: dict):
        """
        Aktualisiert die Charts mit verbessertem Layout

        Args:
                result_data: Dictionary mit Testergebnissen
        """
        try:
            # Daten extrahieren
            time_data = np.array(result_data.get("time_data", []))
            platform_data = np.array(result_data.get("platform_position", []))
            force_data = np.array(result_data.get("tire_force", []))
            phase_shifts = np.array(result_data.get("phase_shifts", []))
            frequencies = np.array(result_data.get("frequencies", []))

            # VERBESSERUNG: Alle Achsen leeren und neu konfigurieren
            self.ax1.clear()
            self.ax2.clear()

            if len(time_data) > 0:
                self._plot_combined_signals(time_data, platform_data, force_data)
                self._plot_phase_analysis(frequencies, phase_shifts)
            else:
                self._plot_placeholder()

            # KRITISCHE VERBESSERUNG: Layout optimieren
            self._optimize_layout()

            # Canvas aktualisieren
            self.canvas.draw()

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Charts: {e}")
            self._plot_error_message(str(e))

    def _plot_combined_signals(self, time_data, platform_data, force_data):
        """
        VERBESSERT: Plottet Plattformposition und Reifenkraft übereinander
        """
        # LÖSUNG: Twin-Axes für unterschiedliche Einheiten
        ax1_twin = self.ax1.twinx()

        # Plattformposition (linke Y-Achse, blau)
        line1 = self.ax1.plot(
            time_data,
            platform_data,
            "b-",
            linewidth=2.5,
            label="Plattformposition",
            alpha=0.8,
        )
        self.ax1.set_ylabel(
            "Position (mm)", color="blue", fontweight="bold", fontsize=11
        )
        self.ax1.tick_params(axis="y", labelcolor="blue")

        # Reifenkraft (rechte Y-Achse, rot)
        line2 = ax1_twin.plot(
            time_data, force_data, "r-", linewidth=2.5, label="Reifenkraft", alpha=0.8
        )
        ax1_twin.set_ylabel("Kraft (N)", color="red", fontweight="bold", fontsize=11)
        ax1_twin.tick_params(axis="y", labelcolor="red")

        # VERBESSERTE TITEL-POSITIONIERUNG
        self.ax1.set_title(
            "🔧 Plattformposition über Zeit",
            fontweight="bold",
            fontsize=12,
            pad=20,
            color="blue",
        )
        ax1_twin.set_title(
            "⚡ Reifenkraft über Zeit",
            fontweight="bold",
            fontsize=12,
            pad=5,
            color="red",
        )

        # X-Achse nur beim unteren Plot
        self.ax1.set_xlabel("")  # Kein X-Label hier

        # Grid für bessere Lesbarkeit
        self.ax1.grid(True, alpha=0.3, linestyle="-", color="blue")
        ax1_twin.grid(True, alpha=0.3, linestyle="--", color="red")

        # VERBESSERUNG: Kombinierte Legende
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        self.ax1.legend(lines, labels, loc="upper left", framealpha=0.9, fontsize=10)

        # Y-Achsen-Limits automatisch anpassen
        self.ax1.margins(y=0.1)
        ax1_twin.margins(y=0.1)

    def _plot_combined_signals(self, time_data, platform_data, force_data):
        """
        VERBESSERT: Plottet Plattformposition und Reifenkraft übereinander
        """
        # LÖSUNG: Twin-Axes für unterschiedliche Einheiten
        ax1_twin = self.ax1.twinx()

        # Plattformposition (linke Y-Achse, blau)
        line1 = self.ax1.plot(
            time_data,
            platform_data,
            "b-",
            linewidth=2.5,
            label="Plattformposition",
            alpha=0.8,
        )
        self.ax1.set_ylabel(
            "Position (mm)", color="blue", fontweight="bold", fontsize=11
        )
        self.ax1.tick_params(axis="y", labelcolor="blue")

        # Reifenkraft (rechte Y-Achse, rot)
        line2 = ax1_twin.plot(
            time_data, force_data, "r-", linewidth=2.5, label="Reifenkraft", alpha=0.8
        )
        ax1_twin.set_ylabel("Kraft (N)", color="red", fontweight="bold", fontsize=11)
        ax1_twin.tick_params(axis="y", labelcolor="red")

        # VERBESSERTE TITEL-POSITIONIERUNG
        self.ax1.set_title(
            "🔧 Plattformposition über Zeit",
            fontweight="bold",
            fontsize=12,
            pad=20,
            color="blue",
        )
        ax1_twin.set_title(
            "⚡ Reifenkraft über Zeit",
            fontweight="bold",
            fontsize=12,
            pad=5,
            color="red",
        )

        # X-Achse nur beim unteren Plot
        self.ax1.set_xlabel("")  # Kein X-Label hier

        # Grid für bessere Lesbarkeit
        self.ax1.grid(True, alpha=0.3, linestyle="-", color="blue")
        ax1_twin.grid(True, alpha=0.3, linestyle="--", color="red")

        # VERBESSERUNG: Kombinierte Legende
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        self.ax1.legend(lines, labels, loc="upper left", framealpha=0.9, fontsize=10)

        # Y-Achsen-Limits automatisch anpassen
        self.ax1.margins(y=0.1)
        ax1_twin.margins(y=0.1)

    def _extract_value_robust(
        self, data: Dict, keys: List[str], default: float, field_name: str
    ) -> float:
        """
        ✅ KRITISCHE KORREKTUR: Robuste Datenextraktion mit NumPy Array Support

        Kann verarbeiten:
        - Skalare (int, float)
        - NumPy Arrays (nimmt letzten Wert)
        - Listen (nimmt letzten Wert)
        - Strings (versucht Konvertierung)
        """
        for key in keys:
            if key in data:
                raw_value = data[key]

                try:
                    # ✅ NUMPY ARRAY HANDLING
                    if isinstance(raw_value, np.ndarray):
                        self.numpy_conversion_stats["arrays_received"] += 1

                        if raw_value.size == 0:
                            if self.debug_enabled:
                                logger.debug(
                                    f"   ⚠️ {field_name}: Empty NumPy array for key '{key}'"
                                )
                            continue

                        # Nimm den letzten Wert (aktuellster)
                        if raw_value.ndim == 1:  # 1D Array
                            value = float(raw_value[-1])
                        else:  # Multi-dimensional
                            value = float(raw_value.flat[-1])  # Letztes Element

                        if np.isfinite(value):
                            self.numpy_conversion_stats["arrays_converted"] += 1
                            if self.debug_enabled and (self.update_count % 50 == 0):
                                logger.debug(
                                    f"   ✅ {field_name}: NumPy array[{raw_value.size}] → {value:.2f} (last value)"
                                )
                            return value
                        else:
                            if self.debug_enabled:
                                logger.warning(
                                    f"   ⚠️ {field_name}: NumPy array contains non-finite value: {value}"
                                )
                            continue

                    # ✅ LISTEN HANDLING
                    elif isinstance(raw_value, (list, tuple)):
                        if len(raw_value) == 0:
                            if self.debug_enabled:
                                logger.debug(
                                    f"   ⚠️ {field_name}: Empty list for key '{key}'"
                                )
                            continue

                        # Nimm den letzten Wert
                        value = float(raw_value[-1])
                        if np.isfinite(value):
                            if self.debug_enabled and (self.update_count % 50 == 0):
                                logger.debug(
                                    f"   ✅ {field_name}: List[{len(raw_value)}] → {value:.2f} (last value)"
                                )
                            return value
                        else:
                            if self.debug_enabled:
                                logger.warning(
                                    f"   ⚠️ {field_name}: List contains non-finite value: {value}"
                                )
                            continue

                    # ✅ SKALARE HANDLING
                    else:
                        # Direkter Skalar (int, float, string)
                        self.numpy_conversion_stats["scalars_received"] += 1
                        value = float(raw_value)

                        if np.isfinite(value):
                            if self.debug_enabled and (self.update_count % 50 == 0):
                                logger.debug(
                                    f"   ✅ {field_name}: Scalar {raw_value} → {value:.2f}"
                                )
                            return value
                        else:
                            if self.debug_enabled:
                                logger.warning(
                                    f"   ⚠️ {field_name}: Scalar non-finite value: {value}"
                                )
                            continue

                except (ValueError, TypeError, IndexError) as e:
                    self.numpy_conversion_stats["conversion_failures"] += 1
                    if self.debug_enabled:
                        logger.warning(
                            f"   ⚠️ {field_name}: Conversion failed for key '{key}' (type: {type(raw_value)}): {e}"
                        )
                    continue

            else:
                if self.debug_enabled and (self.update_count % 100 == 0):
                    logger.debug(f"   ❌ Key '{key}' not found for {field_name}")

        # Fallback auf Default
        if self.debug_enabled and (self.update_count % 50 == 0):
            logger.warning(
                f"   🚨 {field_name}: Using default value {default} (no valid data found)"
            )

        return default

    def _get_display_data(self) -> Dict[str, List[float]]:
        """Rolling-Window Datenextraktion."""
        if not self.time_data:
            return {
                "time": [],
                "platform": [],
                "force": [],
                "phase": [],
                "frequency": [],
            }

        latest_time = self.time_data[-1]
        window_start = max(0, latest_time - self.time_window)

        # Daten im Zeitfenster sammeln
        display_time = []
        display_platform = []
        display_force = []
        display_phase = []
        display_frequency = []

        for i, t in enumerate(self.time_data):
            if t >= window_start:
                relative_t = t - window_start
                display_time.append(relative_t)
                display_platform.append(self.platform_data[i])
                display_force.append(self.force_data[i])
                display_phase.append(self.phase_data[i])
                display_frequency.append(self.frequency_data[i])

        return {
            "time": display_time,
            "platform": display_platform,
            "force": display_force,
            "phase": display_phase,
            "frequency": display_frequency,
        }

    def _update_charts_display(self, display_data: Dict[str, List[float]]):
        """Chart-Update mit Datenvalidierung."""
        time_data = display_data["time"]

        if not time_data:
            return

        data_mapping = {
            "platform": display_data["platform"],
            "force": display_data["force"],
            "phase": display_data["phase"],
            "frequency": display_data["frequency"],
        }

        for chart_name, y_data in data_mapping.items():
            if chart_name in self.lines and len(y_data) == len(time_data):
                # Line-Daten setzen
                self.lines[chart_name].set_data(time_data, y_data)

                # Achsen-Limits aktualisieren
                ax = self.axes[chart_name]
                ax.set_xlim(0, self.time_window)

                # Y-Achse auto-scale
                if y_data and len(y_data) > 0:
                    y_min, y_max = min(y_data), max(y_data)
                    if y_max != y_min:
                        margin = (y_max - y_min) * 0.1
                        ax.set_ylim(y_min - margin, y_max + margin)
                    else:
                        # Fallback für konstante Werte
                        if abs(y_min) > 0.01:  # Nicht-Null-Werte
                            margin = max(abs(y_min) * 0.1, 1.0)
                            ax.set_ylim(y_min - margin, y_max + margin)
                        else:
                            ax.set_ylim(-1, 1)  # Standard für Null-Werte

        # Canvas aktualisieren
        self.canvas.draw_idle()

    def clear_charts(self):
        """Leert alle Chart-Daten."""
        try:
            logger.info("🗑️ Clearing all chart data...")

            # Alle Buffers leeren
            self.time_data.clear()
            self.platform_data.clear()
            self.force_data.clear()
            self.phase_data.clear()
            self.frequency_data.clear()

            # Startzeit zurücksetzen
            self.start_time = None

            # Line-Daten zurücksetzen
            for line in self.lines.values():
                line.set_data([], [])

            # Achsen neu skalieren
            for ax in self.axes.values():
                ax.relim()
                ax.autoscale()
                ax.set_xlim(0, self.time_window)

            # Canvas neu zeichnen
            self.canvas.draw()

            # Counters zurücksetzen
            self.update_count = 0
            self.last_update_time = time.time()
            self.numpy_conversion_stats = {
                "arrays_received": 0,
                "arrays_converted": 0,
                "scalars_received": 0,
                "conversion_failures": 0,
            }

            logger.info("✅ Charts cleared successfully")

        except Exception as e:
            logger.error(f"❌ Error clearing charts: {e}", exc_info=True)

    def _start_update_cycle(self):
        """Startet den Update-Zyklus."""
        self._schedule_next_update()

    def _schedule_next_update(self):
        """Plant nächstes Update."""
        try:
            if hasattr(self.canvas, "get_tk_widget"):
                self.canvas.get_tk_widget().after(
                    self.update_interval, self._schedule_next_update
                )
        except Exception as e:
            logger.error(f"❌ Update scheduling error: {e}")
            if hasattr(self.canvas, "get_tk_widget"):
                self.canvas.get_tk_widget().after(1000, self._schedule_next_update)

    def configure_performance(
        self,
        time_window: float = None,
        max_points: int = None,
        update_interval: int = None,
        debug_enabled: bool = None,
    ):
        """Konfiguriert Performance-Einstellungen."""
        if time_window is not None:
            self.time_window = max(1.0, time_window)
            logger.info(f"⚙️ Time window set to {self.time_window}s")

        if max_points is not None:
            self.max_points = max(100, max_points)
            logger.info(f"⚙️ Max points set to {self.max_points}")

        if update_interval is not None:
            self.update_interval = max(20, update_interval)
            logger.info(f"⚙️ Update interval set to {self.update_interval}ms")

        if debug_enabled is not None:
            self.debug_enabled = debug_enabled
            logger.info(f"⚙️ Debug mode: {'enabled' if debug_enabled else 'disabled'}")

    def get_debug_info(self) -> Dict[str, Any]:
        """Gibt Debug-Informationen zurück."""
        debug_info = {
            "data_flow": {
                "total_chart_updates": self.update_count,
                "numpy_stats": self.numpy_conversion_stats.copy(),
            },
            "buffers": {
                "time_points": len(self.time_data),
                "platform_points": len(self.platform_data),
                "force_points": len(self.force_data),
                "phase_points": len(self.phase_data),
                "frequency_points": len(self.frequency_data),
            },
            "performance": {
                "time_window": self.time_window,
                "max_points": self.max_points,
                "update_interval": self.update_interval,
            },
        }

        # Buffer-Samples (letzte Werte)
        if self.time_data:
            debug_info["buffer_samples"] = {
                "time": list(self.time_data)[-5:],
                "platform": list(self.platform_data)[-5:],
                "force": list(self.force_data)[-5:],
                "phase": list(self.phase_data)[-5:],
                "frequency": list(self.frequency_data)[-5:],
            }

        return debug_info

    def print_debug_summary(self):
        """Druckt Debug-Zusammenfassung."""
        debug_info = self.get_debug_info()

        print("\n" + "=" * 60)
        print("🔍 CHART WIDGET DEBUG SUMMARY")
        print("=" * 60)

        print("📊 DATA FLOW:")
        print(f"   Chart updates: {debug_info['data_flow']['total_chart_updates']}")

        numpy_stats = debug_info["data_flow"]["numpy_stats"]
        print("\n🔢 NUMPY CONVERSION STATS:")
        print(f"   Arrays received: {numpy_stats['arrays_received']}")
        print(f"   Arrays converted: {numpy_stats['arrays_converted']}")
        print(f"   Scalars received: {numpy_stats['scalars_received']}")
        print(f"   Conversion failures: {numpy_stats['conversion_failures']}")

        print("\n📈 BUFFER STATUS:")
        for name, count in debug_info["buffers"].items():
            print(f"   {name}: {count} points")

        if "buffer_samples" in debug_info:
            print("\n📋 RECENT VALUES:")
            for name, values in debug_info["buffer_samples"].items():
                if values:
                    print(
                        f"   {name}: [{values[0]:.2f} ... {values[-1]:.2f}] (range: {len(values)} points)"
                    )

        print("=" * 60 + "\n")


# Factory-Funktion
def create_chart_widget(
    parent_container: tk.Widget, debug_enabled: bool = True
) -> ChartWidget:
    """Factory-Funktion für NumPy-kompatibles ChartWidget."""
    return ChartWidget(parent_container, debug_enabled)


# Kompatibilitäts-Alias
OptimizedChartWidget = ChartWidget

# Test-Implementierung
if __name__ == "__main__":
    import random

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🔧 Chart Widget - NumPy Array Support")
    print("=" * 50)
    print("✅ Kann NumPy Arrays verarbeiten")
    print("✅ Nimmt letzten Wert aus Arrays")
    print("✅ Robuste Datenextraktion")
    print("=" * 50)

    root = tk.Tk()
    root.title("Chart Widget - NumPy Test")
    root.geometry("1200x800")

    # Chart-Widget erstellen
    chart_widget = create_chart_widget(root, debug_enabled=True)

    # Control-Panel
    control_frame = ttk.Frame(root)
    control_frame.pack(fill="x", padx=10, pady=5)

    test_running = False

    def toggle_test():
        global test_running
        test_running = not test_running
        if test_running:
            start_button.config(text="⏹️ Stop")
            generate_numpy_test_data()
        else:
            start_button.config(text="▶️ Start")

    def clear_charts():
        chart_widget.clear_charts()

    def show_debug():
        chart_widget.print_debug_summary()

    start_button = ttk.Button(control_frame, text="▶️ Start", command=toggle_test)
    start_button.pack(side="left", padx=(0, 5))

    ttk.Button(control_frame, text="🗑️ Clear", command=clear_charts).pack(
        side="left", padx=5
    )
    ttk.Button(control_frame, text="📋 Debug", command=show_debug).pack(
        side="left", padx=5
    )

    def generate_numpy_test_data():
        """Generiert Test-Daten mit NumPy Arrays (wie im echten System)."""
        if not test_running:
            return

        try:
            # Simuliere MQTT-Payload mit NumPy Arrays
            batch_size = random.randint(10, 50)  # Variable Array-Größen

            # NumPy Arrays erstellen (wie sie vom echten System kommen)
            time_array = np.full(batch_size, time.time())
            frequency_array = np.linspace(25.0, 6.0, batch_size) + np.random.uniform(
                -0.5, 0.5, batch_size
            )
            platform_array = 3.0 * np.sin(frequency_array) + np.random.uniform(
                -0.5, 0.5, batch_size
            )
            force_array = (
                500
                + 50 * np.sin(frequency_array + np.pi / 4)
                + np.random.uniform(-20, 20, batch_size)
            )
            phase_array = (
                35.0
                + 10 * np.sin(frequency_array * 0.1)
                + np.random.uniform(-2, 2, batch_size)
            )

            # MQTT-Payload simulieren (genau wie im echten System)
            mqtt_data = {
                "time": time_array,
                "platform_position": platform_array,
                "tire_force": force_array,
                "frequency": frequency_array,
                "phase_shift": phase_array,
                "egea_status": {"min_phase_shift": None, "quality_index": 0.0},
                "test_active": True,
            }

            # Chart aktualisieren
            chart_widget.update_charts(mqtt_data)

            # Nächste Iteration
            root.after(100, generate_numpy_test_data)  # 10 Hz Updates

        except Exception as e:
            logger.error(f"Test data error: {e}")
            root.after(1000, generate_numpy_test_data)

    logger.info("🧪 NumPy Array Test ready - this simulates the real MQTT data format")
    root.mainloop()