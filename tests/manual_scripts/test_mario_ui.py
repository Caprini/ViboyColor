#!/usr/bin/env python3
"""
Script de prueba para mario.gbc con UI
Captura logs de renderizado y estado del juego
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
    print("▶️  Ejecutando con UI (presiona Ctrl+C para detener después de unos segundos)\n")
    
    try:
        viboy = Viboy(rom_path)
        
        # Información del cartucho
        cartridge = viboy.get_cartridge()
        if cartridge is not None:
            header_info = cartridge.get_header_info()
            print(f"📦 Cartucho: {header_info['title']} ({header_info['cartridge_type']})")
        
        # Ejecutar bucle principal (con UI)
        # Esto abrirá una ventana Pygame
        viboy.run(debug=False)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Detenido por el usuario")
        cpu = viboy.get_cpu()
        if cpu is not None:
            print(f"   PC final = 0x{cpu.registers.get_pc():04X}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

