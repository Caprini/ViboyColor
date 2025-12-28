#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico para Problemas con pytest en Cursor

Este script diagnostica problemas específicos que pueden causar
que pytest se bloquee o que Cursor se cuelgue al ejecutar tests.

Uso:
    python tools/diagnostico_pytest.py
"""

import sys
import os
import subprocess
import time
from pathlib import Path
import io

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import io
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Agregar el directorio raíz al sys.path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def print_header(text: str) -> None:
    """Imprime un encabezado formateado."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_section(text: str) -> None:
    """Imprime una sección formateada."""
    print(f"\n>> {text}")
    print("-" * 70)

def check_pytest_installation() -> bool:
    """Verifica que pytest esté instalado correctamente."""
    print_section("Instalación de pytest")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"  [OK] pytest instalado: {result.stdout.strip()}")
            
            # Verificar plugins
            result_plugins = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "timeout" in result_plugins.stdout or "timeout" in result_plugins.stderr:
                print(f"  [OK] pytest-timeout instalado")
            else:
                print(f"  [WARN] pytest-timeout puede no estar instalado")
            
            return True
        else:
            print(f"  [ERROR] pytest no funciona correctamente")
            print(f"  Salida: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] pytest se bloqueó al verificar versión (timeout)")
        return False
    except Exception as e:
        print(f"  [ERROR] Error al verificar pytest: {e}")
        return False

def check_pytest_config() -> bool:
    """Verifica la configuración de pytest."""
    print_section("Configuración de pytest")
    
    config_file = project_root / "pytest.ini"
    if config_file.exists():
        print(f"  [OK] pytest.ini encontrado")
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "timeout" in content:
                print(f"  [OK] Timeout configurado en pytest.ini")
            else:
                print(f"  [WARN] Timeout no configurado en pytest.ini")
    else:
        print(f"  [WARN] pytest.ini no encontrado")
        return False
    
    conftest_file = project_root / "tests" / "conftest.py"
    if conftest_file.exists():
        print(f"  [OK] tests/conftest.py encontrado")
        with open(conftest_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "SDL_VIDEODRIVER" in content:
                print(f"  [OK] Modo headless configurado en conftest.py")
            else:
                print(f"  [WARN] Modo headless no configurado")
    else:
        print(f"  [WARN] tests/conftest.py no encontrado")
        return False
    
    return True

def check_environment_variables() -> None:
    """Verifica variables de entorno importantes."""
    print_section("Variables de Entorno")
    
    sdl_videodriver = os.environ.get('SDL_VIDEODRIVER', 'NO CONFIGURADO')
    print(f"  SDL_VIDEODRIVER: {sdl_videodriver}")
    if sdl_videodriver == 'dummy':
        print(f"  [OK] Pygame configurado en modo headless")
    else:
        print(f"  [WARN] Pygame puede intentar abrir ventanas")
    
    pygame_hide = os.environ.get('PYGAME_HIDE_SUPPORT_PROMPT', 'NO CONFIGURADO')
    print(f"  PYGAME_HIDE_SUPPORT_PROMPT: {pygame_hide}")

def test_simple_import() -> bool:
    """Prueba importar módulos básicos."""
    print_section("Prueba de Importación")
    
    try:
        import pytest
        print(f"  [OK] pytest importado correctamente")
    except ImportError as e:
        print(f"  [ERROR] No se puede importar pytest: {e}")
        return False
    
    try:
        import pygame
        print(f"  [OK] pygame importado correctamente")
    except ImportError:
        print(f"  [WARN] pygame no disponible (algunos tests se saltarán)")
    
    try:
        from viboy_core import PyMMU
        print(f"  [OK] viboy_core importado correctamente")
    except ImportError as e:
        print(f"  [WARN] viboy_core no disponible: {e}")
    
    return True

def test_single_test_file() -> bool:
    """Prueba ejecutar un test simple con timeout."""
    print_section("Prueba de Ejecución (test simple)")
    
    test_file = project_root / "tests" / "test_core_registers.py"
    if not test_file.exists():
        print(f"  [ERROR] Archivo de test no encontrado: {test_file}")
        return False
    
    print(f"  Ejecutando: pytest {test_file.name} -v --tb=short --timeout=5")
    print(f"  (Esto puede tardar unos segundos...)")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short", "--timeout=5", "-x"],
            capture_output=True,
            text=True,
            timeout=30  # Timeout máximo de 30 segundos para esta prueba
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"  [OK] Test ejecutado correctamente en {elapsed:.2f}s")
            print(f"  Tests pasados: {result.stdout.count('PASSED')}")
            return True
        elif result.returncode == 1:
            print(f"  [WARN] Test falló pero no se bloqueó (tiempo: {elapsed:.2f}s)")
            print(f"  Esto es normal si hay tests que fallan")
            return True  # No es un bloqueo, solo un fallo
        else:
            print(f"  [ERROR] Código de salida: {result.returncode}")
            print(f"  Salida: {result.stdout[:500]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] pytest se bloqueó (timeout de 30s)")
        print(f"  Esto indica que hay un problema de bloqueo")
        return False
    except Exception as e:
        print(f"  [ERROR] Error al ejecutar test: {e}")
        return False

