from components.utils import *
from components.instruction import Ins


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
