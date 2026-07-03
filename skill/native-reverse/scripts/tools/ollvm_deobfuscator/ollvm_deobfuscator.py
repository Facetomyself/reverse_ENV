"""
OLLVM Universal Deobfuscator (ARM64)
=====================================
通用 OLLVM 反混淆工具，支持以下混淆类型的自动识别与还原：
  - 控制流平坦化 (Control Flow Flattening, CFF)
  - 间接跳转混淆 (Indirect Branch Obfuscation)
  - 间接函数调用混淆 (Indirect Call Obfuscation)
  - 虚假控制流 (Bogus Control Flow, BCF)

适配标准 OLLVM 及魔改变体（64位状态变量、寄存器预加载等）

Author: 小肩膀
WeChat: xiaojianbang8888
"""

import argparse
import struct
from collections import Counter
from capstone import *
from capstone.arm64 import *
from unicorn import *
from unicorn.arm64_const import *
from keystone import *


# =============================================================================
# ELF Loader
# =============================================================================

class ELFLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.data = open(filepath, 'rb').read()
        self.segments = []
        self._parse_elf()

    def _parse_elf(self):
        magic = self.data[:4]
        assert magic == b'\x7fELF', "Not a valid ELF file"
        ei_class = self.data[4]
        assert ei_class == 2, "Only ELF64 supported"

        e_phoff = struct.unpack_from('<Q', self.data, 0x20)[0]
        e_phentsize = struct.unpack_from('<H', self.data, 0x36)[0]
        e_phnum = struct.unpack_from('<H', self.data, 0x38)[0]

        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from('<I', self.data, off)[0]
            if p_type != 1:  # PT_LOAD
                continue
            p_flags = struct.unpack_from('<I', self.data, off + 4)[0]
            p_offset = struct.unpack_from('<Q', self.data, off + 8)[0]
            p_vaddr = struct.unpack_from('<Q', self.data, off + 16)[0]
            p_filesz = struct.unpack_from('<Q', self.data, off + 32)[0]
            p_memsz = struct.unpack_from('<Q', self.data, off + 40)[0]
            self.segments.append({
                'offset': p_offset,
                'vaddr': p_vaddr,
                'filesz': p_filesz,
                'memsz': p_memsz,
                'flags': p_flags
            })

    def vaddr_to_offset(self, vaddr):
        for seg in self.segments:
            if seg['vaddr'] <= vaddr < seg['vaddr'] + seg['memsz']:
                return seg['offset'] + (vaddr - seg['vaddr'])
        return None

    def read_at_vaddr(self, vaddr, size):
        off = self.vaddr_to_offset(vaddr)
        if off is None:
            return b'\x00' * size
        return self.data[off:off + size]

    def parse_relocations(self):
        """Parse .rela.dyn to build a map of relocated addresses -> resolved values."""
        self.relocs = {}  # vaddr -> resolved_value (load_base=0 assumed)

        # Find PT_DYNAMIC
        e_phoff = struct.unpack_from('<Q', self.data, 0x20)[0]
        e_phentsize = struct.unpack_from('<H', self.data, 0x36)[0]
        e_phnum = struct.unpack_from('<H', self.data, 0x38)[0]

        dyn_offset = None
        for i in range(e_phnum):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from('<I', self.data, off)[0]
            if p_type == 2:  # PT_DYNAMIC
                dyn_offset = struct.unpack_from('<Q', self.data, off + 8)[0]
                break

        if dyn_offset is None:
            return

        # Parse dynamic entries
        rela_off = None
        rela_sz = None
        symtab = None
        strtab = None
        i = 0
        while True:
            off = dyn_offset + i * 16
            if off + 16 > len(self.data):
                break
            d_tag = struct.unpack_from('<Q', self.data, off)[0]
            d_val = struct.unpack_from('<Q', self.data, off + 8)[0]
            if d_tag == 0:
                break
            if d_tag == 7:    # DT_RELA
                rela_off = d_val
            elif d_tag == 8:  # DT_RELASZ
                rela_sz = d_val
            elif d_tag == 6:  # DT_SYMTAB
                symtab = d_val
            elif d_tag == 5:  # DT_STRTAB
                strtab = d_val
            i += 1

        if rela_off is None or rela_sz is None:
            return

        # Parse rela entries
        num_relas = rela_sz // 24
        for i in range(num_relas):
            entry_file_off = self.vaddr_to_offset(rela_off + i * 24)
            if entry_file_off is None or entry_file_off + 24 > len(self.data):
                continue
            r_offset = struct.unpack_from('<Q', self.data, entry_file_off)[0]
            r_info = struct.unpack_from('<Q', self.data, entry_file_off + 8)[0]
            r_addend = struct.unpack_from('<q', self.data, entry_file_off + 16)[0]
            r_type = r_info & 0xFFFFFFFF

            if r_type == 0x403:  # R_AARCH64_RELATIVE
                # resolved = load_base + r_addend; with load_base=0
                self.relocs[r_offset] = r_addend & 0xFFFFFFFFFFFFFFFF

    def get_relocated_value(self, vaddr):
        """Get the post-relocation value at a given virtual address."""
        if not hasattr(self, 'relocs'):
            self.parse_relocations()
        return self.relocs.get(vaddr)

    def load_into_unicorn(self, uc):
        for seg in self.segments:
            base = seg['vaddr'] & ~0xFFF
            end = (seg['vaddr'] + seg['memsz'] + 0xFFF) & ~0xFFF
            size = end - base
            try:
                uc.mem_map(base, size, UC_PROT_ALL)
            except UcError:
                pass
            file_data = self.data[seg['offset']:seg['offset'] + seg['filesz']]
            uc.mem_write(seg['vaddr'], file_data)


# =============================================================================
# Basic Block Extraction
# =============================================================================

BRANCH_MNEMONICS = {
    'b', 'br', 'ret',
    'b.eq', 'b.ne', 'b.lt', 'b.le', 'b.gt', 'b.ge',
    'b.hi', 'b.hs', 'b.lo', 'b.ls', 'b.mi', 'b.pl',
    'b.vs', 'b.vc', 'b.al', 'b.nv',
    'cbz', 'cbnz', 'tbz', 'tbnz',
}

CSEL_MNEMONICS = {'csel', 'csinc', 'csinv', 'csneg'}


class BasicBlock:
    def __init__(self, start_addr):
        self.start_addr = start_addr
        self.end_addr = start_addr
        self.insns = []
        self.terminal_type = None       # 'b', 'b_cond', 'br', 'blr', 'bl', 'ret', 'cbz', 'tbnz'
        self.terminal_target = None     # direct target address if applicable
        self.has_csel = False
        self.csel_addr = None
        self.csel_cond = None
        self.size = 0

    def __repr__(self):
        return f"BB(0x{self.start_addr:x}-0x{self.end_addr:x}, term={self.terminal_type})"


def extract_basic_blocks(code, base_addr):
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    blocks = {}
    current = BasicBlock(base_addr)

    for insn in md.disasm(code, base_addr):
        current.insns.append(insn)
        current.end_addr = insn.address

        if insn.mnemonic in CSEL_MNEMONICS:
            current.has_csel = True
            current.csel_addr = insn.address
            ops = insn.op_str.split(', ')
            if len(ops) >= 4:
                current.csel_cond = ops[3].strip()

        if insn.mnemonic in BRANCH_MNEMONICS:
            mnem = insn.mnemonic
            if mnem == 'b':
                current.terminal_type = 'b'
                current.terminal_target = insn.operands[0].imm if insn.operands else None
            elif mnem.startswith('b.'):
                current.terminal_type = 'b_cond'
                current.terminal_target = insn.operands[0].imm if insn.operands else None
            elif mnem == 'br':
                current.terminal_type = 'br'
            elif mnem == 'blr':
                current.terminal_type = 'blr'
            elif mnem == 'ret':
                current.terminal_type = 'ret'
            elif mnem in ('cbz', 'cbnz'):
                current.terminal_type = 'cbz'
                current.terminal_target = insn.operands[1].imm if len(insn.operands) > 1 else None
            elif mnem in ('tbz', 'tbnz'):
                current.terminal_type = 'tbnz'
                current.terminal_target = insn.operands[2].imm if len(insn.operands) > 2 else None

            current.size = current.end_addr - current.start_addr + 4
            blocks[current.start_addr] = current
            next_addr = insn.address + insn.size
            current = BasicBlock(next_addr)

    if current.insns:
        current.size = current.end_addr - current.start_addr + 4
        blocks[current.start_addr] = current

    return blocks


