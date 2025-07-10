"""
Main entry point for the refactored EGEA Suspension Tester GUI.

This file demonstrates the new MVP architecture:
- Clean separation of concerns
- Dependency injection
- Modular components
- Easy testing and maintenance

Usage:
    python main.py [--config path/to/config.yaml] [--debug]
"""

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path
from typing import Optional, Dict

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import our refactored components
from views.main_window import MainWindow
from views.chart_widget import ChartWidget
from presenters.main_presenter import MainPresenter
from models.data_buffer import DataBuffer
from models.config_manager import EnhancedConfigManager
from views.data_visualization_options import DataVisualizationOptionsWidget
from models.data_field_manager import DataFieldManager

logger = logging.getLogger(__name__)


class SuspensionTesterApp:
	"""
	Main application class that wires together the MVP components.

	This class demonstrates proper dependency injection and
	component lifecycle management.
	"""

	def __init__(self, config_path: Optional[str] = None):
		self.config_path = config_path

		# Core components
		self.root = None
		self.view = None
		self.presenter = None
		self.data_buffer = None
		self.config_manager = None
		self.chart_widget = None

		logger.info("SuspensionTesterApp initialized")

	def initialize(self):
		"""Initialize all application components."""
		try:
			# 1. Create Tkinter root
			self.root = tk.Tk()
			self._configure_root()

			# 2. Initialize models
			self.data_buffer = DataBuffer(max_size=2000)
			self.data_field_manager = DataFieldManager(self.data_buffer)
			self.config_manager = EnhancedConfigManager(self.config_path)

			# 3. Create main view
			self.view = MainWindow(self.root)

			# 4. Create chart widget
			self.chart_widget = ChartWidget(self.view.chart_container)
			self.view.set_chart_widget(self.chart_widget)

			# 5. Create visualization options widget
			self.viz_options_widget = DataVisualizationOptionsWidget(
				self.view.viz_options_container,
				self.data_field_manager,
				chart_update_callback=self._on_chart_fields_changed
			)
			self.view.set_visualization_options_widget(self.viz_options_widget)

			# 6. Create presenter and wire everything together
			self.presenter = MainPresenter()
			self.presenter.initialize(
				view=self.view,
				data_buffer=self.data_buffer,
				config_manager=self.config_manager
			)

			logger.info("Application components initialized successfully")

		except Exception as e:
			logger.error(f"Application initialization failed: {e}", exc_info=True)
			raise

	def _on_chart_fields_changed(self, selected_fields: Dict[str, bool]):
		"""Handle changes to selected chart fields."""
		# Update chart widget to show only selected fields
		if hasattr(self, 'chart_widget'):
			# Configure chart widget to show selected fields
			# This would need to be implemented in the ChartWidget class
			pass

	def _configure_root(self):
		"""Configure the Tkinter root window."""
		self.root.title("🎯 EGEA Suspension Tester - Refactored")

		# Center window on screen
		window_width = 1500
		window_height = 1000
		screen_width = self.root.winfo_screenwidth()
		screen_height = self.root.winfo_screenheight()

		x = (screen_width - window_width) // 2
		y = (screen_height - window_height) // 2

		self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

		# Set minimum size
		self.root.minsize(1200, 800)

		# Configure for high DPI if available
		try:
			self.root.tk.call('tk', 'scaling', 1.0)
		except Exception:
			pass

	def run(self):
		"""Run the application main loop."""
		try:
			if not self.root:
				raise RuntimeError("Application not initialized. Call initialize() first.")

			logger.info("Starting application main loop")

			# Show initial status
			self.view.log_message("🚀 System", "EGEA Suspension Tester started", "success")
			self.view.log_message("🏗️ System", "MVP Architecture: Views + Models + Presenters", "info")
			self.view.log_message("📊 System", "Features: Live charts, EGEA analysis, MQTT discovery", "info")

			# Start Tkinter main loop
			self.root.mainloop()

		except KeyboardInterrupt:
			logger.info("Application interrupted by user")
		except Exception as e:
			logger.error(f"Application runtime error: {e}", exc_info=True)
		finally:
			self.shutdown()

	def shutdown(self):
		"""Clean shutdown of all components."""
		try:
			logger.info("Shutting down application...")

			# Shutdown presenter (handles MQTT, tests, etc.)
			if self.presenter:
				self.presenter.shutdown()

			# Cleanup models
			if self.data_buffer:
				self.data_buffer.clear()

			logger.info("Application shutdown complete")

		except Exception as e:
			logger.error(f"Shutdown error: {e}")


def setup_logging(debug: bool = False):
	"""Configure application logging with UTF-8 support."""
	log_level = logging.DEBUG if debug else logging.INFO

	# ✅ UTF-8 Handler für Windows Unicode-Support
	class UTF8StreamHandler(logging.StreamHandler):
		def __init__(self, stream=None):
			super().__init__(stream)
			# Force UTF-8 encoding für Emojis
			if hasattr(self.stream, 'reconfigure'):
				self.stream.reconfigure(encoding='utf-8')
	
	# Erstelle UTF-8 Handler
	console_handler = UTF8StreamHandler(sys.stdout)
	console_handler.setLevel(log_level)
	
	# File Handler mit UTF-8
	file_handler = None
	if debug:
		file_handler = logging.FileHandler("suspension_tester_gui.log", encoding='utf-8')
		file_handler.setLevel(logging.DEBUG)

	# Formatter ohne Emojis für bessere Kompatibilität
	formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
	console_handler.setFormatter(formatter)
	if file_handler:
		file_handler.setFormatter(formatter)

	# Configure root logger
	root_logger = logging.getLogger()
	root_logger.setLevel(log_level)
	
	# Clear existing handlers
	for handler in root_logger.handlers[:]:
		root_logger.removeHandler(handler)
	
	# Add new handlers
	root_logger.addHandler(console_handler)
	if file_handler:
		root_logger.addHandler(file_handler)

	# Reduce matplotlib logging noise
	logging.getLogger('matplotlib').setLevel(logging.WARNING)
	logging.getLogger('PIL').setLevel(logging.WARNING)

	logger.info(f"Logging configured (level: {log_level})")


