#!/usr/bin/env python3
"""
8051 Intel HEX 反汇编器
将 .hex 文件解析并反汇编为 8051 汇编代码
"""

import sys
import struct

# 8051 指令集 (mnemonic -> bytes, 这里 key 是 opcode)
# 格式: (mnemonic, operand_type, bytes)
# operand_type: 0=无, 1=#data8, 2=direct, 3=@Ri, 4=rel, 5=addr11, 6=addr16, 7=bit, 8=A+direct, 9=#data16, 10=Ri+direct(A=acc)
OPCODES = {
    0x00: ("NOP",    0, 1),
    0x01: ("AJMP",   5, 2),  # addr11 - handled specially
    0x02: ("LJMP",   6, 3),
    0x03: ("RR",     12, 1),  # A
    0x04: ("INC",    12, 1),  # A
    0x05: ("INC",    2, 2),   # direct
    0x06: ("INC",    10, 1),  # @R0
    0x07: ("INC",    10, 1),  # @R1
    0x08: ("INC",    13, 1),  # R0
    0x09: ("INC",    13, 1),  # R1
    0x0A: ("INC",    13, 1),  # R2
    0x0B: ("INC",    13, 1),  # R3
    0x0C: ("INC",    13, 1),  # R4
    0x0D: ("INC",    13, 1),  # R5
    0x0E: ("INC",    13, 1),  # R6
    0x0F: ("INC",    13, 1),  # R7
    0x10: ("JBC",    7, 3),   # bit, rel
    0x11: ("ACALL",  5, 2),
    0x12: ("LCALL",  6, 3),
    0x13: ("RRC",    12, 1),
    0x14: ("DEC",    12, 1),  # A
    0x15: ("DEC",    2, 2),
    0x16: ("DEC",    10, 1),  # @R0
    0x17: ("DEC",    10, 1),  # @R1
    0x18: ("DEC",    13, 1),  # R0
    0x19: ("DEC",    13, 1),  # R1
    0x1A: ("DEC",    13, 1),  # R2
    0x1B: ("DEC",    13, 1),  # R3
    0x1C: ("DEC",    13, 1),  # R4
    0x1D: ("DEC",    13, 1),  # R5
    0x1E: ("DEC",    13, 1),  # R6
    0x1F: ("DEC",    13, 1),  # R7
    0x20: ("JB",     7, 3),   # bit, rel
    0x21: ("AJMP",   5, 2),
    0x22: ("RET",    0, 1),
    0x23: ("RL",     12, 1),
    0x24: ("ADD",    1, 2),   # A, #data
    0x25: ("ADD",    2, 2),   # A, direct
    0x26: ("ADD",    10, 1),  # A, @R0
    0x27: ("ADD",    10, 1),  # A, @R1
    0x28: ("ADD",    13, 1),  # A, R0
    0x29: ("ADD",    13, 1),  # A, R1
    0x2A: ("ADD",    13, 1),  # A, R2
    0x2B: ("ADD",    13, 1),  # A, R3
    0x2C: ("ADD",    13, 1),  # A, R4
    0x2D: ("ADD",    13, 1),  # A, R5
    0x2E: ("ADD",    13, 1),  # A, R6
    0x2F: ("ADD",    13, 1),  # A, R7
    0x30: ("JNB",    7, 3),
    0x31: ("ACALL",  5, 2),
    0x32: ("RETI",   0, 1),
    0x33: ("RLC",    12, 1),
    0x34: ("ADDC",   1, 2),
    0x35: ("ADDC",   2, 2),
    0x36: ("ADDC",   10, 1),
    0x37: ("ADDC",   10, 1),
    0x38: ("ADDC",   13, 1),
    0x39: ("ADDC",   13, 1),
    0x3A: ("ADDC",   13, 1),
    0x3B: ("ADDC",   13, 1),
    0x3C: ("ADDC",   13, 1),
    0x3D: ("ADDC",   13, 1),
    0x3E: ("ADDC",   13, 1),
    0x3F: ("ADDC",   13, 1),
    0x40: ("JC",     4, 2),
    0x41: ("AJMP",   5, 2),
    0x42: ("ORL",    2, 2),   # direct, A
    0x43: ("ORL",    1, 3),   # direct, #data
    0x44: ("ORL",    1, 2),   # A, #data
    0x45: ("ORL",    2, 2),   # A, direct
    0x46: ("ORL",    10, 1),
    0x47: ("ORL",    10, 1),
    0x48: ("ORL",    13, 1),
    0x49: ("ORL",    13, 1),
    0x4A: ("ORL",    13, 1),
    0x4B: ("ORL",    13, 1),
    0x4C: ("ORL",    13, 1),
    0x4D: ("ORL",    13, 1),
    0x4E: ("ORL",    13, 1),
    0x4F: ("ORL",    13, 1),
    0x50: ("JNC",    4, 2),
    0x51: ("ACALL",  5, 2),
    0x52: ("ANL",    2, 2),   # direct, A
    0x53: ("ANL",    1, 3),   # direct, #data
    0x54: ("ANL",    1, 2),
    0x55: ("ANL",    2, 2),
    0x56: ("ANL",    10, 1),
    0x57: ("ANL",    10, 1),
    0x58: ("ANL",    13, 1),
    0x59: ("ANL",    13, 1),
    0x5A: ("ANL",    13, 1),
    0x5B: ("ANL",    13, 1),
    0x5C: ("ANL",    13, 1),
    0x5D: ("ANL",    13, 1),
    0x5E: ("ANL",    13, 1),
    0x5F: ("ANL",    13, 1),
    0x60: ("JZ",     4, 2),
    0x61: ("AJMP",   5, 2),
    0x62: ("XRL",    2, 2),
    0x63: ("XRL",    1, 3),
    0x64: ("XRL",    1, 2),
    0x65: ("XRL",    2, 2),
    0x66: ("XRL",    10, 1),
    0x67: ("XRL",    10, 1),
    0x68: ("XRL",    13, 1),
    0x69: ("XRL",    13, 1),
    0x6A: ("XRL",    13, 1),
    0x6B: ("XRL",    13, 1),
    0x6C: ("XRL",    13, 1),
    0x6D: ("XRL",    13, 1),
    0x6E: ("XRL",    13, 1),
    0x6F: ("XRL",    13, 1),
    0x70: ("JNZ",    4, 2),
    0x71: ("ACALL",  5, 2),
    0x72: ("ORL",    7, 2),   # C, bit (special)
    0x73: ("JMP",    8, 1),   # @A+DPTR
    0x74: ("MOV",    1, 2),   # A, #data
    0x75: ("MOV",    1, 3),   # direct, #data  -- 3 bytes
    0x76: ("MOV",    10, 2),  # @R0, #data
    0x77: ("MOV",    10, 2),  # @R1, #data
    0x78: ("MOV",    13, 2),  # R0, #data
    0x79: ("MOV",    13, 2),  # R1, #data
    0x7A: ("MOV",    13, 2),  # R2, #data
    0x7B: ("MOV",    13, 2),  # R3, #data
    0x7C: ("MOV",    13, 2),  # R4, #data
    0x7D: ("MOV",    13, 2),  # R5, #data
    0x7E: ("MOV",    13, 2),  # R6, #data
    0x7F: ("MOV",    13, 2),  # R7, #data
    0x80: ("SJMP",   4, 2),
    0x81: ("AJMP",   5, 2),
    0x82: ("ANL",    7, 2),   # C, bit
    0x83: ("MOVC",   8, 1),   # A, @A+PC
    0x84: ("DIV",    11, 1),  # AB
    0x85: ("MOV",    2, 3),   # direct, direct
    0x86: ("MOV",    2, 2),   # direct, @R0 -- actually this is different... let me check
    0x87: ("MOV",    2, 2),   # direct, @R1
    0x88: ("MOV",    2, 2),   # direct, R0
    0x89: ("MOV",    2, 2),   # direct, R1
    0x8A: ("MOV",    2, 2),   # direct, R2
    0x8B: ("MOV",    2, 2),   # direct, R3
    0x8C: ("MOV",    2, 2),   # direct, R4
    0x8D: ("MOV",    2, 2),   # direct, R5
    0x8E: ("MOV",    2, 2),   # direct, R6
    0x8F: ("MOV",    2, 2),   # direct, R7
    0x90: ("MOV",    9, 3),   # DPTR, #data16
    0x91: ("ACALL",  5, 2),
    0x92: ("MOV",    7, 2),   # bit, C
    0x93: ("MOVC",   16, 1),  # A, @A+DPTR
    0x94: ("SUBB",   1, 2),   # A, #data
    0x95: ("SUBB",   2, 2),   # A, direct
    0x96: ("SUBB",   10, 1),
    0x97: ("SUBB",   10, 1),
    0x98: ("SUBB",   13, 1),
    0x99: ("SUBB",   13, 1),
    0x9A: ("SUBB",   13, 1),
    0x9B: ("SUBB",   13, 1),
    0x9C: ("SUBB",   13, 1),
    0x9D: ("SUBB",   13, 1),
    0x9E: ("SUBB",   13, 1),
    0x9F: ("SUBB",   13, 1),
    0xA0: ("ORL",    7, 2),   # C, /bit
    0xA1: ("AJMP",   5, 2),
    0xA2: ("MOV",    17, 2),  # C, bit
    0xA3: ("INC",    9, 1),   # DPTR
    0xA4: ("MUL",    11, 1),  # AB
    0xA5: ("",       0, 1),   # reserved
    0xA6: ("MOV",    10, 2),  # @R0, direct
    0xA7: ("MOV",    10, 2),  # @R1, direct
    0xA8: ("MOV",    13, 2),  # R0, direct
    0xA9: ("MOV",    13, 2),  # R1, direct
    0xAA: ("MOV",    13, 2),  # R2, direct
    0xAB: ("MOV",    13, 2),  # R3, direct
    0xAC: ("MOV",    13, 2),  # R4, direct
    0xAD: ("MOV",    13, 2),  # R5, direct
    0xAE: ("MOV",    13, 2),  # R6, direct
    0xAF: ("MOV",    13, 2),  # R7, direct
    0xB0: ("ANL",    7, 2),   # C, /bit
    0xB1: ("ACALL",  5, 2),
    0xB2: ("CPL",    7, 2),   # bit
    0xB3: ("CPL",    17, 1),  # C
    0xB4: ("CJNE",   1, 3),   # A, #data, rel
    0xB5: ("CJNE",   1, 3),   # A, direct, rel
    0xB6: ("CJNE",   10, 3),  # @R0, #data, rel
    0xB7: ("CJNE",   10, 3),  # @R1, #data, rel
    0xB8: ("CJNE",   13, 3),  # Rn, #data, rel
    0xB9: ("CJNE",   13, 3),
    0xBA: ("CJNE",   13, 3),
    0xBB: ("CJNE",   13, 3),
    0xBC: ("CJNE",   13, 3),
    0xBD: ("CJNE",   13, 3),
    0xBE: ("CJNE",   13, 3),
    0xBF: ("CJNE",   13, 3),
    0xC0: ("PUSH",   2, 2),
    0xC1: ("AJMP",   5, 2),
    0xC2: ("CLR",    7, 2),   # bit
    0xC3: ("CLR",    17, 1),  # C
    0xC4: ("SWAP",   12, 1),  # A
    0xC5: ("XCH",    2, 2),   # A, direct
    0xC6: ("XCH",    10, 1),  # A, @R0
    0xC7: ("XCH",    10, 1),  # A, @R1
    0xC8: ("XCH",    13, 1),  # A, R0
    0xC9: ("XCH",    13, 1),  # A, R1
    0xCA: ("XCH",    13, 1),  # A, R2
    0xCB: ("XCH",    13, 1),  # A, R3
    0xCC: ("XCH",    13, 1),  # A, R4
    0xCD: ("XCH",    13, 1),  # A, R5
    0xCE: ("XCH",    13, 1),  # A, R6
    0xCF: ("XCH",    13, 1),  # A, R7
    0xD0: ("POP",    2, 2),
    0xD1: ("ACALL",  5, 2),
    0xD2: ("SETB",   7, 2),
    0xD3: ("SETB",   17, 1),  # C
    0xD4: ("DA",     12, 1),  # A
    0xD5: ("DJNZ",   2, 3),   # direct, rel
    0xD6: ("XCHD",   10, 1),  # A, @R0
    0xD7: ("XCHD",   10, 1),  # A, @R1
    0xD8: ("DJNZ",   13, 2),  # Rn, rel
    0xD9: ("DJNZ",   13, 2),
    0xDA: ("DJNZ",   13, 2),
    0xDB: ("DJNZ",   13, 2),
    0xDC: ("DJNZ",   13, 2),
    0xDD: ("DJNZ",   13, 2),
    0xDE: ("DJNZ",   13, 2),
    0xDF: ("DJNZ",   13, 2),
    0xE0: ("MOVX",   18, 1),  # A, @DPTR
    0xE1: ("AJMP",   5, 2),
    0xE2: ("MOVX",   10, 1),  # A, @R0
    0xE3: ("MOVX",   10, 1),  # A, @R1
    0xE4: ("CLR",    12, 1),  # A
    0xE5: ("MOV",    2, 2),   # A, direct
    0xE6: ("MOV",    10, 1),  # A, @R0
    0xE7: ("MOV",    10, 1),  # A, @R1
    0xE8: ("MOV",    13, 1),  # A, R0
    0xE9: ("MOV",    13, 1),  # A, R1
    0xEA: ("MOV",    13, 1),  # A, R2
    0xEB: ("MOV",    13, 1),  # A, R3
    0xEC: ("MOV",    13, 1),  # A, R4
    0xED: ("MOV",    13, 1),  # A, R5
    0xEE: ("MOV",    13, 1),  # A, R6
    0xEF: ("MOV",    13, 1),  # A, R7
    0xF0: ("MOVX",   19, 1),  # @DPTR, A
    0xF1: ("ACALL",  5, 2),
    0xF2: ("MOVX",   10, 1),  # @R0, A
    0xF3: ("MOVX",   10, 1),  # @R1, A
    0xF4: ("CPL",    12, 1),  # A
    0xF5: ("MOV",    2, 2),   # direct, A
    0xF6: ("MOV",    10, 1),  # @R0, A
    0xF7: ("MOV",    10, 1),  # @R1, A
    0xF8: ("MOV",    13, 1),  # R0, A
    0xF9: ("MOV",    13, 1),  # R1, A
    0xFA: ("MOV",    13, 1),  # R2, A
    0xFB: ("MOV",    13, 1),  # R3, A
    0xFC: ("MOV",    13, 1),  # R4, A
    0xFD: ("MOV",    13, 1),  # R5, A
    0xFE: ("MOV",    13, 1),  # R6, A
    0xFF: ("MOV",    13, 1),  # R7, A
}