# =============================================================================
# Obfuscation Type Detection
# =============================================================================

def detect_obfuscation_type(blocks):
    br_count = 0
    b_targets = Counter()

    for addr, block in blocks.items():
        if block.terminal_type == 'br':
            br_count += 1
        elif block.terminal_type == 'b' and block.terminal_target is not None:
            b_targets[block.terminal_target] += 1

    max_fan_in = b_targets.most_common(1)[0][1] if b_targets else 0

    if br_count >= 3:
        return "indirect_branch"
    elif max_fan_in >= 5:
        return "cff"
    else:
        return "unknown"


# =============================================================================
# CFF Deobfuscator
# =============================================================================

class CFFDeobfuscator:
    def __init__(self, elf, blocks, func_start, func_end):
        self.elf = elf
        self.blocks = blocks
        self.func_start = func_start
        self.func_end = func_end
        self.dispatcher_addr = None
        self.state_reg = None
        self.state_reg_name = None
        self.real_blocks = []
        self.dispatch_blocks = []

    def find_dispatcher(self):
        b_targets = Counter()
        for addr, block in self.blocks.items():
            if block.terminal_type == 'b' and block.terminal_target is not None:
                target = block.terminal_target
                if self.func_start <= target < self.func_end:
                    b_targets[target] += 1

        if not b_targets:
            return False
        self.dispatcher_addr = b_targets.most_common(1)[0][0]
        self.dispatcher_target = self.dispatcher_addr

        # If dispatcher target is in the middle of a block, split that block
        if self.dispatcher_addr not in self.blocks:
            for addr, block in list(self.blocks.items()):
                if addr < self.dispatcher_addr <= block.end_addr:
                    self._split_block_at(addr, self.dispatcher_addr)
                    break

        print(f"[CFF] Dispatcher found at 0x{self.dispatcher_addr:x} "
              f"(fan-in: {b_targets[self.dispatcher_addr]})")
        return True

    def _split_block_at(self, block_addr, split_addr):
        """Split a basic block at split_addr, creating two blocks."""
        block = self.blocks[block_addr]
        insns_before = []
        insns_after = []

        for insn in block.insns:
            if insn.address < split_addr:
                insns_before.append(insn)
            else:
                insns_after.append(insn)

        if not insns_before or not insns_after:
            return

        # Create the first half (ends with B to split_addr implicitly via fall-through)
        block1 = BasicBlock(block_addr)
        block1.insns = insns_before
        block1.end_addr = insns_before[-1].address
        block1.size = split_addr - block_addr
        block1.terminal_type = 'b'
        block1.terminal_target = split_addr
        # Check for CSEL in first half
        for insn in insns_before:
            if insn.mnemonic in CSEL_MNEMONICS:
                block1.has_csel = True
                block1.csel_addr = insn.address
                ops = insn.op_str.split(', ')
                if len(ops) >= 4:
                    block1.csel_cond = ops[3].strip()

        # Create the second half (inherits the original terminal)
        block2 = BasicBlock(split_addr)
        block2.insns = insns_after
        block2.end_addr = block.end_addr
        block2.size = block.end_addr - split_addr + 4
        block2.terminal_type = block.terminal_type
        block2.terminal_target = block.terminal_target
        block2.has_csel = block.has_csel
        block2.csel_addr = block.csel_addr
        block2.csel_cond = block.csel_cond
        # Re-check CSEL - it might be in first half only
        block2.has_csel = False
        for insn in insns_after:
            if insn.mnemonic in CSEL_MNEMONICS:
                block2.has_csel = True
                block2.csel_addr = insn.address
                ops = insn.op_str.split(', ')
                if len(ops) >= 4:
                    block2.csel_cond = ops[3].strip()

        # Replace in blocks dict
        del self.blocks[block_addr]
        self.blocks[block_addr] = block1
        self.blocks[split_addr] = block2

    def identify_state_variable(self):
        disp_block = self.blocks.get(self.dispatcher_addr)
        if not disp_block:
            print("[CFF] WARNING: dispatcher block not found")
            return False

        # Find state register and state source register
        # Pattern: MOV X11, X12 (state = source) then CMP X11, Xn
        self.state_src_reg_name = None
        for insn in disp_block.insns:
            # Look for MOV state, src pattern at dispatcher entry
            if insn.mnemonic == 'mov' and insn.operands:
                src = insn.reg_name(insn.operands[1].reg) if len(insn.operands) > 1 else None
                dest = insn.reg_name(insn.operands[0].reg)
                if src and dest and dest.startswith(('x', 'w')):
                    # This might be MOV state_reg, src_reg
                    # Verify by checking if dest is used in CMP later
                    for next_insn in disp_block.insns:
                        if next_insn.mnemonic == 'cmp' and next_insn.address > insn.address:
                            if next_insn.operands and insn.reg_name(next_insn.operands[0].reg) == dest:
                                self.state_reg = next_insn.operands[0].reg
                                self.state_reg_name = dest
                                self.state_src_reg_name = src
                                print(f"[CFF] State register: {self.state_reg_name}"
                                      f" (source: {self.state_src_reg_name})")
                                return True
                    break

            if insn.mnemonic == 'cmp' or insn.mnemonic == 'subs':
                if insn.operands:
                    reg = insn.operands[0].reg
                    self.state_reg = reg
                    self.state_reg_name = insn.reg_name(reg)
                    print(f"[CFF] State register: {self.state_reg_name}")
                    return True
            if insn.mnemonic == 'cmp' or insn.mnemonic == 'subs':
                if insn.operands:
                    reg = insn.operands[0].reg
                    self.state_reg = reg
                    self.state_reg_name = insn.reg_name(reg)
                    print(f"[CFF] State register: {self.state_reg_name}")
                    return True

        # If dispatcher starts with loads for comparison, look at successors
        # Try the block that the dispatcher falls into
        for addr, block in sorted(self.blocks.items()):
            if addr > self.dispatcher_addr:
                for insn in block.insns:
                    if insn.mnemonic == 'cmp' or insn.mnemonic == 'subs':
                        if insn.operands:
                            reg = insn.operands[0].reg
                            self.state_reg = reg
                            self.state_reg_name = insn.reg_name(reg)
                            print(f"[CFF] State register: {self.state_reg_name}")
                            return True
                break

        print("[CFF] WARNING: could not identify state register")
        return False

    def classify_blocks(self):
        state_reg_name = self.state_reg_name
        if not state_reg_name:
            return

        # State-related registers: both the state reg and its source (e.g. X11 and X12)
        state_regs = {state_reg_name}
        if self.state_src_reg_name:
            state_regs.add(self.state_src_reg_name)

        store_mnemonics = {'str', 'stur', 'stp', 'strb', 'strh', 'sturb', 'sturh'}
        call_mnemonics = {'bl', 'blr'}

        for addr, block in self.blocks.items():
            if addr == self.dispatcher_addr:
                self.dispatch_blocks.append(addr)
                continue

            # Check if block only assigns state register + jumps to dispatcher
            is_dispatch = True
            has_store = False
            has_call = False
            has_real_work = False
            jumps_to_dispatcher = False

            # Check terminal: must jump to dispatcher (directly or fall-through to it)
            disp_targets = {self.dispatcher_addr, self.dispatcher_target}
            if block.terminal_type == 'b' and block.terminal_target in disp_targets:
                jumps_to_dispatcher = True
            elif block.terminal_type == 'b_cond' and block.terminal_target in disp_targets:
                jumps_to_dispatcher = True

            if not jumps_to_dispatcher:
                # Check if this is part of the dispatcher comparison tree
                # These blocks: CMP + B.cond or B to dispatcher region
                is_cmp_block = False
                for insn in block.insns:
                    if insn.mnemonic in ('cmp', 'subs'):
                        # Check if comparing state register
                        if insn.operands and insn.reg_name(insn.operands[0].reg) == state_reg_name:
                            is_cmp_block = True

                if is_cmp_block and block.terminal_type in ('b_cond', 'b'):
                    self.dispatch_blocks.append(addr)
                    continue

                # Not dispatch, mark as real
                self.real_blocks.append(addr)
                continue

            # Block jumps to dispatcher - check if it does real work
            for insn in block.insns:
                if insn.mnemonic in store_mnemonics:
                    has_store = True
                    break
                if insn.mnemonic in call_mnemonics:
                    has_call = True
                    break

            if has_store or has_call:
                self.real_blocks.append(addr)
            elif block.has_csel:
                # A block with CSEL that reads from memory or compares a non-state register
                # is doing real conditional logic (not just dispatching)
                has_real_condition = False
                state_overwritten = False
                for insn in block.insns:
                    # If state reg is loaded from memory, subsequent CMP is real logic
                    if insn.mnemonic in ('ldr', 'ldur', 'ldrb', 'ldurb', 'ldp'):
                        if insn.operands:
                            dest = insn.reg_name(insn.operands[0].reg)
                            if dest == state_reg_name:
                                state_overwritten = True
                        has_real_condition = True
                        break
                    if insn.mnemonic in ('cmp', 'subs', 'tst'):
                        if insn.operands:
                            cmp_reg = insn.reg_name(insn.operands[0].reg)
                            if cmp_reg != state_reg_name or state_overwritten:
                                has_real_condition = True
                                break

                if has_real_condition:
                    self.real_blocks.append(addr)
                else:
                    self.dispatch_blocks.append(addr)
            else:
                # Block jumps to dispatcher, no store, no call, no csel
                # Check if it compares state register (= dispatcher comparison node)
                compares_state = False
                for insn in block.insns:
                    if insn.mnemonic in ('cmp', 'subs'):
                        if insn.operands and insn.reg_name(insn.operands[0].reg) == state_reg_name:
                            compares_state = True
                            break

                if compares_state:
                    # Dispatcher comparison tree node
                    self.dispatch_blocks.append(addr)
                else:
                    # No state comparison, no store, no call — pure state assignment block
                    self.dispatch_blocks.append(addr)

        # Entry block is always real
        if self.func_start not in self.real_blocks:
            self.real_blocks.append(self.func_start)
            if self.func_start in self.dispatch_blocks:
                self.dispatch_blocks.remove(self.func_start)

        self.real_blocks.sort()
        print(f"[CFF] Real blocks: {len(self.real_blocks)}, "
              f"Dispatch blocks: {len(self.dispatch_blocks)}")

    def _setup_initial_context(self, uc):
        """Execute the entry block up to the dispatcher to initialize constant registers."""
        def hook_mem(uc_inst, type, address, size, value, user_data):
            page = address & ~0xFFF
            try:
                uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
            except UcError:
                pass
            return True

        mem_hook = uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

        try:
            uc.emu_start(self.func_start, self.dispatcher_target, timeout=2000000, count=500)
        except UcError:
            pass

        uc.hook_del(mem_hook)
        return uc.context_save()

    def recover_flow_graph(self):
        uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        # Map stack
        STACK_BASE = 0x80000000
        STACK_SIZE = 0x80000
        uc.mem_map(STACK_BASE, STACK_SIZE, UC_PROT_ALL)
        # Load ELF segments
        self.elf.load_into_unicorn(uc)
        # Set SP
        uc.reg_write(UC_ARM64_REG_SP, STACK_BASE + STACK_SIZE - 0x1000)

        # Pre-execute the entry block up to the dispatcher to set up constant registers
        # (many CFF variants preload state constants into registers like X14-X17, X0-X7)
        initial_ctx = self._setup_initial_context(uc)

        flow = {}
        real_set = set(self.real_blocks)

        # Remove func_start from target real blocks
        target_real = real_set - {self.func_start}

        queue = [(self.func_start, initial_ctx)]

        while queue:
            pc, ctx = queue.pop(0)
            if pc in flow:
                continue
            flow[pc] = []

            block = self.blocks.get(pc)
            if not block:
                continue

            if block.has_csel:
                # Try both CSEL directions
                ctx_save = ctx
                for branch_dir in (0, 1):
                    if ctx_save:
                        uc.context_restore(ctx_save)
                    else:
                        uc.reg_write(UC_ARM64_REG_SP, STACK_BASE + STACK_SIZE - 0x1000)

                    target = self._emulate_path(uc, pc, target_real, branch_dir)
                    if target and target not in flow[pc]:
                        flow[pc].append(target)
                        new_ctx = uc.context_save()
                        queue.append((target, new_ctx))
            else:
                if ctx:
                    uc.context_restore(ctx)
                else:
                    uc.reg_write(UC_ARM64_REG_SP, STACK_BASE + STACK_SIZE - 0x1000)

                target = self._emulate_path(uc, pc, target_real, None)
                if target:
                    flow[pc].append(target)
                    new_ctx = uc.context_save()
                    queue.append((target, new_ctx))

        print(f"[CFF] Flow graph recovered: {len(flow)} nodes")
        return flow

    def _emulate_path(self, uc, start_addr, target_real, branch_control):
        result = {'target': None, 'insn_count': 0}
        MAX_INSNS = 10000

        def hook_code(uc_inst, address, size, user_data):
            result['insn_count'] += 1
            if result['insn_count'] > MAX_INSNS:
                uc_inst.emu_stop()
                return

            if result['target'] is not None:
                uc_inst.emu_stop()
                return

            # Reached a target real block
            if address in target_real and address != start_addr:
                result['target'] = address
                uc_inst.emu_stop()
                return

            # Disassemble current instruction
            code = uc_inst.mem_read(address, size)
            md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
            md.detail = True
            for insn in md.disasm(bytes(code), address):
                # Skip BL/BLR (function calls)
                if insn.mnemonic in ('bl', 'blr'):
                    uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                    return

                # Handle CSEL with branch control
                if insn.mnemonic in CSEL_MNEMONICS and branch_control is not None:
                    ops = insn.op_str.split(', ')
                    if len(ops) >= 3:
                        regs = [ops[0].strip(), ops[1].strip(), ops[2].strip()]
                        reg_ids = [_reg_name_to_id(r) for r in regs]
                        if all(r is not None for r in reg_ids):
                            v1 = uc_inst.reg_read(reg_ids[1])
                            v2 = uc_inst.reg_read(reg_ids[2])
                            if branch_control == 0:
                                uc_inst.reg_write(reg_ids[0], v1)
                            else:
                                uc_inst.reg_write(reg_ids[0], v2)
                            uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                            return

                # Handle RET
                if insn.mnemonic == 'ret':
                    uc_inst.emu_stop()
                    return

        hook_handle = uc.hook_add(UC_HOOK_CODE, hook_code)

        def hook_mem(uc_inst, type, address, size, value, user_data):
            # Map unmapped memory on access
            page = address & ~0xFFF
            try:
                uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
                uc_inst.mem_write(page, b'\x00' * 0x1000)
            except UcError:
                pass
            return True

        mem_hook = uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

        try:
            uc.emu_start(start_addr, self.func_end, timeout=5000000)
        except UcError as e:
            pass

        uc.hook_del(hook_handle)
        uc.hook_del(mem_hook)
        return result['target']


