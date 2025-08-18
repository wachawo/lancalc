# CHANGELOG

All notable changes to LanCalc will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
