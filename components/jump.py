from components.utils import *


class Jump():
    def __init__(self, cur, src_ins, dst_ins, stack: list) -> None:
        self.src_cur = cur
        self.dst_cur = cur + 1
        self.src_ins = src_ins
        self.dst_ins = dst_ins
        self.stack = stack

    def __str__(self) -> str:
        pass
