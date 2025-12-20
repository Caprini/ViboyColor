#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Prueba del Emulador con Timeout y Captura de Logs

Ejecuta el emulador con una ROM durante máximo 1 minuto,
captura todos los logs en un archivo y genera un reporte.
"""

import logging
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from io import StringIO

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import io
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Añadir raíz del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.viboy import Viboy

# Configurar logging para capturar todo
log_stream = StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setLevel(logging.DEBUG)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)

# Configurar logger raíz
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

# Logger para uso en el script
logger = logging.getLogger(__name__)

# También capturar stdout/stderr
stdout_capture = StringIO()
stderr_capture = StringIO()

# Flag para controlar el bucle
running = True
timeout_reached = False
# Lock para sincronización entre threads
running_lock = threading.Lock()


def timeout_handler(viboy: Viboy):
    """Función que se ejecuta después de 60 segundos"""
    global running, timeout_reached
    time.sleep(60)  # Esperar 60 segundos
    with running_lock:
        if running:
            timeout_reached = True
            running = False
            # ✅ CORRECCIÓN: Cambiar directamente viboy.running
            if hasattr(viboy, 'running'):
                viboy.running = False
            print("\n⏰ TIMEOUT: Se alcanzó el límite de 1 minuto. Cerrando emulador...")


def monitor_emulator(viboy: Viboy, stats_dict: dict):
    """Monitorea el estado del emulador mientras corre"""
    global running
    start_time = time.time()
    last_ly = None
    ly_changes = []
    heartbeat_count = 0
    
    while running:
        try:
            time.sleep(0.1)  # Monitorear cada 100ms
            
            # Obtener estado actual
            if hasattr(viboy, '_mmu') and viboy._mmu is not None:
                try:
                    ly = viboy._mmu.read(0xFF44)  # LY
                    if ly != last_ly:
                        ly_changes.append((time.time() - start_time, ly))
                        last_ly = ly
                except:
                    pass
            
            # Contar heartbeats si están activos
            if hasattr(viboy, '_cycles_since_render'):
                heartbeat_count += 1
                
        except Exception as e:
            logging.error(f"Error en monitor: {e}")
            break
    
    # ✅ CORRECCIÓN: Actualizar el diccionario compartido
    stats_dict.update({
        'duration': time.time() - start_time,
        'ly_changes': ly_changes,
        'heartbeat_count': heartbeat_count
    })


def main():
    """Función principal"""
    global running, timeout_reached
    
    # Configurar archivo de log
    log_file = project_root / f"test_emulator_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    print("=" * 70)
    print("🧪 PRUEBA DEL EMULADOR CON TIMEOUT (1 minuto)")
    print("=" * 70)
    print(f"📁 Logs se guardarán en: {log_file}")
    print(f"⏱️  Timeout: 60 segundos")
    print("=" * 70)
    print()
    
    # Ruta a la ROM
    rom_path = project_root / "roms" / "tetris.gb"
    
    if not rom_path.exists():
        print(f"❌ ERROR: No se encontró la ROM en {rom_path}")
        sys.exit(1)
    
    print(f"📦 Cargando ROM: {rom_path}")
    print()
    
    # ✅ CORRECCIÓN: Diccionario compartido para estadísticas
    monitor_stats = {
        'duration': 0.0,
        'ly_changes': [],
        'heartbeat_count': 0
    }
    
    try:
        # ✅ CORRECCIÓN: Configurar variables de entorno para modo headless
        import os
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
        os.environ['VIBOY_TEST_MODE'] = '1'
        os.environ['VIBOY_HEADLESS'] = '1'
        
        # Crear instancia del emulador
        viboy = Viboy(str(rom_path), use_cpp_core=True)
        
        # ✅ CORRECCIÓN: Desactivar el renderer para evitar bloqueos de ventana
        if hasattr(viboy, '_renderer'):
            viboy._renderer = None
            logger.info("Renderer desactivado para modo headless")
        
        # ✅ CORRECCIÓN: Iniciar thread de timeout con viboy como argumento
        timeout_thread = threading.Thread(target=timeout_handler, args=(viboy,), daemon=True)
        timeout_thread.start()
        
        # ✅ CORRECCIÓN: Iniciar thread de monitoreo con diccionario compartido
        monitor_thread = threading.Thread(
            target=monitor_emulator, 
            args=(viboy, monitor_stats), 
            daemon=True
        )
        monitor_thread.start()
        
        print("▶️  Iniciando emulador...")
        print("   (Presiona Ctrl+C para detener manualmente)")
        print()
        
        # Ejecutar emulador en thread separado para poder interrumpirlo
        def run_emulator():
            try:
                viboy.run(debug=False)
            except Exception as e:
                logging.error(f"Error en run(): {e}", exc_info=True)
        
        emulator_thread = threading.Thread(target=run_emulator, daemon=True)
        emulator_thread.start()
        
        # Esperar hasta que se alcance el timeout o se detenga manualmente
        while running:
            time.sleep(0.1)
        
        # ✅ CORRECCIÓN: Detener el emulador de manera más robusta
        print("\n🛑 Intentando detener el emulador...")
        if hasattr(viboy, 'running'):
            viboy.running = False
        
        # ✅ CORRECCIÓN: Esperar a que el emulador responda (timeout de fuerza bruta)
        wait_count = 0
        max_wait = 50  # 5 segundos máximo (50 * 0.1s)
        while wait_count < max_wait and emulator_thread.is_alive():
            time.sleep(0.1)
            wait_count += 1
        
        if emulator_thread.is_alive():
            print("⚠️  El emulador no respondió al flag running=False. Puede estar bloqueado.")
        else:
            print("✅ Emulador detenido correctamente")
        
        # ✅ CORRECCIÓN: Esperar más tiempo para que termine el thread de monitoreo
        monitor_thread.join(timeout=2.0)
        
        # ✅ CORRECCIÓN: Usar estadísticas reales del monitor
        stats = monitor_stats.copy()
        if timeout_reached and stats['duration'] == 0.0:
            stats['duration'] = 60.0
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupción manual (Ctrl+C)")
        with running_lock:
            running = False
        if 'viboy' in locals() and hasattr(viboy, 'running'):
            viboy.running = False
        stats = monitor_stats.copy() if 'monitor_stats' in locals() else {'duration': 0.0, 'ly_changes': [], 'heartbeat_count': 0}
    except Exception as e:
        logging.error(f"Error fatal: {e}", exc_info=True)
        with running_lock:
            running = False
        if 'viboy' in locals() and hasattr(viboy, 'running'):
            viboy.running = False
        stats = monitor_stats.copy() if 'monitor_stats' in locals() else {'duration': 0.0, 'ly_changes': [], 'heartbeat_count': 0}
    
    # Capturar logs
    log_content = log_stream.getvalue()
    
    # Escribir logs a archivo
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("LOG DE PRUEBA DEL EMULADOR\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"ROM: {rom_path}\n")
        f.write(f"Timeout alcanzado: {'Sí' if timeout_reached else 'No'}\n")
        f.write("=" * 70 + "\n\n")
        f.write(log_content)
    
    # Generar reporte
    print()
    print("=" * 70)
    print("📊 REPORTE DE PRUEBA")
    print("=" * 70)
    print(f"⏱️  Duración: {stats['duration']:.2f} segundos")
    print(f"⏰ Timeout alcanzado: {'Sí' if timeout_reached else 'No'}")
    print(f"📁 Log guardado en: {log_file}")
    print()
    
    # Analizar logs
    print("🔍 ANÁLISIS DE LOGS:")
    print("-" * 70)
    
    # Buscar patrones importantes
    log_lines = log_content.split('\n')
    
    # Contar errores
    errors = [line for line in log_lines if 'ERROR' in line or 'error' in line.lower()]
    warnings = [line for line in log_lines if 'WARNING' in line or 'warning' in line.lower()]
    info_messages = [line for line in log_lines if 'INFO' in line]
    
    print(f"❌ Errores encontrados: {len(errors)}")
    if errors:
        print("   Primeros errores:")
        for err in errors[:5]:
            print(f"   - {err[:100]}")
    
    print(f"⚠️  Advertencias encontradas: {len(warnings)}")
    if warnings:
        print("   Primeras advertencias:")
        for warn in warnings[:5]:
            print(f"   - {warn[:100]}")
    
    print(f"ℹ️  Mensajes INFO: {len(info_messages)}")
    
    # Buscar mensajes de heartbeat
    heartbeat_lines = [line for line in log_lines if 'HEARTBEAT' in line or 'heartbeat' in line.lower()]
    print(f"💓 Líneas de heartbeat: {len(heartbeat_lines)}")
    if heartbeat_lines:
        print("   Últimos heartbeats:")
        for hb in heartbeat_lines[-5:]:
            print(f"   - {hb[:100]}")
    
    # Buscar cambios de LY
    ly_lines = [line for line in log_lines if 'LY=' in line or 'LY =' in line]
    print(f"📈 Referencias a LY: {len(ly_lines)}")
    if ly_lines:
        print("   Últimas referencias a LY:")
        for ly in ly_lines[-5:]:
            print(f"   - {ly[:100]}")
    
    # Buscar HALT
    halt_lines = [line for line in log_lines if 'HALT' in line or 'halt' in line.lower()]
    print(f"😴 Referencias a HALT: {len(halt_lines)}")
    
    # Buscar interrupciones
    interrupt_lines = [line for line in log_lines if 'INTERRUPT' in line or 'interrupt' in line.lower()]
    print(f"⚡ Referencias a interrupciones: {len(interrupt_lines)}")
    
    # Buscar V-Blank
    vblank_lines = [line for line in log_lines if 'V-Blank' in line or 'V_BLANK' in line or 'vblank' in line.lower()]
    print(f"📺 Referencias a V-Blank: {len(vblank_lines)}")
    
    print()
    print("=" * 70)
    print("✅ Prueba completada")
    print("=" * 70)
    print(f"📄 Revisa el archivo de log completo para más detalles: {log_file}")
    print()


if __name__ == "__main__":
    main()

