from collections import namedtuple
from enum import Enum

Term = namedtuple('Term', 'line pos')

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



