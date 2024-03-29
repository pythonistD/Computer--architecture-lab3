import argparse
import logging
from collections import deque
from enum import Enum
from typing import Optional

import yaml

from isa import DataType, Opcode, encode_data, load_code_data

instructions = {Opcode.add, Opcode.cmp, Opcode.load, Opcode.mod, Opcode.di, Opcode.ei, Opcode.hlt, Opcode.store}
control_flow = {Opcode.jmp, Opcode.jnz, Opcode.jz, Opcode.jn, Opcode.jnn}
arithmetic_ops = {Opcode.add, Opcode.sub, Opcode.mod}
address_instructions = {Opcode.add, Opcode.cmp, Opcode.load, Opcode.mod, Opcode.store}
stack_instructions = {Opcode.push, Opcode.pop, Opcode.iret}

"""
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(f"{__name__}.log", mode="w")
formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
"""


class MemType(Enum):
    instruction_mem = 0
    data_mem = 1


class ExternalDevice:
    in_data: Optional[deque]
    output_data: list
    interrupt_vector_address: int

    def __init__(self, input_data: Optional[deque] = None) -> None:
        self.in_data = input_data
        self.output_data = []
        self.interrupt_vector_address = 2

    def get_cur_char(self) -> tuple[int, str]:
        if len(self.in_data) == 0:
            return (-1, "")
        return self.in_data[0]

    def send_char(self) -> dict:
        if len(self.in_data) == 0:
            raise BufferError
        char_s = self.in_data[0][1]
        if char_s == "\x00":
            char_s = "\0"
        char = ord(self.in_data[0][1])
        self.in_data.popleft()
        ch_for_log = chr(char)
        if ch_for_log == "\0":
            ch_for_log = "null"
        logging.debug(f"CHAR_IN: {ch_for_log}")
        return {"name": "char_from_input_device", "type": DataType.char, "val": char, "pos_in_data_mem": "0"}

    def read_char(self, char):
        self.output_data.append(chr(int(char)))
        logging.debug(f"CHAR_OUT: {chr(int(char))}")
        if chr(int(char)) == "\0":
            word = "".join(self.output_data)
            logging.debug(f"THE WHOLE WORD: {word}")

    def read_int(self, num):
        self.output_data.append(num)
        logging.debug(f"INT_OUT: {num}")


class ALU:
    operation_res: Optional[int]
    left_in: Optional[int]
    right_in: Optional[int]
    zero_flag: bool
    negative_flag: bool

    def __init__(self) -> None:
        self.operation_res = 0
        self.left_in = 0
        self.right_in = 0
        self.zero_flag = False
        self.negative_flag = False

    def do_arithmetic(self, opcode: Opcode):
        if opcode is Opcode.add:
            self.add_op()
        elif opcode is Opcode.sub:
            self.sub_op()
        elif opcode is Opcode.mod:
            self.mod_op()
        elif opcode is Opcode.cmp:
            self.sub_op()
        self.check_if_zero()
        self.check_if_negative()

    def check_if_zero(self):
        if self.operation_res == 0:
            self.zero_flag = True
        else:
            self.zero_flag = False

    def check_if_negative(self):
        if self.operation_res < 0:
            self.negative_flag = True
        else:
            self.negative_flag = False

    def add_op(self):
        self.operation_res = self.left_in + self.right_in

    def sub_op(self):
        self.operation_res = self.left_in - self.right_in

    def mod_op(self):
        self.operation_res = self.left_in % self.right_in


