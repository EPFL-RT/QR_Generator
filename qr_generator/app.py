from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit("Missing dependency: run `python -m pip install -r requirements.txt` first.") from exc
from PIL import Image, ImageColor

from .renderer import (
    ErrorCorrectionLevel,
    EyeStyle,
    LogoOptions,
    ModuleStyle,
    QrStyle,
    ScanQualityReport,
    generate_qr,
    generate_qr_svg,
)


DEFAULT_OUTPUT = Path("out/qr_with_logo.png")
DEFAULT_LOGO = Path(getattr(sys, "_MEIPASS", Path.cwd())) / "assets" / "logo.png"
OUTPUT_SIZE_PRESETS = ("Original", "512", "1024", "2048", "4096", "Custom")
EXPORT_FORMATS = ("PNG", "SVG")
APP_SETTINGS_PATH = Path(os.getenv("APPDATA", Path.home())) / "QR Code Generator" / "settings.json"

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
SUCCESS = "#00A86B"
WARNING = "#FFB000"
PRESET_VERSION = 1
PRESET_FILETYPES = (("QR preset", "*.qrpreset.json"), ("JSON", "*.json"), ("All files", "*.*"))
PNG_FILETYPES = (("PNG image", "*.png"),)
SVG_FILETYPES = (("SVG image", "*.svg"),)
QUALITY_COLORS = {
    "Excellent": SUCCESS,
    "Good": WARNING,
    "Risky": DANGER,
}
COLOR_SWATCHES = (
    "#000000",
    "#FFFFFF",
    "#D21F3C",
    "#2577B2",
    "#111111",
    "#34383B",
    "#5F6870",
    "#F4F7FB",
    "#E10600",
    "#00A3E0",
    "#00B050",
    "#FFB000",
)

