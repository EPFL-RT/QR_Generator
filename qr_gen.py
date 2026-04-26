import qrcode
from PIL import Image

url = "https://www.epflracingteam.ch/en"
img = "assets/logo.png"

# Create QR with high error correction
qr = qrcode.QRCode(
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=40,
    border=1,
)
qr.add_data(url)
qr.make(fit=True)

qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

# Load and resize logo
logo = Image.open(img)

qr_w, qr_h = qr_img.size
max_logo_size = int(qr_w * 0.3)  # 20% of QR width

# Resize preserving aspect ratio
orig_w, orig_h = logo.size
scale = min(max_logo_size / orig_w, max_logo_size / orig_h)
logo_w, logo_h = int(orig_w * scale), int(orig_h * scale)
logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

# Compute position (center)
pos = ((qr_w - logo_w) // 2, (qr_h - logo_h) // 2)

# Optional: add white background behind logo for contrast
bg = Image.new("RGB", (logo_w + 30, logo_h + 80), "white")
bg_pos = ((qr_w - bg.size[0]) // 2, (qr_h - bg.size[1]) // 2)
qr_img.paste(bg, bg_pos)

# Paste logo
qr_img.paste(logo, pos, mask=logo if logo.mode == "RGBA" else None)

qr_img.save("out/qr_with_logo.png")