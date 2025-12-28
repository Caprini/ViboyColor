#!/usr/bin/env python3
"""
Script de prueba visual para mario.gbc
Ejecuta el emulador con UI y captura información sobre el renderizado
"""

import sys
import logging
import time
from pathlib import Path

# Ajustar ruta para importar desde la raíz del proyecto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configurar logging para INFO (capturar logs de renderizado)
logging.basicConfig(
    level=logging.INFO,
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
    print("▶️  Ejecutando con UI...")
    print("   - La ventana se abrirá automáticamente")
    print("   - Presiona Ctrl+C para detener después de unos segundos")
    print("   - Observa si se muestran gráficos en la pantalla\n")
    
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
        
        print(f"🖥️  CPU inicializada: PC=0x{cpu.registers.get_pc():04X}")
        print("\n▶️  Iniciando bucle de ejecución...\n")
        
        # Ejecutar durante un tiempo limitado para capturar información
        max_seconds = 10
        start_time = time.time()
        frame_count = 0
        last_pc = cpu.registers.get_pc()
        cycles_without_progress = 0
        
        # Estado de registros para monitoreo
        prev_lcdc = None
        
        try:
            while time.time() - start_time < max_seconds:
                # Ejecutar algunos ciclos
                for _ in range(1000):
                    try:
                        cycles = viboy.tick()
                        
                        # Monitorear cambios en LCDC
                        if mmu is not None:
                            lcdc = mmu.read_byte(0xFF40) & 0xFF
                            if prev_lcdc is not None and lcdc != prev_lcdc:
                                print(f"🔄 LCDC cambió: 0x{prev_lcdc:02X} -> 0x{lcdc:02X}")
                                print(f"   Bit 7 (LCD): {prev_lcdc>>7} -> {lcdc>>7}")
                                print(f"   Bit 0 (BG): {prev_lcdc&1} -> {lcdc&1}")
                            prev_lcdc = lcdc
                        
                        # Detectar si el juego está atascado
                        current_pc = cpu.registers.get_pc()
                        if current_pc == last_pc:
                            cycles_without_progress += cycles
                        else:
                            cycles_without_progress = 0
                            last_pc = current_pc
                        
                        # Si está atascado por mucho tiempo, mostrar advertencia
                        if cycles_without_progress > 100000:
                            print(f"⚠️  Posible bucle infinito detectado (PC=0x{current_pc:04X})")
                            cycles_without_progress = 0
                            
                    except NotImplementedError as e:
                        print(f"❌ ERROR: {e}")
                        print(f"   PC = 0x{cpu.registers.get_pc():04X}")
                        break
                    except Exception as e:
                        print(f"❌ ERROR INESPERADO: {e}")
                        import traceback
                        traceback.print_exc()
                        break
                
                # Pequeña pausa para no saturar la CPU
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Detenido por el usuario")
        
        # Estado final
        print(f"\n{'='*60}")
        print(f"📊 ESTADO FINAL")
        print(f"{'='*60}")
        print(f"   PC = 0x{cpu.registers.get_pc():04X}")
        print(f"   SP = 0x{cpu.registers.get_sp():04X}")
        
        if mmu is not None:
            lcdc = mmu.read_byte(0xFF40) & 0xFF
            bgp = mmu.read_byte(0xFF47) & 0xFF
            scx = mmu.read_byte(0xFF43) & 0xFF
            scy = mmu.read_byte(0xFF42) & 0xFF
            
            print(f"\n📊 Registros I/O:")
            print(f"   LCDC = 0x{lcdc:02X} (bit 7={lcdc>>7} LCD, bit 0={lcdc&1} BG)")
            print(f"   BGP = 0x{bgp:02X}")
            print(f"   SCX = 0x{scx:02X} ({scx})")
            print(f"   SCY = 0x{scy:02X} ({scy})")
            
            if lcdc & 0x80:
                print(f"\n✅ LCD está ACTIVO - Deberías ver gráficos en la ventana")
            else:
                print(f"\n⚠️  LCD está INACTIVO - Pantalla debería estar blanca")
        
        print(f"\n💡 Si viste gráficos en la ventana, el renderizado funciona correctamente")
        print(f"💡 Si solo viste pantalla blanca, revisa los logs de renderizado arriba")
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