STYLE_PRESETS = {
    "Classic": {
        "fill_color": "#000000",
        "eye_color": "#000000",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.SQUARE.value,
        "eye_style": EyeStyle.SQUARE.value,
        "module_radius": 0,
        "border": 4,
        "logo_size": 25,
    },
    "EPFL Red Eyes": {
        "fill_color": "#000000",
        "eye_color": "#D21F3C",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.SQUARE.value,
        "eye_style": EyeStyle.ROUNDED.value,
        "module_radius": 0,
        "border": 4,
        "logo_size": 25,
    },
    "Rounded": {
        "fill_color": "#111111",
        "eye_color": "#D21F3C",
        "back_color": "#FFFFFF",
        "module_style": ModuleStyle.ROUNDED.value,
        "eye_style": EyeStyle.ROUNDED.value,
        "module_radius": 35,
        "border": 4,
        "logo_size": 25,
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


class ColorPickerDialog:
    def __init__(self, parent: ctk.CTk, initial_color: str) -> None:
        self.parent = parent
        self.result: str | None = None

        color = _normalize_hex_color(initial_color)
        red, green, blue = _hex_to_rgb(color)

        self.hex_value = tk.StringVar(value=color)
        self.red = tk.IntVar(value=red)
        self.green = tk.IntVar(value=green)
        self.blue = tk.IntVar(value=blue)
        self.error = tk.StringVar(value="")

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Choose Color")
        self.window.configure(fg_color=APP_BG)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Escape>", lambda _: self._cancel())

        self._build_ui()
        self._position()

    def show(self) -> str | None:
        self.window.wait_window()
        return self.result

    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(self.window, fg_color=PANEL, corner_radius=10)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(shell, text="Choose color", font=("Segoe UI Semibold", 18), text_color=TEXT).grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(18, 12),
        )

        preview_row = ctk.CTkFrame(shell, fg_color=PANEL, corner_radius=0)
        preview_row.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
        preview_row.grid_columnconfigure(1, weight=1)

        self.preview = ctk.CTkFrame(preview_row, width=64, height=64, fg_color=self.hex_value.get(), corner_radius=10)
        self.preview.grid(row=0, column=0, sticky="w", padx=(0, 14))
        self.preview.grid_propagate(False)

        ctk.CTkEntry(
            preview_row,
            textvariable=self.hex_value,
            height=42,
            fg_color=FIELD,
            border_color=BORDER,
            text_color=TEXT,
            corner_radius=8,
            font=("Segoe UI Semibold", 15),
        ).grid(row=0, column=1, sticky="ew")

        swatches = ctk.CTkFrame(shell, fg_color=PANEL, corner_radius=0)
        swatches.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        for index, color in enumerate(COLOR_SWATCHES):
            swatch = ctk.CTkButton(
                swatches,
                text="",
                width=34,
                height=34,
                fg_color=color,
                hover_color=color,
                border_color=BORDER,
                border_width=1,
                corner_radius=8,
                command=lambda chosen=color: self._set_color(chosen),
            )
            swatch.grid(row=index // 6, column=index % 6, padx=4, pady=4)

        self._channel_slider(shell, "R", self.red, 3)
        self._channel_slider(shell, "G", self.green, 4)
        self._channel_slider(shell, "B", self.blue, 5)

        ctk.CTkLabel(shell, textvariable=self.error, text_color="#FF9BA7", font=("Segoe UI", 12)).grid(
            row=6,
            column=0,
            sticky="w",
            padx=18,
            pady=(0, 6),
        )

        actions = ctk.CTkFrame(shell, fg_color=PANEL, corner_radius=0)
        actions.grid(row=7, column=0, sticky="ew", padx=18, pady=(4, 18))
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            actions,
            text="Cancel",
            command=self._cancel,
            height=40,
            fg_color=FIELD,
            hover_color="#3F4549",
            border_color=BORDER,
            border_width=1,
            corner_radius=8,
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            actions,
            text="Apply",
            command=self._apply,
            height=40,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            corner_radius=8,
            text_color=TEXT,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _channel_slider(self, parent: ctk.CTkFrame, label: str, variable: tk.IntVar, row: int) -> None:
        frame = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=0)
        frame.grid(row=row, column=0, sticky="ew", padx=18, pady=5)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=label, text_color=MUTED, width=18, font=("Segoe UI Semibold", 13)).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
        )
        ctk.CTkSlider(
            frame,
            from_=0,
            to=255,
            number_of_steps=255,
            variable=variable,
            fg_color="#4A4F54",
            progress_color=ACCENT,
            button_color="#D7E8F6",
            button_hover_color="#FFFFFF",
            command=lambda raw, channel=variable: self._set_channel(channel, raw),
        ).grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(frame, textvariable=variable, text_color=TEXT, width=34, font=("Segoe UI", 13)).grid(
            row=0,
            column=2,
            sticky="e",
            padx=(10, 0),
        )

    def _position(self) -> None:
        self.window.update_idletasks()
        x = self.parent.winfo_rootx() + max(0, (self.parent.winfo_width() - self.window.winfo_width()) // 2)
        y = self.parent.winfo_rooty() + max(0, (self.parent.winfo_height() - self.window.winfo_height()) // 2)
        self.window.geometry(f"+{x}+{y}")
        self.window.focus_force()

    def _set_channel(self, variable: tk.IntVar, raw: float) -> None:
        variable.set(round(float(raw)))
        self._update_from_rgb()

    def _update_from_rgb(self) -> None:
        self._set_color(_rgb_to_hex(self.red.get(), self.green.get(), self.blue.get()))

    def _set_color(self, color: str) -> None:
        normalized = _normalize_hex_color(color, self.hex_value.get())
        red, green, blue = _hex_to_rgb(normalized)
        self.red.set(red)
        self.green.set(green)
        self.blue.set(blue)
        self.hex_value.set(normalized)
        self.preview.configure(fg_color=normalized)
        self.error.set("")

    def _apply(self) -> None:
        raw = self.hex_value.get().strip()
        if not _is_hex_color(raw):
            self.error.set("Use a valid hex color, for example #D21F3C.")
            return

        self.result = _normalize_hex_color(raw)
        self.window.destroy()

    def _cancel(self) -> None:
        self.window.destroy()


class QrGeneratorApp:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.app_settings = _load_app_settings()

        self.root = ctk.CTk()
        self.root.title("QR Code Generator")
        self.root.geometry("1160x760")
        self.root.minsize(1020, 660)
        self.root.configure(fg_color=APP_BG)

        self.content = tk.StringVar(value="https://www.epflracingteam.ch/en")
        self.error_correction = tk.StringVar(value=ErrorCorrectionLevel.H.value)
        self.box_size = tk.IntVar(value=24)
        self.border = tk.IntVar(value=4)
        self.fill_color = tk.StringVar(value="#000000")
        self.back_color = tk.StringVar(value="#FFFFFF")
        self.eye_color = tk.StringVar(value="#000000")
        self.module_style = tk.StringVar(value=ModuleStyle.SQUARE.value)
        self.eye_style = tk.StringVar(value=EyeStyle.SQUARE.value)
        self.module_radius = tk.IntVar(value=0)
        self.preset_name = tk.StringVar(value="Classic")
        self.use_logo = tk.BooleanVar(value=DEFAULT_LOGO.exists())
        self.logo_path = tk.StringVar(value=str(DEFAULT_LOGO if DEFAULT_LOGO.exists() else ""))
        self.logo_size = tk.IntVar(value=25)
        self.logo_padding_x = tk.IntVar(value=30)
        self.logo_padding_y = tk.IntVar(value=80)
        self.export_format = tk.StringVar(value=_settings_choice(self.app_settings, "export_format", EXPORT_FORMATS, "PNG"))
        self.output_size = tk.StringVar(value=_settings_choice(self.app_settings, "output_size", OUTPUT_SIZE_PRESETS, "Original"))
        self.custom_output_size = tk.IntVar(value=_settings_int(self.app_settings, "custom_output_size", 256, 8192, 1024))
        self.transparent_background = tk.BooleanVar(value=bool(self.app_settings.get("transparent_background", False)))
        self.output_path = tk.StringVar(value=str(self.app_settings.get("last_output_path") or DEFAULT_OUTPUT))
        self.status = tk.StringVar(value="Ready")

        self.preview_label: ctk.CTkLabel | None = None
        self.preview_card: ctk.CTkFrame | None = None
        self.preview_photo: ctk.CTkImage | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.quality_badge: ctk.CTkLabel | None = None
        self.quality_title: ctk.CTkLabel | None = None
        self.quality_details: ctk.CTkLabel | None = None
        self.latest_image: Image.Image | None = None
        self.after_id: str | None = None
        self.color_swatches: dict[str, ctk.CTkFrame] = {}
        self.color_buttons: dict[str, ctk.CTkButton] = {}
        self.export_button: ctk.CTkButton | None = None
        self.syncing_logo_error_correction = False

        self._build_ui()
        self._bind_updates()
        self._sync_output_extension()
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

        self.quality_badge = ctk.CTkLabel(
            header,
            text="Ready",
            font=("Segoe UI Semibold", 13),
            text_color=TEXT,
            fg_color=FIELD,
            corner_radius=14,
            padx=12,
            pady=4,
        )
        self.quality_badge.grid(row=0, column=1, sticky="e", padx=(14, 0))

        self.status_label = ctk.CTkLabel(
            header,
            textvariable=self.status,
            font=("Segoe UI", 13),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))

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

        quality_panel = ctk.CTkFrame(panel, fg_color="#242424", corner_radius=8)
        quality_panel.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 22))
        quality_panel.grid_columnconfigure(0, weight=1)

        self.quality_title = ctk.CTkLabel(
            quality_panel,
            text="Scan safety",
            font=("Segoe UI Semibold", 15),
            text_color=TEXT,
            anchor="w",
        )
        self.quality_title.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 2))

        self.quality_details = ctk.CTkLabel(
            quality_panel,
            text="Waiting for preview.",
            font=("Segoe UI", 13),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=520,
        )
        self.quality_details.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))

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
        self._option_row(parent, "Format", self.export_format, list(EXPORT_FORMATS), self._on_export_format_change)
        self._option_row(parent, "Size", self.output_size, list(OUTPUT_SIZE_PRESETS))
        self._number_row(parent, "Custom Size", self.custom_output_size, 256, 8192)
        ctk.CTkCheckBox(
            parent,
            text="Transparent background",
            variable=self.transparent_background,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            border_color=BORDER,
            text_color=TEXT,
            font=("Segoe UI", 14),
        ).pack(anchor="w", padx=8, pady=(5, 10))
        self._file_row(parent, "Output Path", self.output_path, self._choose_output)
        self.export_button = ctk.CTkButton(
            parent,
            text="Export PNG",
            command=self._export,
            fg_color=DANGER,
            hover_color=DANGER_HOVER,
            height=46,
            corner_radius=8,
            font=("Segoe UI Semibold", 15),
            text_color="#FFFFFF",
        )
        self.export_button.pack(fill="x", padx=8, pady=(12, 10))
        self._export_actions(parent)

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

    def _export_actions(self, parent: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=0)
        row.pack(fill="x", padx=8, pady=(0, 18))
        row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            row,
            text="Copy PNG",
            command=self._copy_png,
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
            text="Open Folder",
            command=self._open_output_folder,
            height=38,
            fg_color=FIELD,
            hover_color="#3F4549",
            border_color=BORDER,
            border_width=1,
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
        if self.preview_label:
            self.preview_label.bind("<Configure>", lambda _: self._schedule_preview())

        self.use_logo.trace_add("write", lambda *_: self._ensure_logo_error_correction())
        self.logo_path.trace_add("write", lambda *_: self._ensure_logo_error_correction())

        self.export_format.trace_add("write", lambda *_: self._schedule_preview())
        self.output_size.trace_add("write", lambda *_: self._schedule_preview())
        self.custom_output_size.trace_add("write", lambda *_: self._schedule_preview())
        self.output_size.trace_add("write", lambda *_: self._save_app_settings())
        self.custom_output_size.trace_add("write", lambda *_: self._save_app_settings())
        self.transparent_background.trace_add("write", lambda *_: self._save_app_settings())

    def _schedule_preview(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(120, self._render_preview)

    def _render_preview(self) -> None:
        self.after_id = None
        try:
            result = generate_qr(self._style(), self._logo(), output_size=self._quality_output_size())
        except Exception as exc:
            self.latest_image = None
            self.status.set(str(exc))
            return

        self.latest_image = result.image
        self._draw_preview(result.image)
        self._update_quality(result.quality)

    def _draw_preview(self, image: Image.Image) -> None:
        if self.preview_label is None or self.preview_card is None:
            return

        viewport_w = self.preview_label.winfo_width()
        viewport_h = self.preview_label.winfo_height()
        if viewport_w <= 80 or viewport_h <= 80:
            self.root.after(80, lambda: self._draw_preview(image))
            return

        canvas_limit = max(96, int(min(viewport_w, viewport_h) * 0.84))
        padding = max(10, min(18, canvas_limit // 14))
        preview_limit = max(64, canvas_limit - padding * 2)

        preview = image.copy()
        preview.thumbnail((preview_limit, preview_limit), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (preview.width + padding * 2, preview.height + padding * 2), (255, 255, 255, 255))
        canvas.alpha_composite(preview.convert("RGBA"), (padding, padding))
        canvas_rgb = canvas.convert("RGB")
        self.preview_photo = ctk.CTkImage(light_image=canvas_rgb, dark_image=canvas_rgb, size=canvas_rgb.size)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _update_quality(self, quality: ScanQualityReport) -> None:
        color = QUALITY_COLORS.get(quality.rating, FIELD)
        if self.quality_badge is not None:
            text_color = "#111111" if quality.rating in {"Excellent", "Good"} else "#FFFFFF"
            self.quality_badge.configure(
                text=f"{quality.rating} {quality.score}/100",
                fg_color=color,
                text_color=text_color,
            )

        if self.quality_title is not None:
            self.quality_title.configure(
                text=(
                    f"Scan safety - version {quality.qr_version} - "
                    f"{quality.module_count} modules - {quality.module_pixels:.1f} px/module"
                )
            )

        errors = [item.text for item in quality.messages if item.level == "error"]
        warnings = [item.text for item in quality.messages if item.level == "warning"]
        if errors:
            self.status.set(errors[0])
        elif warnings:
            self.status.set(warnings[0])
        else:
            self.status.set("Excellent scan safety for the current settings.")

        if self.quality_details is not None:
            if quality.messages:
                details = "\n".join(f"- {message.text}" for message in quality.messages[:4])
            else:
                details = "No scan risks detected for the current settings."
            if len(quality.messages) > 4:
                details += f"\n- {len(quality.messages) - 4} more checks need attention."
            wrap = max(280, (self.preview_card.winfo_width() if self.preview_card else 560) - 72)
            self.quality_details.configure(text=details, wraplength=wrap)
            if self.status_label is not None:
                self.status_label.configure(wraplength=wrap)

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

    def _ensure_logo_error_correction(self) -> None:
        if self.syncing_logo_error_correction:
            return
        if not self.use_logo.get() or not self.logo_path.get().strip():
            return
        if self.error_correction.get() == ErrorCorrectionLevel.H.value:
            return

        self.syncing_logo_error_correction = True
        try:
            self.error_correction.set(ErrorCorrectionLevel.H.value)
            self.status.set("Using H error correction for logo safety.")
        finally:
            self.syncing_logo_error_correction = False

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
        picker = ColorPickerDialog(self.root, variable.get())
        hex_color = picker.show()
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

    def _on_export_format_change(self, _: str | None = None) -> None:
        self._sync_output_extension()
        self._save_app_settings()

    def _choose_output(self) -> None:
        export_format = self.export_format.get()
        suffix = _export_suffix(export_format)
        current = self._output_path()
        initial_dir = current.parent if current.parent != Path(".") else Path(self.app_settings.get("last_export_dir", "."))
        filetypes = SVG_FILETYPES if export_format == "SVG" else PNG_FILETYPES
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export QR code",
            defaultextension=suffix,
            filetypes=filetypes,
            initialdir=str(initial_dir),
            initialfile=current.with_suffix(suffix).name,
        )
        if path:
            self.output_path.set(str(_with_suffix(Path(path), suffix)))
            self._save_app_settings()

    def _export(self) -> None:
        result = generate_qr(self._style(), self._logo(), output_size=self._quality_output_size())
        errors = [item.text for item in result.validation if item.level == "error"]
        if errors:
            messagebox.showerror("Cannot export", errors[0], parent=self.root)
            return

        out_path = self._output_path()
        if out_path.exists() and not messagebox.askyesno(
            "Overwrite file?",
            f"{out_path.name} already exists. Replace it?",
            parent=self.root,
        ):
            return

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if self.export_format.get() == "SVG":
            svg = generate_qr_svg(
                self._style(),
                self._logo(),
                transparent_background=self.transparent_background.get(),
                display_size=self._selected_export_size(result.image.size[0]),
            )
            out_path.write_text(svg, encoding="utf-8")
        else:
            image = self._prepared_export_image(result.image)
            image.save(out_path)

        self._save_app_settings()
        self.status.set(f"Saved {out_path.name}")

    def _copy_png(self) -> None:
        result = generate_qr(self._style(), self._logo(), output_size=self._selected_fixed_output_size())
        errors = [item.text for item in result.validation if item.level == "error"]
        if errors:
            messagebox.showerror("Cannot copy", errors[0], parent=self.root)
            return

        image = self._prepared_export_image(result.image)
        try:
            _copy_image_to_clipboard(image)
        except OSError as exc:
            messagebox.showerror("Could not copy image", str(exc), parent=self.root)
            return

        self.status.set("Copied PNG image to clipboard.")

    def _open_output_folder(self) -> None:
        folder = self._output_path().parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc), parent=self.root)

    def _prepared_export_image(self, image: Image.Image) -> Image.Image:
        export = image.convert("RGBA") if self.transparent_background.get() else image.convert("RGB")
        if self.transparent_background.get():
            export = _make_color_transparent(export, self.back_color.get())

        size = self._selected_export_size(export.size[0])
        if size and size != export.size[0]:
            export = export.resize((size, size), Image.Resampling.LANCZOS)
        return export

    def _selected_export_size(self, original_size: int) -> int:
        return self._selected_fixed_output_size() or original_size

    def _selected_fixed_output_size(self) -> int | None:
        selection = self.output_size.get()
        if selection == "Original":
            return None
        if selection == "Custom":
            return self.custom_output_size.get()
        return int(selection)

    def _quality_output_size(self) -> int | None:
        if self.export_format.get() != "PNG":
            return None
        return self._selected_fixed_output_size()

    def _output_path(self) -> Path:
        return _with_suffix(Path(self.output_path.get().strip() or DEFAULT_OUTPUT), _export_suffix(self.export_format.get()))

    def _sync_output_extension(self) -> None:
        path = self._output_path()
        self.output_path.set(str(path))
        if self.export_button is not None:
            self.export_button.configure(text=f"Export {self.export_format.get()}")

    def _save_app_settings(self) -> None:
        output_path = self._output_path()
        self.app_settings = {
            "last_output_path": str(output_path),
            "last_export_dir": str(output_path.parent),
            "export_format": self.export_format.get(),
            "output_size": self.output_size.get(),
            "custom_output_size": self.custom_output_size.get(),
            "transparent_background": self.transparent_background.get(),
        }
        _save_app_settings(self.app_settings)


