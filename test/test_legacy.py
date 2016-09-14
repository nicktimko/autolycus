#!/usr/bin/python

# 2.7.3 on Ubuntu 12.04
from __future__ import print_function, unicode_literals

import sys
import os
import subprocess
import functools

from nose.tools import assert_equals

from support import ccall, callo, TemporaryDirectory

def coro(func):
    def _coro(*args, **kwargs):
        g = func(*args, **kwargs)
        g.send(None)
        return g
    return _coro

def hg_config(username=None):
    if username is None:
        username = 'Alice Applebaum <aappl@mercury.example>'

    with open(os.path.expanduser('~/.hgrc'), 'w') as f:
        f.write('\n'.join([
            '[ui]',
            'username = {}'.format(username),
            '',
        ]))


@coro
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
        hg_config()

        # the repo is born!
        source_repo = make_hg()

        ccall('git init venus --quiet')

        ccall('shelley_legacy -r ../mercury', cwd='venus')
        assert_equals(callo('git show HEAD:a', cwd='venus'), 'apple\n'.encode('utf-8'))

        author, email = callo('git log -1 --pretty="%an|||%ae"', cwd='venus').split('|||')
        assert_equals(author.strip(), 'Alice Applebaum')
        assert_equals(email.strip(), 'aappl@mercury.example')

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


def test_bad_hg_name():
    with TemporaryDirectory() as td:
        os.chdir(td)
        hg_config('Malcom Prenom (creative@syntax.example)')

        source_repo = make_hg()

        ccall('git init venus --quiet')

        ccall('shelley_legacy -r ../mercury', cwd='venus')

        author, email = callo('git log -1 --pretty="%an|||%ae"', cwd='venus').split('|||')
        try:
            assert_equals(author.strip(), 'Malcom Prenom')
            assert_equals(email.strip(), 'creative@syntax.example')
        except AssertionError:
            pass
        else:
            raise AssertionError('git magically parsed malformed name??')


def test_bad_name_mapping_fix():
    with TemporaryDirectory() as td:
        os.chdir(td)
        hg_config('Malcom Prenom (creative@syntax.example)')

        source_repo = make_hg()

        ccall('git init venus --quiet')

        with open('author_map.txt', 'w') as f:
            f.write('Malcom Prenom (creative@syntax.example)=Malcom Prenom <creative@syntax.example>\n')

        ccall('shelley_legacy -r ../mercury -A ../author_map.txt', cwd='venus')

        author, email = callo('git log -1 --pretty="%an|||%ae"', cwd='venus').split('|||')
        assert_equals(author.strip(), 'Malcom Prenom')
        assert_equals(email.strip(), 'creative@syntax.example')
