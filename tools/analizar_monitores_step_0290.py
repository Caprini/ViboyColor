#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Análisis de Monitores del Step 0290
Analiza los logs del emulador para extraer información de los nuevos monitores:
- [LCDC-CHANGE]: Cambios en el registro LCDC
- [PALETTE-APPLY]: Aplicación de la paleta BGP durante el renderizado
- [TILE-LOAD]: Carga de tiles en VRAM (CRÍTICO)
"""

import sys
from pathlib import Path
from collections import defaultdict

def analizar_lcdc_change(lineas):
    """Analiza los logs de [LCDC-CHANGE]"""
    cambios = []
    for linea in lineas:
        if '[LCDC-CHANGE]' in linea:
            cambios.append(linea.strip())
    return cambios

def analizar_palette_apply(lineas):
    """Analiza los logs de [PALETTE-APPLY]"""
    aplicaciones = []
    for linea in lineas:
        if '[PALETTE-APPLY]' in linea:
            aplicaciones.append(linea.strip())
    return aplicaciones

def analizar_tile_load(lineas):
    """Analiza los logs de [TILE-LOAD] (CRÍTICO)"""
    cargas = []
    tile_ids_cargados = defaultdict(int)
    pcs_carga = defaultdict(int)
    
    for linea in lineas:
        if '[TILE-LOAD]' in linea:
            cargas.append(linea.strip())
            # Extraer Tile ID aproximado del log
            # Formato: [TILE-LOAD] Write 8000=XX (TileID~N, Byte:M) PC:XXXX (Bank:B)
            try:
                # Buscar TileID~ en la línea
                if 'TileID~' in linea:
                    idx = linea.find('TileID~')
                    if idx != -1:
                        # Extraer el número después de TileID~
                        tile_id_str = ''
                        idx += len('TileID~')
                        while idx < len(linea) and linea[idx].isdigit():
                            tile_id_str += linea[idx]
                            idx += 1
                        if tile_id_str:
                            tile_id = int(tile_id_str)
                            tile_ids_cargados[tile_id] += 1
                
                # Extraer PC
                if 'PC:' in linea:
                    idx = linea.find('PC:')
                    if idx != -1:
                        pc_str = ''
                        idx += len('PC:')
                        while idx < len(linea) and (linea[idx].isdigit() or linea[idx] in 'ABCDEFabcdef'):
                            pc_str += linea[idx]
                            idx += 1
                        if pc_str:
                            pc = int(pc_str, 16)
                            pcs_carga[pc] += 1
            except:
                pass
    
    return cargas, tile_ids_cargados, pcs_carga

def main():
    if len(sys.argv) < 2:
        print("Uso: python analizar_monitores_step_0290.py <archivo_log>")
        print("\nEjemplo:")
        print("  python main.py roms/pkmn.gb > debug_step_0290.log 2>&1")
        print("  python tools/analizar_monitores_step_0290.py debug_step_0290.log")
        sys.exit(1)
    
    archivo_log = Path(sys.argv[1])
    if not archivo_log.exists():
        print(f"Error: El archivo {archivo_log} no existe")
        sys.exit(1)
    
    print("=" * 80)
    print("ANÁLISIS DE MONITORES DEL STEP 0290")
    print("=" * 80)
    print(f"Archivo de log: {archivo_log}")
    print()
    
    # Leer el archivo de log
    with open(archivo_log, 'r', encoding='utf-8', errors='ignore') as f:
        lineas = f.readlines()
    
    print(f"Total de líneas en el log: {len(lineas)}")
    print()
    
    # Analizar [LCDC-CHANGE]
    print("-" * 80)
    print("1. MONITOR [LCDC-CHANGE] - Cambios en el Registro LCDC")
    print("-" * 80)
    cambios_lcdc = analizar_lcdc_change(lineas)
    print(f"Total de cambios detectados: {len(cambios_lcdc)}")
    if cambios_lcdc:
        print("\nPrimeros 10 cambios:")
        for cambio in cambios_lcdc[:10]:
            print(f"  {cambio}")
        if len(cambios_lcdc) > 10:
            print(f"  ... y {len(cambios_lcdc) - 10} cambios más")
    else:
        print("  [WARNING] NO se detectaron cambios en LCDC")
    print()
    
    # Analizar [PALETTE-APPLY]
    print("-" * 80)
    print("2. MONITOR [PALETTE-APPLY] - Aplicación de Paleta BGP")
    print("-" * 80)
    aplicaciones_paleta = analizar_palette_apply(lineas)
    print(f"Total de aplicaciones detectadas: {len(aplicaciones_paleta)}")
    if aplicaciones_paleta:
        print("\nTodas las aplicaciones (máximo 3 por diseño):")
        for aplicacion in aplicaciones_paleta:
            print(f"  {aplicacion}")
    else:
        print("  [WARNING] NO se detectaron aplicaciones de paleta")
    print()
    
    # Analizar [TILE-LOAD] (CRÍTICO)
    print("-" * 80)
    print("3. MONITOR [TILE-LOAD] - Carga de Tiles en VRAM (CRÍTICO)")
    print("-" * 80)
    cargas_tiles, tile_ids_cargados, pcs_carga = analizar_tile_load(lineas)
    print(f"Total de cargas de tiles detectadas: {len(cargas_tiles)}")
    
    if cargas_tiles:
        print(f"\n✅ SE DETECTARON ESCRITURAS DE TILES EN VRAM")
        print(f"\nPrimeras 20 cargas:")
        for carga in cargas_tiles[:20]:
            print(f"  {carga}")
        if len(cargas_tiles) > 20:
            print(f"  ... y {len(cargas_tiles) - 20} cargas más")
        
        if tile_ids_cargados:
            print(f"\nTile IDs únicos cargados: {len(tile_ids_cargados)}")
            print("Top 10 Tile IDs más cargados:")
            sorted_tiles = sorted(tile_ids_cargados.items(), key=lambda x: x[1], reverse=True)
            for tile_id, count in sorted_tiles[:10]:
                print(f"  Tile ID {tile_id}: {count} escrituras")
        
        if pcs_carga:
            print(f"\nPCs únicos que cargan tiles: {len(pcs_carga)}")
            print("Top 10 PCs que más cargan tiles:")
            sorted_pcs = sorted(pcs_carga.items(), key=lambda x: x[1], reverse=True)
            for pc, count in sorted_pcs[:10]:
                print(f"  PC 0x{pc:04X}: {count} escrituras")
    else:
        print("\n[CRITICO] NO SE DETECTARON ESCRITURAS DE TILES EN VRAM")
        print("  [CRITICO] ESTO ES CRITICO: El juego no esta cargando tiles en VRAM")
        print("  Posibles causas:")
        print("    - El juego carga tiles pero se borran después")
        print("    - Hay alguna condición que impide la carga de tiles")
        print("    - Los tiles se cargan en un momento diferente al esperado")
    
    print()
    print("=" * 80)
    print("ANÁLISIS COMPLETADO")
    print("=" * 80)

if __name__ == '__main__':
    main()

