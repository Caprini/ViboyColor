"""
Test de seguridad: ROM es read-only por defecto (Step 0422)

Este test valida que el comportamiento por defecto del MMU es correcto:
- ROM (0x0000-0x7FFF) NO debe ser escribible sin test_mode
- Esto protege la integridad de la emulación (MBC debe manejar writes)

Si este test falla, significa que alguien rompió el comportamiento real del MMU.
"""

import pytest

try:
    from viboy_core import PyMMU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestMMUROMReadOnlyByDefault:
    """
    Tests de seguridad para validar que ROM es read-only por defecto.
    """
    
    def test_rom_is_readonly_without_test_mode(self, mmu):
        """
        Validar que ROM (0x0000-0x7FFF) es read-only sin test_mode.
        
        Concepto Hardware:
        ------------------
        En Game Boy real, ROM (0x0000-0x7FFF) es memoria de solo lectura.
        Las escrituras en este rango se interpretan como comandos para el
        Memory Bank Controller (MBC), NO como escrituras directas.
        
        Este test valida que el MMU respeta este comportamiento por defecto.
        """
        # Intentar escribir en ROM sin test_mode
        original_value = mmu.read(0x0000)
        mmu.write(0x0000, 0x3E)  # Intentar escribir 0x3E
        
        # Verificar que NO se escribió (debe seguir siendo el valor original)
        readback = mmu.read(0x0000)
        assert readback == original_value, (
            f"ROM debe ser read-only sin test_mode. "
            f"Intentamos escribir 0x3E en 0x0000, pero se leyó 0x{readback:02X} "
            f"(original: 0x{original_value:02X})"
        )
    
    def test_rom_is_writable_with_test_mode(self, mmu_romw):
        """
        Validar que el fixture mmu_romw SÍ permite escrituras en ROM.
        
        Este test valida que el harness de testing funciona correctamente
        cuando se necesita escribir en ROM para tests unitarios.
        """
        # Con test_mode habilitado, las escrituras SÍ deben funcionar
        mmu_romw.write(0x0000, 0x3E)
        readback = mmu_romw.read(0x0000)
        
        assert readback == 0x3E, (
            f"Con test_mode, ROM debe ser escribible. "
            f"Escribimos 0x3E en 0x0000, pero se leyó 0x{readback:02X}"
        )
    
    def test_rom_range_is_readonly(self, mmu):
        """
        Validar que todo el rango ROM (0x0000-0x7FFF) es read-only.
        
        Prueba varios puntos del rango ROM para asegurar que el
        comportamiento es consistente en toda la región.
        """
        test_addresses = [
            0x0000,  # Inicio ROM Bank 0
            0x0100,  # Entry point típico
            0x4000,  # Inicio ROM Bank 1 (switcheable)
            0x7FFF,  # Fin ROM
        ]
        
        for addr in test_addresses:
            original = mmu.read(addr)
            mmu.write(addr, 0xFF)  # Intentar escribir 0xFF
            readback = mmu.read(addr)
            
            assert readback == original, (
                f"ROM debe ser read-only en 0x{addr:04X}. "
                f"Original: 0x{original:02X}, después de write(0xFF): 0x{readback:02X}"
            )
    
    def test_wram_is_writable_without_test_mode(self, mmu):
        """
        Validar que WRAM (0xC000-0xDFFF) SÍ es escribible sin test_mode.
        
        Esto confirma que el comportamiento read-only es específico de ROM,
        no un problema general del MMU.
        """
        # WRAM debe ser escribible sin test_mode
        test_addr = 0xC000
        mmu.write(test_addr, 0x42)
        readback = mmu.read(test_addr)
        
        assert readback == 0x42, (
            f"WRAM debe ser escribible sin test_mode. "
            f"Escribimos 0x42 en 0x{test_addr:04X}, pero se leyó 0x{readback:02X}"
        )