# =============================================================================
# Indirect Branch Deobfuscator
# =============================================================================

class IndirectBRDeobfuscator:
    def __init__(self, elf, blocks, func_start, func_end):
        self.elf = elf
        self.blocks = blocks
        self.func_start = func_start
        self.func_end = func_end
        self.br_blocks = []      # blocks ending in BR
        self.blr_blocks = []     # blocks ending in BLR
        self.uc = None
        self.prologue_ctx = None

    def find_indirect_branches(self):
        for addr, block in self.blocks.items():
            if block.terminal_type == 'br':
                self.br_blocks.append(block)
            else:
                # BLR no longer splits blocks — scan instructions within each block
                for insn in block.insns:
                    if insn.mnemonic == 'blr':
                        self.blr_blocks.append((block, insn))

        print(f"[IndBR] Found {len(self.br_blocks)} BR blocks, "
              f"{len(self.blr_blocks)} BLR instructions")

    def _setup_emulator(self):
        uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        STACK_BASE = 0x80000000
        STACK_SIZE = 0x100000
        uc.mem_map(STACK_BASE, STACK_SIZE, UC_PROT_ALL)
        self.elf.load_into_unicorn(uc)
        SP = STACK_BASE + STACK_SIZE - 0x10000
        uc.reg_write(UC_ARM64_REG_SP, SP)
        uc.reg_write(UC_ARM64_REG_X29, SP + 0x50)
        self.uc = uc

    def _find_constant_setup_range(self):
        """Find ALL blocks of MOV/MOVK/ADRP instructions that set up constants."""
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True
        code = self.elf.read_at_vaddr(self.func_start, self.func_end - self.func_start)

        setup_regions = []
        region_start = None
        consecutive_setup = 0

        for insn in md.disasm(code, self.func_start):
            if insn.mnemonic in ('mov', 'movz', 'movk', 'movn', 'adrp', 'add', 'stp'):
                if region_start is None:
                    region_start = insn.address
                consecutive_setup += 1
            elif insn.mnemonic == 'b' and consecutive_setup > 5:
                setup_regions.append((region_start, insn.address))
                region_start = None
                consecutive_setup = 0
            else:
                if consecutive_setup > 5:
                    setup_regions.append((region_start, insn.address))
                region_start = None
                consecutive_setup = 0

        return setup_regions

    def _emulate_prologue(self):
        """Emulate constant setup regions to capture register values.
        Only emulate regions that set up the main dispatch constants (typically first 2).
        Later regions may overwrite values needed by BR dispatch."""
        regions = self._find_constant_setup_range()
        if not regions:
            print("[IndBR] WARNING: Could not find constant setup block")
            return False

        # Find the largest region (main dispatch setup) and any region before it
        largest_idx = 0
        largest_size = 0
        for i, (start, end) in enumerate(regions):
            size = end - start
            if size > largest_size:
                largest_size = size
                largest_idx = i

        # Emulate all regions up to and including the largest one
        for i in range(largest_idx + 1):
            setup_start, setup_end = regions[i]
            print(f"[IndBR] Emulating constant setup: 0x{setup_start:x} - 0x{setup_end:x}")
            try:
                self.uc.emu_start(setup_start, setup_end, timeout=2000000, count=500)
            except UcError as e:
                pc = self.uc.reg_read(UC_ARM64_REG_PC)
                print(f"[IndBR]   Stopped at 0x{pc:x}: {e}")

        self.prologue_ctx = self.uc.context_save()
        return True

    def resolve_targets(self):
        self._setup_emulator()

        if not self._emulate_prologue():
            return {}

        # Pre-compute the shared cluster start for all BR blocks
        # Find the most common cluster start across all blocks
        self._shared_cluster_start = self._find_shared_cluster_start()
        if self._shared_cluster_start:
            print(f"[IndBR] Shared table base loader at 0x{self._shared_cluster_start:x}")

        resolutions = {}

        # Resolve BR targets using per-block emulation
        for block in self.br_blocks:
            targets = self._resolve_br_block(block)
            if targets:
                resolutions[block.start_addr] = {
                    'type': 'br',
                    'targets': targets,
                    'block': block
                }

        # Resolve BLR targets
        for block, blr_insn in self.blr_blocks:
            target = self._resolve_blr_insn(block, blr_insn)
            if target:
                resolutions[blr_insn.address] = {
                    'type': 'blr',
                    'targets': [target],
                    'block': block,
                    'insn_addr': blr_insn.address
                }

        print(f"[IndBR] Resolved {len(resolutions)} indirect branches")
        return resolutions

    def _find_shared_cluster_start(self):
        """Find the table base loader that precedes the densest BR cluster."""
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True
        code = self.elf.read_at_vaddr(self.func_start, self.func_end - self.func_start)

        # Collect all BR addresses
        br_addrs = []
        # Collect all LDR Xn, [Xm, #imm] followed by ADD within a few insns
        ldr_add_pairs = []

        insns_list = list(md.disasm(code, self.func_start))
        for i, insn in enumerate(insns_list):
            if insn.mnemonic == 'br':
                br_addrs.append(insn.address)
            if insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
                op_str = insn.op_str.lower()
                if op_str.startswith('x') and '[x' in op_str:
                    # Check if followed by ADD within next 4 insns
                    for j in range(i + 1, min(i + 5, len(insns_list))):
                        if insns_list[j].mnemonic == 'add':
                            ldr_add_pairs.append(insn.address)
                            break

        if not ldr_add_pairs or not br_addrs:
            return None

        # Find the LDR+ADD pair that has the most BR blocks within ±0x200
        best = None
        best_count = 0
        for ldr_addr in ldr_add_pairs:
            count = sum(1 for br in br_addrs if abs(br - ldr_addr) < 0x200)
            if count > best_count:
                best_count = count
                best = ldr_addr

        return best

    def _resolve_br_block(self, block):
        """Resolve BR target by emulating the block with prologue context."""
        br_insn = block.insns[-1]
        br_reg_name = br_insn.op_str.strip()
        br_reg_id = _reg_name_to_id(br_reg_name)
        if br_reg_id is None:
            return None

        if block.has_csel:
            targets = []
            for branch_dir in (0, 1):
                target = self._emulate_block_to_br(block, br_reg_id, branch_dir)
                if target and target not in targets:
                    targets.append(target)
            return targets if targets else None
        else:
            target = self._emulate_block_to_br(block, br_reg_id, None)
            return [target] if target else None

    def _resolve_blr_insn(self, block, blr_insn):
        """Resolve BLR target by emulating the block with prologue context.
        Falls back to relocation-based resolution if emulation fails."""
        blr_reg_name = blr_insn.op_str.strip()
        blr_reg_id = _reg_name_to_id(blr_reg_name)
        if blr_reg_id is None:
            return None

        # Try emulation first
        target = self._emulate_blr_with_context(block, blr_insn, blr_reg_id)
        if target:
            return target

        # Fallback: relocation-based resolution
        target = self._resolve_blr_via_relocs(block, blr_insn)
        if target:
            return target

        return None

    def _emulate_blr_with_context(self, block, blr_insn, blr_reg_id):
        """Emulate from block start to BLR to read target register."""
        self.uc.context_restore(self.prologue_ctx)

        cluster_start = self._find_dispatch_cluster_start(block)
        if cluster_start and cluster_start < block.start_addr:
            ctx = self._prepare_cluster_context(cluster_start, block.start_addr)
            self.uc.context_restore(ctx)
        elif cluster_start and cluster_start >= block.start_addr:
            ctx = self._prepare_cluster_context(cluster_start, cluster_start + 0x10)
            self.uc.context_restore(ctx)

        br_addr = blr_insn.address
        result = {'value': None}

        def hook_code(uc_inst, address, size, user_data):
            if address == br_addr:
                result['value'] = uc_inst.reg_read(blr_reg_id)
                uc_inst.emu_stop()
                return
            if address > br_addr:
                uc_inst.emu_stop()
                return
            code = uc_inst.mem_read(address, size)
            md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
            md.detail = True
            for insn in md.disasm(bytes(code), address):
                if insn.mnemonic in ('bl', 'blr') and address != br_addr:
                    uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                    return

        hook_handle = self.uc.hook_add(UC_HOOK_CODE, hook_code)

        def hook_mem(uc_inst, type, address, size, value, user_data):
            page = address & ~0xFFF
            try:
                uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
            except UcError:
                pass
            return True

        mem_hook = self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

        try:
            self.uc.emu_start(block.start_addr, br_addr + 4, timeout=2000000, count=200)
        except UcError:
            pass

        self.uc.hook_del(hook_handle)
        self.uc.hook_del(mem_hook)

        val = result['value']
        if val and val != 0:
            val = val & 0xFFFFFFFFFFFFFFFF
            elf_end = max(s['vaddr'] + s['memsz'] for s in self.elf.segments)
            if 0x100 <= val <= elf_end:
                return val
        return None

    def _extract_rebase_constants(self):
        """Auto-extract rebase constants from MOV Xn, #neg + MOVK Xn, #imm, LSL#16 patterns."""
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True
        code = self.elf.read_at_vaddr(self.func_start, self.func_end - self.func_start)

        mov_regs = {}  # reg -> base_value
        constants = set()

        for insn in md.disasm(code, self.func_start):
            # MOV Xn, #negative (creates 0xFFFFFFFFFFFFxxxx)
            if insn.mnemonic == 'mov' and insn.op_str.startswith('x'):
                parts = insn.op_str.split(', ')
                if len(parts) == 2 and parts[1].startswith('#'):
                    reg = parts[0]
                    try:
                        val = int(parts[1].lstrip('#'), 0)
                        if val < 0:
                            mov_regs[reg] = val & 0xFFFFFFFFFFFFFFFF
                    except ValueError:
                        pass

            # MOVK Xn, #imm, LSL#16
            elif insn.mnemonic == 'movk' and 'lsl #16' in insn.op_str.lower():
                parts = insn.op_str.split(', ')
                if len(parts) >= 2 and parts[0].startswith('x'):
                    reg = parts[0]
                    if reg in mov_regs:
                        try:
                            imm_str = parts[1].lstrip('#')
                            imm = int(imm_str, 0)
                            base_val = mov_regs[reg]
                            result = (base_val & 0xFFFFFFFF0000FFFF) | ((imm & 0xFFFF) << 16)
                            result = result & 0xFFFFFFFFFFFFFFFF
                            if result > 0xF000000000000000:
                                constants.add(result)
                        except ValueError:
                            pass

        if not constants:
            return [], []

        # Separate into offsets (used for table indexing) and rebases (used for final ADD)
        # Heuristic: group similar constants (close values are offsets, isolated ones are rebases)
        sorted_consts = sorted(constants)
        offsets = []
        rebases = []

        # Find clusters: constants within 0x100 of each other are likely offsets
        clusters = []
        current_cluster = [sorted_consts[0]]
        for i in range(1, len(sorted_consts)):
            if sorted_consts[i] - sorted_consts[i-1] < 0x100:
                current_cluster.append(sorted_consts[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [sorted_consts[i]]
        clusters.append(current_cluster)

        # Largest cluster = offsets, remaining = rebases
        clusters.sort(key=len, reverse=True)
        if clusters:
            offsets = clusters[0]
            for c in clusters[1:]:
                rebases.extend(c)

        # If only one cluster, try to identify rebase by checking which produces valid targets
        if not rebases and len(offsets) > 1:
            # The rebase is typically the most different one
            rebases = [offsets.pop(0)] if offsets[0] < offsets[1] - 0x1000 else [offsets.pop()]

        return offsets, rebases

    def _resolve_blr_via_relocs(self, block, blr_insn):
        """Resolve BLR target using relocation table.
        Statically trace the LDR chain backwards from BLR to find
        which relocated address is being loaded, then compute target."""
        self.elf.parse_relocations()
        if not self.elf.relocs:
            return None

        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True

        # Disassemble backwards from BLR within the block
        code = self.elf.read_at_vaddr(block.start_addr, blr_insn.address - block.start_addr + 4)
        insns = list(md.disasm(code, block.start_addr))

        blr_idx = None
        for i, insn in enumerate(insns):
            if insn.address == blr_insn.address:
                blr_idx = i
                break
        if blr_idx is None:
            return None

        # Find ADD Xn, Xn, Xrebase before BLR (provides rebase reg)
        add_rebase_reg = None
        for i in range(blr_idx - 1, max(blr_idx - 6, -1), -1):
            insn = insns[i]
            if insn.mnemonic == 'add':
                ops = insn.op_str.split(', ')
                if len(ops) == 3 and ops[0].startswith('x'):
                    add_rebase_reg = ops[2].strip()
                    break

        if not add_rebase_reg:
            return None

        # Find LDR Xn, [Xm, Xoffset] before the ADD (table entry load with reg offset)
        ldr_offset_reg = None
        ldr_base_reg = None
        for i in range(blr_idx - 1, max(blr_idx - 8, -1), -1):
            insn = insns[i]
            if insn.mnemonic == 'ldr' and '[' in insn.op_str:
                op_str = insn.op_str.lower()
                if op_str.startswith('x') and ', x' in op_str.split('[')[1]:
                    # LDR Xn, [Xm, Xoffset]
                    bracket = op_str.split('[')[1].rstrip(']')
                    parts = bracket.split(',')
                    if len(parts) == 2:
                        ldr_base_reg = parts[0].strip()
                        ldr_offset_reg = parts[1].strip()
                        break

        # Auto-extract rebase constants from the function
        # These are MOV Xn, #negative + MOVK Xn, #imm, LSL#16 patterns
        known_offsets, known_rebases = self._extract_rebase_constants()

        if not known_offsets:
            return None

        # Find the LDR Xn, [Xm, #imm] that loads the table pointer
        table_ptr_addr = None
        for i in range(blr_idx - 1, max(blr_idx - 12, -1), -1):
            insn = insns[i]
            if insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
                op_str = insn.op_str.lower()
                if op_str.startswith('x') and '[x' in op_str:
                    bracket = op_str.split('[')[1].rstrip(']')
                    parts = bracket.split(',')
                    if len(parts) == 2 and '#' in parts[1]:
                        imm_str = parts[1].strip().lstrip('#')
                        try:
                            imm = int(imm_str, 16)
                        except ValueError:
                            continue
                        # Try all LOAD segment pages + common ADRP targets
                        candidates = set()
                        for seg in self.elf.segments:
                            # Add all possible page bases within the segment
                            seg_start_page = seg['vaddr'] & ~0xFFF
                            seg_end_page = (seg['vaddr'] + seg['memsz']) & ~0xFFF
                            for page in range(seg_start_page, seg_end_page + 0x1000, 0x1000):
                                candidates.add(page + imm)

                        # Pick the candidate that has a relocation-reachable value
                        for candidate in sorted(candidates):
                            raw = self.elf.read_at_vaddr(candidate, 8)
                            if raw == b'\x00' * 8:
                                continue
                            raw_val = struct.unpack_from('<Q', raw, 0)[0]
                            # Check if raw_val + any known offset leads to a reloc
                            for offset in known_offsets:
                                eff = (raw_val + offset) & 0xFFFFFFFFFFFFFFFF
                                if self.elf.get_relocated_value(eff) is not None:
                                    table_ptr_addr = candidate
                                    break
                            if table_ptr_addr:
                                break
                        break

        if not table_ptr_addr:
            return None

        # Read the pre-relocation table pointer value
        table_ptr_raw = struct.unpack_from('<Q',
            self.elf.read_at_vaddr(table_ptr_addr, 8), 0)[0]

        # The offset register contains a signed value like -0x5B4 extended to 64-bit
        # These are MOV+MOVK patterns loaded in the prologue
        # Try all known offsets and check which produces a relocated address
        for offset in known_offsets:
            effective_addr = (table_ptr_raw + offset) & 0xFFFFFFFFFFFFFFFF
            reloc_val = self.elf.get_relocated_value(effective_addr)
            if reloc_val is not None:
                for rebase in known_rebases:
                    target = (reloc_val + rebase) & 0xFFFFFFFFFFFFFFFF
                    elf_end = max(s['vaddr'] + s['memsz'] for s in self.elf.segments)
                    if 0x100 <= target <= elf_end:
                        # Validate: check if ldr_offset_reg matches this offset
                        # by checking what MOV/MOVK set it to
                        return target

        return None

    def _find_dispatch_cluster_start(self, block):
        """Find the start of a dispatch cluster (where shared registers like X11 are loaded)."""
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True

        # First try: search backwards from block start
        search_start = max(self.func_start, block.start_addr - 0x100)
        code = self.elf.read_at_vaddr(search_start, block.start_addr - search_start + 4)

        best_ldr_addr = None
        for insn in md.disasm(code, search_start):
            if insn.address >= block.start_addr:
                break
            if insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
                op_str = insn.op_str.lower()
                if op_str.startswith('x') and '[x' in op_str:
                    best_ldr_addr = insn.address

        # Validate: must be followed by ADD within a few insns (table base pattern)
        if best_ldr_addr:
            check_code = self.elf.read_at_vaddr(best_ldr_addr, 0x14)
            for insn in md.disasm(check_code, best_ldr_addr):
                if insn.mnemonic == 'add' and insn.address > best_ldr_addr:
                    return best_ldr_addr
            # Not validated — fall through to shared

        # Fallback: use the shared cluster start (pre-computed)
        return getattr(self, '_shared_cluster_start', None)

    def _prepare_cluster_context(self, cluster_start, block_start):
        """Pre-emulate from cluster_start to set up shared registers (e.g. X11).
        The pattern is: LDR X11, [X3, #imm] ... ADD X11, X11, X21
        These may be interleaved with CMP/CSEL for other purposes.
        Strategy: run from cluster_start, skip anything that isn't LDR/ADD/MOV setup,
        stop at the first LDR that uses the loaded register as a base (table entry load)."""
        self.uc.context_restore(self.prologue_ctx)

        # We need to find the first 'LDR Xn, [Xn, Xm]' pattern (table entry load)
        # and stop BEFORE it. Everything before that is table base setup.
        md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        md.detail = True
        code = self.elf.read_at_vaddr(cluster_start, 0x20)

        stop_addr = cluster_start + 0x10  # default: run a few insns
        found_base_ldr = False
        for insn in md.disasm(code, cluster_start):
            # LDR Xn, [Xm, #imm] - this is loading from GOT/data = table pointer load
            if insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
                found_base_ldr = True
                continue
            # ADD Xn, Xn, Xm after the base LDR = rebasing the table pointer
            if insn.mnemonic == 'add' and found_base_ldr:
                stop_addr = insn.address + insn.size
                break
            # If we hit CMP after the base LDR but before ADD, include the ADD
            if insn.mnemonic == 'cmp' and found_base_ldr:
                continue
            # If we hit something else after finding the LDR, keep looking for ADD
            if found_base_ldr:
                continue

        def hook_mem(uc_inst, type, address, size, value, user_data):
            page = address & ~0xFFF
            try:
                uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
            except UcError:
                pass
            return True

        mem_hook = self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

        try:
            self.uc.emu_start(cluster_start, stop_addr, timeout=2000000, count=20)
        except UcError:
            pass

        self.uc.hook_del(mem_hook)
        return self.uc.context_save()

    def _emulate_block_to_br(self, block, target_reg_id, branch_control, is_blr=False):
        """Emulate from the dispatch cluster start through the block to the BR/BLR."""
        br_addr = block.end_addr
        result = {'value': None}

        # Find the cluster start (where X11/table is loaded)
        cluster_start = self._find_dispatch_cluster_start(block)

        if cluster_start and cluster_start < block.start_addr:
            # Normal case: cluster setup is before the block
            ctx = self._prepare_cluster_context(cluster_start, block.start_addr)
            self.uc.context_restore(ctx)
        elif cluster_start and cluster_start >= block.start_addr:
            # Special case: cluster setup is AFTER the block (block is a BR target)
            # Run the cluster setup first, then jump to the block
            ctx = self._prepare_cluster_context(cluster_start, cluster_start + 0x10)
            self.uc.context_restore(ctx)
        else:
            self.uc.context_restore(self.prologue_ctx)

        def hook_code(uc_inst, address, size, user_data):
            if address == br_addr:
                result['value'] = uc_inst.reg_read(target_reg_id)
                uc_inst.emu_stop()
                return

            if address > br_addr:
                uc_inst.emu_stop()
                return

            code = uc_inst.mem_read(address, size)
            md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
            md.detail = True
            for insn in md.disasm(bytes(code), address):
                if insn.mnemonic in ('bl', 'blr') and address != br_addr:
                    uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                    return

                if insn.mnemonic == 'br' and address != br_addr:
                    uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                    return

                if insn.mnemonic in CSEL_MNEMONICS and branch_control is not None:
                    if block.csel_addr and address == block.csel_addr:
                        ops = insn.op_str.split(', ')
                        if len(ops) >= 3:
                            regs = [ops[0].strip(), ops[1].strip(), ops[2].strip()]
                            reg_ids = [_reg_name_to_id(r) for r in regs]
                            if all(r is not None for r in reg_ids):
                                v1 = uc_inst.reg_read(reg_ids[1])
                                v2 = uc_inst.reg_read(reg_ids[2])
                                if branch_control == 0:
                                    uc_inst.reg_write(reg_ids[0], v1)
                                else:
                                    uc_inst.reg_write(reg_ids[0], v2)
                                uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                                return

        hook_handle = self.uc.hook_add(UC_HOOK_CODE, hook_code)

        def hook_mem(uc_inst, type, address, size, value, user_data):
            page = address & ~0xFFF
            try:
                uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
            except UcError:
                pass
            return True

        mem_hook = self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

        try:
            self.uc.emu_start(block.start_addr, br_addr + 4, timeout=2000000, count=200)
        except UcError:
            pass

        self.uc.hook_del(hook_handle)
        self.uc.hook_del(mem_hook)

        val = result['value']
        if val and val != 0:
            val = val & 0xFFFFFFFFFFFFFFFF
            if is_blr:
                # BLR targets should be valid code addresses within the SO
                # Reject values that are clearly pre-relocation (too large)
                # or too small (likely 0 or near-zero from failed computation)
                elf_end = max(s['vaddr'] + s['memsz'] for s in self.elf.segments)
                if 0x100 <= val <= elf_end:
                    return val
            else:
                # BR targets should be within or near the function
                if self.func_start <= val <= self.func_end + 0x1000:
                    return val
        return None


# =============================================================================
# Patch Generator
# =============================================================================

class PatchGenerator:
    def __init__(self, elf_data):
        self.data = bytearray(elf_data)
        self.ks = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
        self.patches_applied = 0

    def patch_branch(self, elf, patch_addr, target_addr):
        offset = self._vaddr_to_offset(elf, patch_addr)
        if offset is None:
            return False
        try:
            encoding, _ = self.ks.asm(f"b #0x{target_addr:x}", patch_addr)
            self.data[offset:offset + 4] = bytes(encoding)
            self.patches_applied += 1
            return True
        except KsError as e:
            print(f"  [WARN] Failed to patch B at 0x{patch_addr:x}: {e}")
            return False

    def patch_cond_branch(self, elf, patch_addr, true_target, false_target, cond):
        offset = self._vaddr_to_offset(elf, patch_addr)
        if offset is None:
            return False
        try:
            asm_str = f"b.{cond} #0x{true_target:x}; b #0x{false_target:x}"
            encoding, _ = self.ks.asm(asm_str, patch_addr)
            self.data[offset:offset + 8] = bytes(encoding)
            self.patches_applied += 1
            return True
        except KsError as e:
            print(f"  [WARN] Failed to patch B.cond at 0x{patch_addr:x}: {e}")
            return False

    def patch_bl(self, elf, patch_addr, target_addr):
        offset = self._vaddr_to_offset(elf, patch_addr)
        if offset is None:
            return False
        try:
            encoding, _ = self.ks.asm(f"bl #0x{target_addr:x}", patch_addr)
            self.data[offset:offset + 4] = bytes(encoding)
            self.patches_applied += 1
            return True
        except KsError as e:
            print(f"  [WARN] Failed to patch BL at 0x{patch_addr:x}: {e}")
            return False

    def nop_range(self, elf, start_addr, size):
        offset = self._vaddr_to_offset(elf, start_addr)
        if offset is None:
            return
        nop = b'\x1f\x20\x03\xd5'  # NOP encoding
        for i in range(0, size, 4):
            self.data[offset + i:offset + i + 4] = nop

    def _vaddr_to_offset(self, elf, vaddr):
        return elf.vaddr_to_offset(vaddr)

    def save(self, output_path):
        with open(output_path, 'wb') as f:
            f.write(self.data)
        print(f"[PATCH] Saved to {output_path} ({self.patches_applied} patches applied)")


# =============================================================================
# Utility Functions
# =============================================================================

_REG_MAP = {}

def _build_reg_map():
    global _REG_MAP
    if _REG_MAP:
        return
    import unicorn.arm64_const as _arm64
    for i in range(31):
        _REG_MAP[f'x{i}'] = getattr(_arm64, f'UC_ARM64_REG_X{i}')
        _REG_MAP[f'w{i}'] = getattr(_arm64, f'UC_ARM64_REG_W{i}')
    _REG_MAP['xzr'] = UC_ARM64_REG_XZR
    _REG_MAP['wzr'] = UC_ARM64_REG_WZR
    _REG_MAP['sp'] = UC_ARM64_REG_SP

_build_reg_map()


def _reg_name_to_id(name):
    name = name.lower().strip()
    return _REG_MAP.get(name)


# =============================================================================
# Main Orchestration
# =============================================================================

def process_cff(elf, blocks, func_start, func_end, patcher):
    deob = CFFDeobfuscator(elf, blocks, func_start, func_end)

    if not deob.find_dispatcher():
        print("[CFF] ERROR: Could not find dispatcher")
        return False

    if not deob.identify_state_variable():
        print("[CFF] ERROR: Could not identify state variable")
        return False

    deob.classify_blocks()
    flow = deob.recover_flow_graph()

    if not flow:
        print("[CFF] ERROR: Flow graph is empty")
        return False

    # Eliminate bogus control flow (opaque predicates)
    flow = eliminate_bogus_flow(elf, blocks, flow, func_start, func_end)

    # Apply patches
    print("\n[CFF] Applying patches...")
    for block_addr, targets in flow.items():
        if not targets or targets == [None]:
            continue

        block = blocks.get(block_addr)
        if not block:
            continue

        if len(targets) == 1 and targets[0] is not None:
            # Single successor: patch last instruction to B target
            patch_addr = block.end_addr
            patcher.patch_branch(elf, patch_addr, targets[0])
            print(f"  0x{block_addr:x} -> B 0x{targets[0]:x}")

        elif len(targets) == 2 and block.has_csel and block.csel_cond:
            # Two successors: patch at CSEL with B.cond + B
            patch_addr = block.csel_addr
            patcher.patch_cond_branch(elf, patch_addr, targets[0], targets[1], block.csel_cond)
            print(f"  0x{block_addr:x} -> B.{block.csel_cond} 0x{targets[0]:x}, "
                  f"B 0x{targets[1]:x}")

    # NOP everything that is NOT a real block in the flow graph
    real_addrs = set(flow.keys())
    for addr in deob.real_blocks:
        real_addrs.add(addr)

    for addr, block in sorted(blocks.items()):
        if addr not in real_addrs:
            patcher.nop_range(elf, addr, block.size)

    return True


def eliminate_bogus_flow(elf, blocks, flow, func_start, func_end):
    """Eliminate bogus control flow by testing CSEL blocks with multiple random values.
    If a CSEL always takes the same direction regardless of input, it's an opaque predicate."""
    import struct

    csel_blocks = [(addr, targets) for addr, targets in flow.items()
                   if len(targets) == 2 and blocks.get(addr) and blocks[addr].has_csel]

    if not csel_blocks:
        return flow

    # Check if function has opaque predicate pattern (loads from globals + mul)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True

    # Find registers that hold pointers to globals (loaded via ADRP+LDR in prologue)
    # Pattern: ADRP Xn, #page; LDR Xn, [Xn, #offset]
    global_ptr_regs = set()
    adrp_regs = set()
    prologue_code = elf.read_at_vaddr(func_start, min(0x60, func_end - func_start))
    for insn in md.disasm(prologue_code, func_start):
        if insn.mnemonic == 'adrp':
            reg = insn.op_str.split(',')[0].strip()
            adrp_regs.add(reg)
        elif insn.mnemonic == 'ldr' and '#0x' in insn.op_str:
            reg = insn.op_str.split(',')[0].strip()
            if reg in adrp_regs and reg.startswith('x'):
                global_ptr_regs.add(reg)

    if not global_ptr_regs:
        return flow

    # For each CSEL block, test with multiple values
    FAKE_MEM = 0x70000000
    TEST_VALUES = [0, 1, 2, 5, 7, 9, 10, 15, 42, 100, 255, 1000, 0x7FFFFFFF]
    eliminated = 0

    for block_addr, targets in csel_blocks:
        block = blocks[block_addr]

        # Check if this block reads from global pointer registers (opaque predicate indicator)
        has_global_read = False
        for insn in block.insns:
            if insn.mnemonic in ('ldr', 'ldrb'):
                for reg in global_ptr_regs:
                    if reg in insn.op_str:
                        has_global_read = True
                        break
            if has_global_read:
                break

        if not has_global_read:
            continue  # Not an opaque predicate block, skip

        # Multi-simulation: test with different global values
        direction_counts = {0: 0, 1: 0}

        for val1 in TEST_VALUES:
            for val2 in TEST_VALUES[:7]:  # Fewer combinations for speed
                uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
                try:
                    uc.mem_map(0x70000000, 0x10000, UC_PROT_ALL)
                    uc.mem_map(0x80000000, 0x80000, UC_PROT_ALL)
                    elf.load_into_unicorn(uc)
                    uc.reg_write(UC_ARM64_REG_SP, 0x80070000)
                except UcError:
                    continue

                # Set global pointer registers to fake memory with test values
                offset = 0
                for reg in sorted(global_ptr_regs):
                    reg_id = _reg_name_to_id(reg)
                    if reg_id:
                        ptr_addr = FAKE_MEM + offset
                        uc.reg_write(reg_id, ptr_addr)
                        # Write test value at the pointed location
                        test_val = val1 if offset == 0 else val2
                        uc.mem_write(ptr_addr, struct.pack('<I', test_val & 0xFFFFFFFF))
                    offset += 0x1000

                # Emulate to CSEL and read NZCV
                csel_direction = {'dir': None}

                def hook_code(uc_inst, address, size, user_data):
                    if address == block.csel_addr:
                        nzcv = uc_inst.reg_read(UC_ARM64_REG_NZCV)
                        z_flag = (nzcv >> 30) & 1
                        # Decode condition
                        cond = block.csel_cond
                        if cond == 'ne':
                            csel_direction['dir'] = 0 if z_flag == 0 else 1
                        elif cond == 'eq':
                            csel_direction['dir'] = 0 if z_flag == 1 else 1
                        elif cond == 'lt':
                            n_flag = (nzcv >> 31) & 1
                            v_flag = (nzcv >> 28) & 1
                            csel_direction['dir'] = 0 if n_flag != v_flag else 1
                        elif cond == 'ge':
                            n_flag = (nzcv >> 31) & 1
                            v_flag = (nzcv >> 28) & 1
                            csel_direction['dir'] = 0 if n_flag == v_flag else 1
                        elif cond == 'gt':
                            n_flag = (nzcv >> 31) & 1
                            v_flag = (nzcv >> 28) & 1
                            csel_direction['dir'] = 0 if z_flag == 0 and n_flag == v_flag else 1
                        elif cond == 'le':
                            n_flag = (nzcv >> 31) & 1
                            v_flag = (nzcv >> 28) & 1
                            csel_direction['dir'] = 0 if z_flag == 1 or n_flag != v_flag else 1
                        else:
                            csel_direction['dir'] = 0  # default
                        uc_inst.emu_stop()
                        return

                    if address > block.csel_addr:
                        uc_inst.emu_stop()
                        return

                    # Skip BL/BLR calls to avoid crashing on external functions
                    insn_code = uc_inst.mem_read(address, 4)
                    for insn in md.disasm(bytes(insn_code), address):
                        if insn.mnemonic in ('bl', 'blr'):
                            uc_inst.reg_write(UC_ARM64_REG_PC, address + 4)
                            return

                hook_handle = uc.hook_add(UC_HOOK_CODE, hook_code)

                def hook_mem(uc_inst, type, address, size, value, user_data):
                    page = address & ~0xFFF
                    try:
                        uc_inst.mem_map(page, 0x1000, UC_PROT_ALL)
                    except UcError:
                        pass
                    return True

                mem_hook = uc.hook_add(UC_HOOK_MEM_UNMAPPED, hook_mem)

                try:
                    uc.emu_start(block_addr, block.csel_addr + 4, timeout=1000000, count=150)
                except UcError:
                    pass

                uc.hook_del(hook_handle)
                uc.hook_del(mem_hook)

                if csel_direction['dir'] is not None:
                    direction_counts[csel_direction['dir']] += 1

        # Determine if opaque
        total = direction_counts[0] + direction_counts[1]
        if total > 0:
            if direction_counts[0] > 0 and direction_counts[1] == 0:
                # Always direction 0 -> target[1] is bogus
                flow[block_addr] = [targets[0]]
                eliminated += 1
            elif direction_counts[1] > 0 and direction_counts[0] == 0:
                # Always direction 1 -> target[0] is bogus
                flow[block_addr] = [targets[1]]
                eliminated += 1

    if eliminated > 0:
        print(f"[BCF] Eliminated {eliminated} bogus branches (opaque predicates)")

    return flow


def process_indirect_branch(elf, blocks, func_start, func_end, patcher):
    deob = IndirectBRDeobfuscator(elf, blocks, func_start, func_end)
    deob.find_indirect_branches()

    resolutions = deob.resolve_targets()

    if not resolutions:
        print("[IndBR] ERROR: Could not resolve any targets")
        return False

    # Apply patches
    print("\n[IndBR] Applying patches...")
    for block_addr, info in resolutions.items():
        block = info['block']
        targets = info['targets']

        if info['type'] == 'br':
            if len(targets) == 1 and targets[0] is not None:
                # Single BR target
                patch_addr = block.end_addr
                patcher.patch_branch(elf, patch_addr, targets[0])
                print(f"  BR at 0x{block.end_addr:x} -> B 0x{targets[0]:x}")

            elif len(targets) == 2 and block.has_csel and block.csel_cond:
                # Conditional BR
                patch_addr = block.csel_addr
                patcher.patch_cond_branch(elf, patch_addr, targets[0], targets[1],
                                          block.csel_cond)
                print(f"  BR at 0x{block.end_addr:x} -> B.{block.csel_cond} "
                      f"0x{targets[0]:x}, B 0x{targets[1]:x}")

        elif info['type'] == 'blr':
            if targets and targets[0] is not None:
                patch_addr = info.get('insn_addr', block.end_addr)
                patcher.patch_bl(elf, patch_addr, targets[0])
                print(f"  BLR at 0x{patch_addr:x} -> BL 0x{targets[0]:x}")

    return True


# =============================================================================
# Auto-detection and Recursive Processing
# =============================================================================

def find_function_end(elf, func_start, max_size=0x10000):
    """Find function end by looking for RET instruction matching the prologue."""
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    code = elf.read_at_vaddr(func_start, min(max_size, 0x10000))

    # Check if this is a PLT stub (ADRP+LDR+ADD+BR or ADRP+LDR+BR, ~12-16 bytes)
    first_insns = list(md.disasm(code[:20], func_start))
    if len(first_insns) >= 3:
        if first_insns[0].mnemonic == 'adrp':
            for insn in first_insns[1:5]:
                if insn.mnemonic == 'br':
                    return insn.address + 4

    # For normal functions: find RET
    # Track prologue STP count to match with epilogue LDP+RET
    prologue_stps = 0
    for insn in md.disasm(code[:0x30], func_start):
        if insn.mnemonic == 'stp':
            prologue_stps += 1
        elif insn.mnemonic not in ('mov', 'add', 'sub', 'mrs', 'stp'):
            break

    # Find the first RET that follows an LDP sequence of similar length
    if prologue_stps > 0:
        ldp_count = 0
        for insn in md.disasm(code, func_start):
            if insn.mnemonic == 'ldp':
                ldp_count += 1
            elif insn.mnemonic == 'ret' and ldp_count >= prologue_stps - 1:
                return insn.address + 4
            elif insn.mnemonic in ('stp',) and insn.address > func_start + 0x10:
                # Hit another prologue — this function doesn't have a normal epilogue
                ldp_count = 0
    else:
        # No STP prologue — look for first RET
        for insn in md.disasm(code, func_start):
            if insn.mnemonic == 'ret':
                return insn.address + 4

    # Fallback: return a reasonable size
    return func_start + min(0x1000, max_size)


def analyze_function(elf, func_start, func_end):
    """Analyze a function and return its obfuscation type."""
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    code = elf.read_at_vaddr(func_start, func_end - func_start)

    from collections import Counter
    b_targets = Counter()
    br_count = 0

    # Check first few instructions for PLT pattern
    first_insns = list(md.disasm(code[:16], func_start))
    if len(first_insns) >= 3:
        if first_insns[0].mnemonic == 'adrp' and any(i.mnemonic == 'br' for i in first_insns[:4]):
            return 'plt'
    # Also catch SUB SP functions that are too small to be obfuscated
    if func_end - func_start < 0x40:
        return 'clean'

    for insn in md.disasm(code, func_start):
        if insn.mnemonic == 'b' and insn.operands:
            target = insn.operands[0].imm
            if func_start <= target < func_end:
                b_targets[target] += 1
        if insn.mnemonic == 'br':
            br_count += 1

    max_fan = b_targets.most_common(1)[0][1] if b_targets else 0

    if max_fan >= 5:
        return 'cff'
    elif br_count >= 3 and max_fan < 3:
        return 'indirect_branch'
    else:
        return 'clean'


def find_callees(elf, func_start, func_end):
    """Find all BL targets within a function."""
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    code = elf.read_at_vaddr(func_start, func_end - func_start)

    callees = set()
    for insn in md.disasm(code, func_start):
        if insn.mnemonic == 'bl' and insn.operands:
            target = insn.operands[0].imm
            if target > 0 and target != func_start:
                callees.add(target)
    return sorted(callees)


def scan_all_functions(elf):
    """Scan the ELF for all function start addresses."""
    functions = []
    code_seg = elf.segments[0]
    data = elf.read_at_vaddr(code_seg['vaddr'], code_seg['filesz'])

    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True

    seg_start = code_seg['vaddr']
    seg_size = code_seg['filesz']

    for offset in range(0, seg_size - 8, 4):
        addr = seg_start + offset

        # Pattern 1: STP x, x, [sp, #-N]! (pre-index writeback)
        if data[offset + 3] == 0xA9 and (data[offset + 2] & 0x80) != 0:
            insn_bytes = data[offset:offset + 4]
            for insn in md.disasm(insn_bytes, addr):
                if insn.mnemonic == 'stp' and '[sp, #-' in insn.op_str and '!' in insn.op_str:
                    functions.append(addr)

        # Pattern 2: SUB SP, SP, #imm (frame allocation) followed by STP
        elif data[offset + 3] == 0xD1 and data[offset] == 0xFF:
            # Check if this is SUB SP, SP, #imm
            insn_bytes = data[offset:offset + 4]
            for insn in md.disasm(insn_bytes, addr):
                if insn.mnemonic == 'sub' and insn.op_str.startswith('sp, sp, #'):
                    # Verify next instruction is STP
                    next_bytes = data[offset + 4:offset + 8]
                    for next_insn in md.disasm(next_bytes, addr + 4):
                        if next_insn.mnemonic == 'stp':
                            functions.append(addr)

    return functions


def process_all(elf, patcher):
    """Scan all functions in the SO, detect obfuscation, and process each."""
    # Find all functions
    functions = scan_all_functions(elf)
    print(f"[*] Found {len(functions)} potential function prologues")

    # Compute function boundaries and remove overlaps
    func_ranges = []
    for func_start in functions:
        func_end = find_function_end(elf, func_start)
        if func_end - func_start >= 0x20:
            func_ranges.append((func_start, func_end))

    # Sort by start address and remove functions that overlap with a previous one
    func_ranges.sort()
    filtered = []
    for start, end in func_ranges:
        if filtered and start < filtered[-1][1]:
            continue  # skip: overlaps with previous function
        filtered.append((start, end))

    print(f"[*] After dedup: {len(filtered)} functions")

    processed = 0
    skipped = 0
    failed = 0

    for i, (func_start, func_end) in enumerate(filtered):
        ob_type = analyze_function(elf, func_start, func_end)
        if ob_type in ('clean', 'plt'):
            skipped += 1
            continue

        print(f"\n[{processed+1}] Function 0x{func_start:x} - 0x{func_end:x} (type: {ob_type})")

        code = elf.read_at_vaddr(func_start, func_end - func_start)
        blocks = extract_basic_blocks(code, func_start)

        success = False
        if ob_type == 'cff':
            success = process_cff(elf, blocks, func_start, func_end, patcher)
        elif ob_type == 'indirect_branch':
            success = process_indirect_branch(elf, blocks, func_start, func_end, patcher)

        if success:
            processed += 1
        else:
            failed += 1

    print(f"\n[*] Summary: {processed} processed, {skipped} clean/plt skipped, {failed} failed")


def main():
    parser = argparse.ArgumentParser(
        description='OLLVM Universal Deobfuscator (ARM64)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python deobfuscator.py libmsaoaidsec.so 0x14400 0x14898\n"
               "  python deobfuscator.py lib52pojie.so 0xd5cc 0xdbc8 --type indirect\n"
    )
    parser.add_argument('input', help='Input .so file path')
    parser.add_argument('start', help='Function start address (hex)',
                        type=lambda x: int(x, 16))
    parser.add_argument('end', help='Function end address (hex)',
                        type=lambda x: int(x, 16))
    parser.add_argument('-o', '--output', help='Output file path (default: input.patched.so)')
    parser.add_argument('--type', choices=['auto', 'cff', 'indirect'], default='auto',
                        help='Obfuscation type (default: auto-detect)')

    args = parser.parse_args()

    if not args.output:
        args.output = args.input.replace('.so', '.patched.so')

    print(f"[*] Input:  {args.input}")
    print(f"[*] Range:  0x{args.start:x} - 0x{args.end:x}")
    print(f"[*] Output: {args.output}")
    print()

    # Load ELF
    elf = ELFLoader(args.input)
    print(f"[*] Loaded ELF with {len(elf.segments)} LOAD segments")

    # Create patcher
    patcher = PatchGenerator(elf.data)

    # Read function code
    func_size = args.end - args.start
    code = elf.read_at_vaddr(args.start, func_size)

    # Extract basic blocks
    blocks = extract_basic_blocks(code, args.start)
    print(f"[*] Extracted {len(blocks)} basic blocks")

    # Detect obfuscation type
    if args.type == 'auto':
        ob_type = detect_obfuscation_type(blocks)
        print(f"[*] Detected obfuscation type: {ob_type}")
    else:
        ob_type = args.type
        print(f"[*] Using specified type: {ob_type}")

    # Process
    if ob_type == 'cff':
        success = process_cff(elf, blocks, args.start, args.end, patcher)
    elif ob_type == 'indirect' or ob_type == 'indirect_branch':
        success = process_indirect_branch(elf, blocks, args.start, args.end, patcher)
    else:
        print(f"[*] ERROR: Unknown obfuscation type '{ob_type}'")
        return

    if success:
        patcher.save(args.output)
        print("\n[*] Done!")
    else:
        print("\n[*] Deobfuscation failed.")


if __name__ == '__main__':
    main()
