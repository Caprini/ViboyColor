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
        
        # Estado de V-Blank anterior (para detectar transición)
        self._prev_vblank: bool = False
        
        # Sistema de trazado activado por LCDC=0x80 (Trap Trace)
        # Se activa cuando se detecta que LCDC se escribe con 0x80
        self._trace_active: bool = False
        self._trace_counter: int = 0
        self._prev_lcdc: int = 0  # Valor anterior de LCDC para detectar cambios
        
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
            except ImportError:
                logger.warning("Pygame no disponible. El renderer no se inicializará.")
                self._renderer = None
        else:
            self._renderer = None
        
        # Simular "Post-Boot State" (sin Boot ROM)
        self._initialize_post_boot_state()
        
        logger.info(f"Cartucho cargado: {self._cartridge.get_header_info()['title']}")

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
        
        Los juegos Dual Mode (CGB/DMG) leen el registro A al inicio para detectar
        el tipo de hardware y ajustar su comportamiento. Si detectan CGB (A=0x11),
        intentan usar características avanzadas (VRAM Banks, paletas CGB) que aún
        no están implementadas, resultando en pantalla negra.
        
        Por ahora, forzamos A=0x01 para ejecutar en modo DMG (compatible con nuestro
        emulador actual). Más adelante, cuando implementemos características CGB,
        podremos cambiar esto a 0x11.
        
        Fuente: Pan Docs - Boot ROM, Post-Boot State, Game Boy Color detection
        """
        if self._cpu is None:
            return
        
        # PC inicializado a 0x0100 (inicio del código del cartucho)
        self._cpu.registers.set_pc(0x0100)
        
        # SP inicializado a 0xFFFE (top de la pila)
        self._cpu.registers.set_sp(0xFFFE)
        
        # CRÍTICO: Forzar modo DMG (Game Boy Clásica)
        # A = 0x01 indica que es una Game Boy Clásica, no Color
        # Esto hace que los juegos Dual Mode usen el código compatible con DMG
        self._cpu.registers.set_a(0x01)
        
        # Verificar que se estableció correctamente
        reg_a = self._cpu.registers.get_a()
        if reg_a != 0x01:
            logger.error(f"⚠️ ERROR: Registro A no se estableció correctamente. Esperado: 0x01, Obtenido: 0x{reg_a:02X}")
        else:
            logger.info(
                f"✅ Post-Boot State: PC=0x{self._cpu.registers.get_pc():04X}, "
                f"SP=0x{self._cpu.registers.get_sp():04X}, "
                f"A=0x{reg_a:02X} (DMG mode forzado)"
            )

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
        
        Este método ejecuta instrucciones continuamente hasta que se interrumpe
        (Ctrl+C) o se produce un error.
        
        En modo debug, imprime información detallada de cada instrucción ejecutada:
        - PC (Program Counter)
        - Opcode
        - Estado de los registros principales
        
        Args:
            debug: Si es True, activa el modo debug con trazas detalladas
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        logger.info("Iniciando bucle principal de ejecución...")
        
        # Heartbeat inicial: mostrar estado al inicio para diagnóstico
        if self._mmu is not None:
            pc = self._cpu.registers.get_pc()
            reg_a = self._cpu.registers.get_a()
            lcdc = self._mmu.read_byte(0xFF40)
            bgp = self._mmu.read_byte(0xFF47)
            logger.info(
                f"🚀 Inicio: PC=0x{pc:04X} | A=0x{reg_a:02X} (DMG={'✅' if reg_a == 0x01 else '❌'}) | "
                f"LCDC=0x{lcdc:02X} | BGP=0x{bgp:02X}"
            )
        else:
            pc = self._cpu.registers.get_pc()
            reg_a = self._cpu.registers.get_a()
            logger.info(f"🚀 Inicio: PC=0x{pc:04X} | A=0x{reg_a:02X} (DMG={'✅' if reg_a == 0x01 else '❌'})")
        
        # CRÍTICO: Forzar un render inicial para mostrar el visual heartbeat
        # Esto asegura que la ventana muestre algo incluso si el juego no entra en V-Blank
        if self._renderer is not None:
            logger.info("🖼️  Forzando render inicial para mostrar visual heartbeat...")
            self._renderer.render_frame()
        
        # Contador de frames para heartbeat (cada 60 frames ≈ 1 segundo)
        frame_count = 0
        
        # Inicializar valor previo de LCDC para detección de cambios
        if self._mmu is not None:
            self._prev_lcdc = self._mmu.read_byte(0xFF40)
        
        try:
            while True:
                # CRÍTICO: Llamar a pygame.event.pump() en cada iteración para evitar
                # que Windows marque la ventana como "No responde"
                if self._renderer is not None:
                    try:
                        import pygame
                        pygame.event.pump()
                    except ImportError:
                        pass
                
                # Manejar eventos de Pygame (cierre de ventana y teclado)
                if self._renderer is not None:
                    # Manejar eventos de ventana y teclado
                    should_continue = self._handle_pygame_events()
                    if not should_continue:
                        logger.info("Ventana cerrada por el usuario")
                        break
                
                # Obtener estado antes de ejecutar (para debug y trace)
                pc_before = self._cpu.registers.get_pc()
                opcode = self._mmu.read_byte(pc_before) if self._mmu else 0
                
                # Detectar cambio de LCDC a 0x80 (LCD ON sin fondo)
                # Esto activa el sistema de trazado para ver qué ocurre después
                if self._mmu is not None:
                    current_lcdc = self._mmu.read_byte(0xFF40)
                    # Si LCDC cambió de algo distinto a 0x80 a 0x80, activar trace
                    if current_lcdc == 0x80 and self._prev_lcdc != 0x80 and not self._trace_active:
                        self._trace_active = True
                        self._trace_counter = 0
                        print(f"\n{'='*80}")
                        print(f"🔍 TRACE ACTIVADO: LCDC cambió a 0x80 (LCD ON sin fondo)")
                        print(f"   PC actual: 0x{pc_before:04X} | Opcode: 0x{opcode:02X}")
                        print(f"{'='*80}\n")
                    self._prev_lcdc = current_lcdc
                
                # Ejecutar una instrucción
                cycles = self.tick()
                
                # Sistema de trazado: imprimir información detallada si está activo
                # Aumentado a 1000 instrucciones para capturar hasta V-Blank (LY=144)
                # 144 líneas × ~38 instrucciones/línea ≈ 5,472 instrucciones necesarias
                # Usamos 1000 como compromiso entre información y rendimiento
                if self._trace_active and self._trace_counter < 1000:
                    regs = self._cpu.registers
                    # Leer registros de hardware relevantes
                    if self._mmu is not None:
                        if_reg = self._mmu.read_byte(0xFF0F)
                        ie_reg = self._mmu.read_byte(0xFFFF)
                        ly = self._ppu.get_ly() if self._ppu is not None else 0
                        stat = self._mmu.read_byte(0xFF41)
                    else:
                        if_reg = 0
                        ie_reg = 0
                        ly = 0
                        stat = 0
                    
                    # Formato de salida similar al debug pero con más información
                    flags_str = ""
                    if regs.get_flag_z():
                        flags_str += "Z"
                    if regs.get_flag_n():
                        flags_str += "N"
                    if regs.get_flag_h():
                        flags_str += "H"
                    if regs.get_flag_c():
                        flags_str += "C"
                    if not flags_str:
                        flags_str = "-"
                    
                    print(
                        f"TRACE [{self._trace_counter:03}]: "
                        f"PC=0x{pc_before:04X} | OP=0x{opcode:02X} | "
                        f"A=0x{regs.get_a():02X} BC=0x{regs.get_bc():04X} DE=0x{regs.get_de():04X} HL=0x{regs.get_hl():04X} | "
                        f"SP=0x{regs.get_sp():04X} | F={flags_str} | "
                        f"IF=0x{if_reg:02X} IE=0x{ie_reg:02X} | LY={ly:3d} STAT=0x{stat:02X} | "
                        f"Cycles={cycles}"
                    )
                    
                    self._trace_counter += 1
                    
                    # Desactivar trace después de 1000 instrucciones
                    if self._trace_counter >= 1000:
                        self._trace_active = False
                        print(f"\n{'='*80}")
                        print(f"🔍 TRACE COMPLETADO: 1000 instrucciones capturadas")
                        print(f"{'='*80}\n")
                
                # CRÍTICO: Renderizar periódicamente para mostrar el heartbeat incluso si no hay V-Blank
                # Esto asegura que el visual heartbeat sea visible cuando el LCD está apagado
                # o cuando el juego no está generando V-Blanks
                if self._renderer is not None:
                    self._cycles_since_render += cycles * 4  # Convertir a T-Cycles
                    # Renderizar cada ~70,224 T-Cycles (1 frame) para mantener el heartbeat visible
                    if self._cycles_since_render >= 70_224:
                        self._renderer.render_frame()
                        self._cycles_since_render = 0
                
                # Detectar inicio de V-Blank para renderizar
                if self._ppu is not None and self._renderer is not None:
                    ly = self._ppu.get_ly()
                    in_vblank = ly >= 144
                    
                    # Si acabamos de entrar en V-Blank, renderizar el frame
                    if in_vblank and not self._prev_vblank:
                        frame_count += 1
                        
                        # Heartbeat: cada 60 frames (≈1 segundo), mostrar estado
                        # También mostrar en el primer frame para diagnóstico inmediato
                        if frame_count % 60 == 0 or frame_count == 1:
                            pc = self._cpu.registers.get_pc()
                            fps = self._clock.get_fps() if self._clock is not None else 0.0
                            # Monitor de LCDC y BGP para diagnóstico
                            if self._mmu is not None:
                                lcdc = self._mmu.read_byte(0xFF40)
                                bgp = self._mmu.read_byte(0xFF47)
                                logger.info(
                                    f"💓 Heartbeat (frame {frame_count}): PC=0x{pc:04X} | FPS={fps:.2f} | "
                                    f"LCDC=0x{lcdc:02X} | BGP=0x{bgp:02X}"
                                )
                            else:
                                logger.info(f"💓 Heartbeat (frame {frame_count}): PC=0x{pc:04X} | FPS={fps:.2f}")
                        
                        # Log del estado de LCDC, IE, IF para debugging (DEBUG para evitar spam)
                        # CRÍTICO: Cambiado a DEBUG para evitar spam en consola que mata el rendimiento
                        if self._mmu is not None:
                            lcdc = self._mmu.read_byte(0xFF40)
                            ie = self._mmu.read_byte(0xFFFF)
                            if_reg = self._mmu.read_byte(0xFF0F)
                            bgp = self._mmu.read_byte(0xFF47)
                            if lcdc != 0:
                                logger.debug(
                                    f"V-Blank: LY={ly}, LCDC=0x{lcdc:02X}, "
                                    f"BGP=0x{bgp:02X}, IE=0x{ie:02X}, IF=0x{if_reg:02X} - Renderizando"
                                )
                            else:
                                logger.debug(
                                    f"V-Blank: LY={ly}, LCDC=0x{lcdc:02X} (OFF), "
                                    f"BGP=0x{bgp:02X}, IE=0x{ie:02X}, IF=0x{if_reg:02X} - Pantalla blanca"
                                )
                        self._renderer.render_frame()
                        # pygame.display.flip() ya se llama dentro de render_frame()
                        
                        # Actualizar título de ventana con FPS
                        if self._clock is not None:
                            fps = self._clock.get_fps()
                            try:
                                import pygame
                                pygame.display.set_caption(f"Viboy Color - FPS: {fps:.1f}")
                            except ImportError:
                                pass
                    
                    self._prev_vblank = in_vblank
                    
                    # Control de FPS: limitar a 60 FPS (Game Boy original: ~59.73 FPS)
                    # tick() espera el tiempo necesario para mantener 60 FPS
                    if self._clock is not None:
                        self._clock.tick(60)
                
                # Imprimir traza en modo debug (solo si el trace no está activo para evitar duplicación)
                if debug and not self._trace_active:
                    regs = self._cpu.registers
                    print(
                        f"PC: 0x{pc_before:04X} | "
                        f"Op: 0x{opcode:02X} | "
                        f"A: 0x{regs.get_a():02X} | "
                        f"B: 0x{regs.get_b():02X} | "
                        f"C: 0x{regs.get_c():02X} | "
                        f"D: 0x{regs.get_d():02X} | "
                        f"E: 0x{regs.get_e():02X} | "
                        f"H: 0x{regs.get_h():02X} | "
                        f"L: 0x{regs.get_l():02X} | "
                        f"SP: 0x{regs.get_sp():04X} | "
                        f"Cycles: {cycles}"
                    )
        
        except KeyboardInterrupt:
            # Salir limpiamente con Ctrl+C
            logger.info("Ejecución interrumpida por el usuario (Ctrl+C)")
            print(f"\n✅ Ejecución detenida. Total de ciclos: {self._total_cycles}")
        
        except NotImplementedError as e:
            # Opcode no implementado
            logger.error(f"Opcode no implementado: {e}")
            print(f"\n❌ Error: {e}")
            print(f"   Total de ciclos ejecutados: {self._total_cycles}")
            raise
        
        except Exception as e:
            # Otro error inesperado
            logger.error(f"Error inesperado: {e}", exc_info=True)
            print(f"\n❌ Error inesperado: {e}")
            print(f"   Total de ciclos ejecutados: {self._total_cycles}")
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
            key_mapping: dict[int, str] = {
                pygame.K_UP: "up",
                pygame.K_DOWN: "down",
                pygame.K_LEFT: "left",
                pygame.K_RIGHT: "right",
                pygame.K_z: "a",
                pygame.K_x: "b",
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

