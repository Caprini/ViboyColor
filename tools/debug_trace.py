#!/usr/bin/env python3
"""
Herramienta de Trazado Forense para Viboy Color

Este script ejecuta el emulador sin interfaz gráfica y registra cada instrucción
ejecutada, incluyendo escrituras en memoria críticas (IE, LCDC, etc.).

Objetivo: Detectar bucles infinitos y entender por qué el juego no habilita interrupciones.

Uso:
    python tools/debug_trace.py <rom_path> [--max-instructions N]
"""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.viboy import Viboy

if TYPE_CHECKING:
    from src.memory.mmu import MMU

# Constantes de registros críticos
IO_IE = 0xFFFF  # Interrupt Enable
IO_LCDC = 0xFF40  # LCD Control
IO_IF = 0xFF0F  # Interrupt Flag
IO_STAT = 0xFF41  # LCD Status


class TraceMMU:
    """
    Wrapper de MMU que registra todas las escrituras en memoria.
    
    Intercepta las llamadas a write_byte() y las registra en un log
    para análisis forense.
    """
    
    def __init__(self, mmu: MMU, trace_log: list[dict]) -> None:
        """
        Inicializa el wrapper de trazado.
        
        Args:
            mmu: Instancia de MMU real
            trace_log: Lista donde se registrarán las escrituras
        """
        self._mmu = mmu
        self._trace_log = trace_log
    
    def __getattr__(self, name: str):
        """
        Delega todos los atributos no definidos a la MMU real.
        Esto permite que TraceMMU se comporte como una MMU normal.
        """
        return getattr(self._mmu, name)
    
    def write_byte(self, addr: int, value: int) -> None:
        """
        Intercepta escrituras y las registra antes de delegar a la MMU real.
        """
        # Registrar escritura si es a un registro crítico
        if addr in (IO_IE, IO_LCDC, IO_IF, IO_STAT) or (0xFF00 <= addr <= 0xFF7F):
            reg_name = self._get_register_name(addr)
            self._trace_log.append({
                'type': 'write',
                'addr': addr,
                'value': value,
                'reg_name': reg_name
            })
        
        # Delegar a la MMU real
        self._mmu.write_byte(addr, value)
    
    def _get_register_name(self, addr: int) -> str:
        """Obtiene el nombre del registro para logging."""
        names = {
            IO_IE: "IE",
            IO_LCDC: "LCDC",
            IO_IF: "IF",
            IO_STAT: "STAT",
            0xFF42: "SCY",
            0xFF43: "SCX",
            0xFF44: "LY",
            0xFF45: "LYC",
            0xFF47: "BGP",
            0xFF48: "OBP0",
            0xFF49: "OBP1",
        }
        return names.get(addr, f"IO_0x{addr:04X}")


