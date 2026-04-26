# QR Code Generator

Generates a QR code with an optional centered logo overlay. All settings are controlled via a TOML config file.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Use the default config.toml
python qr_gen.py

# Use a custom config file
python qr_gen.py my_config.toml
```

Output is written to the path defined in `config.toml` (default: `out/qr_with_logo.png`). The output directory is created automatically.

## Configuration

All settings live in [config.toml](config.toml):

```toml
[qr]
url              = "https://example.com"
error_correction = "H"    # L · M · Q · H
box_size         = 40     # pixels per module
border           = 1      # quiet-zone width in modules
fill_color       = "black"
back_color       = "white"

[logo]
path             = "assets/logo.png"
max_size_ratio   = 0.30   # logo width as fraction of QR width
bg_padding_x     = 30     # white background horizontal padding (px)
bg_padding_y     = 80     # white background vertical padding (px)

[output]
path             = "out/qr_with_logo.png"
```

### Key options

| Key | Description |
|-----|-------------|
| `error_correction` | `L` 7% · `M` 15% · `Q` 25% · `H` 30% damage recovery. Higher levels allow a larger logo but reduce data density. |
| `box_size` | Pixel size of each QR module. Increase for a higher-resolution output. |
| `border` | Quiet zone around the code (min. 1). Some scanners need at least 4. |
| `max_size_ratio` | Logo size relative to QR width. Keep below ~0.30 to preserve scannability. |

### Logo-less output

Remove or comment out the `[logo]` section to generate a plain QR code without an overlay.
