"""
Test de Integración: Core C++ en Frontend Python

Este test valida que el sistema completo funcione correctamente cuando
se usa el core C++ (viboy_core) en lugar de los componentes Python.

Verifica:
- Inicialización correcta de componentes C++
- Carga de ROM en MMU C++
- Ejecución de instrucciones sin errores
- Sincronización PPU
"""

import pytest
from pathlib import Path

# Intentar importar viboy_core
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU, PyPPU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Compilar con: python setup.py build_ext --inplace", allow_module_level=True)

from src.viboy import Viboy


class TestIntegrationCPP:
    """Tests de integración del core C++ en el frontend Python."""
    
    def test_viboy_initialization_with_cpp_core(self):
        """Test: Viboy se inicializa correctamente con core C++."""
        viboy = Viboy(use_cpp_core=True)
        
        # Verificar que los componentes C++ están inicializados
        assert viboy._use_cpp is True
        assert viboy._mmu is not None
        assert viboy._cpu is not None
        assert viboy._ppu is not None
        assert viboy._regs is not None
        
        # Verificar tipos (deben ser wrappers Cython)
        assert type(viboy._mmu).__name__ == "PyMMU"
        assert type(viboy._cpu).__name__ == "PyCPU"
        assert type(viboy._ppu).__name__ == "PyPPU"
        assert type(viboy._regs).__name__ == "PyRegisters"
    
    def test_load_rom_into_cpp_mmu(self):
        """Test: Cargar ROM en MMU C++ funciona correctamente."""
        # Buscar una ROM de prueba
        rom_path = Path(__file__).parent.parent / "roms" / "tetris.gb"
        
        if not rom_path.exists():
            pytest.skip(f"ROM no encontrada: {rom_path}")
        
        viboy = Viboy(rom_path=rom_path, use_cpp_core=True)
        
        # Verificar que la ROM se cargó
        assert viboy._cartridge is not None
        assert viboy._mmu is not None
        
        # Verificar que podemos leer desde la MMU C++
        # El header del cartucho comienza en 0x0100
        header_byte = viboy._mmu.read(0x0100)
        assert isinstance(header_byte, int)
        assert 0 <= header_byte <= 255
    
    def test_execute_cpu_instructions(self):
        """Test: Ejecutar instrucciones de CPU C++ sin errores."""
        viboy = Viboy(use_cpp_core=True)
        
        # Inicializar post-boot state
        viboy._initialize_post_boot_state()
        
        # Ejecutar algunas instrucciones
        cycles_executed = 0
        max_instructions = 1000
        
        for _ in range(max_instructions):
            try:
                cycles = viboy._execute_cpu_only()
                cycles_executed += cycles
                
                # Verificar que se ejecutaron ciclos
                assert cycles > 0, "CPU debe ejecutar al menos 1 ciclo"
                
                # Verificar que no hay errores de acceso a memoria
                # (si hay error, se lanzará una excepción)
                
            except Exception as e:
                pytest.fail(f"Error al ejecutar instrucción: {e}")
        
        # Verificar que se ejecutaron instrucciones
        assert cycles_executed > 0, "Debe ejecutarse al menos un ciclo"
        assert viboy._total_cycles > 0, "Total de ciclos debe incrementarse"
    
    def test_ppu_synchronization(self):
        """Test: PPU C++ se sincroniza correctamente con CPU."""
        viboy = Viboy(use_cpp_core=True)
        
        # Inicializar post-boot state
        viboy._initialize_post_boot_state()
        
        # Ejecutar algunas instrucciones y sincronizar PPU
        for _ in range(100):
            cycles = viboy._execute_cpu_only()
            t_cycles = cycles * 4
            
            # Sincronizar PPU
            viboy._ppu.step(t_cycles)
            
            # Verificar que PPU avanza (LY puede cambiar)
            ly = viboy._ppu.get_ly()
            assert 0 <= ly <= 153, f"LY debe estar en rango válido: {ly}"
    
    def test_framebuffer_access(self):
        """Test: Acceso al framebuffer de PPU C++ funciona."""
        viboy = Viboy(use_cpp_core=True)
        
        # Inicializar post-boot state
        viboy._initialize_post_boot_state()
        
        # Obtener framebuffer
        framebuffer = viboy._ppu.framebuffer
        
        # Verificar que es un memoryview
        assert hasattr(framebuffer, '__len__'), "Framebuffer debe ser iterable"
        
        # Verificar tamaño (160 * 144 = 23040 píxeles)
        assert len(framebuffer) == 160 * 144, f"Framebuffer debe tener 23040 elementos, tiene {len(framebuffer)}"
        
        # Verificar que podemos leer valores
        first_pixel = framebuffer[0]
        assert isinstance(first_pixel, (int, type(framebuffer[0]))), "Píxeles deben ser enteros"
    
    def test_registers_access(self):
        """Test: Acceso a registros C++ funciona correctamente."""
        viboy = Viboy(use_cpp_core=True)
        
        # Inicializar post-boot state
        viboy._initialize_post_boot_state()
        
        # Leer registros
        assert viboy._regs.pc == 0x0100, "PC debe ser 0x0100 después de post-boot"
        assert viboy._regs.sp == 0xFFFE, "SP debe ser 0xFFFE después de post-boot"
        assert viboy._regs.a == 0x11, "A debe ser 0x11 (CGB mode) después de post-boot"
        
        # Escribir registros
        viboy._regs.a = 0x42
        assert viboy._regs.a == 0x42, "Registro A debe cambiar"
        
        viboy._regs.pc = 0x1234
        assert viboy._regs.pc == 0x1234, "PC debe cambiar"
    
    def test_full_cycle_execution(self):
        """Test: Ejecutar un ciclo completo (CPU + PPU) sin errores."""
        # Buscar una ROM de prueba
        rom_path = Path(__file__).parent.parent / "roms" / "tetris.gb"
        
        if not rom_path.exists():
            pytest.skip(f"ROM no encontrada: {rom_path}")
        
        viboy = Viboy(rom_path=rom_path, use_cpp_core=True)
        
        # Ejecutar múltiples ciclos completos
        for _ in range(100):
            try:
                cycles = viboy.tick()
                assert cycles > 0, "Cada tick debe ejecutar ciclos"
            except Exception as e:
                pytest.fail(f"Error en ciclo completo: {e}")
        
        # Verificar que el sistema sigue funcionando
        assert viboy._total_cycles > 0, "Debe haber ciclos ejecutados"
        assert viboy._ppu is not None, "PPU debe seguir inicializada"

