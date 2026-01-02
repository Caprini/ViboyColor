#!/usr/bin/env python3
"""
Step 0434 - Script de Triage

Ejecuta el emulador con instrumentación de triage activada para capturar evidencia
de por qué Pokémon Red tiene VRAM vacía.
"""

import sys
from pathlib import Path

# Añadir src al path para importar viboy_core
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from viboy_core import PyMMU, PyRegisters, PyCPU, PyPPU
except ImportError as e:
    print(f"Error: No se pudo importar viboy_core: {e}")
    print("Asegúrate de haber compilado con: python setup.py build_ext --inplace")
    sys.exit(1)

def main():
    print("=== Step 0434 - Triage VRAM vacía ===\n")
    
    # Cargar ROM de Pokémon Red
    rom_path = Path("/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb")
    if not rom_path.exists():
        print(f"Error: ROM no encontrada: {rom_path}")
        sys.exit(1)
    
    rom_data = rom_path.read_bytes()
    print(f"ROM cargada: {len(rom_data)} bytes\n")
    
    # Crear componentes del emulador
    regs = PyRegisters()
    mmu = PyMMU()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # Conectar componentes
    mmu.set_ppu(ppu)
    cpu.set_ppu(ppu)
    
    # Cargar ROM
    mmu.load_rom_py(rom_data)
    
    # Activar triage mode (120 frames límite)
    print("[TRIAGE] Activando triage mode...\n")
    cpu.set_triage_mode(True, 120)
    
    # Ejecutar por 120 frames o ~2M ciclos (lo que ocurra primero)
    # 120 frames = 120 × 70224 ciclos = 8,426,880 T-cycles
    # Pero vamos a limitar a 500K T-cycles (~7 frames) para no saturar
    max_t_cycles = 500000
    frame_count = 0
    max_frames = 120
    
    print("[TRIAGE] Ejecutando emulador (max 500K T-cycles o 120 frames)...\n")
    
    try:
        total_t_cycles = 0
        while frame_count < max_frames and total_t_cycles < max_t_cycles:
            # Ejecutar una scanline (456 T-cycles)
            cpu.run_scanline()
            total_t_cycles += 456
            
            # Cada 154 scanlines = 1 frame
            if ppu.get_ly() == 0 and total_t_cycles > 0:
                frame_count += 1
                if frame_count % 10 == 0:
                    print(f"[TRIAGE] Frame {frame_count}, T-cycles: {total_t_cycles}")
        
        print(f"\n[TRIAGE] Ejecución completada: {frame_count} frames, {total_t_cycles} T-cycles\n")
        
    except KeyboardInterrupt:
        print("\n[TRIAGE] Interrumpido por usuario\n")
    except Exception as e:
        print(f"\n[TRIAGE] Error durante ejecución: {e}\n")
    
    # Generar resumen de triage
    print("=== RESUMEN DE TRIAGE ===\n")
    cpu.log_triage_summary()
    
    print("\n=== Triage completado ===")

if __name__ == "__main__":
    main()

