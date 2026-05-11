# QR Code Generator

A desktop QR code generator for creating branded PNG QR codes with a live preview.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python qr_gen.py
```

## Features

- Live desktop GUI preview
- Rounded QR modules
- Custom foreground and background colors
- Optional centered logo
- Error correction controls
- Quiet-zone and scan-safety warnings
- PNG export with a file picker

## Recommended QR Settings

- Keep the quiet zone at `4` or higher for better scanner compatibility.
- Use high color contrast between the QR modules and background.
- Use `H` error correction when adding a logo.
- Keep centered logos around `20-25%` of the QR width.
