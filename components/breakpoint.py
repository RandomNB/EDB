from components.utils import *


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
            elif c.startswith("pc"):
                self.conditions.append(f"self.{c}")
            else:
                print(f"[w] Cannot parse condition: {c}")

    def inspect(self):
        for c in self.conditions:
            print(f"  {c}")