def detect_loop(pc_history: deque[int], threshold: int = 5) -> tuple[bool, list[int] | None]:
    """
    Detecta si el PC está en un bucle (misma secuencia repetida).
    
    Args:
        pc_history: Historial de direcciones PC (últimas N instrucciones)
        threshold: Número mínimo de repeticiones para considerar bucle
        
    Returns:
        Tupla (True si hay bucle, lista de PCs del bucle o None)
    """
    if len(pc_history) < threshold * 2:
        return False, None
    
    # Convertir a lista para análisis
    history_list = list(pc_history)
    
    # Buscar patrones repetidos: comparar últimos N con los N anteriores
    for pattern_len in range(3, min(threshold + 1, len(history_list) // 2)):
        last_pattern = history_list[-pattern_len:]
        prev_pattern = history_list[-pattern_len * 2:-pattern_len]
        
        # Si los patrones coinciden, es un bucle
        if last_pattern == prev_pattern:
            return True, last_pattern
    
    # También detectar si el PC oscila entre las mismas direcciones
    # (bucle corto con saltos condicionales)
    unique_pcs = set(history_list[-10:])
    if len(unique_pcs) <= 3 and len(history_list) >= 10:
        # Si solo hay 3 o menos PCs únicos en las últimas 10 instrucciones, es un bucle
        return True, list(unique_pcs)
    
    return False, None


def format_instruction_log(
    pc: int,
    opcode: int,
    cycles: int,
    registers: dict[str, int],
    memory_writes: list[dict] | None = None
) -> str:
    """
    Formatea una línea de log de instrucción.
    
    Args:
        pc: Program Counter
        opcode: Opcode ejecutado
        cycles: Ciclos consumidos
        registers: Diccionario con valores de registros
        memory_writes: Lista de escrituras en memoria (si las hay)
        
    Returns:
        String formateado para el log
    """
    reg_str = (
        f"A:{registers['A']:02X} B:{registers['B']:02X} "
        f"C:{registers['C']:02X} D:{registers['D']:02X} "
        f"E:{registers['E']:02X} H:{registers['H']:02X} "
        f"L:{registers['L']:02X} SP:{registers['SP']:04X} "
        f"F:{registers['F']:02X}"
    )
    
    line = f"PC: 0x{pc:04X} | Op: 0x{opcode:02X} | {reg_str} | Cycles: {cycles}"
    
    # Añadir información de escrituras críticas
    if memory_writes:
        write_strs = []
        for write in memory_writes:
            reg_name = write.get('reg_name', f"0x{write['addr']:04X}")
            write_strs.append(f"{reg_name}=0x{write['value']:02X}")
        if write_strs:
            line += f" | WRITES: {', '.join(write_strs)}"
    
    return line


def main() -> None:
    """Función principal del script de trazado."""
    if len(sys.argv) < 2:
        print("Uso: python tools/debug_trace.py <rom_path> [--max-instructions N]")
        print("Ejemplo: python tools/debug_trace.py tetris_dx.gbc")
        sys.exit(1)
    
    rom_path = Path(sys.argv[1])
    if not rom_path.exists():
        print(f"Error: ROM no encontrada: {rom_path}")
        sys.exit(1)
    
    # Parsear argumentos opcionales
    max_instructions = 50_000
    if len(sys.argv) > 2 and sys.argv[2] == "--max-instructions":
        if len(sys.argv) > 3:
            try:
                max_instructions = int(sys.argv[3])
            except ValueError:
                print(f"Error: Número inválido: {sys.argv[3]}")
                sys.exit(1)
    
    print("=" * 80)
    print("Viboy Color - Herramienta de Trazado Forense")
    print("=" * 80)
    print(f"ROM: {rom_path}")
    print(f"Instrucciones máximas: {max_instructions:,}")
    print("=" * 80)
    print()
    
    # Inicializar emulador
    try:
        viboy = Viboy(rom_path)
    except Exception as e:
        print(f"Error al cargar ROM: {e}")
        sys.exit(1)
    
    # Obtener componentes
    cpu = viboy.get_cpu()
    mmu = viboy.get_mmu()
    
    if cpu is None or mmu is None:
        print("Error: CPU o MMU no inicializados")
        sys.exit(1)
    
    # Crear log de trazado
    trace_log: list[dict] = []
    instruction_log: list[str] = []
    
    # Historial de PC para detección de bucles
    pc_history: deque[int] = deque(maxlen=20)
    
    # Wrapper de MMU para interceptar escrituras
    trace_mmu = TraceMMU(mmu, trace_log)
    
    # Reemplazar la MMU en la CPU con el wrapper
    # Esto es un hack, pero necesario para interceptar escrituras
    cpu.mmu = trace_mmu
    
    print("Iniciando trazado...")
    print()
    
    instruction_count = 0
    loop_detected = False
    
    try:
        while instruction_count < max_instructions:
            # Obtener estado antes de ejecutar
            pc_before = cpu.registers.get_pc()
            opcode = mmu.read_byte(pc_before)
            
            # Limpiar log de escrituras para esta instrucción
            trace_log.clear()
            
            # Ejecutar instrucción
            cycles = viboy.tick()
            
            # Obtener estado después de ejecutar
            regs = cpu.registers
            registers_dict = {
                'A': regs.get_a(),
                'B': regs.get_b(),
                'C': regs.get_c(),
                'D': regs.get_d(),
                'E': regs.get_e(),
                'H': regs.get_h(),
                'L': regs.get_l(),
                'SP': regs.get_sp(),
                'F': regs.get_f(),
            }
            
            # Registrar instrucción
            memory_writes = list(trace_log) if trace_log else None
            log_line = format_instruction_log(
                pc_before, opcode, cycles, registers_dict, memory_writes
            )
            instruction_log.append(log_line)
            
            # Añadir PC al historial
            pc_history.append(pc_before)
            
            # Detectar bucles
            if not loop_detected:
                has_loop, loop_pattern = detect_loop(pc_history, threshold=5)
                if has_loop:
                    loop_detected = True
                    print("=" * 80)
                    print("BUCLE DETECTADO")
                    print("=" * 80)
                    print(f"PC actual: 0x{pc_before:04X}")
                    print(f"Instrucciones ejecutadas: {instruction_count + 1}")
                    if loop_pattern:
                        print(f"Patron del bucle: {[f'0x{pc:04X}' for pc in loop_pattern]}")
                    print()
                    print("Ultimas 20 instrucciones antes del bucle:")
                    print("-" * 80)
                    for line in instruction_log[-20:]:
                        print(line)
                    print("=" * 80)
                    print()
                    print("Continuando ejecucion para capturar mas contexto...")
                    print()
            
            instruction_count += 1
            
            # Mostrar progreso cada 10,000 instrucciones
            if instruction_count % 10_000 == 0:
                print(f"Progreso: {instruction_count:,} instrucciones ejecutadas...")
    
    except KeyboardInterrupt:
        print("\nTrazado interrumpido por el usuario")
    except Exception as e:
        print(f"\nError durante el trazado: {e}")
        import traceback
        traceback.print_exc()
    
    # Mostrar resumen
    print()
    print("=" * 80)
    print("RESUMEN DEL TRAZADO")
    print("=" * 80)
    print(f"Total de instrucciones ejecutadas: {instruction_count:,}")
    print(f"Bucle detectado: {'Sí' if loop_detected else 'No'}")
    print()
    
    # Contar escrituras críticas
    all_writes = []
    for log_entry in instruction_log:
        if "WRITES:" in log_entry:
            all_writes.append(log_entry)
    
    print(f"Instrucciones con escrituras en I/O: {len(all_writes)}")
    print()
    
    # Buscar escrituras en IE (0xFFFF)
    ie_writes = [line for line in instruction_log if "IE=" in line]
    if ie_writes:
        print("=" * 80)
        print("ESCRITURAS EN IE (0xFFFF) - Interrupt Enable")
        print("=" * 80)
        for line in ie_writes:
            print(line)
        print()
    else:
        print("ADVERTENCIA: No se detectaron escrituras en IE (0xFFFF)")
        print("   Esto explica por que las interrupciones no se habilitan.")
        print()
    
    # Buscar escrituras en LCDC (0xFF40)
    lcdc_writes = [line for line in instruction_log if "LCDC=" in line]
    if lcdc_writes:
        print("=" * 80)
        print("ESCRITURAS EN LCDC (0xFF40) - LCD Control")
        print("=" * 80)
        for line in lcdc_writes[:10]:  # Mostrar solo las primeras 10
            print(line)
        if len(lcdc_writes) > 10:
            print(f"... y {len(lcdc_writes) - 10} más")
        print()
    
    # Mostrar primeras 50 instrucciones
    print("=" * 80)
    print("PRIMERAS 50 INSTRUCCIONES (Inicio de ejecucion)")
    print("=" * 80)
    first_instructions = min(50, len(instruction_log))
    for line in instruction_log[:first_instructions]:
        print(line)
    print("=" * 80)
    print()
    
    # Mostrar últimas 50 instrucciones
    print("=" * 80)
    print("ULTIMAS 50 INSTRUCCIONES (Estado actual)")
    print("=" * 80)
    last_instructions = min(50, len(instruction_log))
    for line in instruction_log[-last_instructions:]:
        print(line)
    print("=" * 80)


if __name__ == "__main__":
    main()

