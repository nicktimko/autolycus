import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='asdf',
    version='0.0.1',
    author='Hermes',
    author_email='hermes@olympus.gr',

    description='Exports a Mercurial repo to Git',
    long_description=read('README.md'),
    license='GPLv2',

    packages=['asdf'],
    entry_points={
        'console_scripts': [
            'hg-fast-export=asdf.hg_fast_export.main',
            'hg-reset=asdf.hg_reset.main',
        ],
    },

    install_requires=[
        'mercurial',
    ],

    url='http://github.com/nicktimko/fast-export',
    keywords='mercurial git vcs dvcs',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
    ],
)
