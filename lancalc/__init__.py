#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LanCalc - A desktop application for calculating network configurations
"""

__version__ = '0.1.8'
__author__ = 'Aleksandr Pimenov'
__email__ = 'wachawo@gmail.com'

from .main import main

# Try to import LanCalc only if GUI is available
try:
    from .main import LanCalc  # noqa: F401
    __all__ = ['main', 'LanCalc', '__version__']
except ImportError:
    # GUI not available, only export main function
    __all__ = ['main', '__version__']
