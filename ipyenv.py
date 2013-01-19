# encoding: utf-8
"""
    ipyenv
    ~~~~~~

    A simple and poor environment supplyer for Python development.

    :copyright: (c) 2013 by drowse314-dev-ymat@github.com.
    :licence: BSD, see LICENCE for more details.
"""

import sys
import os
import re
import subprocess
import logging
import argparse
import functools
import operator
import tempfile
try:
    import ConfigParser as configparser
except ImportError:
    import configparser


__all__ = [
    'PathEnvironment',
    'LibraryEnvironment',
    'ConfiguredLibraryEnvironment',
    'TestProxy',
    'TestRunner',
    'ConfiguredTestRunner',
]

__version__ = '0.6.3'


# Config logger.
def create_logger(level=logging.INFO):
    logger = logging.getLogger('ipyenv')
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter('ipyenv(%(levelname)s): %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
logger = create_logger()


class PathEnvironment(object):
    """Context manager base to extend sys.path."""

    def __init__(self, ext_paths):
        self._ext_paths = ext_paths

    def __enter__(self):
        # Copy the original sys.path & switch.
        self._orig_paths = sys.path[:]
        sys.path.extend(self._ext_paths)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Rollback the original.
        sys.path = self._orig_paths[:]
        self._orig_paths = None
        del self._orig_paths

    @property
    def ext_paths(self):
        """Not to modify manually this property."""
        return self._ext_paths


def _find_rc(extdir_abspath, rc_filename):
    """Find rc path in given directory."""
    rcfile_path = os.sep.join((extdir_abspath, rc_filename))
    if not (os.path.exists(rcfile_path) and os.path.isfile(rcfile_path)):
        return None
    return rcfile_path

# Regular exp. for newline characters.
RE_NEWLINES = re.compile('[(?:\n)(?:\r\n)(?:\r)]+')

def _resolve_rcpath(path_repr, extdir_abspath):
    path_repr = RE_NEWLINES.sub('', path_repr)
    path_repr = path_repr.replace('/', os.sep)
    cat_path = os.sep.join((extdir_abspath, path_repr))
    return os.path.abspath(cat_path)

def _load_extdir(ext_dir, rcfile_encoding, rc_filename):
    """Load rc file & extract import paths to extend."""
    if not (os.path.exists(ext_dir) and os.path.isdir(ext_dir)):
        logger.error('extension directory "{}" not found'.format(ext_dir))
        return []
    ext_dir = os.path.abspath(ext_dir)
    # Get rc.
    rcfile_path = _find_rc(ext_dir, rc_filename)
    if rcfile_path is None:
        logger.error('{} in "{}" not found'.format(rc_filename, ext_dir))
        return []
    # Read out rc.
    library_paths = []
    with open(rcfile_path, 'rb') as rcfile:
        for line in rcfile:
            library_paths.append(_resolve_rcpath(line.decode(rcfile_encoding),
                                                 ext_dir))
    return list(set(library_paths))

def semicolon_to_dirlist(notation):
    """Semi-colon separated string to a directory list."""
    return [os.path.abspath(d.strip().replace('/', os.sep))
            for d in notation.split(';')]

BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                  '0': False, 'no': False, 'false': False, 'off': False}

def state_to_boolean(notation):
    """Boolean-state string to boolean."""
    if notation.lower() not in BOOLEAN_STATES:
        raise ValueError('Not a boolean: {}'.format(notation))
    return BOOLEAN_STATES[notation.lower()]

def configured(args_from_config=None):
    """
    Makes a wrapper for some environment class to instantiate with given
    configuration file. The argument `args_from_config` must be formed:
        {'section1.attrA': ('argument_nameA', attrA_converter_func),
         'section2.attrB': ('argumant_nameB', attrB_converter_func), ...}
    """
    def _wrapper(klass):
        if args_from_config is None:
            logger.warn('no arguments from configuration are set')
            return lambda klass, **kwargs: klass(**kwargs)
        def instantiate(config_path='./.ipyenvrc', **given_args):
            parser = configparser.ConfigParser()
            if not parser.read(config_path):
                logger.warn('configuration file not found: "{}"'.format(config_path))
                return klass(**given_args)
            kwargs_from_config = {}
            for config_opt in args_from_config:
                section, attribute = config_opt.split('.')
                name, converter = args_from_config[config_opt]
                try:
                    kwargs_from_config[name] = converter(parser.get(section, attribute))
                except configparser.NoSectionError:
                    pass
                except configparser.NoOptionError:
                    pass
            # Given arguments precede.
            kwargs_from_config.update(given_args)
            return klass(**kwargs_from_config)
        instantiate.__doc__ = klass.__doc__
        return instantiate
    return _wrapper


