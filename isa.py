from collections import namedtuple
from enum import Enum
import json


class Opcode(Enum):
    load = 1
    store = 2
    add = 3
    sub = 4
    mod = 5
    jmp = 6
    cmp = 7
    jz = 8
    push = 9
    pop = 10
    iret = 11
    ei = 12
    di = 13
    hlt = 14
    jnz = 15


class DataType(Enum):
    num = 1
    string = 2,
    char = 3

def write_code(code: list, filename: str) -> None:
    with open(filename, 'w') as f:
        f.write(json.dumps(code, indent=4))
