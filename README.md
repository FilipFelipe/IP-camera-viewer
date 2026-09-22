# IP Camera Viewer

A lightweight desktop app for monitoring multiple IP cameras over RTSP in a grid layout.

## Features

- Multi-camera layout with pagination
- Fullscreen view for a single camera on double-click
- Keyboard navigation with left/right arrow keys
- Automatic fallback to a secondary stream when the primary one fails
- Automatic reconnection logic
- Separate camera configuration in `cameras.json`
- Built with Python, PySide6, and VLC

## Supported behavior

The app tries to open the camera stream using `subtype=0` first. If the primary stream fails or stops, it automatically retries using `subtype=1` and later attempts to return to the primary stream after a recovery interval.

## Requirements

- Python 3.10+
- VLC installed on the machine
- PySide6 and python-vlc from `requirements.txt`

## macOS setup

### 1. Install VLC

Install the VLC app for macOS. The Python environment must be able to locate the VLC library.

Check the library path:

```bash
ls /Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib
```

### 2. Create a virtual environment

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the cameras

Edit `cameras.json` and replace the example URLs with your real RTSP sources.

Example:

```json
{
  "cameras": [
    {
      "name": "Camera 1",
      "url": "rtsp://admin:YOUR_PASSWORD@192.168.0.100:554/cam/realmonitor?channel=1&subtype=0"
    }
  ]
}
```

The app will automatically replace `subtype=0` with `subtype=1` when the main stream fails.

### 4. Run the app

You can run it directly with Python:

```bash
python main.py
```

Or use the platform-specific launcher:

```bash
./run-mac.sh
```

```bash
./run-linux.sh
```

```bat
run-windows.bat
```

Or in PowerShell:

```powershell
./run-windows.ps1
```

## Controls

- Double-click a camera: open it in fullscreen
- `Esc`: return to the grid view
- Left/right arrow keys: move between pages
- Close the window: exit the application

## Notes

This project is designed to be portable and can also be adapted for a Raspberry Pi or similar low-power devices, but performance depends on camera resolution, codec, bitrate, and available CPU power.

If the device struggles with multiple simultaneous streams, the quickest adjustment is usually to use `subtype=1` directly, since it often points to a lower-resolution or lower-bitrate stream.

It may also be necessary to use a VLC/PySide build compatible with the target ARMv7 or OS environment.

## Screenshots

### Grid view

![Grid view](docs/screenshots/grid-view.png)

### Fallback / connection status

![Fallback view](docs/screenshots/fallback-view.png)

## Contributing

Contributions are welcome.

1. Fork the project.
2. Create a branch for your change.
3. Make your improvements and keep the code clean.
4. Run a quick validation for the affected area.
5. Open a pull request with a clear description of the change.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