def test_collection_only() -> bool:
    """Prueba solo la recolección de tests (sin ejecutarlos)."""
    print_section("Prueba de Recolección de Tests")
    
    print(f"  Ejecutando: pytest --collect-only -q")
    print(f"  (Esto puede tardar unos segundos...)")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=15
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            # Contar tests encontrados
            test_count = result.stdout.count("test_") + result.stdout.count("::test_")
            print(f"  [OK] Recolección completada en {elapsed:.2f}s")
            print(f"  Tests encontrados: ~{test_count}")
            return True
        else:
            print(f"  [ERROR] Error en recolección")
            print(f"  Salida: {result.stderr[:500]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] Recolección se bloqueó (timeout de 15s)")
        print(f"  Esto indica un problema al importar módulos o tests")
        return False
    except Exception as e:
        print(f"  [ERROR] Error en recolección: {e}")
        return False

def generate_report() -> str:
    """Genera un reporte completo para compartir."""
    print_section("Generando Reporte")
    
    report = []
    report.append("=" * 70)
    report.append("REPORTE DE DIAGNÓSTICO - pytest en Cursor")
    report.append("=" * 70)
    report.append(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Python: {sys.version}")
    report.append(f"Ejecutable: {sys.executable}")
    report.append(f"Directorio: {project_root}")
    report.append("")
    
    # Variables de entorno
    report.append("Variables de Entorno:")
    report.append(f"  SDL_VIDEODRIVER: {os.environ.get('SDL_VIDEODRIVER', 'NO CONFIGURADO')}")
    report.append(f"  PYGAME_HIDE_SUPPORT_PROMPT: {os.environ.get('PYGAME_HIDE_SUPPORT_PROMPT', 'NO CONFIGURADO')}")
    report.append("")
    
    # Versión de pytest
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        report.append(f"pytest: {result.stdout.strip()}")
    except:
        report.append("pytest: ERROR al obtener versión")
    
    report.append("")
    report.append("=" * 70)
    
    return "\n".join(report)

def main() -> int:
    """Función principal de diagnóstico."""
    print_header("Diagnóstico de pytest - Viboy Color")
    
    # Verificaciones
    pytest_ok = check_pytest_installation()
    config_ok = check_pytest_config()
    check_environment_variables()
    import_ok = test_simple_import()
    
    # Pruebas de ejecución (solo si todo lo anterior está OK)
    if pytest_ok and config_ok and import_ok:
        collection_ok = test_collection_only()
        if collection_ok:
            test_ok = test_single_test_file()
        else:
            test_ok = False
    else:
        print_section("Omitiendo pruebas de ejecución (problemas previos detectados)")
        collection_ok = False
        test_ok = False
    
    # Resumen
    print_header("Resumen del Diagnóstico")
    
    issues = []
    if not pytest_ok:
        issues.append("[ERROR] pytest no está instalado o no funciona")
    if not config_ok:
        issues.append("[WARN] Configuración de pytest incompleta")
    if not import_ok:
        issues.append("[WARN] Problemas al importar módulos")
    if not collection_ok:
        issues.append("[ERROR] Recolección de tests se bloquea")
    if not test_ok:
        issues.append("[ERROR] Ejecución de tests se bloquea")
    
    if issues:
        print("\nProblemas detectados:")
        for issue in issues:
            print(f"  {issue}")
        
        print("\n" + "=" * 70)
        print("SOLUCIONES RECOMENDADAS:")
        print("=" * 70)
        
        if not pytest_ok:
            print("\n1. REINSTALAR pytest y plugins:")
            print("   pip install pytest pytest-timeout pytest-cov")
        
        if not config_ok:
            print("\n2. VERIFICAR archivos de configuración:")
            print("   - pytest.ini debe existir en la raíz")
            print("   - tests/conftest.py debe existir")
        
        if not collection_ok or not test_ok:
            print("\n3. EJECUTAR con más información:")
            print("   pytest --collect-only -vv")
            print("   pytest tests/test_core_registers.py -vv --tb=long")
        
        print("\n4. COMPARTIR este reporte:")
        report = generate_report()
        report_file = project_root / "pytest_diagnostico_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"   Reporte guardado en: {report_file}")
        print(f"   Comparte este archivo para obtener ayuda")
        
        return 1
    else:
        print("\n[OK] Todo parece estar correcto!")
        print("\nSi pytest aún se bloquea en Cursor:")
        print("  1. Intenta ejecutar pytest desde terminal externa")
        print("  2. Verifica los logs de Cursor: Ctrl+Shift+P > Developer: Show Logs")
        print("  3. Comparte el reporte generado para análisis")
        return 0

if __name__ == "__main__":
    exit(main())

