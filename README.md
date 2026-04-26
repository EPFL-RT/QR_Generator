# QR Code Generator

Generates a QR code with a centered logo overlay, used for the EPFL Racing Team website link.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python qr_gen.py
```

Place your logo as `logo.png` in the same directory. The script outputs `qr_with_logo.png`.

## Configuration

Edit `qr_gen.py` to change:
- `url` — the link encoded in the QR code
- `img` — path to the logo image
- `box_size` — size of each QR module in pixels
- `border` — quiet zone width in modules (minimum 1)
