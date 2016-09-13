#!/usr/bin/python

# 2.7.3 on Ubuntu 12.04
from __future__ import print_function, unicode_literals

import sys
import os
import subprocess
import functools

from support import ccall, TemporaryDirectory


def make_hg():
    ccall('hg init mercury')
    with open('mercury/a', 'wb') as f:
        f.write('apple\n'.encode('utf-8'))

    ccall('hg add a', cwd='mercury')
    ccall('hg commit -m "A"', cwd='mercury')


def test_content_preservation():
    with TemporaryDirectory() as td:
        os.chdir(td)

        make_hg()

        ccall('git init venus')
        ccall('shelley_legacy -r ../mercury', cwd='venus')
