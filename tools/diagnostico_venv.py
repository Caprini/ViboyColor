#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico para Problemas con Entorno Virtual (venv)

Este script diagnostica problemas comunes cuando el emulador no funciona
dentro de un entorno virtual pero sí funciona fuera de él.

Uso:
    python tools/diagnostico_venv.py
"""

import sys
import platform
import io
from pathlib import Path

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Agregar el directorio raíz del proyecto al sys.path si no está
# Esto permite importar viboy_core desde cualquier ubicación
project_root = Path(__file__).parent.parent.absolute()
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

def print_header(text: str) -> None:
    """Imprime un encabezado formateado."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_section(text: str) -> None:
    """Imprime una sección formateada."""
    print(f"\n>> {text}")
    print("-" * 70)

def check_python_version() -> bool:
    """Verifica la versión de Python."""
    print_section("Versión de Python")
    version = sys.version_info
    print(f"  Versión: {version.major}.{version.minor}.{version.micro}")
    print(f"  Ejecutable: {sys.executable}")
    print(f"  Plataforma: {platform.platform()}")
    
    # Verificar si estamos en un venv
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        print(f"  [OK] Estamos en un entorno virtual")
        print(f"  Base prefix: {sys.base_prefix}")
        print(f"  Venv prefix: {sys.prefix}")
    else:
        print(f"  [WARN] NO estamos en un entorno virtual")
    
    return in_venv

def check_viboy_core() -> tuple[bool, str]:
    """Intenta importar viboy_core y diagnostica problemas."""
    print_section("Módulo viboy_core (C++ compilado)")
    
    try:
        import viboy_core
        print(f"  [OK] viboy_core importado correctamente")
        print(f"  Ubicación: {viboy_core.__file__}")
        
        # Intentar importar clases específicas
        try:
            from viboy_core import PyMMU, PyRegisters, PyCPU, PyPPU
            print(f"  [OK] Todas las clases importadas correctamente")
            return True, "OK"
        except ImportError as e:
            print(f"  [ERROR] Error al importar clases: {e}")
            return False, f"Clases no disponibles: {e}"
            
    except ImportError as e:
        print(f"  [ERROR] No se pudo importar viboy_core")
        print(f"  Error: {e}")
        
        # Diagnóstico adicional
        print(f"\n  Diagnóstico:")
        
        # Buscar archivos .pyd
        project_root = Path(__file__).parent.parent
        pyd_files = list(project_root.glob("*.pyd"))
        
        if pyd_files:
            print(f"  [OK] Se encontraron {len(pyd_files)} archivo(s) .pyd:")
            for pyd_file in pyd_files:
                print(f"    - {pyd_file.name}")
                print(f"      Tamaño: {pyd_file.stat().st_size} bytes")
                
            # Verificar compatibilidad de versión
            print(f"\n  Verificando compatibilidad...")
            python_version_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
            matching_pyd = [p for p in pyd_files if python_version_tag in p.name]
            
            if matching_pyd:
                print(f"  [OK] Se encontró .pyd compatible: {matching_pyd[0].name}")
            else:
                print(f"  [ERROR] NO se encontró .pyd compatible con Python {sys.version_info.major}.{sys.version_info.minor}")
                print(f"    Buscando: *{python_version_tag}*.pyd")
                print(f"    Solución: Recompilar con: python setup.py build_ext --inplace")
        else:
            print(f"  [ERROR] No se encontraron archivos .pyd en el directorio raíz")
            print(f"    Solución: Compilar con: python setup.py build_ext --inplace")
        
        return False, str(e)
    except Exception as e:
        print(f"  [ERROR] Error inesperado: {type(e).__name__}: {e}")
        return False, str(e)

def check_dependencies() -> bool:
    """Verifica que las dependencias estén instaladas."""
    print_section("Dependencias de Python")
    
    dependencies = {
        'pygame': 'pygame-ce',
        'cython': 'cython',
        'numpy': 'numpy',
        'setuptools': 'setuptools',
    }
    
    all_ok = True
    for module_name, package_name in dependencies.items():
        try:
            module = __import__(module_name)
            version = getattr(module, '__version__', 'desconocida')
            print(f"  [OK] {package_name}: {version}")
        except ImportError:
            print(f"  [ERROR] {package_name}: NO INSTALADO")
            print(f"    Instalar con: pip install {package_name}")
            all_ok = False
    
    return all_ok

