from __future__ import print_function

import os.path
import errno
import shutil

from invoke import task

ROOT = os.path.abspath(os.path.dirname(__file__))

@task
def clean(ctx):
    targets = ['build', 'dist', 'autolycus.egg-info']

    for t in targets:
        try:
            print('removing {}...'.format(t), end=' ')
            shutil.rmtree(os.path.join(ROOT, t))
            print('OK.')
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            print('already gone.')


@task
def build(ctx):
    ctx.run('python setup.py sdist bdist_wheel')


@task
def test(ctx):
    ctx.run('nosetests test')


@task
def publish(ctx):
    ctx.run('twine upload dist/*')