# Register names for Rn (opcodes with type 13)
REG_NAMES = {
    0x08: "R0", 0x09: "R1", 0x0A: "R2", 0x0B: "R3",
    0x0C: "R4", 0x0D: "R5", 0x0E: "R6", 0x0F: "R7",
    0x18: "R0", 0x19: "R1", 0x1A: "R2", 0x1B: "R3",
    0x1C: "R4", 0x1D: "R5", 0x1E: "R6", 0x1F: "R7",
    0x28: "R0", 0x29: "R1", 0x2A: "R2", 0x2B: "R3",
    0x2C: "R4", 0x2D: "R5", 0x2E: "R6", 0x2F: "R7",
    0x38: "R0", 0x39: "R1", 0x3A: "R2", 0x3B: "R3",
    0x3C: "R4", 0x3D: "R5", 0x3E: "R6", 0x3F: "R7",
    0x48: "R0", 0x49: "R1", 0x4A: "R2", 0x4B: "R3",
    0x4C: "R4", 0x4D: "R5", 0x4E: "R6", 0x4F: "R7",
    0x58: "R0", 0x59: "R1", 0x5A: "R2", 0x5B: "R3",
    0x5C: "R4", 0x5D: "R5", 0x5E: "R6", 0x5F: "R7",
    0x68: "R0", 0x69: "R1", 0x6A: "R2", 0x6B: "R3",
    0x6C: "R4", 0x6D: "R5", 0x6E: "R6", 0x6F: "R7",
    0x78: "R0", 0x79: "R1", 0x7A: "R2", 0x7B: "R3",
    0x7C: "R4", 0x7D: "R5", 0x7E: "R6", 0x7F: "R7",
    0x88: "R0", 0x89: "R1", 0x8A: "R2", 0x8B: "R3",
    0x8C: "R4", 0x8D: "R5", 0x8E: "R6", 0x8F: "R7",
    0x98: "R0", 0x99: "R1", 0x9A: "R2", 0x9B: "R3",
    0x9C: "R4", 0x9D: "R5", 0x9E: "R6", 0x9F: "R7",
    0xA8: "R0", 0xA9: "R1", 0xAA: "R2", 0xAB: "R3",
    0xAC: "R4", 0xAD: "R5", 0xAE: "R6", 0xAF: "R7",
    0xB8: "R0", 0xB9: "R1", 0xBA: "R2", 0xBB: "R3",
    0xBC: "R4", 0xBD: "R5", 0xBE: "R6", 0xBF: "R7",
    0xC8: "R0", 0xC9: "R1", 0xCA: "R2", 0xCB: "R3",
    0xCC: "R4", 0xCD: "R5", 0xCE: "R6", 0xCF: "R7",
    0xD8: "R0", 0xD9: "R1", 0xDA: "R2", 0xDB: "R3",
    0xDC: "R4", 0xDD: "R5", 0xDE: "R6", 0xDF: "R7",
    0xE8: "R0", 0xE9: "R1", 0xEA: "R2", 0xEB: "R3",
    0xEC: "R4", 0xED: "R5", 0xEE: "R6", 0xEF: "R7",
    0xF8: "R0", 0xF9: "R1", 0xFA: "R2", 0xFB: "R3",
    0xFC: "R4", 0xFD: "R5", 0xFE: "R6", 0xFF: "R7",
}

