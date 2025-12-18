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

    def __init__(self, rom_path: str | Path | None = None) -> None:
        """
        Inicializa el sistema Viboy.
        
        Si se proporciona una ruta a ROM, carga el cartucho automáticamente.
        Si no se proporciona, el sistema se inicializa sin cartucho (modo de prueba).
        
        Args:
            rom_path: Ruta opcional al archivo ROM (.gb o .gbc)
            
        Raises:
            FileNotFoundError: Si el archivo ROM no existe
            IOError: Si hay un error al leer el archivo ROM
        """
        # Inicializar componentes
        self._cartridge: Cartridge | None = None
        self._mmu: MMU | None = None
        self._cpu: CPU | None = None
        self._ppu: PPU | None = None
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
                    self._renderer = Renderer(self._mmu, scale=3)
                    # Conectar Renderer a MMU para Tile Caching (marcado de tiles dirty)
                    self._mmu.set_renderer(self._renderer)
                except ImportError:
                    logger.warning("Pygame no disponible. El renderer no se inicializará.")
                    self._renderer = None
            else:
                self._renderer = None
            self._initialize_post_boot_state()
        
        logger.info("Sistema Viboy inicializado")

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
        
        # Inicializar MMU con el cartucho
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
                self._renderer = Renderer(self._mmu, scale=3)
                # Conectar Renderer a MMU para Tile Caching (marcado de tiles dirty)
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
            f"RAM: {header_info['ram_size']}KB"
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
        if self._cpu is None:
            return
        
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
                    # Silenciado para rendimiento: solo forzar avance
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
                
                # Si hay interrupciones pendientes, la CPU debería despertarse
                # en el siguiente handle_interrupts(), así que continuamos
            
            self._total_cycles += total_cycles
            return total_cycles
        
        # Ejecutar una instrucción normal
        cycles = self._cpu.step()
        
        # CRÍTICO: Protección contra bucle infinito
        # Si la CPU devuelve 0 ciclos, el contador de tiempo nunca avanza
        # y el emulador se congela. Forzamos al menos 4 ciclos para evitar deadlock.
        if cycles == 0:
            # Silenciado para rendimiento: solo forzar avance
            cycles = 4  # Forzar avance para no colgar
        
        # Acumular ciclos totales
        self._total_cycles += cycles
        
        # Avanzar la PPU (motor de timing)
        # La CPU devuelve M-Cycles, pero la PPU necesita T-Cycles
        # Conversión: 1 M-Cycle = 4 T-Cycles
        t_cycles = cycles * 4
        if self._ppu is not None:
            self._ppu.step(t_cycles)
        
        # Avanzar el Timer
        # El Timer también necesita T-Cycles
        if self._timer is not None:
            self._timer.tick(t_cycles)
        
        return cycles

    def run(self, debug: bool = False) -> None:
        """
        Ejecuta el bucle principal del emulador (Game Loop).
        
        VERSIÓN 0.0.1: ARQUITECTURA BASADA EN SCANLINES (HÍBRIDA)
        - CPU y Timer: se ejecutan cada instrucción (precisión del RNG)
        - PPU: se actualiza una vez por scanline (456 ciclos) para rendimiento
        - Input: se lee cada frame
        - Equilibrio perfecto entre rendimiento y precisión
        
        ARQUITECTURA:
        - Bucle principal: ejecuta frames completos (70224 T-Cycles)
        - Bucle de scanline: ejecuta 456 T-Cycles por línea
        - Dentro del scanline: CPU y Timer se ejecutan cada instrucción
        - Al final del scanline: PPU se actualiza una vez (mucho más rápido)
        - Renderizado: cuando PPU indica frame listo
        - Sincronización: pygame.Clock limita a 60 FPS
        
        Esta arquitectura reduce el coste de la PPU en un 99% (154 actualizaciones
        por frame en lugar de ~17.556) mientras mantiene la precisión del Timer
        necesaria para juegos como Tetris que usan DIV para RNG.
        
        Este método ejecuta instrucciones continuamente hasta que se interrumpe
        (Ctrl+C) o se produce un error.
        
        Args:
            debug: Si es True, activa el modo debug con trazas detalladas (no implementado aún)
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
            
        Fuente: Pan Docs - System Clock, Timing, Frame Rate, LCD Timing
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        # Constantes de timing
        # Fuente: Pan Docs - LCD Timing
        CYCLES_PER_FRAME = 70_224  # T-Cycles por frame (154 líneas * 456 ciclos)
        CYCLES_PER_LINE = 456       # T-Cycles por scanline
        
        # Configuración de rendimiento
        TARGET_FPS = 60
        
        # Contador de frames para título
        frame_count = 0
        
        try:
            # BUCLE PRINCIPAL: Por frame
            while True:
                # 1. Gestionar Input (una vez por frame)
                if self._renderer is not None:
                    should_continue = self._handle_pygame_events()
                    if not should_continue:
                        break
                
                # 2. Ejecutar un frame completo (70224 T-Cycles)
                frame_cycles = 0
                while frame_cycles < CYCLES_PER_FRAME:
                    # --- BUCLE DE SCANLINE (456 ciclos) ---
                    line_cycles = 0
                    while line_cycles < CYCLES_PER_LINE:
                        # A. Ejecutar CPU y Timer (cada instrucción)
                        # CRÍTICO: El Timer debe actualizarse cada instrucción
                        # para mantener la precisión del RNG (usado por Tetris)
                        t_cycles = self._execute_cpu_timer_only()
                        
                        line_cycles += t_cycles
                    
                    # --- FIN DE SCANLINE ---
                    # B. Actualizar PPU una vez por línea (Mucho más rápido)
                    # La PPU debe avanzar exactamente 456 ciclos por línea
                    # Nota: Si line_cycles > 456, la PPU procesará 456 y los sobrantes
                    # se acumularán en el siguiente scanline (comportamiento correcto)
                    if self._ppu is not None:
                        # Actualizar PPU con exactamente 456 ciclos (una línea completa)
                        # Los ciclos sobrantes (si los hay) se procesarán en la siguiente línea
                        self._ppu.step(CYCLES_PER_LINE)
                    
                    # Acumular ciclos del frame (usamos CYCLES_PER_LINE para mantener
                    # sincronización exacta, aunque line_cycles pueda ser ligeramente mayor)
                    frame_cycles += CYCLES_PER_LINE
                
                # 3. Renderizado si es V-Blank
                if self._ppu is not None and self._ppu.is_frame_ready():
                    if self._renderer is not None:
                        self._renderer.render_frame()
                        try:
                            import pygame
                            pygame.display.flip()
                        except ImportError:
                            pass
                
                # 4. Sincronización FPS
                if self._clock is not None:
                    self._clock.tick(TARGET_FPS)
                
                # 5. Título con FPS (cada 60 frames para no frenar)
                frame_count += 1
                if frame_count % 60 == 0 and self._clock is not None:
                    try:
                        import pygame
                        fps = self._clock.get_fps()
                        pygame.display.set_caption(f"Viboy Color v0.0.1 - FPS: {fps:.1f}")
                    except ImportError:
                        pass
        
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
                            self._joypad.press(button)
                    elif event.type == pygame.KEYUP:
                        button = key_mapping.get(event.key)
                        if button:
                            self._joypad.release(button)
            
            return True
        except ImportError:
            # pygame no disponible, usar método del renderer como fallback
            return self._renderer.handle_events()

