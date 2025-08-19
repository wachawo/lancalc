#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Command-line interface for LanCalc.
"""
import argparse
import json
import logging
import os
import sys
import typing
import traceback


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
    from . import core
    from . import adapters
except ImportError:
    try:
        from lancalc import __version__ as VERSION
        import core
        import adapters
    except Exception as e:
        logger.warning(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        VERSION = "0.0.0"

logger.debug(f"LanCalc {VERSION} starting...")


def print_result_stdout(res: typing.Dict[str, str]) -> None:
    """Print result to stdout in human-readable format."""
    for k in ("network", "prefix", "netmask", "broadcast", "hostmin", "hostmax", "hosts"):
        print(f"{k.capitalize()}: {res[k]}")

    # Print comment if present for special ranges
    if res.get("comment"):
        print(f"Comment: {res['comment']}")


def print_result_json(res: typing.Dict[str, str]) -> None:
    """Print result as valid JSON to stdout."""
    # Filter out type and empty comment fields for cleaner JSON output
    filtered_res = res.copy()
    if filtered_res.get("comment") == "":
        filtered_res.pop("comment", None)
    filtered_res.pop("type", None)
    print(json.dumps(filtered_res))


def print_internal_ip_info(json_output: bool = False) -> None:
    """Print information about detected network interfaces."""
    try:
        ip = adapters.get_internal_ip()
        cidr = adapters.get_cidr(ip)

        if json_output:
            interface_info = {
                "address": ip,
                "prefix": f"/{cidr}",
            }
            print(json.dumps(interface_info))
        else:
            print(f"Address: {ip}")
            print(f"Prefix: /{cidr}")

    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        error_msg = f"Failed to get internal IP: {e}"
        if json_output:
            print(json.dumps({"error": error_msg}))
        else:
            print(error_msg, file=sys.stderr)


def print_external_ip_info(json_output: bool = False) -> None:
    """Print information about external/public IP address."""
    try:
        external_ip = adapters.get_external_ip()

        if json_output:
            external_info = {
                "external_ip": external_ip,
            }
            print(json.dumps(external_info))
        else:
            print(f"External IP: {external_ip}")

    except Exception as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        error_msg = f"Failed to get external IP: {e}"
        if json_output:
            print(json.dumps({"error": error_msg}))
        else:
            print(error_msg, file=sys.stderr)


def run_cli(address: str, json_output: bool = False) -> int:
    """
    Run CLI mode with given address.

    Args:
        address: IPv4 address in CIDR notation
        json_output: Whether to output JSON format

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        result = core.compute_from_cidr(address)
        if json_output:
            print_result_json(result)
        else:
            print_result_stdout(result)
        return 0

    except ValueError as e:
        logger.error(f"{type(e).__name__} {str(e)}\n{traceback.format_exc()}")
        # Log validation errors to stderr only
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def main(argv: typing.Optional[list] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (uses sys.argv[1:] if None)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if argv is None:
        # Exclude program name when parsing args
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="lancalc",
        description="LanCalc: IPv4 subnet calculator",
        epilog="Examples:\n  lancalc 192.168.1.1/24\n  lancalc 10.0.0.1/8 --json\n  lancalc --external",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="IPv4 address in CIDR notation (e.g., 192.168.1.1/24)"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="Output result in JSON format"
    )
    parser.add_argument("--version", "-v", action="version", version=f"LanCalc {VERSION}")
    parser.add_argument(
        "--internal",
        "-i",
        action="store_true",
        help="Show internal IP address"
    )
    parser.add_argument(
        "--external",
        "-e",
        action="store_true",
        help="Show external/public IP address"
    )

    args = parser.parse_args(argv)

    # Handle multiple info requests
    info_requests = []
    if args.internal:
        info_requests.append(("internal", print_internal_ip_info))
    if args.external:
        info_requests.append(("external", print_external_ip_info))

    # If any info requests, process them
    if info_requests:
        for info_type, print_func in info_requests:
            print_func(args.json)
            # Add separator between multiple outputs (except for last one)
            if info_requests.index((info_type, print_func)) < len(info_requests) - 1:
                print()  # Empty line separator
        return 0

    # If address is provided, process it
    if args.address:
        return run_cli(args.address, args.json)

    # For CLI mode without address, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
