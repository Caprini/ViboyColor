#!/usr/bin/env python3
"""
Viboy Color - Emulador de Game Boy Color
Punto de entrada principal del emulador
"""

import argparse
import logging
import sys
from pathlib import Path

from src.viboy import Viboy

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


def main() -> None:
    """Función principal del emulador"""
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
    
    args = parser.parse_args()
    
    # Si se especifica --debug, cambiar nivel de logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("Viboy Color - Sistema Iniciado")
    print("=" * 50)
    
    # Si no se proporciona ROM, mostrar mensaje y salir
    if not args.rom:
        print("Error: Se requiere especificar una ROM")
        print("Uso: python main.py <ruta_a_rom.gb> [--debug]")
        sys.exit(1)
    
    # Inicializar sistema Viboy
    try:
        viboy = Viboy(args.rom)
        
        # Obtener información del cartucho
        cartridge = viboy.get_cartridge()
        if cartridge is not None:
            header_info = cartridge.get_header_info()
            
            print(f"\n📦 Cartucho cargado:")
            print(f"   Título: {header_info['title']}")
            print(f"   Tipo: {header_info['cartridge_type']}")
            print(f"   ROM: {header_info['rom_size']} KB")
            print(f"   RAM: {header_info['ram_size']} KB")
            print(f"   Tamaño total: {cartridge.get_rom_size()} bytes")
        
        # Obtener estado inicial de la CPU
        cpu = viboy.get_cpu()
        if cpu is not None:
            print(f"\n🖥️  CPU inicializada:")
            print(f"   PC = 0x{cpu.registers.get_pc():04X}")
            print(f"   SP = 0x{cpu.registers.get_sp():04X}")
        
        print("\n✅ Sistema listo para ejecutar")
        if args.debug:
            print("   Modo DEBUG activado - Mostrando trazas de instrucciones")
            print("   Presiona Ctrl+C para detener\n")
        else:
            print("   Presiona Ctrl+C para detener\n")
        
        # Ejecutar bucle principal
        viboy.run(debug=args.debug)
        
    except (FileNotFoundError, IOError, ValueError) as e:
        print(f"\n❌ Error al cargar ROM: {e}")
        sys.exit(1)
    except (NotImplementedError, RuntimeError) as e:
        # Errores de ejecución (opcode no implementado, etc.)
        sys.exit(1)


if __name__ == "__main__":
    main()