class DataPath:
    pc: int
    ar: int
    acc: dict
    sp: int
    ir: dict
    dr: dict

    inst_mem: list
    data_mem: list
    alu: ALU

    in_dev: ExternalDevice
    out_dev: ExternalDevice

    def __init__(
        self,
        start_cell_isr: int,
        isr_prog: list,
        isr_data: list,
        input_device: ExternalDevice,
        output_device: ExternalDevice,
    ) -> None:
        # Sp points to 2048, because initially in stack no data
        self.sp = 2048
        self.acc = encode_data("empty acc", 0, DataType.num)
        self.ar = 0
        self.ir = 0
        self.dr = 0
        self.inst_mem = [0] * (2**11)
        self.data_mem = [0] * (2**11)
        self.inst_mem[2] = start_cell_isr
        self.data_mem[2] = encode_data("interrupt vector", start_cell_isr, DataType.num)
        # Указывают на первую свободную ячейку памяти, нужны для загрузки нескольких программ в память
        self.instr_empty_cell = 0
        self.data_empty_cell = 3
        self.load_program_in_mem(isr_prog, isr_data)
        # В instr_empty_cell запишется первая инструкция основной программы
        self.pc = self.instr_empty_cell

        self.alu = ALU()
        self.in_dev = input_device
        self.out_dev = output_device

    def load_program_in_mem(self, instr: list, data: list):
        counter = 0
        d_offset = self.data_empty_cell
        instr_offset = self.instr_empty_cell
        for i in range(d_offset, d_offset + len(data)):
            if data[counter]["l2l"] is True:
                val = int(data[counter]["val"]) + d_offset
                data[counter]["val"] = val
            self.data_mem[i] = data[counter]
            counter += 1
        self.data_empty_cell = self.data_empty_cell + counter
        counter = 0
        for i in range(instr_offset, instr_offset + len(instr)):
            if instr[counter]["opcode"] in {Opcode.add, Opcode.sub, Opcode.cmp, Opcode.load, Opcode.store, Opcode.mod}:
                # Из-за того, что адреса ячеек данные смещены, т.к в памяти данных уже имеются другие значения
                instr[counter]["arg"] += d_offset
            elif instr[counter]["opcode"] in {Opcode.jmp, Opcode.jnz, Opcode.jz, Opcode.jn, Opcode.jnn}:
                # Инструкции тоже смещены, если загружаемая программа загружается не первой.
                instr[counter]["arg"] += instr_offset
            self.inst_mem[i] = instr[counter]
            counter += 1
        self.instr_empty_cell = self.instr_empty_cell + counter

    def latch_pc(self, sel: Opcode, arg: Optional[int] = None):
        if (sel not in control_flow) and (sel is not Opcode.iret):
            self.pc += 1
        elif sel is Opcode.iret:
            self.pc = int(self.dr["val"])
        else:
            self.pc = arg

    def latch_ar(self, sel):
        if sel is Opcode.interrupt:
            self.ar = self.in_dev.interrupt_vector_address
        elif sel in address_instructions:
            self.ar = int(self.ir["arg"])
        elif sel is Opcode.indirect:
            self.ar = int(self.dr["val"])
        elif sel in stack_instructions:
            self.ar = self.sp

    def latch_acc(self, sel):
        if sel is Opcode.interrupt:
            self.acc = encode_data("saved_pc", self.pc, DataType.num)
        elif sel in {Opcode.load, Opcode.pop}:
            self.acc = self.dr
        elif sel in arithmetic_ops:
            self.acc = encode_data(f"{sel} operation res", self.alu.operation_res, DataType.num)

    def latch_sp(self, sel):
        if sel in {Opcode.push, Opcode.interrupt}:
            # Stack grows up that's why we need to decrement it, the newest value will have the lowest address in stack
            # 2045: newest val  ^
            # 2046:             |
            # 2047: oldest val  |
            self.sp -= 1
        elif sel in {Opcode.pop, Opcode.iret}:
            self.sp += 1

    def latch_alu(self):
        self.alu.left_in = int(self.acc["val"])
        self.alu.right_in = int(self.dr["val"])

    def read_from_mem(self, mem_type):
        if mem_type is MemType.instruction_mem:
            self.ir = self.inst_mem[self.pc]
        elif mem_type is MemType.data_mem:
            if self.ar == 0:
                self.dr = self.in_dev.send_char()
            else:
                self.dr = self.data_mem[self.ar]

    def write_to_data_mem(self):
        if self.ar == 1:
            if self.acc["type"] == DataType.char:
                self.out_dev.read_char(self.acc["val"])
            elif self.acc["type"] == DataType.num:
                self.out_dev.read_int(self.acc["val"])
        else:
            self.data_mem[self.ar] = self.acc


