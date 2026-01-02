#!/usr/bin/env python3
"""
Script de verificación del pipeline de compilación C++/Cython.

Este script verifica que el módulo viboy_core se compila e importa correctamente.
Debe ejecutarse desde la raíz del repositorio.

Uso:
    python3 test_build.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

def main() -> int:
    """Ejecuta el test de build y devuelve código de salida."""
    # Asegurar que la raíz del repo está en sys.path
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    
    print("=" * 60)
    print("Test de Compilación - Viboy Color Core (C++/Cython)")
    print("=" * 60)
    
    try:
        # Importar el módulo compilado
        print("\n[1/3] Importando modulo 'viboy_core'...")
        import viboy_core  # noqa: F401
        print("    [OK] Modulo importado correctamente")
        print(f"[test_build] Python: {sys.version.split()[0]}")
        print(f"[test_build] sys.path[0]: {sys.path[0]}")
        
        # Intentar PyNativeCore si existe
        print("\n[2/3] Creando instancia de PyNativeCore...")
        try:
            from viboy_core import PyNativeCore  # type: ignore
            core = PyNativeCore()
            print("    [OK] Instancia creada correctamente")
            
            # Ejecutar prueba: 2 + 2 = 4
            print("\n[3/3] Ejecutando prueba: core.add(2, 2)...")
            result = core.add(2, 2)
            print(f"    [OK] Resultado: {result}")
            
            # Verificar resultado
            if result == 4:
                print("\n" + "=" * 60)
                print("[EXITO] El pipeline de compilacion funciona correctamente")
                print("=" * 60)
                print("\nEl nucleo C++/Cython esta listo para la Fase 2.")
                return 0
            else:
                print("\n" + "=" * 60)
                print("[ERROR] Resultado incorrecto")
                print(f"   Esperado: 4, Obtenido: {result}")
                print("=" * 60)
                return 1
        except Exception as e:
            print(f"[test_build] WARN: viboy_core importó, pero PyNativeCore smoke-test falló: {e}")
            traceback.print_exc(limit=5)
            return 1

    except ImportError as e:
        print("\n" + "=" * 60)
        print("[ERROR] No se pudo importar el modulo")
        print("=" * 60)
        print(f"\nDetalles: {e}")
        print("\nPosibles causas:")
        print("  1. El modulo no ha sido compilado aun")
        print("  2. Ejecuta: python3 setup.py build_ext --inplace")
        print("  3. Verifica que Cython este instalado: pip install cython")
        traceback.print_exc(limit=10)
        return 1
    except Exception as e:
        print("\n" + "=" * 60)
        print("[ERROR] Excepcion inesperada")
        print("=" * 60)
        print(f"\nDetalles: {type(e).__name__}: {e}")
        traceback.print_exc(limit=10)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

