from setuptools import setup, find_packages

setup(
    name="suspension_tester",
    version="0.2.0",  # Version erhöhen wegen größerer Änderungen
    packages=find_packages(),
    install_requires=[
        "paho-mqtt>=2.0.0",  # Aktualisierte Version ohne Deprecation-Warnungen
        "python-can>=4.0.0",
        "numpy",
        "scipy",
        "plotext",
        "pydantic>=1.10.0",  # Für die zentrale Konfigurationsklasse
    ],
    entry_points={
        "console_scripts": [
            "suspension-tester=suspension_tester.main:main",
            "can-monitor=suspension_tester.tools.can_monitor:main",
            "mqtt-tool=suspension_tester.tools.mqtt_tool:main",
        ],
    },
    python_requires=">=3.8",
)