from typing import Optional
import re

from isa import Opcode


class Translator:
    out_instructions_file_name: str
    out_data_file_name: str

    file_data: str

    def __init__(self, path_to_program: str, out_instructions_file_name: str, out_data_file_name: Optional[str]=None) -> None:


        self.out_instructions_file_name = out_instructions_file_name
        self.out_data_file_name = out_data_file_name
        self.file_data = self.read_data_from_file(path_to_program)

    
    def read_data_from_file(self, path_to_file: str) -> str :
        with open(path_to_file, 'r', encoding='utf-8') as f:
            data = f.read()
            print(data)
            return data
        
    def parser(self):
        self.skip()

    
    def skip(self):
        d = self.file_data.find('.data')
        if d == -1:
            d = self.file_data.find('.text')
        self.file_data = self.file_data[d:]





        
    




        






    def translate(self):
        pass
        

