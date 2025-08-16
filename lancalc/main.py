#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LanCalc — GUI + CLI.

Changes:
- CLI via argparse: `lancalc 192.168.88.2/24` prints the result to stdout.
- If no argument is provided and GUI is unavailable (Linux without DISPLAY) — print a notification to stdout and exit with code 2.
- --help from argparse.
- Logging to stderr (logging), computed answer — to stdout.
- GUI starts if no argument is provided and GUI is available.
"""
import argparse
import json
import ipaddress
import logging
import traceback
import os
import platform
import re
import socket
import subprocess
import sys

logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stderr)
    ],
    level=logging.WARNING,
    format='%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Try to import Qt — not required for CLI
try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
    )
    from PyQt5.QtCore import Qt
    from PyQt5.QtCore import QEvent
    from PyQt5.QtGui import QFont, QKeyEvent
    GUI_AVAILABLE = True
except Exception as e:
    logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
    GUI_AVAILABLE = False

# Import version — support running as package/as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from . import __version__
    VERSION = __version__
except Exception:
    try:
        import lancalc
        VERSION = lancalc.__version__
    except Exception:
        VERSION = "0.0.0"


def get_ip() -> str:
    """Return the primary local IPv4 address without external libs."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        # Fallback: hostname resolution (may return 127.0.0.1 in some setups)
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception as e:
            logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
            return "127.0.0.1"
    finally:
        s.close()


def cidr_from_netmask(mask: str) -> int:
    try:
        parts = [int(x) for x in mask.split('.')]
        return sum(bin(p).count('1') for p in parts)
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def get_cidr(ip: str) -> int:
    """Best-effort CIDR detection using system tools; defaults to /24."""
    system = platform.system()
    try:
        if system == "Windows":
            return _get_cidr_windows(ip)
        elif system == "Darwin":
            return _get_cidr_macos(ip)
        else:
            return _get_cidr_linux(ip)
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def _get_cidr_windows(ip: str) -> int:
    """Get CIDR for Windows systems with improved locale support."""
    try:
        # Try PowerShell first for better locale support
        try:
            cmd = [
                "powershell", "-Command",
                f"Get-NetIPAddress -IPAddress '{ip}' | Select-Object -ExpandProperty PrefixLength"
            ]
            out = subprocess.check_output(cmd, encoding="utf-8", errors="ignore", timeout=5)
            prefix = out.strip()
            if prefix.isdigit():
                return int(prefix)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fallback to ipconfig with improved parsing
        out = subprocess.check_output(["ipconfig"], encoding="utf-8", errors="ignore")
        lines = out.splitlines()

        # Find the interface with our IP
        for i, line in enumerate(lines):
            if ip in line and "IPv4" in line:
                # Look for subnet mask in next few lines
                for j in range(i, min(i + 10, len(lines))):
                    line_lower = lines[j].lower()
                    # FIXME: We need to find another way to detect
                    mask_keywords = [
                        "subnet mask", "маска подсети", "subnetmaske", "máscara de sub-rede",
                        "masque de sous-réseau", "subnetmask", "netmask", "маска підмережі"
                    ]
                    if any(keyword in line_lower for keyword in mask_keywords):
                        # Extract mask using multiple patterns
                        mask_patterns = [
                            r'[:=]\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
                            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
                        ]
                        for pattern in mask_patterns:
                            match = re.search(pattern, lines[j])
                            if match:
                                mask = match.group(1)
                                return cidr_from_netmask(mask)
        return 24
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def _get_cidr_macos(ip: str) -> int:
    """Get CIDR for macOS systems."""
    try:
        # Method 1: Use networksetup for better reliability
        try:
            # Get all network services
            services_cmd = ["networksetup", "-listallnetworkservices"]
            services_out = subprocess.check_output(services_cmd, encoding="utf-8", errors="ignore")

            for service in services_out.splitlines()[1:]:  # Skip first line (header)
                service = service.strip()
                if not service:
                    continue

                # Get IP for this service
                try:
                    ip_cmd = ["networksetup", "-getinfo", service]
                    ip_out = subprocess.check_output(ip_cmd, encoding="utf-8", errors="ignore")

                    if ip in ip_out:
                        # Extract subnet mask
                        for line in ip_out.splitlines():
                            if "Subnet mask:" in line:
                                mask = line.split(":")[1].strip()
                                return cidr_from_netmask(mask)
                except subprocess.CalledProcessError:
                    continue
        except subprocess.CalledProcessError:
            pass

        # Method 2: Direct ifconfig parsing
        out = subprocess.check_output(["ifconfig"], encoding="utf-8", errors="ignore")
        for line in out.splitlines():
            m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+0x([0-9a-fA-F]+)", line)
            if m and m.group(1) == ip:
                netmask_hex = m.group(2)
                netmask_int = int(netmask_hex, 16)
                return bin(netmask_int).count('1')
        return 24
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def _get_cidr_linux(ip: str) -> int:
    """Get CIDR for Linux systems."""
    try:
        # Try JSON output first for better parsing
        try:
            out = subprocess.check_output(["ip", "-json", "-4", "addr", "show"], encoding="utf-8", errors="ignore")
            data = json.loads(out)
            for iface in data:
                for addr in iface.get("addr_info", []):
                    if addr.get("local") == ip:
                        return addr.get("prefixlen", 24)
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            pass

        # Fallback to text parsing
        out = subprocess.check_output(["ip", "-o", "-4", "addr", "show"], encoding="utf-8", errors="ignore")
        for line in out.splitlines():
            m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", line)
            if m and m.group(1) == ip:
                return int(m.group(2))
        return 24
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def validate_ip(ip_str: str) -> None:
    """Validate IPv4 address format."""
    if not ip_str or not ip_str.strip():
        raise ValueError("IP address cannot be empty")

    ip_str = ip_str.strip()

    # Check basic format with regex first for better error messages
    ip_pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(ip_pattern, ip_str)
    if not match:
        raise ValueError(f"Invalid IP address format. Expected format: x.x.x.x (e.g., 192.168.1.1), got: {ip_str}")

    # Check each octet range
    octets = [int(match.group(i)) for i in range(1, 5)]
    for i, octet in enumerate(octets, 1):
        if not 0 <= octet <= 255:
            raise ValueError(f"Invalid octet {i}: {octet}. Each octet must be between 0 and 255")

    # Final validation with ipaddress module
    try:
        ipaddress.IPv4Address(ip_str)
    except ipaddress.AddressValueError as e:
        raise ValueError(f"Invalid IP address: {ip_str}") from e


