#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis Detallado de la Zona Crítica (Step 0249)
Analiza el flujo de código en la zona 0x2B20-0x2BC0
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def analyze_critical_zone():
    """Analiza la zona crítica del código."""
    
    print("\n" + "="*80)
    print("🔍 ANÁLISIS FORENSE DE LA ZONA CRÍTICA (0x2B20 - 0x2BC0)")
    print("="*80 + "\n")
    
    # Análisis basado en el volcado
    analysis = {
        "0x2B20": {
            "opcode": "INC HL",
            "description": "Inicio del bucle principal",
            "note": "Incrementa HL (puntero de datos)"
        },
        "0x2B24": {
            "opcode": "JR Z, r8 (si FE FF)",
            "description": "Salto condicional si (HL) == 0xFF",
            "note": "Si encuentra 0xFF, salta hacia atrás (probable salida del bucle)"
        },
        "0x2B96": {
            "opcode": "LD (HL+),A",
            "description": "Escribe A en (HL) e incrementa HL",
            "note": "Parte de la rutina de copia de datos (DMA-like)"
        },
        "0x2BA3": {
            "opcode": "LDH (FF8D),A",
            "description": "Escribe A en HRAM[0xFF8D]",
            "note": "Configuración de parámetros en HRAM"
        },
        "0x2BA9": {
            "opcode": "JP 2B20",
            "description": "SALTO INCONDICIONAL AL INICIO",
            "note": "⚠️ BUCLE INFINITO: Vuelve a 0x2B20"
        }
    }
    
    print("📍 PUNTOS CRÍTICOS IDENTIFICADOS:\n")
    
    for addr, info in analysis.items():
        print(f"  {addr}: {info['opcode']}")
        print(f"    └─ {info['description']}")
        print(f"    └─ {info['note']}\n")
    
    print("\n" + "="*80)
    print("🧩 RECONSTRUCCIÓN DEL FLUJO:")
    print("="*80 + "\n")
    
    print("""
1. El código comienza en 0x2B20 (INC HL)
2. Lee datos desde (HL) y los compara con 0xFF
3. Si encuentra 0xFF, probablemente sale del bucle (JR Z hacia atrás)
4. Si no, continúa procesando datos
5. En 0x2B96, escribe datos usando LD (HL+),A (copia)
6. En 0x2BA3, escribe en HRAM[0xFF8D] (configuración)
7. En 0x2BA9, salta de vuelta a 0x2B20 (BUCLE INFINITO)

⚠️ PROBLEMA IDENTIFICADO:
   El bucle en 0x2BA9 salta a 0x2B20, pero el código debería tener
   una condición de salida. Si el juego está atascado aquí, significa
   que la condición de salida (probablemente en 0x2B24) nunca se cumple.

🔍 HIPÓTESIS:
   - El juego espera que ciertos datos cambien (quizás por DMA o interrupción)
   - Si esos datos no cambian, el bucle nunca termina
   - El juego podría estar esperando que una interrupción modifique el estado
   - O esperando que DMA complete y modifique algún flag
    """)
    
    print("\n" + "="*80)
    print("💡 PRÓXIMOS PASOS:")
    print("="*80 + "\n")
    
    print("""
1. Verificar qué datos lee el código en 0x2B20-0x2B30
2. Verificar si hay una condición de salida que nunca se cumple
3. Verificar si el juego espera que DMA modifique algún flag
4. Verificar si el juego espera una interrupción que nunca llega
5. Comparar el comportamiento con un emulador de referencia
    """)

if __name__ == "__main__":
    analyze_critical_zone()

