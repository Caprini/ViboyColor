"""
SystemClock: Centralización del contrato de ciclos M→T y sincronización CPU↔PPU↔Timer.

Este módulo implementa el patrón de diseño "Clock Domain" para garantizar que:
1. CPU devuelve M-cycles (Machine Cycles)
2. PPU y Timer consumen T-cycles (Clock Cycles)
3. La conversión M→T (factor 4) se hace en UN SOLO LUGAR
4. Es difícil/imposible pasar M-cycles a PPU por error

Basado en Pan Docs:
- CPU opera en M-cycles (1 M-cycle = 4 T-cycles)
- PPU opera en T-cycles (dot clock)
- Timer opera en T-cycles

Autor: Viboy Color Team
Licencia: MIT
"""

from typing import Optional


class SystemClock:
    """
    Reloj maestro del sistema que coordina CPU, PPU y Timer.
    
    Esta clase encapsula el bucle de emulación de grano fino y garantiza
    que la conversión de ciclos M→T se haga correctamente.
    
    Responsabilidades:
    - Ejecutar una instrucción de CPU (retorna M-cycles)
    - Convertir M-cycles a T-cycles (factor 4)
    - Avanzar PPU con T-cycles
    - Avanzar Timer con T-cycles
    - Acumular ciclos totales del sistema
    """
    
    # Constante de conversión M-cycles → T-cycles
    # En Game Boy: 1 M-cycle = 4 T-cycles (4.19 MHz / 1.05 MHz)
    M_TO_T_FACTOR = 4
    
    def __init__(self, cpu, ppu=None, timer=None):
        """
        Inicializa el reloj del sistema.
        
        Args:
            cpu: Instancia de CPU (PyCPU o CPU Python)
            ppu: Instancia de PPU (PyPPU o PPU Python), opcional
            timer: Instancia de Timer (PyTimer o Timer Python), opcional
        """
        self._cpu = cpu
        self._ppu = ppu
        self._timer = timer
        self._total_cycles = 0  # Acumulador de M-cycles totales
    
    def tick_instruction(self) -> int:
        """
        Ejecuta una instrucción completa de CPU y sincroniza todos los subsistemas.
        
        Este método implementa el contrato de ciclos:
        1. CPU.step() retorna M-cycles
        2. Convertir M → T (multiplicar por 4)
        3. PPU.step(T) consume T-cycles
        4. Timer.tick(T) consume T-cycles
        
        Returns:
            int: Número de M-cycles ejecutados por la CPU
            
        Raises:
            RuntimeError: Si la CPU no está inicializada
        """
        if self._cpu is None:
            raise RuntimeError("CPU no inicializada en SystemClock")
        
        # 1. Ejecutar una instrucción de CPU (retorna M-cycles)
        m_cycles = self._cpu.step()
        
        # 2. Protección contra bucle infinito (CPU retorna 0 ciclos)
        if m_cycles == 0:
            m_cycles = 1  # Forzar avance mínimo (4 T-cycles)
        
        # 3. Convertir M-cycles a T-cycles (ÚNICO PUNTO DE CONVERSIÓN)
        t_cycles = m_cycles * self.M_TO_T_FACTOR
        
        # 4. Avanzar PPU con T-cycles
        if self._ppu is not None:
            self._ppu.step(t_cycles)
        
        # 5. Avanzar Timer con T-cycles
        if self._timer is not None:
            self._timer.tick(t_cycles)
        
        # 6. Acumular ciclos totales (en M-cycles)
        self._total_cycles += m_cycles
        
        return m_cycles
    
    def tick_halt(self, max_cycles: int = 456) -> int:
        """
        Ejecuta múltiples ciclos durante HALT hasta que se genere una interrupción.
        
        Durante HALT, la CPU no ejecuta instrucciones pero el reloj sigue avanzando,
        permitiendo que PPU y Timer generen interrupciones.
        
        Args:
            max_cycles: Máximo de T-cycles a ejecutar (por defecto 1 scanline)
            
        Returns:
            int: Número de M-cycles ejecutados
        """
        m_cycles_executed = 0
        t_cycles_executed = 0
        
        # Ejecutar hasta max_cycles o hasta que la CPU se despierte
        while t_cycles_executed < max_cycles:
            # Ejecutar un tick de HALT (consume 1 M-cycle mínimo)
            m_cycles = self._cpu.step()
            
            if m_cycles == 0:
                m_cycles = 1  # Protección
            
            # Convertir a T-cycles
            t_cycles = m_cycles * self.M_TO_T_FACTOR
            
            # Avanzar subsistemas
            if self._ppu is not None:
                self._ppu.step(t_cycles)
            
            if self._timer is not None:
                self._timer.tick(t_cycles)
            
            # Acumular
            m_cycles_executed += m_cycles
            t_cycles_executed += t_cycles
            
            # Verificar si la CPU se despertó (depende de la implementación)
            # Para CPU C++: usar get_halted()
            # Para CPU Python: usar atributo halted
            try:
                if hasattr(self._cpu, 'get_halted'):
                    if not self._cpu.get_halted():
                        break
                elif hasattr(self._cpu, 'halted'):
                    if not self._cpu.halted:
                        break
            except:
                # Si no podemos verificar HALT, salir después de un ciclo
                break
        
        self._total_cycles += m_cycles_executed
        return m_cycles_executed
    
    def get_total_cycles(self) -> int:
        """
        Retorna el total de M-cycles ejecutados desde el inicio.
        
        Returns:
            int: Total de M-cycles acumulados
        """
        return self._total_cycles
    
    def reset_total_cycles(self) -> None:
        """
        Reinicia el contador de ciclos totales.
        """
        self._total_cycles = 0
    
    def set_ppu(self, ppu) -> None:
        """
        Conecta una instancia de PPU al reloj del sistema.
        
        Args:
            ppu: Instancia de PPU (PyPPU o PPU Python)
        """
        self._ppu = ppu
    
    def set_timer(self, timer) -> None:
        """
        Conecta una instancia de Timer al reloj del sistema.
        
        Args:
            timer: Instancia de Timer (PyTimer o Timer Python)
        """
        self._timer = timer

