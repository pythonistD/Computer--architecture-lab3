from collections import namedtuple
from enum import Enum
import json


class Opcode(str, Enum):
    load = "load"
    store = "store"
    add = "add"
    sub = "sub"
    mod = "mod"
    jmp = "jmp"
    cmp = "cmp"
    jz = "jz"
    push = "push"
    pop = "pop"
    iret = "iret"
    ei = "ei"
    di = "di"
    hlt = "hlt"
    jnz = "jnz"
    interrupt = ("interrupt",)
    indirect = ("indirect",)
    jn = ("jn",)
    jnn = "jnn"


class DataType(Enum):
    num = "num"
    string = ("string",)
    char = "char"


def write_code(code: list, filename: str) -> None:
    with open(filename, "w") as f:
        f.write(json.dumps(code, indent=4))


def load_code_data(inst, data):
    with open(inst, "r", encoding="utf-8") as f:
        instructions = json.loads(f.read())
        for inst in instructions:
            inst["opcode"] = Opcode[inst["opcode"]]
            if inst["arg"] != "None":
                inst["arg"] = int(inst["arg"])
            else:
                inst["arg"] = None
    with open(data, "r", encoding="utf-8") as f:
        data = json.loads(f.read())
        for d in data:
            d["type"] = DataType(d["type"])
    return instructions, data


def encode_data(name: str, val, d_type: DataType) -> dict:
    return {"name": name, "type": d_type, "val": f"{val}"}
