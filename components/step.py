from components.utils import *
from components.contract import BytecodeContract
from components.memory import Memory
from components.instruction import Ins
from components.breakpoint import Breakpoint
from components.jump import Jump


class Step():
    def __init__(self, cur: int, log, contract: BytecodeContract, calldata: str, last_step=None) -> None:
        self.pc = log["pc"]
        self.depth = log['depth']
        self.gas = log['gas']
        self.gasCost = log['gasCost']
        self.storage = log['storage']
        self.stack = log['stack']
        self.op = log['op']
        self.log = log
        self.cur = cur
        self.ins: Ins = contract.ins_at(self.pc)

        if last_step:
            self.memory = last_step.memory.copy()
            self.update_memory(contract, calldata, last_step)
            self.jumps = copy.copy(last_step.jumps)
            self.update_jump(last_step)
        else:
            self.memory = Memory()
            self.jumps = []
        assert self.op in self.ins.opcode, f"{self.ins} {self.op} {self.pc}"

    def print_jump(self):
        print("Jump:\n", end='')
        for j in self.jumps:
            print(
                f"  from: {j.src_cur} pc = {j.src_ins.addr} = {hex(j.src_ins.addr)}  ->", end='')
            print(
                f"  to: {j.dst_cur} pc = {j.dst_ins.addr} = {hex(j.dst_ins.addr)}", end='')
            print(f"  {C.OKCYAN}{j.src_ins.short_str()}{C.ENDC}", end='')
            print(f"  stack: [{', '.join(short_stack(j.stack))}]")
        print()

    def update_jump(self, last):
        if last.op == 'JUMP':
            pass
        elif last.op == 'JUMPI':
            dst = int(last.stack[-1], 16)
            if dst != self.pc:
                return
        else:
            return
        jump = Jump(last.cur, last.ins, self.ins, last.stack)
        self.jumps.append(jump)

    def update_memory(self, contract: BytecodeContract, calldata: str, last):
        if last.op == 'MSTORE':
            assert len(
                last.stack) >= 2, f"{last.op} Stack under flow: {last.stack}"
            offset = int(last.stack[-1], 16)
            value = last.stack[-2]
            self.memory.set(offset, 0x20, value)
        elif last.op == 'MSTORE8':
            assert len(
                last.stack) >= 2, f"{last.op} Stack under flow: {last.stack}"
            offset = int(last.stack[-1], 16)
            value = last.stack[-2][-2:]
            self.memory.set(offset, 0x1, value)
        elif last.op == 'CALLDATACOPY':
            assert len(
                last.stack) >= 3, f"{last.op} Stack under flow: {last.stack}"
            destoffset = int(last.stack[-1], 16)
            offset = int(last.stack[-2], 16)
            length = int(last.stack[-3], 16)
            # calldata末尾补0...
            data = calldata[(offset)*2:(offset+length)*2].ljust(length*2, '0')
            self.memory.set(destoffset, length, data)
        elif last.op == 'CODECOPY':
            assert len(
                last.stack) >= 3, f"{last.op} Stack under flow: {last.stack}"
            destoffset = int(last.stack[-1], 16)
            offset = int(last.stack[-2], 16)
            length = int(last.stack[-3], 16)
            data = contract.bytecode[(
                offset)*2:(offset+length)*2].ljust(length*2, '0')
            self.memory.set(destoffset, length, data)
        elif last.op == 'EXTCODECOPY':
            raise Exception("EXTCODECOPY Not Implemented")
        elif last.op == 'RETURNDATACOPY':
            raise Exception("RETURNDATACOPY Not Implemented")
        elif last.op.endswith("CALL"):
            raise Exception(f"{last.op} Not Implemented")
        elif last.op == 'MLOAD':
            # Test My Memory
            offset = int(last.stack[-1], 16)
            real = self.stack[-1]
            if last.memory.get(offset, 0x20) != real:
                print(f"Memory bad {self.cur}")
                print(real)
                print(last.memory.get(offset, 0x20))
                print(offset)
                last.memory.show(Z_MAX)
                exit(-1)

    def match(self, bp: Breakpoint) -> bool:
        for c in bp.conditions:
            try:
                flag = eval(c)
            except:
                # 有可能offset不在其中
                flag = False
            if not flag:
                return False
        return True
