#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core functionality for LanCalc - IPv4 subnet calculations.

Pure business logic for network calculations without external dependencies.
"""
import ipaddress
import logging
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

REPO_URL = "https://github.com/wachawo/lancalc"


def validate_ip(ip: str) -> None:
    """Validate IPv4 address format or raise ValueError."""
    try:
        ipaddress.IPv4Address(ip)
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid IP address: {ip}") from exc


def validate_prefix(prefix: str) -> int:
    """Validate CIDR prefix (0-32). Return int or raise ValueError."""
    try:
        prefix_int = int(prefix)
    except ValueError as exc:
        raise ValueError(f"Invalid prefix: {prefix}") from exc
    if 0 <= prefix_int <= 32:
        return prefix_int
    raise ValueError(f"Invalid prefix: {prefix}")


def classify_ipv4_range(network: ipaddress.IPv4Network) -> str:
    """
    Classify IPv4 network range and return message for special ranges.

    Args:
        network: IPv4Network object to classify

    Returns:
        Message string for special ranges, empty string for unicast

    Special ranges:
        - loopback: Loopback address (127.0.0.0/8) → "Loopback - RFC3330"
        - link_local: Link-local address (169.254.0.0/16) → "Link-local - RFC3927"
        - multicast: Multicast address (224.0.0.0/4) → "Multicast - RFC5771"
        - unspecified: Unspecified address (0.0.0.0/8 but not 0.0.0.0/0) → "Unspecified - RFC1122"
        - broadcast: Limited broadcast (255.255.255.255/32) → "Broadcast - RFC919"
    """
    # Get the network address for classification
    net_addr = network.network_address

    # Check for specific special ranges
    if net_addr in ipaddress.IPv4Network('127.0.0.0/8'):
        return f'RFC 3330 Loopback ({REPO_URL}/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)'
    elif net_addr in ipaddress.IPv4Network('169.254.0.0/16'):
        return f'RFC 3927 Link-local ({REPO_URL}/blob/main/docs/RFC.md#rfc-3927---link-local-addresses)'
    elif net_addr in ipaddress.IPv4Network('224.0.0.0/4'):
        return f'RFC 5771 Multicast ({REPO_URL}/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)'
    elif net_addr in ipaddress.IPv4Network('0.0.0.0/8') and network.prefixlen > 0:
        # Only classify as unspecified if it's not the default route (0.0.0.0/0)
        return f'RFC 1122 Unspecified ({REPO_URL}/blob/main/docs/RFC.md#rfc-1122---unspecified-addresses)'
    elif network.network_address == ipaddress.IPv4Address('255.255.255.255'):
        return f'RFC 919 Broadcast ({REPO_URL}/blob/main/docs/RFC.md#rfc-919---broadcast-address)'
    else:
        return ''


def is_special_range(message: str) -> bool:
    """Check if the message indicates a special range."""
    return bool(message.strip())


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
        - Broadcast: broadcast address (or "*" for special ranges)
        - Hostmin: first usable host (or "*" for special ranges)
        - Hostmax: last usable host (or "*" for special ranges)
        - Hosts: number of usable hosts (or "*" for special ranges)
        - message: message for special ranges (empty for unicast)

    Raises:
        ValueError: if IP or prefix is invalid
    """
    # Validate inputs
    validate_ip(ip)
    validate_prefix(str(prefix))

    # Create network object
    net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
    total = net.num_addresses

    # Classify the range
    message = classify_ipv4_range(net)
    is_special = is_special_range(message)

    # Calculate host range
    if is_special:
        # For special ranges, handle differently based on type
        if net.network_address in ipaddress.IPv4Network('127.0.0.0/8'):
            # Loopback: calculate actual host range for the subnet
            if total > 2:
                hostmin = ipaddress.IPv4Address(int(net.network_address) + 1)
                hostmax = ipaddress.IPv4Address(int(net.broadcast_address) - 1)
                hostmin_str = str(hostmin)
                hostmax_str = str(hostmax)
                hosts_str = str(total - 2)
            else:
                hostmin_str = str(net.network_address)
                hostmax_str = str(net.broadcast_address)
                hosts_str = str(total)
            broadcast_str = "*"
        else:
            # For other special ranges, mark host addresses as "*"
            hostmin_str = "*"
            hostmax_str = "*"
            hosts_str = "*"
            broadcast_str = "*"
    elif total > 2:
        hostmin = ipaddress.IPv4Address(int(net.network_address) + 1)
        hostmax = ipaddress.IPv4Address(int(net.broadcast_address) - 1)
        hostmin_str = str(hostmin)
        hostmax_str = str(hostmax)
        hosts_str = str(total - 2)
        broadcast_str = str(net.broadcast_address)
    else:
        hostmin_str = str(net.network_address)
        hostmax_str = str(net.broadcast_address)
        hosts_str = f"{total}*"
        broadcast_str = str(net.broadcast_address)

    return {
        "network": str(net.network_address),
        "prefix": f"/{prefix}",
        "netmask": str(net.netmask),
        "broadcast": broadcast_str,
        "hostmin": hostmin_str,
        "hostmax": hostmax_str,
        "hosts": hosts_str,
        "comment": message
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


def main():
    pass


if __name__ == '__main__':
    main()
