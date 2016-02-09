#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# add_header.py -i py-file-header.txt <python files>
# find . -name '*.py' | xargs python ../../scripts/add-header.py -i ../../scripts/py-file-header.txt

import argparse
import fileinput

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, type=argparse.FileType('rb'))
    parser.add_argument('source_files', nargs=argparse.REMAINDER)

    args = parser.parse_args()
    header_lines = [l for l in args.input]
    new_header_written = False

    for line in fileinput.input(args.source_files, inplace=True):
        if fileinput.isfirstline():
            new_header_written = False

        if (line.startswith('#!')
                or line.startswith('# -*- coding')
                or line.startswith('# Author')):
            continue

        if not new_header_written:
            for header_line in header_lines:
                print header_line,
            new_header_written = True

        print line,