# @Ri patterns (opcodes with type 10)
RI_NAMES = {
    0x06: "@R0", 0x07: "@R1", 0x16: "@R0", 0x17: "@R1",
    0x26: "@R0", 0x27: "@R1", 0x36: "@R0", 0x37: "@R1",
    0x46: "@R0", 0x47: "@R1", 0x56: "@R0", 0x57: "@R1",
    0x66: "@R0", 0x67: "@R1", 0x76: "@R0", 0x77: "@R1",
    0x86: "@R0", 0x87: "@R1", 0x96: "@R0", 0x97: "@R1",
    0xA6: "@R0", 0xA7: "@R1", 0xB6: "@R0", 0xB7: "@R1",
    0xC6: "@R0", 0xC7: "@R1", 0xD6: "@R0", 0xD7: "@R1",
    0xE2: "@R0", 0xE3: "@R1", 0xE6: "@R0", 0xE7: "@R1",
    0xF2: "@R0", 0xF3: "@R1", 0xF6: "@R0", 0xF7: "@R1",
}

# SFR names for common addresses
SFR_NAMES = {
    0x80: "P0", 0x81: "SP", 0x82: "DPL", 0x83: "DPH",
    0x87: "PCON", 0x88: "TCON", 0x89: "TMOD", 0x8A: "TL0",
    0x8B: "TL1", 0x8C: "TH0", 0x8D: "TH1", 0x90: "P1",
    0x98: "SCON", 0x99: "SBUF", 0xA0: "P2", 0xA8: "IE",
    0xB0: "P3", 0xB8: "IP", 0xD0: "PSW", 0xE0: "ACC",
    0xF0: "B",
    # Bit-addressable
    0x88: "TCON", 0xA8: "IE", 0xB0: "P3", 0xB8: "IP",
    0xD0: "PSW", 0xE0: "ACC",
}

