#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viboy Color - Script de configuración para py2app (macOS)
Genera un bundle .app para macOS

Requisitos:
    pip install py2app

Uso:
    python setup.py py2app
"""

from setuptools import setup
from pathlib import Path

APP_NAME = "ViboyColor"
APP_VERSION = "0.0.1"
APP_DESCRIPTION = "Emulador educativo de Game Boy Color"
APP_AUTHOR = "Viboy Color Project"
APP_URL = "https://github.com/tu-usuario/viboy-color"

# Ruta al script principal
PROJECT_ROOT = Path(__file__).parent.parent.parent
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_FILE = ASSETS_DIR / "viboycolor-icon.png"

# Verificar que el script principal existe
if not MAIN_SCRIPT.exists():
    raise FileNotFoundError(f"No se encontró el script principal: {MAIN_SCRIPT}")

APP = [str(MAIN_SCRIPT)]

DATA_FILES = []
# Incluir assets si existen
if ASSETS_DIR.exists():
    assets_list = []
    for asset_file in ASSETS_DIR.glob("*"):
        if asset_file.is_file():
            assets_list.append(str(asset_file))
    if assets_list:
        DATA_FILES.append(("assets", assets_list))

OPTIONS = {
    "argv_emulation": False,
    "strip": True,
    "iconfile": str(ICON_FILE) if ICON_FILE.exists() else None,
    "includes": [
        "pygame",
        "pygame.ce",
    ],
    "excludes": [
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleGetInfoString": f"{APP_NAME} {APP_VERSION}",
        "CFBundleIdentifier": "com.viboycolor.app",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSHumanReadableCopyright": f"Copyright © 2025 {APP_AUTHOR}",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",  # macOS High Sierra
    },
}

setup(
    name=APP_NAME,
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    url=APP_URL,
)

