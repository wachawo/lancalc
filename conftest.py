#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pytest session-wide bootstrap.

Forces Qt to use the offscreen platform so PyQt5 GUI tests work in headless
environments (pre-commit hooks, SSH sessions, CI without xvfb). Must run before
any QApplication is constructed -- conftest.py is imported before test modules.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
