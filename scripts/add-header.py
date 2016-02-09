#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# add_header.py -i py-file-header.txt <python files>

import argparse
import fileinput

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True, type=argparse.FileType('rb'))
    parser.add_argument('source_files', nargs=argparse.REMAINDER)

    args = parser.parse_args()

    for line in fileinput.input(args.source_files, inplace=True):
        print line
