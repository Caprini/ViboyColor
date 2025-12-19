"""
Script de prueba para verificar la compilación del núcleo C++/Cython.

Este script importa el módulo compilado y ejecuta una prueba simple
para verificar que el pipeline Python -> Cython -> C++ funciona.
"""

def main():
    print("=" * 60)
    print("Test de Compilación - Viboy Color Core (C++/Cython)")
    print("=" * 60)
    
    try:
        # Intentar importar el módulo compilado
        print("\n[1/3] Importando modulo 'viboy_core'...")
        from viboy_core import PyNativeCore
        print("    [OK] Modulo importado correctamente")
        
        # Crear instancia
        print("\n[2/3] Creando instancia de PyNativeCore...")
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
            
    except ImportError as e:
        print("\n" + "=" * 60)
        print("[ERROR] No se pudo importar el modulo")
        print("=" * 60)
        print(f"\nDetalles: {e}")
        print("\nPosibles causas:")
        print("  1. El modulo no ha sido compilado aun")
        print("  2. Ejecuta: python setup.py build_ext --inplace")
        print("  3. Verifica que Cython este instalado: pip install cython")
        return 1
    except Exception as e:
        print("\n" + "=" * 60)
        print("[ERROR] Excepcion inesperada")
        print("=" * 60)
        print(f"\nDetalles: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())

