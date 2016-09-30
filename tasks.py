from __future__ import print_function

import os
import errno
import shutil
import webbrowser
import urlparse
import urllib

from invoke import task

ROOT = os.path.abspath(os.path.dirname(__file__))

def fileurl(path):
    path = os.path.abspath(path)
    return urlparse.urljoin('file:', urllib.pathname2url(path))


@task
def clean(ctx):
    rm_targets = ['build', 'dist', 'autolycus.egg-info']

    for t in rm_targets:
        try:
            print('removing {}...'.format(t), end=' ')
            shutil.rmtree(os.path.join(ROOT, t))
            print('OK.')
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            print('already gone.')

    ctx.run('coverage erase')

@task
def build(ctx):
    ctx.run('python setup.py sdist bdist_wheel')


@task
def install(ctx):
    if int(os.environ.get('INSTALL_WHEEL', 0)):
        print('installing bdist_wheel...')
        ctx.run('pip install dist/autolycus-*.whl')
    else:
        print('installing sdist...')
        ctx.run('pip install dist/autolycus-*.tar.gz')


# def covpth():
#     from distutils.sysconfig import get_python_lib
#     return os.path.join(get_python_lib(), 'covhook.pth')
#
#
# @task
# def hook_coverage(ctx):
#     with open(covpth(), 'w') as f:
#         f.write('import coverage; coverage.process_startup()\n')
#
#
# @task
# def unhook_coverage(ctx):
#     try:
#         os.remove(covpth())
#     except OSError as e:
#         if e.errno != errno.ENOENT:
#             raise


@task
def test(ctx, coverage=False):
    cmd = 'nosetests test'
    if coverage:
        cmd += ' --with-coverage --cover-erase --cover-package=autolycus'

    ctx.run(cmd)

    if coverage:
        ctx.run('coverage xml')


@task
def report(ctx):
    ctx.run('coverage html')
    webbrowser.open_new_tab(fileurl(os.path.join(ROOT, 'coverage_html_report', 'index.html')))


@task
def publish(ctx):
    ctx.run('twine upload dist/*')
