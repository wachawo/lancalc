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
    from . import tui
except ImportError:
    try:
        from lancalc import __version__ as VERSION
        from lancalc import cli
        from lancalc import gui
        from lancalc import tui
    except Exception as e:
        logger.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        VERSION = "0.0.0"
        cli = None
        gui = None
        tui = None

logger.debug(f"LanCalc {VERSION} starting...")

GUI_FLAGS = ("--gui", "-g")
TUI_FLAGS = ("--tui", "-t")
NOGUI_FLAGS = ("--nogui",)


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


def is_interactive_terminal() -> bool:
    """Whether stdin and stdout are both attached to a TTY (TUI requires this)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def detect_interactive_mode() -> str:
    """
    Pick which interactive UI to launch when no positional args are given.

    Order: GUI (if available + has display) → TUI (if available + TTY) → 'cli'.
    """
    gui_available = getattr(gui, 'GUI_AVAILABLE', False)
    tui_available = getattr(tui, 'TUI_AVAILABLE', False)
    if gui_available and not is_headless_environment():
        return 'gui'
    if tui_available and is_interactive_terminal():
        return 'tui'
    return 'cli'


def extract_mode_flag(args: list) -> typing.Tuple[list, typing.Optional[str]]:
    """Pull --gui/--tui/--nogui out of args and return (remaining_args, mode_or_None).

    Mutually exclusive: returns mode='error' if more than one is present.
    Modes: 'gui', 'tui', 'cli' (from --nogui), or None.
    """
    remaining = []
    mode = None
    for a in args:
        if a in GUI_FLAGS:
            target = 'gui'
        elif a in TUI_FLAGS:
            target = 'tui'
        elif a in NOGUI_FLAGS:
            target = 'cli'
        else:
            remaining.append(a)
            continue
        if mode is not None and mode != target:
            return args, 'error'
        mode = target
    return remaining, mode


def has_positional_address(args: list) -> bool:
    """True if args contain at least one non-flag token (CIDR-style positional)."""
    for a in args:
        if not a.startswith('-'):
            return True
    return False


def run_gui_or_fallback() -> int:
    """Run GUI; on failure fall back to TUI (if available), then CLI help."""
    gui_available = getattr(gui, 'GUI_AVAILABLE', False)
    tui_available = getattr(tui, 'TUI_AVAILABLE', False)
    if not gui_available:
        logger.warning("GUI requested but PyQt5 not available")
        if tui_available and is_interactive_terminal():
            return tui.main()
        return cli.main([])
    try:
        return gui.main()
    except Exception as e:
        logger.error(f"GUI failed: {type(e).__name__} {str(e)}")
        if tui_available and is_interactive_terminal():
            return tui.main()
        return cli.main([])


def main(argv: typing.Optional[list] = None) -> int:
    """
    Main entry point for LanCalc.

    Routing:
      - mode flag --gui/-g          → force GUI
      - mode flag --tui/-t          → force TUI
      - mode flag --nogui           → force CLI (for use in scripts)
      - positional address          → CLI one-shot (mode flags ignored)
      - no args                     → auto-detect: GUI > TUI > CLI help

    Args:
        argv: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code (0 success, 1 error, 2 misuse)
    """
    if argv is None:
        argv = sys.argv

    args = list(argv[1:])
    args, forced = extract_mode_flag(args)

    if forced == 'error':
        print("Error: --gui, --tui and --nogui are mutually exclusive", file=sys.stderr)
        return 2

    # --nogui → never launch any interactive UI; always delegate to CLI.
    if forced == 'cli':
        return cli.main(args) if args else cli.main([])

    # Positional CIDR present → CLI one-shot regardless of mode flag.
    if has_positional_address(args):
        return cli.main(args)

    # No positional: interactive launch.
    if forced == 'gui':
        if not getattr(gui, 'GUI_AVAILABLE', False):
            print("Error: --gui requested but PyQt5 is not installed", file=sys.stderr)
            return 1
        return run_gui_or_fallback()

    if forced == 'tui':
        if not getattr(tui, 'TUI_AVAILABLE', False):
            print("Error: --tui requested but prompt_toolkit is not installed", file=sys.stderr)
            return 1
        return tui.main()

    # If extra CLI flags (like --json) were passed without an address, defer to CLI for proper help/handling.
    if args:
        return cli.main(args)

    # Auto-detect.
    mode = detect_interactive_mode()
    if mode == 'gui':
        return run_gui_or_fallback()
    if mode == 'tui':
        return tui.main()
    return cli.main([])


if __name__ == "__main__":
    sys.exit(main())
