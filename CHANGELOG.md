# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-19

### Added
- Initial release of Marshall Bluetooth Speakers Home Assistant integration
- **Media Player Platform**
  - Play/pause/next/previous track controls
  - Volume control with real-time feedback (0-32 range)
  - Media metadata display (track title, artist, album)
  - Audio source selection (Bluetooth, Aux, RCA)
- **Number Platform**
  - LED brightness control (0-35 range)
- **Select Platform**
  - Audio source selector (model-dependent: Bluetooth, Aux, RCA)
  - EQ preset selector (Stanmore II only: Flat, Bright, Warm, Voice)
- **Sensor Platform**
  - Device name sensor
  - Model name sensor
  - Serial number sensor
  - Firmware version sensor
  - Hardware version sensor
  - Volume level sensor
  - Audio source sensor
  - Play status sensor
- **Binary Sensor Platform**
  - Connection status binary sensor
- **Device Support**
  - Acton II model support
  - Stanmore II model support
  - Extensible model configuration system
- **BLE Integration**
  - Bluetooth Low Energy connectivity
  - Automatic device discovery
  - Real-time status updates via BLE notifications
- **Configuration Flow**
  - User-friendly setup wizard
  - Automatic device discovery
  - Manual device configuration option
  - Device confirmation step for security
- **Developer Tools**
  - Setup script for development environment
  - Linting with ruff
  - Development helper scripts
  - HACS integration ready

### Technical Details
- Bluetooth service UUID: `0000fe8f-0000-1000-8000-00805f9b34fb`
- IoT class: `local_push`
- Config flow enabled
- Bluetooth dependency integration

[0.1.0]: https://github.com/elrobertocarlos/marshall_bluetooth_speaker/releases/tag/v0.1.0
