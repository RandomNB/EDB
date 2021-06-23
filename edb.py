# coding=utf8
import cmd
import sys
import math
import os
import copy
from web3 import Web3
from pyevmasm import instruction_tables
instruction_table = {}
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

ZERODATA = '0' * 64
MAX_SIZE = 16


class C:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def init_instruction_table():
    for ik in instruction_tables["serenity"].keys():
        ins = instruction_tables["serenity"][ik]
        name = ins.name
        if name in ["DUP", "PUSH"]:
            name = name + str(ins.operand)
        assert name not in instruction_table
        instruction_table[name] = ins


def short_stack(stack):
    ret = []
    for v in stack:
        ret.append(hex(int(v, 16)))
    return ret


class Ins():
    def __init__(self, addr_op: str) -> None:
        addr, op_s = addr_op.split(':')
        self.addr = int(addr.strip(), 16)
        splited = op_s.strip().split(' ')
        self.opcode = splited[0]
        self.oprand = splited[1:]

    def short_str(self):
        return f"{self.opcode} {' '.join(self.oprand)}".strip()

    def __str__(self) -> str:
        return f"{self.addr}: {self.opcode} {' '.join(self.oprand)}".strip()


class BytecodeContract():
    def __init__(self, addr, bytecode) -> None:
        print("[*] Disassembling bytecode via pyevmasm")
        code = os.popen(f'echo {bytecode} | evmasm -d').read()
        code = code.split('\n')
        self.pc2ins = {}

        for c in code:
            if c:
                ins = Ins(c.strip())
                assert ins.addr not in self.pc2ins, "PC duplicated!"
                self.pc2ins[ins.addr] = ins
        print(f"[i] Loaded {len(self.pc2ins)} instructions of {addr}")

        self.addr = addr
        self.bytecode = bytecode

    def ins_at(self, pc) -> Ins:
        return self.pc2ins[pc]


class Memory():
    def __init__(self) -> None:
        self._mem = {}  # 每0x20存一段

    def copy(self):
        new = Memory()
        new._mem = copy.copy(self._mem)
        return new

    def set(self, offset, length, value):
        assert len(value) == length * \
            2, f"memory.set len mismatch {length}: {value}"
        start = offset // 0x20 * 0x20
        end = math.ceil((offset + length) / 0x20) * 0x20

        prefix = self._mem.get(start, ZERODATA)
        prefix = prefix[:(offset-start)*2]
        suffix = self._mem.get(end, ZERODATA)
        suffix = suffix[(offset+length-end)*2:]
        value = prefix + value + suffix
        assert len(value) % 0x40 == 0, f"Wrong length {len(value)}"

        vi = 0
        for i in range(start, end, 0x20):
            self._mem[i] = value[vi:vi+0x40]
            vi += 0x40

    def get(self, offset, length):
        start = offset // 0x20 * 0x20
        end = math.ceil((offset + length) / 0x20) * 0x20
        res = ""
        for i in range(start, end, 0x20):
            data = self._mem.get(i, ZERODATA)
            res += data
        res = res[(offset-start)*2:(offset+length-end)*2]
        assert len(res) == length, "[x] Wrong ret length"
        return res

    def show(self):
        print("Memory:")
        l = min(MAX_SIZE, len(self._mem))
        keys = sorted(self._mem.keys())
        padding = len(hex(keys[-1])[2:]) if keys else 4
        for i in range(l):
            k = keys[i]
            print(f"  0x{hex(k)[2:].zfill(padding)}: ", end='')
            print(f"  {C.HEADER}{self._mem[k]}{C.ENDC}")
        if len(self._mem) > MAX_SIZE:
            print(f"  ...")
        if not self._mem:
            print(f"  (empty)")
        print()


class Breakpoint():
    def __init__(self, conditions: str) -> None:
        self.condition_str = conditions
        conditions = conditions.split(';')
        self.conditions = []
        for c in conditions:
            c = c.strip().replace(' ', '')
            c = c.replace('=', '==').replace('====', '==')  # 防止意外赋值
            if c.startswith('op'):
                # e.g. op==sha3
                op = c.split('=')[-1].upper()
                self.conditions.append(f"self.op == '{op}'")
            elif c.startswith("sta["):
                # e.g. sta[-1] == 0x123
                left, right = c.split(']')
                offset = left.split('[')[-1]
                self.conditions.append(f"int(self.stack[{offset}],16){right}")
            elif c.startswith("sto["):
                # e.g. sto[0x1] == 0x123
                left, right = c.split(']')
                offset = left.split('[')[-1]
                offset = hex(eval(offset))[2:].zfill(64)
                self.conditions.append(
                    f"int(self.storage['{offset}'],16){right}")
            else:
                print(f"[w] Cannot parse condition: {c}")

    def inspect(self):
        for c in self.conditions:
            print(f"  {c}")


class Jump():
    def __init__(self, cur, src_ins, dst_ins, stack: list) -> None:
        self.src_cur = cur
        self.dst_cur = cur + 1
        self.src_ins = src_ins
        self.dst_ins = dst_ins
        self.stack = stack

    def __str__(self) -> str:
        pass


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
            raise Exception("CODECOPY Not Implemented")
        elif last.op == 'EXTCODECOPY':
            raise Exception("EXTCODECOPY Not Implemented")
        elif last.op == 'RETURNDATACOPY':
            raise Exception("RETURNDATACOPY Not Implemented")
        elif last.op.endswith("CALL"):
            raise Exception(f"{last.op} Not Implemented")

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


def parse(arg):
    'Convert a series of zero or more numbers to an argument tuple'
    try:
        return tuple(map(int, arg.split()))
    except:
        return []


