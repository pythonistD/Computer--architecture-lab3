import logging
import argparse

from translator import Translator



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', metavar='INPUT', nargs='*', help='<file_with_programm> <file for encoded instructions> <file for encoded data>')
    args = parser.parse_args().inputs
    assert len(args) > 1, 'The number of arguments have to be at least 2'

    t = Translator(*args)
    t.translate()


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    main()