# Common bit names
BIT_NAMES = {
    0xA8: "IE", 0xA9: "IE.1", 0xAA: "IE.2", 0xAB: "IE.3",
    0xAC: "IE.4", 0xAD: "IE.5", 0xAE: "IE.6", 0xAF: "IE.7",
    0xB0: "P3.0", 0xB1: "P3.1", 0xB2: "P3.2", 0xB3: "P3.3",
    0xB4: "P3.4", 0xB5: "P3.5", 0xB6: "P3.6", 0xB7: "P3.7",
    0x88: "TCON.0", 0x89: "TCON.1", 0x8A: "TCON.2", 0x8B: "TCON.3",
    0x8C: "TCON.4", 0x8D: "TCON.5", 0x8E: "TCON.6", 0x8F: "TCON.7",
    0xD0: "PSW.0", 0xD1: "PSW.1", 0xD2: "PSW.2", 0xD3: "PSW.3",
    0xD4: "PSW.4", 0xD5: "PSW.5", 0xD6: "PSW.6", 0xD7: "PSW.7",
}


def get_reg_name(opcode):
    """Get register name for register-operand opcodes"""
    return REG_NAMES.get(opcode, f"R{(opcode & 0x07)}")


def get_ri_name(opcode):
    """Get @Ri name"""
    return RI_NAMES.get(opcode, f"@R{(opcode & 0x01)}")


