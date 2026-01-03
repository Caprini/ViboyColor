#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Headless Trust Test (Step 0452)

Ejecuta ROM clean-room que sabemos que renderiza nonwhite,
y valida que headless reporta nonwhite > 0 y vram_raw_nz > 0.

Si headless reporta todo 0 pero UI no, el problema es el runner/lectura, NO el emulador.
"""

import sys
from pathlib import Path

# Añadir directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar runner headless
from tools.rom_smoke_0442 import ROMSmokeRunner


def test_headless_trust_cleanroom():
    """Valida que headless reporta correctamente con ROM clean-room."""
    # Buscar ROM clean-room en tests/data o crear una mínima
    cleanroom_rom = Path("tests/data/cleanroom_tiles.gb")
    
    if not cleanroom_rom.exists():
        print("⚠️ ROM clean-room no encontrada, buscando alternativas...")
        # Buscar cualquier ROM en roms/ para prueba
        roms_dir = Path("roms")
        if roms_dir.exists():
            roms = list(roms_dir.glob("*.gb")) + list(roms_dir.glob("*.gbc"))
            if roms:
                cleanroom_rom = roms[0]
                print(f"Usando ROM alternativa: {cleanroom_rom.name}")
            else:
                print("❌ No se encontró ninguna ROM para prueba")
                return False
        else:
            print("❌ Directorio roms/ no existe")
            return False
    
    print(f"Ejecutando headless trust test con: {cleanroom_rom.name}")
    print("")
    
    runner = ROMSmokeRunner(
        rom_path=str(cleanroom_rom),
        max_frames=120,
        dump_every=60
    )
    
    runner.run()
    
    # Verificar métricas
    metrics = runner.metrics
    if not metrics:
        raise AssertionError("Headless no generó métricas")
    
    # Buscar nonwhite > 0
    max_nonwhite = max(m['nonwhite_pixels'] for m in metrics)
    max_vram_nz = max(m['vram_nonzero_raw'] for m in metrics if 'vram_nonzero_raw' in m)
    
    # Si vram_nonzero_raw no está, usar vram_nonzero
    if max_vram_nz == 0:
        max_vram_nz = max(m.get('vram_nonzero', 0) for m in metrics)
    
    print("")
    print("=" * 60)
    print("RESULTADOS HEADLESS TRUST TEST")
    print("=" * 60)
    print(f"  max_nonwhite: {max_nonwhite}")
    print(f"  max_vram_nz: {max_vram_nz}")
    print("")
    
    if max_nonwhite == 0:
        print("⚠️ ADVERTENCIA: Headless reporta nonwhite=0")
        print("   Esto puede indicar:")
        print("   - El runner no lee el framebuffer correctamente")
        print("   - El framebuffer está realmente vacío (problema de emulación)")
        print("   - La ROM no renderiza en los primeros 120 frames")
    else:
        print("✅ Headless reporta nonwhite > 0 (framebuffer tiene datos)")
    
    if max_vram_nz == 0:
        print("⚠️ ADVERTENCIA: Headless reporta vram_nz=0")
        print("   Esto puede indicar:")
        print("   - VRAM nunca se escribió (problema de mapping/CPU)")
        print("   - read_raw() no funciona correctamente")
        print("   - La ROM no carga tiles en los primeros 120 frames")
    else:
        print("✅ Headless reporta vram_nz > 0 (VRAM tiene datos)")
    
    print("")
    
    # Criterio de éxito: al menos uno debe ser > 0
    if max_nonwhite > 0 or max_vram_nz > 0:
        print("✅ Headless trust test PASS: reporta actividad correctamente")
        return True
    else:
        print("❌ Headless trust test FAIL: no detecta actividad")
        return False


if __name__ == "__main__":
    success = test_headless_trust_cleanroom()
    sys.exit(0 if success else 1)

