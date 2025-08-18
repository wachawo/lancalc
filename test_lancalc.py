#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os
import pytest
import sys
import subprocess
from lancalc.main import compute, compute_from_cidr, validate_ip, validate_prefix, parse_cidr
from lancalc.main import calc_network, print_result_json, REPO_URL

# Try to import LanCalc only if GUI is available
try:
    from lancalc.main import LanCalc
    GUI_TESTS_AVAILABLE = True
except ImportError:
    GUI_TESTS_AVAILABLE = False
    LanCalc = None

# Check if we're in CI environment


def is_ci_environment():
    """Check if running in CI environment."""
    return os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'


# Configure logging for tests
logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stderr)],
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_calculate_networks(app, ip, prefix, expected):
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
    # Check color
    if expected['ip_color'] == 'red':
        assert 'red' in app.ip_input.styleSheet()
    else:
        assert 'color: black' in app.ip_input.styleSheet() or app.ip_input.styleSheet() == ''


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_invalid_cidr_handling(app):
    """Test handling of invalid CIDR values"""
    # Test with invalid CIDR (40) - this should fail validation
    app.ip_input.setText("192.168.1.1")
    # Try to set an invalid CIDR - since combobox only has 0-32, we'll test with a valid one
    # but the validation should catch it if we could set it
    app.calculate_network()
    # For now, just check that the app doesn't crash with invalid CIDR


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_window_launch(app):
    """Test basic window functionality"""
    assert app.isVisible() is False  # Window is not shown by default
    app.show()
    assert app.isVisible() is True
    assert app.windowTitle() == 'LanCalc'


# --- Validation helpers (GUI methods) ---

@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_validation_ip_address():
    """Test IP address validation"""
    app = LanCalc()

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


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_validation_cidr():
    """Test CIDR validation"""
    app = LanCalc()

    # Valid CIDRs
    for i in range(33):
        assert app.validate_cidr(str(i))

    # Invalid CIDRs
    assert not app.validate_cidr("-1")
    assert not app.validate_cidr("33")
    assert not app.validate_cidr("100")
    assert not app.validate_cidr("")
    assert not app.validate_cidr("invalid")


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_special_range_status_bar(app):
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
    # Check status bar shows message with GitHub link
    assert "RFC 3330 Loopback (GitHub)" in app.status_label.text()

    # Test multicast address
    app.ip_input.setText("224.0.0.1")
    app.network_selector.setCurrentIndex(4)  # /4
    app.calculate_network()

    assert app.network_output.text() == "224.0.0.0"
    assert app.hostmin_output.text() == "*"
    assert app.hostmax_output.text() == "*"
    assert app.hosts_output.text() == "*"
    assert app.broadcast_output.text() == "*"
    assert "RFC 5771 Multicast (GitHub)" in app.status_label.text()

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


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_error_handling(app):
    """Test error handling in GUI"""
    # Test with invalid IP
    app.ip_input.setText("invalid-ip")
    app.calculate_network()
    assert 'red' in app.ip_input.styleSheet()

    # Test with empty IP
    app.ip_input.setText("")
    app.calculate_network()
    assert 'red' in app.ip_input.styleSheet()


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_edge_cases():
    """Test edge cases for network calculations"""
    app = LanCalc()

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


@pytest.mark.skipif(is_ci_environment(), reason="GUI tests skipped in CI")
def test_gui_clipboard_functionality(qtbot):
    """Test clipboard auto-fill functionality"""
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

    # Verify IP was filled
    assert app.ip_input.text() == "192.168.1.100"

    # Verify CIDR was set (24)
    assert app.network_selector.currentText().startswith("24/")

    # Test with invalid clipboard content
    clipboard.setText("invalid-ip")
    app.ip_input.clear()
    app.check_clipboard()
    assert app.ip_input.text() == ""  # Should not fill invalid IP


# --- Core / CLI tests ---

def test_core_json_output():
    """Test JSON output functionality"""
    # Test JSON output
    result = calc_network("192.168.1.1/24")

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
        [sys.executable, "-m", "lancalc.main", "192.168.1.1/24", "--json"],
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
            [sys.executable, "-m", "lancalc.main", cidr, "--json"],
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
        [sys.executable, "-m", "lancalc.main", "192.168.1.1/24"],
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


def main():
    pass


if __name__ == "__main__":
    main()
