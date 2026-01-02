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

# Importar core C++ (obligatorio para herramienta headless)
try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters, PyTimer, PyJoypad
    NATIVE_AVAILABLE = True
except ImportError:
    print("ERROR: viboy_core no está disponible. Compilar primero con:")
    print("  python setup.py build_ext --inplace")
    sys.exit(1)


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
        
        # Muestrear VRAM
        vram_nonzero = self._sample_vram_nonzero()
        
        # Leer registros I/O clave
        lcdc = self.mmu.read(0xFF40)
        stat = self.mmu.read(0xFF41)
        bgp = self.mmu.read(0xFF47)
        scy = self.mmu.read(0xFF42)
        scx = self.mmu.read(0xFF43)
        ly = self.mmu.read(0xFF44)
        pc = self.regs.pc
        
        metrics = {
            'frame': frame_idx,
            'pc': pc,
            'nonwhite_pixels': nonwhite_pixels,
            'frame_hash': frame_hash,
            'vram_nonzero': vram_nonzero,
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
            
            # Sample LY/STAT al final del segmento 1 (inicio del frame)
            ly_first = self.mmu.read(0xFF44)
            stat_first = self.mmu.read(0xFF41)
            
            # Segmento 2: 35112 → 70224 T-cycles
            while frame_cycles < SEGMENT_3:
                cycles = self.cpu.step()
                self.ppu.step(cycles)
                self.timer.step(cycles)
                frame_cycles += cycles
            
            # Sample LY/STAT al final del segmento 2 (medio del frame)
            ly_mid = self.mmu.read(0xFF44)
            stat_mid = self.mmu.read(0xFF41)
            
            # Segmento 3: Ya completado, leer final
            ly_last = self.mmu.read(0xFF44)
            stat_last = self.mmu.read(0xFF41)
            
            # Recolectar métricas (incluye LY/STAT 3-points)
            metrics = self._collect_metrics(frame_idx, ly_first, ly_mid, ly_last, stat_first, stat_mid, stat_last)
            self.metrics.append(metrics)
            
            # Dump periódico
            if self.dump_every > 0 and (frame_idx + 1) % self.dump_every == 0:
                print(f"[Frame {frame_idx:04d}] PC={metrics['pc']:04X} "
                      f"nonwhite={metrics['nonwhite_pixels']:5d} "
                      f"vram_nz={metrics['vram_nonzero']:4d} "
                      f"LCDC={metrics['lcdc']:02X} LY={metrics['ly']:02X}")
                
                # Dump PNG si está habilitado
                if self.dump_png:
                    framebuffer = self.ppu.get_framebuffer_rgb()
                    self._dump_png(frame_idx, framebuffer)
        
        # Resumen final
        self._print_summary()
    
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
        
        # Diagnóstico preliminar
        print(f"DIAGNÓSTICO PRELIMINAR:")
        if max_nw == 0:
            print(f"  ⚠️  Framebuffer BLANCO (0 píxeles non-white)")
            
            if max_vram > 0:
                print(f"  🔍 VRAM non-zero detectado (max={max_vram})")
                print(f"     → Caso 1: Probable bug en fetch BG/window/paleta")
            else:
                print(f"  🔍 VRAM completamente vacío (0 bytes non-zero)")
                print(f"     → Caso 2: CPU progresa pero writes no llegan a VRAM")
                print(f"        o juego espera condición (joypad/interrupts/DMA)")
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

