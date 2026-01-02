"""
Test de seguridad: ROM es read-only por defecto (Step 0422, actualizado en Step 0425)

Este test valida que el comportamiento por defecto del MMU es correcto:
- ROM (0x0000-0x7FFF) NO es escribible directamente (escrituras se interpretan como MBC)
- Esto protege la integridad de la emulación (spec-correct según Pan Docs)

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
    
    def test_rom_is_readonly_by_default(self, mmu):
        """
        Validar que ROM (0x0000-0x7FFF) es read-only (spec-correct).
        
        Concepto Hardware (Pan Docs):
        ------------------------------
        En Game Boy real, ROM (0x0000-0x7FFF) es memoria de solo lectura.
        Las escrituras en este rango se interpretan como comandos para el
        Memory Bank Controller (MBC), NO como escrituras directas.
        
        Este test valida que el MMU respeta este comportamiento por defecto.
        
        Step 0425: Eliminado uso de test_mode (hack no spec-correct).
        """
        # Intentar escribir en ROM (debe interpretarse como comando MBC, no escritura directa)
        original_value = mmu.read(0x0000)
        mmu.write(0x0000, 0x3E)  # Intentar escribir 0x3E (o comando MBC según contexto)
        
        # Verificar que NO se escribió (debe seguir siendo el valor original)
        readback = mmu.read(0x0000)
        assert readback == original_value, (
            f"ROM debe ser read-only (spec-correct). "
            f"Intentamos escribir 0x3E en 0x0000, pero se leyó 0x{readback:02X} "
            f"(original: 0x{original_value:02X})"
        )
    
    def test_rom_can_be_loaded_with_load_rom(self, mmu):
        """
        Validar que ROM personalizada se puede cargar con load_rom() (spec-correct).
        
        Step 0425: Reemplazado test que usaba test_mode (hack) por test que usa load_rom().
        Este es el método spec-correct para cargar ROM personalizada en tests.
        
        Concepto:
        ---------
        - load_rom() es el método correcto para cargar datos en ROM (simula cargar cartucho)
        - Una vez cargada, ROM es read-only (escrituras se interpretan como comandos MBC)
        """
        # Preparar ROM personalizada (512 bytes mínimo para incluir entry point 0x100)
        custom_rom = bytearray(512)
        custom_rom[0] = 0x3E  # LD A, d8
        custom_rom[1] = 0x42
        custom_rom[0x100] = 0xC3  # JP nn (entry point típico en 0x0100)
        
        # Cargar ROM usando el método spec-correct (load_rom_py espera bytes)
        mmu.load_rom_py(bytes(custom_rom))
        
        # Verificar que se cargó correctamente
        assert mmu.read(0x0000) == 0x3E, "load_rom() debe cargar datos en ROM"
        assert mmu.read(0x0001) == 0x42
        assert mmu.read(0x0100) == 0xC3
        
        # Verificar que ROM sigue siendo read-only después de cargar
        mmu.write(0x0000, 0xFF)  # Intentar escribir
        readback = mmu.read(0x0000)
        assert readback == 0x3E, (
            f"ROM debe ser read-only incluso después de load_rom(). "
            f"Escribimos 0xFF pero se leyó 0x{readback:02X}"
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
    
    def test_wram_is_writable_always(self, mmu):
        """
        Validar que WRAM (0xC000-0xDFFF) SÍ es escribible (spec-correct).
        
        Concepto (Pan Docs):
        --------------------
        WRAM es memoria de lectura/escritura en el Game Boy real.
        Esto confirma que el comportamiento read-only es específico de ROM,
        no un problema general del MMU.
        
        Step 0425: Eliminada referencia a test_mode (ya no existe).
        """
        # WRAM debe ser escribible siempre (spec-correct)
        test_addr = 0xC000
        mmu.write(test_addr, 0x42)
        readback = mmu.read(test_addr)
        
        assert readback == 0x42, (
            f"WRAM debe ser escribible (spec-correct). "
            f"Escribimos 0x42 en 0x{test_addr:04X}, pero se leyó 0x{readback:02X}"
        )

