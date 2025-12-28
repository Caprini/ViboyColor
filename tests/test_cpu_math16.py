"""
Tests unitarios para aritmética de 16 bits y retornos condicionales.

Valida las siguientes instrucciones:
- INC BC (0x03), INC DE (0x13), INC HL (0x23), INC SP (0x33): Incremento de 16 bits (NO afecta flags)
- DEC BC (0x0B), DEC DE (0x1B), DEC HL (0x2B), DEC SP (0x3B): Decremento de 16 bits (NO afecta flags)
- ADD HL, BC (0x09), ADD HL, DE (0x19), ADD HL, HL (0x29), ADD HL, SP (0x39): Suma de 16 bits (afecta H y C, NO afecta Z)
- RET NZ (0xC0), RET Z (0xC8), RET NC (0xD0), RET C (0xD8): Retornos condicionales
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_Z
from src.memory.mmu import MMU


class TestInc16Bit:
    """Tests para incremento de registros de 16 bits"""

    def test_inc_bc_no_flags(self):
        """
        Test: Verificar que INC BC (0x03) incrementa BC y NO afecta a los flags.
        
        - Establece Z=1 (para verificar que no se modifica)
        - Establece BC = 0x1234
        - Escribe opcode 0x03 en memoria
        - Ejecuta step()
        - Verifica que BC = 0x1235
        - Verifica que Z sigue siendo 1 (NO cambió)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer BC y flags
        cpu.registers.set_bc(0x1234)
        cpu.registers.set_flag(FLAG_Z)  # Activar Z
        
        # Escribir opcode INC BC
        mmu.write_byte(0x0100, 0x03)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que BC se incrementó
        assert cpu.registers.get_bc() == 0x1235, "BC debe incrementarse a 0x1235"
        
        # Verificar que Z NO cambió (CRÍTICO: INC 16-bit no afecta flags)
        assert cpu.registers.get_flag_z(), "Z debe permanecer activo (INC 16-bit no toca flags)"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "INC BC debe consumir 2 M-Cycles"

    def test_inc_bc_wraparound(self):
        """
        Test: Verificar que INC BC maneja wrap-around correctamente (0xFFFF -> 0x0000).
        
        - Establece BC = 0xFFFF
        - Escribe opcode 0x03 en memoria
        - Ejecuta step()
        - Verifica que BC = 0x0000
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_bc(0xFFFF)
        
        mmu.write_byte(0x0100, 0x03)
        cpu.step()
        
        assert cpu.registers.get_bc() == 0x0000, "BC debe hacer wrap-around a 0x0000"

    def test_inc_de(self):
        """Test: Verificar que INC DE (0x13) incrementa DE correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_de(0x5678)
        cpu.registers.set_flag(FLAG_Z)  # Activar Z para verificar que no cambia
        
        mmu.write_byte(0x0100, 0x13)
        cycles = cpu.step()
        
        assert cpu.registers.get_de() == 0x5679, "DE debe incrementarse"
        assert cpu.registers.get_flag_z(), "Z no debe cambiar"
        assert cycles == 2, "INC DE debe consumir 2 M-Cycles"

    def test_inc_hl(self):
        """Test: Verificar que INC HL (0x23) incrementa HL correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x9ABC)
        
        mmu.write_byte(0x0100, 0x23)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x9ABD, "HL debe incrementarse"
        assert cycles == 2, "INC HL debe consumir 2 M-Cycles"

    def test_inc_sp(self):
        """Test: Verificar que INC SP (0x33) incrementa SP correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        mmu.write_byte(0x0100, 0x33)
        cycles = cpu.step()
        
        assert cpu.registers.get_sp() == 0xFFFF, "SP debe incrementarse"
        assert cycles == 2, "INC SP debe consumir 2 M-Cycles"


