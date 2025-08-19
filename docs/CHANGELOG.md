# CHANGELOG

All notable changes to LanCalc will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.9] - 2024-12-19

### Added
- **External IP detection**: New `-e/--external` CLI flag to retrieve external/public IP address via `https://ifconfig.me/`
- **Simultaneous CLI flags**: Support for using multiple info flags simultaneously (e.g., `-i -e`)
- **Modular architecture**: Created `adapters.py` for external system interactions
- **Clean separation**: Moved network interface detection and external IP retrieval to `adapters.py`
- **Enhanced error handling**: Better validation and error messages for external IP retrieval
- **nogui extras**: New optional dependency group for CLI-only installations without PyQt5
- **Adaptive launcher**: Main entry point automatically detects environment and chooses CLI/GUI mode
- **Better error handling**: Improved fallback mechanisms when GUI is unavailable

### Changed
- **Architecture refactoring**: Simplified project structure with main.py as core CLI and gui.py as optional GUI module
- **Modular design**: Separated CLI and GUI functionality into distinct modules for better maintainability
- **Optional GUI**: GUI can now be installed separately or excluded entirely via nogui extras
- **Clean imports**: Replaced complex import fallbacks with clean absolute package imports

### Technical
- **Simplified structure**: Removed cli.py, core.py modules in favor of consolidated main.py
- **Import optimization**: Clean absolute imports throughout the codebase
- **Entry point fixes**: Corrected pyproject.toml entry point to use main module

## [0.1.8] - 2024-12-19

### Added
- Special IPv4 network detection and handling (loopback, link-local, multicast, unspecified, broadcast)
- Comprehensive tests for special network ranges and edge cases
- RFC documentation links for special networks

### Changed
- Renamed output keys changed in JSON output (network, prefix, netmask, broadcast, hostmin, hostmax, hosts, comment)
- Refactored tests classes to top-level functions

### Fixed
- JSON output filtering: empty comment fields omitted when using -j flag
- Documentation examples updated to match actual API output

### Technical
- Improved test organization and maintainability
- Enhanced GUI error handling with red status for invalid addresses
- Simplified special range display logic