class ControUnit:
    input_device: ExternalDevice
    datapath: DataPath

    ei: bool
    interrupt: bool
    _tick: int

    def __init__(self, input_device, datapath) -> None:
        self.input_device = input_device
        self.datapath = datapath
        self._tick = 0
        self.ei = True
        self.interrupt = False

    def execute(self):
        # The first stage: instruction fetch(inst_mem[pc] -> ir)
        self.datapath.read_from_mem(MemType.instruction_mem)
        cur_inst = self.datapath.ir["opcode"]
        arg = self.datapath.ir["arg"]
        ad_type = self.datapath.ir["address_type"]
        self.tick()
        # Decode and execution stage
        if cur_inst in instructions:
            self.execute_basic_instructions(cur_inst, ad_type)
            self.datapath.latch_pc(cur_inst)
        elif cur_inst in control_flow:
            self.execute_control_flow_instruction(cur_inst, arg)
        elif cur_inst in stack_instructions:
            self.excute_stack_instructions(cur_inst)
            if cur_inst is not Opcode.iret:
                self.datapath.latch_pc(cur_inst)
        # Check for interrupt request
        self.check_for_interrupt()

    def execute_control_flow_instruction(self, instr, arg):
        if instr is Opcode.jmp:
            self.datapath.latch_pc(instr, arg)
            self.tick()
        elif instr is Opcode.jz:
            # The first tick is to check flag
            self.tick()
            if self.datapath.alu.zero_flag:
                self.datapath.latch_pc(instr, arg)
            else:
                # Костыли, нужно, чтобы произошёл простой инкремент PC, который происходит после выполнения базовой операции
                self.datapath.latch_pc(Opcode.add)
            # The second to latch pc
            self.tick()
        elif instr is Opcode.jnz:
            self.tick()
            if self.datapath.alu.zero_flag is False:
                self.datapath.latch_pc(instr, arg)
            else:
                self.datapath.latch_pc(Opcode.add)
            self.tick()
        elif instr is Opcode.jn:
            self.tick()
            if self.datapath.alu.negative_flag:
                self.datapath.latch_pc(instr, arg)
            else:
                self.datapath.latch_pc(Opcode.add)
            self.tick()
        elif instr is Opcode.jnn:
            self.tick()
            if self.datapath.alu.negative_flag is False:
                self.datapath.latch_pc(instr, arg)
            else:
                self.datapath.latch_pc(Opcode.add)
            self.tick()

    def excute_stack_instructions(self, instr):
        if instr is Opcode.pop:
            self.datapath.latch_ar(instr)
            self.tick()
            self.datapath.read_from_mem(MemType.data_mem)
            self.datapath.latch_acc(instr)
            # Increment stack
            self.datapath.latch_sp(instr)
            self.tick()
        elif instr is Opcode.push:
            # Decrement stack first
            self.datapath.latch_sp(instr)
            # tick?
            self.datapath.latch_ar(instr)
            # tick?
            self.datapath.write_to_data_mem()
            self.tick()
        elif instr is Opcode.iret:
            # read pc from stack to the acc
            self.datapath.latch_ar(instr)
            self.tick()
            self.datapath.read_from_mem(MemType.data_mem)
            self.datapath.latch_sp(instr)
            self.tick()
            self.datapath.latch_pc(instr)
            self.ei = True
            self.interrupt = False
            self.tick()
            logging.debug("-----------Interrupt-Ended-----------")

    def execute_basic_instructions(self, instr, ad_type):
        # ad_type == True => indirect address
        if ad_type is True:
            self.load_indirect_address(instr)
        else:
            self.datapath.latch_ar(instr)
            self.tick()

        if instr is Opcode.load:
            self.datapath.read_from_mem(MemType.data_mem)
            self.datapath.latch_acc(instr)
            self.tick()
        elif instr is Opcode.store:
            self.datapath.write_to_data_mem()
            self.tick()
        elif instr in arithmetic_ops:
            self.datapath.read_from_mem(MemType.data_mem)
            self.datapath.latch_alu()
            self.tick()
            self.datapath.alu.do_arithmetic(instr)
            self.datapath.latch_acc(instr)
            self.tick()
        elif instr is Opcode.cmp:
            self.datapath.read_from_mem(MemType.data_mem)
            self.datapath.latch_alu()
            self.tick()
            self.datapath.alu.do_arithmetic(instr)
            self.tick()
        elif instr in {Opcode.ei, Opcode.di}:
            if instr is Opcode.ei:
                self.ei = True
            elif instr is Opcode.di:
                self.ei = False
            self.tick()
        elif instr is Opcode.hlt:
            raise SystemExit

    def load_indirect_address(self, instr):
        """Загрузить в AR косвенный адрес, после завершиния функции в AR лежит нужный адрес"""
        self.datapath.latch_ar(instr)
        self.tick()
        self.datapath.read_from_mem(MemType.data_mem)
        self.datapath.latch_ar(Opcode.indirect)
        self.tick()

    def check_for_interrupt(self):
        # One tick to check for interrupt request
        self.tick()
        if (self.ei is True) and (self.interrupt is True):
            logging.debug("-----------Interrupt-Started-----------")
            self.do_interrupt()

    def do_interrupt(self):
        self.ei = False
        logging.debug("EI switched to False")
        self.save_context()
        self.find_isr()

    def save_context(self):
        self.save_pc()

    def save_acc(self):
        # Для push необходимо сначала инкрементировать SP, поэтому сначала вызываем latch_sp
        self.datapath.latch_sp(Opcode.push)
        self.tick()
        self.datapath.latch_ar(Opcode.push)
        self.datapath.write_to_data_mem()
        self.tick()

    def save_pc(self):
        self.datapath.latch_acc(Opcode.interrupt)
        self.datapath.latch_sp(Opcode.push)
        self.tick()
        self.datapath.latch_ar(Opcode.push)
        # tick?
        self.datapath.write_to_data_mem()
        self.tick()
        logging.debug(f"save_pc: ar:{self.datapath.ar} mem[ar]:{self.datapath.data_mem[self.datapath.ar]}")

    def find_isr(self):
        # Write into AR adress where interrupt vector is stored
        self.datapath.latch_ar(Opcode.interrupt)
        self.tick()
        self.datapath.read_from_mem(MemType.data_mem)
        self.tick()
        self.datapath.latch_acc(Opcode.load)
        self.tick()
        self.datapath.latch_pc(Opcode.iret)
        self.tick()
        logging.debug(f"find_isr: ar:{self.datapath.ar} mem[ar]:{self.datapath.data_mem[self.datapath.ar]}")
        logging.debug("-----------Execute-ISR-----------")

    def tick(self):
        self._tick += 1

    def __repr__(self) -> str:
        state_repr = "tick:{} pc:{} ar:{} acc:{} ei:{} interrupt:{}".format(
            self._tick, self.datapath.pc, self.datapath.ar, self.datapath.acc["val"], self.ei, self.interrupt
        )
        cur_instr = self.datapath.inst_mem[self.datapath.pc]
        opcode = cur_instr["opcode"].name
        arg = cur_instr["arg"]
        if (arg is not None) and (opcode not in {"jmp", "jz", "jnz", "jn", "jnn"}):
            arg_in_data_mem = self.datapath.data_mem[arg]
        else:
            arg_in_data_mem = "null"
        if arg is None:
            arg = "null"
        instr_repr = "Opcode:{} Arg:{} Mem[arg]:{}".format(opcode, arg, arg_in_data_mem)
        return "{} \t{}".format(state_repr, instr_repr)


