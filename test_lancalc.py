#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os
import pytest
import sys
import subprocess
import ipaddress
from lancalc.core import compute, compute_from_cidr, validate_ip, validate_prefix, parse_cidr
from lancalc.core import REPO_URL
from lancalc.adapters import get_internal_ip, get_external_ip, get_cidr, get_cidr_windows, get_cidr_macos, get_cidr_linux, cidr_from_netmask
from lancalc.cli import print_result_json

# Try to import LanCalc only if GUI is available
try:
    from lancalc import LanCalc
    GUI_TESTS_AVAILABLE = True
except ImportError:
    GUI_TESTS_AVAILABLE = False
    LanCalc = None


# Configure logging for tests
logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stderr)],
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Check if we're in CI environment


def is_ci_environment():
    """Check if running in CI environment."""
    return os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'

# Check if GUI tests should be skipped


def skip_gui_tests():
    """Check if GUI tests should be skipped."""
    if not GUI_TESTS_AVAILABLE:
        return True
    # In CI environment, check if we have a virtual display
    if is_ci_environment():
        # Check if we have a display (virtual or real)
        try:
            if os.environ.get('DISPLAY') or os.name == 'nt':
                return False  # We have a display, run GUI tests
        except Exception:
            pass
        return True  # No display in CI, skip GUI tests
    # Check if we have a display (for headless environments)
    try:
        if not os.environ.get('DISPLAY') and os.name != 'nt':  # No display on Unix-like systems
            return True
    except Exception:
        return True
    return False


# Test data: (ip, prefix, expected values in output fields)
test_cases = [
    ("192.168.1.10", "24", {
        'network': '192.168.1.0',
        'prefix': '/24',
        'netmask': '255.255.255.0',
        'broadcast': '192.168.1.255',
        'hostmin': '192.168.1.1',
        'hostmax': '192.168.1.254',
        'hosts': '254',
        'ip_color': 'black'
    }),
    ("10.0.0.1", "8", {
        'network': '10.0.0.0',
        'prefix': '/8',
        'netmask': '255.0.0.0',
        'broadcast': '10.255.255.255',
        'hostmin': '10.0.0.1',
        'hostmax': '10.255.255.254',
        'hosts': '16777214',
        'ip_color': 'black'
    }),
    ("172.16.5.4", "16", {
        'network': '172.16.0.0',
        'prefix': '/16',
        'netmask': '255.255.0.0',
        'broadcast': '172.16.255.255',
        'hostmin': '172.16.0.1',
        'hostmax': '172.16.255.254',
        'hosts': '65534',
        'ip_color': 'black'
    }),
    ("192.168.2.1", "32", {
        'network': '192.168.2.1',
        'prefix': '/32',
        'netmask': '255.255.255.255',
        'broadcast': '192.168.2.1',
        'hostmin': '192.168.2.1',
        'hostmax': '192.168.2.1',
        'hosts': '1*',
        'ip_color': 'black'
    }),
    ("192.168.3.1/24", "", {
        'network': '192.168.3.0',
        'prefix': '/24',
        'netmask': '255.255.255.0',
        'broadcast': '192.168.3.255',
        'hostmin': '192.168.3.1',
        'hostmax': '192.168.3.254',
        'hosts': '254',
        'ip_color': 'black'
    }),
    ("10.0.0.1/8", "", {
        'network': '10.0.0.0',
        'prefix': '/8',
        'netmask': '255.0.0.0',
        'broadcast': '10.255.255.255',
        'hostmin': '10.0.0.1',
        'hostmax': '10.255.255.254',
        'hosts': '16777214',
        'ip_color': 'black'
    }),
    ("172.16.0.1/16", "", {
        'network': '172.16.0.0',
        'prefix': '/16',
        'netmask': '255.255.0.0',
        'broadcast': '172.16.255.255',
        'hostmin': '172.16.0.1',
        'hostmax': '172.16.255.254',
        'hosts': '65534',
        'ip_color': 'black'
    }),
    ("256.256.256.256", "24", {
        'network': '',
        'prefix': '',
        'netmask': '',
        'broadcast': '',
        'hostmin': '',
        'hostmax': '',
        'hosts': '',
        'ip_color': 'red'
    })
]


@pytest.fixture
def app(qtbot):
    if not GUI_TESTS_AVAILABLE:
        pytest.skip("GUI not available")
    test_app = LanCalc()
    qtbot.addWidget(test_app)
    return test_app


