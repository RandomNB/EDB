from components.utils import *


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
        end = math.ceil((offset + length) / 0x20 - 1) * 0x20
        assert end >= start

        prefix = self._mem.get(start, ZERODATA)
        prefix = prefix[:(offset-start)*2]
        suffix = self._mem.get(end, ZERODATA)
        suffix = suffix[(offset+length-end)*2:]
        value = prefix + value + suffix
        assert len(value) % 0x40 == 0, f"Wrong length {len(value)}"

        vi = 0
        for i in range(start, end+0x20, 0x20):
            self._mem[i] = value[vi:vi+0x40]
            vi += 0x40

    def get(self, offset, length):
        start = offset // 0x20 * 0x20
        end = math.ceil((offset + length) / 0x20) * 0x20
        res = ""
        for i in range(start, end, 0x20):
            data = self._mem.get(i, ZERODATA)
            res += data
        if offset+length-end == 0:
            res = res[(offset-start)*2:]
        else:
            res = res[(offset-start)*2:(offset+length-end)*2]
        assert len(res) == length*2, "[x] Wrong ret length"
        return res

    def show(self, max_size):
        print("Memory:")
        l = min(max_size, len(self._mem))
        keys = sorted(self._mem.keys())
        padding = len(hex(keys[-1])[2:]) if keys else 4
        for i in range(l):
            k = keys[i]
            print(f"  0x{hex(k)[2:].zfill(padding)}: ", end='')
            print(f"  {C.HEADER}{self._mem[k]}{C.ENDC}")
        if len(self._mem) > max_size:
            print(f"  ...")
        if not self._mem:
            print(f"  (empty)")
        print()