class LibraryEnvironment(PathEnvironment):
    """
    Context manager for appending on the fly
    modules/packeges import paths.
    """

    def __init__(self, sitelib_paths=('./sitelib',), rcfile_encoding='utf-8'):
        # Load .sitelib files.
        library_paths = []
        for sitelib_dir in sitelib_paths:
            library_paths.extend(_load_extdir(sitelib_dir, rcfile_encoding, '.sitelibs'))
        PathEnvironment.__init__(self, library_paths)


@configured(args_from_config={
                'libext.extdirs': ('sitelib_paths', semicolon_to_dirlist),
            })
class ConfiguredLibraryEnvironment(LibraryEnvironment):
    """LibraryEnvironment configured with .ipyenvrc."""
    pass


def _get_module_from_path(target_filename, env):

    path_components = os.path.split(target_filename)
    local_name = path_components[-1]
    dir_path = os.path.sep.join(path_components[:-1])
    module_name = os.path.extsep.join(local_name.split(os.path.extsep)[:-1])

    ext_paths = []
    ext_paths.append(dir_path)
    ext_paths.extend(env.ext_paths)
    with PathEnvironment(ext_paths=ext_paths):
        module = __import__(module_name)
    return module


def _execute_file(target_filename, env=None, load_module=True):
    """
    Execute the target file via `exec`/`execfile`,
    along with the current sys.path environment.
    """
    if load_module:
        # Almost all objects in the target module
        # are visible from `__main__`.
        assert env is not None, \
            'Path environment object is needed to preload file as module.'
        main = __import__('__main__')
        target_module = _get_module_from_path(target_filename, env)
        for name in dir(target_module):
            setattr(main, name, getattr(target_module, name))
    global_vars = {
        'sys': sys,
        '__name__': '__main__',
        '__file__': target_filename,
    }
    if hasattr(__builtins__, 'execfile'):
        execfile(target_filename, global_vars)
    else:
        exec(compile(open(target_filename).read(),
                     target_filename, 'exec'),
             global_vars)


class RWFreeNamedTempFile(object):
    """
    Context manager for creating a temporary file using
    tempfile.NamedTemporaryFile, accessible without no locks
    on R/W operations (since already closed), removed on exit.
    """

    def __init__(self, source='', target_dir='./', encoding='utf-8'):
        self._source = source
        self._target_dir = target_dir
        self._encoding = encoding

    def __enter__(self):
        tempf = tempfile.NamedTemporaryFile(
            mode='wb',
            delete=False,
            dir=self._target_dir
        )
        tempf.write(self._source.encode(self._encoding))
        tempf.close()
        self._tempf_name = tempf.name
        return tempf.name

    def __exit__(self, exc_type, exc_value, traceback):
        while True:
            try:
                os.unlink(self._tempf_name)
                break
            except OSError:
                continue


class TestProxy(RWFreeNamedTempFile):
    """
    Context manager for creating execution proxy script
    for isolated test environment.
    """

    # Script format to create on the fly.

    PROXY_FORMAT_COMMON = (
"""\
# encoding: utf-8
import ipyenv
import os
import sys
test_env = ipyenv.PathEnvironment(ext_paths={ext_paths})
{exec_stmt}\
"""
    )

    PROXY_FORMAT_EXEC = (
"""\
target = '{target_filepath}'
sys.argv = [target.split(os.sep)[-1]]
append_main = {append_main}
with test_env as te:
    ipyenv._execute_file(target, te)
    if append_main:
        import unittest
        unittest.main(verbosity={verbosity})\
"""
    )

    def __init__(self, target_filepath, ext_paths=tuple(),
                 append_main=False, verbosity=1):
        # All paths are desired to be absolute.
        ext_paths = [path for path in ext_paths]  # accept iterator, etc.
        exec_stmt = self.PROXY_FORMAT_EXEC.format(
            target_filepath=target_filepath,
            append_main=append_main,
            verbosity=verbosity,
        )
        script = self.PROXY_FORMAT_COMMON.format(ext_paths=ext_paths,
                                           exec_stmt=exec_stmt)
        RWFreeNamedTempFile.__init__(self, source=script)


