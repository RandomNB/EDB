# coding=utf8
from components import *





def debug(txhash):
    vm = DebugVM(txhash)
    vm.start()


def main():
    txhash = sys.argv[1]
    debug(txhash)


if __name__ == '__main__':
    main()
