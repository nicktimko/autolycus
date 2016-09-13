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

    args = parser.parse_args()

    subprocess.check_call(shlex.split('/bin/sh {script} {repo}'.format(
        script=HFE_SH,
        repo='-r {}'.format(args.repo) if args.repo else '',
    )), cwd=os.getcwd())


if __name__ == '__main__':
    sys.exit(main())
