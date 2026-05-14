# QR Code Generator

A desktop QR code generator for creating branded PNG QR codes with a live preview.

## Setup

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python qr_gen.py
```

## Build Windows EXE

Install the build dependencies and run PyInstaller from the repository root:

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller QR_Generator.spec --noconfirm --clean
```

The executable is created at:

```text
dist/QR Code Generator.exe
```

GitHub Actions also builds the executable automatically on pushes to `dev`, pull requests into `dev`, version tags matching `v*`, and manual workflow runs. Download the `QR-Code-Generator-Windows` artifact from the workflow run.

## Features

- Live desktop GUI preview
- GUI-friendly QR engine separated from the desktop interface
- Content type detection and URL normalization
- Square, rounded, and dot QR modules
- Preset-first UI with visual preset cards and optional module gradients
- Square, rounded, and circular finder eyes
- Style presets including EPFL red-eye variants
- Load and save custom style presets as JSON files
- In-app color picker with swatches, hex input, and RGB sliders
- Custom foreground, eye, gradient, and background colors with contrast guidance
- Optional centered logo with visual safety limits
- Error correction controls
- Live scan-safety score with actionable quality warnings
- Optional generated-image scan validation
- Contrast, quiet-zone, logo-size, payload-density, and PNG export-size checks
- PNG and SVG export with a file picker
- Export size presets and custom sizing
- Transparent background option
- Copy generated PNGs to the clipboard
- Open the output folder from the app

## Recommended QR Settings

- Keep the quiet zone at `4` or higher for better scanner compatibility.
- Use high color contrast between the QR modules and background.
- Use `H` error correction when adding a logo.
- Keep centered logos around `20-25%` of the QR width.
- Export PNGs large enough to keep each module at roughly `8 px` or more.