def get_sfr_name(addr):
    """Get SFR name if known"""
    return SFR_NAMES.get(addr, None)


def get_bit_name(bit_addr):
    """Get bit name if known"""
    # bit addressable: 0x80-0xFF maps to ports and SFRs
    byte_addr = bit_addr & 0xF8
    bit_num = bit_addr & 0x07
    if byte_addr in (0x80, 0x88, 0x90, 0x98, 0xA0, 0xA8, 0xB0, 0xB8, 0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8):
        sfr = SFR_NAMES.get(byte_addr, f"{byte_addr:02X}H")
        return f"{sfr}.{bit_num}"
    return f"{bit_addr:02X}H"


def parse_hex_line(line):
    """Parse a line of Intel HEX. Returns (address, bytes) or None."""
    line = line.strip()
    if not line.startswith(':'):
        return None
    try:
        byte_count = int(line[1:3], 16)
        address = int(line[3:7], 16)
        record_type = int(line[7:9], 16)
        if record_type == 0x01:  # EOF
            return None
        if record_type != 0x00:  # skip non-data records for now
            return None
        data_str = line[9:9 + byte_count * 2]
        data = bytes(int(data_str[i:i+2], 16) for i in range(0, len(data_str), 2))
        return (address, data)
    except Exception:
        return None


def load_hex_file(filepath):
    """Load a hex file and return a dict of address->bytes."""
    memory = {}
    with open(filepath, 'r') as f:
        for line in f:
            result = parse_hex_line(line)
            if result:
                addr, data = result
                for i, b in enumerate(data):
                    memory[addr + i] = b
    return memory


