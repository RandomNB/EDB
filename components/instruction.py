from components.utils import *


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
