import os
import sys
import qrcode
from PIL import Image

try:
    import tomllib
except ImportError:
    import tomli as tomllib

EC_LEVELS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}

config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
with open(config_path, "rb") as f:
    cfg = tomllib.load(f)

qr_cfg   = cfg["qr"]
logo_cfg = cfg.get("logo")
out_cfg  = cfg["output"]

qr = qrcode.QRCode(
    error_correction=EC_LEVELS[qr_cfg["error_correction"]],
    box_size=qr_cfg["box_size"],
    border=qr_cfg["border"],
)
qr.add_data(qr_cfg["url"])
qr.make(fit=True)

qr_img = qr.make_image(
    fill_color=qr_cfg["fill_color"],
    back_color=qr_cfg["back_color"],
).convert("RGB")

if logo_cfg and logo_cfg.get("path"):
    logo = Image.open(logo_cfg["path"])

    qr_w, qr_h = qr_img.size
    max_logo_px = int(qr_w * logo_cfg["max_size_ratio"])

    orig_w, orig_h = logo.size
    scale = min(max_logo_px / orig_w, max_logo_px / orig_h)
    logo_w, logo_h = int(orig_w * scale), int(orig_h * scale)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    pos = ((qr_w - logo_w) // 2, (qr_h - logo_h) // 2)

    bg = Image.new(
        "RGB",
        (logo_w + logo_cfg["bg_padding_x"], logo_h + logo_cfg["bg_padding_y"]),
        qr_cfg["back_color"],
    )
    bg_pos = ((qr_w - bg.size[0]) // 2, (qr_h - bg.size[1]) // 2)
    qr_img.paste(bg, bg_pos)
    qr_img.paste(logo, pos, mask=logo if logo.mode == "RGBA" else None)

out_path = out_cfg["path"]
os.makedirs(os.path.dirname(out_path), exist_ok=True)
qr_img.save(out_path)
print(f"Saved: {out_path}")
