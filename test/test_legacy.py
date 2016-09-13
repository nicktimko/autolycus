#!/usr/bin/python

# 2.7.3 on Ubuntu 12.04
from __future__ import print_function, unicode_literals

import sys
import subprocess
import functools


ccall = functools.partial(subprocess.check_call, shell=True)


def make_hg():
    ccall('hg init mercury')
    with open('mercury/a', 'wb') as f:
        f.write('apple\n'.encode('utf-8'))

    ccall('hg add a', cwd='mercury')
    ccall('hg commit -m "A"', cwd='mercury')

def test_content_preservation():
    make_hg()

    ccall('git init venus')
    ccall('shelley -r ../mercury', cwd='venus')
