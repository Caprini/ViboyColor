#!/usr/bin/env python3
"""
Script de prueba para mario.gbc
Captura errores y logs relevantes
"""

import sys
import logging
from pathlib import Path

# Ajustar ruta para importar desde la raíz del proyecto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configurar logging para capturar errores
logging.basicConfig(
    level=logging.WARNING,  # Solo WARNING y ERROR
    format='%(levelname)s: %(message)s'
)

from src.viboy import Viboy

def main():
    # ROM en la carpeta roms/
    rom_path = project_root / "roms" / "mario.gbc"
    
    if not rom_path.exists():
        print(f"❌ ROM no encontrada: {rom_path}")
        sys.exit(1)
    
    print(f"📦 Cargando ROM: {rom_path}")
    
    try:
        viboy = Viboy(rom_path)
        
        # Información del cartucho
        cartridge = viboy.get_cartridge()
        if cartridge is not None:
            header_info = cartridge.get_header_info()
            print(f"\n📦 Cartucho cargado:")
            print(f"   Título: {header_info['title']}")
            print(f"   Tipo: {header_info['cartridge_type']}")
            print(f"   ROM: {header_info['rom_size']} KB")
        
        cpu = viboy.get_cpu()
        if cpu is not None:
            cpu = viboy.get_cpu()
            print(f"\n🖥️  CPU inicializada:")
            print(f"   PC = 0x{cpu.registers.get_pc():04X}")
            print(f"   SP = 0x{cpu.registers.get_sp():04X}")
        
        print("\n▶️  Ejecutando 100,000 ciclos...")
        print("   (Capturando errores y opcodes no implementados)\n")
        
        # Ejecutar ciclos limitados
        max_cycles = 500_000
        cycles_executed = 0
        errors = []
        
        while cycles_executed < max_cycles:
            try:
                cycles = viboy.tick()
                cycles_executed += cycles
            except NotImplementedError as e:
                error_msg = str(e)
                errors.append(error_msg)
                cpu = viboy.get_cpu()
                if cpu is not None:
                    pc = cpu.registers.get_pc()
                    print(f"❌ ERROR: {error_msg}")
                    print(f"   PC = 0x{pc:04X}")
                    # Continuar para capturar más errores
                    # sys.exit(1)
            except Exception as e:
                print(f"❌ ERROR INESPERADO: {e}")
                cpu = viboy.get_cpu()
                if cpu is not None:
                    print(f"   PC = 0x{cpu.registers.get_pc():04X}")
                sys.exit(1)
        
        cpu = viboy.get_cpu()
        if cpu is not None:
            print(f"\n✅ Ejecutados {cycles_executed:,} ciclos")
            print(f"   PC final = 0x{cpu.registers.get_pc():04X}")
            print(f"   SP final = 0x{cpu.registers.get_sp():04X}")
            
            # Verificar estado de registros importantes
            mmu = viboy._mmu
            if mmu is not None:
                lcdc = mmu.read_byte(0xFF40)
                bgp = mmu.read_byte(0xFF47)
                scx = mmu.read_byte(0xFF43)
                scy = mmu.read_byte(0xFF42)
                print(f"\n📊 Estado de registros I/O:")
                print(f"   LCDC = 0x{lcdc:02X} (bit 7={lcdc>>7}, bit 0={lcdc&1})")
                print(f"   BGP = 0x{bgp:02X}")
                print(f"   SCX = 0x{scx:02X} ({scx})")
                print(f"   SCY = 0x{scy:02X} ({scy})")
        
        if errors:
            print(f"\n⚠️  Errores encontrados ({len(errors)}):")
            for i, error in enumerate(errors[:10], 1):  # Mostrar solo los primeros 10
                print(f"   {i}. {error}")
            if len(errors) > 10:
                print(f"   ... y {len(errors) - 10} más")
        else:
            print("\n✅ No se encontraron errores de opcodes no implementados")
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