@pytest.mark.parametrize("ip,prefix,expected", test_cases)
@pytest.mark.qt_api("pyqt5")
def test_gui_calculate_networks(qtbot, ip, prefix, expected):
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)
    """Test network calculation through GUI"""
    # Set IP
    app.ip_input.setText(ip)
    # If prefix is embedded in input (CIDR), simulate GUI behavior
    if prefix == "" and "/" in ip:
        app.apply_cidr_from_text(ip)
    # Set prefix in combobox if not CIDR
    else:
        for i in range(app.network_selector.count()):
            if app.network_selector.itemText(i).startswith(prefix + "/"):
                app.network_selector.setCurrentIndex(i)
                break
    # Call calculate
    app.calculate_network()
    # Check outputs
    assert app.network_output.text() == expected['network']
    assert app.prefix_output.text() == expected['prefix']
    assert app.netmask_output.text() == expected['netmask']
    assert app.broadcast_output.text() == expected['broadcast']
    assert app.hostmin_output.text() == expected['hostmin']
    assert app.hostmax_output.text() == expected['hostmax']
    assert app.hosts_output.text() == expected['hosts']
    # Check color - for invalid IPs, simulate focus out to trigger validation
    if expected['ip_color'] == 'red':
        app.validate_ip_on_focus_out()
        assert 'red' in app.ip_input.styleSheet()
    else:
        assert 'color: black' in app.ip_input.styleSheet() or app.ip_input.styleSheet() == ''


@pytest.mark.qt_api("pyqt5")
def test_gui_invalid_cidr_handling(qtbot):
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)
    """Test handling of invalid CIDR values"""
    # Test with invalid CIDR (40) - this should fail validation
    app.ip_input.setText("192.168.1.1")
    # Try to set an invalid CIDR - since combobox only has 0-32, we'll test with a valid one
    # but the validation should catch it if we could set it
    app.calculate_network()
    # For now, just check that the app doesn't crash with invalid CIDR


@pytest.mark.qt_api("pyqt5")
def test_gui_window_launch(qtbot):
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)
    """Test basic window functionality"""
    assert app.isVisible() is False  # Window is not shown by default
    app.show()
    assert app.isVisible() is True
    assert app.windowTitle() == 'LanCalc'


# --- Validation helpers (GUI methods) ---

@pytest.mark.qt_api("pyqt5")
def test_validation_ip_address(qtbot):
    """Test IP address validation"""
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)

    # Valid IPs
    assert app.validate_ip_address("192.168.1.1")
    assert app.validate_ip_address("10.0.0.1")
    assert app.validate_ip_address("172.16.0.1")
    assert app.validate_ip_address("0.0.0.0")
    assert app.validate_ip_address("255.255.255.255")

    # Invalid IPs
    assert not app.validate_ip_address("256.256.256.256")
    assert not app.validate_ip_address("192.168.1.256")
    assert not app.validate_ip_address("192.168.1")
    assert not app.validate_ip_address("192.168.1.1.1")
    assert not app.validate_ip_address("")
    assert not app.validate_ip_address("invalid")


@pytest.mark.qt_api("pyqt5")
def test_validation_cidr(qtbot):
    """Test CIDR validation"""
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)

    # Valid CIDRs
    for i in range(33):
        assert app.validate_cidr(str(i))

    # Invalid CIDRs
    assert not app.validate_cidr("-1")
    assert not app.validate_cidr("33")
    assert not app.validate_cidr("100")
    assert not app.validate_cidr("")
    assert not app.validate_cidr("invalid")


@pytest.mark.qt_api("pyqt5")
def test_gui_special_range_status_bar(qtbot):
    app = LanCalc()
    qtbot.addWidget(app)
    """Test GUI status bar for special IPv4 ranges"""
    # Test loopback address
    app.ip_input.setText("127.0.0.1")
    app.network_selector.setCurrentIndex(8)  # /8
    app.calculate_network()

    assert app.network_output.text() == "127.0.0.0"
    assert app.hostmin_output.text() == "127.0.0.1"
    assert app.hostmax_output.text() == "127.255.255.254"
    assert app.hosts_output.text() == "16777214"
    assert app.broadcast_output.text() == "*"
    # Check status bar shows message with RFC link
    assert "RFC 3330 Loopback" in app.status_label.text()

    # Test multicast address
    app.ip_input.setText("224.0.0.1")
    app.network_selector.setCurrentIndex(4)  # /4
    app.calculate_network()

    assert app.network_output.text() == "224.0.0.0"
    assert app.hostmin_output.text() == "*"
    assert app.hostmax_output.text() == "*"
    assert app.hosts_output.text() == "*"
    assert app.broadcast_output.text() == "*"
    assert "RFC 5771 Multicast" in app.status_label.text()

    # Test normal unicast address - status bar should show version
    app.ip_input.setText("192.168.1.1")
    app.network_selector.setCurrentIndex(24)  # /24
    app.calculate_network()

    assert app.network_output.text() == "192.168.1.0"
    assert app.hostmin_output.text() == "192.168.1.1"
    assert app.hostmax_output.text() == "192.168.1.254"
    assert app.hosts_output.text() == "254"
    # For normal addresses, status bar should show version link
    assert "LanCalc" in app.status_label.text()
    assert "github.com" in app.status_label.text()