def validate_prefix(prefix_str: str) -> int:
    """Validate CIDR prefix and return as integer."""
    if not prefix_str or not prefix_str.strip():
        raise ValueError("Prefix cannot be empty")

    prefix_str = prefix_str.strip()

    # Check if it's a valid integer
    if not prefix_str.isdigit():
        raise ValueError(f"Prefix must be a number, got: {prefix_str}")

    try:
        p = int(prefix_str)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid prefix: {prefix_str}") from exc

    if not 0 <= p <= 32:
        raise ValueError(f"Prefix must be between 0 and 32, got: {p}")

    return p


def compute(ip: str, prefix: int) -> dict:
    """
    Core network computation function.

    Args:
        ip: IPv4 address as string
        prefix: CIDR prefix as integer (0-32)

    Returns:
        Dictionary with network parameters:
        - Network: network address
        - Prefix: CIDR prefix with slash
        - Netmask: subnet mask
        - Broadcast: broadcast address
        - Hostmin: first usable host
        - Hostmax: last usable host
        - Hosts: number of usable hosts

    Raises:
        ValueError: if IP or prefix is invalid
    """
    # Validate inputs
    validate_ip(ip)
    validate_prefix(str(prefix))

    # Create network object
    net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
    total = net.num_addresses

    # Calculate host range
    if total > 2:
        hostmin = ipaddress.IPv4Address(int(net.network_address) + 1)
        hostmax = ipaddress.IPv4Address(int(net.broadcast_address) - 1)
        hosts_str = str(total - 2)
    else:
        hostmin = net.network_address
        hostmax = net.broadcast_address
        hosts_str = f"{total}*"

    return {
        "Network": str(net.network_address),
        "Prefix": f"/{prefix}",
        "Netmask": str(net.netmask),
        "Broadcast": str(net.broadcast_address),
        "Hostmin": str(hostmin),
        "Hostmax": str(hostmax),
        "Hosts": hosts_str,
    }


