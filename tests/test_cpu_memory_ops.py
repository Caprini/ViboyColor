"""
Tests unitarios para operaciones de memoria indirecta e incremento/decremento.

Valida:
- Direccionamiento indirecto con HL (LD (HL), A, LD (HL+), A, etc.)
- Operaciones INC/DEC con manejo correcto de flags (especialmente que NO tocan C)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestMemoryIndirect:
    """Tests para direccionamiento indirecto usando HL como puntero"""

    def test_ld_hl_ptr_a(self):
        """
        Test: LD (HL), A escribe correctamente en la dirección apuntada por HL.
        
        - HL = 0xC000
        - A = 0x55
        - Ejecuta 0x77 (LD (HL), A)
        - Verifica que Memoria[0xC000] == 0x55
        - Verifica que HL no cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_hl(0xC000)
        cpu.registers.set_a(0x55)
        cpu.registers.set_pc(0x8000)  # Usar área fuera de ROM
        
        # Escribir opcode en memoria
        mmu.write_byte(0x8000, 0x77)  # LD (HL), A
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió correctamente
        assert mmu.read_byte(0xC000) == 0x55, "Memoria[0xC000] debe ser 0x55"
        assert cpu.registers.get_hl() == 0xC000, "HL no debe cambiar"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_ldi_hl_a(self):
        """
        Test: LD (HL+), A escribe y incrementa HL.
        
        - HL = 0xC000
        - A = 0xAA
        - Ejecuta 0x22 (LD (HL+), A)
        - Verifica escritura en 0xC000
        - Verifica que HL ahora es 0xC001
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_hl(0xC000)
        cpu.registers.set_a(0xAA)
        cpu.registers.set_pc(0x8000)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x8000, 0x22)  # LD (HL+), A
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar escritura
        assert mmu.read_byte(0xC000) == 0xAA, "Memoria[0xC000] debe ser 0xAA"
        # Verificar incremento de HL
        assert cpu.registers.get_hl() == 0xC001, "HL debe incrementarse a 0xC001"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_ldi_hl_a_wrap_around(self):
        """
        Test: LD (HL+), A con wrap-around de HL.
        
        - HL = 0xFFFF
        - A = 0xBB
        - Ejecuta 0x22
        - Verifica que HL hace wrap-around a 0x0000
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_hl(0xFFFF)
        cpu.registers.set_a(0xBB)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0x22)  # LD (HL+), A
        
        cycles = cpu.step()
        
        assert mmu.read_byte(0xFFFF) == 0xBB, "Debe escribir en 0xFFFF"
        assert cpu.registers.get_hl() == 0x0000, "HL debe hacer wrap-around a 0x0000"
        assert cycles == 2
    
    def test_ldd_hl_a(self):
        """
        Test: LD (HL-), A escribe y decrementa HL.
        
        - HL = 0xC000
        - A = 0xCC
        - Ejecuta 0x32 (LD (HL-), A)
        - Verifica escritura en 0xC000
        - Verifica que HL ahora es 0xBFFF
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_hl(0xC000)
        cpu.registers.set_a(0xCC)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0x32)  # LD (HL-), A
        
        cycles = cpu.step()
        
        assert mmu.read_byte(0xC000) == 0xCC, "Memoria[0xC000] debe ser 0xCC"
        assert cpu.registers.get_hl() == 0xBFFF, "HL debe decrementarse a 0xBFFF"
        assert cycles == 2
    
    def test_ldd_hl_a_wrap_around(self):
        """
        Test: LD (HL-), A con wrap-around de HL.
        
        - HL = 0x8000
        - A = 0xDD
        - Ejecuta 0x32
        - Verifica escritura y que HL decrementa correctamente
        - Luego prueba wrap-around desde 0x0000 a 0xFFFF
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Primero verificar decremento normal
        cpu.registers.set_hl(0x8000)
        cpu.registers.set_a(0xDD)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x32)  # LD (HL-), A
        
        cycles = cpu.step()
        assert mmu.read_byte(0x8000) == 0xDD, "Debe escribir en 0x8000"
        assert cpu.registers.get_hl() == 0x7FFF, "HL debe decrementarse a 0x7FFF"
        
        # Ahora verificar wrap-around: 0x0000 -> 0xFFFF
        cpu.registers.set_hl(0x0000)
        cpu.registers.set_a(0xEE)
        cpu.registers.set_pc(0x8001)
        mmu.write_byte(0x8001, 0x32)  # LD (HL-), A
        
        cycles = cpu.step()
        # Nota: No podemos verificar escritura en 0x0000 porque está en área ROM,
        # pero podemos verificar que HL hace wrap-around correctamente
        assert cpu.registers.get_hl() == 0xFFFF, "HL debe hacer wrap-around a 0xFFFF"
        assert cycles == 2
    
    def test_ldi_a_hl_ptr(self):
        """
        Test: LD A, (HL+) lee de memoria e incrementa HL.
        
        - HL = 0xC000
        - Memoria[0xC000] = 0x42
        - Ejecuta 0x2A (LD A, (HL+))
        - Verifica que A == 0x42
        - Verifica que HL ahora es 0xC001
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_hl(0xC000)
        cpu.registers.set_pc(0x8000)
        
        # Escribir dato en memoria
        mmu.write_byte(0xC000, 0x42)
        
        # Escribir opcode
        mmu.write_byte(0x8000, 0x2A)  # LD A, (HL+)
        
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x42, "A debe ser 0x42"
        assert cpu.registers.get_hl() == 0xC001, "HL debe incrementarse a 0xC001"
        assert cycles == 2


class TestIncDecFlags:
    """Tests para operaciones INC/DEC con manejo correcto de flags"""
    
    def test_inc_b_normal(self):
        """
        Test: INC B en caso normal (1 -> 2).
        
        - B = 1
        - Ejecuta INC B
        - Verifica que B == 2
        - Verifica que Z=0, N=0, H=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(1)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x04)  # INC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 2, "B debe ser 2"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        assert not cpu.registers.get_flag_h(), "H debe ser 0"
        assert cycles == 1
    
    def test_inc_b_half_carry(self):
        """
        Test: INC B con Half-Carry (0x0F -> 0x10).
        
        CRÍTICO: Verifica que el flag H se activa cuando hay carry del bit 3 al 4.
        - B = 0x0F
        - Ejecuta INC B
        - Verifica que B == 0x10
        - Verifica que H == 1 (Half-Carry activado)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x0F)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x04)  # INC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x10, "B debe ser 0x10"
        assert cpu.registers.get_flag_h(), "H debe estar activo (Half-Carry)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        assert cycles == 1
    
    def test_inc_b_overflow_no_carry(self):
        """
        Test: INC B con overflow (0xFF -> 0x00) NO afecta flag C.
        
        CRÍTICO: INC NO debe tocar el flag C, incluso con overflow.
        Muchos emuladores fallan aquí.
        - B = 0xFF
        - C flag inicialmente en 0
        - Ejecuta INC B
        - Verifica que B == 0x00, Z == 1
        - Verifica que C NO cambia (sigue siendo 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0xFF)
        cpu.registers.clear_flag(FLAG_C)  # Asegurar que C está en 0
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x04)  # INC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x00, "B debe hacer wrap-around a 0x00"
        assert cpu.registers.get_flag_z(), "Z debe estar activo (resultado es 0)"
        assert not cpu.registers.get_flag_c(), "C NO debe cambiar (debe seguir en 0)"
        assert cycles == 1
    
    def test_inc_b_preserves_carry(self):
        """
        Test: INC B preserva el flag C si estaba activo.
        
        - B = 0x42
        - C flag inicialmente en 1
        - Ejecuta INC B
        - Verifica que C sigue siendo 1 (no se toca)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x42)
        cpu.registers.set_flag(FLAG_C)  # Activar C
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x04)  # INC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x43, "B debe ser 0x43"
        assert cpu.registers.get_flag_c(), "C debe preservarse (sigue en 1)"
        assert cycles == 1
    
    def test_dec_b_normal(self):
        """
        Test: DEC B en caso normal (5 -> 4).
        
        - B = 5
        - Ejecuta DEC B
        - Verifica que B == 4
        - Verifica que Z=0, N=1, H=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(5)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x05)  # DEC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 4, "B debe ser 4"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert cpu.registers.get_flag_n(), "N debe ser 1 (es una resta)"
        assert not cpu.registers.get_flag_h(), "H debe ser 0"
        assert cycles == 1
    
    def test_dec_b_half_borrow(self):
        """
        Test: DEC B con Half-Borrow (0x10 -> 0x0F).
        
        - B = 0x10
        - Ejecuta DEC B
        - Verifica que B == 0x0F
        - Verifica que H == 1 (Half-Borrow activado)
        - Verifica que N == 1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x10)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x05)  # DEC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x0F, "B debe ser 0x0F"
        assert cpu.registers.get_flag_h(), "H debe estar activo (Half-Borrow)"
        assert cpu.registers.get_flag_n(), "N debe ser 1 (es una resta)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert cycles == 1
    
    def test_dec_b_zero_no_carry(self):
        """
        Test: DEC B con resultado cero (1 -> 0) NO afecta flag C.
        
        - B = 1
        - C flag inicialmente en 0
        - Ejecuta DEC B
        - Verifica que B == 0, Z == 1
        - Verifica que C NO cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(1)
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x05)  # DEC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x00, "B debe ser 0x00"
        assert cpu.registers.get_flag_z(), "Z debe estar activo"
        assert cpu.registers.get_flag_n(), "N debe ser 1"
        assert not cpu.registers.get_flag_c(), "C NO debe cambiar"
        assert cycles == 1
    
    def test_inc_dec_variants(self):
        """
        Test: Variantes INC/DEC (C, A) funcionan igual que B.
        
        Verifica que INC C, DEC C, INC A, DEC A tienen el mismo comportamiento
        que INC B y DEC B respecto a flags.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Test INC C con Half-Carry
        cpu.registers.set_c(0x0F)
        cpu.registers.set_pc(0x8000)
        mmu.write_byte(0x8000, 0x0C)  # INC C
        
        cpu.step()
        assert cpu.registers.get_c() == 0x10
        assert cpu.registers.get_flag_h()
        
        # Test DEC C con Half-Borrow
        cpu.registers.set_c(0x10)
        cpu.registers.set_pc(0x8002)
        mmu.write_byte(0x8002, 0x0D)  # DEC C
        
        cpu.step()
        assert cpu.registers.get_c() == 0x0F
        assert cpu.registers.get_flag_h()
        assert cpu.registers.get_flag_n()
        
        # Test INC A con overflow (preserva C)
        cpu.registers.set_a(0xFF)
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_pc(0x8004)
        mmu.write_byte(0x8004, 0x3C)  # INC A
        
        cpu.step()
        assert cpu.registers.get_a() == 0x00
        assert cpu.registers.get_flag_z()
        assert not cpu.registers.get_flag_c()  # C no cambia
        
        # Test DEC A con cero (preserva C)
        cpu.registers.set_a(1)
        cpu.registers.set_flag(FLAG_C)  # Activar C
        cpu.registers.set_pc(0x8006)
        mmu.write_byte(0x8006, 0x3D)  # DEC A
        
        cpu.step()
        assert cpu.registers.get_a() == 0x00
        assert cpu.registers.get_flag_z()
        assert cpu.registers.get_flag_n()
        assert cpu.registers.get_flag_c()  # C se preserva