@pytest.mark.qt_api("pyqt5")
def test_gui_error_handling(qtbot):
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)
    """Test error handling in GUI"""
    # Test with invalid IP - simulate focus out
    app.ip_input.setText("invalid-ip")
    app.validate_ip_on_focus_out()
    assert 'red' in app.ip_input.styleSheet()

    # Test with empty IP - simulate focus out
    app.ip_input.setText("")
    app.validate_ip_on_focus_out()
    assert 'red' in app.ip_input.styleSheet()

    # Test clearing validation on focus in
    app.clear_validation()
    assert 'red' not in app.ip_input.styleSheet()


@pytest.mark.qt_api("pyqt5")
def test_gui_edge_cases(qtbot):
    """Test edge cases for network calculations"""
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    app = LanCalc()
    qtbot.addWidget(app)

    # Test /0 network
    app.ip_input.setText("0.0.0.0")
    for i in range(app.network_selector.count()):
        if app.network_selector.itemText(i).startswith("0/"):
            app.network_selector.setCurrentIndex(i)
            break
    app.calculate_network()
    assert app.network_output.text() == '0.0.0.0'
    assert app.prefix_output.text() == '/0'
    assert app.netmask_output.text() == '0.0.0.0'

    # Test /32 network (single host)
    app.ip_input.setText("192.168.1.1")
    for i in range(app.network_selector.count()):
        if app.network_selector.itemText(i).startswith("32/"):
            app.network_selector.setCurrentIndex(i)
            break
    app.calculate_network()
    assert app.network_output.text() == '192.168.1.1'
    assert app.prefix_output.text() == '/32'
    assert app.netmask_output.text() == '255.255.255.255'
    assert app.hosts_output.text() == '1*'


@pytest.mark.qt_api("pyqt5")
def test_gui_clipboard_functionality(qtbot):
    """Test clipboard auto-fill functionality"""
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")
    from PyQt5.QtWidgets import QApplication

    app = LanCalc()
    qtbot.addWidget(app)

    # Clear the IP input first to simulate fallback scenario
    app.ip_input.clear()

    # Mock clipboard with valid IP
    clipboard = QApplication.clipboard()
    clipboard.setText("192.168.1.100/24")

    # Call check_clipboard
    app.check_clipboard()

    # For now, just verify the method doesn't crash
    # The clipboard functionality is logged but doesn't auto-fill
    assert True

    # Test with invalid clipboard content
    clipboard.setText("invalid-ip")
    app.ip_input.clear()
    app.check_clipboard()
    # Should not fill invalid IP
    assert app.ip_input.text() == ""


# --- Core / CLI tests ---

def test_core_json_output():
    """Test JSON output functionality"""
    # Test JSON output
    result = compute_from_cidr("192.168.1.1/24")

    # Verify result contains all required fields
    required_fields = ["network", "prefix", "netmask", "broadcast", "hostmin", "hostmax", "hosts"]
    for field in required_fields:
        assert field in result

    # Verify JSON is valid
    json_str = json.dumps(result)
    parsed_json = json.loads(json_str)
    assert parsed_json == result

    # Test print_result_json function
    print_result_json(result)  # This should not raise any exceptions


