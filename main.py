#!/usr/bin/env python3
"""
Viboy Color - Emulador de Game Boy Color
Punto de entrada principal del emulador
"""

import argparse
import logging
import sys
from pathlib import Path

from src.cpu.core import CPU
from src.memory.cartridge import Cartridge
from src.memory.mmu import MMU

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
        help="Activar logging en modo DEBUG",
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
        print("Uso: python main.py <ruta_a_rom.gb>")
        sys.exit(1)
    
    # Cargar cartucho
    try:
        cartridge = Cartridge(args.rom)
        header_info = cartridge.get_header_info()
        
        print(f"\n📦 Cartucho cargado:")
        print(f"   Título: {header_info['title']}")
        print(f"   Tipo: {header_info['cartridge_type']}")
        print(f"   ROM: {header_info['rom_size']} KB")
        print(f"   RAM: {header_info['ram_size']} KB")
        print(f"   Tamaño total: {cartridge.get_rom_size()} bytes")
        
    except (FileNotFoundError, IOError, ValueError) as e:
        print(f"\n❌ Error al cargar ROM: {e}")
        sys.exit(1)
    
    # Inicializar MMU con el cartucho
    mmu = MMU(cartridge)
    
    # Inicializar CPU
    cpu = CPU(mmu)
    
    # Simular "Post-Boot State" (sin Boot ROM)
    # En un Game Boy real, la Boot ROM inicializa:
    # - PC = 0x0100 (inicio del código del cartucho)
    # - SP = 0xFFFE (top de la pila)
    # - Registros con valores específicos
    # Por ahora, inicializamos valores básicos
    cpu.registers.set_pc(0x0100)  # Inicio del código del cartucho
    cpu.registers.set_sp(0xFFFE)   # Top de la pila
    
    print(f"\n🖥️  CPU inicializada:")
    print(f"   PC = 0x{cpu.registers.get_pc():04X}")
    print(f"   SP = 0x{cpu.registers.get_sp():04X}")
    
    print("\n✅ Sistema listo para ejecutar")
    print("   (Bucle principal de ejecución pendiente de implementar)")


if __name__ == "__main__":
    main()

