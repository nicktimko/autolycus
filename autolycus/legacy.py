# coding: utf-8
from __future__ import absolute_import, print_function

# stdlib
import sys
import os
import argparse
import subprocess
import shlex

# third party
import pkg_resources # setuptools


HFE_SH = pkg_resources.resource_filename('autolycus', 'sh/hg-fast-export.sh')


def main():
    parser = argparse.ArgumentParser(description=
        'Import Hg repository <repo> up to either tip or <max>. If <repo> '
        'is omitted, use last hg repository as obtained from state file, '
        'GIT_DIR/hg2git-state by default.')

    parser.add_argument('-r', '--repo', type=str, help='Mercurial repository to import')
    parser.add_argument('-A', '--authors-map', type=str, help='Author mapping file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output from git-fast-import')

    args = parser.parse_args()

    subprocess.check_call(shlex.split('/bin/sh {script} {quiet} {repo} {authors}'.format(
        script=HFE_SH,
        repo='-r {}'.format(args.repo) if args.repo else '',
        authors='-A {}'.format(args.authors_map) if args.authors_map else '',
        quiet='' if args.verbose else '--quiet',
    )), cwd=os.getcwd())


if __name__ == '__main__':
    sys.exit(main())
