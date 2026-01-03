#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para abrir múltiples ROMs en ventanas organizadas en cuadrícula de 2 filas
Para captura de pantalla - sin timing automático
"""

import subprocess
import sys
import time
import os
from pathlib import Path

try:
    from Xlib import display, X
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False
    print("⚠️  python3-xlib no está instalado. Instala con: sudo apt-get install python3-xlib")
    print("   Las ventanas se abrirán pero no se posicionarán automáticamente.")

# Colores para output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def find_roms(roms_dir: Path):
    """Encontrar todas las ROMs en el directorio"""
    roms = sorted(roms_dir.glob("*.gb")) + sorted(roms_dir.glob("*.gbc"))
    return [str(r) for r in roms]

def get_screen_size():
    """Obtener tamaño de pantalla usando xrandr"""
    try:
        result = subprocess.run(
            ["xrandr"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        for line in result.stdout.split('\n'):
            if '*' in line:
                parts = line.split()
                for part in parts:
                    if 'x' in part and '*' in part:
                        width, height = part.replace('*', '').split('x')
                        return int(width), int(height)
    except:
        pass
    # Fallback
    return 1920, 1080

def position_windows_xlib(window_pids, roms, cols_per_row=4):
    """Posicionar ventanas usando Xlib"""
    if not HAS_XLIB:
        return False
    
    try:
        d = display.Display()
        root = d.screen().root
        
        # Dimensiones de ventana
        WINDOW_WIDTH = 640
        WINDOW_HEIGHT = 576
        SPACING = 20
        
        # Calcular posiciones
        screen_width, screen_height = get_screen_size()
        total_grid_width = cols_per_row * WINDOW_WIDTH + (cols_per_row - 1) * SPACING
        start_x = (screen_width - total_grid_width) // 2
        start_y = 50
        
        # Esperar a que las ventanas se abran
        time.sleep(3)
        
        # Obtener todas las ventanas
        windows = []
        window_count = 0
        
        def find_windows(window, depth=0):
            nonlocal window_count
            if depth > 10:  # Limitar profundidad
                return
            
            try:
                # Obtener propiedades de la ventana
                attrs = window.get_attributes()
                geom = window.get_geometry()
                
                # Buscar ventanas de Pygame (típicamente tienen cierto tamaño)
                if geom.width >= 600 and geom.height >= 500:
                    wm_name = window.get_wm_name()
                    if wm_name and ('python' in wm_name.lower() or 'viboy' in wm_name.lower()):
                        windows.append((window.id, window))
                        window_count += 1
                
                # Buscar en hijos
                children = window.query_tree().children
                for child in children:
                    find_windows(child, depth + 1)
            except:
                pass
        
        # Buscar ventanas desde la raíz
        find_windows(root)
        
        # Filtrar ventanas recientes (últimas N)
        windows = windows[-len(roms):] if len(windows) > len(roms) else windows
        
        # Posicionar ventanas
        for i, (window_id, window) in enumerate(windows[:len(roms)]):
            row = i // cols_per_row
            col = i % cols_per_row
            
            x = start_x + col * (WINDOW_WIDTH + SPACING)
            y = start_y + row * (WINDOW_HEIGHT + SPACING)
            
            try:
                # Configurar geometría de la ventana
                window.configure(
                    x=x,
                    y=y,
                    width=WINDOW_WIDTH,
                    height=WINDOW_HEIGHT
                )
                d.sync()
                
                rom_name = Path(roms[i]).name
                print(f"  → [{i+1}/{len(roms)}] {rom_name} → ({x}, {y})")
            except Exception as e:
                print(f"  ⚠️  Error posicionando ventana {i+1}: {e}")
        
        return True
    except Exception as e:
        print(f"  ⚠️  Error usando Xlib: {e}")
        return False

def main():
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    roms_dir = project_dir / "roms"
    
    print(f"{GREEN}🎮 Abriendo ROMs en cuadrícula de 2 filas...{NC}")
    
    # Buscar ROMs
    roms = find_roms(roms_dir)
    
    if not roms:
        print(f"❌ No se encontraron ROMs en {roms_dir}")
        sys.exit(1)
    
    print(f"{YELLOW}Encontradas {len(roms)} ROMs{NC}")
    
    # Abrir cada ROM en background
    print(f"{GREEN}Abriendo {len(roms)} ventanas...{NC}")
    pids = []
    
    for i, rom in enumerate(roms):
        rom_name = Path(rom).name
        print(f"  → Abriendo: {rom_name}")
        
        # Ejecutar en background
        process = subprocess.Popen(
            [sys.executable, str(project_dir / "main.py"), rom],
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        pids.append(process.pid)
        
        # Pequeña pausa entre aperturas
        time.sleep(0.5)
    
    print(f"{YELLOW}Esperando a que las ventanas se abran...{NC}")
    
    # Intentar posicionar ventanas
    if HAS_XLIB:
        print(f"{GREEN}Posicionando ventanas en cuadrícula...{NC}")
        position_windows_xlib(pids, roms)
    else:
        print(f"{YELLOW}⚠️  Saltando posicionamiento automático (Xlib no disponible){NC}")
    
    print("")
    print(f"{GREEN}✅ Todas las ventanas abiertas{NC}")
    print(f"{YELLOW}💡 Cierra las ventanas manualmente cuando termines{NC}")
    print("")
    print(f"PIDs de procesos: {' '.join(map(str, pids))}")
    print(f"Para cerrar todas las ventanas: kill {' '.join(map(str, pids))}")

if __name__ == "__main__":
    main()

