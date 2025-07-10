"""
Main Window View for EGEA Suspension Tester - Refactored MVP Architecture.

Responsibility: Main UI layout and component coordination.
Uses separate components for status, controls, and charts.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any
import logging

# Import our refactored UI components
from .status_bar import StatusBar
from .control_panel import ControlPanel
from .discovery_dialog import DiscoveryDialog

logger = logging.getLogger(__name__)


class MainWindow:
	"""
	Main window view component - now using MVP refactored components.

	Coordinates separate UI components:
	- StatusBar: System status and connection info
	- ControlPanel: Test controls and settings
	- ChartWidget: Data visualization (injected externally)
	- DiscoveryDialog: MQTT broker discovery
	"""

	def __init__(self, root: tk.Tk):
		self.root = root
		self.root.title("🎯 EGEA-Fahrwerkstester - MVP Refactored")
		self.root.geometry("1500x1000")

		# Callbacks to presenter (injected later)
		self.presenter_callbacks = {}

		# UI Components (created in _setup_ui)
		self.status_bar = None
		self.control_panel = None
		self.chart_widget = None
		self.test_log = None

		# UI Containers
		self.chart_container = None
		self.log_container = None

		self._setup_ui()
		self._setup_window_callbacks()

		logger.info("MainWindow initialized with MVP components")

	def _setup_ui(self):
		"""Creates the main UI layout with component containers."""
		# Main container with grid
		self.root.grid_rowconfigure(0, weight=1)
		self.root.grid_columnconfigure(0, weight=1)

		main_container = ttk.Frame(self.root)
		main_container.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
		main_container.grid_rowconfigure(3, weight=1)  # Chart area expandable
		main_container.grid_columnconfigure(0, weight=1)

		# 1. Status Bar Section (using StatusBar component)
		self._setup_status_section(main_container)

		# 2. Visualization Options Section (NEW)
		self._setup_visualization_options(main_container)

		# 3. Chart Section (container for injected ChartWidget)
		self._setup_chart_section(main_container)

		# 4. Control Panel Section (using ControlPanel component)
		self._setup_control_section(main_container)

		# 5. Log Section (simple log display)
		self._setup_log_section(main_container)

	def _setup_status_section(self, parent):
		"""Creates status display section using StatusBar component."""
		# Create container for StatusBar
		status_container = ttk.Frame(parent)
		status_container.grid(row=0, column=0, sticky='ew', pady=(0, 10))

		# Create StatusBar component
		self.status_bar = StatusBar(status_container)

		logger.info("StatusBar component integrated")

	def _setup_chart_section(self, parent):
		"""Creates chart display section (container for external ChartWidget)."""
		chart_frame = ttk.LabelFrame(parent, text="📈 Live Data Visualization", padding="5")
		chart_frame.grid(row=1, column=0, sticky='nsew', pady=(0, 10))

		# Container for chart widget (will be injected)
		self.chart_container = chart_frame

		logger.info("Chart container prepared")

	def _setup_visualization_options(self, parent):
		"""Creates visualization options section (container for DataVisualizationOptionsWidget)."""
		# Container for visualization options
		self.viz_options_container = ttk.Frame(parent)
		self.viz_options_container.grid(row=1, column=0, sticky='ew', pady=(0, 10))

		# The actual widget will be injected by the presenter
		logger.info("Visualization options container prepared")

	def set_visualization_options_widget(self, widget):
		"""Sets the visualization options widget."""
		if hasattr(self, 'viz_options_widget'):
			self.viz_options_widget.destroy()

		self.viz_options_widget = widget
		if widget:
			widget.pack(fill=tk.BOTH, expand=True)

		logger.info("Visualization options widget integrated")

	def _setup_control_section(self, parent):
		"""Creates control panel section using ControlPanel component."""
		# Create container for ControlPanel
		control_container = ttk.Frame(parent)
		control_container.grid(row=2, column=0, sticky='ew', pady=(0, 10))

		# Create ControlPanel component
		self.control_panel = ControlPanel(control_container)

		logger.info("ControlPanel component integrated")

	def _setup_log_section(self, parent):
		"""Creates simplified log display section."""
		log_frame = ttk.LabelFrame(parent, text="📋 System Log", padding="5")
		log_frame.grid(row=3, column=0, sticky='ew')

		# Log controls
		log_controls = ttk.Frame(log_frame)
		log_controls.pack(fill=tk.X, pady=(0, 5))

		ttk.Button(log_controls, text="🗑 Clear Log",
		           command=self._clear_log).pack(side=tk.LEFT, padx=(0, 10))

		ttk.Button(log_controls, text="💾 Save Log",
		           command=self._save_log).pack(side=tk.LEFT, padx=(0, 10))

		# Log level filter
		ttk.Label(log_controls, text="Level:").pack(side=tk.LEFT, padx=(20, 5))
		self.log_level_var = tk.StringVar(value="All")
		log_level_combo = ttk.Combobox(log_controls, textvariable=self.log_level_var,
		                               values=["All", "Error", "Warning", "Info", "Success"],
		                               state="readonly", width=8)
		log_level_combo.pack(side=tk.LEFT)

		# ScrolledText for log
		from tkinter import scrolledtext
		self.test_log = scrolledtext.ScrolledText(log_frame, height=6, state=tk.DISABLED,
		                                          font=("Courier", 9))
		self.test_log.pack(fill=tk.BOTH, expand=True)

		# Tag configuration for colored messages
		self.test_log.tag_config("error", foreground="red", font=("Courier", 9, "bold"))
		self.test_log.tag_config("success", foreground="green", font=("Courier", 9, "bold"))
		self.test_log.tag_config("warning", foreground="orange", font=("Courier", 9, "bold"))
		self.test_log.tag_config("info", foreground="blue")
		self.test_log.tag_config("debug", foreground="gray")

		logger.info("Log section initialized")

	def _setup_window_callbacks(self):
		"""Setup window-level callbacks."""
		self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

		# Handle window state changes
		self.root.bind("<Configure>", self._on_window_configure)

	def _on_window_configure(self, event):
		"""Handles window resize/configure events."""
		# Only handle root window events
		if event.widget == self.root:
			# Could add responsive layout adjustments here
			pass

	def _on_window_close(self):
		"""Handles window close event."""
		logger.info("Window close requested")

		# Confirm close if test is running
		if self.control_panel and self.control_panel.test_active_var.get():
			response = self.show_message_box(
				"Test Running",
				"A test is currently running. Do you want to stop it and exit?",
				"question"
			)
			if response != 'yes':
				return

		# Call presenter callback
		if self.presenter_callbacks.get('on_closing'):
			self.presenter_callbacks['on_closing']()
		else:
			self.root.destroy()

	def _clear_log(self):
		"""Clears the test log."""
		if self.test_log:
			self.test_log.config(state=tk.NORMAL)
			self.test_log.delete(1.0, tk.END)
			self.test_log.config(state=tk.DISABLED)
			self.log_message("System", "Log cleared", "info")

	def _save_log(self):
		"""Saves the test log to file."""
		try:
			from tkinter import filedialog
			import time

			# Generate default filename with timestamp
			timestamp = time.strftime("%Y%m%d_%H%M%S")
			default_filename = f"egea_test_log_{timestamp}.txt"

			filename = filedialog.asksaveasfilename(
				title="Save Test Log",
				defaultextension=".txt",
				filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
				initialvalue=default_filename
			)

			if filename:
				log_content = self.test_log.get('1.0', tk.END)
				with open(filename, 'w', encoding='utf-8') as f:
					f.write(log_content)
				self.log_message("System", f"Log saved to {filename}", "success")

		except Exception as e:
			logger.error(f"Error saving log: {e}")
			self.show_message_box("Error", f"Failed to save log: {e}", "error")

	# =================================================================
	# Discovery Dialog Integration
	# =================================================================

	def show_discovery_dialog(self) -> Optional[Dict[str, Any]]:
		"""Shows the discovery dialog and returns selected broker."""
		try:
			discovery_dialog = DiscoveryDialog(self.root)

			# Set discovery callbacks from presenter
			if hasattr(self, '_discovery_callbacks'):
				discovery_dialog.set_callbacks(self._discovery_callbacks)

			result = discovery_dialog.show()

			if result:
				self.log_message("Discovery", f"Selected broker: {result.get('ip')}", "success")
			else:
				self.log_message("Discovery", "Discovery cancelled", "info")

			return result

		except Exception as e:
			logger.error(f"Error showing discovery dialog: {e}")
			self.show_message_box("Error", f"Discovery dialog error: {e}", "error")
			return None

	def set_discovery_callbacks(self, callbacks: Dict[str, Callable]):
		"""Sets callbacks for discovery dialog operations."""
		self._discovery_callbacks = callbacks
		logger.info("Discovery callbacks configured")

	# =================================================================
	# Component Integration Methods
	# =================================================================

	def set_callbacks(self, callbacks: Dict[str, Callable]):
		"""Sets callback functions from presenter and distributes to components."""
		self.presenter_callbacks = callbacks

		# Distribute callbacks to components
		self._distribute_callbacks_to_components()

		logger.info("Presenter callbacks distributed to components")

	def _distribute_callbacks_to_components(self):
		"""Distributes presenter callbacks to individual UI components."""
		# StatusBar callbacks
		if self.status_bar:
			status_callbacks = {
				'on_mqtt_reconnect': self.presenter_callbacks.get('on_reconnect_mqtt'),
				'on_discovery_open': self._handle_discovery_request,
				'on_status_details': self.presenter_callbacks.get('on_status_details')
			}
			self.status_bar.set_callbacks(status_callbacks)

		# ControlPanel callbacks
		if self.control_panel:
			control_callbacks = {
				'on_start_test': self.presenter_callbacks.get('on_start_test'),
				'on_stop_test': self.presenter_callbacks.get('on_stop_test'),
				'on_emergency_stop': self.presenter_callbacks.get('on_emergency_stop'),
				'on_clear_buffer': self.presenter_callbacks.get('on_clear_buffer'),
				'on_send_command': self.presenter_callbacks.get('on_send_command')
			}
			self.control_panel.set_callbacks(control_callbacks)

	def _handle_discovery_request(self):
		"""Handles discovery request from status bar."""
		if self.presenter_callbacks.get('on_discovery_dialog'):
			self.presenter_callbacks['on_discovery_dialog']()
		else:
			# Fallback: show discovery dialog directly
			result = self.show_discovery_dialog()
			if result and self.presenter_callbacks.get('on_broker_selected'):
				self.presenter_callbacks['on_broker_selected'](result)

	# =================================================================
	# Public Interface for Presenter (delegates to components)
	# =================================================================

	def update_broker_status(self, broker_ip: str = None, status: str = None, connected: bool = None):
		"""Updates MQTT broker status display."""
		if self.status_bar:
			self.status_bar.update_mqtt_status(broker_ip, status, connected)

	def update_data_count(self, count: int):
		"""Updates data count display."""
		if self.status_bar:
			self.status_bar.update_data_status(count=count)

	def update_data_status(self, count: int = None, rate: float = None, buffer_usage: float = None):
		"""Updates complete data status."""
		if self.status_bar:
			self.status_bar.update_data_status(count, rate, buffer_usage)

	def update_egea_status(self, status: Dict[str, Any]):
		"""Updates EGEA status display."""
		if self.status_bar:
			evaluation = status.get("evaluation", "insufficient_data")
			phase_shift = status.get("min_phase_shift")
			quality = status.get("quality_index", 0)

			# Determine passing status
			passing = None
			if evaluation == "passing":
				passing = True
			elif evaluation == "failing":
				passing = False

			self.status_bar.update_egea_status(
				status=evaluation,
				phase_shift=phase_shift,
				quality=quality,
				passing=passing
			)

	def update_performance_status(self, metrics: Dict[str, Any]):
		"""Updates performance metrics display."""
		if self.status_bar:
			self.status_bar.update_performance_status(metrics)

	def set_test_active(self, active: bool):
		"""Updates UI for test active state."""
		if self.control_panel:
			self.control_panel.set_test_active(active)

		if self.status_bar:
			self.status_bar.set_test_active(active)

		# Log test state change
		state_text = "started" if active else "stopped"
		self.log_message("Test", f"Test {state_text}", "info")

	def enable_controls(self, enabled: bool = True):
		"""Enables/disables all controls."""
		if self.control_panel:
			self.control_panel.enable_controls(enabled)

	def get_test_parameters(self) -> Dict[str, Any]:
		"""Gets current test parameters from control panel."""
		if self.control_panel:
			return self.control_panel.get_test_parameters()
		return {}

	def set_test_parameters(self, position: str = None, vehicle: str = None, duration: float = None):
		"""Sets test parameters in control panel."""
		if self.control_panel:
			self.control_panel.set_test_parameters(position, vehicle, duration)

	def log_message(self, category: str, message: str, level: str = "info"):
		"""Adds message to test log with filtering."""
		try:
			if not self.test_log:
				return

			# Check log level filter
			current_filter = self.log_level_var.get()
			if current_filter != "All":
				if current_filter.lower() != level.lower():
					return

			import time
			timestamp = time.strftime("%H:%M:%S")
			formatted_message = f"[{timestamp}] {category}: {message}\n"

			self.test_log.config(state=tk.NORMAL)
			self.test_log.insert(tk.END, formatted_message, level)
			self.test_log.see(tk.END)
			self.test_log.config(state=tk.DISABLED)

			# Also log to Python logger
			if level == "error":
				logger.error(f"{category}: {message}")
			elif level == "warning":
				logger.warning(f"{category}: {message}")
			else:
				logger.info(f"{category}: {message}")

		except Exception as e:
			logger.error(f"Error logging message: {e}")

	def set_chart_widget(self, chart_widget):
		"""Sets the chart widget component."""
		self.chart_widget = chart_widget

		# Pack chart widget into container
		if hasattr(chart_widget, 'widget') and self.chart_container:
			chart_widget.widget.pack(fill=tk.BOTH, expand=True)
			self.log_message("System", "Chart widget integrated", "info")
		else:
			logger.warning("Chart widget or container not available")

	def show_message_box(self, title: str, message: str, msg_type: str = "info"):
		"""Shows message box to user."""
		from tkinter import messagebox

		try:
			if msg_type == "error":
				messagebox.showerror(title, message)
			elif msg_type == "warning":
				messagebox.showwarning(title, message)
			elif msg_type == "question":
				return messagebox.askquestion(title, message)
			else:
				messagebox.showinfo(title, message)
		except Exception as e:
			logger.error(f"Error showing message box: {e}")

	def show(self):
		"""Shows the main window."""
		self.root.deiconify()
		self.log_message("System", "Main window shown", "info")

	def hide(self):
		"""Hides the main window."""
		self.root.withdraw()
		self.log_message("System", "Main window hidden", "info")

	def get_window_geometry(self) -> str:
		"""Gets current window geometry."""
		return self.root.geometry()

	def set_window_geometry(self, geometry: str):
		"""Sets window geometry."""
		self.root.geometry(geometry)

	def get_current_status(self) -> Dict[str, Any]:
		"""Gets current status from all components."""
		status = {
			'window': {
				'geometry': self.get_window_geometry(),
				'title': self.root.title()
			}
		}

		# Get status from components
		if self.status_bar:
			status['status_bar'] = self.status_bar.get_current_status()

		if self.control_panel:
			status['control_panel'] = self.control_panel.get_test_parameters()

		return status

	# =================================================================
	# Utility Methods
	# =================================================================

	def center_window(self):
		"""Centers the window on screen."""
		self.root.update_idletasks()
		x = (self.root.winfo_screenwidth() // 2) - (self.root.winfo_width() // 2)
		y = (self.root.winfo_screenheight() // 2) - (self.root.winfo_height() // 2)
		self.root.geometry(f"+{x}+{y}")

		self.log_message("System", "Window centered", "info")

	def minimize_window(self):
		"""Minimizes the window."""
		self.root.iconify()

	def maximize_window(self):
		"""Maximizes the window."""
		self.root.state('zoomed')  # Windows
		# For Linux/Mac: self.root.attributes('-zoomed', True)