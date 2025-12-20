"""
Setup script para compilar extensiones Cython del núcleo de Viboy Color.

Este script configura el sistema de compilación para generar extensiones
Python (.pyd en Windows, .so en Linux/macOS) a partir de código C++/Cython.

Uso:
    python setup.py build_ext --inplace
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
from pathlib import Path
import sys

# Intentar importar numpy de forma segura (opcional)
try:
    import numpy
    numpy_available = True
    numpy_include = numpy.get_include()
except (ImportError, AttributeError) as e:
    numpy_available = False
    numpy_include = None
    print(f"[INFO] NumPy no disponible o corrupto: {e}")
    print("[INFO] Continuando sin NumPy (no es necesario para la compilación actual)")

# Obtener el directorio raíz del proyecto
project_root = Path(__file__).parent.absolute()
cpp_dir = project_root / "src" / "core" / "cpp"
cython_dir = project_root / "src" / "core" / "cython"

# Construir include_dirs
include_dirs = [str(cpp_dir.absolute())]
if numpy_available and numpy_include:
    include_dirs.append(numpy_include)

# Definir la extensión
extensions = [
    Extension(
        name="viboy_core",
        sources=[
            str(cython_dir / "native_core.pyx"),
            str(cpp_dir / "NativeCore.cpp"),
            str(cpp_dir / "MMU.cpp"),
            str(cpp_dir / "Registers.cpp"),
            str(cpp_dir / "CPU.cpp"),
            str(cpp_dir / "PPU.cpp"),  # PPU (Pixel Processing Unit)
            str(cpp_dir / "Timer.cpp"),  # Timer (Subsistema de Temporización)
            str(cpp_dir / "Joypad.cpp"),  # Joypad (Subsistema de Entrada del Usuario)
        ],
        include_dirs=include_dirs,
        language="c++",
        extra_compile_args=[
            "/std:c++17" if sys.platform == "win32" else "-std=c++17",
        ],
    )
]

setup(
    name="viboy_core",
    version="0.0.2",
    description="Núcleo de emulación de Viboy Color (C++/Cython)",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",  # Python 3
            "boundscheck": False,   # Desactivar checks de bounds para rendimiento
            "wraparound": False,    # Desactivar índices negativos para rendimiento
        },
    ),
    zip_safe=False,
)

