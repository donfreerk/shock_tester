# suspension_core/setup.py
from setuptools import find_packages, setup

setup(
	name="fahrwerkstester-common",
	version="1.0.0",
	description="Common library for Fahrwerkstester applications",
	packages=find_packages(),
	install_requires=[
		"paho-mqtt>=1.6",
		"pyyaml>=5.4",
		"python-can>=4.0.0",
		"numpy>=1.20.0",
		"pyserial>=3.5",
	],
	classifiers=[
		"Development Status :: 4 - Beta",
		"Intended Audience :: Developers",
		"Programming Language :: Python :: 3",
		"Programming Language :: Python :: 3.8",
		"Programming Language :: Python :: 3.9",
		"Programming Language :: Python :: 3.10",
		"Topic :: Software Development :: Libraries",
	],
	python_requires=">=3.8",
)