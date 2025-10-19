#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LanCalc - IPv4 subnet calculator with GUI and CLI interfaces.

A cross-platform tool for calculating IPv4 network parameters including
network address, broadcast address, host range, and special IPv4 range detection.
"""

__version__ = "0.1.11"
__author__ = 'Aleksandr Pimenov'
__email__ = 'wachawo@gmail.com'

# Import modules
from . import core
from . import cli
from . import gui
from . import main
from . import adapters

# Export LanCalc for tests
try:
    from .gui import LanCalcGUI
    LanCalc = LanCalcGUI
except ImportError:
    LanCalc = None

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "core",
    "cli",
    "gui",
    "main",
    "adapters",
    "LanCalc",
]
