#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
External system adapters for LanCalc.

This module handles all external interactions:
- Network interface detection
- External IP retrieval
- System-specific network operations
"""
import json
import logging
import socket
import subprocess
import sys
import platform
import re
import traceback
import urllib.request
import urllib.error


logging.basicConfig(
    handlers=[logging.StreamHandler(sys.stderr)],
    level=logging.WARNING,
    format="%(asctime)s.%(msecs)03d [%(levelname)s]: (%(name)s.%(funcName)s) - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_internal_ip() -> str:
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


def get_external_ip() -> str:
    """Return the external/public IPv4 address using ifconfig.me service."""
    try:
        # Use ifconfig.me service to get external IP
        with urllib.request.urlopen("https://ifconfig.me/ip", timeout=10) as response:
            external_ip = response.read().decode("utf-8").strip()
            # Basic validation that it looks like an IP
            if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", external_ip):
                raise ValueError(f"Invalid IP format returned: {external_ip}")
            return external_ip

    except urllib.error.URLError as e:
        logger.error(
            f"Failed to get external IP from ifconfig.me: {type(e).__name__} {str(e)}"
        )
        raise ValueError("Failed to retrieve external IP address") from e
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error getting external IP: {e.code} {e.reason}")
        raise ValueError("Failed to retrieve external IP address") from e
    except socket.timeout as e:
        logger.error(f"Timeout getting external IP: {str(e)}")
        raise ValueError("Timeout retrieving external IP address") from e
    except Exception as e:
        logger.error(
            f"Unexpected error getting external IP: {type(e).__name__} {str(e)}"
        )
        raise ValueError("Failed to retrieve external IP address") from e


def cidr_from_netmask(mask: str) -> int:
    """Convert netmask to CIDR prefix."""
    try:
        parts = [int(x) for x in mask.split(".")]
        if len(parts) != 4:
            raise ValueError(f"Invalid netmask format: {mask}")

        # Validate netmask (must be consecutive 1s followed by 0s)
        binary = "".join(f"{p:08b}" for p in parts)
        if "01" in binary:  # Check for 1s after 0s
            raise ValueError(f"Invalid netmask: {mask}")

        return sum(bin(p).count("1") for p in parts)
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        raise ValueError(f"Invalid netmask: {mask}") from e


def get_cidr(ip: str) -> int:
    """Best-effort CIDR detection using system tools; defaults to /24."""
    system = platform.system()
    try:
        if system == "Windows":
            return get_cidr_windows(ip)
        elif system == "Darwin":
            return get_cidr_macos(ip)
        else:
            return get_cidr_linux(ip)
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def get_cidr_windows(ip: str) -> int:
    """Get CIDR for Windows systems with improved locale support."""
    try:
        # Try PowerShell first for better locale support
        try:
            cmd = [
                "powershell",
                "-Command",
                f"Get-NetIPAddress -IPAddress '{ip}' | Select-Object -ExpandProperty PrefixLength",
            ]
            out = subprocess.check_output(
                cmd, encoding="utf-8", errors="ignore", timeout=5
            )
            prefix = out.strip()
            if prefix.isdigit():
                return int(prefix)
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
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
                    mask_keywords = [
                        "subnet mask",
                        "маска подсети",
                        "subnetmaske",
                        "máscara de sub-rede",
                        "masque de sous-réseau",
                        "subnetmask",
                        "netmask",
                        "маска підмережі",
                    ]
                    if any(keyword in line_lower for keyword in mask_keywords):
                        # Extract mask using multiple patterns
                        mask_patterns = [
                            r"[:=]\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
                            r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})",
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


def get_cidr_macos(ip: str) -> int:
    """Get CIDR for macOS systems."""
    try:
        # Method 1: Use networksetup for better reliability
        try:
            # Get all network services
            services_cmd = ["networksetup", "-listallnetworkservices"]
            services_out = subprocess.check_output(
                services_cmd, encoding="utf-8", errors="ignore"
            )

            for service in services_out.splitlines()[1:]:  # Skip first line (header)
                service = service.strip()
                if not service:
                    continue

                # Get IP for this service
                try:
                    ip_cmd = ["networksetup", "-getinfo", service]
                    ip_out = subprocess.check_output(
                        ip_cmd, encoding="utf-8", errors="ignore"
                    )

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
            m = re.search(
                r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+0x([0-9a-fA-F]+)", line
            )
            if m and m.group(1) == ip:
                netmask_hex = m.group(2)
                netmask_int = int(netmask_hex, 16)
                return bin(netmask_int).count("1")
        return 24
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def get_cidr_linux(ip: str) -> int:
    """Get CIDR for Linux systems."""
    try:
        # Try JSON output first for better parsing
        try:
            out = subprocess.check_output(
                ["ip", "-json", "-4", "addr", "show"], encoding="utf-8", errors="ignore"
            )
            data = json.loads(out)
            for iface in data:
                for addr in iface.get("addr_info", []):
                    if addr.get("local") == ip:
                        return addr.get("prefixlen", 24)
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            pass
        # Fallback to text parsing
        out = subprocess.check_output(
            ["ip", "-o", "-4", "addr", "show"], encoding="utf-8", errors="ignore"
        )
        for line in out.splitlines():
            m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", line)
            if m and m.group(1) == ip:
                return int(m.group(2))
        return 24
    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        return 24


def main():
    pass


if __name__ == '__main__':
    main()
