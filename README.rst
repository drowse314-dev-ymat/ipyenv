ipyenv
~~~~~~

ipyenv is a simple and poor environment supplyer for Python development
in the most restrictive environments, such as lacking virtualenv or nose.
And still you don't want to use pip, easy_install or setup.py in the global
context!

It provides an import path environment(instead of providing a comprehensive
environment like virtualenv), with a simple test finder & runner.

Though the main target would be IronPython, it also works with CPython.
All written in pure Python!

Usage: Library environment
--------------------------

Suppose you have your source tree below, and put ``ipyenv.py`` on the
project root.::

    project/
    |-- ipyenv.py
    |-- runner_script.py
    |-- package
    |   |-- __init__.py
    |   |-- mod_top.py
    |   `-- subpkg
    |       |-- __init__.py
    |       `-- mod_inner.py
    |-- sitelib
    |   |-- .sitelibs
    |   |-- package_wrapping_dir
    |   |   `-- ...
    |   `-- your_favorite_package
    |       `-- ...
    `-- tests
        |-- .testfor
        |-- sub
        |   `-- test_mod_inner.py
        `-- test_mod_top.py

Remember you can just copy ``ipyenv.py`` to your project to apply it (we
assume that you can access no library management tools or libraries).

Configure ``.sitelibs`` under ``sitelib`` directory for your favorite modules
or packages.  Just write up a relative path (to ``sitelib`` dir.) per line in
``.sitelibs``, **FROM WHICH YOU CAN IMPORT** ones (NOT the packege root dirs, etc.).
For this project it would be like::

    ./
    ./package_wrapping_dir

After this, you can import everything in ``sitelib`` through ipyenv.py.
Suppose ``package.mod_top`` imports one of these, then ``runner_script.py``
imports ``package.mod_top``, you can do as::

    $ ipy ipyenv.py shell
    (ipyenv interactive shell)
    >>> import your_favorite_package
    >>>    # OK!
    >>> from package import mod_top
    >>>    # OK!

and also::

   $ ipy ipyenv.py exec runner_script.py
   
Usage: Test environment
-----------------------

Suppose the same project source tree.

Configure ``.testfor`` under ``tests`` directory.  Similarly to ``.sitelibs``,
write up a relative path per line **FROM WHICH YOU CAN IMPORT** modules/packages
the tests want to import for testing.  For this project it would be simply like::

    ../

Then you can execute all tests (named '^[Tt]est.*\.py$') with::

    $ ipy ipyenv.py test

or with a test script path::

    $ ipy ipyenv.py test -n tests/test_mod_top.py

In this way, test scripts must provide command-line interfaces like ``unittest.main``.
If you do not want to write those extra lines you should add some options::

    $ ipy ipyenv.py test --autoexec -v <verbosity>

Test cases loaded with this option equal to those when you write up::

    if __name__ == '__main__:
        from unittest import main
        main(verbosity=<verbosity>)

at the bottom of your test scripts.

Setup with configuration
------------------------

You can setup ``ipyenv`` as your environment by putting  a configuration
file named ``.ipyenvrc`` in the same directory as ``ipyenv.py``, which looks like
the following::

    # library extension
    [libext]
    extdirs=./sitelib
    # test runner configurations
    [test]
    extdirs=./sitelib
    testdirs=./tests
    autoexec=on
    verbosity=2

If you want to set multiple paths, separate with ';' like::

    extdirs=./sitelib1;./sitelib2;...

Further information
-------------------

Please type like::

    $ ipy ipyenv.py -h

or::

    $ ipy ipyenv.py shell -h

etc.

Additionally we recommend that you let your VCS ignore ``ipyenv.py`` and ``/sitelib/*``
except ``.sitelibs`` :).
