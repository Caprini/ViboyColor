#!/usr/bin/env python3
"""
Script de Análisis para Step 0245: Interceptor de Transferencia DMA/HRAM

Analiza los logs del emulador para detectar:
1. Escrituras en el registro DMA (0xFF46)
2. Lecturas en HRAM (0xFF8D)
3. Patrones de transferencia de datos

Uso:
    python main.py roms/tetris.gb > dma_check.log 2>&1
    python tools/analizar_dma_0245.py dma_check.log > RESUMEN_DMA_0245.txt
"""

import sys
import re
from collections import defaultdict
from datetime import datetime

def analizar_log(archivo_log):
    """Analiza el log y extrae eventos DMA y HRAM"""
    
    eventos_dma = []
    eventos_hram = []
    eventos_sentinel = []
    
    # Patrones de búsqueda
    patron_dma = re.compile(r'\[DMA\] ¡Escritura en Registro DMA \(FF46\)! Valor: ([0-9A-F]{2}) \(Source: ([0-9A-F]{4})00\)')
    patron_hram = re.compile(r'\[HRAM\] ¡Lectura detectada en FF8D! PC podría estar copiando datos\.')
    patron_sentinel = re.compile(r'\[SENTINEL\] ¡Detectada escritura de 0xFD en Address: ([0-9A-F]{4})!')
    
    try:
        with open(archivo_log, 'r', encoding='utf-8', errors='ignore') as f:
            for num_linea, linea in enumerate(f, 1):
                # Buscar eventos DMA
                match_dma = patron_dma.search(linea)
                if match_dma:
                    valor = match_dma.group(1)
                    source = match_dma.group(2)
                    eventos_dma.append({
                        'linea': num_linea,
                        'valor': valor,
                        'source': source,
                        'raw': linea.strip()
                    })
                
                # Buscar lecturas HRAM
                if patron_hram.search(linea):
                    eventos_hram.append({
                        'linea': num_linea,
                        'raw': linea.strip()
                    })
                
                # Buscar escrituras Sentinel (0xFD)
                match_sentinel = patron_sentinel.search(linea)
                if match_sentinel:
                    addr = match_sentinel.group(1)
                    eventos_sentinel.append({
                        'linea': num_linea,
                        'addr': addr,
                        'raw': linea.strip()
                    })
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo {archivo_log}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR al leer el archivo: {e}", file=sys.stderr)
        return None
    
    return {
        'dma': eventos_dma,
        'hram': eventos_hram,
        'sentinel': eventos_sentinel
    }

