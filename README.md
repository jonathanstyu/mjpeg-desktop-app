# MJPEG Desktop App

Desktop Electron app for working with MJPEG camera streams.  
It lets you:

- Preview a stream URL in-app.
- Capture a single snapshot frame (`.png`).
- Record a short 5-second clip (`.mp4`).
- Save and reuse recent stream URLs from local storage.

This repo now also includes an in-progress all-Python shell (`PySide6`) that reuses
the same Python camera logic.

## How It Works

- Electron renders the UI (`index.html`, `renderer.js`, `styles.css`).
- The renderer launches Python scripts via `python-shell`.
- Python wrappers call shared camera services:
  - `python/camera_still.py` -> `native_app/services/camera_service.py`
  - `python/camera_record.py` -> `native_app/services/camera_service.py`

## Tech Stack

- Electron (desktop shell)
- Node.js (app runtime)
- Python + OpenCV (media capture)
- PySide6 (native shell migration target)

## Requirements

- Node.js 18+
- Python 3 available in your environment
- OpenCV for Python (`cv2`)

## Run Locally

```bash
npm install
npm start
```

## Run Native Python Shell (Migration Preview)

```bash
python3 -m pip install -r requirements-native.txt
python3 -m native_app.main
```

The native shell currently includes:

- URL entry and saved URL history
- Preview loading (single-frame fetch from stream)
- Snapshot capture
- Timed clip recording with countdown and status updates

## Usage

1. Enter an MJPEG stream URL.
2. Click `Preview` to load the stream.
3. Click `Take Snapshot` to save a PNG image.
4. Click `Record 5 Seconds` to save a short MP4 clip.

## Output Files

Current Python scripts write files one level above the repo directory:

- Snapshot: `../frame--YY-MM-DD-HH-MM.png`
- Recording: `../output--YY-MM-DD-HH-MM.mp4`

## Notes

- Saved URLs are stored in browser local storage (up to 20 entries).
- Window defaults to a desktop layout and supports responsive behavior for smaller screens.
