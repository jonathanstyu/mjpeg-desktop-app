# MJPEG Desktop App

Native desktop app for working with MJPEG streams using PySide6 + OpenCV.

## Features

- Stream preview from URL
- Snapshot capture to PNG
- Timed clip recording to MP4
- Persistent output folder setting (browse/reset)
- Saved URL library with pin/unpin, rename, delete, and clear-all
- Credential-safe URL display (embedded credentials are masked in UI)

## Tech Stack

- Python 3
- PySide6
- OpenCV (`opencv-python`)

## Requirements

- Python 3.10+ recommended
- Install dependencies:

```bash
python3 -m pip install -r requirements-native.txt
```

## Run

```bash
python3 -m native_app.main
```

## Tests

```bash
python3 -m unittest discover -s native_app/tests -p 'test_*.py'
```

## Usage

1. Enter an MJPEG stream URL.
2. Click `Preview`.
3. Click `Take Snapshot` or `Record Clip`.
4. Manage saved URLs from the right-side panel.
5. Set output folder from `Session Status` (`Browse...` or `Reset`).

## Notes

- Saved URLs are capped at 20 entries.
- Pinned URLs are protected from auto-pruning.
- If all saved URLs are pinned, new URLs are not added until one is unpinned or deleted.
