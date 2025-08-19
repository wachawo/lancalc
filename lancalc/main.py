#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for LanCalc - adaptive launcher.
"""
import logging
import os
import sys
import traceback
import typing

# Configure logging
logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stderr)],
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from . import __version__ as VERSION
    from . import cli
    from . import gui
except ImportError:
    try:
        from lancalc import __version__ as VERSION
        import cli
        import gui
    except Exception as e:
        logger.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        VERSION = "0.0.0"

logger.debug(f"LanCalc {VERSION} starting...")


def is_headless_environment() -> bool:
    """
    Check if running in headless environment (no GUI available).

    Returns:
        True if headless, False if GUI is available
    """
    # Check for CI environment
    if any(os.environ.get(var) == 'true' for var in ['CI', 'GITHUB_ACTIONS', 'TRAVIS']):
        return True

    # Check for display environment variables
    display_vars = ['DISPLAY', 'WAYLAND_DISPLAY', 'QT_QPA_PLATFORM']
    for var in display_vars:
        if os.environ.get(var):
            return False

    # Additional check for Qt platform
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        return True

    # Platform-specific checks
    if sys.platform.startswith('linux'):
        # Linux: check for SSH connection or no display
        if os.environ.get('SSH_CONNECTION'):
            return True
        return True  # Default to headless on Linux without display

    elif sys.platform.startswith('darwin'):
        # macOS: usually has GUI available
        return False

    elif sys.platform.startswith('win'):
        # Windows: usually has GUI available
        return False

    # Default to headless for unknown platforms
    return True


def detect_interface_mode() -> str:
    """
    Detect whether to use GUI or CLI mode based on environment.

    Returns:
        'gui' or 'cli'
    """
    # If arguments are provided, use CLI mode
    if len(sys.argv) > 1:
        return 'cli'

    # Check if GUI is available
    if not hasattr(gui, 'GUI_AVAILABLE') or not gui.GUI_AVAILABLE:
        return 'cli'

    # Check if we're in a headless environment
    if is_headless_environment():
        return 'cli'

    # Default to GUI if available
    return 'gui'


def main(argv: typing.Optional[list] = None) -> int:
    """
    Main entry point for LanCalc.

    Automatically detects whether to run in GUI or CLI mode based on:
    - Command line arguments
    - Environment variables (CI, DISPLAY, etc.)
    - System capabilities
    - GUI availability

    Args:
        argv: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code (0 for success, 1 for error, 2 for headless without args)
    """
    if argv is None:
        argv = sys.argv

    # If arguments are provided, use CLI mode
    if len(argv) > 1:
        return cli.main(argv[1:])  # Skip the script name

    # Auto-detect interface mode
    mode = detect_interface_mode()

    if mode == 'gui':
        try:
            return gui.main()
        except Exception as e:
            logger.error(f"GUI failed: {type(e).__name__} {str(e)}")
            # Fallback to CLI help
            return cli.main(['--help'])
    else:
        # For CLI mode without arguments, show help
        return cli.main(['--help'])


if __name__ == "__main__":
    sys.exit(main())
