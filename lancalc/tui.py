#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive terminal user interface for LanCalc (prompt_toolkit-based)."""
import logging
import os
import platform
import subprocess
import sys
import traceback
import typing

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
    from . import core
    from . import adapters
except ImportError:
    try:
        from lancalc import __version__ as VERSION
        from lancalc import core
        from lancalc import adapters
    except Exception as e:
        logger.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        VERSION = "0.0.0"
        core = None
        adapters = None

logger.debug(f"LanCalc {VERSION} starting...")


try:
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import Layout, HSplit, Window
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import FormattedText

    TUI_AVAILABLE = True
except ImportError:
    TUI_AVAILABLE = False
    logger.warning("prompt_toolkit not available - TUI mode disabled")


FIELD_KEYS = ("network", "prefix", "netmask", "broadcast", "hostmin", "hostmax", "hosts")
FIELD_LABELS = ("Network", "Prefix", "Netmask", "Broadcast", "Hostmin", "Hostmax", "Hosts")


def clipboard_candidates() -> list:
    """Return ordered list of clipboard-set commands to try on the current OS."""
    system = platform.system()
    if system == "Darwin":
        return [["pbcopy"]]
    if system == "Windows":
        return [["clip"]]
    # Linux / BSD: try Wayland first, then X11 tools.
    return [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]


def copy_to_system_clipboard(text: str) -> typing.Tuple[bool, str]:
    """Try OS-native clipboard tools in order. Return (success, tool_name_or_error)."""
    last_error = ""
    for cmd in clipboard_candidates():
        try:
            subprocess.run(cmd, input=text, text=True, timeout=2, check=True)
            return True, cmd[0]
        except FileNotFoundError:
            continue
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            last_error = f"{cmd[0]}: {type(e).__name__}"
            logger.warning(f"Clipboard tool {cmd[0]} failed: {type(e).__name__} {str(e)}")
            continue
        except Exception as e:
            last_error = f"{cmd[0]}: {type(e).__name__}"
            logger.warning(f"Clipboard tool {cmd[0]} error: {type(e).__name__} {str(e)}")
            continue
    if last_error:
        return False, last_error
    return False, "no clipboard tool found (install xclip / wl-clipboard)"


