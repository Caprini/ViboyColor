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

# Imports para el bucle principal (evitar imports dentro del bucle)
try:
    import pygame
except ImportError:
    pygame = None  # type: ignore

# Configurar logger antes de usarlo
logger = logging.getLogger(__name__)

# --- Step 0362: Corrección de Logs de Python ---
# Configurar logger explícitamente con salida a stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    force=True,  # Forzar reconfiguración si ya estaba configurado
    stream=sys.stdout  # Asegurar que va a stdout
)
# -------------------------------------------

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
from .system_clock import SystemClock

# Importar Renderer condicionalmente (requiere pygame)
try:
    from .gpu.renderer import Renderer
except ImportError:
    Renderer = None  # type: ignore

if TYPE_CHECKING:
    pass


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

    def __init__(
        self, 
        rom_path: str | Path | None = None, 
        use_cpp_core: bool = True,
        bootrom_bytes: bytes | None = None,
        bootrom_stub: bool = False
    ) -> None:
        """
        Inicializa el sistema Viboy.
        
        Si se proporciona una ruta a ROM, carga el cartucho automáticamente.
        Si no se proporciona, el sistema se inicializa sin cartucho (modo de prueba).
        
        Args:
            rom_path: Ruta opcional al archivo ROM (.gb o .gbc)
            use_cpp_core: Si es True, usa componentes C++ (más rápido). Si False o no disponible, usa Python.
            bootrom_bytes: Bytes opcionales de la Boot ROM (DMG: 256 bytes, CGB: 2304 bytes)
            bootrom_stub: Si es True, activa modo stub sin binario propietario
            
        Raises:
            FileNotFoundError: Si el archivo ROM no existe
            IOError: Si hay un error al leer el archivo ROM
        """
        # Determinar si usar core C++ o Python
        self._use_cpp = use_cpp_core and CPP_CORE_AVAILABLE
        
        # Step 0402: Guardar Boot ROM y modo stub para aplicar después de cargar ROM
        self._bootrom_bytes = bootrom_bytes
        self._bootrom_stub = bootrom_stub
        
        # Inicializar componentes
        self._cartridge: Cartridge | None = None
        self._mmu: MMU | PyMMU | None = None
        self._cpu: CPU | PyCPU | None = None
        self._ppu: PPU | PyPPU | None = None
        self._regs: Registers | PyRegisters | None = None
        self._renderer: Renderer | None = None
        self._joypad: Joypad | None = None
        self._timer: Timer | None = None
        self._system_clock: SystemClock | None = None
        
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
        
        # --- Step 0344: Variables de Timer de Debug ---
        # Inicializar variables de instancia para el timer de debug
        self._start_time: float | None = None
        self._first_event_time: float | None = None
        self._first_event_detected: bool = False
        # -------------------------------------------
        
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
                # Crear SystemClock para centralizar conversión M→T
                self._system_clock = SystemClock(self._cpu, self._ppu, None)
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
                # Crear SystemClock para centralizar conversión M→T
                self._system_clock = SystemClock(self._cpu, self._ppu, self._timer)
            
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

    def load_cartridge(self, rom_path: str | Path, load_test_tiles: bool = True) -> None:
        """
        Carga un cartucho (ROM) en el sistema.
        
        Args:
            rom_path: Ruta al archivo ROM (.gb o .gbc)
            load_test_tiles: Si es True, carga tiles de prueba manualmente en VRAM (hack temporal).
                           Por defecto es True (Step 0311 - activado temporalmente para desarrollo)
            
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
            # Crear SystemClock para centralizar conversión M→T
            self._system_clock = SystemClock(self._cpu, self._ppu, self._timer)
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
            # Crear SystemClock para centralizar conversión M→T
            self._system_clock = SystemClock(self._cpu, self._ppu, self._timer)
        
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
        
        # Step 0402: Aplicar Boot ROM si se proveyó, o modo stub si está activado
        if self._use_cpp and self._mmu is not None:
            if self._bootrom_bytes:
                # Cargar Boot ROM real (provista por el usuario)
                self._mmu.set_boot_rom(self._bootrom_bytes)
                logger.info(f"✅ Boot ROM cargada: {len(self._bootrom_bytes)} bytes")
                
                # Verificar si Boot ROM está habilitada
                if self._mmu.is_boot_rom_enabled():
                    # Boot ROM activa: PC debe iniciar en 0x0000
                    if self._regs is not None:
                        self._regs.pc = 0x0000
                        logger.info("🔧 PC ajustado a 0x0000 (Boot ROM habilitada)")
                else:
                    # Boot ROM no activa (deshabilitada por FF50): usar Post-Boot State
                    self._initialize_post_boot_state()
            elif self._bootrom_stub:
                # Modo stub: activar stub sin binario propietario
                self._mmu.enable_bootrom_stub(True, cgb_mode=False)  # Por defecto DMG
                logger.info("🔧 Modo Boot ROM stub activado")
                # Boot ROM stub deja boot_rom_enabled_=False, usar Post-Boot State
                self._initialize_post_boot_state()
            else:
                # Sin Boot ROM ni stub: usar Post-Boot State (skip-boot)
                self._initialize_post_boot_state()
        else:
            # Fallback para modo Python o sin MMU
            self._initialize_post_boot_state()
        
        # --- Step 0298/0311: Carga Manual de Tiles (Hack Temporal) ---
        # Step 0311: Activado por defecto (load_test_tiles=True) para desarrollo
        # Esto permite avanzar con gráficos visibles mientras se investiga por qué
        # los juegos no cargan tiles automáticamente.
        # Step 0313: Añadir log para verificar ejecución
        # --- Step 0356: DESACTIVACIÓN DE TILES DE PRUEBA ---
        # Desactivar load_test_tiles() para permitir que los juegos carguen sus propios tiles
        # sin interferencia de tiles de prueba
        # if load_test_tiles and self._use_cpp and self._mmu is not None:
        #     print("[VIBOY] Ejecutando load_test_tiles()...")
        #     self._mmu.load_test_tiles()
        #     print("[VIBOY] load_test_tiles() ejecutado")
        # else:
        #     print(f"[VIBOY] load_test_tiles() NO ejecutado: load_test_tiles={load_test_tiles}, use_cpp={self._use_cpp}, mmu={self._mmu is not None}")
        print("[VIBOY] load_test_tiles() DESACTIVADO (Step 0356) - Los juegos cargarán sus propios tiles")
        # --- Fin Step 0356 ---
        # --- Fin Step 0298/0311 ---
        
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
            # --- Step 0411: Aplicar estado Post-Boot según modo de hardware ---
            # Detectar modo de hardware desde MMU (que lo leyó del header ROM)
            hardware_mode_str = self._mmu.get_hardware_mode()
            is_cgb_mode = (hardware_mode_str == "CGB")
            
            # Aplicar estado post-boot coherente con el modo HW
            self._regs.apply_post_boot_state(is_cgb_mode)
            
            # Log de estado aplicado
            mode_str = "CGB" if is_cgb_mode else "DMG"
            logger.info(
                f"✅ Post-Boot State ({mode_str}): PC=0x{self._regs.pc:04X}, "
                f"SP=0x{self._regs.sp:04X}, "
                f"A=0x{self._regs.a:02X} ({mode_str} mode), "
                f"F=0x{self._regs.f:02X} (Z={self._regs.flag_z}, N={self._regs.flag_n}, H={self._regs.flag_h}, C={self._regs.flag_c}), "
                f"BC=0x{self._regs.bc:04X}, "
                f"DE=0x{self._regs.de:04X}, "
                f"HL=0x{self._regs.hl:04X}"
            )
            logger.info(f"🔧 Registros CPU alineados con Hardware Mode detectado desde header ROM (Step 0411)")
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
    
    @staticmethod
    def _m_to_t_cycles(m_cycles: int) -> int:
        """
        Convierte M-cycles a T-cycles.
        
        En Game Boy: 1 M-Cycle = 4 T-Cycles (Clock Ticks)
        Este método encapsula la conversión para mantener DRY.
        
        Step 0441: Encapsulación para eliminar literales '*4' del código.
        
        Args:
            m_cycles: Número de M-cycles (Machine Cycles)
            
        Returns:
            int: Número de T-cycles (Timing Cycles)
        """
        return m_cycles << 2  # Equivalente a m_cycles * 4, pero sin literal
    
    def _execute_cpu_timer_only(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU y actualiza el Timer, pero NO la PPU.
        
        Este método es para uso en la arquitectura basada en scanlines, donde:
        - CPU y Timer se ejecutan cada instrucción (para precisión del RNG)
        - PPU se actualiza una vez por scanline (456 ciclos) para rendimiento
        
        STEP 0440: SystemClock ya sincroniza Timer (si está configurado).
        Sin embargo, este método tiene lógica especial para NO avanzar PPU.
        
        Returns:
            Número de T-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
        """
        if self._cpu is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        # Ejecutar CPU directamente (sin SystemClock para evitar avanzar PPU)
        m_cycles = self._cpu.step()
        
        # STEP 0440 Fase C: Validación explícita en lugar de hack silencioso
        if m_cycles <= 0:
            raise RuntimeError(
                f"CPU.step() devolvió {m_cycles} M-cycles (esperado >0). "
                f"Bug en CPU o opcode no manejado."
            )
        
        # Convertir a T-cycles usando método encapsulado (Step 0441)
        t_cycles = self._m_to_t_cycles(m_cycles)
        
        # Actualizar Timer si está disponible
        if self._timer is not None:
            self._timer.tick(t_cycles)
        
        # Acumular ciclos totales
        self._total_cycles += m_cycles
        
        return t_cycles
    
    def tick(self) -> int:
        """
        Ejecuta una sola instrucción de la CPU.
        
        Este método es el "latido" del sistema. Cada llamada ejecuta una instrucción
        y devuelve los ciclos consumidos.
        
        STEP 0440: Delegado a SystemClock para centralizar conversión M→T.
        SystemClock.tick_instruction() maneja:
        - Ejecución de CPU.step()
        - Conversión M→T (único punto con factor 4)
        - Sincronización PPU/Timer
        - Protección contra m_cycles == 0
        
        Returns:
            Número de M-Cycles consumidos por la instrucción ejecutada
            
        Raises:
            RuntimeError: Si el sistema no está inicializado correctamente
            
        Fuente: Pan Docs - System Clock
        """
        if self._system_clock is None:
            raise RuntimeError("Sistema no inicializado. Llama a load_cartridge() primero.")
        
        # Delegar a SystemClock (único punto de conversión M→T)
        m_cycles = self._system_clock.tick_instruction()
        self._total_cycles += m_cycles
        return m_cycles

    def run(self, debug: bool = False, simulate_input: bool = False) -> None:
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
            simulate_input: Si es True, simula presionar botones automáticamente en tiempos específicos
            
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
        
        # --- Step 0346: Verificación de Redirección de Salida ---
        # Verificar que la redirección de salida funciona correctamente
        test_msg = "[Viboy-Output-Test] Verificando redirección de salida"
        logger.info(test_msg)
        print(test_msg)
        print(test_msg, file=sys.stderr)
        
        logger.info(f"[Viboy-Output-Test] stdout: {sys.stdout}, stderr: {sys.stderr}")
        print(f"[Viboy-Output-Test] stdout: {sys.stdout}, stderr: {sys.stderr}")
        # -------------------------------------------
        
        # --- Step 0344: Inicializar Timer de Debug al Iniciar el Emulador ---
        # Reiniciar timer cuando se inicia una nueva ejecución
        self._start_time = time.time()
        self._first_event_time = None
        self._first_event_detected = False
        logger.info(f"[Viboy-Timer] Emulador iniciado en t={self._start_time:.6f}s")
        # -------------------------------------------
        
        # --- Step 0298: Simulación de Entrada ---
        # --- Step 0381: Simulación Temprana de Input ---
        # Mapeo de nombres de botones a índices numéricos para PyJoypad C++
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
        
        # Lista de acciones de simulación: (frames, botón, acción: "press" o "release")
        # Step 0381: Acciones más tempranas para verificar progreso del juego
        simulated_actions: list[tuple[int, str, str]] = []
        if simulate_input:
            # Step 0412: Simulación de input más agresiva y con repeticiones
            simulated_actions = [
                # Primera secuencia: START + A (frames 60-150)
                (60, "start", "press"),     # 1.0s: Presionar START
                (90, "start", "release"),   # 1.5s: Soltar START
                (120, "a", "press"),        # 2.0s: Presionar A
                (150, "a", "release"),      # 2.5s: Soltar A
                # Segunda secuencia: START + A (frames 360-450, ~6s)
                (360, "start", "press"),    # 6.0s: Presionar START (repetir)
                (390, "start", "release"),  # 6.5s: Soltar START
                (420, "a", "press"),        # 7.0s: Presionar A (repetir)
                (450, "a", "release"),      # 7.5s: Soltar A
                # Tercera secuencia: START + A (frames 660-750, ~11s)
                (660, "start", "press"),    # 11.0s: Presionar START (repetir)
                (690, "start", "release"),  # 11.5s: Soltar START
                (720, "a", "press"),        # 12.0s: Presionar A (repetir)
                (750, "a", "release"),      # 12.5s: Soltar A
                # Cuarta secuencia: START + A (frames 960-1050, ~16s)
                (960, "start", "press"),    # 16.0s: Presionar START (repetir)
                (990, "start", "release"),  # 16.5s: Soltar START
                (1020, "a", "press"),       # 17.0s: Presionar A (repetir)
                (1050, "a", "release"),     # 17.5s: Soltar A
            ]
            print("🎮 [Step 0412] Modo de simulación de entrada activado (agresivo + repeticiones)")
            print("   Secuencias programadas:")
            print("   - Secuencia 1 (1.0s-2.5s): START + A")
            print("   - Secuencia 2 (6.0s-7.5s): START + A")
            print("   - Secuencia 3 (11.0s-12.5s): START + A")
            print("   - Secuencia 4 (16.0s-17.5s): START + A")
        # --- Fin Step 0381 / Step 0298 ---
        
        print("🚀 Ejecutando el núcleo C++ con bucle de emulación nativo...")
        
        # --- Step 0317: Optimización - Verificar paleta solo una vez al inicio ---
        # Si BGP es 0x00, el juego no ha configurado la paleta y la pantalla será blanca.
        # Forzamos 0xE4 (paleta estándar) para que al menos veamos algo.
        # OPTIMIZACIÓN: Verificar solo una vez al inicio, no en cada frame
        palette_checked = False
        if self._use_cpp and self._mmu is not None:
            if self._mmu.read(0xFF47) == 0:
                self._mmu.write(0xFF47, 0xE4)
                palette_checked = True
        # ------------------------------------------------------------------------------------
        
        # --- Step 0393: Toggle de trazas via variable de entorno ---
        # VBC_TRACE=1 activa trazas, por defecto desactivadas para rendimiento
        import os
        ENABLE_DEBUG_LOGS = os.getenv('VBC_TRACE', '0') == '1'
        # ------------------------------------------------------------------------------------
        
        try:
            # Bucle principal del emulador
            while self.running:
                # --- Step 0361: Investigación de Rendimiento ---
                # Identificar qué causa el FPS muy bajo
                frame_start_time = time.time()
                # -------------------------------------------
                
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
                        
                        # --- Step 0333: SNAPSHOT INMUTABLE (CORREGIDO) ---
                        # CORRECCIÓN CRÍTICA: get_frame_ready_and_reset() ahora NO limpia el framebuffer
                        # El framebuffer se limpia al inicio del siguiente frame (cuando LY se resetea a 0)
                        # Esto asegura que Python siempre lee el framebuffer ANTES de que se limpie
                        if self._ppu is not None:
                            if self._ppu.get_frame_ready_and_reset():
                                # --- Step 0348: Verificación de Sincronización de Frames ---
                                # Verificar que la sincronización de frames es correcta
                                if not hasattr(self, '_frame_sync_check_count'):
                                    self._frame_sync_check_count = 0
                                
                                self._frame_sync_check_count += 1
                                
                                # Loggear cuándo se detecta frame listo
                                frame_ready_time = time.time()
                                
                                if self._frame_sync_check_count <= 20:
                                    logger.info(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                               f"Frame ready detectado en t={frame_ready_time:.6f}s")
                                    print(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                          f"Frame ready detectado en t={frame_ready_time:.6f}s")
                                # -------------------------------------------
                                
                                # --- Step 0348: Verificación de Timing Entre Generación y Visualización ---
                                # Verificar el timing entre cuando se genera el framebuffer y cuando se muestra
                                if not hasattr(self, '_timing_check_count'):
                                    self._timing_check_count = 0
                                    self._last_frame_ready_time = None
                                    self._frames_generated = 0
                                    self._frames_displayed = 0
                                
                                self._frames_generated += 1
                                current_time = time.time()
                                
                                if self._last_frame_ready_time is not None:
                                    time_between_frames = (current_time - self._last_frame_ready_time) * 1000  # ms
                                    expected_time = 1000.0 / 60.0  # ~16.67ms para 60 FPS
                                    
                                    if self._timing_check_count < 20:
                                        self._timing_check_count += 1
                                        logger.info(f"[Viboy-Timing] Frame {self._timing_check_count} | "
                                                   f"Time between frames: {time_between_frames:.3f}ms "
                                                   f"(expected: {expected_time:.3f}ms)")
                                        print(f"[Viboy-Timing] Frame {self._timing_check_count} | "
                                              f"Time between frames: {time_between_frames:.3f}ms "
                                              f"(expected: {expected_time:.3f}ms)")
                                        
                                        if abs(time_between_frames - expected_time) > 5.0:
                                            logger.warning(f"[Viboy-Timing] ⚠️ Timing anormal!")
                                            print(f"[Viboy-Timing] ⚠️ Timing anormal!")
                                
                                self._last_frame_ready_time = current_time
                                # -------------------------------------------
                                
                                # --- Step 0344: Detectar Primer Evento (Frame Listo) ---
                                # Detectar primer evento si aún no se ha detectado
                                if not self._first_event_detected:
                                    self._first_event_time = time.time()
                                    self._first_event_detected = True
                                    elapsed_time = self._first_event_time - self._start_time
                                    logger.info(f"[Viboy-Timer] Primer evento detectado en t={elapsed_time:.6f}s "
                                               f"(desde inicio: {self._start_time:.6f}s, evento: {self._first_event_time:.6f}s)")
                                # -------------------------------------------
                                
                                # --- Step 0340: Verificación de Timing de Lectura del Framebuffer ---
                                if not hasattr(self, '_framebuffer_timing_count'):
                                    self._framebuffer_timing_count = 0
                                if self._framebuffer_timing_count < 10:
                                    self._framebuffer_timing_count += 1
                                    logger.info(f"[Viboy-Framebuffer-Timing] Frame {self._framebuffer_timing_count} | "
                                               f"Frame ready detectado, leyendo framebuffer...")
                                
                                # --- Step 0340: Verificación de Timing Cuando Se Lee el Framebuffer ---
                                read_start_time = time.time()
                                
                                if not hasattr(self, '_framebuffer_read_timing_count'):
                                    self._framebuffer_read_timing_count = 0
                                
                                if self._framebuffer_read_timing_count < 10:
                                    self._framebuffer_read_timing_count += 1
                                    logger.info(f"[Viboy-Framebuffer-Read-Timing] Frame {self._framebuffer_read_timing_count} | "
                                               f"Leyendo framebuffer en t={read_start_time:.6f}s")
                                
                                # --- Step 0372: Tarea 6 - Verificar Estado del Framebuffer en Python ---
                                # Obtener el framebuffer usando la propiedad (memoryview)
                                raw_view = self._ppu.framebuffer
                                if raw_view is not None:
                                    # Verificar contenido antes de copiar
                                    if not hasattr(self, '_framebuffer_read_verify_count'):
                                        self._framebuffer_read_verify_count = 0
                                    
                                    self._framebuffer_read_verify_count += 1
                                    
                                    if self._framebuffer_read_verify_count <= 50:
                                        # Verificar primeros 100 píxeles
                                        non_zero_count = 0
                                        index_counts = [0, 0, 0, 0]
                                        
                                        for i in range(min(100, len(raw_view))):
                                            color_idx = raw_view[i] & 0x03
                                            index_counts[color_idx] += 1
                                            if color_idx != 0:
                                                non_zero_count += 1
                                        
                                        logger.info(f"[Viboy-Framebuffer-Read] Frame {self._framebuffer_read_verify_count} | "
                                                   f"Non-zero pixels (first 100): {non_zero_count}/100 | "
                                                   f"Distribution: 0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                                        print(f"[Viboy-Framebuffer-Read] Frame {self._framebuffer_read_verify_count} | "
                                              f"Non-zero pixels (first 100): {non_zero_count}/100 | "
                                              f"Distribution: 0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                                        
                                        if non_zero_count == 0:
                                            logger.warning("[Viboy-Framebuffer-Read] ⚠️ PROBLEMA: Framebuffer completamente vacío cuando Python lo lee!")
                                            print("[Viboy-Framebuffer-Read] ⚠️ PROBLEMA: Framebuffer completamente vacío cuando Python lo lee!")
                                    
                                    # --- Step 0395: Verificar pipeline framebuffer → Python ---
                                    if not hasattr(self, '_python_fb_verify_count'):
                                        self._python_fb_verify_count = 0
                                    
                                    current_frame = self._framebuffer_read_verify_count
                                    should_verify = (current_frame == 676 or current_frame == 742)
                                    
                                    if should_verify and self._python_fb_verify_count < 2:
                                        self._python_fb_verify_count += 1
                                        
                                        # Obtener snapshot completo del framebuffer
                                        snapshot = self._ppu.get_framebuffer_snapshot()
                                        if snapshot is not None:
                                            # Calcular distribución de valores
                                            import numpy as np
                                            counts = [0, 0, 0, 0]
                                            for y in range(144):
                                                for x in range(160):
                                                    value = snapshot[y, x] & 0x03
                                                    if value < 4:
                                                        counts[value] += 1
                                            
                                            total_pixels = 144 * 160
                                            logger.info(f"[PYTHON-FB-VERIFY] Frame {current_frame} | "
                                                       f"Distribution: 0={counts[0]} 1={counts[1]} 2={counts[2]} 3={counts[3]} | "
                                                       f"Total: {total_pixels}")
                                            print(f"[PYTHON-FB-VERIFY] Frame {current_frame} | "
                                                  f"Distribution: 0={counts[0]} 1={counts[1]} 2={counts[2]} 3={counts[3]} | "
                                                  f"Total: {total_pixels}")
                                # -------------------------------------------
                                
                                # --- Step 0332: Verificación Detallada de Copia del Framebuffer ---
                                # --- Step 0365: Verificación de Lectura del Framebuffer en Python ---
                                # 1. Obtener la vista directa de C++
                                raw_view = self._ppu.framebuffer
                                
                                # 2. Verificar que el framebuffer tiene datos antes de copiar
                                if raw_view is not None:
                                    # Verificar contenido ANTES de copiar
                                    first_20_before = [raw_view[i] & 0x03 for i in range(min(20, len(raw_view)))]
                                    non_zero_before = sum(1 for i in range(min(100, len(raw_view))) if (raw_view[i] & 0x03) != 0)
                                    
                                    if not hasattr(self, '_python_read_check_count'):
                                        self._python_read_check_count = 0
                                    if self._python_read_check_count < 20:
                                        self._python_read_check_count += 1
                                        log_msg = f"[Python-Read-Framebuffer] Frame {self._python_read_check_count} | " \
                                                 f"First 20 indices: {first_20_before} | " \
                                                 f"Non-zero in first 100: {non_zero_before}/100"
                                        print(log_msg, flush=True)
                                        logger.info(log_msg)
                                        
                                        if non_zero_before == 0:
                                            log_msg = f"[Python-Read-Framebuffer] ⚠️ PROBLEMA: Framebuffer está completamente vacío cuando Python lo lee!"
                                            print(log_msg, flush=True)
                                            logger.warning(log_msg)
                                    
                                    # 3. --- STEP 0219: SNAPSHOT INMUTABLE ---
                                    # Hacemos una copia profunda inmediata a la memoria de Python.
                                    # Esto "congela" el frame y nos protege de cualquier cambio en C++.
                                    fb_data = bytearray(raw_view)
                                    # ----------------------------------------
                                    
                                    # Verificar contenido DESPUÉS de copiar
                                    first_20_after = [fb_data[i] & 0x03 for i in range(min(20, len(fb_data)))]
                                    non_zero_after = sum(1 for i in range(min(100, len(fb_data))) if (fb_data[i] & 0x03) != 0)
                                    
                                    if self._python_read_check_count <= 20:
                                        if first_20_before != first_20_after:
                                            log_msg = f"[Python-Read-Framebuffer] ⚠️ PROBLEMA: La copia cambió los datos! " \
                                                     f"Before: {first_20_before} | After: {first_20_after}"
                                            print(log_msg, flush=True)
                                            logger.warning(log_msg)
                                        else:
                                            log_msg = f"[Python-Read-Framebuffer] ✅ Copia correcta: {non_zero_after} non-zero pixels"
                                            print(log_msg, flush=True)
                                            logger.info(log_msg)
                                    
                                    # --- Step 0348: Loggear cuándo se completa la lectura del framebuffer ---
                                    read_end_time = time.time()
                                    read_duration = (read_end_time - read_start_time) * 1000  # ms
                                    
                                    if self._frame_sync_check_count <= 20:
                                        logger.info(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                                   f"Framebuffer leído en {read_duration:.3f}ms "
                                                   f"(t={read_end_time:.6f}s)")
                                        print(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                              f"Framebuffer leído en {read_duration:.3f}ms "
                                              f"(t={read_end_time:.6f}s)")
                                    # -------------------------------------------
                                    
                                    # --- Step 0360: Confirmar Lectura del Framebuffer ---
                                    # Confirmar que Python leyó el framebuffer antes de que C++ lo limpie
                                    # Esto previene condiciones de carrera entre C++ y Python
                                    # -------------------------------------------
                                    
                                    # 4. Verificar primeros 20 píxeles después de copiar
                                    first_20_after = [fb_data[i] & 0x03 for i in range(min(20, len(fb_data)))]
                                    
                                    # Inicializar contador si no existe
                                    if not hasattr(self, '_framebuffer_copy_detailed_count'):
                                        self._framebuffer_copy_detailed_count = 0
                                    
                                    if self._framebuffer_copy_detailed_count <= 5:
                                        self._framebuffer_copy_detailed_count += 1
                                        logger.info(f"[Viboy-Framebuffer-Copy-Detailed] First 20 indices after copy: {first_20_after}")
                                    
                                    # --- Step 0359: Verificación Framebuffer C++ → Python ---
                                    # Verificar que el framebuffer se copia correctamente de C++ a Python
                                    if len(raw_view) != 23040:
                                        logger.warning(f"[Viboy-Framebuffer-Copy] ⚠️ Tamaño incorrecto: {len(raw_view)} != 23040")
                                    
                                    # Contar índices no-blancos
                                    non_white_count = sum(1 for idx in raw_view[:1000] if idx != 0)
                                    
                                    if non_white_count > 50:
                                        # Hay tiles reales
                                        if not hasattr(self, '_framebuffer_copy_verify_count'):
                                            self._framebuffer_copy_verify_count = 0
                                        if self._framebuffer_copy_verify_count < 10:
                                            self._framebuffer_copy_verify_count += 1
                                            logger.info(f"[Viboy-Framebuffer-Copy] Framebuffer con tiles | "
                                                       f"Non-white pixels (first 1000): {non_white_count}/1000")
                                            
                                            # Verificar primeros 20 índices
                                            first_20 = list(raw_view[:20])
                                            logger.info(f"[Viboy-Framebuffer-Copy] First 20 indices: {first_20}")
                                            
                                            # Verificar que la copia es idéntica
                                            if len(fb_data) == len(raw_view):
                                                matches = sum(1 for i in range(min(100, len(fb_data))) if fb_data[i] == raw_view[i])
                                                logger.info(f"[Viboy-Framebuffer-Copy] Copy verification: {matches}/100 matches")
                                    # -------------------------------------------
                                    
                                    # 5. Verificar que la copia es idéntica
                                    if first_20_before != first_20_after:
                                        logger.warning(f"[Viboy-Framebuffer-Copy-Detailed] ⚠️ DISCREPANCIA: "
                                                      f"Before={first_20_before}, After={first_20_after}")
                                    
                                    # 6. Contar índices en la copia
                                    index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                                    for idx in range(len(fb_data)):
                                        color_idx = fb_data[idx] & 0x03
                                        if color_idx in index_counts:
                                            index_counts[color_idx] += 1
                                    
                                    # Inicializar contador si no existe (ya debería estar inicializado arriba, pero por seguridad)
                                    if not hasattr(self, '_framebuffer_copy_detailed_count'):
                                        self._framebuffer_copy_detailed_count = 0
                                    
                                    if self._framebuffer_copy_detailed_count <= 5:
                                        logger.info(f"[Viboy-Framebuffer-Copy-Detailed] Index counts in copy: "
                                                   f"0={index_counts[0]} 1={index_counts[1]} "
                                                   f"2={index_counts[2]} 3={index_counts[3]}")
                                    
                                    # 7. Guardar la COPIA SEGURA para el renderizador
                                    framebuffer_to_render = fb_data
                                    
                                    # --- Step 0363: Diagnóstico de Rendimiento en Python ---
                                    # Medir tiempo de lectura del framebuffer y reportar cada 60 frames
                                    if not hasattr(self, '_framebuffer_read_timing_count'):
                                        self._framebuffer_read_timing_count = 0
                                    self._framebuffer_read_timing_count += 1
                                    
                                    if self._framebuffer_read_timing_count % 60 == 0:
                                        logger.info(f"[Viboy-Perf] Frame {self._framebuffer_read_timing_count} | "
                                                   f"Read: {read_duration:.2f}ms")
                                        print(f"[Viboy-Perf] Frame {self._framebuffer_read_timing_count} | "
                                              f"Read: {read_duration:.2f}ms", flush=True)
                                    
                                    # --- Step 0340: Finalizar Timing de Lectura del Framebuffer ---
                                    if self._framebuffer_read_timing_count <= 10:
                                        logger.info(f"[Viboy-Framebuffer-Read-Timing] Frame {self._framebuffer_read_timing_count} | "
                                                   f"Framebuffer leído en {read_duration:.3f}ms")
                                else:
                                    # --- Step 0348: Loggear si el framebuffer es None ---
                                    if self._frame_sync_check_count <= 20:
                                        logger.warning(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                                      f"⚠️ Framebuffer es None!")
                                        print(f"[Viboy-Frame-Sync] Frame {self._frame_sync_check_count} | "
                                              f"⚠️ Framebuffer es None!")
                                    # -------------------------------------------
                                    logger.error("[Viboy-Framebuffer-Copy-Detailed] ⚠️ Framebuffer es None!")
                                    framebuffer_to_render = None
                                # -------------------------------------------
                    # Step 0441: Eliminado bloque fallback Python legacy (nunca se ejecuta)
                    # Si _use_cpp es False, el sistema debería fallar tempranamente
                    # en lugar de usar código legacy no mantenido.
                
                # --- Fin del Frame ---
                # En este punto, se ha dibujado un frame completo (154 scanlines)
                
                # Renderizado en Python (solo si hay un frame listo)
                if self._renderer:
                    # --- Step 0445: Garantizar event pump cada frame ---
                    # Crítico para evitar "no responde" en el OS
                    if pygame is not None:
                        pygame.event.pump()
                    # -------------------------------------------
                    
                    should_continue = self._handle_pygame_events()
                    if not should_continue:
                        self.running = False
                        break
                    
                    # --- Step 0219: Pasar snapshot inmutable al renderizador ---
                    # Si tenemos un framebuffer capturado (snapshot), pasarlo al renderer
                    if framebuffer_to_render is not None:
                        # --- Step 0361: Verificación de Llamada a render_frame() ---
                        # Verificar que render_frame() se llama y recibe datos correctos
                        if not hasattr(self, '_render_call_count'):
                            self._render_call_count = 0
                        
                        self._render_call_count += 1
                        
                        # Verificar contenido antes de copiar
                        non_white_before = sum(1 for idx in framebuffer_to_render[:1000] if idx != 0)
                        
                        # --- Step 0362: Logs de Python con print() ---
                        # Usar tanto logger como print() para asegurar que aparece
                        if self._render_call_count <= 20:
                            log_msg = f"[Viboy-Render] Frame ready, reading framebuffer"
                            logger.info(log_msg)
                            print(log_msg, flush=True)  # flush=True para asegurar salida inmediata
                            
                            log_msg = f"[Viboy-Render] Call #{self._render_call_count} | " \
                                     f"Non-white pixels (first 1000): {non_white_before}/1000"
                            logger.info(log_msg)
                            print(log_msg, flush=True)
                            
                            # Mostrar primeros 20 índices
                            first_20 = list(framebuffer_to_render[:20])
                            log_msg = f"[Viboy-Render] First 20 indices: {first_20}"
                            logger.info(log_msg)
                            print(log_msg, flush=True)
                            
                            # Advertencia si está vacío
                            if non_white_before < 10:
                                log_msg = f"[Viboy-Render] ⚠️ ADVERTENCIA: " \
                                         f"Framebuffer está vacío cuando se va a renderizar!"
                                logger.warning(log_msg)
                                print(log_msg, flush=True)
                        # -------------------------------------------
                        
                        # --- Step 0406: Renderizado CGB RGB vs DMG índices ---
                        # --- Step 0445: Forzar path C++ RGB si está disponible ---
                        # Asegurar que SIEMPRE se usa rgb_view si PPU C++ está disponible
                        if self._ppu is not None and hasattr(self._ppu, 'get_framebuffer_rgb'):
                            rgb_view = self._ppu.get_framebuffer_rgb()
                            if rgb_view is not None:
                                self._renderer.render_frame(rgb_view=rgb_view)
                                # No fallback a legacy
                                # Confirmar lectura y continuar
                                self._ppu.confirm_framebuffer_read()
                                # Saltar al pacing (no ejecutar fallback)
                                # Continuar con el siguiente frame
                            else:
                                # RGB view no disponible, usar framebuffer_data si existe
                                if framebuffer_to_render is not None:
                                    self._renderer.render_frame(framebuffer_data=framebuffer_to_render)
                                    if self._ppu is not None:
                                        self._ppu.confirm_framebuffer_read()
                        else:
                            # Fallback: modo DMG con framebuffer_data
                            if framebuffer_to_render is not None:
                                self._renderer.render_frame(framebuffer_data=framebuffer_to_render)
                                if self._ppu is not None:
                                    self._ppu.confirm_framebuffer_read()
                        # -------------------------------------------
                        
                        # --- Step 0360: Confirmar Lectura del Framebuffer ---
                        # (Movido dentro del bloque anterior para evitar duplicación)
                        # -------------------------------------------
                    else:
                        # --- Step 0445: Legacy fallback deshabilitado en modo C++ ---
                        # Si use_cpp_ppu=True, no deberíamos llegar aquí
                        if self._use_cpp:
                            logger.error("[Viboy-Render] ⚠️ Legacy path deshabilitado en modo C++ | "
                                       "framebuffer_to_render es None pero PPU C++ está activo")
                            # Intentar obtener RGB view directamente
                            if self._ppu is not None and hasattr(self._ppu, 'get_framebuffer_rgb'):
                                rgb_view = self._ppu.get_framebuffer_rgb()
                                if rgb_view is not None:
                                    self._renderer.render_frame(rgb_view=rgb_view)
                                    self._ppu.confirm_framebuffer_read()
                                else:
                                    logger.warning("[Viboy-Render] RGB view también es None, no renderizando")
                            else:
                                logger.warning("[Viboy-Render] PPU C++ no disponible, no renderizando")
                        else:
                            # Fallback legacy solo si NO estamos en modo C++
                            self._renderer.render_frame()
                            if self._ppu is not None:
                                self._ppu.confirm_framebuffer_read()
                        # -------------------------------------------
                    
                    # --- Step 0309: Limitador de FPS y Reporte Correcto ---
                    # Sincronización con el reloj del host para mantener 60 FPS
                    tick_time_ms = None
                    if self._clock is not None:
                        tick_time_ms = self._clock.tick(TARGET_FPS)
                    
                    # --- Step 0317: Optimización - Actualizar título con FPS (cada 60 frames) ---
                    # Step 0309: Corregir cálculo de FPS para reflejar el FPS limitado
                    # --- Step 0324: Agregar nombre del juego en el título ---
                    if self.frame_count % 60 == 0 and self._clock is not None:
                        if pygame is not None:
                            # Opción A: Usar get_fps() que debería retornar FPS limitado
                            fps_from_clock = self._clock.get_fps()
                            
                            # Opción B: Calcular desde tick_time (más preciso)
                            if tick_time_ms is not None and tick_time_ms > 0:
                                fps_calculated = 1000.0 / tick_time_ms
                                # Usar el cálculo basado en tick_time para mayor precisión
                                fps = fps_calculated
                            else:
                                # Fallback a get_fps() si tick_time no está disponible
                                fps = fps_from_clock if fps_from_clock > 0 else TARGET_FPS
                            
                            # Obtener título del juego desde el cartucho
                            game_title = "ViboyColor"
                            if self._cartridge is not None:
                                try:
                                    header_info = self._cartridge.get_header_info()
                                    cart_title = header_info.get('title', '')
                                    if cart_title and cart_title != 'UNKNOWN' and cart_title.strip():
                                        game_title = f"ViboyColor - {cart_title}"
                                    else:
                                        game_title = "ViboyColor"
                                except Exception:
                                    game_title = "ViboyColor"
                            
                            # --- Step 0344: Agregar Timer de Debug al Título ---
                            # Calcular tiempo transcurrido
                            current_time = time.time()
                            elapsed_time = current_time - self._start_time
                            
                            # Construir string del timer
                            timer_str = f"Time: {elapsed_time:.3f}s"
                            if self._first_event_detected and self._first_event_time is not None:
                                first_event_elapsed = self._first_event_time - self._start_time
                                timer_str += f" | First Event: {first_event_elapsed:.3f}s"
                            
                            # Actualizar título con FPS y timer
                            pygame.display.set_caption(f"{game_title} - FPS: {fps:.1f} - {timer_str}")
                            # -------------------------------------------
                    
                    # --- Step 0317: Optimización - Logs de debug desactivados por defecto ---
                    # Los logs se ejecutan solo si ENABLE_DEBUG_LOGS es True
                    if ENABLE_DEBUG_LOGS:
                        # Log temporal para verificación (cada segundo)
                        if self.frame_count % 60 == 0:
                            print(f"[FPS-LIMITER] Frame {self.frame_count} | Tick time: {tick_time_ms:.2f}ms | Target: {TARGET_FPS} FPS")
                        
                        # Step 0309: Verificación de sincronización (cada minuto)
                        if not hasattr(self, '_start_time'):
                            self._start_time = time.time()
                        if self.frame_count % 3600 == 0 and self.frame_count > 0:  # Cada minuto (60 * 60 frames)
                            elapsed_real = time.time() - self._start_time
                            expected_frames = elapsed_real * TARGET_FPS
                            actual_frames = self.frame_count
                            drift = actual_frames - expected_frames
                            print(f"[SYNC-CHECK] Real: {elapsed_real:.1f}s | Expected: {expected_frames:.0f} frames | Actual: {actual_frames} | Drift: {drift:.0f}")
                        
                        # --- Step 0313: Logs de diagnóstico de FPS ---
                        if self.frame_count % 60 == 0 and self.frame_count > 0:
                            if not hasattr(self, '_start_time'):
                                self._start_time = time.time()
                            elapsed = time.time() - self._start_time
                            fps_actual = self.frame_count / elapsed if elapsed > 0 else 0
                            print(f"[FPS-DIAG] Frame {self.frame_count} | Elapsed: {elapsed:.2f}s | FPS actual: {fps_actual:.2f} | Tick time: {tick_time_ms:.2f}ms" if tick_time_ms is not None else f"[FPS-DIAG] Frame {self.frame_count} | Elapsed: {elapsed:.2f}s | FPS actual: {fps_actual:.2f}")
                    # ----------------------------------------
                
                
                # --- Step 0236: AUTOPSIA DESACTIVADA ---
                # La autopsia (Step 0235) se desactiva para limpiar la consola.
                # Solo queremos ver los logs del Francotirador (Step 0236) en 0x2B30.
                # if not hasattr(self, '_autopsy_done'):
                #     self._autopsy_done = False
                # 
                # if not self._autopsy_done and self.frame_count >= 600:
                #     # Preparar el contenido de la Autopsia
                #     autopsy_lines = []
                #     autopsy_lines.append("\n" + "=" * 40)
                #     autopsy_lines.append("💀 AUTOPSIA DEL SISTEMA (Frame 600 - 10 segundos)")
                #     autopsy_lines.append("=" * 40)
                #     
                #     if self._use_cpp:
                #         # 1. Estado de la CPU
                #         pc = self._regs.pc
                #         sp = self._regs.sp
                #         af = self._regs.af
                #         bc = self._regs.bc
                #         de = self._regs.de
                #         hl = self._regs.hl
                #         autopsy_lines.append(f"CPU State:")
                #         autopsy_lines.append(f"  PC: 0x{pc:04X} | SP: 0x{sp:04X}")
                #         autopsy_lines.append(f"  AF: 0x{af:04X} | BC: 0x{bc:04X} | DE: 0x{de:04X} | HL: 0x{hl:04X}")
                #         autopsy_lines.append(f"  Flags: Z={self._regs.flag_z}, N={self._regs.flag_n}, H={self._regs.flag_h}, C={self._regs.flag_c}")
                #         autopsy_lines.append(f"  Halted: {self._cpu.get_halted() if hasattr(self._cpu, 'get_halted') else 'N/A'}")
                #         
                #         # 2. Estado de Video (IO)
                #         lcdc = self._mmu.read(0xFF40)
                #         stat = self._mmu.read(0xFF41)
                #         ly = self._ppu.ly  # Propiedad directa
                #         bgp = self._mmu.read(0xFF47)
                #         autopsy_lines.append(f"\nVideo Registers:")
                #         autopsy_lines.append(f"  LCDC: 0x{lcdc:02X} (Bit 7={'ON' if lcdc & 0x80 else 'OFF'}, BG={'ON' if lcdc & 1 else 'OFF'}, Map={'0x9C00' if lcdc & 0x08 else '0x9800'})")
                #         autopsy_lines.append(f"  STAT: 0x{stat:02X} | LY: {ly} (Decimal)")
                #         autopsy_lines.append(f"  BGP:  0x{bgp:02X} (Palette)")
                #         
                #         # 3. Estado del Timer (CRÍTICO para Step 0235)
                #         div = self._mmu.read(0xFF04)  # DIV
                #         tima = self._mmu.read(0xFF05)  # TIMA
                #         tma = self._mmu.read(0xFF06)   # TMA
                #         tac = self._mmu.read(0xFF07)   # TAC
                #         autopsy_lines.append(f"\nTimer Registers:")
                #         autopsy_lines.append(f"  DIV:  0x{div:02X} | TIMA: 0x{tima:02X} | TMA: 0x{tma:02X} | TAC: 0x{tac:02X}")
                #         autopsy_lines.append(f"  Timer Enabled: {'YES' if (tac & 0x04) else 'NO'} (TAC bit 2)")
                #         freq_mode = tac & 0x03
                #         freq_str = ""
                #         if freq_mode == 0:
                #             freq_str = "4096 Hz (1024 T-Cycles)"
                #         elif freq_mode == 1:
                #             freq_str = "262144 Hz (16 T-Cycles)"
                #         elif freq_mode == 2:
                #             freq_str = "65536 Hz (64 T-Cycles)"
                #         elif freq_mode == 3:
                #             freq_str = "16384 Hz (256 T-Cycles)"
                #         autopsy_lines.append(f"  Timer Frequency: {freq_str}")
                #         
                #         # 4. Muestra de VRAM (Tile Data - El logo de Nintendo suele estar en 0x8010-0x802F)
                #         autopsy_lines.append(f"\nVRAM Tile Data (0x8010 - Primeros bytes del logo?):")
                #         data_sample = [f"{self._mmu.read(0x8010 + i):02X}" for i in range(16)]
                #         autopsy_lines.append(f"  {' '.join(data_sample)}")
                #         
                #         # 5. Muestra de VRAM (Tile Map - Leer según LCDC Bit 3)
                #         # Step 0234: Leer el mapa correcto según la configuración del juego
                #         bg_map_base = 0x9C00 if (lcdc & 0x08) else 0x9800
                #         autopsy_lines.append(f"\nVRAM Tile Map (Base 0x{bg_map_base:04X} - según LCDC Bit 3):")
                #         map_sample = [f"{self._mmu.read(bg_map_base + i):02X}" for i in range(16)]
                #         autopsy_lines.append(f"  {' '.join(map_sample)}")
                #         
                #         # 6. Estado de interrupciones
                #         ie = self._mmu.read(0xFFFF)  # Interrupt Enable
                #         if_register = self._mmu.read(0xFF0F)  # Interrupt Flag
                #         autopsy_lines.append(f"\nInterrupts:")
                #         autopsy_lines.append(f"  IE: 0x{ie:02X} | IF: 0x{if_register:02X}")
                #         autopsy_lines.append(f"  Timer IE: {'ENABLED' if (ie & 0x04) else 'DISABLED'} (Bit 2)")
                #         autopsy_lines.append(f"  Timer IF: {'PENDING' if (if_register & 0x04) else 'CLEAR'} (Bit 2)")
                #         
                #         # 7. Ciclos totales ejecutados
                #         autopsy_lines.append(f"\nSystem State:")
                #         autopsy_lines.append(f"  Total Cycles: {self._total_cycles:,}")
                #         autopsy_lines.append(f"  Frames: {self.frame_count}")
                #         
                #         # 8. Estado de ciclos de CPU (verificar que cycles_ se incrementa)
                #         cpu_cycles = self._cpu.get_cycles() if hasattr(self._cpu, 'get_cycles') else 0
                #         autopsy_lines.append(f"  CPU Cycles (cycles_): {cpu_cycles:,}")
                #     else:
                #         # Fallback para modo Python (si se usa)
                #         autopsy_lines.append("⚠️ Autopsia solo disponible en modo C++")
                #     
                #     autopsy_lines.append("=" * 40 + "\n")
                #     
                #     # Imprimir en consola
                #     autopsy_text = "\n".join(autopsy_lines)
                #     print(autopsy_text)
                #     
                #     # Escribir en archivo de log
                #     try:
                #         from datetime import datetime
                #         log_filename = f"autopsy_step_0235_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                #         with open(log_filename, 'w', encoding='utf-8') as f:
                #             f.write("=" * 70 + "\n")
                #             f.write("AUTOPSIA DEL SISTEMA - Step 0235\n")
                #             f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                #             f.write(f"Frame: {self.frame_count}\n")
                #             f.write("=" * 70 + "\n\n")
                #             f.write(autopsy_text)
                #         print(f"📝 Autopsia guardada en: {log_filename}")
                #     except Exception as e:
                #         logger.error(f"Error al escribir autopsia en archivo: {e}")
                #     
                #     self._autopsy_done = True
                # -----------------------------------------------
                
                self.frame_count += 1
                
                # --- Step 0361: Investigación de Rendimiento (Final del Frame) ---
                frame_end_time = time.time()
                frame_duration = (frame_end_time - frame_start_time) * 1000  # ms
                
                if not hasattr(self, '_performance_check_count'):
                    self._performance_check_count = 0
                
                self._performance_check_count += 1
                
                if self._performance_check_count <= 20:
                    logger.info(f"[Viboy-Performance] Frame {self.frame_count} | "
                               f"Duration: {frame_duration:.2f}ms | "
                               f"FPS: {1000.0 / frame_duration:.1f}")
                    
                    # Advertencia si el frame toma demasiado tiempo
                    if frame_duration > 100:  # Más de 100ms = menos de 10 FPS
                        logger.warning(f"[Viboy-Performance] ⚠️ ADVERTENCIA: "
                                      f"Frame toma {frame_duration:.2f}ms (muy lento!)")
                # -------------------------------------------
                
                # --- Step 0298: Ejecutar acciones de simulación de entrada ---
                if simulate_input and self._joypad is not None:
                    for frames, button, action in simulated_actions:
                        if self.frame_count == frames:
                            # Ejecutar la acción
                            if isinstance(self._joypad, PyJoypad):
                                button_index = button_index_map.get(button)
                                if button_index is not None:
                                    if action == "press":
                                        self._joypad.press_button(button_index)
                                        print(f"[SIM-INPUT] Frame {frames} ({frames/60.0:.1f}s): PRESS {button.upper()}")
                                    else:
                                        self._joypad.release_button(button_index)
                                        print(f"[SIM-INPUT] Frame {frames} ({frames/60.0:.1f}s): RELEASE {button.upper()}")
                            else:
                                # Fallback para Joypad Python
                                if action == "press":
                                    self._joypad.press(button)
                                    print(f"[SIM-INPUT] Frame {frames} ({frames/60.0:.1f}s): PRESS {button.upper()}")
                                else:
                                    self._joypad.release(button)
                                    print(f"[SIM-INPUT] Frame {frames} ({frames/60.0:.1f}s): RELEASE {button.upper()}")
                # --- Fin Step 0298 ---
                
                # --- Step 0358: Simulación de Interacción del Usuario ---
                # Simular presiones de botones para verificar si TETRIS y Mario requieren interacción
                if self._joypad is not None:
                    if self.frame_count == 3000:  # Después de ~50 segundos
                        # Simular presionar START
                        if isinstance(self._joypad, PyJoypad):
                            self._joypad.press_button(button_index_map.get("start", 7))
                        else:
                            self._joypad.press("start")
                        logger.info("[Viboy-User-Interaction] Simulando presión de START en Frame 3000")
                        print("[Viboy-User-Interaction] Simulando presión de START en Frame 3000")
                    
                    if self.frame_count == 3100:  # Un frame después
                        # Liberar START
                        if isinstance(self._joypad, PyJoypad):
                            self._joypad.release_button(button_index_map.get("start", 7))
                        else:
                            self._joypad.release("start")
                        logger.info("[Viboy-User-Interaction] Liberando START en Frame 3100")
                        print("[Viboy-User-Interaction] Liberando START en Frame 3100")
                # -------------------------------------------
                
                # --- Step 0240: Monitor GPS (Navegador) ---
                # Reporta la posición de la CPU y el estado del hardware cada segundo (60 frames)
                # Step 0317: Optimización - Desactivado por defecto para mejorar rendimiento
                if ENABLE_DEBUG_LOGS and self.frame_count % 60 == 0:
                    if self._use_cpp and self._regs is not None and self._cpu is not None and self._mmu is not None:
                        # Leer registros de la CPU
                        pc = self._regs.pc
                        sp = self._regs.sp
                        ime = self._cpu.get_ime()
                        
                        # Leer registros de interrupciones
                        ie = self._mmu.read(0xFFFF)  # Interrupt Enable
                        if_register = self._mmu.read(0xFF0F)  # Interrupt Flag
                        
                        # Leer registros de video
                        lcdc = self._mmu.read(0xFF40)  # LCD Control
                        ly = self._ppu.ly if self._ppu is not None else self._mmu.read(0xFF44)  # LY (scanline actual)
                        
                        # Formato: [GPS] PC:XXXX | SP:XXXX | IME:X | IE:XX IF:XX | LCDC:XX LY:XX
                        print(f"[GPS] PC:{pc:04X} | SP:{sp:04X} | IME:{ime} | IE:{ie:02X} IF:{if_register:02X} | LCDC:{lcdc:02X} LY:{ly:02X}")
                        
                        # --- Step 0255: OAM & PALETTE INSPECTOR ---
                        # Leer registros de Paleta
                        bgp = self._mmu.read(0xFF47)  # Background Palette
                        obp0 = self._mmu.read(0xFF48)  # Object Palette 0
                        obp1 = self._mmu.read(0xFF49)  # Object Palette 1
                        
                        # Leer primeros 2 sprites de OAM (4 bytes cada uno)
                        # Sprite 0: Y=FE00, X=FE01, Tile=FE02, Attr=FE03
                        s0_y = self._mmu.read(0xFE00)
                        s0_x = self._mmu.read(0xFE01)
                        s0_tile = self._mmu.read(0xFE02)
                        s0_attr = self._mmu.read(0xFE03)
                        
                        s1_y = self._mmu.read(0xFE04)
                        s1_x = self._mmu.read(0xFE05)
                        s1_tile = self._mmu.read(0xFE06)
                        s1_attr = self._mmu.read(0xFE07)
                        
                        # Log extendido de Video
                        logger.info(f"[VIDEO] BGP:{bgp:02X} OBP0:{obp0:02X} OBP1:{obp1:02X} | LCDC:{lcdc:02X}")
                        logger.info(f"[SPRITE 0] Y:{s0_y:02X} X:{s0_x:02X} T:{s0_tile:02X} A:{s0_attr:02X}")
                        logger.info(f"[SPRITE 1] Y:{s1_y:02X} X:{s1_x:02X} T:{s1_tile:02X} A:{s1_attr:02X}")
                        
                        # --- Step 0258: VRAM CHECKSUM ---
                        # Leer muestras masivas para ver si hay vida
                        # Nota: Esto es lento, pero solo ocurre 1 vez por segundo
                        vram_sum = 0
                        tile_sum = 0
                        map_sum = 0
                        # Muestreo rápido: leer cada 16 bytes para no matar el rendimiento
                        for addr in range(0x8000, 0xA000, 16):
                            val = self._mmu.read(addr)
                            vram_sum += val
                            if addr < 0x9800:
                                tile_sum += val
                            else:
                                map_sum += val
                        
                        logger.info(f"[MEMORY] VRAM_SUM: {vram_sum} (Si es 0, no hay gráficos)")
                        logger.info(f"[MEMORY] VRAM_TILE_SUM: {tile_sum} | VRAM_MAP_SUM: {map_sum}")
                        flag_d732 = self._mmu.read(0xD732)
                        logger.info(f"[WRAM] D732: {flag_d732:02X}")
                        # -------------------------------------------------
                    elif not self._use_cpp and self._cpu is not None and self._mmu is not None:
                        # Fallback para modo Python
                        pc = self._cpu.registers.get_pc()
                        sp = self._cpu.registers.get_sp()
                        ime = 1 if self._cpu.ime else 0
                        
                        ie = self._mmu.read(0xFFFF)
                        if_register = self._mmu.read(0xFF0F)
                        
                        lcdc = self._mmu.read(0xFF40)
                        ly = self._ppu.ly if self._ppu is not None else self._mmu.read(0xFF44)
                        
                        print(f"[GPS] PC:{pc:04X} | SP:{sp:04X} | IME:{ime} | IE:{ie:02X} IF:{if_register:02X} | LCDC:{lcdc:02X} LY:{ly:02X}")
                        
                        # --- Step 0255: OAM & PALETTE INSPECTOR (Python) ---
                        bgp = self._mmu.read(0xFF47)
                        obp0 = self._mmu.read(0xFF48)
                        obp1 = self._mmu.read(0xFF49)
                        
                        s0_y = self._mmu.read(0xFE00)
                        s0_x = self._mmu.read(0xFE01)
                        s0_tile = self._mmu.read(0xFE02)
                        s0_attr = self._mmu.read(0xFE03)
                        
                        s1_y = self._mmu.read(0xFE04)
                        s1_x = self._mmu.read(0xFE05)
                        s1_tile = self._mmu.read(0xFE06)
                        s1_attr = self._mmu.read(0xFE07)
                        
                        logger.info(f"[VIDEO] BGP:{bgp:02X} OBP0:{obp0:02X} OBP1:{obp1:02X} | LCDC:{lcdc:02X}")
                        logger.info(f"[SPRITE 0] Y:{s0_y:02X} X:{s0_x:02X} T:{s0_tile:02X} A:{s0_attr:02X}")
                        logger.info(f"[SPRITE 1] Y:{s1_y:02X} X:{s1_x:02X} T:{s1_tile:02X} A:{s1_attr:02X}")
                        
                        # --- Step 0258: VRAM CHECKSUM (Python) ---
                        # Leer muestras masivas para ver si hay vida
                        # Nota: Esto es lento, pero solo ocurre 1 vez por segundo
                        vram_sum = 0
                        tile_sum = 0
                        map_sum = 0
                        # Muestreo rápido: leer cada 16 bytes para no matar el rendimiento
                        for addr in range(0x8000, 0xA000, 16):
                            val = self._mmu.read(addr)
                            vram_sum += val
                            if addr < 0x9800:
                                tile_sum += val
                            else:
                                map_sum += val
                        
                        logger.info(f"[MEMORY] VRAM_SUM: {vram_sum} (Si es 0, no hay gráficos)")
                        logger.info(f"[MEMORY] VRAM_TILE_SUM: {tile_sum} | VRAM_MAP_SUM: {map_sum}")
                        flag_d732 = self._mmu.read(0xD732)
                        logger.info(f"[WRAM] D732: {flag_d732:02X}")
                        # -------------------------------------------------
                # -------------------------------------------------
        
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
            # --- Step 0410: Resumen de DMA/VRAM al finalizar ---
            if self._use_cpp and self._mmu is not None:
                try:
                    self._mmu.log_dma_vram_summary()
                except Exception as e:
                    logger.warning(f"[Step 0410] Error al generar resumen DMA/VRAM: {e}")
            # -------------------------------------------
            
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


