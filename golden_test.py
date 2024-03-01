import contextlib
import io
import logging
import os
import tempfile

import pytest

from isa import load_code_data
from machine import simulation
from translator import Translator


@pytest.mark.golden_test("golden/*.yml")
def test_translator_and_machine(golden):
    with tempfile.TemporaryDirectory() as tmpdirname:
        source = os.path.join(tmpdirname, "source.asm")
        instr = os.path.join(tmpdirname, "instr.json")
        data = os.path.join(tmpdirname, "data.json")

        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])

        t = Translator(source, instr, data)

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(f"{__name__}.log", mode="w")
        formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            t.translate()
            code_p, d = load_code_data(instr, data)
            code_isr, d_isr = load_code_data("static/isr/instr.json", "static/isr/data.json")
            print("============================================================")
            simulation(100000, code_p, d, code_isr, d_isr, golden["in_stdin"])
        with open(instr, encoding="utf-8") as f:
            code = f.read()

        with open(data, encoding="utf-8") as f:
            data = f.read()

        with open("machine.log", encoding="utf-8") as f:
            log = f.read()

        assert code == golden.out["out_code"]
        #assert data == golden.out["out_data"]

        assert stdout.getvalue() == golden.out["out_stdout"]
        assert log == golden.out["out_log"]
