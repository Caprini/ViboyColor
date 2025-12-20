"""
Tests para instrucciones de control de sistema y operaciones lógicas

Estos tests validan:
- Control de interrupciones (DI/EI)
- Operaciones lógicas (XOR A)
- Carga inmediata de 16 bits (LD SP, d16, LD HL, d16)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestCPUControl:
    """Tests para instrucciones de control de sistema"""

    def test_di_disables_interrupts(self) -> None:
        """Test: DI desactiva las interrupciones (IME = False)"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Inicialmente IME puede estar en False o True, pero lo activamos primero
        cpu.ime = True
        assert cpu.ime is True
        
        # Ejecutar DI
        cycles = cpu._op_di()
        
        # Verificar que IME está desactivado
        assert cpu.ime is False
        assert cycles == 1

    def test_ei_enables_interrupts(self) -> None:
        """Test: EI activa las interrupciones (IME = True) después de la siguiente instrucción"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Inicialmente IME está en False
        cpu.ime = False
        assert cpu.ime is False
        
        # Ejecutar EI
        cycles = cpu._op_ei()
        assert cycles == 1
        
        # EI tiene un retraso de 1 instrucción, así que IME aún no está activado
        assert cpu.ime is False, "IME no debe estar activado inmediatamente después de EI"
        
        # Ejecutar una instrucción (NOP) para que EI tome efecto
        mmu.write_byte(0x0100, 0x00)  # NOP
        cpu.registers.set_pc(0x0100)
        cpu.step()
        
        # Ahora IME debe estar activado
        assert cpu.ime is True, "IME debe estar activado después de ejecutar una instrucción después de EI"

    def test_di_ei_sequence(self) -> None:
        """Test: Secuencia DI seguida de EI"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Activar IME primero
        cpu.ime = True
        assert cpu.ime is True
        
        # Ejecutar DI
        cpu._op_di()
        assert cpu.ime is False
        
        # Ejecutar EI
        cpu._op_ei()
        assert cpu.ime is True

    def test_xor_a_zeros_accumulator(self) -> None:
        """Test: XOR A pone el registro A a cero"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Establecer A a un valor no cero
        cpu.registers.set_a(0x55)
        assert cpu.registers.get_a() == 0x55
        
        # Ejecutar XOR A
        cycles = cpu._op_xor_a()
        
        # Verificar que A es 0
        assert cpu.registers.get_a() == 0
        assert cycles == 1

    def test_xor_a_sets_zero_flag(self) -> None:
        """Test: XOR A siempre activa el flag Z"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Establecer A a cualquier valor
        cpu.registers.set_a(0xFF)
        cpu.registers.clear_flag(FLAG_Z)
        
        # Ejecutar XOR A
        cpu._op_xor_a()
        
        # Verificar que Z está activado
        assert cpu.registers.get_flag_z() is True

    def test_xor_a_clears_other_flags(self) -> None:
        """Test: XOR A siempre desactiva N, H y C"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Activar todos los flags
        cpu.registers.set_a(0x55)
        cpu.registers.set_flag(FLAG_N)
        cpu.registers.set_flag(FLAG_H)
        cpu.registers.set_flag(FLAG_C)
        
        # Ejecutar XOR A
        cpu._op_xor_a()
        
        # Verificar que N, H y C están desactivados
        assert cpu.registers.get_flag_n() is False
        assert cpu.registers.get_flag_h() is False
        assert cpu.registers.get_flag_c() is False
        # Z debe estar activado
        assert cpu.registers.get_flag_z() is True

    def test_xor_a_with_different_values(self) -> None:
        """Test: XOR A siempre da 0 independientemente del valor inicial"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Probar con diferentes valores
        test_values = [0x00, 0x01, 0x55, 0xAA, 0xFF]
        
        for value in test_values:
            cpu.registers.set_a(value)
            cpu._op_xor_a()
            assert cpu.registers.get_a() == 0, f"XOR A con 0x{value:02X} debería dar 0"

    def test_ld_sp_d16_loads_immediate_value(self) -> None:
        """Test: LD SP, d16 carga un valor inmediato de 16 bits en SP"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar memoria: opcode 0x31 seguido de 0xFE 0xFF (Little-Endian = 0xFFFE)
        mmu.write_byte(0x0100, 0x31)  # LD SP, d16
        mmu.write_byte(0x0101, 0xFE)   # Low byte
        mmu.write_byte(0x0102, 0xFF)  # High byte
        
        # Establecer PC después del opcode (fetch_word lee desde PC actual)
        cpu.registers.set_pc(0x0101)
        
        # Ejecutar LD SP, d16
        cycles = cpu._op_ld_sp_d16()
        
        # Verificar que SP se actualizó correctamente (Little-Endian)
        assert cpu.registers.get_sp() == 0xFFFE
        assert cycles == 3

    def test_ld_sp_d16_with_different_values(self) -> None:
        """Test: LD SP, d16 con diferentes valores"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        test_cases = [
            (0x0000, 0x00, 0x00),
            (0x1234, 0x34, 0x12),  # Little-Endian
            (0xFFFF, 0xFF, 0xFF),
            (0xC000, 0x00, 0xC0),
        ]
        
        for expected, low, high in test_cases:
            mmu.write_byte(0x0100, 0x31)
            mmu.write_byte(0x0101, low)
            mmu.write_byte(0x0102, high)
            cpu.registers.set_pc(0x0101)  # PC después del opcode
            
            cpu._op_ld_sp_d16()
            
            assert cpu.registers.get_sp() == expected, \
                f"LD SP, d16 con {low:02X} {high:02X} debería dar 0x{expected:04X}"

    def test_ld_hl_d16_loads_immediate_value(self) -> None:
        """Test: LD HL, d16 carga un valor inmediato de 16 bits en HL"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar memoria: opcode 0x21 seguido de 0x00 0xC0 (Little-Endian = 0xC000)
        mmu.write_byte(0x0100, 0x21)  # LD HL, d16
        mmu.write_byte(0x0101, 0x00)   # Low byte
        mmu.write_byte(0x0102, 0xC0)  # High byte
        
        # Establecer PC después del opcode (fetch_word lee desde PC actual)
        cpu.registers.set_pc(0x0101)
        
        # Ejecutar LD HL, d16
        cycles = cpu._op_ld_hl_d16()
        
        # Verificar que HL se actualizó correctamente (Little-Endian)
        assert cpu.registers.get_hl() == 0xC000
        assert cycles == 3

    def test_ld_hl_d16_with_different_values(self) -> None:
        """Test: LD HL, d16 con diferentes valores"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        test_cases = [
            (0x0000, 0x00, 0x00),
            (0x1234, 0x34, 0x12),  # Little-Endian
            (0xFFFF, 0xFF, 0xFF),
            (0x8000, 0x00, 0x80),
        ]
        
        for expected, low, high in test_cases:
            mmu.write_byte(0x0100, 0x21)
            mmu.write_byte(0x0101, low)
            mmu.write_byte(0x0102, high)
            cpu.registers.set_pc(0x0101)  # PC después del opcode
            
            cpu._op_ld_hl_d16()
            
            assert cpu.registers.get_hl() == expected, \
                f"LD HL, d16 con {low:02X} {high:02X} debería dar 0x{expected:04X}"

    def test_ld_sp_d16_advances_pc(self) -> None:
        """Test: LD SP, d16 avanza el PC correctamente"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        mmu.write_byte(0x0100, 0x31)
        mmu.write_byte(0x0101, 0xFE)
        mmu.write_byte(0x0102, 0xFF)
        cpu.registers.set_pc(0x0101)  # PC después del opcode
        
        cpu._op_ld_sp_d16()
        
        # PC debería haber avanzado en 2 bytes (los datos leídos por fetch_word)
        assert cpu.registers.get_pc() == 0x0103

    def test_ld_hl_d16_advances_pc(self) -> None:
        """Test: LD HL, d16 avanza el PC correctamente"""
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        mmu.write_byte(0x0100, 0x21)
        mmu.write_byte(0x0101, 0x00)
        mmu.write_byte(0x0102, 0xC0)
        cpu.registers.set_pc(0x0101)  # PC después del opcode
        
        cpu._op_ld_hl_d16()
        
        # PC debería haber avanzado en 2 bytes (los datos leídos por fetch_word)
        assert cpu.registers.get_pc() == 0x0103

