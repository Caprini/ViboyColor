"""
Viboy - Sistema Principal (Placa Base)

La clase Viboy representa la "placa base" del emulador, integrando todos los componentes:
- CPU (LR35902)
- MMU (Memory Management Unit)
- Cartridge (Cartucho con ROM)

El bucle principal (Game Loop) ejecuta instrucciones continuamente, simulando el funcionamiento
de la Game Boy real que ejecuta ~4.194.304 ciclos por segundo (4.19 MHz).

Concepto de System Clock:
- La Game Boy funciona a 4.194304 MHz (4.194.304 ciclos por segundo)
- Un fotograma (frame) dura aproximadamente 70.224 ciclos de reloj para mantener 59.7 FPS
- Sin control de timing, un ordenador moderno ejecutaría millones de instrucciones por segundo
  y el juego iría a velocidad de la luz

En esta primera iteración, no implementamos sincronización de tiempo real (sleep).
Solo ejecutamos instrucciones en un bucle continuo. La sincronización se añadirá más adelante
cuando implementemos la PPU (Pixel Processing Unit) y el renderizado.

Fuente: Pan Docs - System Clock, Timing
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

# Importar componentes C++ (core nativo)
try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters, PyTimer, PyJoypad
    CPP_CORE_AVAILABLE = True
except ImportError:
    # Fallback a componentes Python si C++ no está compilado
    PyCPU = None  # type: ignore
    PyMMU = None  # type: ignore
    PyPPU = None  # type: ignore
    PyRegisters = None  # type: ignore
    PyTimer = None  # type: ignore
    PyJoypad = None  # type: ignore
    CPP_CORE_AVAILABLE = False
    logger.warning("viboy_core no disponible. Usando componentes Python (más lentos).")

from .cpu.core import CPU
from .cpu.registers import Registers
from .gpu.ppu import PPU
from .io.joypad import Joypad
from .io.timer import Timer
from .memory.cartridge import Cartridge
from .memory.mmu import MMU

# Importar Renderer condicionalmente (requiere pygame)
try:
    from .gpu.renderer import Renderer
except ImportError:
    Renderer = None  # type: ignore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Viboy:
    """
    Sistema principal del emulador Viboy Color.
    
    Actúa como la "placa base" que integra todos los componentes:
    - CPU (LR35902)
    - MMU (Memory Management Unit)
    - Cartridge (Cartucho con ROM)
    
    Proporciona el bucle principal de ejecución que simula el funcionamiento
    continuo de la Game Boy.
    """

    # Frecuencia del reloj del sistema (Game Boy original)
    # 4.194304 MHz = 4.194.304 ciclos por segundo
    SYSTEM_CLOCK_HZ = 4_194_304
    
    # Ciclos por fotograma (frame) para mantener 59.7 FPS
    # 4.194.304 / 59.7 ≈ 70.224 ciclos por frame
    CYCLES_PER_FRAME = 70_224

    def __init__(self, rom_path: str | Path | None = None, use_cpp_core: bool = True) -> None:
        """
        Inicializa el sistema Viboy.
        
        Si se proporciona una ruta a ROM, carga el cartucho automáticamente.
        Si no se proporciona, el sistema se inicializa sin cartucho (modo de prueba).
        
        Args:
            rom_path: Ruta opcional al archivo ROM (.gb o .gbc)
            use_cpp_core: Si es True, usa componentes C++ (más rápido). Si False o no disponible, usa Python.
            
        Raises:
            FileNotFoundError: Si el archivo ROM no existe
            IOError: Si hay un error al leer el archivo ROM
        """
        # Determinar si usar core C++ o Python
        self._use_cpp = use_cpp_core and CPP_CORE_AVAILABLE
        
        # Inicializar componentes
        self._cartridge: Cartridge | None = None
        self._mmu: MMU | PyMMU | None = None
        self._cpu: CPU | PyCPU | None = None
        self._ppu: PPU | PyPPU | None = None
        self._regs: Registers | PyRegisters | None = None
        self._renderer: Renderer | None = None
        self._joypad: Joypad | None = None
        self._timer: Timer | None = None
        
        # Contador de ciclos totales ejecutados
        self._total_cycles: int = 0
        
        # Contador de ciclos desde el último render (para heartbeat visual)
        self._cycles_since_render: int = 0
        
        # Sistema de trazado desactivado para rendimiento (comentado)
        # self._trace_active: bool = False
        # self._trace_counter: int = 0
        # self._prev_lcdc: int = 0  # Valor anterior de LCDC para detectar cambios
        
        # Control de FPS (sincronización de tiempo)
        # pygame.time.Clock permite limitar la velocidad del bucle a 60 FPS
        try:
            import pygame
            self._clock = pygame.time.Clock()
        except ImportError:
            self._clock = None
            logger.warning("Pygame no disponible. Control de FPS desactivado.")
        
        # Si se proporciona ROM, cargarla
        if rom_path is not None:
            self.load_cartridge(rom_path)
        else:
            # Inicializar sin cartucho (modo de prueba)
            if self._use_cpp:
                # Usar componentes C++
                self._regs = PyRegisters()
                self._mmu = PyMMU()
                self._cpu = PyCPU(self._mmu, self._regs)
                self._ppu = PyPPU(self._mmu)
                # CRÍTICO: Conectar PPU a MMU para lectura dinámica del registro STAT (0xFF41)
                self._mmu.set_ppu(self._ppu)
                # CRÍTICO: Conectar PPU a CPU para sincronización ciclo a ciclo
                self._cpu.set_ppu(self._ppu)
            else:
                # Usar componentes Python (fallback)
                self._mmu = MMU(None)
                # Inicializar Timer
                self._timer = Timer()
                # Conectar Timer a MMU para lectura/escritura de DIV/TIMA/TMA/TAC
                self._mmu.set_timer(self._timer)
                # Conectar MMU al Timer para solicitar interrupciones
                self._timer.set_mmu(self._mmu)
                # Inicializar Joypad con la MMU
                self._joypad = Joypad(self._mmu)
                # Conectar Joypad a MMU para lectura/escritura de P1
                self._mmu.set_joypad(self._joypad)
                self._cpu = CPU(self._mmu)
                self._ppu = PPU(self._mmu)
                # Conectar PPU a MMU para que pueda leer LY
                self._mmu.set_ppu(self._ppu)
            
            # Inicializar Renderer si está disponible
            if Renderer is not None:
                try:
                    # Renderer necesita acceso a MMU (puede ser Python o C++)
                    self._renderer = Renderer(self._mmu, scale=3)
                    # Conectar Renderer a MMU solo si es MMU Python (tile caching)
                    if not self._use_cpp and isinstance(self._mmu, MMU):
                        self._mmu.set_renderer(self._renderer)
                except ImportError:
                    logger.warning("Pygame no disponible. El renderer no se inicializará.")
                    self._renderer = None
            else:
                self._renderer = None
            
            self._initialize_post_boot_state()
        
        logger.info(f"Sistema Viboy inicializado ({'C++ Core' if self._use_cpp else 'Python Core'})")

    def load_cartridge(self, rom_path: str | Path) -> None:
        """
        Carga un cartucho (ROM) en el sistema.
        
        Args:
            rom_path: Ruta al archivo ROM (.gb o .gbc)
            
        Raises:
            FileNotFoundError: Si el archivo ROM no existe
            IOError: Si hay un error al leer el archivo ROM
        """
        # Cargar cartucho
        self._cartridge = Cartridge(rom_path)
        
        # Obtener datos de la ROM como bytes
        rom_data = bytes(self._cartridge._rom_data)
        
        if self._use_cpp:
            # Usar componentes C++
            self._regs = PyRegisters()
            self._mmu = PyMMU()
            # Cargar ROM en MMU C++
            self._mmu.load_rom_py(rom_data)
            # Inicializar CPU, PPU y Timer con componentes C++
            self._cpu = PyCPU(self._mmu, self._regs)
            self._ppu = PyPPU(self._mmu)
            # CRÍTICO: Timer necesita MMU para solicitar interrupciones cuando TIMA desborda
            self._timer = PyTimer(self._mmu)
            self._joypad = PyJoypad()
            # CRÍTICO: Conectar PPU a MMU para lectura dinámica del registro STAT (0xFF41)
            self._mmu.set_ppu(self._ppu)
            # CRÍTICO: Conectar PPU a CPU para sincronización ciclo a ciclo
            self._cpu.set_ppu(self._ppu)
            # CRÍTICO: Conectar Timer a CPU y MMU para actualización del registro DIV (0xFF04)
            self._cpu.set_timer(self._timer)
            self._mmu.set_timer(self._timer)
            # CRÍTICO: Conectar Joypad a MMU para lectura/escritura del registro P1 (0xFF00)
            self._mmu.set_joypad(self._joypad)
            print("⏰ Timer C++ conectado al sistema.")
            print("🎮 Joypad C++ conectado al sistema.")
        else:
            # Usar componentes Python (fallback)
            self._mmu = MMU(self._cartridge)
            
            # Inicializar Timer
            self._timer = Timer()
            # Conectar Timer a MMU para lectura/escritura de DIV/TIMA/TMA/TAC
            self._mmu.set_timer(self._timer)
            # Conectar MMU al Timer para solicitar interrupciones
            self._timer.set_mmu(self._mmu)
            
            # Inicializar Joypad con la MMU
            self._joypad = Joypad(self._mmu)
            
            # Conectar Joypad a MMU para lectura/escritura de P1
            self._mmu.set_joypad(self._joypad)
            
            # Inicializar CPU con la MMU
            self._cpu = CPU(self._mmu)
            
            # Inicializar PPU con la MMU
            self._ppu = PPU(self._mmu)
            
            # Conectar PPU a MMU para que pueda leer LY (evitar dependencia circular)
            self._mmu.set_ppu(self._ppu)
        
        # Inicializar Renderer si está disponible
        if Renderer is not None:
            try:
                # Pasar PPU C++ al renderer si está disponible
                ppu_for_renderer = self._ppu if self._use_cpp else None
                # Pasar Joypad al renderer para mapeo de teclas
                joypad_for_renderer = self._joypad if self._use_cpp else (self._joypad if hasattr(self, '_joypad') else None)
                self._renderer = Renderer(self._mmu, scale=3, use_cpp_ppu=self._use_cpp, ppu=ppu_for_renderer, joypad=joypad_for_renderer)
                # Conectar Renderer a MMU solo si es MMU Python (tile caching)
                if not self._use_cpp and isinstance(self._mmu, MMU):
                    self._mmu.set_renderer(self._renderer)
            except ImportError:
                logger.warning("Pygame no disponible. El renderer no se inicializará.")
                self._renderer = None
        else:
            self._renderer = None
        
        # Simular "Post-Boot State" (sin Boot ROM)
        self._initialize_post_boot_state()
        
        # Mostrar información del cartucho cargado
        header_info = self._cartridge.get_header_info()
        logger.info(
            f"Cartucho cargado: {header_info['title']} | "
            f"Tipo: {header_info['cartridge_type']} | "
            f"ROM: {header_info['rom_size']}KB | "
            f"RAM: {header_info['ram_size']}KB | "
            f"Core: {'C++' if self._use_cpp else 'Python'}"
        )

    def _initialize_post_boot_state(self) -> None:
        """
        Inicializa el estado post-arranque (Post-Boot State).
        
        En un Game Boy real, la Boot ROM interna (256 bytes) inicializa:
        - PC = 0x0100 (inicio del código del cartucho)
        - SP = 0xFFFE (top de la pila)
        - Registros con valores específicos
        
        CRÍTICO: El registro A determina la identidad del hardware:
        - A = 0x01: Game Boy Clásica (DMG)
        - A = 0x11: Game Boy Color (CGB)
        - A = 0xFF: Game Boy Pocket / Super Game Boy
        
        VERSIÓN 0.0.1: Usamos valores CGB para compatibilidad máxima.
        Los juegos Dual Mode (CGB/DMG) detectan CGB y pueden usar características
        avanzadas (VRAM Banks, paletas CGB) que ahora están implementadas.
        
        Valores exactos de Boot ROM CGB (según documentación):
        - AF = 0x1180 (A=0x11, F=0x80: Z flag activo)
        - BC = 0x0000
        - DE = 0xFF56
        - HL = 0x000D
        - SP = 0xFFFE
        - PC = 0x0100
        
        Fuente: Pan Docs - Boot ROM, Post-Boot State, Game Boy Color detection
        """
        if self._cpu is None or self._regs is None:
            return
        
        if self._use_cpp:
            # Step 0196: Los registros ya están inicializados con valores Post-BIOS
            # en el constructor de CoreRegisters (C++). El constructor establece automáticamente:
            # - AF = 0x01B0 (A=0x01 indica DMG, F=0xB0: Z=1, N=0, H=1, C=1)
            # - BC = 0x0013
            # - DE = 0x00D8
            # - HL = 0x014D
            # - SP = 0xFFFE
            # - PC = 0x0100
            #
            # Esto simula el estado exacto que la Boot ROM oficial deja en la CPU
            # antes de transferir el control al código del cartucho.
            #
            # CRÍTICO: No modificamos los registros aquí. El constructor de CoreRegisters
            # ya los inicializó correctamente. Solo verificamos que todo esté bien.
            
            # Verificación del estado Post-BIOS (sin modificar valores)
            expected_af = 0x01B0
            expected_bc = 0x0013
            expected_de = 0x00D8
            expected_hl = 0x014D
            expected_sp = 0xFFFE
            expected_pc = 0x0100
            
            if (self._regs.af != expected_af or 
                self._regs.bc != expected_bc or 
                self._regs.de != expected_de or 
                self._regs.hl != expected_hl or 
                self._regs.sp != expected_sp or 
                self._regs.pc != expected_pc):
                logger.error(
                    f"⚠️ ERROR: Estado Post-BIOS incorrecto. "
                    f"AF=0x{self._regs.af:04X} (esperado 0x{expected_af:04X}), "
                    f"BC=0x{self._regs.bc:04X} (esperado 0x{expected_bc:04X}), "
                    f"DE=0x{self._regs.de:04X} (esperado 0x{expected_de:04X}), "
                    f"HL=0x{self._regs.hl:04X} (esperado 0x{expected_hl:04X}), "
                    f"SP=0x{self._regs.sp:04X} (esperado 0x{expected_sp:04X}), "
                    f"PC=0x{self._regs.pc:04X} (esperado 0x{expected_pc:04X})"
                )
            else:
                logger.info(
                    f"✅ Post-Boot State (DMG): PC=0x{self._regs.pc:04X}, "
                    f"SP=0x{self._regs.sp:04X}, "
                    f"A=0x{self._regs.a:02X} (DMG mode), "
                    f"F=0x{self._regs.f:02X} (Z={self._regs.flag_z}, N={self._regs.flag_n}, H={self._regs.flag_h}, C={self._regs.flag_c}), "
                    f"BC=0x{self._regs.bc:04X}, "
                    f"DE=0x{self._regs.de:04X}, "
                    f"HL=0x{self._regs.hl:04X}"
                )
                logger.info("🔧 Core C++: Estado Post-BIOS inicializado automáticamente en constructor (Step 0196)")
        else:
            # Usar componentes Python (fallback)
            # PC inicializado a 0x0100 (inicio del código del cartucho)
            self._cpu.registers.set_pc(0x0100)
            
            # SP inicializado a 0xFFFE (top de la pila)
            self._cpu.registers.set_sp(0xFFFE)
            
            # VERSIÓN 0.0.1: Valores CGB exactos para compatibilidad máxima
            # AF = 0x1180 (A=0x11 indica CGB, F=0x80 con Z flag activo)
            self._cpu.registers.set_a(0x11)
            self._cpu.registers.set_f(0x80)  # Z flag activo
            
            # BC = 0x0000
            self._cpu.registers.set_b(0x00)
            self._cpu.registers.set_c(0x00)
            
            # DE = 0xFF56
            self._cpu.registers.set_d(0xFF)
            self._cpu.registers.set_e(0x56)
            
            # HL = 0x000D
            self._cpu.registers.set_h(0x00)
            self._cpu.registers.set_l(0x0D)
            
            # Verificar que se estableció correctamente
            reg_a = self._cpu.registers.get_a()
            if reg_a != 0x11:
                logger.error(f"⚠️ ERROR: Registro A no se estableció correctamente. Esperado: 0x11, Obtenido: 0x{reg_a:02X}")
            else:
                logger.info(
                    f"✅ Post-Boot State (CGB): PC=0x{self._cpu.registers.get_pc():04X}, "
                    f"SP=0x{self._cpu.registers.get_sp():04X}, "
                    f"A=0x{reg_a:02X} (CGB mode), "
                    f"BC=0x{self._cpu.registers.get_bc():04X}, "
                    f"DE=0x{self._cpu.registers.get_de():04X}, "
                    f"HL=0x{self._cpu.registers.get_hl():04X}"
                )

    def _execute_cpu_only(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU sin actualizar periféricos (PPU/Timer).
        
        Este método es para uso interno en el bucle optimizado con batching.
        NO actualiza PPU ni Timer; solo ejecuta la CPU y devuelve los ciclos consumidos.
        
        Returns:
            Número de M-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        if self._use_cpp:
            # CPU C++: verificar HALT y ejecutar
            if self._cpu.get_halted():
                cycles = self._cpu.step()
                if cycles == 0:
                    cycles = 4  # Protección contra bucle infinito
                self._total_cycles += cycles
                return cycles
            
            # Ejecutar una instrucción normal
            cycles = self._cpu.step()
            
            # CRÍTICO: Protección contra bucle infinito
            if cycles == 0:
                cycles = 4  # Forzar avance para no colgar
            
            # Acumular ciclos totales
            self._total_cycles += cycles
            
            return cycles
        else:
            # CPU Python: comportamiento original
            # Si la CPU está en HALT, ejecutar un paso normal (el batching manejará múltiples ciclos)
            if self._cpu.halted:
                cycles = self._cpu.step()
                if cycles == 0:
                    cycles = 4  # Protección contra bucle infinito
                self._total_cycles += cycles
                return cycles
            
            # Ejecutar una instrucción normal
            cycles = self._cpu.step()
            
            # CRÍTICO: Protección contra bucle infinito
            if cycles == 0:
                cycles = 4  # Forzar avance para no colgar
            
            # Acumular ciclos totales
            self._total_cycles += cycles
            
            return cycles
    
    def _execute_cpu_timer_only(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU y actualiza el Timer, pero NO la PPU.
        
        Este método es para uso en la arquitectura basada en scanlines, donde:
        - CPU y Timer se ejecutan cada instrucción (para precisión del RNG)
        - PPU se actualiza una vez por scanline (456 ciclos) para rendimiento
        
        Returns:
            Número de T-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        if self._use_cpp:
            # CPU C++: verificar HALT y ejecutar
            if self._cpu.get_halted():
                cycles = self._cpu.step()
                if cycles == 0:
                    cycles = 4  # Protección contra bucle infinito
                self._total_cycles += cycles
            else:
                # Ejecutar una instrucción normal
                cycles = self._cpu.step()
                
                # CRÍTICO: Protección contra bucle infinito
                if cycles == 0:
                    cycles = 4  # Forzar avance para no colgar
                
                # Acumular ciclos totales
                self._total_cycles += cycles
            
            # NOTA: Timer aún no está en C++, así que no lo actualizamos
            # TODO: Implementar Timer C++ o mantener compatibilidad con Python
            # Por ahora, solo devolvemos los T-Cycles
            t_cycles = cycles * 4
            
            # CRÍTICO: Garantizar que siempre devolvemos al menos algunos ciclos
            # Si por alguna razón t_cycles es 0, forzar avance mínimo
            if t_cycles <= 0:
                logger.warning(f"⚠️ ADVERTENCIA: _execute_cpu_timer_only() devolvió {t_cycles} T-Cycles. Forzando avance mínimo.")
                t_cycles = 16  # 4 M-Cycles * 4 = 16 T-Cycles (mínimo seguro)
            
            return t_cycles
        else:
            # CPU Python: comportamiento original
            # Si la CPU está en HALT, ejecutar un paso normal
            if self._cpu.halted:
                cycles = self._cpu.step()
                if cycles == 0:
                    cycles = 4  # Protección contra bucle infinito
                self._total_cycles += cycles
            else:
                # Ejecutar una instrucción normal
                cycles = self._cpu.step()
                
                # CRÍTICO: Protección contra bucle infinito
                if cycles == 0:
                    cycles = 4  # Forzar avance para no colgar
                
                # Acumular ciclos totales
                self._total_cycles += cycles
            
            # Convertir M-Cycles a T-Cycles y actualizar Timer
            # CRÍTICO: El Timer debe actualizarse cada instrucción para mantener
            # la precisión del RNG (usado por juegos como Tetris)
            t_cycles = cycles * 4
            
            # CRÍTICO: Garantizar que siempre devolvemos al menos algunos ciclos
            # Si por alguna razón t_cycles es 0, forzar avance mínimo
            if t_cycles <= 0:
                logger.warning(f"⚠️ ADVERTENCIA: _execute_cpu_timer_only() (Python) devolvió {t_cycles} T-Cycles. Forzando avance mínimo.")
                t_cycles = 16  # 4 M-Cycles * 4 = 16 T-Cycles (mínimo seguro)
            
            if self._timer is not None:
                self._timer.tick(t_cycles)
            
            return t_cycles
    
    def tick(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU.
        
        Este método es el "latido" del sistema. Cada llamada ejecuta una instrucción
        y devuelve los ciclos consumidos.
        
        CRÍTICO: Si la CPU está en HALT, el reloj del sistema sigue funcionando.
        La PPU y el Timer deben seguir avanzando normalmente. Para evitar que el
        emulador se quede congelado esperando interrupciones, cuando la CPU está
        en HALT avanzamos múltiples ciclos hasta que ocurra algo (interrupción
        o cambio de estado).
        
        Returns:
            Número de M-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
            
        Fuente: Pan Docs - HALT behavior, System Clock
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        if self._use_cpp:
            # CPU C++: verificar HALT y ejecutar
            if self._cpu.get_halted():
                # Avanzar ciclos hasta que ocurra algo (interrupción o cambio de estado)
                # Usamos un límite de seguridad para evitar bucles infinitos
                max_halt_cycles = 114  # 114 M-Cycles = 456 T-Cycles = 1 línea de PPU
                total_cycles = 0
                
                for _ in range(max_halt_cycles):
                    # Ejecutar un tick de HALT (consume 1 M-Cycle)
                    cycles = self._cpu.step()
                    
                    # CRÍTICO: Protección contra bucle infinito también en HALT
                    if cycles == 0:
                        cycles = 4  # Forzar avance para no colgar
                    
                    total_cycles += cycles
                    
                    # Convertir a T-Cycles y avanzar subsistemas
                    t_cycles = cycles * 4
                    if self._ppu is not None:
                        self._ppu.step(t_cycles)
                    # Timer aún no está en C++, omitir por ahora
                    
                    # Si la CPU se despertó (ya no está en HALT), salir
                    if not self._cpu.get_halted():
                        break
                
                self._total_cycles += total_cycles
                return total_cycles
            
            # Ejecutar una instrucción normal
            cycles = self._cpu.step()
            
            # CRÍTICO: Protección contra bucle infinito
            if cycles == 0:
                cycles = 4  # Forzar avance para no colgar
            
            # Acumular ciclos totales
            self._total_cycles += cycles
            
            # Avanzar la PPU (motor de timing)
            # La CPU devuelve M-Cycles, pero la PPU necesita T-Cycles
            # Conversión: 1 M-Cycle = 4 T-Cycles
            t_cycles = cycles * 4
            if self._ppu is not None:
                self._ppu.step(t_cycles)
            
            # Timer aún no está en C++, omitir por ahora
            
            return cycles
        else:
            # CPU Python: comportamiento original
            # Si la CPU está en HALT, simular el paso del tiempo de forma más agresiva
            # para que la PPU y el Timer puedan avanzar y generar interrupciones.
            # En hardware real, el reloj sigue funcionando durante HALT.
            if self._cpu.halted:
                # Avanzar ciclos hasta que ocurra algo (interrupción o cambio de estado)
                # Usamos un límite de seguridad para evitar bucles infinitos
                max_halt_cycles = 114  # 114 M-Cycles = 456 T-Cycles = 1 línea de PPU
                total_cycles = 0
                
                for _ in range(max_halt_cycles):
                    # Ejecutar un tick de HALT (consume 1 M-Cycle)
                    cycles = self._cpu.step()
                    
                    # CRÍTICO: Protección contra bucle infinito también en HALT
                    if cycles == 0:
                        cycles = 4  # Forzar avance para no colgar
                    
                    total_cycles += cycles
                    
                    # Convertir a T-Cycles y avanzar subsistemas
                    t_cycles = cycles * 4
                    if self._ppu is not None:
                        self._ppu.step(t_cycles)
                    if self._timer is not None:
                        self._timer.tick(t_cycles)
                    
                    # Si la CPU se despertó (ya no está en HALT), salir
                    if not self._cpu.halted:
                        break
                
                self._total_cycles += total_cycles
                return total_cycles
            
            # Ejecutar una instrucción normal
            cycles = self._cpu.step()
            
            # CRÍTICO: Protección contra bucle infinito
            if cycles == 0:
                cycles = 4  # Forzar avance para no colgar
            
            # Acumular ciclos totales
            self._total_cycles += cycles
            
            # Avanzar la PPU (motor de timing)
            t_cycles = cycles * 4
            if self._ppu is not None:
                self._ppu.step(t_cycles)
            
            # Avanzar el Timer
            if self._timer is not None:
                self._timer.tick(t_cycles)
            
            return cycles

    def run(self, debug: bool = False) -> None:
        """
        Ejecuta el bucle principal del emulador (Game Loop).
        
        VERSIÓN 0.0.2: ARQUITECTURA FINAL - BUCLE DE EMULACIÓN NATIVO EN C++
        
        Esta arquitectura mueve el bucle de emulación de grano fino completamente a C++,
        eliminando la sobrecarga de llamadas entre Python y C++ y permitiendo sincronización
        ciclo a ciclo precisa. La PPU se actualiza después de cada instrucción de la CPU,
        resolviendo definitivamente los deadlocks de polling.
        
        ARQUITECTURA:
        1. Bucle Externo (por Frame): Se repite mientras el emulador esté corriendo.
        2. Bucle Medio (por Scanline): Se repite 154 veces (número total de líneas).
        3. Llamada a C++: Para cada scanline, se llama a cpu.run_scanline() que ejecuta
           el bucle completo de 456 T-Cycles en C++ nativo, actualizando la PPU después
           de cada instrucción.
        
        Este diseño garantiza que:
        - La PPU se actualiza después de cada instrucción, permitiendo cambios de modo
          en los ciclos exactos.
        - Los bucles de polling de la CPU pueden leer cambios de estado de la PPU
          inmediatamente, rompiendo deadlocks.
        - El rendimiento es máximo al ejecutarse todo el bucle crítico en C++ nativo.
        
        Args:
            debug: Si es True, activa el modo debug con trazas detalladas (no implementado aún)
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
            
        Fuente: Pan Docs - System Clock, Timing, Frame Rate, LCD Timing
        """
        if self._cpu is None or self._mmu is None or self._ppu is None:
            raise RuntimeError("El emulador no está inicializado.")
        
        # Constantes de timing
        # Fuente: Pan Docs - LCD Timing
        SCANLINES_PER_FRAME = 154  # Total de líneas por frame (144 visibles + 10 V-Blank)
        
        # Configuración de rendimiento
        TARGET_FPS = 60
        
        # Contador de frames
        self.frame_count = 0
        self.running = True
        self.verbose = True  # Para heartbeat
        
        print("🚀 Ejecutando el núcleo C++ con bucle de emulación nativo...")
        
        try:
            # Bucle principal del emulador
            while self.running:
                # --- Step 0200: La limpieza del framebuffer ahora es responsabilidad de la PPU ---
                # La PPU limpia el framebuffer sincrónicamente cuando LY se resetea a 0,
                # eliminando la condición de carrera entre Python y C++.
                
                # --- Bucle de Frame Completo (154 scanlines) ---
                framebuffer_to_render = None
                
                for line in range(SCANLINES_PER_FRAME):
                    # ✅ PROTECCIÓN: Verificar running antes de cada scanline
                    if not self.running:
                        break
                    
                    # C++ se encarga de toda la emulación de una scanline
                    # El método run_scanline() ejecuta instrucciones hasta acumular
                    # 456 T-Cycles, actualizando la PPU después de cada instrucción
                    if self._use_cpp:
                        self._cpu.run_scanline()
                        
                        # --- Step 0219: SNAPSHOT INMUTABLE ---
                        # Verificar si el frame está listo usando el método de la PPU
                        if self._ppu is not None:
                            if self._ppu.get_frame_ready_and_reset():
                                # 1. Obtener la vista directa de C++
                                raw_view = self._ppu.framebuffer
                                
                                # 2. --- STEP 0219: SNAPSHOT INMUTABLE ---
                                # Hacemos una copia profunda inmediata a la memoria de Python.
                                # Esto "congela" el frame y nos protege de cualquier cambio en C++.
                                fb_data = bytearray(raw_view)
                                # ----------------------------------------
                                
                                # --- Sonda de Datos (Actualizada) ---
                                if not hasattr(self, '_debug_frame_printed'):
                                    self._debug_frame_printed = False
                                
                                if not self._debug_frame_printed:
                                    p0 = fb_data[0]
                                    mid = fb_data[23040 // 2]
                                    print(f"\n--- [PYTHON SNAPSHOT PROBE] ---")
                                    print(f"Pixel 0 (Snapshot): {p0} (Esperado: 3)")
                                    # Confirmamos que BGP es correcto
                                    print(f"BGP Register: 0x{self._mmu.read(0xFF47):02X}")
                                    print(f"-------------------------------\n")
                                    self._debug_frame_printed = True
                                
                                # 3. Guardar la COPIA SEGURA para el renderizador
                                framebuffer_to_render = fb_data
                                # ----------------------------------------
                    else:
                        # Fallback para modo Python (arquitectura antigua)
                        # Este código se mantiene por compatibilidad pero no debería usarse
                        CYCLES_PER_SCANLINE = 456
                        cycles_this_scanline = 0
                        while cycles_this_scanline < CYCLES_PER_SCANLINE:
                            if not self.running:
                                break
                            m_cycles = self._cpu.step()
                            if m_cycles == 0:
                                m_cycles = 1
                            is_halted = self._cpu.halted
                            if is_halted:
                                t_cycles = 4
                            else:
                                t_cycles = m_cycles * 4
                            cycles_this_scanline += t_cycles
                            if self._timer is not None:
                                self._timer.tick(t_cycles)
                        self._ppu.step(CYCLES_PER_SCANLINE)
                
                # --- Fin del Frame ---
                # En este punto, se ha dibujado un frame completo (154 scanlines)
                
                # Renderizado en Python (solo si hay un frame listo)
                if self._renderer:
                    should_continue = self._handle_pygame_events()
                    if not should_continue:
                        self.running = False
                        break
                    
                    # --- Step 0219: Pasar snapshot inmutable al renderizador ---
                    # Si tenemos un framebuffer capturado (snapshot), pasarlo al renderer
                    if framebuffer_to_render is not None:
                        # Pasar la COPIA SEGURA al renderizador
                        self._renderer.render_frame(framebuffer_data=framebuffer_to_render)
                    else:
                        # Fallback: el renderer leerá el framebuffer directamente desde la PPU
                        self._renderer.render_frame()
                    
                    # Sincronización con el reloj del host para mantener 60 FPS
                    if self._clock is not None:
                        self._clock.tick(TARGET_FPS)
                    
                    # Título con FPS (cada 60 frames para no frenar)
                    if self.frame_count % 60 == 0 and self._clock is not None:
                        try:
                            import pygame
                            fps = self._clock.get_fps()
                            pygame.display.set_caption(f"Viboy Color v0.0.2 - FPS: {fps:.1f}")
                        except ImportError:
                            pass
                
                # Heartbeat (opcional, para depuración)
                if self.verbose and self.frame_count % 60 == 0:
                    # Obtener LY y modo de la PPU
                    ly_value = 0
                    mode_value = 0
                    lcdc_value = 0
                    
                    try:
                        if self._use_cpp:
                            ly_value = self._ppu.ly
                            mode_value = self._ppu.mode
                            lcdc_value = self._mmu.read(0xFF40)
                        else:
                            ly_value = self._ppu.get_ly()
                            mode_value = self._ppu.get_mode()
                            lcdc_value = self._mmu.read(0xFF40)
                    except (AttributeError, Exception):
                        pass
                    
                    logger.info(
                        f"💓 Heartbeat ... LY={ly_value} | Mode={mode_value} | LCDC={lcdc_value:02X}"
                    )
                
                self.frame_count += 1
        
        except KeyboardInterrupt:
            # Salir limpiamente con Ctrl+C
            pass
        
        except NotImplementedError as e:
            # Opcode no implementado
            logger.error(f"Opcode no implementado: {e}")
            raise
        
        except Exception as e:
            # Otro error inesperado
            logger.error(f"Error inesperado: {e}", exc_info=True)
            raise
        finally:
            # Cerrar renderer si está activo
            if self._renderer is not None:
                self._renderer.quit()

    def get_total_cycles(self) -> int:
        """
        Devuelve el número total de ciclos ejecutados desde el inicio.
        
        Returns:
            Número total de M-Cycles ejecutados
        """
        return self._total_cycles

    @property
    def registers(self) -> Registers | PyRegisters | None:
        """
        Devuelve la instancia de registros (compatible con Python y C++).
        
        Returns:
            Instancia de Registers (Python) o PyRegisters (C++), o None si no está inicializada
        """
        return self._regs
    
    def get_cpu(self) -> CPU | None:
        """
        Devuelve la instancia de la CPU (para tests y debugging).
        
        Returns:
            Instancia de CPU o None si no está inicializada
        """
        return self._cpu

    def get_mmu(self) -> MMU | None:
        """
        Devuelve la instancia de la MMU (para tests y debugging).
        
        Returns:
            Instancia de MMU o None si no está inicializada
        """
        return self._mmu

    def get_cartridge(self) -> Cartridge | None:
        """
        Devuelve la instancia del cartucho (para tests y debugging).
        
        Returns:
            Instancia de Cartridge o None si no hay cartucho cargado
        """
        return self._cartridge

    def get_ppu(self) -> PPU | None:
        """
        Devuelve la instancia de la PPU (para tests y debugging).
        
        Returns:
            Instancia de PPU o None si no está inicializada
        """
        return self._ppu
    
    def _handle_pygame_events(self) -> bool:
        """
        Maneja eventos de Pygame (cierre de ventana y teclado para Joypad).
        
        IMPORTANTE: En macOS, pygame.event.pump() es necesario para que la ventana se actualice.
        
        Returns:
            True si se debe continuar ejecutando, False si se debe cerrar
        """
        if self._renderer is None:
            return True
        
        try:
            import pygame
            # En macOS (y algunos otros sistemas), pygame.event.pump() es necesario
            # para que la ventana se actualice correctamente
            pygame.event.pump()
            
            # Mapeo de teclas a botones del Joypad
            # Múltiples teclas mapean al mismo botón para mayor comodidad
            key_mapping: dict[int, str] = {
                pygame.K_UP: "up",
                pygame.K_DOWN: "down",
                pygame.K_LEFT: "left",
                pygame.K_RIGHT: "right",
                pygame.K_z: "a",      # Z o A para botón A
                pygame.K_a: "a",       # Alternativa: A también mapea a botón A
                pygame.K_x: "b",       # X o S para botón B
                pygame.K_s: "b",       # Alternativa: S también mapea a botón B
                pygame.K_RETURN: "start",
                pygame.K_RSHIFT: "select",
            }
            
            # Mapeo de nombres de botones (strings) a índices numéricos para PyJoypad C++
            # El wrapper Cython espera índices: 0-3 (dirección), 4-7 (acción)
            # 0=Derecha, 1=Izquierda, 2=Arriba, 3=Abajo, 4=A, 5=B, 6=Select, 7=Start
            button_index_map: dict[str, int] = {
                "right": 0,
                "left": 1,
                "up": 2,
                "down": 3,
                "a": 4,
                "b": 5,
                "select": 6,
                "start": 7,
            }
            
            # Obtener todos los eventos pendientes
            for event in pygame.event.get():
                # Manejar cierre de ventana
                if event.type == pygame.QUIT:
                    return False
                
                # Manejar eventos de teclado para el Joypad
                if self._joypad is not None:
                    if event.type == pygame.KEYDOWN:
                        button = key_mapping.get(event.key)
                        if button:
                            logger.debug(f"KEY PRESS: {event.key} -> button '{button}'")
                            # CORRECCIÓN: Convertir string a índice y usar press_button()
                            if isinstance(self._joypad, PyJoypad):
                                button_index = button_index_map.get(button)
                                if button_index is not None:
                                    self._joypad.press_button(button_index)
                            else:
                                # Fallback para Joypad Python (usa strings)
                                self._joypad.press(button)
                    elif event.type == pygame.KEYUP:
                        button = key_mapping.get(event.key)
                        if button:
                            logger.debug(f"KEY RELEASE: {event.key} -> button '{button}'")
                            # CORRECCIÓN: Convertir string a índice y usar release_button()
                            if isinstance(self._joypad, PyJoypad):
                                button_index = button_index_map.get(button)
                                if button_index is not None:
                                    self._joypad.release_button(button_index)
                            else:
                                # Fallback para Joypad Python (usa strings)
                                self._joypad.release(button)
            
            return True
        except ImportError:
            # pygame no disponible, usar método del renderer como fallback
            return self._renderer.handle_events()