class TestRunner(object):
    """
    Implements test runner functionality.
    Uses PathEnvironment as environment supplyer.
    """

    def __init__(self, test_paths=('./tests',), sitelib_paths=('./sitelib',),
                 rcfile_encoding='utf-8', append_main=False, verbosity=1,
                 suite_autoload=False):
        # Extend common library pahts.
        self._library_paths = []
        for sitelib_dir in sitelib_paths:
            self._library_paths.extend(_load_extdir(sitelib_dir, rcfile_encoding, '.sitelibs'))
        # Find tests with extension config. recursively.
        self._tests = {}        # context => tests
        self._ext_paths = {}    # context => extension paths(test target paths)
        for test_dir in test_paths:
            if not (os.path.exists(test_dir) and os.path.isdir(test_dir)):
                logger.error('tests directory "{}" not found'.format(test_dir))
                continue
            test_dir = os.path.abspath(test_dir)
            self._tests[test_dir] = self._find_tests(test_dir)
            self._ext_paths[test_dir] = _load_extdir(test_dir, rcfile_encoding, '.testfor')
        # Save extra arguments.
        if append_main is True and suite_autoload is True:
            raise RuntimeError('confusing auto-exec options')
        self._append_main = append_main
        self._suite_autoload = suite_autoload
        self._verbosity = verbosity

    # Test script filename patterns.
    RE_TEST_SCRIPT_NAME = re.compile('^[Tt]est.*\.py$')

    def _find_tests(self, test_dir):
        """Find recursively test scripts under the given path."""
        test_paths = []
        for root, dirs, files in os.walk(test_dir):
            for filename in files:
                if self.RE_TEST_SCRIPT_NAME.search(filename):
                    test_paths.append(os.sep.join((root, filename)))
        return test_paths

    def execute_all(self):
        """Execute all tests found."""
        library_paths = self._library_paths
        for context, tests in self._tests.items():
            # Setup full extension paths set.
            ext_paths = self._ext_paths[context]
            ext_paths.extend(library_paths)
            if self._suite_autoload:
                self._run_testsuites(
                    tests,
                    ext_paths=ext_paths,
                    verbosity=self._verbosity,
                )
            else:
                # Iterate over tests.
                for testfile_path in tests:
                    self._execute_test(testfile_path, ext_paths=ext_paths,
                                       append_main=self._append_main,
                                       verbosity=self._verbosity)

    def execute_by_path(self, testfile_path):
        """Execute a specifiv test by given path."""
        abs_testfile_path = os.path.abspath(testfile_path.replace('/', os.sep))
        for context, tests in self._tests.items():
            # Find given path.
            for test_path in tests:
                if test_path == abs_testfile_path:
                    # Setup full extension paths set.
                    ext_paths = self._ext_paths[context]
                    ext_paths.extend(self._library_paths)
                    if self._suite_autoload:
                        self._run_testsuites(
                            [test_path],
                            ext_paths=ext_paths,
                            verbosity=self._verbosity,
                        )
                    else:
                        self._execute_test(abs_testfile_path, ext_paths=ext_paths,
                                           append_main=self._append_main,
                                           verbosity=self._verbosity)
                    return
            # If the path not found.
            logger.error('test not found: {}'.format(abs_testfile_path))

    def _escape_path(self, path):
        """Path separator escaping in Windows."""
        return path.replace('\\', '\\\\')

    def _execute_test(self, testfile_path, ext_paths=tuple(),
                      append_main=False, verbosity=1):
        """
        Execute test script, with invoking executable
        & given paths extension by subprocessing.
        """
        logger.info('will execute test: {}'.format(testfile_path))
        ext_paths = [path for path in ext_paths]  # accept iterator, etc.
        # `_escape_path` only applied to  `testfile_path`:
        #     Built-in `open` never accepts unescaped special characters,
        #     while a sequence of `list.__repr__` -> `str.format` does.
        with TestProxy(self._escape_path(testfile_path),
                       ext_paths=ext_paths,
                       append_main=append_main,
                       verbosity=verbosity) as proxy_filename:
            subprocess.call([sys.executable, proxy_filename])

    def _run_testsuites(self, testfile_paths, ext_paths=tuple(), verbosity=1):
        """
        Execute tests, by aggregating test suites from target scripts,
        & running with given paths extension.
        """
        import unittest
        loader = unittest.TestLoader()
        ext_paths = [path for path in ext_paths]  # accept iterator, etc.
        with PathEnvironment(ext_paths=ext_paths) as env:
            suites = []
            for testfile_path in testfile_paths:
                logger.info('load test suites from: {}'.format(testfile_path))
                test_module = _get_module_from_path(testfile_path, env)
                suites.append(loader.loadTestsFromModule(test_module))
            aggregated = unittest.TestSuite(suites)
            unittest.TextTestRunner(verbosity=verbosity).run(aggregated)

    @property
    def ext_paths(self):
        """Not to modify manually this property."""
        return functools.reduce(operator.add,
                                [list(dirs) for dirs in self._ext_paths.values()]) \
               + self._library_paths