class DebugVM(cmd.Cmd):
    intro = None
    real_intro = 'Welcome to the EDB shell. Type help or ? to list commands.\n'
    file = None

    def __init__(self, txhash: str) -> None:
        self.txhash = txhash
        info = w3.eth.getTransaction(txhash)
        contract_addr = info["to"]
        self.caller = info["from"]
        self.calldata = info['input']
        if self.calldata:
            self.calldata = self.calldata[2:]
        print(f"[*] Calldata: {self.calldata}")
        code = w3.eth.getCode(contract_addr).hex()
        self.contract = BytecodeContract(contract_addr, code[2:])

        self.steps = []
        self.load_trace()

        self.total = len(self.steps)
        self.cur = 0
        self.breakpoints = []
        super(DebugVM, self).__init__()

    def load_trace(self):
        trace = w3.provider.make_request(
            'debug_traceTransaction', [self.txhash, {"disableMemory": True}]
        )
        trace = trace['result']['structLogs']
        print(f"[i] Loaded {len(trace)} steps")
        last_step = None
        cur = 0
        for s in trace:
            step = Step(cur, s, self.contract, self.calldata, last_step)
            self.steps.append(step)
            last_step = step
            cur += 1

    def start(self):
        print(self.real_intro)
        self.info()
        while True:
            try:
                self.cmdloop()
                break
            except KeyboardInterrupt:
                break

    def check_cur(self):
        self.cur = min(self.total-1, self.cur)
        self.cur = max(0, self.cur)

    def do_n(self, args):
        "n [delta]: Next delta steps"
        args = parse(args)
        delta = 1
        if args:
            delta = args[0]
        self.cur += delta
        self.check_cur()
        self.info()

    def _run(self, delta):
        broken = False
        while True:
            self.cur += delta
            if not 0 <= self.cur < self.total:
                break
            bcnt = 0
            for b in self.breakpoints:
                if self.steps[self.cur].match(b):
                    print(
                        f"Breakpoint #{bcnt} {C.OKGREEN}{b.condition_str}{C.ENDC} matched")
                    broken = True
                    break
                bcnt += 1
            if broken:
                break
        self.check_cur()
        self.info()
        if not broken:
            print("[*] Transaction finished without match any breakpoints")

    def do_rb(self, args):
        "rb: Run backward until match breakpoints"
        self._run(-1)

    def do_r(self, args):
        "r: Run until match breakpoints"
        self._run(1)

    def do_b(self, args):
        """
        b [exp]: Add breakpoint with exp or show breakpoints
            e.g b op==sha3;sta[-2]==0x100
            可用条件如下：
                op: 操作码
                sta[xx]: 栈元素
                sto[xx]: storage元素
        """
        print()
        if not args.strip():
            self.show_breakpoints()
            return
        self.breakpoints.append(Breakpoint(args))
        print(f"Breakpoint #{len(self.breakpoints)-1} added:")
        self.breakpoints[-1].inspect()

    def show_breakpoints(self):
        print("Breakpoints:")
        bcnt = 0
        for b in self.breakpoints:
            print(f"  #{bcnt}: {C.OKGREEN}{b.condition_str}{C.ENDC}")
            bcnt += 1
        if not self.breakpoints:
            print(f"  (empty)")
        print()
        return

    def do_db(self, args):
        "db [k]: Delete breakpoint #k"
        print()
        args = parse(args)
        if not args or args[0] >= len(self.breakpoints) or args[0] < 0:
            print("Invalid breakpoint id to delete")
        print(
            f"Deleted breakpoint #{args[0]}: {C.OKGREEN}{self.breakpoints[args[0]].condition_str}{C.ENDC}")
        del self.breakpoints[args[0]]
        self.show_breakpoints()

    def do_g(self, args):
        "goto step: Goto step"
        args = parse(args)
        if not args:
            print("Wrong destination")
            return
        self.cur = args[0] - 1
        self.check_cur()
        self.info()

    def do_q(self, args):
        "Quit"
        return True

    def do_j(self, args):
        "j: Print jump info"
        self.print_jump()

    def print_stack(self):
        stack = self.steps[self.cur].stack
        print("Stack:")
        l = len(stack)
        for i in range(l):
            print(
                f"  {C.WARNING}{stack[i]}{C.ENDC} ({str(l-i-1) + ' from ' if i<l-1 else ''}top)")
        if not stack:
            print("  (empty)")
        print()

    def print_pc(self):
        ins: Ins = self.steps[self.cur].ins
        print(f"({self.cur+1}/{self.total})", end=' ')
        print(f"{C.OKCYAN}{ins.short_str()}{C.ENDC}")
        print(f"  PC = {ins.addr} = {hex(ins.addr)}")
        print()

    def print_storage(self):
        storage = self.steps[self.cur].storage
        print("Storage:")
        l = min(len(storage), MAX_SIZE)
        keys = sorted([int(x, 16) for x in storage.keys()])
        for i in range(l):
            k = hex(keys[i])[2:].zfill(64)
            print(f"  {k}: ", end='')
            print(f"  {C.OKBLUE}{storage[k]}{C.ENDC}")
        if len(storage) > MAX_SIZE:
            print(f"  ...")
        if not storage:
            print("  (empty)")
        print()

    def print_memory(self):
        memory: Memory = self.steps[self.cur].memory
        memory.show()

    def print_jump(self):
        self.steps[self.cur].print_jump()

    @property
    def prompt(self):
        return f"debug({self.contract.addr})> "

    def info(self):
        print()
        self.print_memory()
        self.print_storage()
        self.print_stack()
        # self.print_jump()
        self.print_pc()


def debug(txhash):
    vm = DebugVM(txhash)
    vm.start()


def main():
    txhash = sys.argv[1]
    init_instruction_table()
    debug(txhash)


if __name__ == '__main__':
    main()