def simulation(limit: int, inst_mem: list, data_mem: list, inst_isr, data_isr, input_data: list):
    in_d: deque = deque(input_data)
    in_dev = ExternalDevice(input_data=in_d)
    out_dev = ExternalDevice()
    datapath = DataPath(
        start_cell_isr=0, isr_prog=inst_isr, isr_data=data_isr, input_device=in_dev, output_device=out_dev
    )
    datapath.load_program_in_mem(inst_mem, data_mem)
    controlunit = ControUnit(input_device=in_dev, datapath=datapath)
    try:
        c = 0
        while c < limit:
            logging.debug("%s", controlunit)
            if len(in_dev.in_data) != 0:
                if in_dev.get_cur_char()[0] <= c:
                    controlunit.interrupt = True
            controlunit.execute()
            c += 1
    except SystemExit:
        logging.debug(f"Simulation stopted by HLT command Total ticks: {controlunit._tick}")
        if len(out_dev.output_data) != 0:
            print(*out_dev.output_data)
    except BufferError:
        logging.debug("Input buffer is empty")
        return


def main(instr_f: str, data_f: str, input_f: str):
    inst_p, data_p = load_code_data(instr_f, data_f)

    inst_isr, data_isr = load_code_data("static/isr/instr.json", "static/isr/data.json")

    with open(input_f, encoding="utf-8") as f:
        ym = yaml.safe_load(f.read())
    data = ym
    simulation(limit=100000, inst_mem=inst_p, data_mem=data_p, inst_isr=inst_isr, data_isr=data_isr, input_data=data)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        metavar="INPUT",
        nargs="*",
        help="<path to file with instruction memory> <path to file with data memory> <path to input file>",
    )
    args: list[str] = parser.parse_args().inputs
    assert len(args) == 3, "There should be two arguments"
    main(args[0], args[1], args[2])