def disasm(memory, start_addr=0, max_bytes=None):
    """Disassemble 8051 code from memory dict. Returns list of (addr, bytes, asm) tuples."""
    if not memory:
        return []

    keys = sorted(memory.keys())
    min_addr = min(keys)
    max_addr = max(keys)
    if max_bytes:
        max_addr = min(max_addr, start_addr + max_bytes - 1)

    result = []
    addr = start_addr

    while addr <= max_addr:
        if addr not in memory:
            # try to find next valid address
            next_addrs = [k for k in keys if k >= addr]
            if not next_addrs:
                break
            result.append((addr, b'', f"; --- gap to {next_addrs[0]:04X}H ---"))
            addr = next_addrs[0]
            if addr > max_addr:
                break

        opcode = memory.get(addr)
        if opcode is None:
            addr += 1
            continue

        info = OPCODES.get(opcode)
        if info is None:
            result.append((addr, bytes([opcode]), f"DB {opcode:02X}H    ; UNKNOWN OPCODE"))
            addr += 1
            continue

        mnemonic, optype, length = info

        # Read operand bytes
        operand_bytes = bytearray()
        for i in range(1, length):
            if addr + i in memory:
                operand_bytes.append(memory[addr + i])
            else:
                # Incomplete instruction
                result.append((addr, bytes([opcode]), f"DB {opcode:02X}H    ; INCOMPLETE"))
                addr += 1
                break
        else:
            raw_bytes = bytes([opcode]) + bytes(operand_bytes)
            try:
                asm = format_instruction(addr, opcode, mnemonic, optype, operand_bytes)
            except IndexError as e:
                print(f"ERROR at {addr:04X}: opcode={opcode:02X} {mnemonic} optype={optype} len={length} operands={list(operand_bytes)}", file=sys.stderr)
                asm = f"DB     {opcode:02X}H    ; ERROR: {e}"
            result.append((addr, raw_bytes, asm))
            addr += length
            continue

        # if we broke out:
        continue

    return result


