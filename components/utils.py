# coding=utf8
import sys
import math
import os
import copy
import rlp
from sha3 import keccak_256
from web3 import Web3
from eth_utils import remove_0x_prefix
from pyevmasm import instruction_tables
from config import *
instruction_table = {}
ZERODATA = '0' * 64


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
    global instruction_table
    instruction_table = {}
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


def parse(arg):
    'Convert a series of zero or more numbers to an argument tuple'
    try:
        return tuple(map(int, arg.split()))
    except:
        return []


def create_addr(creator: str, nonce: int):
    return keccak_256(rlp.encode(
        [bytes.fromhex(remove_0x_prefix(creator)), nonce])
    ).hexdigest()[-40:]


w3 = Web3(Web3.HTTPProvider(ENDPOINT_URI))
init_instruction_table()
