#!/usr/bin/env python3
"""
Script para verificar el renderizado visual de mario.gbc
Ejecuta el emulador y captura información sobre el renderizado
"""

import sys
import logging
from pathlib import Path

# Ajustar ruta para importar desde la raíz del proyecto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configurar logging para INFO (capturar logs de renderizado)
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

print("="*70)
print("VERIFICACIÓN DE RENDERIZADO - Mario.gbc")
print("="*70)
print("\nEste script ejecutará el emulador y mostrará información sobre:")
print("  - Estado de LCDC (LCD Enable, Background Enable)")
print("  - Estado de BGP (paleta)")
print("  - Logs de renderizado")
print("  - Diagnósticos de VRAM/Tilemap")
print("\nLa ventana Pygame se abrirá automáticamente.")
print("Presiona Ctrl+C después de unos segundos para detener.\n")
print("="*70)
print()

from src.viboy import Viboy

def main():
    # ROM en la carpeta roms/
    rom_path = project_root / "roms" / "mario.gbc"
    
    if not rom_path.exists():
        print(f"❌ ROM no encontrada: {rom_path}")
        sys.exit(1)
    
    try:
        viboy = Viboy(rom_path)
        
        # Información del cartucho
        cartridge = viboy.get_cartridge()
        if cartridge is not None:
            header_info = cartridge.get_header_info()
            print(f"📦 Cartucho: {header_info['title']}")
        
        cpu = viboy.get_cpu()
        if cpu is not None:
            print(f"🖥️  CPU inicializada: PC=0x{cpu.registers.get_pc():04X}\n")
        
        print("▶️  Iniciando emulador...")
        print("   Observa la ventana Pygame y los logs de renderizado abajo.\n")
        print("-" * 70)
        
        # Ejecutar bucle principal (con UI)
        # Esto abrirá una ventana Pygame y mostrará los logs
        viboy.run(debug=False)
        
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("⏹️  DETENIDO POR EL USUARIO")
        print("="*70)
        cpu = viboy.get_cpu()
        mmu = viboy._mmu
        if cpu is not None and mmu is not None:
            lcdc = mmu.read_byte(0xFF40) & 0xFF
            bgp = mmu.read_byte(0xFF47) & 0xFF
            print(f"\n📊 Estado final:")
            print(f"   PC = 0x{cpu.registers.get_pc():04X}")
            print(f"   LCDC = 0x{lcdc:02X} (bit 7={lcdc>>7} LCD, bit 0={lcdc&1} BG)")
            print(f"   BGP = 0x{bgp:02X}")
            print("\n💡 Revisa los logs de renderizado arriba para ver:")
            print("   - Si se renderizaron frames")
            print("   - Estado de VRAM/Tilemap")
            print("   - Si hubo errores de renderizado")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