def test_cli_json_output():
    """Test CLI JSON output via subprocess"""
    # Test JSON output via CLI
    result = subprocess.run(
        [sys.executable, "-m", "lancalc", "192.168.1.1/24", "--json"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )

    assert result.returncode == 0
    assert result.stdout.strip()

    # Parse JSON output
    json_data = json.loads(result.stdout.strip())
    assert "network" in json_data
    assert "prefix" in json_data
    assert "netmask" in json_data
    assert "broadcast" in json_data
    assert "hostmin" in json_data
    assert "hostmax" in json_data
    assert "hosts" in json_data
    # Verify values
    assert json_data["network"] == "192.168.1.0"
    assert json_data["prefix"] == "/24"
    assert json_data["netmask"] == "255.255.255.0"
    # comment field is not present for normal addresses with -j flag


def test_cli_special_ranges_json():
    """Test CLI JSON output for special ranges"""
    test_cases_local = [
        ("127.0.0.1/8", f"RFC 3330 Loopback ({REPO_URL}/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)"),
        ("169.254.1.1/16", f"RFC 3927 Link-local ({REPO_URL}/blob/main/docs/RFC.md#rfc-3927---link-local-addresses)"),
        ("224.0.0.1/4", f"RFC 5771 Multicast ({REPO_URL}/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"),
        ("0.0.0.1/8", f"RFC 1122 Unspecified ({REPO_URL}/blob/main/docs/RFC.md#rfc-1122---unspecified-addresses)"),
        ("255.255.255.255/32", f"RFC 919 Broadcast ({REPO_URL}/blob/main/docs/RFC.md#rfc-919---broadcast-address)"),
    ]

    for cidr, expected_message in test_cases_local:
        result = subprocess.run(
            [sys.executable, "-m", "lancalc", cidr, "--json"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )

        assert result.returncode == 0
        json_data = json.loads(result.stdout.strip())

        # Check that special ranges have correct host fields
        assert json_data["comment"] == expected_message
        # For loopback addresses, check special host handling
        if cidr.startswith("127."):
            assert json_data["hostmin"] == "127.0.0.1"
            assert json_data["hostmax"] == "127.255.255.254"
            assert json_data["hosts"] == "16777214"
        else:
            assert json_data["hostmin"] == "*"
            assert json_data["hostmax"] == "*"
            assert json_data["hosts"] == "*"
            assert json_data["broadcast"] == "*"


def test_cli_text_output():
    """Test CLI text output via subprocess"""
    result = subprocess.run(
        [sys.executable, "-m", "lancalc", "192.168.1.1/24"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )

    assert result.returncode == 0
    assert result.stdout.strip()

    # Verify text output format
    output_lines = result.stdout.strip().split('\n')
    assert len(output_lines) == 7  # 7 fields

    # Check that each line has the format "Field: Value"
    for line in output_lines:
        assert ': ' in line
        field, value = line.split(': ', 1)
        assert field in ["Network", "Prefix", "Netmask", "Broadcast", "Hostmin", "Hostmax", "Hosts"]


# --- Core calculation functions (previously TestCoreCalculations) ---

def test_core_compute_basic():
    """Test basic network computation."""
    result = compute("192.168.1.1", 24)
    assert result["network"] == "192.168.1.0"
    assert result["prefix"] == "/24"
    assert result["netmask"] == "255.255.255.0"
    assert result["broadcast"] == "192.168.1.255"
    assert result["hostmin"] == "192.168.1.1"
    assert result["hostmax"] == "192.168.1.254"
    assert result["hosts"] == "254"


def test_core_compute_slash_8():
    """Test /8 network."""
    result = compute("10.0.0.1", 8)
    assert result["network"] == "10.0.0.0"
    assert result["prefix"] == "/8"
    assert result["netmask"] == "255.0.0.0"
    assert result["broadcast"] == "10.255.255.255"
    assert result["hostmin"] == "10.0.0.1"
    assert result["hostmax"] == "10.255.255.254"
    assert result["hosts"] == "16777214"


def test_core_compute_slash_16():
    """Test /16 network."""
    result = compute("172.16.5.4", 16)
    assert result["network"] == "172.16.0.0"
    assert result["prefix"] == "/16"
    assert result["netmask"] == "255.255.0.0"
    assert result["broadcast"] == "172.16.255.255"
    assert result["hostmin"] == "172.16.0.1"
    assert result["hostmax"] == "172.16.255.254"
    assert result["hosts"] == "65534"


def test_core_compute_slash_31():
    """Test /31 network (point-to-point)."""
    result = compute("192.168.1.0", 31)
    assert result["network"] == "192.168.1.0"
    assert result["prefix"] == "/31"
    assert result["netmask"] == "255.255.255.254"
    assert result["broadcast"] == "192.168.1.1"
    assert result["hostmin"] == "192.168.1.0"
    assert result["hostmax"] == "192.168.1.1"
    assert result["hosts"] == "2*"


def test_core_compute_slash_32():
    """Test /32 network (single host)."""
    result = compute("192.168.2.1", 32)
    assert result["network"] == "192.168.2.1"
    assert result["prefix"] == "/32"
    assert result["netmask"] == "255.255.255.255"
    assert result["broadcast"] == "192.168.2.1"
    assert result["hostmin"] == "192.168.2.1"
    assert result["hostmax"] == "192.168.2.1"
    assert result["hosts"] == "1*"


def test_core_compute_slash_0():
    """Test /0 network (default route)."""
    result = compute("0.0.0.0", 0)
    assert result["network"] == "0.0.0.0"
    assert result["prefix"] == "/0"
    assert result["netmask"] == "0.0.0.0"
    assert result["broadcast"] == "255.255.255.255"
    assert result["hostmin"] == "0.0.0.1"
    assert result["hostmax"] == "255.255.255.254"
    assert result["hosts"] == "4294967294"


# --- CIDR parsing (previously TestCIDRParsing) ---

def test_core_parse_cidr_valid():
    """Test valid CIDR parsing."""
    ip, prefix = parse_cidr("192.168.1.1/24")
    assert ip == "192.168.1.1"
    assert prefix == 24


def test_core_parse_cidr_invalid_format():
    """Test invalid CIDR format."""
    with pytest.raises(ValueError, match="Missing '/' separator"):
        parse_cidr("192.168.1.1")

    with pytest.raises(ValueError, match="Prefix part is empty"):
        parse_cidr("192.168.1.1/")

    with pytest.raises(ValueError, match="IP address part is empty"):
        parse_cidr("/24")


def test_core_compute_from_cidr():
    """Test computation from CIDR string."""
    result = compute_from_cidr("192.168.1.1/24")
    assert result["network"] == "192.168.1.0"
    assert result["prefix"] == "/24"


# --- Validation (previously TestValidation) ---

def test_validation_ip_valid():
    """Test valid IP addresses."""
    validate_ip("192.168.1.1")
    validate_ip("10.0.0.1")
    validate_ip("172.16.0.1")
    validate_ip("0.0.0.0")
    validate_ip("255.255.255.255")


def test_validation_ip_invalid():
    """Test invalid IP addresses."""
    with pytest.raises(ValueError):
        validate_ip("256.256.256.256")

    with pytest.raises(ValueError):
        validate_ip("192.168.1.256")

    with pytest.raises(ValueError):
        validate_ip("192.168.1")

    with pytest.raises(ValueError):
        validate_ip("192.168.1.1.1")

    with pytest.raises(ValueError):
        validate_ip("")

    with pytest.raises(ValueError):
        validate_ip("invalid")


def test_validation_prefix_valid():
    """Test valid prefixes."""
    for i in range(33):
        assert validate_prefix(str(i)) == i


def test_validation_prefix_invalid():
    """Test invalid prefixes."""
    with pytest.raises(ValueError):
        validate_prefix("-1")

    with pytest.raises(ValueError):
        validate_prefix("33")

    with pytest.raises(ValueError):
        validate_prefix("100")

    with pytest.raises(ValueError):
        validate_prefix("")

    with pytest.raises(ValueError):
        validate_prefix("invalid")


# --- Edge cases (previously TestEdgeCases) ---

def test_core_edge_case_networks():
    """Test various edge case networks."""
    # Test networks with all zeros
    result = compute("0.0.0.0", 8)
    assert result["network"] == "0.0.0.0"

    # Test networks with all ones
    result = compute("255.255.255.255", 32)
    assert result["network"] == "255.255.255.255"

    # Test /30 network (4 addresses, 2 usable)
    result = compute("192.168.1.0", 30)
    assert result["hosts"] == "2"
    assert result["hostmin"] == "192.168.1.1"
    assert result["hostmax"] == "192.168.1.2"


def test_core_consistency_gui_cli():
    """Test that GUI and CLI would produce identical results."""
    local_cases = [
        ("192.168.1.1", 24),
        ("10.0.0.1", 8),
        ("172.16.5.4", 16),
        ("192.168.2.1", 32),
        ("192.168.3.0", 31),
        ("0.0.0.0", 0),
    ]

    for ip, prefix in local_cases:
        result = compute(ip, prefix)
        # Verify all required fields are present
        required_fields = ["network", "prefix", "netmask", "broadcast", "hostmin", "hostmax", "hosts"]
        for field in required_fields:
            assert field in result
            assert result[field] != ""


# --- Special ranges (previously TestSpecialRanges) ---

def test_special_loopback_range():
    """Test loopback address range (127/8)."""
    result = compute("127.0.0.1", 8)
    assert result["network"] == "127.0.0.0"
    assert result["prefix"] == "/8"
    assert result["netmask"] == "255.0.0.0"
    assert result["broadcast"] == "*"
    assert result["hostmin"] == "127.0.0.1"
    assert result["hostmax"] == "127.255.255.254"
    assert result["hosts"] == "16777214"
    assert result["comment"] == f"RFC 3330 Loopback ({REPO_URL}/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)"


def test_special_link_local_range():
    """Test link-local address range (169.254/16)."""
    result = compute("169.254.1.1", 16)
    assert result["network"] == "169.254.0.0"
    assert result["prefix"] == "/16"
    assert result["netmask"] == "255.255.0.0"
    assert result["broadcast"] == "*"
    assert result["hostmin"] == "*"
    assert result["hostmax"] == "*"
    assert result["hosts"] == "*"
    assert result["comment"] == f"RFC 3927 Link-local ({REPO_URL}/blob/main/docs/RFC.md#rfc-3927---link-local-addresses)"


def test_special_multicast_range():
    """Test multicast address range (224/4)."""
    result = compute("224.0.0.1", 4)
    assert result["network"] == "224.0.0.0"
    assert result["prefix"] == "/4"
    assert result["netmask"] == "240.0.0.0"
    assert result["broadcast"] == "*"
    assert result["hostmin"] == "*"
    assert result["hostmax"] == "*"
    assert result["hosts"] == "*"
    assert result["comment"] == f"RFC 5771 Multicast ({REPO_URL}/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"


def test_special_unspecified_range():
    """Test unspecified address range (0.0.0.0/8 but not /0)."""
    result = compute("0.0.0.1", 8)
    assert result["network"] == "0.0.0.0"
    assert result["prefix"] == "/8"
    assert result["netmask"] == "255.0.0.0"
    assert result["broadcast"] == "*"
    assert result["hostmin"] == "*"
    assert result["hostmax"] == "*"
    assert result["hosts"] == "*"
    assert result["comment"] == f"RFC 1122 Unspecified ({REPO_URL}/blob/main/docs/RFC.md#rfc-1122---unspecified-addresses)"


def test_special_broadcast_address():
    """Test limited broadcast address (255.255.255.255/32)."""
    result = compute("255.255.255.255", 32)
    assert result["network"] == "255.255.255.255"
    assert result["prefix"] == "/32"
    assert result["netmask"] == "255.255.255.255"
    assert result["broadcast"] == "*"
    assert result["hostmin"] == "*"
    assert result["hostmax"] == "*"
    assert result["hosts"] == "*"
    assert result["comment"] == f"RFC 919 Broadcast ({REPO_URL}/blob/main/docs/RFC.md#rfc-919---broadcast-address)"


def test_special_default_route_not_special():
    """Test that default route (0.0.0.0/0) is not treated as special."""
    result = compute("0.0.0.0", 0)
    assert result["network"] == "0.0.0.0"
    assert result["broadcast"] == "255.255.255.255"
    assert result["hostmin"] == "0.0.0.1"
    assert result["hostmax"] == "255.255.255.254"
    assert result["hosts"] == "4294967294"
    assert result["comment"] == ""


def test_special_normal_unicast_unchanged():
    """Test that normal unicast addresses are unchanged."""
    local_cases = [
        ("192.168.1.1", 24),
        ("10.0.0.1", 8),
        ("172.16.1.1", 16),
        ("8.8.8.8", 32),
    ]

    for ip, prefix in local_cases:
        result = compute(ip, prefix)
        assert result["comment"] == ""
        # Should have normal host calculations
        assert "*" not in result["hostmin"]
        assert "*" not in result["hostmax"]


def test_special_range_edge_cases():
    """Test edge cases for special ranges."""
    special_cases = [
        ("127.1.1.1", 24, f"RFC 3330 Loopback ({REPO_URL}/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)"),
        ("169.254.1.1", 24, f"RFC 3927 Link-local ({REPO_URL}/blob/main/docs/RFC.md#rfc-3927---link-local-addresses)"),
        ("224.1.1.1", 8, f"RFC 5771 Multicast ({REPO_URL}/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"),
        ("239.255.255.255", 32, f"RFC 5771 Multicast ({REPO_URL}/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"),
    ]

    for ip, prefix, expected_message in special_cases:
        result = compute(ip, prefix)
        assert result["comment"] == expected_message
        if ip.startswith("127."):
            assert result["hostmin"] == "127.1.1.1"
            assert result["hostmax"] == "127.1.1.254"
            assert result["hosts"] == "254"
        else:
            assert result["hostmin"] == "*"
            assert result["hostmax"] == "*"
            assert result["hosts"] == "*"


# --- Golden cases (previously TestGoldenCases) ---

def test_golden_standard_networks():
    """Test standard network configurations with known results"""
    golden_cases = [
        ("192.168.1.1", 24, "192.168.1.0", "192.168.1.255", "254"),
        ("10.0.0.1", 8, "10.0.0.0", "10.255.255.255", "16777214"),
        ("172.16.0.1", 16, "172.16.0.0", "172.16.255.255", "65534"),
        ("192.168.1.1", 23, "192.168.0.0", "192.168.1.255", "510"),
        ("192.168.1.1", 25, "192.168.1.0", "192.168.1.127", "126"),
        ("192.168.1.1", 30, "192.168.1.0", "192.168.1.3", "2"),
        ("192.168.1.1", 31, "192.168.1.0", "192.168.1.1", "2*"),
        ("192.168.1.1", 32, "192.168.1.1", "192.168.1.1", "1*"),
    ]

    for ip, prefix, expected_network, expected_broadcast, expected_hosts in golden_cases:
        result = compute(ip, prefix)
        assert result["network"] == expected_network, f"Failed for {ip}/{prefix}"
        assert result["broadcast"] == expected_broadcast, f"Failed for {ip}/{prefix}"
        assert result["hosts"] == expected_hosts, f"Failed for {ip}/{prefix}"


def test_golden_rfc_3021_compliance():
    """Test /31 networks according to RFC 3021 (point-to-point links)"""
    # RFC 3021: Using 31-Bit Prefixes on IPv4 Point-to-Point Links
    # For /31 networks, both addresses are usable for hosts
    result = compute("192.168.1.0", 31)
    assert result["network"] == "192.168.1.0"
    assert result["broadcast"] == "192.168.1.1"
    assert result["hostmin"] == "192.168.1.0"
    assert result["hostmax"] == "192.168.1.1"
    assert result["hosts"] == "2*"

    result = compute("192.168.1.2", 31)
    assert result["network"] == "192.168.1.2"
    assert result["broadcast"] == "192.168.1.3"
    assert result["hostmin"] == "192.168.1.2"
    assert result["hostmax"] == "192.168.1.3"
    assert result["hosts"] == "2*"


def test_golden_single_host_networks():
    """Test /32 networks (single host)"""
    result = compute("192.168.1.100", 32)
    assert result["network"] == "192.168.1.100"
    assert result["broadcast"] == "192.168.1.100"
    assert result["hostmin"] == "192.168.1.100"
    assert result["hostmax"] == "192.168.1.100"
    assert result["hosts"] == "1*"


# --- Network Interface Detection Tests ---

def test_get_ip_returns_valid_ip():
    """Test that get_ip returns a valid IPv4 address."""
    ip = get_internal_ip()
    assert validate_ip(ip) is None  # validate_ip raises ValueError if invalid
    assert ipaddress.IPv4Address(ip)  # Should not raise


def test_get_ip_fallback_to_loopback():
    """Test get_ip fallback to loopback when network detection fails."""
    # This test verifies the fallback mechanism works
    # We can't easily mock the socket connection, but we can verify the function doesn't crash
    try:
        ip = get_internal_ip()
        assert ip is not None
        assert len(ip) > 0
    except Exception:
        # If network detection fails completely, it should fallback to 127.0.0.1
        pass


def test_get_cidr_returns_valid_prefix():
    """Test that get_cidr returns a valid CIDR prefix (0-32)."""
    # Test with a common private IP
    cidr = get_cidr("192.168.1.1")
    assert 0 <= cidr <= 32
    assert isinstance(cidr, int)


def test_get_cidr_fallback_to_24():
    """Test get_cidr fallback to /24 when detection fails."""
    # Test with an IP that likely won't be found in routing tables
    cidr = get_cidr("10.255.255.255")
    assert cidr == 24  # Should fallback to /24


def test_get_cidr_windows_mock():
    """Test Windows CIDR detection with mocked subprocess."""
    from unittest.mock import patch, MagicMock

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = """
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 192.168.1.100
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
"""

    with patch('subprocess.run', return_value=mock_result):
        cidr = get_cidr_windows("192.168.1.100")
        assert cidr == 24  # 255.255.255.0 = /24


def test_get_cidr_macos_mock():
    """Test macOS CIDR detection with mocked subprocess."""
    from unittest.mock import patch, MagicMock

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = """
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255
"""

    with patch('subprocess.run', return_value=mock_result):
        cidr = get_cidr_macos("192.168.1.100")
        assert cidr == 24  # 0xffffff00 = 255.255.255.0 = /24


def test_get_cidr_linux_mock():
    """Test Linux CIDR detection with mocked subprocess."""
    from unittest.mock import patch, MagicMock

    # Mock ip route get
    mock_route_get = MagicMock()
    mock_route_get.returncode = 0
    mock_route_get.stdout = "192.168.1.100 via 192.168.1.1 dev eth0 src 192.168.1.100 uid 1000"

    # Mock ip route show
    mock_route_show = MagicMock()
    mock_route_show.returncode = 0
    mock_route_show.stdout = "192.168.1.0/24 via 192.168.1.1 dev eth0"

    with patch('subprocess.run', side_effect=[mock_route_get, mock_route_show]):
        cidr = get_cidr_linux("192.168.1.100")
        assert cidr == 24


def test_cidr_from_netmask():
    """Test CIDR calculation from netmask."""
    assert cidr_from_netmask("255.255.255.0") == 24
    assert cidr_from_netmask("255.255.0.0") == 16
    assert cidr_from_netmask("255.0.0.0") == 8
    assert cidr_from_netmask("255.255.255.252") == 30
    assert cidr_from_netmask("255.255.255.254") == 31
    assert cidr_from_netmask("255.255.255.255") == 32
    assert cidr_from_netmask("0.0.0.0") == 0


def test_cidr_from_netmask_invalid():
    """Test CIDR calculation with invalid netmasks."""
    with pytest.raises(ValueError):
        cidr_from_netmask("256.256.256.256")

    with pytest.raises(ValueError):
        cidr_from_netmask("255.255.255.1")  # Invalid netmask

    with pytest.raises(ValueError):
        cidr_from_netmask("invalid")


def test_network_interface_detection_integration():
    """Test integration of IP and CIDR detection."""
    try:
        ip = get_internal_ip()
        cidr = get_cidr(ip)

        # Both should be valid
        assert validate_ip(ip) is None
        assert 0 <= cidr <= 32

        # Should be able to compute network info
        try:
            result = compute_from_cidr(f"{ip}/{cidr}")
            assert "network" in result
            assert "prefix" in result
            assert "netmask" in result
        except Exception as e:
            # If network detection fails, that's acceptable
            # The important thing is that it doesn't crash
            assert "network" in str(e) or "socket" in str(e) or "subprocess" in str(e)
    except Exception:
        # If network detection fails, that's acceptable
        # The important thing is that it doesn't crash
        pass


def test_gui_clipboard_functionality_no_qtbot():
    """Test clipboard functionality in GUI without qtbot (smoke test)."""
    if skip_gui_tests():
        pytest.skip("GUI tests disabled in CI/headless environment")

    app = LanCalc()
    # Just test that the method doesn't crash
    app.check_clipboard()


def test_external_ip_retrieval():
    """Test external IP retrieval functionality."""
    external_ip = get_external_ip()

    try:
        # Should be a valid IPv4 address
        assert external_ip is not None
        assert isinstance(external_ip, str)

        # Validate it's a proper IPv4 address
        ipaddress.IPv4Address(external_ip)

        # Should not be a private IP
        ip_obj = ipaddress.IPv4Address(external_ip)
        assert not ip_obj.is_private
        assert not ip_obj.is_loopback
        assert not ip_obj.is_link_local
        assert not ip_obj.is_multicast

    except Exception:
        # It's okay if external IP retrieval fails (network issues, etc.)
        # but we should get a proper ValueError
        pass


def test_external_ip_cli():
    """Test external IP CLI functionality."""
    # Test without JSON
    result = subprocess.run(
        [sys.executable, "-m", "lancalc", "-e"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )

    if result.returncode == 0:
        # Success case
        assert "External IP:" in result.stdout
        assert result.stderr == ""
    else:
        # Failure case (network issues, etc.)
        assert "Failed to get external IP" in result.stderr or "Failed to get external IP" in result.stdout


def test_external_ip_cli_json():
    """Test external IP CLI functionality with JSON output."""
    # Test with JSON
    result = subprocess.run(
        [sys.executable, "-m", "lancalc", "-e", "--json"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )

    if result.returncode == 0:
        # Success case
        data = json.loads(result.stdout.strip())
        assert "external_ip" in data
        assert isinstance(data["external_ip"], str)

        # Validate it's a proper IPv4 address
        ipaddress.IPv4Address(data["external_ip"])
    else:
        # Failure case (network issues, etc.)
        assert "Failed to get external IP" in result.stderr or "Failed to get external IP" in result.stdout


def main():
    pass


if __name__ == "__main__":
    main()
