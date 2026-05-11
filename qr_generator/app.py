from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.colorchooser import askcolor

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit("Missing dependency: run `python -m pip install -r requirements.txt` first.") from exc
from PIL import Image

from .renderer import ErrorCorrectionLevel, EyeStyle, LogoOptions, ModuleStyle, QrStyle, generate_qr


DEFAULT_OUTPUT = Path("out/qr_with_logo.png")
DEFAULT_LOGO = Path(getattr(sys, "_MEIPASS", Path.cwd())) / "assets" / "logo.png"

APP_BG = "#202020"
PANEL = "#2B2B2B"
PANEL_SOFT = "#333333"
FIELD = "#34383B"
BORDER = "#5F6870"
TEXT = "#F4F7FB"
MUTED = "#A8B0BA"
ACCENT = "#2577B2"
ACCENT_HOVER = "#1E669B"
DANGER = "#D21F3C"
DANGER_HOVER = "#B81731"
PRESET_VERSION = 1
PRESET_FILETYPES = (("QR preset", "*.qrpreset.json"), ("JSON", "*.json"), ("All files", "*.*"))

STYLE_PRESETS = {
    "Classic": {
        "fill_color": "#000000",
        "eye_color": "#000000",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.SQUARE.value,
        "eye_style": EyeStyle.SQUARE.value,
        "module_radius": 0,
    },
    "EPFL Red Eyes": {
        "fill_color": "#000000",
        "eye_color": "#D21F3C",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.SQUARE.value,
        "eye_style": EyeStyle.ROUNDED.value,
        "module_radius": 0,
    },
    "Rounded": {
        "fill_color": "#111111",
        "eye_color": "#D21F3C",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.ROUNDED.value,
        "eye_style": EyeStyle.ROUNDED.value,
        "module_radius": 35,
    },
    "Dots": {
        "fill_color": "#111111",
        "eye_color": "#D21F3C",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.DOTS.value,
        "eye_style": EyeStyle.CIRCLE.value,
        "module_radius": 50,
        "border": 4,
        "logo_size": 24,
    },
}