def format_instruction(addr, opcode, mnemonic, optype, operand_bytes):
    """Format a single 8051 instruction."""
    raw = ' '.join(f'{b:02X}' for b in bytes([opcode]) + bytes(operand_bytes))
    raw_str = f"{raw:<10}"

    op = ""

    if optype == 0:  # No operand
        op = mnemonic

    elif optype == 1:  # A, #data or direct, #data or A, #data etc
        data = operand_bytes[0]
        if opcode == 0x75:  # MOV direct, #data
            direct = operand_bytes[0]
            data2 = operand_bytes[1]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"MOV    {dir_name}, #{data2:02X}H"
        elif opcode == 0x43:  # ORL direct, #data
            direct = operand_bytes[0]
            data2 = operand_bytes[1]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"ORL    {dir_name}, #{data2:02X}H"
        elif opcode == 0x53:  # ANL direct, #data
            direct = operand_bytes[0]
            data2 = operand_bytes[1]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"ANL    {dir_name}, #{data2:02X}H"
        elif opcode == 0x63:  # XRL direct, #data
            direct = operand_bytes[0]
            data2 = operand_bytes[1]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"XRL    {dir_name}, #{data2:02X}H"
        elif opcode == 0xB4:  # CJNE A, #data, rel
            data = operand_bytes[0]
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            op = f"CJNE   A, #{data:02X}H, {target:04X}H"
        elif opcode == 0xB5:  # CJNE A, direct, rel
            direct = operand_bytes[0]
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"CJNE   A, {dir_name}, {target:04X}H"
        elif opcode in (0xB6, 0xB7):  # CJNE @Ri, #data, rel
            ri = "@R0" if opcode == 0xB6 else "@R1"
            data = operand_bytes[0]
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            op = f"CJNE   {ri}, #{data:02X}H, {target:04X}H"
        elif opcode in (0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF):  # CJNE Rn, #data, rel
            rn = f"R{opcode & 0x07}"
            data = operand_bytes[0]
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            op = f"CJNE   {rn}, #{data:02X}H, {target:04X}H"
        else:
            # Default: A, #data
            if mnemonic in ("MOV", "ADD", "ADDC", "SUBB", "ORL", "ANL", "XRL"):
                op = f"{mnemonic}   A, #{data:02X}H"
            else:
                op = f"{mnemonic}   A, #{data:02X}H"

    elif optype == 2:  # A, direct or direct, A or direct, direct etc
        if opcode in range(0x05, 0x08):  # INC direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"INC    {dir_name}"
        elif opcode in range(0x15, 0x18):  # DEC direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"DEC    {dir_name}"
        elif opcode == 0x85:  # MOV direct, direct
            src = operand_bytes[0]
            dst = operand_bytes[1]
            sfr_src = get_sfr_name(src)
            sfr_dst = get_sfr_name(dst)
            src_name = sfr_src if sfr_src else f"{src:02X}H"
            dst_name = sfr_dst if sfr_dst else f"{dst:02X}H"
            op = f"MOV    {dst_name}, {src_name}"
        elif opcode == 0xD5:  # DJNZ direct, rel
            direct = operand_bytes[0]
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"DJNZ   {dir_name}, {target:04X}H"
        elif opcode in range(0x88, 0x90):  # MOV direct, Rn
            rn = f"R{opcode & 0x07}"
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"MOV    {dir_name}, {rn}"
        elif opcode in (0x25, 0x35, 0x45, 0x55, 0x65):  # A, direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"{mnemonic}   A, {dir_name}"
        elif opcode in (0x42, 0x52, 0x62):  # direct, A
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"{mnemonic}   {dir_name}, A"
        elif opcode == 0xC5:  # XCH A, direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"XCH    A, {dir_name}"
        elif opcode in (0xE5, 0xF5):  # MOV A, direct / MOV direct, A
            if opcode == 0xE5:
                direct = operand_bytes[0]
                sfr = get_sfr_name(direct)
                dir_name = sfr if sfr else f"{direct:02X}H"
                op = f"MOV    A, {dir_name}"
            else:
                direct = operand_bytes[0]
                sfr = get_sfr_name(direct)
                dir_name = sfr if sfr else f"{direct:02X}H"
                op = f"MOV    {dir_name}, A"
        elif opcode in (0xC0, 0xD0):  # PUSH/POP direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"{mnemonic}   {dir_name}"
        else:
            direct = operand_bytes[0]
            op = f"{mnemonic}  {direct:02X}H"

    elif optype == 5:  # AJMP/ACALL addr11
        addr11 = ((opcode & 0xE0) << 3) | operand_bytes[0]
        # Calculate full address
        pc = addr + 2
        target = (pc & 0xF800) | addr11
        target = target & 0xFFFF
        op = f"{mnemonic}  {target:04X}H"

    elif optype == 6:  # LJMP/LCALL addr16
        addr16 = (operand_bytes[0] << 8) | operand_bytes[1]
        op = f"{mnemonic}  {addr16:04X}H"

    elif optype == 7:  # bit, C or C, bit or bit, rel
        bit_addr = operand_bytes[0]

        if opcode in (0x10, 0x20, 0x30):  # JBC/JB/JNB bit, rel
            rel = operand_bytes[1]
            target = (addr + 3 + rel) if rel < 0x80 else (addr + 3 + rel - 0x100)
            target = target & 0xFFFF
            bit_name = get_bit_name(bit_addr)
            op = f"{mnemonic}   {bit_name}, {target:04X}H"
        elif opcode in (0x82, 0xB0):  # ANL C, bit / ANL C, /bit
            bit_name = get_bit_name(bit_addr)
            op = f"{mnemonic}   C, {bit_name}"
        elif opcode == 0xA0:  # ORL C, /bit
            bit_name = get_bit_name(bit_addr)
            op = f"ORL    C, /{bit_name}"
        elif opcode in (0x72, 0x92):  # ORL C, bit / MOV C, bit / MOV bit, C
            bit_name = get_bit_name(bit_addr)
            if opcode == 0x72:
                op = f"ORL    C, {bit_name}"
            elif opcode == 0x92:
                op = f"MOV    {bit_name}, C"
            elif opcode == 0xA2:
                op = f"MOV    C, {bit_name}"
            else:
                op = f"{mnemonic}  {bit_name}"
        elif opcode == 0xB2:  # CPL bit
            bit_name = get_bit_name(bit_addr)
            op = f"CPL    {bit_name}"
        elif opcode in (0xC2, 0xD2):  # CLR/SETB bit
            bit_name = get_bit_name(bit_addr)
            op = f"{mnemonic} {bit_name}"
        else:
            op = f"{mnemonic}  {bit_addr:02X}H"

    elif optype == 8:  # @A+DPTR or @A+PC
        op = f"{mnemonic}  @A+DPTR" if opcode == 0x93 else f"{mnemonic}  @A+PC"

    elif optype == 9:  # DPTR, #data16 or INC DPTR
        if opcode == 0xA3:  # INC DPTR
            op = "INC    DPTR"
        elif len(operand_bytes) >= 2:
            data16 = (operand_bytes[0] << 8) | operand_bytes[1]
            op = f"MOV    DPTR, #{data16:04X}H"
        else:
            op = f"DB     {opcode:02X}H    ; MOV DPTR with incomplete operands"

    elif optype == 10:  # @Ri
        ri = get_ri_name(opcode)
        if opcode in (0x76, 0x77):  # MOV @Ri, #data
            op = f"MOV    {ri}, #{operand_bytes[0]:02X}H"
        elif opcode in (0xA6, 0xA7):  # MOV @Ri, direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"MOV    {ri}, {dir_name}"
        else:
            op = f"{mnemonic}   A, {ri}"

    elif optype == 11:  # AB (MUL/DIV)
        op = f"{mnemonic}   AB"

    elif optype == 12:  # A only
        op = f"{mnemonic}   A"

    elif optype == 13:  # Rn
        rn = get_reg_name(opcode)
        if opcode in (0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F):  # MOV Rn, #data
            op = f"MOV    {rn}, #{operand_bytes[0]:02X}H"
        elif opcode in (0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF):  # MOV Rn, direct
            direct = operand_bytes[0]
            sfr = get_sfr_name(direct)
            dir_name = sfr if sfr else f"{direct:02X}H"
            op = f"MOV    {rn}, {dir_name}"
        elif opcode in (0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF):  # DJNZ Rn, rel
            rn = f"R{opcode & 0x07}"
            rel = operand_bytes[0]
            target = (addr + 2 + rel) if rel < 0x80 else (addr + 2 + rel - 0x100)
            target = target & 0xFFFF
            op = f"DJNZ   {rn}, {target:04X}H"
        else:
            # Determine operand format based on opcode range
            if opcode in range(0x08, 0x10) or opcode in range(0x18, 0x20):
                # INC Rn / DEC Rn: just "INC R0", not "INC A, R0"
                op = f"{mnemonic}   {rn}"
            elif opcode in range(0xE8, 0xF0):
                # MOV A, Rn
                op = f"MOV    A, {rn}"
            elif opcode in range(0xF8, 0x100):
                # MOV Rn, A
                op = f"MOV    {rn}, A"
            else:
                # ADD/ADDC/SUBB/ORL/ANL/XRL/XCH A, Rn
                op = f"{mnemonic}   A, {rn}"

    elif optype == 4:  # rel (SJMP, JZ, JNZ, JC, JNC)
        rel = operand_bytes[0]
        target = (addr + 2 + rel) if rel < 0x80 else (addr + 2 + rel - 0x100)
        target = target & 0xFFFF
        op = f"{mnemonic}   {target:04X}H"

    elif optype == 16:  # MOVC A, @A+DPTR
        op = f"MOVC   A, @A+DPTR"

    elif optype == 17:  # C bit (SETB C, CLR C, MOV C, bit, CPL C)
        if opcode == 0xA2:  # MOV C, bit
            bit_addr = operand_bytes[0]
            bit_name = get_bit_name(bit_addr)
            op = f"MOV    C, {bit_name}"
        elif opcode in (0xC3, 0xD3, 0xB3):  # CLR C / SETB C / CPL C
            op = f"{mnemonic} C"
        else:
            op = mnemonic

    elif optype == 18:  # MOVX A, @DPTR
        op = f"MOVX   A, @DPTR"

    elif optype == 19:  # MOVX @DPTR, A
        op = f"MOVX   @DPTR, A"

    else:
        op = f"{mnemonic}  {operand_bytes.hex().upper()}"

    return f"{raw_str} {op}"


def main():
    if len(sys.argv) < 2:
        print("Usage: python disasm_8051.py <hex_file> [start_addr]")
        print("  e.g.: python disasm_8051.py main.hex")
        print("  e.g.: python disasm_8051.py pasted_project.hex 0x0000")
        sys.exit(1)

    filepath = sys.argv[1]
    start_addr = 0
    if len(sys.argv) >= 3:
        if sys.argv[2].startswith('0x') or sys.argv[2].startswith('0X'):
            start_addr = int(sys.argv[2], 16)
        else:
            start_addr = int(sys.argv[2])

    memory = load_hex_file(filepath)
    instructions = disasm(memory, start_addr)

    print(f"; Disassembly of {filepath}")
    print(f"; Start address: {start_addr:04X}H")
    print(f"; Total unique bytes in hex: {len(memory)}")
    print(f"; {'='*60}")
    print()

    for addr, raw, asm in instructions:
        print(f"{addr:04X}:  {asm}")

    print()
    print(f"; {'='*60}")
    print(f"; End of disassembly")


if __name__ == "__main__":
    main()
