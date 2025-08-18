# LanCalc

[![CI](https://github.com/lancalc/lancalc/actions/workflows/ci.yml/badge.svg)](https://github.com/lancalc/lancalc/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lancalc.svg)](https://pypi.org/project/lancalc/)
[![Python](https://img.shields.io/pypi/pyversions/lancalc.svg)](https://pypi.org/project/lancalc/)

LanCalc is a desktop application built with PyQt5, designed to calculate network configurations for Windows, macOS, and Linux systems.

![image](https://github.com/user-attachments/assets/be7655cc-9348-4d7c-bb25-a650e00cc422)

[Download](https://github.com/lancalc/lancalc/releases)

It provides a user-friendly interface to compute essential network parameters such as network address, broadcast address, the minimum and maximum host addresses, and the number of hosts within a given subnet. 

Support IPv4 address formats, subnet masks and prefixes. This tool is particularly useful for network administrators and IT professionals who require quick calculations of network parameters.

## Quick Start

### Installation

**Install LanCalc Stable version:**

```bash
pip3 install lancalc
```

**Or install LanCalc from GitHub:**

```bash
pip3 install git+https://github.com/lancalc/lancalc.git
```

Install PIP

```bash
curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py
```

If the `lancalc` command is not found after installation, add the local packages path to PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

To permanently add to PATH, add this line to your `~/.bashrc` or `~/.zshrc`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Running the Application

### GUI Mode

After installation, launch the application with the command:

```bash
lancalc
```

### CLI Mode

LanCalc also supports command-line interface for automation and scripting:

```bash
# Basic usage
lancalc 192.168.1.1/24

# JSON output for parsing
lancalc 192.168.1.1/24 --json

# Examples
lancalc 10.0.0.1/8
lancalc 172.16.0.1/16
lancalc 192.168.1.100/31  # Point-to-point network
lancalc 192.168.1.1/32    # Single host
```

### Output Format

**Text mode** (default):
```
Network: 192.168.1.0
Prefix: /24
Netmask: 255.255.255.0
Broadcast: 192.168.1.255
Hostmin: 192.168.1.1
Hostmax: 192.168.1.254
Hosts: 254
```

**JSON mode** (`--json`):
```json
{
  "network": "192.168.1.0",
  "prefix": "/24",
  "netmask": "255.255.255.0",
  "broadcast": "192.168.1.255",
  "hostmin": "192.168.1.1",
  "hostmax": "192.168.1.254",
  "hosts": "254",
  "comment": ""
}
```

### Uninstall

```bash
pip3 uninstall -y lancalc
```

That's it! The application will start and automatically detect your current network settings.

## For Developers

### Prerequisites

Python 3.9+ is required.

For production use (CLI only):
```bash
pip3 install -r requirements.txt
```

For GUI support:
```bash
pip3 install -e .[gui]
```

For development:
```bash
pip3 install -e .[dev,gui]
```

### Installation for Development

Clone the repository and install in development mode:

```bash
git clone https://github.com/lancalc/lancalc.git
```

### Running from Source

```bash
python3 lancalc/main.py
```

### Development Tools

```bash
pip3 install pre-commit flake8 pytest pytest-qt
pre-commit install
pre-commit run --all-files
pre-commit autoupdate
```

### Running Tests
```bash
pytest -v
```

### Test Build
```bash
pip3 install -e .
~/.local/bin/lancalc
```

### Test Build Linux
```bash
pip3 install git+file://$(pwd) 
export PATH="$HOME/.local/bin:$PATH" 
lancalc
```

### Test Build Windows
```powershell
pip3 install "git+file://$(Get-Location)"
lancalc
```

## License

Distributed under the MIT License. See LICENSE for more information.

## Contact

[GitHub](https://github.com/lancalc/lancalc) [Telegram](https://t.me/wachawo)

## Notes

A /31 mask allows the use of 2 addresses. The first will be the network address, the last the broadcast address, and for connecting hosts we use these same addresses.
Limitations when using a /31 prefix:
Protocols that use L3 broadcast stop working.
In fact, at present there are almost no protocols left that rely on L3 broadcast in their operation. The main currently relevant protocols, such as OSPF, IS-IS, EIGRP, and BGP, use multicast or unicast addresses instead.
This limitation can even be seen as an advantage, because it increases resistance to DoS attacks based on broadcast traffic distribution.
But not all devices support /31 prefixes.
On Juniper and Cisco devices, you can safely use a /31 mask, although Cisco will issue a warning (% Warning: use /31 mask on non point-to-point interface cautiously).
ZyXEL, however, does not allow you to select a /31 mask at all.
As a result, there are additional limitations in network operation — from using equipment of different manufacturers to even using equipment from the same vendor but with different firmware versions.
If you are not concerned by the above limitations, you can confidently save addresses by using the /31 prefix.

The use of the /31 prefix is described in detail in RFC 3021 — Using 31-Bit Prefixes on IPv4 Point-to-Point Links.


## Special IPv4 Ranges and Cases

### Special Network Types

- **/31 networks**: Show `2*` in Hosts field - both addresses are usable (RFC 3021)
- **/32 networks**: Show `1*` in Hosts field - single host network
- The asterisk (*) indicates special network types where all addresses are usable

### Special IPv4 Address Ranges

LanCalc automatically detects and handles special IPv4 address ranges according to RFC specifications. For these ranges, host-related fields show "*" and a message field indicates the range type with RFC reference.

#### Supported Special Ranges

| Range | Type | RFC | Description |
|-------|------|-----|-------------|
| **127.0.0.0/8** | Loopback | [RFC 3330](docs/RFC.md#rfc-3330---loopback-addresses) | Loopback addresses - not routable on the Internet |
| **169.254.0.0/16** | Link-local | [RFC 3927](docs/RFC.md#rfc-3927---link-local-addresses) | Link-local addresses - not routable |
| **224.0.0.0/4** | Multicast | [RFC 5771](docs/RFC.md#rfc-5771---multicast-addresses) | Multicast addresses - not for host addressing |
| **0.0.0.0/8** | Unspecified | [RFC 1122](docs/RFC.md#rfc-1122---unspecified-addresses) | Unspecified addresses - not for host addressing |
| **255.255.255.255/32** | Broadcast | [RFC 919](docs/RFC.md#rfc-919---broadcast-address) | Limited broadcast address - not for host addressing |

#### Special Range Behavior

When you enter an address from a special range:

**CLI Text Mode:**
```bash
lancalc 127.0.0.1/8
```
```
Network: 127.0.0.0
Prefix: /8
Netmask: 255.0.0.0
Broadcast: *
Hostmin: 127.0.0.1
Hostmax: 127.255.255.254
Hosts: 16777214
Comment: RFC 3330 Loopback (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-3330---loopback-addresses)
```

**CLI JSON Mode:**
```bash
lancalc 224.0.0.1/4 --json
```
```json
{
  "network": "224.0.0.0",
  "prefix": "/4",
  "netmask": "240.0.0.0",
  "broadcast": "*",
  "hostmin": "*",
  "hostmax": "*",
  "hosts": "*",
  "comment": "RFC 5771 Multicast (https://github.com/lancalc/lancalc/blob/main/docs/RFC.md#rfc-5771---multicast-addresses)"
}
```

**GUI Mode:**
- Host fields (Hostmin, Hostmax, Broadcast, Hosts) show "*"
- Status bar displays the special range message instead of version
- No special styling or warnings needed

#### JSON Fields

The JSON output includes the following fields:

- **`comment`**: Description and RFC reference for special ranges (empty for normal unicast addresses)
- **`comment`**: Description and RFC reference for special ranges (empty for normal unicast addresses)
- **`hosts`**: Number of available host addresses in the specified subnet

These fields are always present, making the JSON output format consistent regardless of address type.