class LanCalcTUI:
    """Interactive subnet calculator that runs in the terminal.

    Uses the same core.compute_from_cidr / adapters.* helpers as the GUI.
    Recomputes on every keystroke; ↑/↓ nudge the prefix.
    """

    def __init__(self, initial_text: str = ""):
        self.result = {k: "" for k in FIELD_KEYS}
        self.status_text = f"LanCalc {VERSION}"
        self.status_class = "class:status"

        self.input_buffer = Buffer(
            on_text_changed=lambda _: self._compute(),
            multiline=False,
        )
        self.input_buffer.text = initial_text or default_input_text()

        self.kb = self._build_keybindings()
        self.layout = self._build_layout()
        self.style = self._build_style()

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            style=self.style,
            mouse_support=False,
        )

        self._compute()

    def _compute(self) -> None:
        """Recalculate result from current input buffer text."""
        text = self.input_buffer.text.strip()
        if not text:
            self.result = {k: "" for k in FIELD_KEYS}
            self.status_text = "Enter IP[/prefix] (e.g. 192.168.1.1/24)"
            self.status_class = "class:hint"
            return

        cidr_str = text if "/" in text else f"{text}/24"
        try:
            res = core.compute_from_cidr(cidr_str)
            self.result = {k: res[k] for k in FIELD_KEYS}
            comment = res.get("comment") or ""
            if comment:
                self.status_text = comment
                self.status_class = "class:special"
            else:
                self.status_text = f"LanCalc {VERSION}"
                self.status_class = "class:status"
        except ValueError as e:
            self.result = {k: "" for k in FIELD_KEYS}
            self.status_text = f"Error: {e}"
            self.status_class = "class:error"
        except Exception as e:
            logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
            self.result = {k: "" for k in FIELD_KEYS}
            self.status_text = f"Unexpected: {type(e).__name__}: {e}"
            self.status_class = "class:error"

    def _shift_prefix(self, delta: int) -> None:
        """Increase or decrease the prefix in the input buffer (clamped to 0..32)."""
        text = self.input_buffer.text.strip()
        if "/" not in text:
            ip = text or "192.168.1.1"
            try:
                core.validate_ip(ip)
            except ValueError:
                return
            self.input_buffer.text = f"{ip}/24"
            return
        ip, _, prefix_str = text.partition("/")
        try:
            prefix = int(prefix_str)
        except ValueError:
            return
        new_prefix = max(0, min(32, prefix + delta))
        if new_prefix == prefix:
            return
        self.input_buffer.text = f"{ip}/{new_prefix}"

    def _refresh_from_adapters(self) -> None:
        """Re-detect local IP and CIDR, replace input buffer contents."""
        self.input_buffer.text = default_input_text()

    def _copy_result(self) -> None:
        """Copy formatted result to the system clipboard via a native tool."""
        lines = []
        for label, key in zip(FIELD_LABELS, FIELD_KEYS):
            value = self.result.get(key, "")
            if value:
                lines.append(f"{label}: {value}")
        if not lines:
            return
        text = "\n".join(lines)

        ok, info = copy_to_system_clipboard(text)

        # Also keep prompt_toolkit's internal buffer in sync (for in-app paste).
        try:
            from prompt_toolkit.clipboard import ClipboardData

            self.app.clipboard.set_data(ClipboardData(text))
        except Exception:
            pass

        if ok:
            self.status_text = f"Copied to clipboard ({info})"
            self.status_class = "class:hint"
        else:
            self.status_text = f"Copy failed: {info}"
            self.status_class = "class:error"

    def _build_keybindings(self) -> "KeyBindings":
        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-q")
        @kb.add("escape")
        def _quit(event):
            event.app.exit()

        @kb.add("up")
        def _up(event):
            self._shift_prefix(+1)

        @kb.add("down")
        def _down(event):
            self._shift_prefix(-1)

        @kb.add("c-r")
        def _refresh(event):
            self._refresh_from_adapters()

        @kb.add("c-y")
        def _copy(event):
            self._copy_result()

        return kb

    def _result_fragments(self):
        """Render the result panel as prompt_toolkit formatted text."""
        fragments = []
        fragments.append(("class:label-bar", " IP / CIDR "))
        fragments.append(("", "\n"))
        fragments.append(("", "\n"))
        for label, key in zip(FIELD_LABELS, FIELD_KEYS):
            value = self.result.get(key, "") or "—"
            fragments.append(("class:label", f"  {label:<10} "))
            fragments.append(("class:value", f"{value}\n"))
        fragments.append(("", "\n"))
        fragments.append((self.status_class, self.status_text))
        return FormattedText(fragments)

    def _hints_fragments(self):
        return FormattedText([
            ("class:hints-bar", "  ↑↓ prefix  ·  Ctrl-R refresh  ·  Ctrl-Y copy  ·  Esc/Ctrl-Q quit  "),
        ])

    def _build_layout(self) -> "Layout":
        input_window = Window(
            BufferControl(buffer=self.input_buffer),
            height=1,
            style="class:input",
        )
        result_window = Window(
            FormattedTextControl(self._result_fragments),
            wrap_lines=False,
        )
        hints_window = Window(
            FormattedTextControl(self._hints_fragments),
            height=1,
            style="class:hints-bar",
        )
        body = HSplit([
            Window(FormattedTextControl(lambda: " Enter IP[/prefix] then ↑↓ to change prefix:"), height=1),
            input_window,
            Window(height=1, char=" "),
            result_window,
            hints_window,
        ])
        return Layout(body, focused_element=input_window)

    def _build_style(self) -> "Style":
        return Style.from_dict({
            "title": "bold reverse",
            "label": "bold",
            "value": "",
            "label-bar": "reverse",
            "input": "bg:#202020 fg:#ffffff",
            "hint": "italic #808080",
            "hints-bar": "reverse",
            "status": "fg:#88cc88",
            "special": "fg:#ffcc00 bold",
            "error": "fg:#ff5555 bold",
        })

    def run(self) -> int:
        try:
            self.app.run()
            return 0
        except Exception as e:
            logger.error(f"TUI failed: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
            return 1


def default_input_text() -> str:
    """Detect local IP + CIDR and format as 'ip/prefix', with safe fallbacks."""
    try:
        ip = adapters.get_internal_ip()
        try:
            core.validate_ip(ip)
        except ValueError:
            ip = "192.168.1.1"
        try:
            cidr = adapters.get_cidr(ip)
        except Exception as e:
            logger.warning(f"CIDR detect failed: {type(e).__name__} {str(e)}")
            cidr = 24
        return f"{ip}/{cidr}"
    except Exception as e:
        logger.warning(f"Default input fallback: {type(e).__name__} {str(e)}")
        return "192.168.1.1/24"


def main(initial_text: str = "") -> int:
    """Run TUI mode.

    Returns:
        Exit code (0 success, 1 error/unavailable).
    """
    if not TUI_AVAILABLE:
        print("TUI not available - prompt_toolkit not installed", file=sys.stderr)
        print("Install with: pip install 'lancalc[tui]'  or  pip install prompt_toolkit", file=sys.stderr)
        return 1
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("TUI requires an interactive terminal (TTY)", file=sys.stderr)
        return 1
    try:
        tui_app = LanCalcTUI(initial_text=initial_text)
        return tui_app.run()
    except Exception as e:
        logger.error(f"TUI failed: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