@configured(args_from_config={
                'test.testdirs': ('test_paths', semicolon_to_dirlist),
                'test.extdirs': ('sitelib_paths', semicolon_to_dirlist),
                'test.appendmain': ('append_main', state_to_boolean),
                'test.autoexec': ('suite_autoload', state_to_boolean),
                'test.verbosity': ('verbosity', int),
            })
class ConfiguredTestRunner(TestRunner):
    """TestRunner configured with .ipyenvrc."""
    pass


def shell():
    """Make an interactive shell with given extension paths."""
    # CLI configs.
    parser = argparse.ArgumentParser(
        description='ipyenv v{}: shell with a supplied environment'.format(__version__)
    )
    parser.add_argument('shell') # ignore this.
    parser.add_argument('-l', '--libext', help='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', help='.sitelibs file encoding')
    args = parser.parse_args()
    # Invoke a shell.
    kwargs = {}
    if args.libext:
        kwargs['sitelib_paths'] = args.libext
    if args.encoding:
        kwargs['rcfile_encoding'] = args.encoding
    import code
    with ConfiguredLibraryEnvironment(**kwargs):
        ic = code.InteractiveConsole()
        try:
            ic.interact('(ipyenv interactive shell)')
        except SystemExit as ex:
            print('(Terminate ipyenv shell)')

def execute():
    """Execute a script with given extension paths."""
    # CLI configs.
    parser = argparse.ArgumentParser(
        description='ipyenv v{}: execute scripts with a supplied environment'.format(__version__)
    )
    parser.add_argument('exec') # ignore this.
    parser.add_argument('target_script')
    parser.add_argument('-l', '--libext', help='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', help='.sitelibs file encoding')
    args = parser.parse_args()
    target = args.target_script
    if not os.path.exists(target):
        logger.error('target script not found: {}'.format(target))
        return
    # Execute target.
    kwargs = {}
    if args.libext:
        kwargs['sitelib_paths'] = args.libext
    if args.encoding:
        kwargs['rcfile_encoding'] = args.encoding
    with ConfiguredLibraryEnvironment(**kwargs) as env:
        sys.argv = [target.split(os.sep)[-1]]
        _execute_file(target, env)

def test():
    """Execute tests with given extension paths."""
    # CLI configs.
    parser = argparse.ArgumentParser(
        description='ipyenv v{}: Execute test scripts with a supplied environment'.format(__version__)
    )
    parser.add_argument('test') # ignore this.
    parser.add_argument('-n', '--name', help='target test script name/path')
    parser.add_argument('-t', '--testdir', help='target test directory paths', nargs='*')
    parser.add_argument('-l', '--libext', help='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', help='.sitelibs file encoding')
    parser.add_argument('--appendmain', action='store_true', default=False,
                        help='auto-exec tests by appending command-line interfaces to test scripts '
                             '(exec twice if originally provided)')
    parser.add_argument('-a', '--autoexec', action='store_true', default=False,
                        help='auto-exec tests without command-line interfaces on scripts by test-suites loading '
                             '(exec twice if originally provided)')
    parser.add_argument('-v', '--verbosity', type=int, help='verbosity for unittest.main')
    args = parser.parse_args()
    # Execute target.
    kwargs = {}
    if args.testdir:
        kwargs['test_paths'] = args.testdir
    if args.libext:
        kwargs['sitelib_paths'] = args.libext
    if args.encoding:
        kwargs['rcfile_encoding'] = args.encoding
    if args.appendmain:
        # Append-main option precedes if provided.
        kwargs['append_main'] = args.appendmain
        kwargs['suite_autoload'] = False
    elif args.autoexec:
        kwargs['suite_autoload'] = args.autoexec
    if args.verbosity:
        kwargs['verbosity'] = args.verbosity
    test_runner = ConfiguredTestRunner(**kwargs)
    if args.name:
        test_runner.execute_by_path(args.name)
    else:
        test_runner.execute_all()


if __name__ == '__main__':
    # Command-line interfaces.
    parser = argparse.ArgumentParser(
        description='ipyenv v{}: A simple and poor environment supplyer for Python development'.format(__version__)
    )
    # Action routings.
    actions = (
        'shell',
        'exec',
        'test',
    )
    action_funcs = {
        'shell': shell,
        'exec': execute,
        'test': test,
    }
    parser.add_argument('action',
                        help='ACTION: ( {} )'.format(', '.join(actions)),
                        choices=actions)
    # Parse & execute.
    args = parser.parse_args(sys.argv[1:2])
    action_funcs[args.action]()
