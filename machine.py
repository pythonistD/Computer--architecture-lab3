from typing import Optional
from enum import Enum
import logging
import argparse
import json

from isa import Opcode, DataType, load_code_data

instructions = {Opcode.add, Opcode.cmp, Opcode.load, Opcode.mod, Opcode.di, Opcode.ei, Opcode.hlt, Opcode.push, Opcode.pop, Opcode.iret}
control_flow = {Opcode.jmp, Opcode.jnz, Opcode.jz}
arithmetic_ops = {Opcode.add, Opcode.sub, Opcode.mod}
address_instructions = {Opcode.add, Opcode.cmp, Opcode.load, Opcode.mod}
stack_instructions = {Opcode.push, Opcode.pop, Opcode.iret}

class MemType(Enum):
    instruction_mem = 0
    data_mem = 1


class ExternalDevice:
    ei_or_di: bool
    input_data: Optional[list]
    output_data: list
    pointer: int
    interrupt_vector_address: int = 2

    time_c : int

    def __init__(self, input_data: Optional[list]=None) -> None:
        self.input_data = input_data
        self.time_c = 0
    
    def get_cur_char(self) -> tuple[int, str]:
        return self.input_data[self.pointer]

    def send_char(self) -> dict:
        char = self.input_data[self.pointer]
        self.pointer += 1
        return char

    def read_char(self, char):
        self.output_data.append(char)


class ALU:
    operation_res: Optional[int]
    left_in: Optional[int]
    right_in: Optional[int]
    zero_flag: bool

    def __init__(self) -> None:
        self.operation_res = 0
        self.left_in = 0
        self.right_in = 0
        self.zero_flag = False

    def do_arithmetic(self, opcode: Opcode):
        if opcode is Opcode.add:
            self.add_op()
        elif opcode is Opcode.sub:
            self.sub_op()
        elif opcode is Opcode.mod:
            self.mod_op()
        elif opcode is Opcode.cmp:
            self.sub_op()

    def check_if_zero(self):
        if self.operation_res == 0:
            self.zero_flag = True
        else:
            self.zero_flag = False

    def add_op(self):
        self.operation_res = self.left_in + self.right_in
        self.check_if_zero()

    def sub_op(self):
        self.operation_res = self.left_in - self.right_in
        self.check_if_zero()
   
    def mod_op(self):
        self.operation_res = self.left_in % self.right_in
        self.check_if_zero()


