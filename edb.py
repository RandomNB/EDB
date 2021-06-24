# coding=utf8
from components import *


def main():
    txhash = sys.argv[1]
    vm = DebugVM(txhash)
    vm.start()


if __name__ == '__main__':
    main()
