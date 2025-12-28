"""
Tests unitarios para transferencias de 8 bits (LD r, r') y HALT.

Valida el bloque de opcodes 0x40-0x7F:
- Transferencias entre registros (LD r, r')
- Transferencias con memoria indirecta (LD r, (HL) y LD (HL), r)
- HALT (0x76) - Estado de bajo consumo de la CPU
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU


class TestLoad8Bit:
    """Tests para transferencias de 8 bits (LD r, r')"""
    
    def test_ld_r_r(self):
        """
        Test 1: Verificar transferencia entre registros (LD A, D - 0x7A).
        
        - Establece D = 0x42
        - Ejecuta LD A, D (0x7A)
        - Verifica que A = 0x42
        - Verifica que consume 1 M-Cycle
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer D = 0x42
        cpu.registers.set_d(0x42)
        
        # Escribir opcode LD A, D (0x7A) en memoria
        mmu.write_byte(0x0100, 0x7A)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que A = 0x42
        assert cpu.registers.get_a() == 0x42, "A debe contener el valor de D"
        
        # Verificar que D no cambió
        assert cpu.registers.get_d() == 0x42, "D no debe cambiar"
        
        # Verificar que PC avanzó 1 byte
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar 1 byte"
        
        # Verificar que consume 1 M-Cycle (transferencia entre registros)
        assert cycles == 1, "LD r, r debe consumir 1 M-Cycle"
    
    def test_ld_r_hl(self):
        """
        Test 2: Verificar lectura desde memoria indirecta (LD B, (HL) - 0x46).
        
        - Escribe 0x55 en memoria en dirección 0xC000
        - Establece HL = 0xC000
        - Ejecuta LD B, (HL) (0x46)
        - Verifica que B = 0x55
        - Verifica que consume 2 M-Cycles (acceso a memoria)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir valor en memoria
        mmu.write_byte(0xC000, 0x55)
        
        # Establecer HL = 0xC000
        cpu.registers.set_hl(0xC000)
        
        # Escribir opcode LD B, (HL) (0x46) en memoria
        mmu.write_byte(0x0100, 0x46)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que B = 0x55
        assert cpu.registers.get_b() == 0x55, "B debe contener el valor de (HL)"
        
        # Verificar que HL no cambió
        assert cpu.registers.get_hl() == 0xC000, "HL no debe cambiar"
        
        # Verificar que PC avanzó 1 byte
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar 1 byte"
        
        # Verificar que consume 2 M-Cycles (acceso a memoria)
        assert cycles == 2, "LD r, (HL) debe consumir 2 M-Cycles"
    
    def test_ld_hl_r(self):
        """
        Test 3: Verificar escritura a memoria indirecta (LD (HL), C - 0x71).
        
        - Establece C = 0x99
        - Establece HL = 0xC000
        - Ejecuta LD (HL), C (0x71)
        - Verifica que memoria[0xC000] = 0x99
        - Verifica que consume 2 M-Cycles (acceso a memoria)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer C = 0x99
        cpu.registers.set_c(0x99)
        
        # Establecer HL = 0xC000
        cpu.registers.set_hl(0xC000)
        
        # Escribir opcode LD (HL), C (0x71) en memoria
        mmu.write_byte(0x0100, 0x71)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que memoria[0xC000] = 0x99
        assert mmu.read_byte(0xC000) == 0x99, "Memoria en (HL) debe contener el valor de C"
        
        # Verificar que C no cambió
        assert cpu.registers.get_c() == 0x99, "C no debe cambiar"
        
        # Verificar que HL no cambió
        assert cpu.registers.get_hl() == 0xC000, "HL no debe cambiar"
        
        # Verificar que PC avanzó 1 byte
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar 1 byte"
        
        # Verificar que consume 2 M-Cycles (acceso a memoria)
        assert cycles == 2, "LD (HL), r debe consumir 2 M-Cycles"
    
    def test_ld_all_registers(self):
        """
        Test 4: Verificar transferencias entre todos los registros básicos.
        
        Prueba varias combinaciones de LD r, r' para asegurar que todas funcionan:
        - LD B, A (0x47)
        - LD C, B (0x48)
        - LD D, C (0x51)
        - LD E, D (0x5A)
        - LD H, E (0x63)
        - LD L, H (0x6C)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer valores iniciales
        cpu.registers.set_a(0xAA)
        cpu.registers.set_pc(0x0100)
        
        # LD B, A (0x47)
        mmu.write_byte(0x0100, 0x47)
        cycles = cpu.step()
        assert cpu.registers.get_b() == 0xAA
        assert cycles == 1
        
        # LD C, B (0x48)
        mmu.write_byte(0x0101, 0x48)
        cycles = cpu.step()
        assert cpu.registers.get_c() == 0xAA
        assert cycles == 1
        
        # LD D, C (0x51)
        mmu.write_byte(0x0102, 0x51)
        cycles = cpu.step()
        assert cpu.registers.get_d() == 0xAA
        assert cycles == 1
        
        # LD E, D (0x5A)
        mmu.write_byte(0x0103, 0x5A)
        cycles = cpu.step()
        assert cpu.registers.get_e() == 0xAA
        assert cycles == 1
        
        # LD H, E (0x63)
        mmu.write_byte(0x0104, 0x63)
        cycles = cpu.step()
        assert cpu.registers.get_h() == 0xAA
        assert cycles == 1
        
        # LD L, H (0x6C)
        mmu.write_byte(0x0105, 0x6C)
        cycles = cpu.step()
        assert cpu.registers.get_l() == 0xAA
        assert cycles == 1


class TestHALT:
    """Tests para la instrucción HALT (0x76)"""
    
    def test_halt_sets_flag(self):
        """
        Test 5: Verificar que HALT activa el flag halted.
        
        - Ejecuta HALT (0x76)
        - Verifica que cpu.halted == True
        - Verifica que consume 1 M-Cycle
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Verificar que inicialmente no está en HALT
        assert not cpu.halted, "CPU no debe estar en HALT inicialmente"
        
        # Escribir opcode HALT (0x76) en memoria
        mmu.write_byte(0x0100, 0x76)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que halted está activado
        assert cpu.halted, "CPU debe estar en HALT después de ejecutar HALT"
        
        # Verificar que PC avanzó 1 byte
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar 1 byte"
        
        # Verificar que consume 1 M-Cycle
        assert cycles == 1, "HALT debe consumir 1 M-Cycle"
    
    def test_halt_pc_does_not_advance(self):
        """
        Test 6: Verificar que en HALT, el PC no avanza (no se ejecutan instrucciones).
        
        - Ejecuta HALT
        - Ejecuta step() nuevamente (CPU en HALT)
        - Verifica que PC no cambió
        - Verifica que consume 1 ciclo (espera activa)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir HALT en memoria
        mmu.write_byte(0x0100, 0x76)
        
        # Ejecutar HALT
        cpu.step()
        
        # Verificar que está en HALT
        assert cpu.halted, "CPU debe estar en HALT"
        
        # Guardar PC actual
        pc_before = cpu.registers.get_pc()
        
        # Ejecutar step() mientras está en HALT (IME desactivado)
        cpu.ime = False
        cycles = cpu.step()
        
        # Verificar que PC no cambió
        assert cpu.registers.get_pc() == pc_before, "PC no debe avanzar en HALT"
        
        # Verificar que consume 1 ciclo (espera activa)
        assert cycles == 1, "HALT debe consumir 1 ciclo por tick"
        
        # Verificar que sigue en HALT
        assert cpu.halted, "CPU debe seguir en HALT"
    
    def test_halt_wake_on_interrupt(self):
        """
        Test 7: Verificar que HALT se despierta cuando IME está activado.
        
        - Ejecuta HALT
        - Activa IME
        - Ejecuta step() (debe despertar)
        - Verifica que halted == False
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir HALT en memoria
        mmu.write_byte(0x0100, 0x76)
        
        # Ejecutar HALT
        cpu.step()
        
        # Verificar que está en HALT
        assert cpu.halted, "CPU debe estar en HALT"
        
        # Activar IME (simula interrupción pendiente)
        cpu.ime = True
        
        # Ejecutar step() (debe despertar)
        cpu.step()
        
        # Verificar que se despertó
        assert not cpu.halted, "CPU debe despertar cuando IME está activado"
    
    def test_ld_hl_hl_is_halt(self):
        """
        Test 8: Verificar que 0x76 es HALT, no LD (HL), (HL).
        
        - Intenta ejecutar 0x76
        - Verifica que es HALT, no una transferencia de memoria a memoria
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir 0x76 en memoria
        mmu.write_byte(0x0100, 0x76)
        
        # Escribir un valor en memoria para verificar que no se lee
        mmu.write_byte(0xC000, 0x42)
        cpu.registers.set_hl(0xC000)
        
        # Ejecutar instrucción
        cpu.step()
        
        # Verificar que es HALT, no LD (HL), (HL)
        assert cpu.halted, "0x76 debe ser HALT, no LD (HL), (HL)"
        
        # Verificar que la memoria no cambió (no se ejecutó transferencia)
        assert mmu.read_byte(0xC000) == 0x42, "Memoria no debe cambiar si es HALT"

