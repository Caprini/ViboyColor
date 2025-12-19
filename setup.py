"""
Setup script para compilar extensiones Cython del núcleo de Viboy Color.

Este script configura el sistema de compilación para generar extensiones
Python (.pyd en Windows, .so en Linux/macOS) a partir de código C++/Cython.

Uso:
    python setup.py build_ext --inplace
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy
from pathlib import Path

# Obtener el directorio raíz del proyecto
project_root = Path(__file__).parent.absolute()
cpp_dir = project_root / "src" / "core" / "cpp"
cython_dir = project_root / "src" / "core" / "cython"

# Definir la extensión
extensions = [
    Extension(
        name="viboy_core",
        sources=[
            str(cython_dir / "native_core.pyx"),
            str(cpp_dir / "NativeCore.cpp"),
        ],
        include_dirs=[
            str(cpp_dir.absolute()),
            numpy.get_include(),  # Para futuros usos de numpy
        ],
        language="c++",
        extra_compile_args=[
            "/std:c++17" if __import__("sys").platform == "win32" else "-std=c++17",
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

