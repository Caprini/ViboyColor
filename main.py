#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viboy Color - Emulador de Game Boy Color
Punto de entrada principal del emulador
"""

import argparse
import logging
import sys
from pathlib import Path

# Configurar encoding UTF-8 para Windows (permite mostrar emojis en consola)
# Nota: En modo windowed de PyInstaller, sys.stdout/stderr pueden ser None
if sys.platform == "win32":
    import io
    # Solo configurar encoding si hay consola disponible
    # En modo windowed (--noconsole), sys.stdout/stderr son None
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from src.viboy import Viboy

# Configurar logging básico
# ERROR: Solo errores fatales. Silencio total para máximo rendimiento.
logging.basicConfig(
    level=logging.ERROR,  # Solo errores fatales
    format="%(message)s",
    force=True,  # Forzar reconfiguración
)


def main() -> None:
    """Función principal del emulador"""
    # Detectar si hay consola disponible (no disponible en modo windowed de PyInstaller)
    has_console = sys.stdout is not None
    
    parser = argparse.ArgumentParser(
        description="Viboy Color - Emulador educativo de Game Boy Color"
    )
    parser.add_argument(
        "rom",
        nargs="?",
        type=str,
        help="Ruta al archivo ROM (.gb o .gbc)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activar modo debug con trazas detalladas de instrucciones",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Activar modo verbose (muestra mensajes INFO, incluyendo heartbeat)",
    )
    parser.add_argument(
        "--simulate-input",
        action="store_true",
        help="Simular entrada del usuario automáticamente (presionar botones en tiempos específicos)",
    )
    parser.add_argument(
        "--load-test-tiles",
        action="store_true",
        help="Cargar tiles de prueba manualmente en VRAM (hack temporal para desarrollo)",
    )
    
    args = parser.parse_args()
    
    # Si se especifica --debug, cambiar nivel de logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        # Modo verbose: mostrar INFO (incluye heartbeat)
        logging.getLogger().setLevel(logging.INFO)
    
    # Solo mostrar mensajes en consola si está disponible
    if has_console:
        print("Viboy Color - Sistema Iniciado")
        print("=" * 50)
    
    # Si no se proporciona ROM, mostrar mensaje y salir
    if not args.rom:
        if has_console:
            print("Error: Se requiere especificar una ROM")
            print("Uso: python main.py <ruta_a_rom.gb> [--debug]")
        else:
            # En modo windowed, mostrar diálogo de error
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "Error: Se requiere especificar una ROM\n\nUso: ViboyColor.exe <ruta_a_rom.gb>",
                    "Viboy Color - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                # Si falla el diálogo, usar logging
                logging.error("Error: Se requiere especificar una ROM")
        sys.exit(1)
    
    # Verificar dependencias críticas antes de continuar
    try:
        import pygame
        pygame_available = True
    except ImportError:
        pygame_available = False
        error_msg = "❌ ERROR: Pygame no está instalado.\n\nInstala con: pip install pygame-ce"
        if has_console:
            print(f"\n{error_msg}")
        else:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    error_msg,
                    "Viboy Color - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                logging.error(error_msg)
        sys.exit(1)
    
    # Inicializar sistema Viboy
    try:
        viboy = Viboy()
        viboy.load_cartridge(args.rom, load_test_tiles=args.load_test_tiles)
        
        # Obtener información del cartucho
        cartridge = viboy.get_cartridge()
        if cartridge is not None and has_console:
            header_info = cartridge.get_header_info()
            
            print(f"\n📦 Cartucho cargado:")
            print(f"   Título: {header_info['title']}")
            print(f"   Tipo: {header_info['cartridge_type']}")
            print(f"   ROM: {header_info['rom_size']} KB")
            print(f"   RAM: {header_info['ram_size']} KB")
            print(f"   Tamaño total: {cartridge.get_rom_size()} bytes")
        
        # Obtener estado inicial de la CPU
        cpu = viboy.get_cpu()
        regs = viboy.registers
        if cpu is not None and regs is not None and has_console:
            print(f"\n🖥️  CPU inicializada:")
            # Acceso compatible con ambas APIs (Python: get_pc(), C++: .pc)
            pc = regs.pc if hasattr(regs, 'pc') else regs.get_pc()
            sp = regs.sp if hasattr(regs, 'sp') else regs.get_sp()
            print(f"   PC = 0x{pc:04X}")
            print(f"   SP = 0x{sp:04X}")
        
        if has_console:
            print("\n✅ Sistema listo para ejecutar")
            if args.debug:
                print("   Modo DEBUG activado - Mostrando trazas de instrucciones")
                print("   Presiona Ctrl+C para detener\n")
            elif args.verbose:
                print("   Modo VERBOSE activado - Mostrando heartbeat y mensajes INFO")
                print("   Presiona Ctrl+C para detener\n")
            else:
                print("   Presiona Ctrl+C para detener")
                print("   (Usa --verbose para ver el heartbeat con VRAM_SUM)\n")
        
        # Ejecutar bucle principal
        viboy.run(debug=args.debug, simulate_input=args.simulate_input)
        
    except (FileNotFoundError, IOError, ValueError) as e:
        error_msg = f"Error al cargar ROM: {e}"
        if has_console:
            print(f"\n❌ {error_msg}")
            if args.debug or args.verbose:
                import traceback
                traceback.print_exc()
        else:
            # En modo windowed, mostrar diálogo de error
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    error_msg,
                    "Viboy Color - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                logging.error(error_msg)
        sys.exit(1)
    except (NotImplementedError, RuntimeError) as e:
        error_msg = f"Error de ejecución: {e}"
        if has_console:
            print(f"\n❌ {error_msg}")
            if args.debug or args.verbose:
                import traceback
                traceback.print_exc()
        else:
            # En modo windowed, mostrar diálogo de error
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    error_msg,
                    "Viboy Color - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                logging.error(error_msg)
        sys.exit(1)
    except Exception as e:
        # Capturar TODAS las demás excepciones (ImportError, AttributeError, etc.)
        error_msg = f"Error inesperado: {e}"
        if has_console:
            print(f"\n❌ {error_msg}")
            print("\nTraceback completo:")
            import traceback
            traceback.print_exc()
            print("\n💡 Sugerencias:")
            print("   - Ejecuta con --verbose para más información")
            print("   - Ejecuta con --debug para trazas detalladas")
            print("   - Verifica que todas las dependencias estén instaladas: pip install -r requirements.txt")
        else:
            # En modo windowed, mostrar diálogo de error
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{error_msg}\n\nRevisa la consola para más detalles.",
                    "Viboy Color - Error",
                    0x10  # MB_ICONERROR
                )
            except Exception:
                logging.error(error_msg, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