class TestDec16Bit:
    """Tests para decremento de registros de 16 bits"""

    def test_dec_bc_no_flags(self):
        """
        Test: Verificar que DEC BC (0x0B) decrementa BC y NO afecta a los flags.
        
        - Establece Z=1 (para verificar que no se modifica)
        - Establece BC = 0x1235
        - Escribe opcode 0x0B en memoria
        - Ejecuta step()
        - Verifica que BC = 0x1234
        - Verifica que Z sigue siendo 1 (NO cambió)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_bc(0x1235)
        cpu.registers.set_flag(FLAG_Z)  # Activar Z
        
        mmu.write_byte(0x0100, 0x0B)
        cycles = cpu.step()
        
        assert cpu.registers.get_bc() == 0x1234, "BC debe decrementarse a 0x1234"
        assert cpu.registers.get_flag_z(), "Z debe permanecer activo (DEC 16-bit no toca flags)"
        assert cycles == 2, "DEC BC debe consumir 2 M-Cycles"

    def test_dec_bc_wraparound(self):
        """
        Test: Verificar que DEC BC maneja wrap-around correctamente (0x0000 -> 0xFFFF).
        
        - Establece BC = 0x0000
        - Escribe opcode 0x0B en memoria
        - Ejecuta step()
        - Verifica que BC = 0xFFFF
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_bc(0x0000)
        
        mmu.write_byte(0x0100, 0x0B)
        cpu.step()
        
        assert cpu.registers.get_bc() == 0xFFFF, "BC debe hacer wrap-around a 0xFFFF"

    def test_dec_de(self):
        """Test: Verificar que DEC DE (0x1B) decrementa DE correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_de(0x5678)
        cpu.registers.set_flag(FLAG_Z)  # Activar Z para verificar que no cambia
        
        mmu.write_byte(0x0100, 0x1B)
        cycles = cpu.step()
        
        assert cpu.registers.get_de() == 0x5677, "DE debe decrementarse"
        assert cpu.registers.get_flag_z(), "Z no debe cambiar"
        assert cycles == 2, "DEC DE debe consumir 2 M-Cycles"

    def test_dec_hl(self):
        """Test: Verificar que DEC HL (0x2B) decrementa HL correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x9ABC)
        
        mmu.write_byte(0x0100, 0x2B)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x9ABB, "HL debe decrementarse"
        assert cycles == 2, "DEC HL debe consumir 2 M-Cycles"

    def test_dec_sp(self):
        """Test: Verificar que DEC SP (0x3B) decrementa SP correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFF)
        
        mmu.write_byte(0x0100, 0x3B)
        cycles = cpu.step()
        
        assert cpu.registers.get_sp() == 0xFFFE, "SP debe decrementarse"
        assert cycles == 2, "DEC SP debe consumir 2 M-Cycles"


class TestAddHL16Bit:
    """Tests para ADD HL, rr (suma de 16 bits a HL)"""

    def test_add_hl_bc(self):
        """
        Test: Verificar que ADD HL, BC (0x09) suma BC a HL y actualiza flags H y C.
        
        - Establece HL = 0x0FFF, BC = 0x0001
        - Escribe opcode 0x09 en memoria
        - Ejecuta step()
        - Verifica que HL = 0x1000
        - Verifica que H flag está activo (carry del bit 11 al 12)
        - Verifica que Z NO cambió (ADD HL no toca Z)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x0FFF)
        cpu.registers.set_bc(0x0001)
        # Establecer Z=0 para verificar que no cambia
        cpu.registers.clear_flag(FLAG_Z)
        
        mmu.write_byte(0x0100, 0x09)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x1000, "HL debe ser 0x1000"
        assert cpu.registers.get_flag_h(), "H debe estar activo (carry del bit 11)"
        assert not cpu.registers.get_flag_z(), "Z no debe cambiar (ADD HL no toca Z)"
        assert cycles == 2, "ADD HL, BC debe consumir 2 M-Cycles"

    def test_add_hl_bc_carry(self):
        """
        Test: Verificar que ADD HL, BC activa C cuando hay carry de 16 bits.
        
        - Establece HL = 0xFFFE, BC = 0x0003
        - Escribe opcode 0x09 en memoria
        - Ejecuta step()
        - Verifica que HL = 0x0001 (wrap-around)
        - Verifica que C flag está activo (carry del bit 15)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0xFFFE)
        cpu.registers.set_bc(0x0003)
        cpu.registers.clear_flag(FLAG_C)  # Asegurar C=0 inicialmente
        
        mmu.write_byte(0x0100, 0x09)
        cpu.step()
        
        assert cpu.registers.get_hl() == 0x0001, "HL debe hacer wrap-around a 0x0001"
        assert cpu.registers.get_flag_c(), "C debe estar activo (carry de 16 bits)"

    def test_add_hl_de(self):
        """Test: Verificar que ADD HL, DE (0x19) suma DE a HL correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x1000)
        cpu.registers.set_de(0x2000)
        
        mmu.write_byte(0x0100, 0x19)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x3000, "HL debe ser 0x3000"
        assert cycles == 2, "ADD HL, DE debe consumir 2 M-Cycles"

    def test_add_hl_hl(self):
        """
        Test: Verificar que ADD HL, HL (0x29) duplica HL (suma HL a sí mismo).
        
        - Establece HL = 0x1000
        - Escribe opcode 0x29 en memoria
        - Ejecuta step()
        - Verifica que HL = 0x2000
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x1000)
        
        mmu.write_byte(0x0100, 0x29)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x2000, "HL debe duplicarse a 0x2000"
        assert cycles == 2, "ADD HL, HL debe consumir 2 M-Cycles"

    def test_add_hl_sp(self):
        """Test: Verificar que ADD HL, SP (0x39) suma SP a HL correctamente."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        mmu.write_byte(0x0100, 0x39)
        cycles = cpu.step()
        
        assert cpu.registers.get_hl() == 0x00FE, "HL debe ser 0x00FE (wrap-around)"
        assert cycles == 2, "ADD HL, SP debe consumir 2 M-Cycles"

    def test_add_hl_no_z_flag(self):
        """
        Test: Verificar que ADD HL, rr NO modifica el flag Z.
        
        - Establece HL = 0x0000, BC = 0x0000
        - Establece Z=1
        - Escribe opcode 0x09 en memoria
        - Ejecuta step()
        - Verifica que Z sigue siendo 1 (NO cambió aunque resultado es 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x0000)
        cpu.registers.set_bc(0x0000)
        cpu.registers.set_flag(FLAG_Z)  # Activar Z
        
        mmu.write_byte(0x0100, 0x09)
        cpu.step()
        
        assert cpu.registers.get_hl() == 0x0000, "HL debe seguir siendo 0x0000"
        assert cpu.registers.get_flag_z(), "Z NO debe cambiar (ADD HL no toca Z)"


class TestConditionalReturn:
    """Tests para retornos condicionales"""

    def test_ret_nz_taken(self):
        """
        Test: Verificar que RET NZ (0xC0) retorna cuando Z=0.
        
        - Establece SP apuntando a dirección de retorno (0x2000)
        - Establece Z=0 (condición verdadera)
        - Simula CALL previo: PUSH return address 0x015B en la pila
        - Escribe opcode 0xC0 en memoria
        - Ejecuta step()
        - Verifica que PC = 0x015B (retornó)
        - Verifica que consume 5 M-Cycles (20 T-Cycles)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        # Simular que hubo un CALL previo: la dirección de retorno está en la pila
        # PUSH escribe primero high luego low, así que SP termina en low
        # POP lee primero low luego high
        return_addr = 0x015B
        mmu.write_byte(0xFFFC, return_addr & 0xFF)  # Low byte (SP apunta aquí)
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)  # High byte
        cpu.registers.set_sp(0xFFFC)  # SP apunta al low byte (primero en POP)
        
        # Establecer Z=0 (condición verdadera para RET NZ)
        cpu.registers.clear_flag(FLAG_Z)
        
        # Escribir opcode RET NZ
        mmu.write_byte(0x0100, 0xC0)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC es la dirección de retorno
        assert cpu.registers.get_pc() == return_addr, "PC debe ser la dirección de retorno"
        
        # Verificar que SP se incrementó (se hizo POP de 2 bytes)
        assert cpu.registers.get_sp() == 0xFFFE, "SP debe incrementarse en 2 después del POP"
        
        # Verificar que consume 5 M-Cycles (cuando se toma el retorno)
        assert cycles == 5, "RET NZ (taken) debe consumir 5 M-Cycles"

    def test_ret_nz_not_taken(self):
        """
        Test: Verificar que RET NZ (0xC0) NO retorna cuando Z=1.
        
        - Establece PC inicial en 0x0100
        - Establece Z=1 (condición falsa)
        - Escribe opcode 0xC0 en memoria
        - Ejecuta step()
        - Verifica que PC = 0x0101 (solo avanzó 1 byte, no retornó)
        - Verifica que consume 2 M-Cycles (8 T-Cycles)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_flag(FLAG_Z)  # Z=1 (condición falsa)
        
        # Escribir opcode RET NZ
        mmu.write_byte(0x0100, 0xC0)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC solo avanzó 1 byte (no retornó)
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar solo 1 byte (no retornó)"
        
        # Verificar que consume 2 M-Cycles (cuando NO se toma el retorno)
        assert cycles == 2, "RET NZ (not taken) debe consumir 2 M-Cycles"

    def test_ret_z_taken(self):
        """Test: Verificar que RET Z (0xC8) retorna cuando Z=1."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        return_addr = 0x0200
        mmu.write_byte(0xFFFC, return_addr & 0xFF)  # Low byte
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)  # High byte
        cpu.registers.set_sp(0xFFFC)  # SP apunta al low byte
        
        cpu.registers.set_flag(FLAG_Z)  # Z=1 (condición verdadera)
        
        mmu.write_byte(0x0100, 0xC8)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == return_addr, "PC debe ser la dirección de retorno"
        assert cycles == 5, "RET Z (taken) debe consumir 5 M-Cycles"

    def test_ret_z_not_taken(self):
        """Test: Verificar que RET Z (0xC8) NO retorna cuando Z=0."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.clear_flag(FLAG_Z)  # Z=0 (condición falsa)
        
        mmu.write_byte(0x0100, 0xC8)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar solo 1 byte"
        assert cycles == 2, "RET Z (not taken) debe consumir 2 M-Cycles"

    def test_ret_nc_taken(self):
        """Test: Verificar que RET NC (0xD0) retorna cuando C=0."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        return_addr = 0x0300
        mmu.write_byte(0xFFFC, return_addr & 0xFF)  # Low byte
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)  # High byte
        cpu.registers.set_sp(0xFFFC)  # SP apunta al low byte
        
        cpu.registers.clear_flag(FLAG_C)  # C=0 (condición verdadera)
        
        mmu.write_byte(0x0100, 0xD0)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == return_addr, "PC debe ser la dirección de retorno"
        assert cycles == 5, "RET NC (taken) debe consumir 5 M-Cycles"

    def test_ret_nc_not_taken(self):
        """Test: Verificar que RET NC (0xD0) NO retorna cuando C=1."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_flag(FLAG_C)  # C=1 (condición falsa)
        
        mmu.write_byte(0x0100, 0xD0)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar solo 1 byte"
        assert cycles == 2, "RET NC (not taken) debe consumir 2 M-Cycles"

    def test_ret_c_taken(self):
        """Test: Verificar que RET C (0xD8) retorna cuando C=1."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        return_addr = 0x0400
        mmu.write_byte(0xFFFC, return_addr & 0xFF)  # Low byte
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)  # High byte
        cpu.registers.set_sp(0xFFFC)  # SP apunta al low byte
        
        cpu.registers.set_flag(FLAG_C)  # C=1 (condición verdadera)
        
        mmu.write_byte(0x0100, 0xD8)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == return_addr, "PC debe ser la dirección de retorno"
        assert cycles == 5, "RET C (taken) debe consumir 5 M-Cycles"

    def test_ret_c_not_taken(self):
        """Test: Verificar que RET C (0xD8) NO retorna cuando C=0."""
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.clear_flag(FLAG_C)  # C=0 (condición falsa)
        
        mmu.write_byte(0x0100, 0xD8)
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar solo 1 byte"
        assert cycles == 2, "RET C (not taken) debe consumir 2 M-Cycles"

