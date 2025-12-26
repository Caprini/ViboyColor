#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para ejecutar el emulador con timeout automático.
Útil para pruebas extendidas sin intervención manual.
"""

import subprocess
import sys
import time
import signal
import os

def run_with_timeout(command, timeout_seconds):
    """
    Ejecuta un comando con timeout automático.
    
    Args:
        command: Lista con el comando y argumentos
        timeout_seconds: Tiempo máximo de ejecución en segundos
    """
    print(f"[RUN] Ejecutando: {' '.join(command)}")
    print(f"[RUN] Timeout: {timeout_seconds} segundos")
    print("=" * 60)
    
    # Iniciar proceso
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8',
        errors='replace'
    )
    
    start_time = time.time()
    output_lines = []
    
    try:
        # Leer salida línea por línea hasta el timeout
        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                print(f"\n[TIMEOUT] Timeout alcanzado ({timeout_seconds}s). Deteniendo proceso...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                break
            
            # Leer una línea si está disponible
            line = process.stdout.readline()
            if line:
                output_lines.append(line)
                # Mostrar solo algunas líneas importantes para no saturar
                if any(tag in line for tag in ['[SIM-INPUT]', '[VRAM-ACCESS-GLOBAL.*DATA]', '[ROM-TO-VRAM]', '[LOAD-SEQUENCE']):
                    print(line.rstrip())
            elif process.poll() is not None:
                # Proceso terminó
                break
            
            # Pequeña pausa para no consumir CPU
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Interrupcion manual (Ctrl+C)")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    
    # Devolver todas las líneas
    return output_lines

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python run_with_timeout.py <timeout_segundos> <comando> [args...]")
        print("Ejemplo: python run_with_timeout.py 60 python main.py roms/pkmn.gb --simulate-input")
        sys.exit(1)
    
    timeout = int(sys.argv[1])
    command = sys.argv[2:]
    
    output = run_with_timeout(command, timeout)
    
    # Guardar salida completa en archivo
    output_file = f"logs/debug_step_0298_timeout_{timeout}s.log"
    os.makedirs("logs", exist_ok=True)
    with open(output_file, "w", encoding="utf-8", errors='replace') as f:
        f.writelines(output)
    
    print(f"\n[OK] Salida guardada en: {output_file}")
    print(f"[OK] Total de lineas: {len(output)}")

