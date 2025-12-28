#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Verificación Automatizada - Step 0318
Ejecuta verificaciones donde sea posible y guía al usuario en verificaciones manuales.
"""

import subprocess
import sys
import time
from pathlib import Path

def ejecutar_emulador_con_logs(rom_path: str, duracion_segundos: int = 10) -> dict:
    """
    Ejecuta el emulador con logs habilitados temporalmente y captura información.
    """
    print(f"🚀 Ejecutando emulador con ROM: {rom_path}")
    print(f"⏱️  Duración: {duracion_segundos} segundos")
    print("")
    
    # Modificar temporalmente ENABLE_DEBUG_LOGS
    viboy_path = Path("src/viboy.py")
    if not viboy_path.exists():
        print(f"❌ ERROR: No se encuentra {viboy_path}")
        return {}
    
    # Leer archivo
    with open(viboy_path, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    # Verificar si ya está habilitado
    if "ENABLE_DEBUG_LOGS = True" in contenido:
        logs_ya_habilitados = True
        contenido_original = None
    else:
        logs_ya_habilitados = False
        contenido_original = contenido
        # Habilitar logs temporalmente
        contenido = contenido.replace(
            "ENABLE_DEBUG_LOGS = False",
            "ENABLE_DEBUG_LOGS = True  # Habilitado temporalmente para Step 0318"
        )
    
    resultados = {}
    
    try:
        # Escribir archivo modificado
        if not logs_ya_habilitados:
            with open(viboy_path, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print("✅ Logs habilitados temporalmente")
        
        # Ejecutar emulador
        log_file = Path(f"logs/verificacion_step_0318_auto.log")
        log_file.parent.mkdir(exist_ok=True)
        
        print("📝 Ejecutando emulador (capturando logs)...")
        print("   Presiona Ctrl+C para detener antes de tiempo")
        print("")
        
        proceso = subprocess.Popen(
            [sys.executable, "main.py", rom_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Capturar salida durante duracion_segundos
        lineas_capturadas = []
        inicio = time.time()
        
        try:
            while time.time() - inicio < duracion_segundos:
                if proceso.poll() is not None:
                    break
                # Leer línea si está disponible
                if proceso.stdout:
                    linea = proceso.stdout.readline()
                    if linea:
                        lineas_capturadas.append(linea.strip())
                        # Mostrar algunas líneas importantes
                        if any(keyword in linea.lower() for keyword in ['fps', 'error', 'exception']):
                            print(f"   {linea.strip()}")
        except KeyboardInterrupt:
            print("\n⚠️  Interrumpido por usuario")
        
        # Terminar proceso
        proceso.terminate()
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()
        
        # Guardar logs
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lineas_capturadas))
        
        print(f"\n✅ Logs guardados en: {log_file}")
        print(f"   Líneas capturadas: {len(lineas_capturadas)}")
        
        # Analizar logs
        resultados['log_file'] = str(log_file)
        resultados['lineas_capturadas'] = len(lineas_capturadas)
        
        # Buscar información de FPS en logs
        fps_encontrados = []
        for linea in lineas_capturadas:
            if 'fps' in linea.lower():
                fps_encontrados.append(linea)
        
        resultados['fps_logs'] = fps_encontrados[:20]  # Primeros 20
        
    except Exception as e:
        print(f"❌ ERROR durante ejecución: {e}")
        resultados['error'] = str(e)
    
    finally:
        # Restaurar archivo original
        if not logs_ya_habilitados and contenido_original:
            with open(viboy_path, 'w', encoding='utf-8') as f:
                f.write(contenido_original)
            print("✅ Logs restaurados a estado original")
    
    return resultados


def main():
    """Función principal"""
    print("=" * 60)
    print("Verificación Automatizada - Step 0318")
    print("=" * 60)
    print("")
    
    # Verificar ROM
    rom_path = "roms/pkmn.gb"
    if not Path(rom_path).exists():
        print(f"❌ ERROR: No se encuentra la ROM: {rom_path}")
        print("   Por favor, asegúrate de que la ROM existe")
        return 1
    
    print(f"✅ ROM encontrada: {rom_path}")
    print("")
    
    # Ejecutar verificación automatizada
    print("=" * 60)
    print("PASO 1: Verificación Automatizada (Logs)")
    print("=" * 60)
    print("")
    
    resultados = ejecutar_emulador_con_logs(rom_path, duracion_segundos=30)
    
    print("")
    print("=" * 60)
    print("RESUMEN DE VERIFICACIÓN AUTOMATIZADA")
    print("=" * 60)
    print("")
    
    if 'error' in resultados:
        print(f"❌ Error: {resultados['error']}")
    else:
        print(f"✅ Logs capturados: {resultados.get('lineas_capturadas', 0)} líneas")
        print(f"✅ Archivo de log: {resultados.get('log_file', 'N/A')}")
        
        if resultados.get('fps_logs'):
            print(f"\n📊 Líneas con FPS encontradas: {len(resultados['fps_logs'])}")
            print("   Primeras líneas:")
            for linea in resultados['fps_logs'][:5]:
                print(f"   - {linea}")
    
    print("")
    print("=" * 60)
    print("PRÓXIMOS PASOS - VERIFICACIONES MANUALES")
    print("=" * 60)
    print("")
    print("Ahora necesitas completar las verificaciones manuales:")
    print("")
    print("1. 📊 VERIFICACIÓN DE FPS:")
    print("   - Ejecuta: python3 main.py roms/pkmn.gb")
    print("   - Observa el FPS en la barra de título durante 2 minutos")
    print("   - Anota: FPS promedio, mínimo, máximo, estabilidad")
    print("   - Completa: VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md")
    print("")
    print("2. 👁️  VERIFICACIÓN VISUAL:")
    print("   - Mientras el emulador está ejecutándose")
    print("   - Verifica: ¿Se muestran tiles? ¿Pantalla blanca? ¿Estable?")
    print("   - Toma captura de pantalla (opcional)")
    print("   - Completa: VERIFICACION_RENDERIZADO_STEP_0312.md")
    print("")
    print("3. 🎮 VERIFICACIÓN DE CONTROLES:")
    print("   - Ejecuta: python3 main.py roms/pkmn.gb")
    print("   - Prueba cada botón: D-Pad, A, B, Start, Select")
    print("   - Observa respuesta del juego")
    print("   - Completa: VERIFICACION_CONTROLES_STEP_0315.md")
    print("")
    print("4. 💾 VERIFICACIÓN DE COMPATIBILIDAD:")
    print("   - Prueba ROMs GB y GBC (si están disponibles)")
    print("   - Observa: ¿Carga? ¿Renderiza? ¿FPS estable?")
    print("   - Completa: COMPATIBILIDAD_GB_GBC_STEP_0315.md")
    print("")
    print("📖 Guía completa: GUIA_VERIFICACION_STEP_0318.md")
    print("")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

