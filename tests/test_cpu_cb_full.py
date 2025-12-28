"""
Tests unitarios para operaciones CB completas: BIT, RES y SET (rango 0x40-0xFF).

Valida:
- BIT: Prueba de bits con flags correctos (Z inverso, H=1, C preservado)
- RES: Apagar bits sin afectar flags
- SET: Encender bits sin afectar flags
- Acceso a memoria indirecta (HL) con timing correcto
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestBIT:
    """Tests para la instrucción BIT (Test bit)"""

    def test_bit_all_registers(self):
        """
        Test: BIT 0 funciona en todos los registros.
        
        Verifica que BIT 0, r funciona correctamente para todos los registros
        (B, C, D, E, H, L, A) y memoria indirecta (HL).
        """
        # Opcodes CB para BIT 0, r (0x40 + reg_index)
        opcodes = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]  # B, C, D, E, H, L, (HL), A
        reg_names = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
        
        for i, (opcode, reg_name) in enumerate(zip(opcodes, reg_names)):
            # Crear CPU nueva para cada test (aislar estado)
            mmu = MMU()
            cpu = CPU(mmu)
            
            # Configurar registros con bit 0 encendido
            cpu.registers.set_b(0x01)
            cpu.registers.set_c(0x01)
            cpu.registers.set_d(0x01)
            cpu.registers.set_e(0x01)
            cpu.registers.set_a(0x01)
            # Para (HL), necesitamos una dirección válida
            # Usamos 0xC000 para (HL), pero configuramos H y L individualmente
            if i == 6:  # (HL)
                cpu.registers.set_hl(0xC000)
                mmu.write_byte(0xC000, 0x01)
            else:
                # Para registros individuales, configuramos H y L después
                cpu.registers.set_hl(0xC000)  # Esto establece H=0xC0, L=0x00
                cpu.registers.set_h(0x01)  # Sobrescribir H después de set_hl()
                cpu.registers.set_l(0x01)  # Sobrescribir L después de set_hl()
            cpu.registers.set_pc(0x8000)
            
            # Escribir prefijo CB y opcode
            mmu.write_byte(0x8000, 0xCB)
            mmu.write_byte(0x8001, opcode)
            
            # Ejecutar instrucción
            cycles = cpu.step()
            
            # Verificar flags: bit 0 está encendido, Z debe ser 0
            assert not cpu.registers.get_flag_z(), f"BIT 0, {reg_name}: Z debe ser 0 (bit encendido)"
            assert cpu.registers.get_flag_h(), f"BIT 0, {reg_name}: H debe ser 1"
            assert not cpu.registers.get_flag_n(), f"BIT 0, {reg_name}: N debe ser 0"
            
            # Timing: (HL) consume 4 M-Cycles, registros consumen 2
            expected_cycles = 4 if i == 6 else 2
            assert cycles == expected_cycles, f"BIT 0, {reg_name}: debe consumir {expected_cycles} M-Cycles"
    
    def test_bit_flags_quirk(self):
        """
        Test: BIT pone H=1 siempre (quirk del hardware).
        
        Verifica que BIT siempre activa H=1, independientemente del valor del bit.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x8000)
        
        # Probar BIT 7, H con bit apagado (H = 0x00)
        cpu.registers.set_h(0x00)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x7C)  # BIT 7, H
        
        cpu.step()
        
        # Verificar flags: bit apagado -> Z=1, H=1 (siempre)
        assert cpu.registers.get_flag_z(), "Z debe ser 1 (bit apagado)"
        assert cpu.registers.get_flag_h(), "H debe ser 1 (siempre en BIT)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        
        # Probar BIT 7, H con bit encendido (H = 0x80)
        cpu.registers.set_h(0x80)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x7C)  # BIT 7, H
        
        cpu.step()
        
        # Verificar flags: bit encendido -> Z=0, H=1 (siempre)
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (bit encendido)"
        assert cpu.registers.get_flag_h(), "H debe ser 1 (siempre en BIT)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
    
    def test_bit_preserves_carry(self):
        """
        Test: BIT preserva el flag C (no lo modifica).
        
        Verifica que BIT no afecta al flag C, independientemente del resultado.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x8000)
        
        # Probar con C activado
        cpu.registers.set_b(0x01)
        cpu.registers.set_flag(FLAG_C)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x40)  # BIT 0, B
        
        cpu.step()
        
        assert cpu.registers.get_flag_c(), "C debe preservarse (seguir activado)"
        
        # Probar con C desactivado
        cpu.registers.set_b(0x00)
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x40)  # BIT 0, B
        
        cpu.step()
        
        assert not cpu.registers.get_flag_c(), "C debe preservarse (seguir desactivado)"


class TestRES:
    """Tests para la instrucción RES (Reset bit)"""

    def test_res_memory(self):
        """
        Test: RES apaga bits en memoria indirecta (HL).
        
        - (HL) = 0xFF (todos los bits encendidos)
        - Ejecuta RES 0, (HL)
        - Verifica que (HL) = 0xFE (bit 0 apagado)
        - Verifica que flags no cambian
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_hl(0xC000)
        mmu.write_byte(0xC000, 0xFF)  # Todos los bits encendidos
        cpu.registers.set_pc(0x8000)
        
        # Guardar flags iniciales
        cpu.registers.set_flag(FLAG_Z)
        cpu.registers.set_flag(FLAG_C)
        initial_flags = {
            'Z': cpu.registers.get_flag_z(),
            'N': cpu.registers.get_flag_n(),
            'H': cpu.registers.get_flag_h(),
            'C': cpu.registers.get_flag_c(),
        }
        
        # Escribir prefijo CB y opcode
        mmu.write_byte(0x8000, 0xCB)  # Prefijo CB
        mmu.write_byte(0x8001, 0x86)  # RES 0, (HL)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultado
        assert mmu.read_byte(0xC000) == 0xFE, "(HL) debe ser 0xFE (bit 0 apagado)"
        
        # Verificar que flags no cambian (RES no afecta flags)
        assert cpu.registers.get_flag_z() == initial_flags['Z'], "Z no debe cambiar"
        assert cpu.registers.get_flag_n() == initial_flags['N'], "N no debe cambiar"
        assert cpu.registers.get_flag_h() == initial_flags['H'], "H no debe cambiar"
        assert cpu.registers.get_flag_c() == initial_flags['C'], "C no debe cambiar"
        
        # Timing: (HL) consume 4 M-Cycles
        assert cycles == 4, "Debe consumir 4 M-Cycles (acceso a memoria)"
    
    def test_res_all_bits(self):
        """
        Test: RES apaga correctamente todos los bits (0-7).
        
        Verifica que RES b, B funciona para todos los bits.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x8000)
        
        # Probar cada bit (0-7)
        for bit in range(8):
            # B = 0xFF (todos los bits encendidos)
            cpu.registers.set_b(0xFF)
            
            # Opcode CB para RES bit, B (0x80 + bit*8 + 0)
            opcode = 0x80 + (bit * 8) + 0
            
            # Escribir prefijo CB y opcode
            mmu.write_byte(0x8000, 0xCB)
            mmu.write_byte(0x8001, opcode)
            cpu.registers.set_pc(0x8000)
            
            # Ejecutar instrucción
            cpu.step()
            
            # Verificar que el bit específico está apagado
            expected = 0xFF & ~(1 << bit)
            assert cpu.registers.get_b() == expected, f"RES {bit}, B: debe ser 0x{expected:02X}"


class TestSET:
    """Tests para la instrucción SET (Set bit)"""

    def test_set_memory(self):
        """
        Test: SET enciende bits en memoria indirecta (HL).
        
        - (HL) = 0x00 (todos los bits apagados)
        - Ejecuta SET 7, (HL)
        - Verifica que (HL) = 0x80 (bit 7 encendido)
        - Verifica que flags no cambian
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_hl(0xC000)
        mmu.write_byte(0xC000, 0x00)  # Todos los bits apagados
        cpu.registers.set_pc(0x8000)
        
        # Guardar flags iniciales
        cpu.registers.clear_flag(FLAG_Z)
        cpu.registers.clear_flag(FLAG_C)
        initial_flags = {
            'Z': cpu.registers.get_flag_z(),
            'N': cpu.registers.get_flag_n(),
            'H': cpu.registers.get_flag_h(),
            'C': cpu.registers.get_flag_c(),
        }
        
        # Escribir prefijo CB y opcode
        mmu.write_byte(0x8000, 0xCB)  # Prefijo CB
        mmu.write_byte(0x8001, 0xFE)  # SET 7, (HL)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultado
        assert mmu.read_byte(0xC000) == 0x80, "(HL) debe ser 0x80 (bit 7 encendido)"
        
        # Verificar que flags no cambian (SET no afecta flags)
        assert cpu.registers.get_flag_z() == initial_flags['Z'], "Z no debe cambiar"
        assert cpu.registers.get_flag_n() == initial_flags['N'], "N no debe cambiar"
        assert cpu.registers.get_flag_h() == initial_flags['H'], "H no debe cambiar"
        assert cpu.registers.get_flag_c() == initial_flags['C'], "C no debe cambiar"
        
        # Timing: (HL) consume 4 M-Cycles
        assert cycles == 4, "Debe consumir 4 M-Cycles (acceso a memoria)"
    
    def test_set_all_bits(self):
        """
        Test: SET enciende correctamente todos los bits (0-7).
        
        Verifica que SET b, B funciona para todos los bits.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x8000)
        
        # Probar cada bit (0-7)
        for bit in range(8):
            # B = 0x00 (todos los bits apagados)
            cpu.registers.set_b(0x00)
            
            # Opcode CB para SET bit, B (0xC0 + bit*8 + 0)
            opcode = 0xC0 + (bit * 8) + 0
            
            # Escribir prefijo CB y opcode
            mmu.write_byte(0x8000, 0xCB)
            mmu.write_byte(0x8001, opcode)
            cpu.registers.set_pc(0x8000)
            
            # Ejecutar instrucción
            cpu.step()
            
            # Verificar que el bit específico está encendido
            expected = 1 << bit
            assert cpu.registers.get_b() == expected, f"SET {bit}, B: debe ser 0x{expected:02X}"


class TestBITRESETIntegration:
    """Tests de integración para BIT, RES y SET"""

    def test_bit_res_set_workflow(self):
        """
        Test: Flujo completo BIT -> RES -> SET.
        
        Simula un caso de uso típico:
        1. BIT 7, H para verificar si un bloque ha dejado de caer
        2. RES 7, (HL) para marcar que el bloque ha dejado de caer
        3. SET 0, (HL) para activar un flag
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_h(0x80)  # Bit 7 encendido
        cpu.registers.set_hl(0xC000)
        mmu.write_byte(0xC000, 0xFF)  # Todos los bits encendidos
        cpu.registers.set_pc(0x8000)
        
        # 1. BIT 7, H (verificar si bit 7 está encendido)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x7C)  # BIT 7, H
        cpu.step()
        
        # Verificar que Z=0 (bit está encendido)
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (bit 7 encendido)"
        assert cpu.registers.get_flag_h(), "H debe ser 1"
        
        # 2. RES 7, (HL) (apagar bit 7 en memoria)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0xBE)  # RES 7, (HL)
        cpu.step()
        
        # Verificar que bit 7 está apagado
        assert mmu.read_byte(0xC000) == 0x7F, "(HL) debe ser 0x7F (bit 7 apagado)"
        
        # 3. SET 0, (HL) (encender bit 0 en memoria)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0xC6)  # SET 0, (HL)
        cpu.step()
        
        # Verificar que bit 0 está encendido (0x7F | 0x01 = 0x7F, pero esperamos 0x7F)
        # Espera: 0x7F ya tiene bit 0 encendido, así que debería seguir siendo 0x7F
        # Mejor: empezar con 0x7E y verificar que queda 0x7F
        mmu.write_byte(0xC000, 0x7E)  # 0x7E = 01111110 (bit 0 apagado)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0xC6)  # SET 0, (HL)
        cpu.step()
        
        # Verificar que bit 0 está encendido
        assert mmu.read_byte(0xC000) == 0x7F, "(HL) debe ser 0x7F (bit 0 encendido)"