def validate_cidr_format(cidr_str: str) -> tuple[str, str]:
    """
    Validate CIDR format and provide detailed error messages.

    Args:
        cidr_str: CIDR notation string

    Returns:
        Tuple of (ip, prefix_str) if valid

    Raises:
        ValueError: with specific error message about what's wrong
    """
    if not cidr_str or not cidr_str.strip():
        raise ValueError("Empty input. Please provide an address in CIDR format (e.g., 192.168.1.1/24)")

    cidr_str = cidr_str.strip()

    # Check if it contains the slash separator
    if '/' not in cidr_str:
        raise ValueError(f"Missing '/' separator. Expected format: IP/PREFIX (e.g., 192.168.1.1/24), got: {cidr_str}")

    # Split into IP and prefix parts
    parts = cidr_str.split('/')
    if len(parts) != 2:
        raise ValueError(f"Invalid format. Expected exactly one '/' separator, got: {cidr_str}")

    ip_part, prefix_part = parts

    # Validate IP part format
    if not ip_part.strip():
        raise ValueError("IP address part is empty. Expected format: IP/PREFIX (e.g., 192.168.1.1/24)")

    if not prefix_part.strip():
        raise ValueError("Prefix part is empty. Expected format: IP/PREFIX (e.g., 192.168.1.1/24)")

    return ip_part.strip(), prefix_part.strip()


def parse_cidr(cidr_str: str) -> tuple[str, int]:
    """
    Parse CIDR notation (e.g., "192.168.1.1/24") into IP and prefix.

    Args:
        cidr_str: CIDR notation string

    Returns:
        Tuple of (ip, prefix)

    Raises:
        ValueError: if CIDR format is invalid
    """
    # First validate the format and get parts
    ip_part, prefix_part = validate_cidr_format(cidr_str)

    # Validate IP address format
    try:
        validate_ip(ip_part)
    except ValueError as e:
        raise ValueError(f"Invalid IP address '{ip_part}': {str(e)}")

    # Validate prefix
    try:
        prefix = validate_prefix(prefix_part)
    except ValueError as e:
        raise ValueError(f"Invalid prefix '{prefix_part}': {str(e)}")

    return ip_part, prefix


def compute_from_cidr(cidr_str: str) -> dict:
    """
    Compute network parameters from CIDR notation.

    Args:
        cidr_str: CIDR notation string (e.g., "192.168.1.1/24")

    Returns:
        Dictionary with network parameters

    Raises:
        ValueError: if CIDR format is invalid
    """
    ip, prefix = parse_cidr(cidr_str)
    return compute(ip, prefix)


def calc_network(ip_cidr: str) -> dict:
    """Calculation of the network from a string like '192.168.88.254/24'. Returns a dict with fields.
    Logs are written to stderr, the result is used for stdout/GUI.
    """
    return compute_from_cidr(ip_cidr)


def print_result_stdout(res: dict) -> None:
    """Print only the result (stdout), without extra logs."""
    for k in ("Network", "Prefix", "Netmask", "Broadcast", "Hostmin", "Hostmax", "Hosts"):
        print(f"{k}: {res[k]}")


def print_result_json(res: dict) -> None:
    """Print result as valid JSON to stdout."""
    print(json.dumps(res))


def is_headless_linux() -> bool:
    """Check if running in headless environment (no GUI available)."""
    if not sys.platform.startswith('linux'):
        return False

    # Check for display environment variables
    display_vars = ['DISPLAY', 'WAYLAND_DISPLAY', 'QT_QPA_PLATFORM']
    for var in display_vars:
        if os.environ.get(var):
            return False

    # Additional check for Qt platform
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        return True

    return True


