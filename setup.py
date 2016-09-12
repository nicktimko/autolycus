import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='autolycus',
    version='0.0.4',
    author='Hermes & Chione',
    author_email='hermes@olympus.gr',

    description='Exports a Mercurial repo to Git',
    long_description=read('README.md'),
    license='GPLv2',

    packages=['autolycus'],
    entry_points={
        'console_scripts': [
            'shelley=autolycus.hg_fast_export:main',
            # 'hg-reset=autolycus.hg_reset:main',
        ],
    },

    install_requires=[
        'mercurial',
    ],

    url='http://github.com/nicktimko/autolycus',
    keywords='mercurial git vcs dvcs',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 2 :: Only',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
    ],
)