def check_project_structure() -> bool:
    """Verifica la estructura del proyecto."""
    print_section("Estructura del Proyecto")
    
    project_root = Path(__file__).parent.parent
    required_paths = [
        'src',
        'src/core',
        'src/core/cpp',
        'src/core/cython',
        'setup.py',
        'main.py',
    ]
    
    all_ok = True
    for path_str in required_paths:
        path = project_root / path_str
        if path.exists():
            print(f"  [OK] {path_str}")
        else:
            print(f"  [ERROR] {path_str}: NO ENCONTRADO")
            all_ok = False
    
    return all_ok

def check_sys_path() -> tuple[bool, str]:
    """Muestra el sys.path actual y verifica si el directorio raíz está incluido."""
    print_section("sys.path (Rutas de búsqueda de módulos)")
    
    project_root = Path(__file__).parent.parent.absolute()
    project_root_str = str(project_root)
    
    root_in_path = project_root_str in sys.path
    
    for i, path in enumerate(sys.path):
        marker = "  [VENV]" if "venv" in path.lower() or "env" in path.lower() else "  "
        if path == project_root_str:
            marker = "  [ROOT]"
        print(f"{marker}{i}: {path}")
    
    if not root_in_path:
        print(f"\n  [WARN] El directorio raíz NO está en sys.path")
        print(f"  Directorio raíz: {project_root_str}")
        print(f"  Esto puede causar problemas al importar viboy_core")
        return False, "Directorio raíz no en sys.path"
    
    return True, "OK"

def main() -> int:
    """Función principal de diagnóstico."""
    print_header("Diagnóstico de Entorno Virtual - Viboy Color")
    
    # Verificaciones
    in_venv = check_python_version()
    core_ok, core_msg = check_viboy_core()
    deps_ok = check_dependencies()
    structure_ok = check_project_structure()
    path_ok, path_msg = check_sys_path()
    
    # Resumen
    print_header("Resumen del Diagnóstico")
    
    issues = []
    if not core_ok:
        issues.append("[ERROR] viboy_core no está disponible o no es compatible")
    if not path_ok:
        issues.append("[WARN] El directorio raíz no está en sys.path (puede causar problemas de importación)")
    if not deps_ok:
        issues.append("[WARN] Faltan dependencias de Python")
    if not structure_ok:
        issues.append("[WARN] Estructura del proyecto incompleta")
    
    if issues:
        print("\nProblemas detectados:")
        for issue in issues:
            print(f"  {issue}")
        
        print("\n" + "=" * 70)
        print("SOLUCIONES RECOMENDADAS:")
        print("=" * 70)
        
        if not path_ok:
            print("\n1. AGREGAR el directorio raíz al sys.path:")
            print("   Ejecuta el script desde la raíz del proyecto:")
            print("   cd C:\\Users\\fabin\\Desktop\\ViboyColor")
            print("   python tools\\diagnostico_venv.py")
            print("\n   O ejecuta el emulador desde la raíz:")
            print("   python main.py roms/tetris.gb")
        
        if not core_ok:
            print("\n2. RECOMPILAR el módulo C++ dentro del venv:")
            print("   python setup.py build_ext --inplace")
            print("\n   Esto generará un .pyd compatible con tu versión de Python del venv.")
        
        if not deps_ok:
            print("\n3. INSTALAR dependencias faltantes:")
            print("   pip install -r requirements.txt")
        
        if in_venv:
            print("\n4. VERIFICAR que el venv use la misma versión de Python:")
            print("   python --version")
            print("   (Debe coincidir con la versión usada para compilar .pyd)")
        
        print("\n5. Si el problema persiste:")
        print("   - Desactiva el venv: deactivate")
        print("   - O recrea el venv: python -m venv venv --clear")
        print("   - Luego reinstala: pip install -r requirements.txt")
        print("   - Y recompila: python setup.py build_ext --inplace")
        
        return 1
    else:
        print("\n[OK] Todo parece estar correcto!")
        print("\nSi aún así el emulador no funciona, prueba:")
        print("  python main.py roms/tetris.gb --verbose")
        return 0

if __name__ == "__main__":
    exit(main())