def main() -> None:
    app = QrGeneratorApp()
    app.run()


def _preset_filename(name: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in name.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return f"{safe or 'qr-preset'}.qrpreset.json"


def _load_app_settings() -> dict[str, object]:
    try:
        data = json.loads(APP_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_app_settings(settings: dict[str, object]) -> None:
    try:
        APP_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        APP_SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def _settings_choice(settings: dict[str, object], key: str, allowed: tuple[str, ...], default: str) -> str:
    value = str(settings.get(key, default))
    return value if value in allowed else default


def _settings_int(settings: dict[str, object], key: str, minimum: int, maximum: int, default: int) -> int:
    try:
        value = round(float(settings.get(key, default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _export_suffix(export_format: str) -> str:
    return ".svg" if export_format == "SVG" else ".png"


def _with_suffix(path: Path, suffix: str) -> Path:
    return path if path.suffix.lower() == suffix else path.with_suffix(suffix)


def _make_color_transparent(image: Image.Image, color: str) -> Image.Image:
    transparent = image.convert("RGBA")
    red, green, blue = ImageColor.getrgb(color)[:3]
    pixels = []
    for pixel_red, pixel_green, pixel_blue, pixel_alpha in transparent.getdata():
        distance = abs(pixel_red - red) + abs(pixel_green - green) + abs(pixel_blue - blue)
        if distance <= 24:
            pixels.append((pixel_red, pixel_green, pixel_blue, 0))
        else:
            pixels.append((pixel_red, pixel_green, pixel_blue, pixel_alpha))
    transparent.putdata(pixels)
    return transparent


def _copy_image_to_clipboard(image: Image.Image) -> None:
    if sys.platform != "win32":
        raise OSError("Copying images is currently supported on Windows only.")

    image_for_clipboard = image.convert("RGBA")
    if image_for_clipboard.getchannel("A").getextrema()[0] < 255:
        background = Image.new("RGB", image_for_clipboard.size, "#FFFFFF")
        background.paste(image_for_clipboard, mask=image_for_clipboard.getchannel("A"))
        image_for_clipboard = background
    else:
        image_for_clipboard = image_for_clipboard.convert("RGB")

    output = BytesIO()
    image_for_clipboard.save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    cf_dib = 8
    gmem_moveable = 0x0002
    gmem_zeroinit = 0x0040
    handle = None

    if not user32.OpenClipboard(None):
        raise OSError("Could not open the Windows clipboard.")

    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(gmem_moveable | gmem_zeroinit, len(data))
        if not handle:
            raise OSError("Could not allocate clipboard memory.")

        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            raise OSError("Could not lock clipboard memory.")

        ctypes.memmove(ctypes.c_void_p(pointer), data, len(data))
        kernel32.GlobalUnlock(handle)

        if not user32.SetClipboardData(cf_dib, handle):
            raise OSError("Could not write image data to the clipboard.")
        handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)


def _normalize_hex_color(value: str, default: str = "#000000") -> str:
    raw_value = value.strip()
    if _is_hex_color(raw_value):
        normalized = raw_value if raw_value.startswith("#") else f"#{raw_value}"
        return normalized.upper()

    try:
        red, green, blue = ImageColor.getrgb(raw_value or default)[:3]
    except ValueError:
        red, green, blue = ImageColor.getrgb(default)[:3]
    return _rgb_to_hex(red, green, blue)


def _is_hex_color(value: str) -> bool:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    return len(value) == 6 and all(character in "0123456789abcdefABCDEF" for character in value)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = _normalize_hex_color(value)
    return int(normalized[1:3], 16), int(normalized[3:5], 16), int(normalized[5:7], 16)


def _rgb_to_hex(red: int, green: int, blue: int) -> str:
    return f"#{_clamp_color(red):02X}{_clamp_color(green):02X}{_clamp_color(blue):02X}"


def _clamp_color(value: int) -> int:
    return max(0, min(255, int(value)))


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
