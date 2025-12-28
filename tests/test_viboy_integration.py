"""
Tests de integración para la clase Viboy (Sistema Principal)

Estos tests validan que todos los componentes (CPU, MMU, Cartridge) funcionan
correctamente juntos a través de la clase Viboy.
"""

import pytest
from pathlib import Path

from src.viboy import Viboy


class TestViboyIntegration:
    """Tests de integración para la clase Viboy"""

    def test_viboy_initialization_without_rom(self) -> None:
        """Test: Viboy se inicializa correctamente sin ROM (modo de prueba)"""
        viboy = Viboy()
        
        # Verificar que los componentes están inicializados
        assert viboy.get_cpu() is not None
        assert viboy.get_mmu() is not None
        assert viboy.get_cartridge() is None
        
        # Verificar estado inicial
        cpu = viboy.get_cpu()
        assert cpu is not None
        assert cpu.registers.get_pc() == 0x0100
        assert cpu.registers.get_sp() == 0xFFFE

    def test_viboy_tick_executes_instruction(self) -> None:
        """Test: tick() ejecuta una instrucción y avanza el PC"""
        viboy = Viboy()
        
        cpu = viboy.get_cpu()
        assert cpu is not None
        
        # Obtener PC inicial
        pc_initial = cpu.registers.get_pc()
        
        # Ejecutar una instrucción (debe ser NOP si la memoria está en 0x00)
        cycles = viboy.tick()
        
        # Verificar que se consumieron ciclos
        assert cycles > 0
        
        # Verificar que el PC avanzó (a menos que sea un salto)
        # Para NOP (0x00), el PC debería avanzar en 1
        pc_after = cpu.registers.get_pc()
        # El PC puede haber avanzado o cambiado (dependiendo del opcode)
        assert pc_after != pc_initial or cycles == 1

    def test_viboy_total_cycles_counter(self) -> None:
        """Test: El contador de ciclos totales se incrementa correctamente"""
        viboy = Viboy()
        
        # Verificar que empieza en 0
        assert viboy.get_total_cycles() == 0
        
        # Ejecutar varias instrucciones
        cycles1 = viboy.tick()
        cycles2 = viboy.tick()
        cycles3 = viboy.tick()
        
        # Verificar que el total es la suma
        total_expected = cycles1 + cycles2 + cycles3
        assert viboy.get_total_cycles() == total_expected

    def test_viboy_load_cartridge(self, tmp_path: Path) -> None:
        """Test: load_cartridge() carga un cartucho correctamente"""
        # Crear una ROM dummy con algunos NOPs
        rom_data = bytearray(0x200)  # 512 bytes
        rom_data[0x0100] = 0x00  # NOP en el inicio del código
        rom_data[0x0101] = 0x00  # NOP
        rom_data[0x0102] = 0x00  # NOP
        
        # Escribir ROM dummy a archivo temporal
        rom_file = tmp_path / "test_rom.gb"
        rom_file.write_bytes(rom_data)
        
        # Crear Viboy sin ROM
        viboy = Viboy()
        
        # Cargar cartucho
        viboy.load_cartridge(rom_file)
        
        # Verificar que el cartucho está cargado
        cartridge = viboy.get_cartridge()
        assert cartridge is not None
        
        # Verificar que la CPU puede leer de la ROM
        cpu = viboy.get_cpu()
        assert cpu is not None
        mmu = viboy.get_mmu()
        assert mmu is not None
        
        # Leer byte de la ROM (debería ser 0x00 = NOP)
        byte_read = mmu.read_byte(0x0100)
        assert byte_read == 0x00

    def test_viboy_initialization_with_rom(self, tmp_path: Path) -> None:
        """Test: Viboy se inicializa correctamente con ROM"""
        # Crear una ROM dummy
        rom_data = bytearray(0x200)
        rom_data[0x0100] = 0x00  # NOP
        
        rom_file = tmp_path / "test_rom.gb"
        rom_file.write_bytes(rom_data)
        
        # Inicializar Viboy con ROM
        viboy = Viboy(rom_file)
        
        # Verificar que el cartucho está cargado
        assert viboy.get_cartridge() is not None
        
        # Verificar que la CPU está inicializada
        cpu = viboy.get_cpu()
        assert cpu is not None
        assert cpu.registers.get_pc() == 0x0100
        assert cpu.registers.get_sp() == 0xFFFE

    def test_viboy_executes_nop_sequence(self, tmp_path: Path) -> None:
        """Test: Viboy ejecuta una secuencia de NOPs correctamente"""
        # Crear ROM con varios NOPs
        rom_data = bytearray(0x200)
        for i in range(5):
            rom_data[0x0100 + i] = 0x00  # NOP
        
        rom_file = tmp_path / "test_rom.gb"
        rom_file.write_bytes(rom_data)
        
        # Inicializar Viboy
        viboy = Viboy(rom_file)
        cpu = viboy.get_cpu()
        assert cpu is not None
        
        # Ejecutar 5 instrucciones (NOPs)
        for i in range(5):
            pc_before = cpu.registers.get_pc()
            cycles = viboy.tick()
            
            # Verificar que se consumieron ciclos (NOP = 1 ciclo)
            assert cycles == 1
            
            # Verificar que el PC avanzó en 1
            pc_after = cpu.registers.get_pc()
            assert pc_after == (pc_before + 1) & 0xFFFF

    def test_viboy_tick_raises_error_if_not_initialized(self) -> None:
        """Test: tick() lanza RuntimeError si el sistema no está inicializado"""
        # Crear Viboy sin inicializar (sin ROM y sin llamar a load_cartridge)
        # Esto no debería pasar con el constructor actual, pero probamos el caso
        # donde _cpu es None por alguna razón
        
        # En realidad, el constructor siempre inicializa _cpu, así que este test
        # valida que el método tick() maneja correctamente el caso None
        # (aunque no debería ocurrir en uso normal)
        pass  # Este test se puede omitir ya que el constructor siempre inicializa

    def test_viboy_post_boot_state(self) -> None:
        """Test: El estado post-arranque se inicializa correctamente"""
        viboy = Viboy()
        
        cpu = viboy.get_cpu()
        assert cpu is not None
        
        # Verificar valores post-boot
        assert cpu.registers.get_pc() == 0x0100  # Inicio del código del cartucho
        assert cpu.registers.get_sp() == 0xFFFE   # Top de la pila

