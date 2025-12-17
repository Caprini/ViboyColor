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
from pathlib import Path
from typing import TYPE_CHECKING

from .cpu.core import CPU
from .cpu.registers import Registers
from .gpu.ppu import PPU
from .memory.cartridge import Cartridge
from .memory.mmu import MMU

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
        
        # Contador de ciclos totales ejecutados
        self._total_cycles: int = 0
        
        # Si se proporciona ROM, cargarla
        if rom_path is not None:
            self.load_cartridge(rom_path)
        else:
            # Inicializar sin cartucho (modo de prueba)
            self._mmu = MMU(None)
            self._cpu = CPU(self._mmu)
            self._ppu = PPU(self._mmu)
            # Conectar PPU a MMU para que pueda leer LY
            self._mmu.set_ppu(self._ppu)
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
        
        # Inicializar CPU con la MMU
        self._cpu = CPU(self._mmu)
        
        # Inicializar PPU con la MMU
        self._ppu = PPU(self._mmu)
        
        # Conectar PPU a MMU para que pueda leer LY (evitar dependencia circular)
        self._mmu.set_ppu(self._ppu)
        
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
        
        Por ahora, inicializamos valores básicos. Más adelante, cuando implementemos
        la Boot ROM, estos valores se establecerán automáticamente.
        
        Fuente: Pan Docs - Boot ROM, Post-Boot State
        """
        if self._cpu is None:
            return
        
        # PC inicializado a 0x0100 (inicio del código del cartucho)
        self._cpu.registers.set_pc(0x0100)
        
        # SP inicializado a 0xFFFE (top de la pila)
        self._cpu.registers.set_sp(0xFFFE)
        
        logger.debug(
            f"Post-Boot State: PC=0x{self._cpu.registers.get_pc():04X}, "
            f"SP=0x{self._cpu.registers.get_sp():04X}"
        )

    def tick(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU.
        
        Este método es el "latido" del sistema. Cada llamada ejecuta una instrucción
        y devuelve los ciclos consumidos.
        
        Returns:
            Número de M-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            NotImplementedError: Si se encuentra un opcode no implementado
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        # Ejecutar una instrucción
        cycles = self._cpu.step()
        
        # Acumular ciclos totales
        self._total_cycles += cycles
        
        # Avanzar la PPU (motor de timing)
        # La CPU devuelve M-Cycles, pero la PPU necesita T-Cycles
        # Conversión: 1 M-Cycle = 4 T-Cycles
        if self._ppu is not None:
            t_cycles = cycles * 4
            self._ppu.step(t_cycles)
        
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
        
        try:
            while True:
                # Obtener estado antes de ejecutar (para debug)
                if debug:
                    pc_before = self._cpu.registers.get_pc()
                    opcode = self._mmu.read_byte(pc_before) if self._mmu else 0
                
                # Ejecutar una instrucción
                cycles = self.tick()
                
                # Imprimir traza en modo debug
                if debug:
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

