"""
Doctor Viboy - Herramienta de Diagnóstico Autónoma

Esta herramienta ejecuta el emulador sin interfaz gráfica y analiza el comportamiento
de la CPU para encontrar la causa de bloqueos (pantalla negra, bucles infinitos).

Funcionalidades:
- Detección automática de bucles infinitos
- Desensamblado del código del bucle
- Análisis del estado del sistema (registros, hardware)
- Heurísticas de diagnóstico (V-Blank, Timer, Interrupciones, etc.)

Fuente: Clean-room implementation basado en documentación técnica.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import deque
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.viboy import Viboy

# Configurar logging (solo WARNING y ERROR para evitar spam)
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

# Constantes de hardware (I/O Ports)
IO_LY = 0xFF44
IO_STAT = 0xFF41
IO_LCDC = 0xFF40
IO_IF = 0xFF0F
IO_IE = 0xFFFF
IO_DIV = 0xFF04
IO_TIMA = 0xFF05
IO_TAC = 0xFF07


class Disassembler:
    """
    Desensamblador básico para instrucciones LR35902.
    
    Solo implementa las instrucciones más comunes que aparecen en bucles
    de espera (polling loops). No es un desensamblador completo.
    """
    
    @staticmethod
    def disassemble(mmu, addr: int, max_bytes: int = 16) -> tuple[str, int]:
        """
        Desensambla una instrucción en la dirección especificada.
        
        Returns:
            (mnemónico, bytes_leídos)
        """
        try:
            opcode = mmu.read_byte(addr) & 0xFF
        except:
            return f"DB 0x{opcode:02X}", 1
        
        # Instrucciones de 1 byte
        if opcode == 0x00:
            return "NOP", 1
        elif opcode == 0x76:
            return "HALT", 1
        elif opcode == 0xF3:
            return "DI", 1
        elif opcode == 0xFB:
            return "EI", 1
        elif opcode == 0x27:
            return "DAA", 1
        elif opcode == 0x2F:
            return "CPL", 1
        elif opcode == 0x37:
            return "SCF", 1
        elif opcode == 0x3F:
            return "CCF", 1
        elif opcode == 0xC9:
            return "RET", 1
        
        # LD A, (nn) - 3 bytes
        elif opcode == 0xFA:
            try:
                lo = mmu.read_byte((addr + 1) & 0xFFFF) & 0xFF
                hi = mmu.read_byte((addr + 2) & 0xFFFF) & 0xFF
                nn = (hi << 8) | lo
                reg_name = Disassembler._get_io_register_name(nn)
                return f"LD A, ({reg_name})", 3
            except:
                return f"LD A, (nn)", 3
        
        # LD A, (C) - 1 byte (lee de 0xFF00 + C)
        elif opcode == 0xF2:
            return "LD A, (C)", 1
        
        # LD A, (HL) - 1 byte
        elif opcode == 0x7E:
            return "LD A, (HL)", 1
        
        # CP d8 - 2 bytes
        elif opcode == 0xFE:
            try:
                d8 = mmu.read_byte((addr + 1) & 0xFFFF) & 0xFF
                return f"CP 0x{d8:02X} ({d8})", 2
            except:
                return "CP d8", 2
        
        # CP (HL) - 1 byte
        elif opcode == 0xBE:
            return "CP (HL)", 1
        
        # JR e - 2 bytes (salto relativo)
        elif opcode == 0x18:
            try:
                e = mmu.read_byte((addr + 1) & 0xFFFF)
                if e & 0x80:  # Signo negativo
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (addr + 2 + offset) & 0xFFFF
                return f"JR 0x{target:04X} ({offset:+d})", 2
            except:
                return "JR e", 2
        
        # JR NZ, e - 2 bytes
        elif opcode == 0x20:
            try:
                e = mmu.read_byte((addr + 1) & 0xFFFF)
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (addr + 2 + offset) & 0xFFFF
                return f"JR NZ, 0x{target:04X} ({offset:+d})", 2
            except:
                return "JR NZ, e", 2
        
        # JR Z, e - 2 bytes
        elif opcode == 0x28:
            try:
                e = mmu.read_byte((addr + 1) & 0xFFFF)
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (addr + 2 + offset) & 0xFFFF
                return f"JR Z, 0x{target:04X} ({offset:+d})", 2
            except:
                return "JR Z, e", 2
        
        # JP nn - 3 bytes
        elif opcode == 0xC3:
            try:
                lo = mmu.read_byte((addr + 1) & 0xFFFF) & 0xFF
                hi = mmu.read_byte((addr + 2) & 0xFFFF) & 0xFF
                nn = (hi << 8) | lo
                return f"JP 0x{nn:04X}", 3
            except:
                return "JP nn", 3
        
        # AND d8 - 2 bytes
        elif opcode == 0xE6:
            try:
                d8 = mmu.read_byte((addr + 1) & 0xFFFF) & 0xFF
                return f"AND 0x{d8:02X}", 2
            except:
                return "AND d8", 2
        
        # BIT n, (HL) - 2 bytes (prefijo CB)
        elif opcode == 0xCB:
            try:
                cb_op = mmu.read_byte((addr + 1) & 0xFFFF) & 0xFF
                if 0x46 <= cb_op <= 0x7E and (cb_op & 0x07) == 0x06:
                    bit = (cb_op >> 3) & 0x07
                    return f"BIT {bit}, (HL)", 2
            except:
                pass
            return "CB ...", 2
        
        # Por defecto, mostrar opcode
        return f"DB 0x{opcode:02X}", 1
    
    @staticmethod
    def _get_io_register_name(addr: int) -> str:
        """Devuelve el nombre de un registro I/O si es conocido."""
        names = {
            0xFF44: "LY",
            0xFF41: "STAT",
            0xFF40: "LCDC",
            0xFF0F: "IF",
            0xFFFF: "IE",
            0xFF04: "DIV",
            0xFF05: "TIMA",
            0xFF07: "TAC",
        }
        return names.get(addr, f"0x{addr:04X}")


class LoopDetector:
    """
    Detecta bucles infinitos analizando el historial de direcciones PC.
    """
    
    def __init__(self, window_size: int = 100, confidence_threshold: int = 5000):
        """
        Args:
            window_size: Tamaño de la ventana de direcciones recientes
            confidence_threshold: Número de iteraciones en el mismo rango para considerar bucle
        """
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.pc_history: deque[int] = deque(maxlen=window_size)
        self.loop_counter: dict[int, int] = {}
        self.current_loop_start: int | None = None
        self.iterations_in_loop: int = 0
    
    def add_pc(self, pc: int) -> bool:
        """
        Añade una dirección PC al historial y detecta si estamos en un bucle.
        
        Returns:
            True si se detecta un bucle con alta confianza
        """
        self.pc_history.append(pc)
        
        # Contar cuántas veces aparece PC en la ventana reciente
        count = sum(1 for p in self.pc_history if p == pc)
        
        # Si aparece muchas veces, incrementar contador de confianza
        if count >= 10:  # Aparece al menos 10 veces en las últimas 100
            if pc not in self.loop_counter:
                self.loop_counter[pc] = 0
            self.loop_counter[pc] += 1
            
            # Si este PC es el inicio del bucle actual
            if self.current_loop_start == pc:
                self.iterations_in_loop += 1
            else:
                # Nuevo bucle detectado
                self.current_loop_start = pc
                self.iterations_in_loop = 1
            
            # Si tenemos alta confianza, reportar bucle
            if self.iterations_in_loop >= self.confidence_threshold:
                return True
        else:
            # Resetear si salimos del bucle
            if self.current_loop_start == pc:
                self.current_loop_start = None
                self.iterations_in_loop = 0
        
        return False
    
    def get_loop_range(self) -> tuple[int, int]:
        """
        Devuelve el rango de direcciones del bucle detectado.
        
        Returns:
            (min_pc, max_pc) del bucle
        """
        if not self.pc_history:
            return (0, 0)
        
        # Obtener el rango de direcciones únicas en la ventana
        unique_pcs = sorted(set(self.pc_history))
        if not unique_pcs:
            return (0, 0)
        
        return (min(unique_pcs), max(unique_pcs))


class DoctorViboy:
    """
    Herramienta de diagnóstico autónoma para el emulador Viboy.
    """
    
    def __init__(self, rom_path: str | Path):
        """
        Inicializa el Doctor Viboy con una ROM.
        
        Args:
            rom_path: Ruta al archivo ROM (.gb o .gbc)
        """
        self.rom_path = Path(rom_path)
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM no encontrada: {rom_path}")
        
        self.viboy = Viboy(rom_path)
        self.loop_detector = LoopDetector(window_size=100, confidence_threshold=5000)
        self.instruction_count = 0
        self.max_instructions = 10_000_000  # Límite de seguridad
    
    def run(self) -> None:
        """
        Ejecuta el emulador y analiza el comportamiento hasta detectar un bucle.
        """
        print("=" * 80)
        print("DOCTOR VIBOY - DIAGNÓSTICO AUTÓNOMO")
        print("=" * 80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Ejecutando hasta {self.max_instructions:,} instrucciones o detección de bucle...")
        print()
        
        mmu = self.viboy.get_mmu()
        cpu = self.viboy.get_cpu()
        
        if mmu is None or cpu is None:
            print("ERROR: Sistema no inicializado correctamente")
            return
        
        try:
            while self.instruction_count < self.max_instructions:
                # Ejecutar una instrucción
                pc_before = cpu.registers.get_pc()
                cycles = self.viboy.tick()
                self.instruction_count += 1
                
                # Detectar bucle
                if self.loop_detector.add_pc(pc_before):
                    print(f"\n{'=' * 80}")
                    print("[!] BUCLE INFINITO DETECTADO")
                    print(f"{'=' * 80}\n")
                    self._analyze_loop(mmu, cpu)
                    return
                
                # Heartbeat cada 100k instrucciones
                if self.instruction_count % 100_000 == 0:
                    pc = cpu.registers.get_pc()
                    print(f"  [{self.instruction_count:,} inst] PC=0x{pc:04X}", end='\r')
            
            print(f"\n\n{'=' * 80}")
            print("[OK] EJECUCION COMPLETADA SIN DETECTAR BUCLE")
            print(f"{'=' * 80}\n")
            print(f"Total de instrucciones ejecutadas: {self.instruction_count:,}")
            pc = cpu.registers.get_pc()
            print(f"PC final: 0x{pc:04X}")
        
        except KeyboardInterrupt:
            print("\n\n[!] Ejecucion interrumpida por el usuario")
            self._print_current_state(mmu, cpu)
        except Exception as e:
            print(f"\n\n[ERROR] ERROR: {e}")
            self._print_current_state(mmu, cpu)
            raise
    
    def _analyze_loop(self, mmu, cpu) -> None:
        """
        Analiza el bucle detectado y genera un reporte de diagnóstico.
        """
        # Obtener rango del bucle
        min_pc, max_pc = self.loop_detector.get_loop_range()
        
        print(f"[*] Ubicacion del bucle: 0x{min_pc:04X} - 0x{max_pc:04X}")
        print(f"[*] Iteraciones detectadas: {self.loop_detector.iterations_in_loop:,}")
        print()
        
        # Desensamblar el bucle
        print("[*] CODIGO DESENSAMBLADO DEL BUCLE:")
        print("-" * 80)
        current_pc = min_pc
        instructions_shown = 0
        max_instructions_to_show = 20
        
        while current_pc <= max_pc and instructions_shown < max_instructions_to_show:
            try:
                mnemonic, bytes_read = Disassembler.disassemble(mmu, current_pc)
                print(f"  0x{current_pc:04X}: {mnemonic}")
                current_pc = (current_pc + bytes_read) & 0xFFFF
                instructions_shown += 1
            except Exception as e:
                print(f"  0x{current_pc:04X}: ERROR al desensamblar: {e}")
                break
        
        print()
        
        # Estado del sistema
        self._print_system_state(mmu, cpu)
        
        # Heurísticas de diagnóstico
        self._diagnose_loop(mmu, cpu, min_pc, max_pc)
    
    def _print_system_state(self, mmu, cpu) -> None:
        """Imprime el estado completo del sistema."""
        print("[*] ESTADO DEL SISTEMA:")
        print("-" * 80)
        
        # Registros de la CPU
        regs = cpu.registers
        print("Registros CPU:")
        print(f"  AF: 0x{regs.get_af():04X}  (A=0x{regs.get_a():02X}, F=0x{regs.get_f():02X})")
        print(f"  BC: 0x{regs.get_bc():04X}  (B=0x{regs.get_b():02X}, C=0x{regs.get_c():02X})")
        print(f"  DE: 0x{regs.get_de():04X}  (D=0x{regs.get_d():02X}, E=0x{regs.get_e():02X})")
        print(f"  HL: 0x{regs.get_hl():04X}  (H=0x{regs.get_h():02X}, L=0x{regs.get_l():02X})")
        print(f"  PC: 0x{regs.get_pc():04X}")
        print(f"  SP: 0x{regs.get_sp():04X}")
        
        # Flags
        flags = []
        if regs.get_flag_z(): flags.append("Z")
        if regs.get_flag_n(): flags.append("N")
        if regs.get_flag_h(): flags.append("H")
        if regs.get_flag_c(): flags.append("C")
        print(f"  Flags: {' '.join(flags) if flags else '(ninguno)'}")
        
        # Estado de interrupciones
        print(f"  IME: {cpu.ime}")
        print(f"  Halted: {cpu.halted}")
        print()
        
        # Registros de hardware
        print("Registros de Hardware:")
        try:
            lcdc = mmu.read_byte(IO_LCDC) & 0xFF
            stat = mmu.read_byte(IO_STAT) & 0xFF
            ly = mmu.read_byte(IO_LY) & 0xFF
            lyc = mmu.read_byte(0xFF45) & 0xFF
            if_reg = mmu.read_byte(IO_IF) & 0xFF
            ie = mmu.read_byte(IO_IE) & 0xFF
            div = mmu.read_byte(IO_DIV) & 0xFF
            tima = mmu.read_byte(IO_TIMA) & 0xFF
            tac = mmu.read_byte(IO_TAC) & 0xFF
            
            print(f"  LCDC: 0x{lcdc:02X} ({'ON' if lcdc & 0x80 else 'OFF'})")
            print(f"  STAT: 0x{stat:02X}")
            print(f"  LY:   {ly} (0x{ly:02X})")
            print(f"  LYC:  {lyc} (0x{lyc:02X})")
            print(f"  IF:   0x{if_reg:02X} (V-Blank={'ON' if if_reg & 0x01 else 'OFF'}, "
                  f"STAT={'ON' if if_reg & 0x02 else 'OFF'}, "
                  f"Timer={'ON' if if_reg & 0x04 else 'OFF'}, "
                  f"Serial={'ON' if if_reg & 0x08 else 'OFF'}, "
                  f"Joypad={'ON' if if_reg & 0x10 else 'OFF'})")
            print(f"  IE:   0x{ie:02X}")
            print(f"  DIV:  0x{div:02X}")
            print(f"  TIMA: 0x{tima:02X}")
            print(f"  TAC:  0x{tac:02X} ({'ON' if tac & 0x04 else 'OFF'})")
        except Exception as e:
            print(f"  ERROR al leer registros: {e}")
        
        print()
    
    def _diagnose_loop(self, mmu, cpu, min_pc: int, max_pc: int) -> None:
        """
        Aplica heurísticas de diagnóstico para identificar la causa del bucle.
        """
        print("[*] DIAGNOSTICO:")
        print("-" * 80)
        
        # Analizar las instrucciones del bucle
        diagnoses = []
        
        # Leer las instrucciones del bucle
        loop_instructions = []
        current_pc = min_pc
        for _ in range(20):  # Analizar hasta 20 instrucciones
            if current_pc > max_pc:
                break
            try:
                opcode = mmu.read_byte(current_pc) & 0xFF
                loop_instructions.append((current_pc, opcode))
                
                # Leer operandos si es necesario
                if opcode == 0xFA:  # LD A, (nn)
                    lo = mmu.read_byte((current_pc + 1) & 0xFFFF) & 0xFF
                    hi = mmu.read_byte((current_pc + 2) & 0xFFFF) & 0xFF
                    nn = (hi << 8) | lo
                    if nn == IO_LY:
                        diagnoses.append("Esperando V-Blank (LY)")
                    elif nn == IO_STAT:
                        diagnoses.append("Esperando Modo LCD (STAT)")
                    elif nn == IO_IF:
                        diagnoses.append("Esperando Interrupción (Polling IF)")
                    elif nn == IO_DIV or nn == IO_TIMA:
                        diagnoses.append("Esperando Timer")
                
                elif opcode == 0xF2:  # LD A, (C) - lee de 0xFF00 + C
                    c = cpu.registers.get_c()
                    addr = 0xFF00 + c
                    if addr == IO_LY:
                        diagnoses.append("Esperando V-Blank (LY via C)")
                    elif addr == IO_STAT:
                        diagnoses.append("Esperando Modo LCD (STAT via C)")
                    elif addr == IO_IF:
                        diagnoses.append("Esperando Interrupción (IF via C)")
                
                elif opcode == 0xFE:  # CP d8
                    d8 = mmu.read_byte((current_pc + 1) & 0xFFFF) & 0xFF
                    if d8 == 144 or d8 == 0x90:
                        diagnoses.append("Comparando con 144 (V-Blank threshold)")
                
                elif opcode == 0xE6:  # AND d8
                    d8 = mmu.read_byte((current_pc + 1) & 0xFFFF) & 0xFF
                    if d8 == 0x03 or d8 == 0x07:  # Máscaras comunes para STAT
                        diagnoses.append("Verificando bits de STAT")
                
                # Avanzar PC
                if opcode == 0xCB:
                    current_pc = (current_pc + 2) & 0xFFFF
                elif opcode in [0xFA, 0xC3, 0xCD]:  # 3 bytes
                    current_pc = (current_pc + 3) & 0xFFFF
                elif opcode in [0x18, 0x20, 0x28, 0x30, 0x38, 0xFE, 0xE6]:  # 2 bytes
                    current_pc = (current_pc + 2) & 0xFFFF
                else:
                    current_pc = (current_pc + 1) & 0xFFFF
            except:
                break
        
        # Verificar estado de hardware
        try:
            ly = mmu.read_byte(IO_LY) & 0xFF
            if ly == 0 and "V-Blank" in str(diagnoses):
                diagnoses.append(f"[!] LY esta fijo en {ly} (no avanza)")
            
            if_reg = mmu.read_byte(IO_IF) & 0xFF
            if (if_reg & 0x01) == 0 and "V-Blank" in str(diagnoses):
                diagnoses.append("[!] IF bit 0 (V-Blank) no esta activado")
            
            lcdc = mmu.read_byte(IO_LCDC) & 0xFF
            if (lcdc & 0x80) == 0:
                diagnoses.append("[!] LCD esta apagado (LCDC bit 7 = 0)")
            
            # Detectar HALT sin interrupciones
            if cpu.halted:
                ie = mmu.read_byte(IO_IE) & 0xFF
                if_reg = mmu.read_byte(IO_IF) & 0xFF
                active_interrupts = if_reg & ie
                if active_interrupts == 0:
                    diagnoses.append("[!] CPU en HALT esperando interrupcion, pero ninguna esta activa")
                    diagnoses.append(f"    IE=0x{ie:02X} (habilitadas), IF=0x{if_reg:02X} (pendientes)")
                    if (ie & 0x01) != 0 and (if_reg & 0x01) == 0:
                        diagnoses.append("    - V-Blank habilitada pero no activa (IF bit 0 = 0)")
                    if (ie & 0x04) != 0 and (if_reg & 0x04) == 0:
                        diagnoses.append("    - Timer habilitado pero no activo (IF bit 2 = 0)")
        except:
            pass
        
        # Mostrar diagnósticos
        if diagnoses:
            for i, diag in enumerate(set(diagnoses), 1):  # Eliminar duplicados
                print(f"  {i}. {diag}")
        else:
            print("  No se pudo determinar la causa específica del bucle.")
            print("  Revisa el código desensamblado y el estado del sistema arriba.")
        
        print()
        print("[*] RECOMENDACIONES:")
        print("-" * 80)
        if "HALT esperando interrupcion" in str(diagnoses):
            print("  - La CPU esta en HALT esperando una interrupcion que nunca llega")
            print("  - Verificar que la PPU active IF bit 0 (V-Blank) cuando LY llega a 144")
            print("  - Verificar que el Timer active IF bit 2 cuando corresponde")
            print("  - Verificar que step() de PPU y Timer se llamen correctamente")
        if "V-Blank" in str(diagnoses) and "LY esta fijo" in str(diagnoses):
            print("  - Verificar que la PPU avance LY correctamente en cada frame")
            print("  - Verificar que step() de PPU se llame con los T-Cycles correctos")
        if "IF bit 0" in str(diagnoses):
            print("  - Verificar que la PPU active IF bit 0 cuando LY llega a 144")
        if "LCD esta apagado" in str(diagnoses):
            print("  - El LCD esta apagado, pero el juego puede estar esperando que se encienda")
        print()
    
    def _print_current_state(self, mmu, cpu) -> None:
        """Imprime el estado actual del sistema (para errores/interrupciones)."""
        print("\nEstado actual:")
        self._print_system_state(mmu, cpu)


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Doctor Viboy - Herramienta de diagnóstico autónoma"
    )
    parser.add_argument(
        "rom",
        type=str,
        help="Ruta al archivo ROM (.gb o .gbc)"
    )
    parser.add_argument(
        "--max-instructions",
        type=int,
        default=10_000_000,
        help="Número máximo de instrucciones a ejecutar (default: 10,000,000)"
    )
    
    args = parser.parse_args()
    
    doctor = DoctorViboy(args.rom)
    doctor.max_instructions = args.max_instructions
    doctor.run()


if __name__ == "__main__":
    main()

