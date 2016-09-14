#!/usr/bin/python

# 2.7.3 on Ubuntu 12.04
from __future__ import print_function, unicode_literals

import sys
import os
import subprocess
import functools

from nose.tools import assert_equals

from support import ccall, callo, TemporaryDirectory

def hg_config():
    with open(os.path.expanduser('~/.hgrc'), 'w') as f:
        f.write('''\
[ui]
username = Alice Applebaum <aappl@mercury.example>
''')
hg_config()


def make_hg():
    ccall('hg init mercury')
    with open('mercury/a', 'wb') as f:
        f.write('apple\n'.encode('utf-8'))

    ccall('hg add a', cwd='mercury')
    ccall('hg commit -m "1. add A"', cwd='mercury')

    yield {'a': 'apple\n'}

    with open('mercury/b', 'wb') as f:
        f.write('chom-chom\n'.encode('utf-8'))
    ccall('hg add b', cwd='mercury')
    ccall('hg commit -m "2. for scale"', cwd='mercury')

    with open('mercury/a', 'wb') as f:
        f.write('apricot\n'.encode('utf-8'))
    ccall('hg add a', cwd='mercury')
    ccall('hg commit -m "3. different"', cwd='mercury')

    yield {'a': 'apricot\n', 'b': 'chom-chom\n'}


def test_suite():
    with TemporaryDirectory() as td:
        os.chdir(td)
        source_repo = make_hg()\

        # the repo hatches!
        source_repo.send(None)

        ccall('git init venus --quiet')

        ccall('shelley_legacy -r ../mercury', cwd='venus')
        assert_equals(callo('git show HEAD:a', cwd='venus'), 'apple\n'.encode('utf-8'))

        # repo is evolving!
        source_repo.send(None)

        ccall('shelley_legacy', cwd='venus')
        # should update without -r using the repo it's recorded in its metadata
        assert_equals(
            callo('git show HEAD:a', cwd='venus'),
            'apricot\n'.encode('utf-8')
        )
        assert_equals(
            callo('git log -1 --pretty=%B', cwd='venus').rstrip('\n'),
            '3. different'.encode('utf-8')
        )
