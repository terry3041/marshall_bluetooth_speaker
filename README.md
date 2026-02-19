# Marshall Bluetooth Speakers - Home Assistant Integration

A Home Assistant integration for controlling Marshall Bluetooth speakers over BLE (Bluetooth Low Energy).

## Features

- 🔊 **Media Player Control**: Play, pause, next, previous track controls
- 🔈 **Volume Control**: Adjust speaker volume with real-time feedback
- 💡 **LED Brightness**: Control speaker LED brightness (0-35 range)
- 🎵 **Audio Source Selection**: Switch between Bluetooth, Aux, and RCA inputs (model-dependent)
- 🎧 **EQ Presets**: Select equalizer presets - Flat, Bright, Warm, Voice (Stanmore II only)
- 📊 **Media Metadata**: Display track title, artist, and album information
- 🔌 **Connection Status**: Track device connectivity
- 🏷️ **Device Information**: Model, serial number, firmware, and hardware details
- 🎯 **Multi-Model Support**: Acton II, Stanmore II, and extensible for additional models

## Supported Devices

| Model | Features |
|-------|----------|
| **Acton II** | Volume, LED Brightness, Audio Source (Bluetooth/Aux), Media Controls, Media Info |
| **Stanmore II** | Volume, LED Brightness, Audio Source (Bluetooth/Aux/RCA), EQ Presets, Media Controls, Media Info |

## Installation

### HACS (Recommended)

1. Open Home Assistant and go to **Settings** → **Devices & Services** → **Custom repositories**
2. Add this repository URL: `https://github.com/elrobertocarlos/marshall_bluetooth_speaker`
3. Search for "Marshall Bluetooth Speakers" in HACS and install

### Manual Installation

1. Copy the `custom_components/marshall` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Create Integration**
4. Search for "Marshall Bluetooth Speakers" and select it

## Configuration

### Discovery

The integration will automatically discover nearby Marshall speakers via Bluetooth:

1. Go to **Settings** → **Devices & Services**
2. Look for "Discovered" section showing your Marshall speaker
3. Click "Add" to add the integration
4. Confirm the device when prompted (prevents accidental pairing)

### Manual Setup

If auto-discovery doesn't work:

1. Open **Settings** → **Devices & Services** → **Create Integration**
2. Search for "Marshall Bluetooth Speakers"
3. Select and configure (will prompt for device address)

## Entities

### Media Player
- **Play/Pause/Next/Previous**: Full playback control
- **Media Title**: Shows current track - artist (album)
- **Source Selection**: Switch between available audio inputs
- **Volume**: Adjustable via slider (0-32)

### Numbers
- **LED Brightness**: Adjustable LED brightness (0-35)

### Selectors
- **Audio Source**: Bluetooth, Aux, RCA (model-dependent)
- **EQ Preset**: Flat, Bright, Warm, Voice (Stanmore II only)

### Sensors (Diagnostic Category)
- **Device Name**: Speaker name from device
- **Model**: Device model name
- **Serial Number**: Device serial number
- **Firmware Version**: Current firmware version
- **Hardware Version**: Hardware revision
- **Volume Level**: Current volume setting (0-32)
- **Audio Source**: Currently active audio source
- **Play Status**: Current playback state (playing/paused/stopped)

### Binary Sensors (Diagnostic Category)
- **Connected**: Speaker connection status

## Usage Examples

### Toggle Playback
```yaml
service: media_player.toggle
target:
  entity_id: media_player.acton_ii
```

### Change Volume
```yaml
service: media_player.volume_set
target:
  entity_id: media_player.acton_ii
data:
  volume_level: 0.5
```

### Switch Audio Source
```yaml
service: select.select_option
target:
  entity_id: select.acton_ii_source
data:
  option: "Aux"
```

### Set EQ Preset (Stanmore II)
```yaml
service: select.select_option
target:
  entity_id: select.stanmore_ii_eq_preset
data:
  option: "Bright"
```

### Adjust LED Brightness
```yaml
service: number.set_value
target:
  entity_id: number.acton_ii_led_brightness
data:
  value: 20
```

## Troubleshooting

### Device Not Discovered
- Ensure the speaker is powered on and in Bluetooth pairing mode
- Check that your Home Assistant device has Bluetooth capability
- Try rebooting Home Assistant

### Connection Timeouts
- Move the speaker closer to your Home Assistant device
- Reduce interference from other Bluetooth devices
- Restart the speaker

### Volume/Source Not Changing
- Ensure the characteristic is writable
- Check the device is responding to commands (LED should blink)
- Verify the speaker model supports the feature

### Missing EQ Preset Select
- This is only available on Stanmore II models
- Check the device model in the entity details

## Contributing

Contributions are welcome! Please open an issue or submit a PR for:
- Additional Marshall speaker models
- Bug fixes
- Feature improvements
- Documentation updates

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with Marshall Amplification plc.

## Credits

This integration was developed by reverse-engineering the Marshall Bluetooth protocol and is built upon research and insights from:

- [rabbit-aaron/marshall-stanmore-2](https://github.com/rabbit-aaron/marshall-stanmore-2) - Protocol analysis and characteristic research for Marshall speakers

Developed for controlling Marshall speakers via BLE without requiring official apps.
