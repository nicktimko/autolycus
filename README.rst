Autolycus - Mercurial to Git converter
===============================================

.. image:: https://img.shields.io/travis/nicktimko/autolycus.svg?maxAge=2592000?style=flat-square   :target: https://travis-ci.org/nicktimko/autolycus

.. image:: https://img.shields.io/codecov/c/github/nicktimko/autolycus.svg?maxAge=2592000?style=flat-square   :target: https://codecov.io/gh/nicktimko/autolycus

.. image:: https://img.shields.io/pypi/v/autolycus.svg?maxAge=2592000?style=flat-square   :target:  https://pypi.python.org/pypi/autolycus

Usage
-----

Using ``hg-fast-export`` is quite simple for a Mercurial repository :

::

    mkdir repo-git # or whatever
    cd repo-git
    git init
    hg-fast-export.sh -r <repo>

Please note that ``hg-fast-export`` does not automatically check out the newly imported repository. You probably want to follow up the import with a ``git checkout``-command.

Incremental imports to track hg repos is supported, too.

Using ``hg-reset`` it is quite simple within a Git repository that is ``hg-fast-export``\ 'ed from Mercurial:

::

    hg-reset.sh -R <revision>

will give hints on which branches need adjustment for starting over again.

When a Mercurial repository does not use UTF-8 for encoding author strings and commit messages the ``-e <encoding>`` command line option can be used to force fast-export to convert incoming meta data from to UTF-8. This encoding option is also applied to file names.

In some locales Mercurial uses different encodings for commit messages and file names. In that case, you can use ``--fe <encoding>`` command line option which overrides the ``-e`` option for file names.

As Mercurial appears to be much less picky about the syntax of the author information than Git, an author mapping file can be given to hg-fast-export to fix up malformed author strings. The file is specified using the ``-A`` option. The file should contain lines of the form ``FromAuthor=ToAuthor``. The example ``authors.map`` below will translate ``User <garbage<user@example.com>`` to ``User <user@example.com>``.

::

    -- Start of authors.map --
    User <garbage<user@example.com>=User <user@example.com>
    -- End of authors.map --

Tag and Branch Naming
---------------------

As Git and Mercurial have differ in what is a valid branch and tag name the ``-B`` and ``-T`` options allow a mapping file to be specified to rename branches and tags (respectively). The syntax of the mapping file is the same as for the author mapping.

Notes/Limitations
-----------------

``hg-fast-export`` supports multiple branches but only named branches with exactly one head each. Otherwise commits to the tip of these heads within the branch will get flattened into merge commits.

As each ``git-fast-import`` run creates a new pack file, it may be required to repack the repository quite often for incremental imports (especially when importing a small number of changesets per incremental import).

The way the Hg API and remote access protocol is designed it is not possible to use ``hg-fast-export`` on remote repositories (HTTP/SSH). First clone the repository, then convert it.

Mercurial `doesn't support Python 3`_ and probably won't for a while.

Design
------

``hg-fast-export.py`` was designed in a way that doesn't require a 2-pass mechanism or any prior repository analysis: if just feeds what it finds into `git-fast-import`. This also implies that it heavily relies on strictly linear ordering of changesets from Hg, i.e. its append-only storage model so that changesets `hg-fast-export` already saw never get modified.

.. _doesn't support Python 3: https://www.mercurial-scm.org/wiki/SupportedPythonVersions#Python_3.x_support
