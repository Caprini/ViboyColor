#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Profile Viboy - Script de Perfilado de Rendimiento

Este script ejecuta el emulador en modo headless durante 10 segundos
y muestra un análisis de las funciones que más tiempo consumen.

Uso:
    python tools/profile_viboy.py [ruta_rom.gb]

Si no se especifica ROM, intenta cargar tetris.gb desde la raíz del proyecto.
"""

import cProfile
import logging
import pstats
import sys
import time
from pathlib import Path
from io import StringIO

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Añadir raíz del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.viboy import Viboy

# Desactivar logging para máximo rendimiento
logging.basicConfig(
    level=logging.CRITICAL,  # Solo errores críticos
    format="%(message)s",
    force=True,
)


def run_emulator_headless(viboy: Viboy, duration_seconds: int = 10) -> None:
    """
    Ejecuta el emulador en modo headless (sin interfaz gráfica) durante
    un tiempo determinado.
    
    Args:
        viboy: Instancia del emulador Viboy
        duration_seconds: Segundos de ejecución
    """
    start_time = time.time()
    cycles_count = 0
    target_cycles_per_frame = 70224  # T-Cycles por frame
    frame_cycles = 0
    
    print(f"Ejecutando emulador en modo headless durante {duration_seconds} segundos...")
    print("(Sin renderizado gráfico, solo cálculo CPU/PPU/Timer)\n")
    
    try:
        while (time.time() - start_time) < duration_seconds:
            # Ejecutar un tick (una instrucción)
            # Nota: tick() ya avanza PPU y Timer internamente
            cycles = viboy.tick()
            
            # Protección contra 0 ciclos
            if cycles == 0:
                cycles = 4
            
            # Convertir M-Cycles a T-Cycles para contabilizar frames
            t_cycles = cycles * 4
            
            # Acumular ciclos del frame
            frame_cycles += t_cycles
            cycles_count += cycles
            
            # Si completamos un frame, resetear contador
            # (No renderizamos, pero mantenemos el timing)
            if frame_cycles >= target_cycles_per_frame:
                frame_cycles = 0
                
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario")
    
    elapsed = time.time() - start_time
    print(f"\nEjecución completada:")
    print(f"  Tiempo real: {elapsed:.2f} segundos")
    print(f"  M-Cycles ejecutados: {cycles_count:,}")
    print(f"  M-Cycles/segundo: {cycles_count / elapsed:,.0f}")
    print(f"  T-Cycles/segundo: {(cycles_count * 4) / elapsed:,.0f}")
    print(f"  FPS teórico: {(cycles_count * 4) / elapsed / target_cycles_per_frame:.1f}\n")


def main() -> None:
    """Función principal del script de perfilado"""
    # Determinar ruta de ROM
    if len(sys.argv) > 1:
        rom_path = Path(sys.argv[1])
    else:
        # Buscar tetris.gb en la raíz del proyecto
        rom_path = project_root / "tetris.gb"
    
    if not rom_path.exists():
        print(f"❌ Error: No se encontró la ROM en: {rom_path}")
        print(f"   Uso: python tools/profile_viboy.py [ruta_rom.gb]")
        sys.exit(1)
    
    print("=" * 70)
    print("Viboy Color - Perfilado de Rendimiento (cProfile)")
    print("=" * 70)
    print(f"ROM: {rom_path.name}")
    print()
    
    # Crear perfilador
    profiler = cProfile.Profile()
    
    # Cargar emulador (fuera del perfilado para no medir inicialización)
    print("Cargando emulador...")
    viboy = Viboy(rom_path)
    print("✅ Emulador cargado\n")
    
    # Ejecutar con perfilado
    print("Iniciando perfilado...\n")
    profiler.enable()
    
    try:
        run_emulator_headless(viboy, duration_seconds=10)
    finally:
        profiler.disable()
    
    # Generar estadísticas
    print("=" * 70)
    print("ANÁLISIS DE RENDIMIENTO - Top 20 funciones por tiempo acumulado")
    print("=" * 70)
    print()
    
    # Crear buffer para capturar salida de pstats
    stats_buffer = StringIO()
    stats = pstats.Stats(profiler, stream=stats_buffer)
    
    # Ordenar por tiempo acumulado (cumtime) y mostrar top 20
    stats.sort_stats('cumulative')
    stats.print_stats(20)
    
    # Mostrar resultados
    output = stats_buffer.getvalue()
    print(output)
    
    # También mostrar por tiempo propio (tottime)
    print("=" * 70)
    print("Top 20 funciones por tiempo propio (excluyendo subllamadas)")
    print("=" * 70)
    print()
    
    stats_buffer2 = StringIO()
    stats2 = pstats.Stats(profiler, stream=stats_buffer2)
    stats2.sort_stats('tottime')
    stats2.print_stats(20)
    
    print(stats_buffer2.getvalue())
    
    print("=" * 70)
    print("Perfilado completado.")
    print("=" * 70)


if __name__ == "__main__":
    main()

