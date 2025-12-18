#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viboy Color - Script de Build y Empaquetado
Genera ejecutables para Windows, Linux y macOS usando PyInstaller
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
RELEASE_DIR = PROJECT_ROOT / "release"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "ViboyColor.spec"

# Nombre de la aplicación
APP_NAME = "ViboyColor"
APP_VERSION = "0.0.1"


def detect_os() -> str:
    """Detecta el sistema operativo actual"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "macos"
    else:
        logger.warning(f"Sistema operativo no reconocido: {system}. Asumiendo Linux.")
        return "linux"


def find_icon() -> Path | None:
    """Busca un archivo de icono disponible (.ico para Windows, .png para otros)"""
    current_os = detect_os()
    
    if current_os == "windows":
        # Priorizar .ico en Windows
        icon_ico = ASSETS_DIR / "viboycolor-icon.ico"
        if icon_ico.exists():
            return icon_ico
        # Fallback a .png si PyInstaller lo soporta
        icon_png = ASSETS_DIR / "viboycolor-icon.png"
        if icon_png.exists():
            logger.info("Usando .png como icono (PyInstaller lo convertirá)")
            return icon_png
    else:
        # Linux/macOS: usar .png
        icon_png = ASSETS_DIR / "viboycolor-icon.png"
        if icon_png.exists():
            return icon_png
    
    logger.warning("No se encontró archivo de icono. PyInstaller usará el icono por defecto.")
    return None


def clean_build_artifacts() -> None:
    """Limpia artefactos de builds anteriores"""
    logger.info("Limpiando artefactos de builds anteriores...")
    
    dirs_to_clean = [DIST_DIR, BUILD_DIR]
    files_to_clean = [SPEC_FILE]
    
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            logger.info(f"  Eliminando {dir_path}")
            shutil.rmtree(dir_path)
    
    for file_path in files_to_clean:
        if file_path.exists():
            logger.info(f"  Eliminando {file_path}")
            file_path.unlink()
    
    logger.info("Limpieza completada.")


def build_windows() -> None:
    """Construye el ejecutable para Windows"""
    logger.info("=" * 60)
    logger.info("Construyendo ejecutable para Windows")
    logger.info("=" * 60)
    
    # Verificar que main.py existe
    if not MAIN_SCRIPT.exists():
        logger.error(f"No se encontró {MAIN_SCRIPT}")
        sys.exit(1)
    
    # Buscar icono
    icon_path = find_icon()
    icon_arg = []
    if icon_path:
        icon_arg = ["--icon", str(icon_path)]
        logger.info(f"Usando icono: {icon_path}")
    
    # Preparar argumentos de PyInstaller
    pyinstaller_args = [
        "pyinstaller",
        "--name", APP_NAME,
        "--noconsole",  # Windowed mode (sin terminal)
        "--onefile",  # Un solo archivo ejecutable
        "--clean",  # Limpiar cachés
        # Incluir carpeta assets
        "--add-data", f"{ASSETS_DIR}{os.pathsep}assets",
    ]
    
    # Añadir icono si existe
    if icon_arg:
        pyinstaller_args.extend(icon_arg)
    
    # Añadir el script principal
    pyinstaller_args.append(str(MAIN_SCRIPT))
    
    logger.info("Ejecutando PyInstaller...")
    logger.info(f"Comando: {' '.join(pyinstaller_args)}")
    
    try:
        result = subprocess.run(
            pyinstaller_args,
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=False
        )
        logger.info("PyInstaller ejecutado exitosamente.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar PyInstaller: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("PyInstaller no está instalado. Ejecuta: pip install pyinstaller")
        sys.exit(1)


def build_linux() -> None:
    """Construye el ejecutable para Linux"""
    logger.info("=" * 60)
    logger.info("Construyendo ejecutable para Linux")
    logger.info("=" * 60)
    
    if not MAIN_SCRIPT.exists():
        logger.error(f"No se encontró {MAIN_SCRIPT}")
        sys.exit(1)
    
    icon_path = find_icon()
    icon_arg = []
    if icon_path:
        icon_arg = ["--icon", str(icon_path)]
        logger.info(f"Usando icono: {icon_path}")
    
    # En Linux, podemos mantener la consola o quitarla según preferencia
    # Por ahora, mantenemos --noconsole para consistencia
    pyinstaller_args = [
        "pyinstaller",
        "--name", APP_NAME,
        "--noconsole",
        "--onefile",
        "--clean",
        "--add-data", f"{ASSETS_DIR}{os.pathsep}assets",
    ]
    
    if icon_arg:
        pyinstaller_args.extend(icon_arg)
    
    pyinstaller_args.append(str(MAIN_SCRIPT))
    
    logger.info("Ejecutando PyInstaller...")
    logger.info(f"Comando: {' '.join(pyinstaller_args)}")
    
    try:
        result = subprocess.run(
            pyinstaller_args,
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=False
        )
        logger.info("PyInstaller ejecutado exitosamente.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar PyInstaller: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("PyInstaller no está instalado. Ejecuta: pip install pyinstaller")
        sys.exit(1)


def build_macos() -> None:
    """Construye el ejecutable para macOS (.app bundle)"""
    logger.info("=" * 60)
    logger.info("Construyendo aplicación para macOS")
    logger.info("=" * 60)
    
    if not MAIN_SCRIPT.exists():
        logger.error(f"No se encontró {MAIN_SCRIPT}")
        sys.exit(1)
    
    icon_path = find_icon()
    icon_arg = []
    if icon_path:
        icon_arg = ["--icon", str(icon_path)]
        logger.info(f"Usando icono: {icon_path}")
    
    # En macOS, usamos --windowed para crear un .app bundle
    pyinstaller_args = [
        "pyinstaller",
        "--name", APP_NAME,
        "--windowed",  # macOS: crea .app bundle
        "--onefile",
        "--clean",
        "--add-data", f"{ASSETS_DIR}{os.pathsep}assets",
    ]
    
    if icon_arg:
        pyinstaller_args.extend(icon_arg)
    
    pyinstaller_args.append(str(MAIN_SCRIPT))
    
    logger.info("Ejecutando PyInstaller...")
    logger.info(f"Comando: {' '.join(pyinstaller_args)}")
    
    try:
        result = subprocess.run(
            pyinstaller_args,
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=False
        )
        logger.info("PyInstaller ejecutado exitosamente.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar PyInstaller: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error("PyInstaller no está instalado. Ejecuta: pip install pyinstaller")
        sys.exit(1)


def move_to_release() -> None:
    """Mueve el ejecutable generado a la carpeta release/"""
    logger.info("=" * 60)
    logger.info("Moviendo ejecutables a carpeta release/")
    logger.info("=" * 60)
    
    # Crear carpeta release si no existe
    RELEASE_DIR.mkdir(exist_ok=True)
    
    current_os = detect_os()
    
    if current_os == "windows":
        exe_name = f"{APP_NAME}.exe"
        source = DIST_DIR / exe_name
        target = RELEASE_DIR / exe_name
    elif current_os == "linux":
        exe_name = APP_NAME
        source = DIST_DIR / exe_name
        target = RELEASE_DIR / exe_name
    elif current_os == "macos":
        app_name = f"{APP_NAME}.app"
        source = DIST_DIR / app_name
        target = RELEASE_DIR / app_name
    
    if not source.exists():
        logger.error(f"No se encontró el ejecutable generado: {source}")
        logger.error("El build puede haber fallado. Revisa los logs de PyInstaller.")
        sys.exit(1)
    
    # Si el target ya existe, eliminarlo
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    
    # Mover/copiar el ejecutable
    if source.is_dir():
        shutil.copytree(source, target)
        logger.info(f"Aplicación copiada: {target}")
    else:
        shutil.copy2(source, target)
        logger.info(f"Ejecutable copiado: {target}")
    
    logger.info(f"✅ Ejecutable disponible en: {target}")
    logger.info(f"   Tamaño: {target.stat().st_size / (1024*1024):.2f} MB")


def main() -> None:
    """Función principal del script de build"""
    logger.info("=" * 60)
    logger.info(f"Viboy Color - Sistema de Build v{APP_VERSION}")
    logger.info("=" * 60)
    
    current_os = detect_os()
    logger.info(f"Sistema operativo detectado: {current_os}")
    logger.info(f"Directorio del proyecto: {PROJECT_ROOT}")
    
    # Limpiar builds anteriores
    clean_build_artifacts()
    
    # Construir según el SO
    if current_os == "windows":
        build_windows()
    elif current_os == "linux":
        build_linux()
    elif current_os == "macos":
        build_macos()
    else:
        logger.error(f"Sistema operativo no soportado: {current_os}")
        sys.exit(1)
    
    # Mover a release/
    move_to_release()
    
    logger.info("=" * 60)
    logger.info("✅ Build completado exitosamente!")
    logger.info("=" * 60)
    logger.info(f"Ejecutable disponible en: {RELEASE_DIR}")
    logger.info("")
    logger.info("Nota: Si tu antivirus marca el .exe como sospechoso, es un falso positivo.")
    logger.info("      PyInstaller genera ejecutables legítimos. Añade una excepción si es necesario.")


if __name__ == "__main__":
    main()

