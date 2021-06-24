# coding=utf8
import cmd
from components.utils import *
from components.contract import BytecodeContract
from components.step import *


class DebugVM(cmd.Cmd):
    intro = None
    real_intro = 'Welcome to the EDB shell. Type help or ? to list commands.\n'
    file = None

    def __init__(self, txhash: str) -> None:
        self.txhash = txhash
        info = w3.eth.getTransaction(txhash)
        contract_addr = info["to"]
        self.caller = info["from"]
        self.calldata = info['input']  # 是不是不应该放这里
        self.block_number = info['blockNumber'] - 1
        if self.calldata:
            self.calldata = remove_0x_prefix(self.calldata)
        print(f"[*] Calldata: {self.calldata}")
        code = w3.eth.getCode(
            contract_addr, block_identifier=self.block_number).hex()
        code = remove_0x_prefix(code)
        self.contract = BytecodeContract(contract_addr, code)

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
                pc: pc
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

    def do_p(self, args):
        "p mem|sto|sta: Print memory or storage or stack (full print)"
        args = args.strip()
        if args == 'mem':
            self.print_memory(Z_MAX)
        elif args == 'sto':
            self.print_storage(Z_MAX)
        elif args == 'sta':
            self.print_stack()
        else:
            print(f"[x] Unkown {args} to print")

    def do_x(self, args):
        "x mem[a:b]|sto[k]|sta[k]: Print memory or storage or stack value at specified position"
        args = args.strip()
        if args.startswith('mem'):
            l, r = map(eval, args.split('[')[-1].strip(']').split(':'))
            print(self.steps[self.cur].memory.get(l, r-l))
        elif args.startswith('sto'):
            k = eval(args.split('[')[-1].strip(']'))
            k = hex(k)[2:].zfill(64)
            record = self.steps[self.cur].storage.get(k, None)
            if not record:
                print("No record, loading origin data from chain")
                record = self.get_old_storage(self.contract.addr, k)
            print(record)
        elif args.startswith('sta'):
            k = eval(args.split('[')[-1].strip(']'))
            print(self.steps[self.cur].stack[k])
        else:
            print(f"[x] Unkown {args} to exp")

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

    def do_ws(self, args):
        "ws stack_k: Run back to watch who changed stack[k]"
        args = parse(args)
        k = args[0]
        if k < 0:
            k += len(self.steps[self.cur].stack)
        check_stack = self.steps[self.cur].stack[:k+1]
        found = False
        while True:
            self.cur -= 1
            if not 0 <= self.cur < self.total:
                break
            if self.steps[self.cur].stack[:k+1] != check_stack:
                found = True
                break
        self.check_cur()
        self.info()
        if not found:
            print("[*] Cannot found who changed the stack")

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

    def get_old_storage(self, addr, offset):
        return w3.eth.get_storage_at(addr, offset, block_identifier=self.block_number).hex()

    def print_pc(self):
        ins: Ins = self.steps[self.cur].ins
        print(f"({self.cur+1}/{self.total})", end=' ')
        print(f"{C.OKCYAN}{ins.short_str()}{C.ENDC}")
        print(f"  PC = {ins.addr} = {hex(ins.addr)}")
        print()

    def print_storage(self, max_size=MAX_SIZE):
        storage = self.steps[self.cur].storage
        print("Storage:")
        l = min(len(storage), max_size)
        keys = sorted([int(x, 16) for x in storage.keys()])
        for i in range(l):
            k = hex(keys[i])[2:].zfill(64)
            print(f"  {k}: ", end='')
            print(f"  {C.OKBLUE}{storage[k]}{C.ENDC}")
        if len(storage) > max_size:
            print(f"  ...")
        if not storage:
            print("  (empty)")
        print()

    def print_memory(self, max_size=MAX_SIZE):
        memory: Memory = self.steps[self.cur].memory
        memory.show(max_size)

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