def generar_resumen(eventos):
    """Genera el resumen en formato texto"""
    
    if eventos is None:
        return "ERROR: No se pudieron analizar los eventos.\n"
    
    resumen = []
    resumen.append("=" * 80)
    resumen.append("RESUMEN DMA/HRAM - STEP 0245")
    resumen.append("=" * 80)
    resumen.append(f"Fecha de análisis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    resumen.append("")
    
    # Estadísticas DMA
    resumen.append("=" * 80)
    resumen.append("1. EVENTOS DMA (Registro 0xFF46)")
    resumen.append("=" * 80)
    resumen.append(f"Total de escrituras en DMA: {len(eventos['dma'])}")
    resumen.append("")
    
    if eventos['dma']:
        resumen.append("Detalles de las escrituras DMA:")
        resumen.append("-" * 80)
        for i, evento in enumerate(eventos['dma'][:20], 1):  # Mostrar primeros 20
            resumen.append(f"  {i}. Línea {evento['linea']}: Valor={evento['valor']}, Source={evento['source']}00")
        if len(eventos['dma']) > 20:
            resumen.append(f"  ... y {len(eventos['dma']) - 20} eventos más")
    else:
        resumen.append("  ⚠️  NO se detectaron escrituras en el registro DMA (0xFF46)")
        resumen.append("  Esto sugiere que el juego NO está intentando usar DMA para transferir datos.")
    
    resumen.append("")
    
    # Estadísticas HRAM
    resumen.append("=" * 80)
    resumen.append("2. LECTURAS HRAM (Dirección 0xFF8D)")
    resumen.append("=" * 80)
    resumen.append(f"Total de lecturas en 0xFF8D: {len(eventos['hram'])}")
    resumen.append("")
    
    if eventos['hram']:
        resumen.append("Detalles de las lecturas HRAM:")
        resumen.append("-" * 80)
        for i, evento in enumerate(eventos['hram'][:20], 1):  # Mostrar primeros 20
            resumen.append(f"  {i}. Línea {evento['linea']}")
        if len(eventos['hram']) > 20:
            resumen.append(f"  ... y {len(eventos['hram']) - 20} eventos más")
    else:
        resumen.append("  ⚠️  NO se detectaron lecturas en HRAM (0xFF8D)")
        resumen.append("  Esto sugiere que NADIE está intentando leer el marcador 0xFD desde HRAM.")
    
    resumen.append("")
    
    # Estadísticas Sentinel
    resumen.append("=" * 80)
    resumen.append("3. ESCRITURAS SENTINEL (0xFD)")
    resumen.append("=" * 80)
    resumen.append(f"Total de escrituras de 0xFD: {len(eventos['sentinel'])}")
    resumen.append("")
    
    if eventos['sentinel']:
        resumen.append("Detalles de las escrituras Sentinel:")
        resumen.append("-" * 80)
        direcciones = defaultdict(int)
        for evento in eventos['sentinel']:
            direcciones[evento['addr']] += 1
        
        for addr, count in sorted(direcciones.items()):
            resumen.append(f"  Dirección {addr}: {count} escritura(s)")
    else:
        resumen.append("  ⚠️  NO se detectaron escrituras de 0xFD (esto es consistente con Step 0244)")
    
    resumen.append("")
    
    # Análisis de correlación
    resumen.append("=" * 80)
    resumen.append("4. ANÁLISIS DE CORRELACIÓN")
    resumen.append("=" * 80)
    resumen.append("")
    
    if eventos['dma'] and eventos['hram']:
        resumen.append("  ✅ Se detectaron AMBOS eventos (DMA y HRAM)")
        resumen.append("     → El juego SÍ está intentando transferir datos, pero algo falla.")
    elif eventos['dma'] and not eventos['hram']:
        resumen.append("  ⚠️  Se detectó DMA pero NO lecturas HRAM")
        resumen.append("     → El juego activa DMA, pero nadie lee 0xFF8D antes de la transferencia.")
    elif not eventos['dma'] and eventos['hram']:
        resumen.append("  ⚠️  Se detectaron lecturas HRAM pero NO DMA")
        resumen.append("     → El juego lee 0xFF8D manualmente, pero no usa DMA.")
    else:
        resumen.append("  ❌ NO se detectaron NI DMA NI lecturas HRAM")
        resumen.append("     → El juego escribió 0xFD en HRAM y se olvidó de transferirlo.")
        resumen.append("     → O hay una rutina de copia manual que no estamos detectando.")
    
    resumen.append("")
    
    # Conclusiones
    resumen.append("=" * 80)
    resumen.append("5. CONCLUSIONES")
    resumen.append("=" * 80)
    resumen.append("")
    
    if not eventos['dma'] and not eventos['hram']:
        resumen.append("  HIPÓTESIS PRINCIPAL: El juego NO está usando DMA ni leyendo HRAM.")
        resumen.append("  Posibles causas:")
        resumen.append("    a) El juego usa una rutina de copia manual (LDI/LDD) que no detectamos")
        resumen.append("    b) El juego escribió en HRAM pero nunca intentó copiar los datos")
        resumen.append("    c) Hay un problema anterior que impide que el juego llegue a la rutina de copia")
    elif eventos['dma']:
        resumen.append("  HIPÓTESIS PRINCIPAL: El juego SÍ activa DMA, pero la transferencia falla.")
        resumen.append("  Posibles causas:")
        resumen.append("    a) Nuestra implementación de DMA no está funcionando correctamente")
        resumen.append("    b) El juego espera que DMA copie a una dirección específica y no lo hace")
        resumen.append("    c) La transferencia DMA se completa, pero el juego busca en la dirección incorrecta")
    else:
        resumen.append("  HIPÓTESIS PRINCIPAL: El juego lee HRAM manualmente, pero no copia a WRAM.")
        resumen.append("  Posibles causas:")
        resumen.append("    a) La rutina de copia manual falla silenciosamente")
        resumen.append("    b) El juego lee pero no escribe en WRAM")
    
    resumen.append("")
    resumen.append("=" * 80)
    
    return "\n".join(resumen)

def main():
    if len(sys.argv) < 2:
        print("Uso: python analizar_dma_0245.py <archivo_log>", file=sys.stderr)
        print("Ejemplo: python analizar_dma_0245.py dma_check.log", file=sys.stderr)
        sys.exit(1)
    
    archivo_log = sys.argv[1]
    eventos = analizar_log(archivo_log)
    resumen = generar_resumen(eventos)
    print(resumen)

if __name__ == "__main__":
    main()

