#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta headless para smoke test de ROMs sin pygame.

Step 0442: Ejecutar ROM real headless y recolectar métricas para diagnosticar
si el framebuffer sigue blanco o si hay actividad VRAM/rendering.

Uso:
    python tools/rom_smoke_0442.py <ROM_PATH> [--frames N] [--dump-every N] [--dump-png]

Métricas recolectadas por frame:
    - PC (Program Counter)
    - nonwhite_pixels (muestreo de framebuffer)
    - frame_hash (hash simple del framebuffer)
    - vram_nonzero_count (muestreo de VRAM 0x8000-0x9FFF)
    - LCDC, STAT, BGP, SCY, SCX, LY (registros I/O)

Referencias:
    - Pan Docs: Memory Map, I/O Registers
    - Step 0442: Smoke real de ejecución + evidencia no-blanco
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Step 0450: Preflight check - verificar que viboy_core está disponible y compilado ---
try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters, PyTimer, PyJoypad
    NATIVE_AVAILABLE = True
except ImportError as e:
    print("=" * 80, file=sys.stderr)
    print("ERROR CRÍTICO: viboy_core no está disponible", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Detalles: {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("SOLUCIÓN: Compilar el módulo C++ primero:", file=sys.stderr)
    print("", file=sys.stderr)
    print("  cd $(git rev-parse --show-toplevel)", file=sys.stderr)
    print("  python3 setup.py build_ext --inplace", file=sys.stderr)
    print("", file=sys.stderr)
    print("O usar test_build.py:", file=sys.stderr)
    print("  python3 test_build.py", file=sys.stderr)
    print("", file=sys.stderr)
    print("Si el error persiste, verificar:", file=sys.stderr)
    print("  - Cython instalado: pip install cython", file=sys.stderr)
    print("  - Compilador C++ disponible: gcc/clang", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    sys.exit(1)

# Verificación adicional: intentar crear instancia para detectar errores de linking
try:
    test_mmu = PyMMU()
    del test_mmu
except Exception as e:
    print("=" * 80, file=sys.stderr)
    print("ERROR: viboy_core importado pero falla al crear instancia", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Detalles: {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Posible causa: módulo compilado pero linking fallido o incompleto", file=sys.stderr)
    print("Recompilar:", file=sys.stderr)
    print("  python3 setup.py build_ext --inplace --force", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    sys.exit(1)


# --- Step 0474: Funciones helper para disasembly ---
def _get_io_register_name(addr: int) -> str:
    """
    Devuelve el nombre de un registro I/O si es conocido.
    
    Args:
        addr: Dirección del registro I/O
    
    Returns:
        Nombre del registro o dirección hexadecimal
    """
    names = {
        0xFF00: "JOYP",
        0xFF01: "SB",
        0xFF02: "SC",
        0xFF04: "DIV",
        0xFF05: "TIMA",
        0xFF06: "TMA",
        0xFF07: "TAC",
        0xFF0F: "IF",
        0xFF40: "LCDC",
        0xFF41: "STAT",
        0xFF42: "SCY",
        0xFF43: "SCX",
        0xFF44: "LY",
        0xFF45: "LYC",
        0xFF46: "DMA",
        0xFF47: "BGP",
        0xFF48: "OBP0",
        0xFF49: "OBP1",
        0xFF4A: "WY",
        0xFF4B: "WX",
        0xFF4D: "KEY1",
        0xFFFF: "IE",
    }
    return names.get(addr, f"0x{addr:04X}")


def dump_rom_bytes(mmu: PyMMU, pc: int, count: int = 32) -> List[int]:
    """
    Dumpea bytes de ROM desde una dirección PC.
    
    Args:
        mmu: Instancia de MMU
        pc: Program Counter (dirección)
        count: Número de bytes a leer
    
    Returns:
        Lista de bytes leídos
    """
    bytes_list = []
    for i in range(count):
        addr = (pc + i) & 0xFFFF
        # Usar read_raw para evitar restricciones de modo PPU
        byte_val = mmu.read_raw(addr) if hasattr(mmu, 'read_raw') else mmu.read(addr)
        bytes_list.append(byte_val)
    return bytes_list


def disasm_lr35902(bytes_list: List[int], start_pc: int, max_instructions: int = 20) -> List[Tuple[int, str, int]]:
    """
    Desensambla instrucciones LR35902 básicas (clean-room).
    
    Solo decodifica opcodes comunes necesarios para identificar bucles de espera.
    Fuente: Pan Docs - CPU Instruction Set
    
    Args:
        bytes_list: Lista de bytes de ROM
        start_pc: PC inicial
        max_instructions: Máximo de instrucciones a decodificar
    
    Returns:
        Lista de tuplas (pc, mnemónico, bytes_leídos)
    """
    instructions = []
    pc = start_pc
    idx = 0
    
    while idx < len(bytes_list) and len(instructions) < max_instructions:
        if idx >= len(bytes_list):
            break
        
        opcode = bytes_list[idx]
        mnemonic = ""
        bytes_read = 1
        
        # Opcodes de 1 byte
        if opcode == 0x00:
            mnemonic = "NOP"
        elif opcode == 0x76:
            mnemonic = "HALT"
        elif opcode == 0xF3:
            mnemonic = "DI"
        elif opcode == 0xFB:
            mnemonic = "EI"
        elif opcode == 0xC9:
            mnemonic = "RET"
        # LD A, n (0x3E)
        elif opcode == 0x3E:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"LD A, 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "LD A, n"
        # LDH (FF00+n),A (0xE0) - Step 0477
        elif opcode == 0xE0:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                io_name = _get_io_register_name(0xFF00 + n)
                mnemonic = f"LDH ({io_name}),A"
                bytes_read = 2
            else:
                mnemonic = "LDH (FF00+n),A"
        # LD (FF00+C),A (0xE2) - Step 0477
        elif opcode == 0xE2:
            mnemonic = "LD (FF00+C),A"
        # LD A,(FF00+C) (0xF2) - Step 0477
        elif opcode == 0xF2:
            mnemonic = "LD A,(FF00+C)"
        # LD A, (n) (0xF0) - LDH A,(FF00+n)
        elif opcode == 0xF0:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                io_name = _get_io_register_name(0xFF00 + n)
                mnemonic = f"LDH A,({io_name})"
                bytes_read = 2
            else:
                mnemonic = "LDH A,(FF00+n)"
        # LD (a16),A (0xEA) - Step 0477
        elif opcode == 0xEA:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                addr = (hi << 8) | lo
                io_name = _get_io_register_name(addr)
                mnemonic = f"LD ({io_name}),A"
                bytes_read = 3
            else:
                mnemonic = "LD (a16),A"
        # LD A,(a16) (0xFA) - Step 0477
        elif opcode == 0xFA:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                addr = (hi << 8) | lo
                io_name = _get_io_register_name(addr)
                mnemonic = f"LD A,({io_name})"
                bytes_read = 3
            else:
                mnemonic = "LD A,(a16)"
        # Prefijo CB (0xCB) - Step 0477
        elif opcode == 0xCB:
            if idx + 1 < len(bytes_list):
                cb_opcode = bytes_list[idx + 1]
                mnemonic = f"CB {cb_opcode:02X}"
                bytes_read = 2  # Consumir 2 bytes para no desalinear
            else:
                mnemonic = "CB ??"
                bytes_read = 2
        # AND n (0xE6)
        elif opcode == 0xE6:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"AND 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "AND n"
        # JR Z, e (0x28)
        elif opcode == 0x28:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR Z, 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR Z, e"
        # JR NZ, e (0x20)
        elif opcode == 0x20:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR NZ, 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR NZ, e"
        # JR e (0x18)
        elif opcode == 0x18:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR e"
        # CALL nn (0xCD)
        elif opcode == 0xCD:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                nn = (hi << 8) | lo
                mnemonic = f"CALL 0x{nn:04X}"
                bytes_read = 3
            else:
                mnemonic = "CALL nn"
        # LD (HL), A (0x77)
        elif opcode == 0x77:
            mnemonic = "LD (HL), A"
        # INC HL (0x23)
        elif opcode == 0x23:
            mnemonic = "INC HL"
        # DEC HL (0x2B)
        elif opcode == 0x2B:
            mnemonic = "DEC HL"
        # LD A, (HL) (0x7E)
        elif opcode == 0x7E:
            mnemonic = "LD A, (HL)"
        # CP (HL) (0xBE)
        elif opcode == 0xBE:
            mnemonic = "CP (HL)"
        # CP n (0xFE)
        elif opcode == 0xFE:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"CP 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "CP n"
        else:
            # Opcode desconocido
            mnemonic = f"DB 0x{opcode:02X}"
        
        instructions.append((pc, mnemonic, bytes_read))
        pc = (pc + bytes_read) & 0xFFFF
        idx += bytes_read
    
    return instructions
# --- Fin Step 0474 ---


def disasm_window(mmu: PyMMU, pc: int, before: int = 16, after: int = 32) -> List[Tuple[int, str, bool]]:
    """
    Desensambla ventana alrededor de PC para evitar empezar en mitad de instrucción.
    
    Step 0477: Esta función lee bytes alrededor del PC y desensambla desde el inicio
    de la ventana, marcando cuál instrucción corresponde al PC actual.
    
    Args:
        mmu: Instancia MMU
        pc: PC actual (centro de la ventana)
        before: Bytes antes de PC a leer
        after: Bytes después de PC a leer
    
    Returns:
        Lista de (addr, instruction, is_current_pc)
    """
    start_addr = (pc - before) & 0xFFFF
    end_addr = (pc + after) & 0xFFFF
    
    # Leer bytes de ROM
    bytes_data = []
    for addr in range(start_addr, end_addr + 1):
        addr_wrapped = addr & 0xFFFF
        byte_val = mmu.read_raw(addr_wrapped) if hasattr(mmu, 'read_raw') else mmu.read(addr_wrapped)
        bytes_data.append(byte_val)
    
    # Desensamblar desde start_addr
    instructions = []
    offset = 0
    current_pc = pc
    
    while offset < len(bytes_data):
        addr = (start_addr + offset) & 0xFFFF
        
        # Determinar longitud de instrucción
        opcode = bytes_data[offset]
        if opcode == 0xCB:
            bytes_read = 2  # CB prefix consume 2 bytes
        elif opcode in [0xE0, 0xF0, 0xEA, 0xFA]:
            bytes_read = 2 if opcode in [0xE0, 0xF0] else 3  # LDH 2 bytes, LD (a16) 3 bytes
        else:
            # Usar disasm_lr35902 para obtener bytes_read
            inst_list = disasm_lr35902(bytes_data[offset:], addr, max_instructions=1)
            if inst_list:
                _, _, bytes_read = inst_list[0]
            else:
                bytes_read = 1  # Default: 1 byte
        
        # Marcar si es el PC actual
        is_current = (addr == current_pc)
        
        # Obtener mnemónico
        inst_list = disasm_lr35902(bytes_data[offset:], addr, max_instructions=1)
        if inst_list:
            _, mnemonic, _ = inst_list[0]
        else:
            mnemonic = f"DB 0x{opcode:02X}"
        
        instructions.append((addr, mnemonic, is_current))
        offset += bytes_read
        
        if offset >= len(bytes_data):
            break
    
    return instructions
# --- Fin Step 0477 Fase A2 ---


class ROMSmokeRunner:
    """Runner headless para smoke test de ROMs."""
    
    # Constantes del sistema
    CYCLES_PER_FRAME = 70224  # 4.194.304 MHz / 59.7 FPS
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144
    FRAMEBUFFER_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * 3  # RGB
    
    def __init__(self, rom_path: str, max_frames: int = 300, 
                 dump_every: int = 0, dump_png: bool = False,
                 max_seconds: int = 120):
        """
        Inicializa el runner.
        
        Args:
            rom_path: Ruta al archivo ROM
            max_frames: Número máximo de frames a ejecutar
            dump_every: Cada cuántos frames dumpear métricas detalladas (0 = solo final)
            dump_png: Si True, genera PNGs de framebuffers seleccionados
            max_seconds: Timeout máximo de ejecución (segundos)
        """
        self.rom_path = Path(rom_path)
        self.max_frames = max_frames
        self.dump_every = dump_every
        self.dump_png = dump_png
        self.max_seconds = max_seconds
        
        # Validar ROM
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM no encontrada: {self.rom_path}")
        
        # Métricas acumuladas
        self.metrics: List[Dict] = []
        self.first_nonwhite_frame: Optional[int] = None
        self.start_time: float = 0
        
        # Step 0470: Contadores para hotspots
        self.pc_samples: Dict[int, int] = {}  # Dict: PC -> count
        self.step_count = 0
        
        # Inicializar core
        self._init_core()
    
    def _init_core(self):
        """Inicializa componentes core C++ con wiring correcto."""
        # Leer ROM
        with open(self.rom_path, 'rb') as f:
            rom_bytes = f.read()
        
        # Inicializar core (mismo wiring que runtime)
        self.mmu = PyMMU()
        self.regs = PyRegisters()
        self.cpu = PyCPU(self.mmu, self.regs)
        self.ppu = PyPPU(self.mmu)
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        
        # Wiring: MMU ↔ PPU
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
        
        # Cargar ROM
        self.mmu.load_rom_py(rom_bytes)
        
        # Estado post-boot DMG (Step 0401)
        self.regs.a = 0x01  # DMG
        self.regs.b = 0x00
        self.regs.c = 0x13
        self.regs.d = 0x00
        self.regs.e = 0xD8
        self.regs.h = 0x01
        self.regs.l = 0x4D
        self.regs.sp = 0xFFFE
        self.regs.pc = 0x0100
        
        # Registros I/O post-boot
        io_values = [
            (0xFF05, 0x00), (0xFF06, 0x00), (0xFF07, 0x00),  # Timer
            (0xFF10, 0x80), (0xFF11, 0xBF), (0xFF12, 0xF3), (0xFF14, 0xBF),  # Audio CH1
            (0xFF16, 0x3F), (0xFF17, 0x00), (0xFF19, 0xBF),  # Audio CH2
            (0xFF1A, 0x7F), (0xFF1B, 0xFF), (0xFF1C, 0x9F), (0xFF1E, 0xBF),  # Audio CH3
            (0xFF20, 0xFF), (0xFF21, 0x00), (0xFF22, 0x00), (0xFF23, 0xBF),  # Audio CH4
            (0xFF24, 0x77), (0xFF25, 0xF3), (0xFF26, 0xF1),  # Audio control
            (0xFF40, 0x91),  # LCDC
            (0xFF42, 0x00), (0xFF43, 0x00),  # SCY, SCX
            (0xFF45, 0x00),  # LYC
            (0xFF47, 0xFC),  # BGP
            (0xFF48, 0xFF), (0xFF49, 0xFF),  # OBP0, OBP1
            (0xFF4A, 0x00), (0xFF4B, 0x00),  # WY, WX
            (0xFFFF, 0x00),  # IE
        ]
        
        for addr, value in io_values:
            self.mmu.write(addr, value)
    
    def _sample_nonwhite_pixels(self, framebuffer: List[int]) -> int:
        """
        Cuenta píxeles non-white en el framebuffer (muestreo eficiente).
        
        Args:
            framebuffer: Lista RGB [R,G,B,R,G,B,...]
        
        Returns:
            Número de píxeles non-white (muestreados)
        """
        if not framebuffer or len(framebuffer) != self.FRAMEBUFFER_SIZE:
            return 0
        
        count = 0
        # Muestrear cada 8º pixel para eficiencia
        for i in range(0, len(framebuffer), 3 * 8):
            r = framebuffer[i]
            g = framebuffer[i + 1]
            b = framebuffer[i + 2]
            
            # Non-white si cualquier canal < 200
            if r < 200 or g < 200 or b < 200:
                count += 1
        
        # Estimar total (multiplicar por 8 por el muestreo)
        return count * 8
    
    def _calculate_robust_metrics(self, framebuffer: List[int]) -> Dict[str, any]:
        """
        Calcula métricas robustas del framebuffer (Step 0454).
        
        Args:
            framebuffer: Lista RGB [R,G,B,R,G,B,...]
        
        Returns:
            Dict con unique_rgb_count, dominant_ratio, frame_hash, hash_changed
        """
        if not framebuffer or len(framebuffer) != self.FRAMEBUFFER_SIZE:
            return {
                'unique_rgb_count': 0,
                'dominant_ratio': 1.0,
                'frame_hash': 'empty',
                'hash_changed': False
            }
        
        # Muestrear grid 16x16 (256 píxeles)
        # Grid: 160/16 = 10 columnas, 144/16 = 9 filas (144/16 = 9)
        # Muestrear centro de cada celda del grid
        unique_colors = set()
        color_freq = {}
        samples = []
        
        grid_step_x = 160 // 16  # 10 píxeles
        grid_step_y = 144 // 16  # 9 píxeles (aproximado)
        
        for grid_y in range(16):
            for grid_x in range(16):
                # Calcular posición real en framebuffer
                y = (grid_y * grid_step_y) if grid_y < 16 else 143
                x = (grid_x * grid_step_x) if grid_x < 16 else 159
                
                # Asegurar dentro de límites
                y = min(y, 143)
                x = min(x, 159)
                
                # Calcular índice en framebuffer (RGB)
                idx = (y * 160 + x) * 3
                if idx + 2 < len(framebuffer):
                    r = framebuffer[idx]
                    g = framebuffer[idx + 1]
                    b = framebuffer[idx + 2]
                    rgb_tuple = (r, g, b)
                    
                    unique_colors.add(rgb_tuple)
                    color_freq[rgb_tuple] = color_freq.get(rgb_tuple, 0) + 1
                    samples.append(rgb_tuple)
        
        # Calcular dominant_ratio
        max_freq = max(color_freq.values()) if color_freq else 0
        total_samples = len(samples)
        dominant_ratio = max_freq / total_samples if total_samples > 0 else 1.0
        
        # Frame hash (MD5 de muestra)
        sample_bytes = bytes([c for rgb in samples[:100] for c in rgb])  # Primeros 100 píxeles
        frame_hash = hashlib.md5(sample_bytes).hexdigest()[:8]
        
        # Hash changed vs frame anterior
        hash_changed = False
        if hasattr(self, '_last_frame_hash'):
            hash_changed = (frame_hash != self._last_frame_hash)
        self._last_frame_hash = frame_hash
        
        return {
            'unique_rgb_count': len(unique_colors),
            'dominant_ratio': dominant_ratio,
            'frame_hash': frame_hash,
            'hash_changed': hash_changed
        }
    
    def _hash_framebuffer(self, framebuffer: List[int]) -> str:
        """Genera hash simple del framebuffer para detectar cambios."""
        if not framebuffer:
            return "empty"
        
        # Hash de muestra (primeros 1000 bytes para eficiencia)
        sample = bytes(framebuffer[:min(1000, len(framebuffer))])
        return hashlib.md5(sample).hexdigest()[:8]
    
    def _sample_vram_nonzero(self) -> int:
        """
        Cuenta bytes non-zero en VRAM 0x8000-0x9FFF (muestreo por bloques).
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 16º byte (0x2000 bytes / 16 = 512 muestras)
        for addr in range(0x8000, 0xA000, 16):
            value = self.mmu.read(addr)
            if value != 0:
                count += 1
        
        # Estimar total (multiplicar por 16)
        return count * 16
    
    def _sample_vram_nonzero_raw(self) -> int:
        """
        Cuenta bytes non-zero en VRAM usando read_raw (sin restricciones).
        
        Step 0450: Usa read_raw() para diagnóstico confiable, bypassing PPU mode restrictions.
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 16º byte (0x2000 bytes / 16 = 128 muestras)
        for addr in range(0x8000, 0xA000, 16):
            value = self.mmu.read_raw(addr)  # ← RAW, no read()
            if value != 0:
                count += 1
        
        # Estimar total (multiplicar por 16)
        return count * 16
    
    def _sample_oam_nonzero(self) -> int:
        """
        Cuenta bytes non-zero en OAM 0xFE00-0xFE9F (muestreo).
        
        Step 0444: Métricas OAM para validar DMA correctness.
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 4º byte (40 sprites * 4 bytes = 160 bytes, 40 muestras)
        for addr in range(0xFE00, 0xFEA0, 4):
            value = self.mmu.read(addr)
            if value != 0:
                count += 1
        # Estimar total (multiplicar por 4)
        return count * 4
    
    def _collect_metrics(self, frame_idx: int, ly_first: int, ly_mid: int, ly_last: int,
                        stat_first: int, stat_mid: int, stat_last: int) -> Dict:
        """
        Recolecta métricas del frame actual (Step 0443: incluye LY/STAT 3-points).
        
        Args:
            frame_idx: Índice del frame (0-based)
            ly_first: LY al inicio del frame
            ly_mid: LY a mitad del frame
            ly_last: LY al final del frame
            stat_first: STAT al inicio del frame
            stat_mid: STAT a mitad del frame
            stat_last: STAT al final del frame
        
        Returns:
            Diccionario con métricas
        """
        # Obtener framebuffer
        framebuffer = self.ppu.get_framebuffer_rgb()
        
        # Contar píxeles non-white
        nonwhite_pixels = self._sample_nonwhite_pixels(framebuffer)
        
        # Hash del framebuffer
        frame_hash = self._hash_framebuffer(framebuffer)
        
        # Step 0454: Calcular métricas robustas
        robust_metrics = self._calculate_robust_metrics(framebuffer)
        
        # Muestrear VRAM
        vram_nonzero = self._sample_vram_nonzero()
        
        # Step 0450: Muestrear VRAM usando read_raw (diagnóstico confiable)
        vram_nonzero_raw = self._sample_vram_nonzero_raw()
        
        # Step 0444: Muestrear OAM
        oam_nonzero = self._sample_oam_nonzero()
        
        # Leer registros I/O clave
        lcdc = self.mmu.read(0xFF40)
        stat = self.mmu.read(0xFF41)
        bgp = self.mmu.read(0xFF47)
        scy = self.mmu.read(0xFF42)
        scx = self.mmu.read(0xFF43)
        ly = self.mmu.read(0xFF44)
        pc = self.regs.pc
        
        # Step 0463: Derivar modo de tile data y tilemap base
        bg_tile_data_mode = "8000(unsigned)" if (lcdc & 0x10) else "8800(signed)"
        bg_tilemap_base = 0x9C00 if (lcdc & 0x08) else 0x9800
        win_tilemap_base = 0x9C00 if (lcdc & 0x40) else 0x9800
        
        # Step 0465: Contar nonzero bytes en ambos tilemaps usando read_raw() (RAW VRAM, sin restricciones)
        tilemap_nz_9800 = 0
        for addr in range(0x9800, 0x9C00):
            if self.mmu.read_raw(addr) != 0:  # Usar read_raw() para evitar restricciones
                tilemap_nz_9800 += 1
        
        tilemap_nz_9C00 = 0
        for addr in range(0x9C00, 0xA000):
            if self.mmu.read_raw(addr) != 0:  # Usar read_raw()
                tilemap_nz_9C00 += 1
        
        # Leer 16 tile IDs desde el base actual usando read_raw()
        tile_ids_sample = []
        for i in range(16):
            tile_ids_sample.append(self.mmu.read_raw(bg_tilemap_base + i))  # Usar read_raw()
        
        # Step 0474: Métricas IF/LY/STAT quirúrgicas
        if_read_count = self.mmu.get_if_read_count()
        if_write_count = self.mmu.get_if_write_count()
        last_if_read_val = self.mmu.get_last_if_read_val()
        last_if_write_val = self.mmu.get_last_if_write_val()
        last_if_write_pc = self.mmu.get_last_if_write_pc()
        if_writes_0 = self.mmu.get_if_writes_0()
        if_writes_nonzero = self.mmu.get_if_writes_nonzero()
        
        ly_read_min = self.mmu.get_ly_read_min()
        ly_read_max = self.mmu.get_ly_read_max()
        last_ly_read = self.mmu.get_last_ly_read()
        
        last_stat_read = self.mmu.get_last_stat_read()
        
        # Step 0475: Source tagging para IF/IE
        if_reads_program = self.mmu.get_if_reads_program() if hasattr(self.mmu, 'get_if_reads_program') else 0
        if_reads_cpu_poll = self.mmu.get_if_reads_cpu_poll() if hasattr(self.mmu, 'get_if_reads_cpu_poll') else 0
        if_writes_program = self.mmu.get_if_writes_program() if hasattr(self.mmu, 'get_if_writes_program') else 0
        ie_reads_program = self.mmu.get_ie_reads_program() if hasattr(self.mmu, 'get_ie_reads_program') else 0
        ie_reads_cpu_poll = self.mmu.get_ie_reads_cpu_poll() if hasattr(self.mmu, 'get_ie_reads_cpu_poll') else 0
        ie_writes_program = self.mmu.get_ie_writes_program() if hasattr(self.mmu, 'get_ie_writes_program') else 0
        
        # Step 0475: IF Clear on Service tracking
        last_irq_serviced_vector = self.cpu.get_last_irq_serviced_vector() if hasattr(self.cpu, 'get_last_irq_serviced_vector') else 0
        last_irq_serviced_timestamp = self.cpu.get_last_irq_serviced_timestamp() if hasattr(self.cpu, 'get_last_irq_serviced_timestamp') else 0
        last_if_before_service = self.cpu.get_last_if_before_service() if hasattr(self.cpu, 'get_last_if_before_service') else 0
        last_if_after_service = self.cpu.get_last_if_after_service() if hasattr(self.cpu, 'get_last_if_after_service') else 0
        last_if_clear_mask = self.cpu.get_last_if_clear_mask() if hasattr(self.cpu, 'get_last_if_clear_mask') else 0
        
        # Step 0475: Boot logo prefill status
        boot_logo_prefill_enabled = self.mmu.get_boot_logo_prefill_enabled() if hasattr(self.mmu, 'get_boot_logo_prefill_enabled') else 0
        
        metrics = {
            'frame': frame_idx,
            'pc': pc,
            'nonwhite_pixels': nonwhite_pixels,
            'frame_hash': frame_hash,
            'vram_nonzero': vram_nonzero,
            'vram_nonzero_raw': vram_nonzero_raw,  # Step 0450: VRAM raw (sin restricciones)
            'oam_nonzero': oam_nonzero,  # Step 0444: OAM metrics
            'lcdc': lcdc,
            'stat': stat,
            'bgp': bgp,
            'scy': scy,
            'scx': scx,
            'ly': ly,
            # Step 0443: LY/STAT 3-points sampling
            'ly_first': ly_first,
            'ly_mid': ly_mid,
            'ly_last': ly_last,
            'stat_first': stat_first,
            'stat_mid': stat_mid,
            'stat_last': stat_last,
            # Step 0454: Métricas robustas
            'unique_rgb_count': robust_metrics['unique_rgb_count'],
            'dominant_ratio': robust_metrics['dominant_ratio'],
            'frame_hash_robust': robust_metrics['frame_hash'],
            'hash_changed': robust_metrics['hash_changed'],
            # Step 0463: Modo tile data y tilemap base
            'bg_tile_data_mode': bg_tile_data_mode,
            'bg_tilemap_base': bg_tilemap_base,
            'win_tilemap_base': win_tilemap_base,
            # Step 0464: Tilemap nonzero counts y sample
            'tilemap_nz_9800': tilemap_nz_9800,
            'tilemap_nz_9C00': tilemap_nz_9C00,
            'tile_ids_sample': tile_ids_sample,
            # Step 0474: Métricas IF/LY/STAT quirúrgicas
            'if_read_count': if_read_count,
            'if_write_count': if_write_count,
            'last_if_read_val': last_if_read_val,
            'last_if_write_val': last_if_write_val,
            'last_if_write_pc': last_if_write_pc,
            'if_writes_0': if_writes_0,
            'if_writes_nonzero': if_writes_nonzero,
            'ly_read_min': ly_read_min,
            'ly_read_max': ly_read_max,
            'last_ly_read': last_ly_read,
            'last_stat_read': last_stat_read,
            # Step 0475: Source tagging para IF/IE
            'if_reads_program': if_reads_program,
            'if_reads_cpu_poll': if_reads_cpu_poll,
            'if_writes_program': if_writes_program,
            'ie_reads_program': ie_reads_program,
            'ie_reads_cpu_poll': ie_reads_cpu_poll,
            'ie_writes_program': ie_writes_program,
            # Step 0475: IF Clear on Service tracking
            'last_irq_serviced_vector': last_irq_serviced_vector,
            'last_irq_serviced_timestamp': last_irq_serviced_timestamp,
            'last_if_before_service': last_if_before_service,
            'last_if_after_service': last_if_after_service,
            'last_if_clear_mask': last_if_clear_mask,
            # Step 0475: Boot logo prefill status
            'boot_logo_prefill_enabled': boot_logo_prefill_enabled,
        }
        
        # Detectar primer frame non-white
        if self.first_nonwhite_frame is None and nonwhite_pixels > 0:
            self.first_nonwhite_frame = frame_idx
        
        return metrics
    
    def _dump_png(self, frame_idx: int, framebuffer: List[int]):
        """
        Dumped framebuffer a PNG (requiere PIL/Pillow).
        
        Args:
            frame_idx: Índice del frame
            framebuffer: Lista RGB del framebuffer
        """
        try:
            from PIL import Image
        except ImportError:
            print("WARNING: PIL/Pillow no disponible, no se puede generar PNG")
            return
        
        # Crear directorio out/
        out_dir = Path("tools/out")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Convertir lista plana a imagen
        # framebuffer = [R,G,B,R,G,B,...] (160*144*3 = 69120 valores)
        img_data = bytes(framebuffer)
        img = Image.frombytes('RGB', (self.SCREEN_WIDTH, self.SCREEN_HEIGHT), img_data)
        
        # Guardar
        out_path = out_dir / f"frame_{frame_idx:04d}.png"
        img.save(out_path)
        print(f"  [PNG] Guardado: {out_path}")
    
    def run(self):
        """Ejecuta el smoke test."""
        # Step 0465: Imprimir estado de env vars para evidencia (solo en tools, no en runtime)
        import os
        env_vars = [
            'VIBOY_DEBUG_INJECTION',
            'VIBOY_FORCE_BGP',
            'VIBOY_AUTOPRESS',
            'VIBOY_FRAMEBUFFER_TRACE',
            'VIBOY_DEBUG_UI',
            'VIBOY_DEBUG_PPU',
            'VIBOY_DEBUG_IO'
        ]
        
        env_status = []
        for var in env_vars:
            value = os.environ.get(var, '0')
            env_status.append(f"{var}={value}")
        
        print(f"[ENV] {' '.join(env_status)}")
        
        print(f"=" * 80)
        print(f"ROM Smoke Test - Step 0443 (LY/STAT 3-Points Sampling)")
        print(f"=" * 80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Max frames: {self.max_frames}")
        print(f"Max seconds: {self.max_seconds}")
        print(f"Dump every: {self.dump_every} frames" if self.dump_every > 0 else "Dump: final only")
        print(f"Dump PNG: {'Yes' if self.dump_png else 'No'}")
        print(f"-" * 80)
        
        self.start_time = time.time()
        
        # Segmentos del frame para sampling 3-points (Step 0443)
        SEGMENT_1 = 0           # Inicio
        SEGMENT_2 = 35112       # Medio (~50%)
        SEGMENT_3 = 70224       # Final (CYCLES_PER_FRAME)
        
        for frame_idx in range(self.max_frames):
            # Timeout check
            elapsed = time.time() - self.start_time
            if elapsed > self.max_seconds:
                print(f"\nTIMEOUT: {self.max_seconds}s alcanzado, deteniendo en frame {frame_idx}")
                break
            
            # Ejecutar frame por segmentos para sampling 3-points
            frame_cycles = 0
            
            # Segmento 1: 0 → 35112 T-cycles
            while frame_cycles < SEGMENT_2:
                cycles = self.cpu.step()
                self.ppu.step(cycles)
                self.timer.step(cycles)
                frame_cycles += cycles
                
                # Step 0470: Muestrear PC cada N instrucciones
                self.step_count += 1
                if self.step_count % 50 == 0:  # Cada 50 steps
                    pc = self.regs.pc
                    self.pc_samples[pc] = self.pc_samples.get(pc, 0) + 1
            
            # Sample LY/STAT al final del segmento 1 (inicio del frame)
            ly_first = self.mmu.read(0xFF44)
            stat_first = self.mmu.read(0xFF41)
            
            # Segmento 2: 35112 → 70224 T-cycles
            while frame_cycles < SEGMENT_3:
                cycles = self.cpu.step()
                self.ppu.step(cycles)
                self.timer.step(cycles)
                frame_cycles += cycles
                
                # Step 0470: Muestrear PC cada N instrucciones
                self.step_count += 1
                if self.step_count % 50 == 0:  # Cada 50 steps
                    pc = self.regs.pc
                    self.pc_samples[pc] = self.pc_samples.get(pc, 0) + 1
            
            # Sample LY/STAT al final del segmento 2 (medio del frame)
            ly_mid = self.mmu.read(0xFF44)
            stat_mid = self.mmu.read(0xFF41)
            
            # Segmento 3: Ya completado, leer final
            ly_last = self.mmu.read(0xFF44)
            stat_last = self.mmu.read(0xFF41)
            
            # Recolectar métricas (incluye LY/STAT 3-points)
            metrics = self._collect_metrics(frame_idx, ly_first, ly_mid, ly_last, stat_first, stat_mid, stat_last)
            self.metrics.append(metrics)
            
            # --- Step 0469: Snapshot cada 60 frames (o frames 0, 60, 120, 180, 240) ---
            should_snapshot = (frame_idx % 60 == 0) or frame_idx < 3
            if should_snapshot:
                # Leer registros
                pc = self.regs.pc
                ime = self.cpu.get_ime()
                halted = self.cpu.get_halted()
                
                ie = self.mmu.read(0xFFFF)
                if_reg = self.mmu.read(0xFF0F)
                
                # Contadores IRQ (si están expuestos)
                vblank_req = self.ppu.get_vblank_irq_requested_count() if hasattr(self.ppu, 'get_vblank_irq_requested_count') else 0
                vblank_serv = self.cpu.get_vblank_irq_serviced_count() if hasattr(self.cpu, 'get_vblank_irq_serviced_count') else 0
                
                # Step 0470: Contadores IE/IF writes y EI/DI
                ie_write_count = self.mmu.get_ie_write_count() if hasattr(self.mmu, 'get_ie_write_count') else 0
                if_write_count = self.mmu.get_if_write_count() if hasattr(self.mmu, 'get_if_write_count') else 0
                ei_count = self.cpu.get_ei_count() if hasattr(self.cpu, 'get_ei_count') else 0
                di_count = self.cpu.get_di_count() if hasattr(self.cpu, 'get_di_count') else 0
                
                # Step 0477: Tracking de transiciones IME + EI delayed
                ime_set_events_count = self.cpu.get_ime_set_events_count() if hasattr(self.cpu, 'get_ime_set_events_count') else 0
                last_ime_set_pc = self.cpu.get_last_ime_set_pc() if hasattr(self.cpu, 'get_last_ime_set_pc') else 0xFFFF
                last_ime_set_timestamp = self.cpu.get_last_ime_set_timestamp() if hasattr(self.cpu, 'get_last_ime_set_timestamp') else 0
                last_ei_pc = self.cpu.get_last_ei_pc() if hasattr(self.cpu, 'get_last_ei_pc') else 0xFFFF
                last_di_pc = self.cpu.get_last_di_pc() if hasattr(self.cpu, 'get_last_di_pc') else 0xFFFF
                ei_pending = self.cpu.get_ei_pending() if hasattr(self.cpu, 'get_ei_pending') else False
                
                # Step 0477: Timestamps de writes IE/IF
                last_ie_write_timestamp = self.mmu.get_last_ie_write_timestamp() if hasattr(self.mmu, 'get_last_ie_write_timestamp') else 0
                last_if_write_timestamp = self.mmu.get_last_if_write_timestamp() if hasattr(self.mmu, 'get_last_if_write_timestamp') else 0
                
                # Step 0471: Instrumentación microscópica de IE
                last_ie_write_value = self.mmu.get_last_ie_write_value() if hasattr(self.mmu, 'get_last_ie_write_value') else 0
                last_ie_read_value = self.mmu.get_last_ie_read_value() if hasattr(self.mmu, 'get_last_ie_read_value') else 0
                ie_read_count = self.mmu.get_ie_read_count() if hasattr(self.mmu, 'get_ie_read_count') else 0
                last_ie_write_pc = self.mmu.get_last_ie_write_pc() if hasattr(self.mmu, 'get_last_ie_write_pc') else 0
                
                # Step 0470: IO reads top 3
                io_reads = {}
                for io_addr in [0xFF00, 0xFF41, 0xFF44, 0xFF0F, 0xFFFF, 0xFF4D, 0xFF4F, 0xFF70]:
                    count = self.mmu.get_io_read_count(io_addr) if hasattr(self.mmu, 'get_io_read_count') else 0
                    if count > 0:
                        io_reads[io_addr] = count
                
                io_reads_top3 = sorted(io_reads.items(), key=lambda x: x[1], reverse=True)[:3]
                io_reads_str = ' '.join([f"0x{addr:04X}:{count}" for addr, count in io_reads_top3])
                
                # Step 0470: PC hotspots top 3
                pc_hotspots_top3 = sorted(self.pc_samples.items(), key=lambda x: x[1], reverse=True)[:3]
                pc_hotspots_str = ' '.join([f"0x{pc:04X}:{count}" for pc, count in pc_hotspots_top3])
                
                # Tilemap nonzero (RAW)
                tilemap_nz_9800_raw = 0
                for addr in range(0x9800, 0x9C00):
                    if self.mmu.read_raw(addr) != 0:
                        tilemap_nz_9800_raw += 1
                
                tilemap_nz_9C00_raw = 0
                for addr in range(0x9C00, 0xA000):
                    if self.mmu.read_raw(addr) != 0:
                        tilemap_nz_9C00_raw += 1
                
                # Registros PPU
                lcdc = self.mmu.read(0xFF40)
                stat = self.mmu.read(0xFF41)
                ly = self.mmu.read(0xFF44)
                
                # Step 0472: Power-up defaults (DMG)
                bgp = self.mmu.read(0xFF47)
                obp0 = self.mmu.read(0xFF48)
                obp1 = self.mmu.read(0xFF49)
                
                # Step 0472: Speed switch (CGB)
                key1 = self.mmu.read(0xFF4D)
                joyp = self.mmu.read(0xFF00)
                
                # Step 0472: STOP execution
                stop_executed_count = self.cpu.get_stop_executed_count() if hasattr(self.cpu, 'get_stop_executed_count') else 0
                last_stop_pc = self.cpu.get_last_stop_pc() if hasattr(self.cpu, 'get_last_stop_pc') else 0xFFFF
                
                # Step 0472: KEY1 writes
                key1_write_count = self.mmu.get_key1_write_count() if hasattr(self.mmu, 'get_key1_write_count') else 0
                last_key1_write_value = self.mmu.get_last_key1_write_value() if hasattr(self.mmu, 'get_last_key1_write_value') else 0
                last_key1_write_pc = self.mmu.get_last_key1_write_pc() if hasattr(self.mmu, 'get_last_key1_write_pc') else 0xFFFF
                
                # Step 0472: JOYP writes
                joyp_write_count = self.mmu.get_joyp_write_count() if hasattr(self.mmu, 'get_joyp_write_count') else 0
                last_joyp_write_value = self.mmu.get_last_joyp_write_value() if hasattr(self.mmu, 'get_last_joyp_write_value') else 0
                last_joyp_write_pc = self.mmu.get_last_joyp_write_pc() if hasattr(self.mmu, 'get_last_joyp_write_pc') else 0xFFFF
                
                # Step 0471: fb_nonzero = count de índices != 0 en framebuffer (sobre 23040 píxeles)
                fb_nonzero = 0
                try:
                    fb_indices = self.ppu.get_presented_framebuffer_indices()
                    if fb_indices is not None:
                        # fb_indices es bytes, indexable como bytes
                        for idx in range(23040):  # 160 * 144
                            if fb_indices[idx] != 0:
                                fb_nonzero += 1
                except (AttributeError, TypeError, IndexError):
                    fb_nonzero = 0  # Fallback si no está disponible
                
                # Step 0474: Métricas IF/LY/STAT quirúrgicas
                if_read_count = metrics.get('if_read_count', 0)
                if_write_count = metrics.get('if_write_count', 0)
                last_if_read_val = metrics.get('last_if_read_val', 0)
                last_if_write_val = metrics.get('last_if_write_val', 0)
                last_if_write_pc = metrics.get('last_if_write_pc', 0)
                if_writes_0 = metrics.get('if_writes_0', 0)
                if_writes_nonzero = metrics.get('if_writes_nonzero', 0)
                ly_read_min = metrics.get('ly_read_min', 0)
                ly_read_max = metrics.get('ly_read_max', 0)
                last_ly_read = metrics.get('last_ly_read', 0)
                last_stat_read = metrics.get('last_stat_read', 0)
                
                # Step 0475: Source tagging para IF/IE
                if_reads_program = metrics.get('if_reads_program', 0)
                if_reads_cpu_poll = metrics.get('if_reads_cpu_poll', 0)
                if_writes_program = metrics.get('if_writes_program', 0)
                ie_reads_program = metrics.get('ie_reads_program', 0)
                ie_reads_cpu_poll = metrics.get('ie_reads_cpu_poll', 0)
                ie_writes_program = metrics.get('ie_writes_program', 0)
                
                # Step 0475: IF Clear on Service tracking
                last_irq_serviced_vector = metrics.get('last_irq_serviced_vector', 0)
                last_irq_serviced_timestamp = metrics.get('last_irq_serviced_timestamp', 0)
                last_if_before_service = metrics.get('last_if_before_service', 0)
                last_if_after_service = metrics.get('last_if_after_service', 0)
                last_if_clear_mask = metrics.get('last_if_clear_mask', 0)
                
                # Step 0475: Boot logo prefill status
                boot_logo_prefill_enabled = metrics.get('boot_logo_prefill_enabled', 0)
                
                # Step 0474: Obtener PC hotspot #1 y disasembly
                pc_hotspot_1 = None
                disasm_snippet = ""
                io_touched = []
                
                if pc_hotspots_top3:
                    pc_hotspot_1 = pc_hotspots_top3[0][0]  # PC del hotspot más frecuente
                    
                    # Dumpear bytes de ROM en hotspot
                    try:
                        rom_bytes = dump_rom_bytes(self.mmu, pc_hotspot_1, 32)
                        bytes_hex = ''.join(f'{b:02X}' for b in rom_bytes[:16])  # Primeros 16 bytes
                        
                        # Disasembly mínimo (16-20 instrucciones)
                        disasm_instructions = disasm_lr35902(rom_bytes, pc_hotspot_1, 16)
                        disasm_lines = []
                        for inst_pc, mnemonic, _ in disasm_instructions:
                            disasm_lines.append(f"0x{inst_pc:04X}: {mnemonic}")
                        disasm_snippet = " | ".join(disasm_lines[:8])  # Primeras 8 instrucciones
                        
                        # Identificar IO tocado por el bucle (analizar disasm)
                        for inst_pc, mnemonic, _ in disasm_instructions:
                            if "0xFF" in mnemonic:
                                # Extraer dirección IO del mnemónico
                                import re
                                matches = re.findall(r'0x([0-9A-F]{2,4})', mnemonic)
                                for match in matches:
                                    io_addr = int(match, 16)
                                    if 0xFF00 <= io_addr <= 0xFFFF and io_addr not in io_touched:
                                        io_touched.append(io_addr)
                    except Exception as e:
                        disasm_snippet = f"ERROR: {e}"
                
                io_touched_str = ' '.join([f"0x{addr:04X}" for addr in sorted(io_touched)]) if io_touched else "None"
                
                print(f"[SMOKE-SNAPSHOT] Frame={frame_idx} | "
                      f"PC=0x{pc:04X} IME={ime} HALTED={halted} | "
                      f"IE=0x{ie:02X} IF=0x{if_reg:02X} | "
                      f"BGP=0x{bgp:02X} OBP0=0x{obp0:02X} OBP1=0x{obp1:02X} | "
                      f"KEY1=0x{key1:02X} JOYP=0x{joyp:02X} | "
                      f"STOP_count={stop_executed_count} STOP_PC=0x{last_stop_pc:04X} | "
                      f"KEY1_write_count={key1_write_count} KEY1_write_val=0x{last_key1_write_value:02X} KEY1_write_PC=0x{last_key1_write_pc:04X} | "
                      f"JOYP_write_count={joyp_write_count} JOYP_write_val=0x{last_joyp_write_value:02X} JOYP_write_PC=0x{last_joyp_write_pc:04X} | "
                      f"VBlankReq={vblank_req} VBlankServ={vblank_serv} | "
                      f"IEWrite={ie_write_count} IFWrite={if_write_count} EI={ei_count} DI={di_count} | "
                      f"IEWriteVal=0x{last_ie_write_value:02X} IEReadVal=0x{last_ie_read_value:02X} IEReadCount={ie_read_count} IEWritePC=0x{last_ie_write_pc:04X} IEWriteTS={last_ie_write_timestamp} | "
                      f"IME_SetEvents={ime_set_events_count} IME_SetPC=0x{last_ime_set_pc:04X} IME_SetTS={last_ime_set_timestamp} | "
                      f"EI_PC=0x{last_ei_pc:04X} DI_PC=0x{last_di_pc:04X} EI_Pending={1 if ei_pending else 0} | "
                      f"IF_WriteTS={last_if_write_timestamp} | "
                      f"fb_nonzero={fb_nonzero} | "
                      f"IOReadsTop3={io_reads_str} | "
                      f"PCHotspotsTop3={pc_hotspots_str} | "
                      f"PCHotspot1={'0x' + format(pc_hotspot_1, '04X') if pc_hotspot_1 is not None else 'None'} | "
                      f"Disasm={disasm_snippet[:200]} | "  # Limitar a 200 chars
                      f"IOTouched={io_touched_str} | "
                      f"TilemapNZ_9800_RAW={tilemap_nz_9800_raw} TilemapNZ_9C00_RAW={tilemap_nz_9C00_raw} | "
                      f"LCDC=0x{lcdc:02X} STAT=0x{stat:02X} LY={ly} | "
                      f"IF_ReadCount={if_read_count} IF_WriteCount={if_write_count} IF_ReadVal=0x{last_if_read_val:02X} IF_WriteVal=0x{last_if_write_val:02X} IF_WritePC=0x{last_if_write_pc:04X} IF_Writes0={if_writes_0} IF_WritesNonZero={if_writes_nonzero} | "
                      f"LY_ReadMin={ly_read_min} LY_ReadMax={ly_read_max} LY_LastRead={last_ly_read} | "
                      f"STAT_LastRead=0x{last_stat_read:02X} | "
                      f"IF_ReadsProg={if_reads_program} IF_ReadsPoll={if_reads_cpu_poll} IF_WritesProg={if_writes_program} | "
                      f"IE_ReadsProg={ie_reads_program} IE_ReadsPoll={ie_reads_cpu_poll} IE_WritesProg={ie_writes_program} | "
                      f"LastIRQVec=0x{last_irq_serviced_vector:04X} LastIRQTS={last_irq_serviced_timestamp} | "
                      f"IF_BeforeSvc=0x{last_if_before_service:02X} IF_AfterSvc=0x{last_if_after_service:02X} IF_ClearMask=0x{last_if_clear_mask:02X} | "
                      f"BootLogoPrefill={boot_logo_prefill_enabled}")
                
                # Step 0477: Clasificador automático (Caso A/B/C/D)
                classification = self._classify_ime_ie_state(
                    ei_count, ime_set_events_count, ime, ie, vblank_serv
                )
                if classification:
                    print(f"[SMOKE-CLASSIFICATION] {classification}")
            
            # Dump periódico
            if self.dump_every > 0 and (frame_idx + 1) % self.dump_every == 0:
                print(f"[Frame {frame_idx:04d}] PC={metrics['pc']:04X} "
                      f"nonwhite={metrics['nonwhite_pixels']:5d} "
                      f"vram_nz={metrics['vram_nonzero']:4d} "
                      f"oam_nz={metrics['oam_nonzero']:4d} "
                      f"LCDC={metrics['lcdc']:02X} LY={metrics['ly']:02X}")
            
            # Step 0464: Imprimir diagnóstico de tilemap (primeros 5 frames + cada 120)
            should_log_tilemap_diag = (frame_idx < 5) or (frame_idx % 120 == 0)
            if should_log_tilemap_diag:
                tile_ids_str = ''.join(f'{t:02X}' for t in metrics.get('tile_ids_sample', []))
                print(f"LCDC=0x{metrics['lcdc']:02X} | BGMapBase=0x{metrics['bg_tilemap_base']:04X} | TileDataMode={metrics['bg_tile_data_mode']} | "
                      f"BG={(metrics['lcdc'] & 0x01) != 0} Win={(metrics['lcdc'] & 0x20) != 0} | "
                      f"SCX={metrics['scx']} SCY={metrics['scy']} WX={self.mmu.read(0xFF4B)} WY={self.mmu.read(0xFF4A)} LY={metrics['ly']} | "
                      f"TilemapNZ_9800={metrics.get('tilemap_nz_9800', 0)} TilemapNZ_9C00={metrics.get('tilemap_nz_9C00', 0)} | "
                      f"TileIDs[0:16]={tile_ids_str}")
            
            # Step 0463: Imprimir modo tile data en frames loggeados (mantener para compatibilidad)
            if self.dump_every > 0 and (frame_idx % self.dump_every == 0 or frame_idx <= 3 or frame_idx >= self.max_frames - 1):
                print(f"LCDC=0x{metrics['lcdc']:02X} | TileDataMode={metrics['bg_tile_data_mode']} | "
                      f"BGTilemap=0x{metrics['bg_tilemap_base']:04X} | WinTilemap=0x{metrics['win_tilemap_base']:04X} | "
                      f"SCX={metrics['scx']} SCY={metrics['scy']} LY={metrics['ly']}")
                
                # Dump PNG si está habilitado
                if self.dump_png:
                    framebuffer = self.ppu.get_framebuffer_rgb()
                    self._dump_png(frame_idx, framebuffer)
            
            # Step 0454: Imprimir métricas robustas en frames loggeados
            if self.dump_every > 0 and (frame_idx % self.dump_every == 0 or frame_idx <= 3 or frame_idx >= self.max_frames - 1):
                print(f"[ROBUST-METRICS] Frame {frame_idx} | "
                      f"unique_rgb={metrics['unique_rgb_count']} | "
                      f"dominant_ratio={metrics['dominant_ratio']:.3f} | "
                      f"hash={metrics['frame_hash_robust']} | "
                      f"hash_changed={metrics['hash_changed']}")
        
        # Resumen final
        self._print_summary()
    
    def _classify_ime_ie_state(self, ei_count: int, ime_set_events_count: int, 
                                ime: bool, ie: int, vblank_serv: int) -> Optional[str]:
        """
        Step 0477: Clasificador automático para identificar causa raíz de IME/IE en 0.
        
        Clasifica el estado en uno de los casos:
        - Caso A: EI nunca se ejecuta (el juego está atascado antes)
        - Caso B: EI ejecutado pero IME no sube (bug EI delayed enable)
        - Caso C: IME sube pero IE=0 (juego no habilita IE o no lo necesita)
        - Caso D: IME+IE OK pero no hay service (revisar generación de requests)
        
        Args:
            ei_count: Número de veces que se ejecutó EI
            ime_set_events_count: Número de veces que IME se activó
            ime: Estado actual de IME
            ie: Valor actual de IE
            vblank_serv: Número de VBlank IRQs servidos
        
        Returns:
            String con la clasificación o None si no aplica
        """
        # Caso A: EI nunca se ejecuta
        if ei_count == 0 and ime == 0:
            return "CASO_A: EI nunca ejecutado, IME=0 sostenido. El juego está atascado antes de habilitar interrupciones. Buscar condición del loop con disasm real."
        
        # Caso B: EI ejecutado pero IME no sube
        if ei_count > 0 and ime_set_events_count == 0:
            return "CASO_B: EI ejecutado pero IME no sube (ime_set_events_count=0). Bug EI delayed enable casi seguro. Revisar implementación de EI delayed enable en CPU::step()."
        
        # Caso C: IME sube pero IE=0
        if ime == 1 and ie == 0:
            return "CASO_C: IME=1 pero IE=0x00. Juego no habilita IE o no lo necesita. Mirar el loop con disasm para ver si espera otra condición (no IRQ)."
        
        # Caso D: IME+IE OK pero no hay service
        if ime == 1 and ie != 0 and vblank_serv == 0:
            return "CASO_D: IME=1 e IE!=0 pero vblank_serv=0. Revisar generación de requests (PPU/Timer) o masks. Verificar si PPU/Timer están generando IF correctamente."
        
        # Si no encaja en ningún caso, retornar None
        return None
    
    def _print_summary(self):
        """Imprime resumen final de métricas."""
        elapsed = time.time() - self.start_time
        frames_executed = len(self.metrics)
        
        print(f"\n" + "=" * 80)
        print(f"RESUMEN FINAL")
        print(f"=" * 80)
        print(f"Frames ejecutados: {frames_executed}")
        print(f"Tiempo total: {elapsed:.2f}s")
        print(f"")
        
        # Baseline rendimiento (Step 0443)
        if frames_executed > 0:
            fps_approx = frames_executed / elapsed
            ms_per_frame = (elapsed / frames_executed) * 1000
            print(f"RENDIMIENTO:")
            print(f"  FPS aproximado: {fps_approx:.1f}")
            print(f"  ms/frame promedio: {ms_per_frame:.2f}")
            print(f"  Tiempo total: {elapsed:.2f}s")
            print(f"")
        
        if not self.metrics:
            print("Sin métricas recolectadas.")
            return
        
        # Estadísticas de nonwhite_pixels
        nonwhite_values = [m['nonwhite_pixels'] for m in self.metrics]
        min_nw = min(nonwhite_values)
        max_nw = max(nonwhite_values)
        avg_nw = sum(nonwhite_values) / len(nonwhite_values)
        
        print(f"NONWHITE PIXELS (estimado por muestreo):")
        print(f"  Mín: {min_nw:5d}  Máx: {max_nw:5d}  Prom: {avg_nw:5.0f}")
        print(f"  Primer frame > 0: {self.first_nonwhite_frame if self.first_nonwhite_frame is not None else 'NUNCA'}")
        print(f"")
        
        # Estadísticas de VRAM nonzero
        vram_values = [m['vram_nonzero'] for m in self.metrics]
        min_vram = min(vram_values)
        max_vram = max(vram_values)
        avg_vram = sum(vram_values) / len(vram_values)
        
        print(f"VRAM NONZERO (bytes, estimado por muestreo):")
        print(f"  Mín: {min_vram:4d}  Máx: {max_vram:4d}  Prom: {avg_vram:4.0f}")
        print(f"")
        
        # Step 0450: Estadísticas de VRAM nonzero RAW (sin restricciones)
        vram_raw_values = [m['vram_nonzero_raw'] for m in self.metrics]
        min_vram_raw = min(vram_raw_values)
        max_vram_raw = max(vram_raw_values)
        avg_vram_raw = sum(vram_raw_values) / len(vram_raw_values)
        
        print(f"VRAM NONZERO RAW (bytes, read_raw, sin restricciones) - Step 0450:")
        print(f"  Mín: {min_vram_raw:4d}  Máx: {max_vram_raw:4d}  Prom: {avg_vram_raw:4.0f}")
        print(f"")
        
        # Step 0444: Estadísticas de OAM nonzero
        oam_values = [m['oam_nonzero'] for m in self.metrics]
        min_oam = min(oam_values)
        max_oam = max(oam_values)
        avg_oam = sum(oam_values) / len(oam_values)
        
        print(f"OAM NONZERO (bytes, estimado por muestreo) - Step 0444:")
        print(f"  Mín: {min_oam:4d}  Máx: {max_oam:4d}  Prom: {avg_oam:4.0f}")
        print(f"")
        
        # Step 0454: Estadísticas de métricas robustas
        unique_rgb_values = [m['unique_rgb_count'] for m in self.metrics]
        dominant_ratio_values = [m['dominant_ratio'] for m in self.metrics]
        min_unique = min(unique_rgb_values) if unique_rgb_values else 0
        max_unique = max(unique_rgb_values) if unique_rgb_values else 0
        avg_unique = sum(unique_rgb_values) / len(unique_rgb_values) if unique_rgb_values else 0
        min_dominant = min(dominant_ratio_values) if dominant_ratio_values else 1.0
        max_dominant = max(dominant_ratio_values) if dominant_ratio_values else 1.0
        avg_dominant = sum(dominant_ratio_values) / len(dominant_ratio_values) if dominant_ratio_values else 1.0
        
        print(f"ROBUST METRICS (Step 0454):")
        print(f"  unique_rgb_count: Mín={min_unique}  Máx={max_unique}  Prom={avg_unique:.1f}")
        print(f"  dominant_ratio: Mín={min_dominant:.3f}  Máx={max_dominant:.3f}  Prom={avg_dominant:.3f}")
        print(f"")
        
        # Resumen I/O con LY/STAT 3-points (Step 0443)
        print(f"I/O RESUMEN (primeros 3 frames) - LY/STAT 3-Points:")
        for i in range(min(3, len(self.metrics))):
            m = self.metrics[i]
            print(f"  Frame {m['frame']:04d}: PC={m['pc']:04X} LCDC={m['lcdc']:02X} BGP={m['bgp']:02X}")
            print(f"    LY: first={m['ly_first']:02X} mid={m['ly_mid']:02X} last={m['ly_last']:02X}")
            print(f"    STAT: first={m['stat_first']:02X} mid={m['stat_mid']:02X} last={m['stat_last']:02X}")
        
        if len(self.metrics) > 6:
            print(f"  ... ({len(self.metrics) - 6} frames omitidos) ...")
        
        if len(self.metrics) > 3:
            print(f"I/O RESUMEN (últimos 3 frames) - LY/STAT 3-Points:")
            for i in range(max(3, len(self.metrics) - 3), len(self.metrics)):
                m = self.metrics[i]
                print(f"  Frame {m['frame']:04d}: PC={m['pc']:04X} LCDC={m['lcdc']:02X} BGP={m['bgp']:02X}")
                print(f"    LY: first={m['ly_first']:02X} mid={m['ly_mid']:02X} last={m['ly_last']:02X}")
                print(f"    STAT: first={m['stat_first']:02X} mid={m['stat_mid']:02X} last={m['stat_last']:02X}")
        
        print(f"")
        
        # Diagnóstico LY/STAT (Step 0443)
        print(f"DIAGNÓSTICO LY/STAT 3-POINTS:")
        ly_samples_all = []
        stat_samples_all = []
        for m in self.metrics[:10]:  # Primeros 10 frames
            ly_samples_all.extend([m['ly_first'], m['ly_mid'], m['ly_last']])
            stat_samples_all.extend([m['stat_first'], m['stat_mid'], m['stat_last']])
        
        unique_ly = len(set(ly_samples_all))
        unique_stat = len(set(stat_samples_all))
        max_ly = max(ly_samples_all) if ly_samples_all else 0
        min_ly = min(ly_samples_all) if ly_samples_all else 0
        
        if unique_ly == 1 and ly_samples_all[0] == 0:
            print(f"  ⚠️  LY siempre 0 en los 3 puntos → BUG REAL (LY no avanza o lectura incorrecta)")
        elif unique_ly == 1:
            print(f"  ⚠️  LY siempre {ly_samples_all[0]:02X} en los 3 puntos → posible bug (LY no avanza)")
        else:
            print(f"  ✅ LY varía correctamente (range: {min_ly:02X}..{max_ly:02X}, únicos: {unique_ly})")
            print(f"     → Sampling issue resuelto: LY avanza durante el frame")
        
        if unique_stat == 1:
            print(f"  ⚠️  STAT siempre igual ({stat_samples_all[0]:02X}) → posible bug en PPU.step() (modo no cambia)")
        else:
            stat_modes = [s & 0x03 for s in stat_samples_all]
            unique_modes = len(set(stat_modes))
            print(f"  ✅ STAT varía correctamente (modos únicos: {unique_modes}, range: {min(stat_modes)}..{max(stat_modes)})")
        
        print(f"")
        
        # Step 0450: Log MBC writes summary si está disponible
        if hasattr(self.mmu, 'log_mbc_writes_summary'):
            self.mmu.log_mbc_writes_summary()
            print(f"")
        
        # Diagnóstico preliminar
        print(f"DIAGNÓSTICO PRELIMINAR:")
        if max_nw == 0:
            print(f"  ⚠️  Framebuffer BLANCO (0 píxeles non-white)")
            
            # Step 0450: Comparar VRAM normal vs RAW
            if max_vram_raw > 0 and max_vram == 0:
                print(f"  🔍 VRAM RAW tiene datos (max={max_vram_raw}) pero read() devuelve 0")
                print(f"     → Caso: Restricciones de acceso (modo PPU/banking) bloquean lectura")
            elif max_vram_raw > 0:
                print(f"  🔍 VRAM non-zero detectado (max={max_vram_raw} raw, {max_vram} normal)")
                print(f"     → Caso 1: Probable bug en fetch BG/window/paleta")
            else:
                print(f"  🔍 VRAM completamente vacío (0 bytes non-zero)")
                print(f"     → Caso 2: CPU progresa pero writes no llegan a VRAM")
                print(f"        o juego espera condición (joypad/interrupts/DMA/MBC)")
        else:
            print(f"  ✅ Framebuffer NO BLANCO (max={max_nw} píxeles non-white)")
            print(f"     → Sistema funciona correctamente")
        
        print(f"=" * 80)


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="ROM Smoke Test - Herramienta headless para diagnóstico (Step 0442)"
    )
    parser.add_argument("rom", type=str, help="Ruta al archivo ROM (.gb o .gbc)")
    parser.add_argument("--frames", type=int, default=300,
                        help="Número máximo de frames a ejecutar (default: 300)")
    parser.add_argument("--dump-every", type=int, default=0,
                        help="Cada cuántos frames dumpear métricas (default: 0 = solo final)")
    parser.add_argument("--dump-png", action="store_true",
                        help="Generar PNGs de framebuffers seleccionados")
    parser.add_argument("--max-seconds", type=int, default=120,
                        help="Timeout máximo de ejecución en segundos (default: 120)")
    
    args = parser.parse_args()
    
    try:
        runner = ROMSmokeRunner(
            rom_path=args.rom,
            max_frames=args.frames,
            dump_every=args.dump_every,
            dump_png=args.dump_png,
            max_seconds=args.max_seconds
        )
        runner.run()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

