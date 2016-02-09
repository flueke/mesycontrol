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
    old_header_seen    = False
    new_header_written = False
    header_starts = ['#', '__author__', '__email__']

    for line in fileinput.input(args.source_files, inplace=True):
        if fileinput.isfirstline():
            old_header_seen    = False
            new_header_written = False

        if not old_header_seen:
            if any((line.startswith(s) for s in header_starts)):
                continue
            else:
                old_header_seen = True

        if old_header_seen and not new_header_written:
            for header_line in header_lines:
                print header_line,
            new_header_written = True

        print line,
