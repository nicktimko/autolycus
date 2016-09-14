import os
from setuptools import setup

import autolycus

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='autolycus',
    version=autolycus.__version__,
    author='Nick Timkovich',
    author_email='prometheus235@gmail.com',

    description='Exports/synchronizes a Mercurial repo to Git',
    long_description=read('README.rst'),
    license='GPLv2',

    packages=['autolycus'],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'shelley=autolycus.sync:main',
            'shelley_legacy=autolycus.legacy:main'
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
