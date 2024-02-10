from typing import Optional

from isa import Opcode, DataType, write_code


def symbol2opcode(symbol):
    return {
    'load': Opcode.load,
    'store': Opcode.store,
    'add' : Opcode.add,
    'sub' : Opcode.sub,
    'mod' : Opcode.mod,
    'jmp' : Opcode.jmp,
    'cmp' : Opcode.cmp,
    'jz' : Opcode.jz,
    'push' : Opcode.push,
    'pop' : Opcode.push,
    'iret' : Opcode.iret,
    'ei' : Opcode.ei,
    'di' : Opcode.di,
    'hlt' : Opcode.hlt,
    'jnz' : Opcode.jnz
    }.get(symbol)

def symbol2datatype(symbol):
    return {
        'num' : DataType.num,
        'string' : DataType.string,
        'char' : DataType.char
    }.get(symbol)

class Translator:
    out_instructions_file_name: str
    out_data_file_name: str

    file_data: str
    labels: list[dict] = []
    instructions: list[dict] = []
    label_pos: dict = dict()

    def __init__(self, path_to_program: str, out_instructions_file_name: str, out_data_file_name: Optional[str]=None) -> None:
        self.out_instructions_file_name = out_instructions_file_name
        self.out_data_file_name = out_data_file_name
        self.file_data = self.read_data_from_file(path_to_program)

    
    def read_data_from_file(self, path_to_file: str) -> str :
        with open(path_to_file, 'r', encoding='utf-8') as f:
            data = f.read()
            return data
    
    def translate(self):
        self.parse()
        write_code(self.labels, self.out_data_file_name)
        write_code(self.instructions, self.out_instructions_file_name)

        
    def parse(self):
        self.skip()
        programm_lines = self.delete_spaces_comments()
        self.parse_labels(programm_lines)
        self.parse_instructions(programm_lines)



    
    def skip(self):
        d = self.file_data.find('.data')
        t = self.file_data.find('.text')
        if t == -1:
            raise Exception('.text section must be')
        if d == -1:
            self.file_data = self.file_data[t:]
        else:
            self.file_data = self.file_data[d:]
        

    
    def delete_spaces_comments(self) -> list :
        lines = self.file_data.split('\n')
        updated_lines = []
        for i in range(len(lines)):
            if lines[i] == '' or lines[i] == '.text:' or lines[i] == '.data:':
                continue
            cur_line = lines[i].strip()
            pos = cur_line.find(';')
            if pos != -1:
                cur_line = cur_line[:pos]
            updated_lines.append(cur_line)
        return updated_lines
    
    def parse_labels(self, lines: list) -> None:
        # Count position of instruction to which label points
        counter = 0
        pos_in_data_mem = 3
        for i in range(len(lines)):
            pos = lines[i].find(':')
            if pos == -1:
                counter += 1
                continue
            line = lines[i].split(' ')
            name = line[0][:pos]
            # Points to the instruction
            if len(line) == 1:
                pointer = counter
            # Points to the memory cell
            elif len(line) == 3:
                datatype = symbol2datatype(line[1])
                if datatype is None:
                    raise ValueError(f'There is no such data type.\n line:{i} {line[i]}')
                var_type = datatype
                val = int(line[2])
                pointer = pos_in_data_mem
                self.labels.append({
                    'name' : f'{name}',
                    'type' : f'{var_type}',
                    'val' : f'{val}',
                    'pos_in_data_mem': f'{pos_in_data_mem}'
                })
            self.label_pos[name] = pointer
            pos_in_data_mem += 1

    def parse_instructions(self, lines: list):
        counter = 0
        for i in range(len(lines)):
            line = lines[i].split(' ')
            pos = lines[i].find(':')
            if pos != -1:
                continue
            opcode = symbol2opcode(line[0])
            if opcode is None:
                raise ValueError(f'There is no such instruction: {line[0]}')
            # instructions with no operand
            if len(line) == 1:
                arg = None
            else:
                if line[1].isnumeric():
                    arg = int(line[1])
                else:
                    # Replace label with position in data memory or instruction memory
                    arg = self.label_pos[line[1]]
            self.instructions.append({
                'opcode' : f'{opcode}',
                'arg' : f'{arg}',
                'pos_in_instr_mem': f'{counter}'
            })
            counter += 1
