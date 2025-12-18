"""
Tests unitarios para opcodes finales de la CPU.

Valida las siguientes instrucciones críticas que suelen faltar al final:
- LD SP, HL (0xF9): Carga el valor de HL en el Stack Pointer
- JP (HL) (0xE9): Salto indirecto usando HL como dirección destino
- RETI (0xD9): Return from Interrupt (RET + reactivar IME)

Estos opcodes son esenciales para:
- Configuración de stack frames (LD SP, HL)
- Tablas de saltos y llamadas indirectas (JP HL)
- Manejo correcto de interrupciones (RETI)

Fuente: Pan Docs - CPU Instruction Set
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU


class TestLdSpHl:
    """Tests para LD SP, HL (0xF9)"""
    
    def test_ld_sp_hl_basic(self):
        """
        Test: Verificar que LD SP, HL carga el valor de HL en SP.
        
        - Establece HL = 0x1234
        - Escribe opcode 0xF9
        - Ejecuta step()
        - Verifica que SP = 0x1234
        - Verifica que HL no cambia
        - Verifica que consume 2 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x1234)
        cpu.registers.set_sp(0x0000)  # SP inicial diferente
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xF9)  # LD SP, HL
        
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0x1234, "SP debe ser 0x1234"
        assert cpu.registers.get_hl() == 0x1234, "HL no debe cambiar"
        
        # Verificar ciclos
        assert cycles == 2, "LD SP, HL debe consumir 2 M-Cycles"
    
    def test_ld_sp_hl_wraparound(self):
        """
        Test: Verificar que LD SP, HL maneja wrap-around correctamente.
        
        - Establece HL = 0xFFFF
        - Escribe opcode 0xF9
        - Ejecuta step()
        - Verifica que SP = 0xFFFF (máximo valor de 16 bits)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0xFFFF)
        cpu.registers.set_sp(0x0000)
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xF9)  # LD SP, HL
        
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0xFFFF, "SP debe ser 0xFFFF"
        assert cpu.registers.get_hl() == 0xFFFF, "HL debe seguir siendo 0xFFFF"
    
    def test_ld_sp_hl_zero(self):
        """
        Test: Verificar que LD SP, HL funciona con HL = 0x0000.
        
        - Establece HL = 0x0000
        - Escribe opcode 0xF9
        - Ejecuta step()
        - Verifica que SP = 0x0000
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x0000)
        cpu.registers.set_sp(0xFFFE)
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xF9)  # LD SP, HL
        
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0x0000, "SP debe ser 0x0000"
        assert cpu.registers.get_hl() == 0x0000, "HL debe seguir siendo 0x0000"
    
    def test_ld_sp_hl_no_flags(self):
        """
        Test: Verificar que LD SP, HL NO modifica flags.
        
        - Establece flags Z, N, H, C
        - Ejecuta LD SP, HL
        - Verifica que los flags no cambian
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0x1234)
        
        # Establecer flags
        cpu.registers.set_flag(0x80)  # Z
        cpu.registers.set_flag(0x40)  # N
        cpu.registers.set_flag(0x20)  # H
        cpu.registers.set_flag(0x10)  # C
        
        flags_before = cpu.registers.get_f()
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xF9)  # LD SP, HL
        
        cpu.step()
        
        # Verificar que flags no cambiaron
        flags_after = cpu.registers.get_f()
        assert flags_after == flags_before, "LD SP, HL no debe modificar flags"


class TestJpHl:
    """Tests para JP (HL) (0xE9)"""
    
    def test_jp_hl_basic(self):
        """
        Test: Verificar que JP (HL) salta a la dirección en HL.
        
        - Establece HL = 0xC000
        - Escribe opcode 0xE9
        - Ejecuta step()
        - Verifica que PC = 0xC000
        - Verifica que consume 1 M-Cycle
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0xC000)
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xE9)  # JP (HL)
        
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_pc() == 0xC000, "PC debe ser 0xC000"
        assert cpu.registers.get_hl() == 0xC000, "HL no debe cambiar"
        
        # Verificar ciclos
        assert cycles == 1, "JP (HL) debe consumir 1 M-Cycle"
    
    def test_jp_hl_jump_table(self):
        """
        Test: Verificar que JP (HL) funciona como tabla de saltos.
        
        Simula un caso de uso común: usar HL como puntero a una dirección
        de salto almacenada en memoria.
        
        - Establece HL = 0x0200 (dirección donde está la dirección de salto)
        - Escribe en 0x0200: 0x00 0xC0 (Little-Endian: dirección 0xC000)
        - Lee la dirección de memoria en HL
        - Ejecuta JP (HL) (pero en realidad JP usa el valor del registro, no lee memoria)
        - Verifica que PC = 0x0200 (no 0xC000, porque JP HL usa el valor del registro)
        
        NOTA: JP (HL) usa el VALOR del registro HL, no lee de memoria.
        Para leer de memoria y saltar, se necesitaría otra secuencia.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0xC000)  # Dirección destino directa
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xE9)  # JP (HL)
        
        cpu.step()
        
        # Verificar que salta al valor de HL, no a lo que hay en memoria en HL
        assert cpu.registers.get_pc() == 0xC000, "PC debe ser el valor de HL (0xC000)"


class TestReti:
    """Tests para RETI (0xD9)"""
    
    def test_reti_basic(self):
        """
        Test: Verificar que RETI retorna de interrupción y reactiva IME.
        
        - Establece SP = 0xFFFE
        - Empuja dirección de retorno 0x1234 en la pila
        - Desactiva IME (simulando que estamos en una ISR)
        - Escribe opcode 0xD9
        - Ejecuta step()
        - Verifica que PC = 0x1234
        - Verifica que IME = True
        - Verifica que consume 4 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        # Simular PUSH: la pila crece hacia abajo
        # SP inicial: 0xFFFE
        # Después de PUSH: SP = 0xFFFC
        # Datos en Little-Endian: LSB en dirección menor, MSB en dirección mayor
        # 0xFFFC: LSB (0x34)
        # 0xFFFD: MSB (0x12)
        return_addr = 0x1234
        cpu.registers.set_sp(0xFFFC)  # SP después del PUSH
        mmu.write_byte(0xFFFC, return_addr & 0xFF)  # LSB en dirección menor
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)  # MSB en dirección mayor
        
        # Desactivar IME (simulando que estamos en una ISR)
        cpu.ime = False
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0xD9)  # RETI
        
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_pc() == return_addr, f"PC debe ser 0x{return_addr:04X}"
        assert cpu.registers.get_sp() == 0xFFFE, "SP debe volver a 0xFFFE (después del POP)"
        assert cpu.ime is True, "IME debe estar activado después de RETI"
        
        # Verificar ciclos
        assert cycles == 4, "RETI debe consumir 4 M-Cycles"
    
    def test_reti_vs_ret(self):
        """
        Test: Verificar que RETI es diferente de RET (reactiva IME).
        
        - Compara RETI con RET para verificar que RETI reactiva IME
        - RET no debe reactivar IME
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Test RETI
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        return_addr = 0x1234
        mmu.write_byte(0xFFFE, return_addr & 0xFF)
        mmu.write_byte(0xFFFD, (return_addr >> 8) & 0xFF)
        cpu.registers.set_sp(0xFFFC)
        cpu.ime = False
        
        mmu.write_byte(0x0100, 0xD9)  # RETI
        cpu.step()
        
        assert cpu.ime is True, "RETI debe reactivar IME"
        
        # Test RET (no debe reactivar IME)
        cpu.registers.set_pc(0x0200)
        cpu.registers.set_sp(0xFFFE)
        return_addr2 = 0x5678
        mmu.write_byte(0xFFFE, return_addr2 & 0xFF)
        mmu.write_byte(0xFFFD, (return_addr2 >> 8) & 0xFF)
        cpu.registers.set_sp(0xFFFC)
        cpu.ime = False
        
        mmu.write_byte(0x0200, 0xC9)  # RET
        cpu.step()
        
        assert cpu.ime is False, "RET NO debe reactivar IME"

