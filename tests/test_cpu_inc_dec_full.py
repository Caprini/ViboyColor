"""
Tests para verificar todas las variantes de INC/DEC de 8 bits.

Este test suite verifica:
- INC/DEC para todos los registros (B, C, D, E, H, L, A)
- INC/DEC para memoria indirecta (HL)
- Comportamiento correcto de flags (Z, N, H, C)
- Operaciones Read-Modify-Write en memoria

Fuente: Pan Docs - CPU Instruction Set (INC/DEC instructions)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z, Registers
from src.memory.mmu import MMU


@pytest.fixture
def cpu() -> CPU:
    """Crea una instancia de CPU para testing."""
    mmu = MMU()
    return CPU(mmu)


class TestIncDecRegisters:
    """Tests para INC/DEC en registros individuales."""
    
    def test_inc_dec_e(self, cpu: CPU) -> None:
        """
        Verifica que DEC E funciona correctamente y afecta flags Z, N, H.
        
        Este test es crítico porque DEC E (0x1D) es el opcode que causaba
        el crash en Tetris cuando no estaba implementado.
        """
        # Test 1: DEC E desde valor no cero
        cpu.registers.set_e(0x05)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags
        cycles = cpu._op_dec_e()
        
        assert cycles == 1
        assert cpu.registers.get_e() == 0x04
        assert not cpu.registers.get_flag_z()  # No es cero
        assert cpu.registers.get_flag_n()  # Es una resta
        assert not cpu.registers.get_flag_h()  # No hay half-borrow
        assert not cpu.registers.get_flag_c()  # C no se toca
        
        # Test 2: DEC E desde 0x01 (debe dar 0x00 y activar Z)
        cpu.registers.set_e(0x01)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_dec_e()
        
        assert cycles == 1
        assert cpu.registers.get_e() == 0x00
        assert cpu.registers.get_flag_z()  # Es cero
        assert cpu.registers.get_flag_n()  # Es una resta
        assert not cpu.registers.get_flag_h()  # No hay half-borrow
        assert not cpu.registers.get_flag_c()  # C no se toca
        
        # Test 3: DEC E desde 0x00 (wrap-around a 0xFF)
        cpu.registers.set_e(0x00)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_dec_e()
        
        assert cycles == 1
        assert cpu.registers.get_e() == 0xFF
        assert not cpu.registers.get_flag_z()  # No es cero
        assert cpu.registers.get_flag_n()  # Es una resta
        assert cpu.registers.get_flag_h()  # Hay half-borrow (0x0 -> 0xF)
        assert not cpu.registers.get_flag_c()  # C no se toca
        
        # Test 4: INC E desde 0x0F (debe activar H)
        cpu.registers.set_e(0x0F)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_inc_e()
        
        assert cycles == 1
        assert cpu.registers.get_e() == 0x10
        assert not cpu.registers.get_flag_z()  # No es cero
        assert not cpu.registers.get_flag_n()  # Es una suma
        assert cpu.registers.get_flag_h()  # Hay half-carry (0xF -> 0x10)
        assert not cpu.registers.get_flag_c()  # C no se toca
    
    def test_inc_dec_d(self, cpu: CPU) -> None:
        """Verifica INC/DEC D."""
        # INC D desde 0x42
        cpu.registers.set_d(0x42)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_inc_d()
        
        assert cycles == 1
        assert cpu.registers.get_d() == 0x43
        assert not cpu.registers.get_flag_z()
        assert not cpu.registers.get_flag_n()
        assert not cpu.registers.get_flag_h()
        
        # DEC D desde 0x43
        cycles = cpu._op_dec_d()
        
        assert cycles == 1
        assert cpu.registers.get_d() == 0x42
        assert not cpu.registers.get_flag_z()
        assert cpu.registers.get_flag_n()
        assert not cpu.registers.get_flag_h()
    
    def test_inc_dec_h(self, cpu: CPU) -> None:
        """Verifica INC/DEC H."""
        # INC H desde 0x80
        cpu.registers.set_h(0x80)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_inc_h()
        
        assert cycles == 1
        assert cpu.registers.get_h() == 0x81
        assert not cpu.registers.get_flag_z()
        assert not cpu.registers.get_flag_n()
        assert not cpu.registers.get_flag_h()
        
        # DEC H desde 0x81
        cycles = cpu._op_dec_h()
        
        assert cycles == 1
        assert cpu.registers.get_h() == 0x80
        assert not cpu.registers.get_flag_z()
        assert cpu.registers.get_flag_n()
        assert not cpu.registers.get_flag_h()
    
    def test_inc_dec_l(self, cpu: CPU) -> None:
        """Verifica INC/DEC L."""
        # INC L desde 0xFF (wrap-around)
        cpu.registers.set_l(0xFF)
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        cycles = cpu._op_inc_l()
        
        assert cycles == 1
        assert cpu.registers.get_l() == 0x00
        assert cpu.registers.get_flag_z()  # Es cero
        assert not cpu.registers.get_flag_n()
        assert cpu.registers.get_flag_h()  # Hay half-carry (0xF -> 0x0)
        
        # DEC L desde 0x00 (wrap-around)
        cycles = cpu._op_dec_l()
        
        assert cycles == 1
        assert cpu.registers.get_l() == 0xFF
        assert not cpu.registers.get_flag_z()
        assert cpu.registers.get_flag_n()
        assert cpu.registers.get_flag_h()  # Hay half-borrow


class TestIncDecMemory:
    """Tests para INC/DEC en memoria indirecta (HL)."""
    
    def test_inc_hl_memory(self, cpu: CPU) -> None:
        """
        Verifica INC (HL) con operación Read-Modify-Write.
        
        Pone 0x0F en (HL), ejecuta INC (HL), y verifica que:
        - La memoria tiene 0x10
        - Flag H=1 (half-carry)
        """
        # Configurar HL para apuntar a una dirección de RAM
        hl_addr = 0xC000  # Dirección en RAM de la Game Boy
        cpu.registers.set_hl(hl_addr)
        
        # Escribir 0x0F en memoria
        cpu.mmu.write_byte(hl_addr, 0x0F)
        
        # Limpiar flags
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        
        # Ejecutar INC (HL)
        cycles = cpu._op_inc_hl_ptr()
        
        # Verificar ciclos (3 M-Cycles para Read-Modify-Write)
        assert cycles == 3
        
        # Verificar que la memoria se actualizó correctamente
        assert cpu.mmu.read_byte(hl_addr) == 0x10
        
        # Verificar flags
        assert not cpu.registers.get_flag_z()  # 0x10 no es cero
        assert not cpu.registers.get_flag_n()  # Es una suma
        assert cpu.registers.get_flag_h()  # Hay half-carry (0xF -> 0x10)
        assert not cpu.registers.get_flag_c()  # C no se toca
    
    def test_dec_hl_memory(self, cpu: CPU) -> None:
        """Verifica DEC (HL) con operación Read-Modify-Write."""
        hl_addr = 0xC000
        cpu.registers.set_hl(hl_addr)
        
        # Escribir 0x10 en memoria
        cpu.mmu.write_byte(hl_addr, 0x10)
        
        # Limpiar flags
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        
        # Ejecutar DEC (HL)
        cycles = cpu._op_dec_hl_ptr()
        
        # Verificar ciclos
        assert cycles == 3
        
        # Verificar que la memoria se actualizó correctamente
        assert cpu.mmu.read_byte(hl_addr) == 0x0F
        
        # Verificar flags
        assert not cpu.registers.get_flag_z()  # 0x0F no es cero
        assert cpu.registers.get_flag_n()  # Es una resta
        assert cpu.registers.get_flag_h()  # Hay half-borrow (0x0 -> 0xF)
        assert not cpu.registers.get_flag_c()  # C no se toca
    
    def test_inc_hl_memory_zero_flag(self, cpu: CPU) -> None:
        """Verifica que INC (HL) activa Z cuando el resultado es 0xFF -> 0x00."""
        hl_addr = 0xC000
        cpu.registers.set_hl(hl_addr)
        
        # Escribir 0xFF en memoria
        cpu.mmu.write_byte(hl_addr, 0xFF)
        
        # Limpiar flags
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        
        # Ejecutar INC (HL)
        cycles = cpu._op_inc_hl_ptr()
        
        assert cycles == 3
        assert cpu.mmu.read_byte(hl_addr) == 0x00
        assert cpu.registers.get_flag_z()  # Es cero
        assert not cpu.registers.get_flag_n()
        assert cpu.registers.get_flag_h()  # Hay half-carry
    
    def test_dec_hl_memory_zero_flag(self, cpu: CPU) -> None:
        """Verifica que DEC (HL) activa Z cuando el resultado es 0x01 -> 0x00."""
        hl_addr = 0xC000
        cpu.registers.set_hl(hl_addr)
        
        # Escribir 0x01 en memoria
        cpu.mmu.write_byte(hl_addr, 0x01)
        
        # Limpiar flags
        cpu.registers.set_f(0x00)  # Limpiar todos los flags()
        
        # Ejecutar DEC (HL)
        cycles = cpu._op_dec_hl_ptr()
        
        assert cycles == 3
        assert cpu.mmu.read_byte(hl_addr) == 0x00
        assert cpu.registers.get_flag_z()  # Es cero
        assert cpu.registers.get_flag_n()  # Es una resta
        assert not cpu.registers.get_flag_h()  # No hay half-borrow


class TestIncDecFlagsPreservation:
    """Tests para verificar que el flag C no se modifica en INC/DEC."""
    
    def test_inc_preserves_carry(self, cpu: CPU) -> None:
        """Verifica que INC no modifica el flag C."""
        # Establecer C=1
        cpu.registers.set_flag(FLAG_C)
        cpu.registers.set_e(0x42)
        
        # Ejecutar INC E
        cpu._op_inc_e()
        
        # C debe seguir siendo 1
        assert cpu.registers.get_flag_c()
        
        # Limpiar C
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_e(0x42)
        
        # Ejecutar INC E
        cpu._op_inc_e()
        
        # C debe seguir siendo 0
        assert not cpu.registers.get_flag_c()
    
    def test_dec_preserves_carry(self, cpu: CPU) -> None:
        """Verifica que DEC no modifica el flag C."""
        # Establecer C=1
        cpu.registers.set_flag(FLAG_C)
        cpu.registers.set_e(0x42)
        
        # Ejecutar DEC E
        cpu._op_dec_e()
        
        # C debe seguir siendo 1
        assert cpu.registers.get_flag_c()
        
        # Limpiar C
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_e(0x42)
        
        # Ejecutar DEC E
        cpu._op_dec_e()
        
        # C debe seguir siendo 0
        assert not cpu.registers.get_flag_c()

