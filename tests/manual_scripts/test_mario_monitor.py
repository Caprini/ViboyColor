#!/usr/bin/env python3
"""
Script de monitoreo para mario.gbc
Monitorea cambios en LCDC, BGP, SCX, SCY y captura errores
"""

import sys
import logging
from pathlib import Path

# Ajustar ruta para importar desde la raíz del proyecto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configurar logging solo para errores
logging.basicConfig(
    level=logging.ERROR,
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
            print(f"📦 Cartucho: {header_info['title']} ({header_info['cartridge_type']})")
        
        cpu = viboy.get_cpu()
        mmu = viboy._mmu
        
        if cpu is None or mmu is None:
            print("❌ Sistema no inicializado correctamente")
            sys.exit(1)
        
        print(f"🖥️  CPU inicializada: PC=0x{cpu.registers.get_pc():04X}, SP=0x{cpu.registers.get_sp():04X}")
        print("\n▶️  Ejecutando y monitoreando cambios en registros I/O...\n")
        
        # Estado anterior de registros
        prev_lcdc = None
        prev_bgp = None
        prev_scx = None
        prev_scy = None
        
        # Contadores
        max_cycles = 1_000_000
        cycles_executed = 0
        errors = []
        lcdc_changes = []
        bgp_changes = []
        
        # Ejecutar ciclos
        while cycles_executed < max_cycles:
            try:
                cycles = viboy.tick()
                cycles_executed += cycles
                
                # Leer registros I/O cada 1000 ciclos (para no saturar)
                if cycles_executed % 1000 == 0:
                    lcdc = mmu.read_byte(0xFF40) & 0xFF
                    bgp = mmu.read_byte(0xFF47) & 0xFF
                    scx = mmu.read_byte(0xFF43) & 0xFF
                    scy = mmu.read_byte(0xFF42) & 0xFF
                    
                    # Detectar cambios
                    if prev_lcdc is not None and lcdc != prev_lcdc:
                        lcdc_changes.append((cycles_executed, prev_lcdc, lcdc))
                        print(f"🔄 LCDC cambió: 0x{prev_lcdc:02X} -> 0x{lcdc:02X} (ciclo {cycles_executed:,})")
                        print(f"   Bit 7 (LCD): {prev_lcdc>>7} -> {lcdc>>7}")
                        print(f"   Bit 0 (BG): {prev_lcdc&1} -> {lcdc&1}")
                    
                    if prev_bgp is not None and bgp != prev_bgp:
                        bgp_changes.append((cycles_executed, prev_bgp, bgp))
                        print(f"🔄 BGP cambió: 0x{prev_bgp:02X} -> 0x{bgp:02X} (ciclo {cycles_executed:,})")
                    
                    prev_lcdc = lcdc
                    prev_bgp = bgp
                    prev_scx = scx
                    prev_scy = scy
                
            except NotImplementedError as e:
                error_msg = str(e)
                errors.append((cycles_executed, error_msg))
                pc = cpu.registers.get_pc()
                print(f"❌ ERROR: {error_msg}")
                print(f"   PC = 0x{pc:04X}, Ciclos = {cycles_executed:,}")
                # Continuar para capturar más errores
            except Exception as e:
                error_msg = str(e)
                errors.append((cycles_executed, error_msg))
                pc = cpu.registers.get_pc()
                print(f"❌ ERROR INESPERADO: {error_msg}")
                print(f"   PC = 0x{pc:04X}, Ciclos = {cycles_executed:,}")
                # Continuar para capturar más errores
        
        # Resumen final
        print(f"\n{'='*60}")
        print(f"📊 RESUMEN")
        print(f"{'='*60}")
        print(f"✅ Ejecutados {cycles_executed:,} ciclos")
        print(f"   PC final = 0x{cpu.registers.get_pc():04X}")
        print(f"   SP final = 0x{cpu.registers.get_sp():04X}")
        
        # Estado final de registros
        lcdc = mmu.read_byte(0xFF40) & 0xFF
        bgp = mmu.read_byte(0xFF47) & 0xFF
        scx = mmu.read_byte(0xFF43) & 0xFF
        scy = mmu.read_byte(0xFF42) & 0xFF
        print(f"\n📊 Estado final de registros I/O:")
        print(f"   LCDC = 0x{lcdc:02X} (bit 7={lcdc>>7} LCD, bit 0={lcdc&1} BG)")
        print(f"   BGP = 0x{bgp:02X}")
        print(f"   SCX = 0x{scx:02X} ({scx})")
        print(f"   SCY = 0x{scy:02X} ({scy})")
        
        # Cambios detectados
        if lcdc_changes:
            print(f"\n🔄 Cambios en LCDC: {len(lcdc_changes)}")
            for cycle, old, new in lcdc_changes[:5]:  # Mostrar primeros 5
                print(f"   Ciclo {cycle:,}: 0x{old:02X} -> 0x{new:02X}")
        else:
            print(f"\n⚠️  No se detectaron cambios en LCDC")
        
        if bgp_changes:
            print(f"\n🔄 Cambios en BGP: {len(bgp_changes)}")
            for cycle, old, new in bgp_changes[:5]:  # Mostrar primeros 5
                print(f"   Ciclo {cycle:,}: 0x{old:02X} -> 0x{new:02X}")
        
        if errors:
            print(f"\n❌ Errores encontrados: {len(errors)}")
            for cycle, error in errors[:10]:  # Mostrar primeros 10
                print(f"   Ciclo {cycle:,}: {error}")
            if len(errors) > 10:
                print(f"   ... y {len(errors) - 10} más")
        else:
            print(f"\n✅ No se encontraron errores de opcodes no implementados")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Detenido por el usuario")
        if cpu is not None:
            print(f"   PC final = 0x{cpu.registers.get_pc():04X}")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

