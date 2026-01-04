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