class QrGeneratorApp:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("QR Code Generator")
        self.root.geometry("1160x760")
        self.root.minsize(1020, 660)
        self.root.configure(fg_color=APP_BG)

        self.content = tk.StringVar(value="https://www.epflracingteam.ch/en")
        self.error_correction = tk.StringVar(value=ErrorCorrectionLevel.H.value)
        self.box_size = tk.IntVar(value=24)
        self.border = tk.IntVar(value=1)
        self.fill_color = tk.StringVar(value="#000000")
        self.back_color = tk.StringVar(value="#FFFFFF")
        self.eye_color = tk.StringVar(value="#000000")
        self.module_style = tk.StringVar(value=ModuleStyle.SQUARE.value)
        self.eye_style = tk.StringVar(value=EyeStyle.SQUARE.value)
        self.module_radius = tk.IntVar(value=0)
        self.preset_name = tk.StringVar(value="Classic")
        self.use_logo = tk.BooleanVar(value=DEFAULT_LOGO.exists())
        self.logo_path = tk.StringVar(value=str(DEFAULT_LOGO if DEFAULT_LOGO.exists() else ""))
        self.logo_size = tk.IntVar(value=30)
        self.logo_padding_x = tk.IntVar(value=30)
        self.logo_padding_y = tk.IntVar(value=80)
        self.output_path = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.status = tk.StringVar(value="Ready")

        self.preview_label: ctk.CTkLabel | None = None
        self.preview_card: ctk.CTkFrame | None = None
        self.preview_photo: ctk.CTkImage | None = None
        self.latest_image: Image.Image | None = None
        self.after_id: str | None = None
        self.color_swatches: dict[str, ctk.CTkFrame] = {}
        self.color_buttons: dict[str, ctk.CTkButton] = {}

        self._build_ui()
        self._bind_updates()
        self._schedule_preview()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(self.root, fg_color=APP_BG, corner_radius=0)
        shell.pack(fill="both", expand=True, padx=22, pady=22)
        shell.grid_columnconfigure(0, weight=0, minsize=600)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        settings_panel = ctk.CTkFrame(shell, fg_color=PANEL, corner_radius=8)
        settings_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        settings_panel.grid_columnconfigure(0, weight=1)
        settings_panel.grid_rowconfigure(1, weight=1)

        preview_panel = ctk.CTkFrame(shell, fg_color=PANEL, corner_radius=8)
        preview_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 0))
        preview_panel.grid_columnconfigure(0, weight=1)
        preview_panel.grid_rowconfigure(1, weight=1)

        self._build_settings_panel(settings_panel)
        self._build_preview_panel(preview_panel)

    def _build_settings_panel(self, panel: ctk.CTkFrame) -> None:
        title_bar = ctk.CTkFrame(panel, fg_color=PANEL_SOFT, corner_radius=8, height=42)
        title_bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 12))
        title_bar.grid_propagate(False)
        title_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title_bar, text="Settings", font=("Segoe UI Semibold", 18), text_color=TEXT).grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scroll = ctk.CTkScrollableFrame(panel, fg_color=PANEL, scrollbar_button_color="#737373")
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)

        self._build_qr_section(scroll)
        self._build_logo_section(scroll)
        self._build_export_section(scroll)

    def _build_preview_panel(self, panel: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(panel, fg_color=PANEL, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Preview", font=("Segoe UI Semibold", 20), text_color=TEXT).grid(
            row=0,
            column=0,
            sticky="w",
        )

        status = ctk.CTkLabel(
            header,
            textvariable=self.status,
            font=("Segoe UI", 13),
            text_color=MUTED,
            anchor="e",
        )
        status.grid(row=0, column=1, sticky="e")

        preview_outer = ctk.CTkFrame(panel, fg_color=PANEL, corner_radius=0)
        preview_outer.grid(row=1, column=0, sticky="nsew", padx=22, pady=(8, 22))
        preview_outer.grid_columnconfigure(0, weight=1)
        preview_outer.grid_rowconfigure(0, weight=1)

        self.preview_card = ctk.CTkFrame(preview_outer, fg_color="#242424", corner_radius=10)
        self.preview_card.grid(row=0, column=0, sticky="nsew")
        self.preview_card.grid_columnconfigure(0, weight=1)
        self.preview_card.grid_rowconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(
            self.preview_card,
            text="No preview yet",
            font=("Segoe UI", 16),
            text_color=TEXT,
            fg_color="#242424",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)

    def _build_qr_section(self, parent: ctk.CTkFrame) -> None:
        self._section_title(parent, "QR Code").pack(anchor="w", padx=8, pady=(24, 12))
        self._entry_row(parent, "URL", self.content)
        self._option_row(parent, "Preset", self.preset_name, list(STYLE_PRESETS), self._apply_preset)
        self._preset_actions(parent)
        self._option_row(parent, "Error Correction", self.error_correction, [level.value for level in ErrorCorrectionLevel])
        self._option_row(parent, "Module Style", self.module_style, [style.value for style in ModuleStyle])
        self._option_row(parent, "Eye Style", self.eye_style, [style.value for style in EyeStyle])
        self._number_row(parent, "Box Size", self.box_size, 8, 64)
        self._number_row(parent, "Border", self.border, 1, 8)
        self._color_row(parent, "Fill Color", self.fill_color, "fill")
        self._color_row(parent, "Eye Color", self.eye_color, "eye")
        self._color_row(parent, "Background", self.back_color, "back")
        self._number_row(parent, "Roundness", self.module_radius, 0, 50)

    def _build_logo_section(self, parent: ctk.CTkFrame) -> None:
        self._section_title(parent, "Logo  (optional)").pack(anchor="w", padx=8, pady=(24, 12))
        ctk.CTkCheckBox(
            parent,
            text="Use centered logo",
            variable=self.use_logo,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=TEXT,
            font=("Segoe UI", 14),
        ).pack(anchor="w", padx=8, pady=(0, 10))
        self._file_row(parent, "Logo Path", self.logo_path, self._choose_logo)
        self._number_row(parent, "Max Size Ratio", self.logo_size, 10, 30, display=lambda value: f"{value / 100:.2f}")
        self._number_row(parent, "BG Padding X", self.logo_padding_x, 0, 160)
        self._number_row(parent, "BG Padding Y", self.logo_padding_y, 0, 200)

    def _build_export_section(self, parent: ctk.CTkFrame) -> None:
        self._section_title(parent, "Export").pack(anchor="w", padx=8, pady=(24, 12))
        self._file_row(parent, "Output Path", self.output_path, self._choose_output)
        ctk.CTkButton(
            parent,
            text="Export PNG",
            command=self._export,
            fg_color=DANGER,
            hover_color=DANGER_HOVER,
            height=46,
            corner_radius=8,
            font=("Segoe UI Semibold", 15),
            text_color="#FFFFFF",
        ).pack(fill="x", padx=8, pady=(12, 18))

    def _section_title(self, parent: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=("Segoe UI Semibold", 17), text_color=TEXT)

    def _row(self, parent: ctk.CTkFrame, label: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        row = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=0)
        row.pack(fill="x", padx=8, pady=5)
        row.grid_columnconfigure(0, weight=0, minsize=150)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=label, font=("Segoe UI", 15), text_color=TEXT, anchor="w").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=2,
        )
        control = ctk.CTkFrame(row, fg_color=PANEL, corner_radius=0)
        control.grid(row=0, column=1, sticky="ew")
        control.grid_columnconfigure(0, weight=1)
        return row, control

    def _entry_row(self, parent: ctk.CTkFrame, label: str, variable: tk.StringVar) -> None:
        _, control = self._row(parent, label)
        ctk.CTkEntry(
            control,
            textvariable=variable,
            height=40,
            fg_color=FIELD,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=8,
        ).grid(row=0, column=0, sticky="ew")

    def _file_row(self, parent: ctk.CTkFrame, label: str, variable: tk.StringVar, command: Callable[[], None]) -> None:
        _, control = self._row(parent, label)
        control.grid_columnconfigure(0, weight=1)
        control.grid_columnconfigure(1, weight=0)
        ctk.CTkEntry(
            control,
            textvariable=variable,
            height=40,
            fg_color=FIELD,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=8,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            control,
            text="...",
            command=command,
            width=48,
            height=40,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            corner_radius=8,
            font=("Segoe UI Semibold", 15),
        ).grid(row=0, column=1, sticky="e")

    def _preset_actions(self, parent: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=0)
        row.pack(fill="x", padx=8, pady=(0, 10))
        row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            row,
            text="Load Preset",
            command=self._load_preset_file,
            height=38,
            fg_color=FIELD,
            hover_color="#3F4549",
            border_color=BORDER,
            border_width=1,
            corner_radius=8,
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            row,
            text="Save Preset",
            command=self._save_preset_file,
            height=38,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            corner_radius=8,
            text_color=TEXT,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _option_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        command: Callable[[str], None] | None = None,
    ) -> None:
        _, control = self._row(parent, label)
        ctk.CTkOptionMenu(
            control,
            variable=variable,
            values=values,
            command=command,
            height=40,
            width=120,
            fg_color=ACCENT,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            dropdown_fg_color=FIELD,
            dropdown_hover_color=ACCENT,
            dropdown_text_color=TEXT,
            corner_radius=8,
            font=("Segoe UI", 15),
        ).grid(row=0, column=0, sticky="w")

    def _number_row(
        self,
        parent: ctk.CTkFrame,
        label: str,
        variable: tk.IntVar,
        minimum: int,
        maximum: int,
        display: Callable[[int], str] | None = None,
    ) -> None:
        _, control = self._row(parent, label)
        control.grid_columnconfigure(0, weight=1)
        value = tk.StringVar()

        def sync_value(*_: object) -> None:
            current = variable.get()
            value.set(display(current) if display else str(current))

        sync_value()
        variable.trace_add("write", sync_value)

        entry = ctk.CTkEntry(
            control,
            textvariable=value,
            height=40,
            fg_color=FIELD,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=8,
        )
        entry.grid(row=0, column=0, sticky="ew")

        slider = ctk.CTkSlider(
            control,
            from_=minimum,
            to=maximum,
            number_of_steps=maximum - minimum,
            variable=variable,
            fg_color="#4A4F54",
            progress_color=ACCENT,
            button_color="#D7E8F6",
            button_hover_color="#FFFFFF",
            height=18,
            command=lambda raw: variable.set(round(float(raw))),
        )
        slider.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        def commit_entry(_: object | None = None) -> None:
            raw = value.get().strip()
            try:
                parsed = float(raw)
            except ValueError:
                sync_value()
                return
            if display:
                parsed *= 100
            variable.set(max(minimum, min(maximum, round(parsed))))

        entry.bind("<Return>", commit_entry)
        entry.bind("<FocusOut>", commit_entry)

    def _color_row(self, parent: ctk.CTkFrame, label: str, variable: tk.StringVar, key: str) -> None:
        _, control = self._row(parent, label)
        control.grid_columnconfigure(0, weight=1)
        self.color_swatches[key] = ctk.CTkFrame(control, width=40, height=40, fg_color=variable.get(), corner_radius=8)
        self.color_swatches[key].grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.color_swatches[key].grid_propagate(False)
        button = ctk.CTkButton(
            control,
            text=variable.get(),
            command=lambda: self._pick_color(variable),
            height=40,
            fg_color=FIELD,
            hover_color="#3F4549",
            border_color=BORDER,
            border_width=1,
            corner_radius=8,
            text_color=TEXT,
            anchor="w",
        )
        button.grid(row=0, column=0, sticky="ew", padx=(52, 0))
        self.color_buttons[key] = button

    def _bind_updates(self) -> None:
        variables = (
            self.content,
            self.error_correction,
            self.box_size,
            self.border,
            self.fill_color,
            self.back_color,
            self.eye_color,
            self.module_style,
            self.eye_style,
            self.module_radius,
            self.use_logo,
            self.logo_path,
            self.logo_size,
            self.logo_padding_x,
            self.logo_padding_y,
        )
        for variable in variables:
            variable.trace_add("write", lambda *_: self._schedule_preview())

        self.fill_color.trace_add("write", lambda *_: self._paint_swatch("fill", self.fill_color.get()))
        self.eye_color.trace_add("write", lambda *_: self._paint_swatch("eye", self.eye_color.get()))
        self.back_color.trace_add("write", lambda *_: self._paint_swatch("back", self.back_color.get()))

        if self.preview_card:
            self.preview_card.bind("<Configure>", lambda _: self._schedule_preview())

    def _schedule_preview(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(120, self._render_preview)

    def _render_preview(self) -> None:
        self.after_id = None
        try:
            result = generate_qr(self._style(), self._logo())
        except Exception as exc:
            self.latest_image = None
            self.status.set(str(exc))
            return

        self.latest_image = result.image
        self._draw_preview(result.image)

        errors = [item.text for item in result.validation if item.level == "error"]
        warnings = [item.text for item in result.validation if item.level == "warning"]
        if errors:
            self.status.set(errors[0])
        elif warnings:
            self.status.set(warnings[0])
        else:
            self.status.set("Looks good for export.")

    def _draw_preview(self, image: Image.Image) -> None:
        if self.preview_label is None or self.preview_card is None:
            return

        card_w = max(320, self.preview_card.winfo_width())
        card_h = max(320, self.preview_card.winfo_height())
        preview = image.copy()
        preview.thumbnail((card_w - 96, card_h - 96), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (preview.width + 44, preview.height + 44), (255, 255, 255, 255))
        canvas.alpha_composite(preview.convert("RGBA"), (22, 22))
        canvas_rgb = canvas.convert("RGB")
        self.preview_photo = ctk.CTkImage(light_image=canvas_rgb, dark_image=canvas_rgb, size=canvas_rgb.size)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _style(self) -> QrStyle:
        return QrStyle(
            content=self.content.get(),
            error_correction=ErrorCorrectionLevel(self.error_correction.get()),
            box_size=self.box_size.get(),
            border=self.border.get(),
            fill_color=self.fill_color.get(),
            back_color=self.back_color.get(),
            eye_color=self.eye_color.get(),
            module_style=ModuleStyle(self.module_style.get()),
            eye_style=EyeStyle(self.eye_style.get()),
            module_radius=self.module_radius.get() / 100,
        )

    def _logo(self) -> LogoOptions | None:
        if not self.use_logo.get() or not self.logo_path.get().strip():
            return None
        return LogoOptions(
            path=Path(self.logo_path.get().strip()),
            max_size_ratio=self.logo_size.get() / 100,
            bg_padding_x=self.logo_padding_x.get(),
            bg_padding_y=self.logo_padding_y.get(),
        )

    def _paint_swatch(self, key: str, color: str) -> None:
        swatch = self.color_swatches.get(key)
        if swatch is not None:
            swatch.configure(fg_color=color)
        button = self.color_buttons.get(key)
        if button is not None:
            button.configure(text=color)

    def _apply_preset(self, name: str) -> None:
        preset = STYLE_PRESETS.get(name)
        if not preset:
            return

        self.fill_color.set(str(preset["fill_color"]))
        self.eye_color.set(str(preset["eye_color"]))
        self.back_color.set(str(preset["back_color"]))
        self.module_style.set(str(preset["module_style"]))
        self.eye_style.set(str(preset["eye_style"]))
        self.module_radius.set(int(preset["module_radius"]))

        if "border" in preset:
            self.border.set(int(preset["border"]))
        if "logo_size" in preset:
            self.logo_size.set(int(preset["logo_size"]))

    def _save_preset_file(self) -> None:
        initial_name = _preset_filename(self.preset_name.get())
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save QR preset",
            defaultextension=".qrpreset.json",
            filetypes=PRESET_FILETYPES,
            initialfile=initial_name,
        )
        if not path:
            return

        try:
            Path(path).write_text(json.dumps(self._preset_data(), indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save preset", str(exc), parent=self.root)
            return

        self.status.set(f"Saved preset {Path(path).name}")

    def _load_preset_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load QR preset",
            filetypes=PRESET_FILETYPES,
        )
        if not path:
            return

        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            self._apply_preset_data(raw)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("Could not load preset", str(exc), parent=self.root)
            return

        self.status.set(f"Loaded preset {Path(path).name}")

    def _preset_data(self) -> dict[str, object]:
        return {
            "schema": "qr-generator-preset",
            "version": PRESET_VERSION,
            "name": self.preset_name.get() or "Custom",
            "settings": {
                "error_correction": self.error_correction.get(),
                "box_size": self.box_size.get(),
                "border": self.border.get(),
                "fill_color": self.fill_color.get(),
                "eye_color": self.eye_color.get(),
                "back_color": self.back_color.get(),
                "module_style": self.module_style.get(),
                "eye_style": self.eye_style.get(),
                "module_radius": self.module_radius.get(),
                "use_logo": self.use_logo.get(),
                "logo_path": self._serializable_logo_path(),
                "logo_size": self.logo_size.get(),
                "logo_padding_x": self.logo_padding_x.get(),
                "logo_padding_y": self.logo_padding_y.get(),
            },
        }

    def _apply_preset_data(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            raise ValueError("Preset file must contain a JSON object.")

        settings = raw.get("settings", raw)
        if not isinstance(settings, dict):
            raise ValueError("Preset file is missing a settings object.")

        name = raw.get("name")
        self.preset_name.set(str(name) if name else "Custom")
        self.error_correction.set(_choice(settings, "error_correction", ErrorCorrectionLevel, self.error_correction.get()))
        self.box_size.set(_int_between(settings, "box_size", 8, 64, self.box_size.get()))
        self.border.set(_int_between(settings, "border", 1, 8, self.border.get()))
        self.fill_color.set(_string(settings, "fill_color", self.fill_color.get()))
        self.eye_color.set(_string(settings, "eye_color", self.eye_color.get()))
        self.back_color.set(_string(settings, "back_color", self.back_color.get()))
        self.module_style.set(_choice(settings, "module_style", ModuleStyle, self.module_style.get()))
        self.eye_style.set(_choice(settings, "eye_style", EyeStyle, self.eye_style.get()))
        self.module_radius.set(_int_between(settings, "module_radius", 0, 50, self.module_radius.get()))
        self.use_logo.set(_bool(settings, "use_logo", self.use_logo.get()))
        self.logo_path.set(self._deserialized_logo_path(_string(settings, "logo_path", self.logo_path.get())))
        self.logo_size.set(_int_between(settings, "logo_size", 10, 30, self.logo_size.get()))
        self.logo_padding_x.set(_int_between(settings, "logo_padding_x", 0, 160, self.logo_padding_x.get()))
        self.logo_padding_y.set(_int_between(settings, "logo_padding_y", 0, 200, self.logo_padding_y.get()))

    def _serializable_logo_path(self) -> str:
        raw_path = self.logo_path.get().strip()
        if not raw_path:
            return ""

        current = Path(raw_path)
        try:
            if current.resolve() == DEFAULT_LOGO.resolve():
                return "__bundled_logo__"
        except OSError:
            pass
        return str(current)

    def _deserialized_logo_path(self, value: str) -> str:
        if value == "__bundled_logo__":
            return str(DEFAULT_LOGO)
        return value

    def _pick_color(self, variable: tk.StringVar) -> None:
        _, hex_color = askcolor(color=variable.get(), parent=self.root)
        if hex_color:
            variable.set(hex_color)

    def _choose_logo(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose logo",
            filetypes=(("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")),
        )
        if path:
            self.logo_path.set(path)
            self.use_logo.set(True)

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export QR code",
            defaultextension=".png",
            filetypes=(("PNG image", "*.png"),),
            initialfile="qr_code.png",
        )
        if path:
            self.output_path.set(path)

    def _export(self) -> None:
        result = generate_qr(self._style(), self._logo())
        errors = [item.text for item in result.validation if item.level == "error"]
        if errors:
            messagebox.showerror("Cannot export", errors[0], parent=self.root)
            return

        out_path = Path(self.output_path.get().strip() or DEFAULT_OUTPUT)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result.image.save(out_path)
        self.status.set(f"Saved {out_path}")


def main() -> None:
    app = QrGeneratorApp()
    app.run()


def _preset_filename(name: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in name.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return f"{safe or 'qr-preset'}.qrpreset.json"


def _string(settings: dict[Any, Any], key: str, default: str) -> str:
    value = settings.get(key, default)
    if value is None:
        return ""
    return str(value)


def _bool(settings: dict[Any, Any], key: str, default: bool) -> bool:
    value = settings.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"Preset value for {key} must be true or false.")


def _int_between(settings: dict[Any, Any], key: str, minimum: int, maximum: int, default: int) -> int:
    value = settings.get(key, default)
    try:
        parsed = round(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Preset value for {key} must be a number.") from exc
    return max(minimum, min(maximum, parsed))


def _choice(settings: dict[Any, Any], key: str, enum_class: Any, default: str) -> str:
    value = str(settings.get(key, default))
    allowed = {item.value for item in enum_class}
    if value not in allowed:
        raise ValueError(f"Preset value for {key} must be one of: {', '.join(sorted(allowed))}.")
    return value