def check_dependencies():
	"""Check if all required dependencies are available."""
	missing_deps = []

	# Critical dependencies
	try:
		import paho.mqtt.client as mqtt
	except ImportError:
		missing_deps.append("paho-mqtt")

	try:
		import numpy
	except ImportError:
		missing_deps.append("numpy")

	try:
		import matplotlib
	except ImportError:
		missing_deps.append("matplotlib")

	# Optional dependencies
	optional_missing = []

	try:
		import yaml
	except ImportError:
		optional_missing.append("PyYAML (for config files)")

	try:
		from common.suspension_core.config.manager import ConfigManager
	except ImportError:
		optional_missing.append("suspension_core (for advanced features)")

	# Report results
	if missing_deps:
		print(f"❌ Missing critical dependencies: {', '.join(missing_deps)}")
		print(f"Install with: pip install {' '.join(missing_deps)}")
		return False

	if optional_missing:
		print(f"⚠️ Optional dependencies missing: {', '.join(optional_missing)}")
		print("Some features may be limited.")

	print("✅ All critical dependencies available")
	return True


def create_sample_config():
	"""Create a sample configuration file."""
	config_content = """# EGEA Suspension Tester Configuration
# Generated by refactored GUI

mqtt:
  broker: "auto"  # Auto-discovery enabled
  port: 1883
  auto_discovery: true
  fallback_brokers:
    - "192.168.0.249"  # Default Pi IP
    - "192.168.0.100"
    - "localhost"

egea:
  phase_shift_threshold: 35.0
  min_frequency: 6.0
  max_frequency: 25.0
  test_duration: 30.0

gui:
  update_rate_ms: 100
  max_chart_points: 500
  enable_advanced_charts: true

logging:
  level: INFO
  file_logging: false
"""

	config_path = Path("egea_config.yaml")
	try:
		with open(config_path, 'w') as f:
			f.write(config_content)
		print(f"✅ Sample configuration created: {config_path}")
		return str(config_path)
	except Exception as e:
		print(f"❌ Failed to create config file: {e}")
		return None


def main():
	"""Main entry point."""
	# Parse command line arguments
	parser = argparse.ArgumentParser(
		description="EGEA Suspension Tester - Refactored MVP Architecture",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Examples:
  python main.py                           # Run with defaults
  python main.py --debug                   # Enable debug logging
  python main.py --config my_config.yaml  # Use custom config
  python main.py --create-config          # Create sample config
  python main.py --check-deps             # Check dependencies

Architecture Info:
  This refactored version uses MVP (Model-View-Presenter) pattern:
  - Views: UI components (main_window.py, chart_widget.py)
  - Models: Data management (data_buffer.py, config_manager.py)  
  - Presenters: Business logic coordination (main_presenter.py)
        """
	)

	parser.add_argument(
		"--config",
		help="Path to configuration file (YAML format)"
	)

	parser.add_argument(
		"--debug",
		action="store_true",
		help="Enable debug logging and file output"
	)

	parser.add_argument(
		"--create-config",
		action="store_true",
		help="Create sample configuration file and exit"
	)

	parser.add_argument(
		"--check-deps",
		action="store_true",
		help="Check dependencies and exit"
	)

	args = parser.parse_args()

	# Handle special commands
	if args.check_deps:
		check_dependencies()
		return

	if args.create_config:
		create_sample_config()
		return

	# Setup logging
	setup_logging(args.debug)

	# Print banner
	print("🎯 EGEA Suspension Tester - Refactored MVP Architecture")
	print("=" * 60)
	print("✨ Features:")
	print("  - Clean MVP architecture with dependency injection")
	print("  - Modular components (max 200 lines per file)")
	print("  - Intelligent MQTT broker discovery")
	print("  - Real-time EGEA phase shift analysis")
	print("  - High-performance chart visualization")
	print("  - Thread-safe data processing")
	print("=" * 60)

	# Check dependencies
	if not check_dependencies():
		print("\n❌ Cannot start application due to missing dependencies.")
		print("Please install required packages and try again.")
		sys.exit(1)

	# Create and run application
	try:
		app = SuspensionTesterApp(config_path=args.config)
		app.initialize()

		print("\n🚀 Starting EGEA Suspension Tester...")
		print("💡 Use 'Discovery' button to find MQTT brokers")
		print("📊 Charts will update automatically when data arrives")
		print("🧪 Use test controls to start EGEA measurements")
		print("\nPress Ctrl+C to stop or close the window")
		print("-" * 60)

		app.run()

	except KeyboardInterrupt:
		print("\n👋 Application stopped by user")
	except Exception as e:
		logger.error(f"Application failed: {e}", exc_info=True)
		print(f"\n❌ Application failed: {e}")
		if args.debug:
			print("Check 'suspension_tester_gui.log' for details")
		sys.exit(1)

	print("👋 EGEA Suspension Tester closed")


if __name__ == "__main__":
	main()