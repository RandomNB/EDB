from components.utils import *


class FakeTransaction():
    # 方便解析internal transaction
    def __init__(self, caller, to, data, value) -> None:
        self.caller = caller
        self.to = to