class DataPath:
    pc: int
    ar: int
    acc: int
    sp: int
    ir: dict
    dr: dict

    inst_mem: list 
    data_mem: list
    alu: ALU

    in_dev: ExternalDevice
    out_dev: ExternalDevice


    def __init__(self, start_cell_isr: int, isr: list, input_device: ExternalDevice, output_device: ExternalDevice) -> None:
        # Sp points to 2048, because initially in stack no data
        self.sp = 2048
        self.pc = 0
        self.acc = 0
        self.ar = 0
        self.ir = 0
        self.dr = 0
        self.inst_mem = [0] * (2 ** 11)
        self.data_mem = [0] * (2 ** 11)
        self.load_program_in_mem(start_cell_isr, isr, True)
        self.data_mem[3] = {
            "name": "in_d",
            "type": "num",
            "val": "0",
            "pos_in_data_mem": "3"
        }
        self.inst_mem[2] = start_cell_isr
        self.alu = ALU()
        self.in_dev = input_device
        self.out_dev = output_device

        self.empty_cell = 3


    def load_program_in_mem(self, base, instr_or_data: list, instr_mem: bool=True):
        counter = 0
        mem = self.inst_mem
        if instr_mem is False:
            mem = self.data_mem
        for i in range(base, base + len(instr_or_data)):
            mem[i] = instr_or_data[counter]
            counter += 1

    
    def load_program_in_mem_test(self, base_inst, instr: list, base_data, data: list):
        counter = 0
        for i in range(base_data, base_data + len(data)):
            self.data_mem[i] = data[counter]
            counter += 1
        counter = 0
        for i in range(base_inst, base_inst + len(instr)):
            instr[counter]['arg']
            self.inst_mem[i] = instr[counter]
            counter += 1

    def latch_pc(self, sel: Opcode, arg: Optional[int] = None):
        if sel not in control_flow:
            self.pc += 1
        elif sel is Opcode.iret:
            self.pc = self.acc
        else:
            self.pc = arg
    
    def latch_ar(self, sel):
        if sel is Opcode.interrupt:
            self.ar = self.in_dev.interrupt_vector_address
        elif sel in address_instructions:
            self.ar = int(self.ir['arg'])
        elif sel in stack_instructions:
            self.ar = self.sp

    def latch_acc(self, sel):
        if sel is Opcode.interrupt:
            self.acc = self.pc
        elif sel is Opcode.load:
            if self.dr['type'] is DataType.char:
                val_to_acc = ord(self.dr['val'])
            elif self.dr['type'] is DataType.num:
                val_to_acc = int(self.dr['val'])
            self.acc = val_to_acc
        elif sel is arithmetic_ops:
            self.acc = self.alu.operation_res

    def latch_sp(self, sel):
        if sel in {Opcode.push, Opcode.interrupt}:
            # Stack grows up that's why we need to decrement it, the newest value will have the lowest address in stack
            #2045: newest val  ^
            #2046:             |
            #2047: oldest val  |
            self.sp -= 1
        elif sel in {Opcode.pop, Opcode.iret}:
            self.sp += 1
    
    def latch_alu(self):
        self.alu.left_in = self.acc
        t = self.dr['val']
        self.alu.right_in = ord(self.dr['val'])

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
            self.out_dev.read_char(self.acc)
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
        cur_inst = self.datapath.ir['opcode']
        arg = self.datapath.ir['arg']
        self.tick()
        # Decode and execution stage
        if cur_inst in instructions:
            self.execute_basic_instructions(cur_inst)
            self.datapath.latch_pc(cur_inst)
        elif cur_inst in control_flow:
            self.execute_control_flow_instruction(cur_inst, arg)
        elif cur_inst in stack_instructions:
            self.excute_stack_instructions(cur_inst)
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
                self.datapath.latch_pc(Opcode.add)
            # The second to latch pc
            self.tick()
        elif instr is Opcode.jnz:
            self.tick()
            if self.datapath.alu.zero_flag == False:
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
            self.datapath.latch_acc(instr)
            self.tick()
            self.datapath.latch_pc(instr)
            self.tick()

    def execute_basic_instructions(self, instr):
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

    def check_for_interrupt(self):
        # One tick to check for interrupt request
        self.tick()
        if (self.ei == True) and (self.interrupt == True):
            self.do_interrupt()


    def do_interrupt(self):
        self.save_context()
        self.find_isr()

    def save_context(self):
        self.datapath.latch_acc(Opcode.interrupt)
        self.datapath.latch_sp(Opcode.push)
        self.tick()
        self.datapath.latch_ar(Opcode.push)
        # tick?
        self.datapath.write_to_data_mem()
        self.tick()

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
    
        
    def tick(self):
        self._tick += 1

    def __repr__(self) -> str:
        state_repr = 'tick {} pc {} ar {} mem_out {} acc {} ei {}'.format(
            self._tick,
            self.datapath.pc,
            self.datapath.ar,
            self.datapath.data_mem[self.datapath.ar],
            self.datapath.acc,
            self.ei
        )
        cur_instr = self.datapath.inst_mem[self.datapath.pc]
        print(cur_instr['opcode'].name)
        opcode = cur_instr['opcode'].name
        arg = cur_instr['arg']
        arg_in_data_mem = self.datapath.data_mem[arg]
        instr_repr = '{} {} {}'.format(opcode, arg, arg_in_data_mem)
        return '{} \t{}'.format(state_repr, instr_repr)




def simulation(limit: int, inst_mem: list, data_mem: list, inst_isr, data_isr):
    in_dev = ExternalDevice([(1, 'h'), (10, 'e'), (20, 'l'), (25, 'l'), (100, 'o')])
    out_dev = ExternalDevice()
    datapath = DataPath(start_cell_isr=1947, isr=inst_isr, input_device=in_dev, output_device=out_dev)
    datapath.load_program_in_mem(0, inst_mem, instr_mem=True)
    datapath.load_program_in_mem(4, data_mem, instr_mem=False)
    controlunit = ControUnit(input_device=in_dev, datapath=datapath)
    try:
        c = 0
        while c < limit:
            logger.debug('%s', controlunit)
            if in_dev.get_cur_char()[0] == c:
                controlunit.interrupt = True
            print(controlunit)
            controlunit.execute()
            c += 1
    except SystemExit:
        logger.debug(f'Simulation stopted by HLT command Total ticks: {controlunit._tick}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', metavar='INPUT', nargs='*', help='<path to file with instruction memory> <path to file with data memory>')
    args:list[str] = parser.parse_args().inputs
    assert len(args) == 2, 'There should be two arguments'

    inst_p, data_p = load_code_data(args[0], args[1])

    inst_isr, data_isr = load_code_data('static/inst_isr.json', 'static/data_mem.json')

    
    simulation(limit=1000, inst_mem=inst_p, data_mem=data_p, inst_isr=inst_isr, data_isr=data_isr)
    


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(f'{__name__}.log', mode='w')
    formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()