if GUI_AVAILABLE:
    class ClickToCopyLineEdit(QLineEdit):
        def mousePressEvent(self, event):
            super().mousePressEvent(event)
            self.selectAll()
            QApplication.clipboard().setText(self.text())

    class IpInputLineEdit(QLineEdit):
        def focusInEvent(self, event):
            self.setStyleSheet("color: black;")
            super().focusInEvent(event)

    class LanCalc(QWidget):
        def __init__(self):
            super().__init__()
            logger.info("Initializing LanCalc application")
            self.init_ui()
            self.check_clipboard()
            logger.info("LanCalc application initialized successfully")

        def init_ui(self):
            try:
                main_layout = QVBoxLayout()
                self.setWindowTitle('LanCalc')
                input_width = 200
                font = QFont('Ubuntu', 12)  # 12
                # Fallback font if Ubuntu is not available
                if not font.exactMatch():
                    font = QFont('Arial', 12)
                readonly_style = "QLineEdit { background-color: #f0f0f0; color: #333; text-align: right; }"

                ip_layout = QHBoxLayout()
                ip_label = QLabel("IP Address")
                ip_label.setFont(font)
                self.ip_input = IpInputLineEdit(self)
                self.ip_input.setFont(font)
                self.ip_input.setFixedWidth(input_width)
                self.ip_input.setAlignment(Qt.AlignRight)
                ip_layout.addWidget(ip_label)
                ip_layout.addWidget(self.ip_input)
                # Defer parsing "IP/prefix" until focus is lost or Enter/Tab is pressed
                self.ip_input.installEventFilter(self)
                main_layout.addLayout(ip_layout)

                network_layout = QHBoxLayout()
                network_label = QLabel("Subnet")
                network_label.setFont(font)
                self.network_selector = QComboBox(self)
                self.network_selector.setFont(font)
                for cidr in range(33):
                    mask = str(ipaddress.IPv4Network(f'0.0.0.0/{cidr}', strict=False).netmask)
                    self.network_selector.addItem(f'{cidr}/{mask}')
                self.network_selector.setFixedWidth(input_width)
                network_layout.addWidget(network_label)
                network_layout.addWidget(self.network_selector)
                main_layout.addLayout(network_layout)

                self.set_default_values()

                self.calc_button = QPushButton('Calculate', self)
                self.calc_button.setFont(font)
                self.calc_button.clicked.connect(self.calculate_network)
                main_layout.addWidget(self.calc_button)

                self.network_output = ClickToCopyLineEdit(self)
                self.prefix_output = ClickToCopyLineEdit(self)
                self.netmask_output = ClickToCopyLineEdit(self)
                self.broadcast_output = ClickToCopyLineEdit(self)
                self.hostmin_output = ClickToCopyLineEdit(self)
                self.hostmax_output = ClickToCopyLineEdit(self)
                self.hosts_output = ClickToCopyLineEdit(self)

                for field in [
                    self.network_output,
                    self.prefix_output,
                    self.netmask_output,
                    self.broadcast_output,
                    self.hostmin_output,
                    self.hostmax_output,
                    self.hosts_output,
                ]:
                    field.setReadOnly(True)
                    field.setStyleSheet(readonly_style)
                    field.setAlignment(Qt.AlignRight)
                    field.setFont(font)
                    field.setFixedWidth(input_width)

                self.add_output_field(main_layout, "Network", self.network_output)
                self.add_output_field(main_layout, "Prefix", self.prefix_output)
                self.add_output_field(main_layout, "Netmask", self.netmask_output)
                self.add_output_field(main_layout, "Broadcast", self.broadcast_output)
                self.add_output_field(main_layout, "Hostmin", self.hostmin_output)
                self.add_output_field(main_layout, "Hostmax", self.hostmax_output)
                self.add_output_field(main_layout, "Hosts", self.hosts_output)

                self.link_label = QLabel(f'<a href="https://github.com/lancalc/lancalc">LanCalc {VERSION}</a>')
                self.link_label.setOpenExternalLinks(True)
                self.link_label.setAlignment(Qt.AlignCenter)
                link_font = QFont('Ubuntu', 11)  # 11
                if not link_font.exactMatch():
                    link_font = QFont('Arial', 11)
                self.link_label.setFont(link_font)
                main_layout.addWidget(self.link_label)

                self.setLayout(main_layout)
            except Exception as e:
                logging.error(f"Failed to initialize UI: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")

        def apply_cidr_from_text(self, text: str) -> None:
            """Apply CIDR from the IP input when triggered (focus out or Enter/Tab).
            Splits "IP/prefix" and updates selector when valid. Highlights red on invalid.
            """
            try:
                t = (text or "").strip()
                if not t:
                    self.ip_input.setStyleSheet("color: black;")
                    return
                if "/" in t:
                    m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})(?:\/(\d{1,2}))?$", t)
                    if not m:
                        self.ip_input.setStyleSheet("color: red;")
                        return
                    ip_address, cidr = m.group(1), m.group(2)
                    if not self.validate_ip_address(ip_address):
                        self.ip_input.setStyleSheet("color: red;")
                        return
                    if cidr is not None and self.validate_cidr(cidr) and 0 <= int(cidr) < self.network_selector.count():
                        try:
                            self.ip_input.blockSignals(True)
                            self.ip_input.setText(ip_address)
                        finally:
                            self.ip_input.blockSignals(False)
                        self.network_selector.setCurrentIndex(int(cidr))
                        self.ip_input.setStyleSheet("color: black;")
                        return
                    # CIDR invalid or not present in selector
                    self.ip_input.setStyleSheet("color: red;")
                    return
                # No slash: validate full IP once on trigger
                if self.validate_ip_address(t):
                    self.ip_input.setStyleSheet("color: black;")
                else:
                    self.ip_input.setStyleSheet("color: red;")
            except Exception as e:
                logging.error(f"Error applying CIDR from IP input: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
                self.ip_input.setStyleSheet("color: red;")

        def eventFilter(self, obj, event):
            try:
                if obj is self.ip_input:
                    if event.type() == QEvent.FocusOut:
                        self.apply_cidr_from_text(self.ip_input.text())
                        return False
                    if event.type() == QEvent.KeyPress:
                        key = event.key()
                        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                            self.apply_cidr_from_text(self.ip_input.text())
                            # Do not consume; keep normal behavior (focus move, calculate on return, etc.)
                            return False
                return super().eventFilter(obj, event)
            except Exception as e:
                logger.error(f"Error in event filter: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
                return super().eventFilter(obj, event)

        def validate_ip_address(self, ip_str: str) -> bool:
            try:
                validate_ip(ip_str)
                return True
            except ValueError as e:
                logger.warning(f"Invalid IP address format: {ip_str} - {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
                return False

        def validate_cidr(self, cidr_str: str) -> bool:
            try:
                validate_prefix(cidr_str)
                return True
            except ValueError as e:
                logger.warning(f"Invalid CIDR format: {cidr_str} - {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
                return False

        def check_clipboard(self):
            try:
                # Only check clipboard if we have a fallback/localhost IP (interface detection failed)
                current_ip = self.ip_input.text().strip()
                if current_ip and current_ip not in ["127.0.0.1", "0.0.0.0"]:
                    logger.debug(f"Interface detection successful ({current_ip}), skipping clipboard check")
                    return

                clipboard = QApplication.clipboard()
                clipboard_text = clipboard.text()
                logger.debug(f"Checking clipboard content: {clipboard_text}")
                match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(/(\d{1,2}))?$', clipboard_text)
                if match:
                    ip_address = match.group(1)
                    cidr = match.group(3)
                    if self.validate_ip_address(ip_address):
                        self.ip_input.setText(ip_address)
                        logger.info(f"Auto-filled IP address from clipboard: {ip_address}")
                        if cidr and self.validate_cidr(cidr):
                            self.network_selector.setCurrentIndex(int(cidr))
                            logger.info(f"Auto-filled CIDR from clipboard: {cidr}")
                        else:
                            logger.warning(f"Invalid CIDR in clipboard: {cidr}")
                    else:
                        logger.warning(f"Invalid IP address in clipboard: {ip_address}")
            except Exception as e:
                logger.error(f"Error checking clipboard: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")

        def set_default_values(self):
            try:
                system = platform.system()
                if system == 'Linux':
                    import netifaces
                    gateways = netifaces.gateways()
                    default_interface = gateways['default'][netifaces.AF_INET][1]
                    addrs = netifaces.ifaddresses(default_interface)
                    ip_info = addrs[netifaces.AF_INET][0]
                    default_ip = ip_info['addr']
                    netmask = ip_info['netmask']
                    default_cidr = sum([bin(int(x)).count('1') for x in netmask.split('.')])
                elif system == 'Windows' or system == 'Darwin':  # Windows and macOS
                    default_ip = get_ip()
                    default_cidr = get_cidr(default_ip)
                else:
                    default_ip = "127.0.0.1"
                    default_cidr = 8
                if self.validate_ip_address(default_ip):
                    self.ip_input.setText(default_ip)
                    self.network_selector.setCurrentIndex(default_cidr)
                    logger.info(f"Set default values - IP: {default_ip}, CIDR: {default_cidr}")
                else:
                    logger.warning(f"Invalid default IP address: {default_ip}")
            except Exception as e:
                logger.warning(f"Could not determine default network settings: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")

        def add_output_field(self, layout, label_text, line_edit):
            try:
                field_layout = QHBoxLayout()
                label = QLabel(label_text)
                label_font = QFont('Ubuntu', 13)  # 13
                if not label_font.exactMatch():
                    label_font = QFont('Arial', 13)
                label.setFont(label_font)
                line_edit.setReadOnly(True)
                field_layout.addWidget(label)
                field_layout.addWidget(line_edit)
                layout.addLayout(field_layout)
            except Exception as e:
                logger.error(f"Failed to add output field '{label_text}': {type(e).__name__} {str(e)}\n{traceback.format_exc()}")

        def calculate_network(self, *args, **kwargs):
            try:
                ip_addr = self.ip_input.text().strip()
                prefix_text = self.network_selector.currentText()
                if not ip_addr:
                    raise ValueError("IP address is required")
                if not self.validate_ip_address(ip_addr):
                    raise ValueError(f"Invalid IP address format: {ip_addr}")
                prefix, netmask = prefix_text.split('/')
                if not self.validate_cidr(prefix):
                    raise ValueError(f"Invalid CIDR: {prefix}")

                # Use core calculation module
                result = compute(ip_addr, int(prefix))

                self.network_output.setText(result["Network"])
                self.broadcast_output.setText(result["Broadcast"])
                self.prefix_output.setText(result["Prefix"])
                self.netmask_output.setText(netmask)
                self.hostmin_output.setText(result["Hostmin"])
                self.hostmax_output.setText(result["Hostmax"])
                self.hosts_output.setText(result["Hosts"])
                self.ip_input.setStyleSheet("color: black;")
            except Exception as e:
                logger.error(f"Unexpected error in network calculation: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
                self.ip_input.setStyleSheet("color: red;")

        def keyPressEvent(self, event: QKeyEvent):
            try:
                if event.key() == Qt.Key_Return:
                    self.calculate_network()
                else:
                    super().keyPressEvent(event)
            except Exception as e:
                logger.error(f"Error handling key press event: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")

        def closeEvent(self, event):
            logger.info("LanCalc application closing")
            super().closeEvent(event)


def _run_gui() -> int:
    if not GUI_AVAILABLE:
        logger.critical("GUI is not available on this system (PyQt5 not installed or no display)")
        return 1
    app = QApplication(sys.argv)
    ex = LanCalc()  # type: ignore[name-defined]
    ex.show()
    return app.exec_()


def main(argv=None) -> int:
    """
    Main entry point for LanCalc.

    Exit codes:
    0 - Success
    1 - Validation error or general error
    2 - Headless environment and no address provided
    """
    parser = argparse.ArgumentParser(
        prog="lancalc",
        description=f"LanCalc {VERSION}: GUI + CLI IPv4 calculator. Result to stdout, logs to stderr.",
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="IPv4 in CIDR, for example 192.168.88.2/24",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output result as JSON instead of text",
    )

    args = parser.parse_args(argv)

    have_addr = bool(args.address and args.address.strip())
    headless = is_headless_linux()

    # Conditions for CLI: there is an address OR CLI is forced OR headless environment
    if have_addr or headless:
        if not have_addr:
            # Argument is required: print a hint to stdout, code 2
            print("ADDRESS argument required, e.g. 192.168.88.2/24. Use --help for details.")
            return 2
        try:
            res = calc_network(args.address)
            if args.json:
                print_result_json(res)
            else:
                print_result_stdout(res)
            return 0
        except ValueError as e:
            # Log validation errors to stderr only
            logger.error(f"Validation error: {str(e)}")
            return 1
        except Exception as e:
            logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
            return 1

    # Otherwise — try GUI
    try:
        return _run_gui()
    except Exception as e:
        logger.critical(f"Failed to start GUI: {type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        # Last attempt — inform the user about the argument
        print("GUI is unavailable. Provide ADDRESS argument, e.g. 192.168.88.2/24. Use --help.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
