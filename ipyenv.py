# encoding: utf-8

import sys
import os
import re
import subprocess
import logging
import argparse
try:
    import ConfigParser as configparser
except ImportError:
    import configparser


__all__ = [
    'PathEnvironment',
    'LibraryEnvironment',
    'TestProxy',
    'TestRunner',
]

__version__ = 0.1


# Config logger.
logging.basicConfig(format='ipyenv(%(levelname)s): %(message)s',
                    level=logging.INFO)


class PathEnvironment(object):
    """Context manager base to extend sys.path."""

    def __init__(self, ext_paths):
        self._ext_paths = ext_paths

    def __enter__(self):
        # Copy the original sys.path & switch.
        self._orig_paths = sys.path[:]
        sys.path.extend(self._ext_paths)

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
        logging.error('extension directory "{}" not found'.format(ext_dir))
        return []
    ext_dir = os.path.abspath(ext_dir)
    # Get rc.
    rcfile_path = _find_rc(ext_dir, rc_filename)
    if rcfile_path is None:
        logging.error('{} in "{}" not found'.format(rc_filename, ext_dir))
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

def configured(args_from_config=None):
    """
    Makes a wrapper for  some environment class to instantiate with given
    configuration file. The argument `args_from_config` must be formed:
        {'section1.attrA': ('attrA', attrA_converter_func),
         'section2.attrB': ('attrB', attrB_converter_func), ...}
    """
    def _wrapper(klass):
        if args_from_config is None:
            logging.warn('no arguments from configuration are set')
            return lambda klass: klass()
        def instantiate(config_path='./.ipyenvrc', **given_args):
            parser = configparser.ConfigParser()
            if not parser.read(config_path):
                logging.warn('configuration file not found: "{}"'.format(config_path))
                return klass(**given_args)
            kwargs_from_config = {}
            for config_opt in args_from_config:
                section, attribute = config_opt.split('.')
                name, converter = args_from_config[config_opt]
                kwargs_from_config[name] = converter(parser.get(section, attribute))
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


# Test script filename patterns.
RE_TEST_SCRIPT_NAME = re.compile('^[Tt]est.*')

def _find_tests(test_dir):
    """Find recursively test scripts under the given path."""
    test_paths = []
    for root, dirs, files in os.walk(test_dir):
        for filename in files:
            if RE_TEST_SCRIPT_NAME.search(filename):
                test_paths.append(os.sep.join((root, filename)))
    return test_paths


class TestProxy(object):
    """
    Context manager for creating execution proxy script
    for isolated test environment.
    """

    # Script format to create on the fly.
    TEST_PROXY_FORMAT = (
        """
# encoding: utf-8
import ipyenv
import os
import sys
target = '{target_filepath}'
sys.argv = [target.split(os.sep)[-1]]
test_env = ipyenv.PathEnvironment(ext_paths={ext_paths})
with test_env as te:
    try:
        execfile(target)
    except NameError:
        exec(compile(open(target).read(),
                     target, 'exec'))
"""
    )

    def __init__(self, target_filepath, ext_paths=tuple()):
        # All paths are desired to be absolute.
        ext_paths = [path for path in ext_paths]  # accept iterator, etc.
        self._script = self.TEST_PROXY_FORMAT.format(ext_paths=ext_paths,
                                                     target_filepath=target_filepath)
        self._target = target_filepath.split(os.sep)[-1]

    def __enter__(self):
        proxy_name = '.' + self._target + '.testproxy'
        while os.path.exists(proxy_name):
            proxy_name += '.temp'
        proxy_name = os.path.abspath(proxy_name)
        with open(proxy_name, 'wb') as proxy:
            proxy.write(self._script.encode('utf-8'))
        self._proxy_name = proxy_name
        return proxy_name

    def __exit__(self, exc_type, exc_value, traceback):
        os.remove(self._proxy_name)


def _escape_path(path):
    """Path separator escaping in Windows."""
    return path.replace('\\', '\\\\')

def _execute_test(testfile_path, ext_paths=tuple()):
    """
    Execute test script, with invoking executable
    & given path sextension by subprocessing.
    """
    logging.info('will execute test: {}'.format(testfile_path))
    ext_paths = [path for path in ext_paths]  # accept iterator, etc.
    # `_escape_path` only applied to  `testfile_path`:
    #     Built-in `open` never accepts unescaped special characters,
    #     while a sequence of `list.__repr__` -> `str.format` does.
    with TestProxy(_escape_path(testfile_path),
                   ext_paths=ext_paths) as proxy_filename:
        subprocess.call([sys.executable, proxy_filename])


class TestRunner(object):
    """
    Implements test runner functionality.
    Uses PathEnvironment as environment supplyer.
    """

    def __init__(self, test_paths=('./tests',), sitelib_paths=('./sitelib',),
                 rcfile_encoding='utf-8'):
        # Extend common library pahts.
        self._library_paths = []
        for sitelib_dir in sitelib_paths:
            self._library_paths.extend(_load_extdir(sitelib_dir, rcfile_encoding, '.sitelibs'))
        # Find tests with extension config. recursively.
        self._tests = {}        # context => tests
        self._ext_paths = {}    # context => extension paths(test target paths)
        for test_dir in test_paths:
            if not (os.path.exists(test_dir) and os.path.isdir(test_dir)):
                logging.error('tests directory "{}" not found'.format(test_dir))
                continue
            test_dir = os.path.abspath(test_dir)
            self._tests[test_dir] = _find_tests(test_dir)
            self._ext_paths[test_dir] = _load_extdir(test_dir, rcfile_encoding, '.testfor')

    def execute_all(self):
        """Execute all tests found."""
        library_paths = self._library_paths
        for context, tests in self._tests.items():
            # Setup full extension paths set.
            ext_paths = self._ext_paths[context]
            ext_paths.extend(library_paths)
            # Iterate over tests.
            for testfile_path in tests:
                _execute_test(testfile_path, ext_paths=ext_paths)

    def execute_by_path(self, testfile_path):
        """Execute a specifiv test by given path."""
        abs_testfile_path = os.path.abspath(testfile_path)
        for context, tests in self._tests.items():
            # Find given path.
            for test_path in tests:
                if test_path == abs_testfile_path:
                    # Setup full extension paths set.
                    ext_paths = self._ext_paths[context]
                    ext_paths.extend(self._library_paths)
                    _execute_test(abs_testfile_path, ext_paths=ext_paths)
                    return
            # If the path not found.
            logging.error('test not found: {}'.format(abs_testfile_path))

    @property
    def ext_paths(self):
        """Not to modify manually this property."""
        return self._ext_paths


@configured(args_from_config={
                'test.testdirs': ('test_paths', semicolon_to_dirlist),
                'test.extdirs': ('sitelib_paths', semicolon_to_dirlist),
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
    parser.add_argument('-l', '--libext', metavar='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', metavar='.sitelibs file encoding')
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
    parser.add_argument('-l', '--libext', metavar='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', metavar='.sitelibs file encoding')
    args = parser.parse_args()
    target = args.target_script
    if not os.path.exists(target):
        logging.error('target script not found: {}'.format(target))
        return
    # Execute target.
    kwargs = {}
    if args.libext:
        kwargs['sitelib_paths'] = args.libext
    if args.encoding:
        kwargs['rcfile_encoding'] = args.encoding
    with ConfiguredLibraryEnvironment(**kwargs):
        sys.argv = [target.split(os.sep)[-1]]
        try:
            execfile(target)
        except NameError:
            exec(compile(open(target).read(),
                         target, 'exec'))

def test():
    """Execute tests with given extension paths."""
    # CLI configs.
    parser = argparse.ArgumentParser(
        description='ipyenv v{}: Execute tests with a supplied environment'.format(__version__)
    )
    parser.add_argument('test') # ignore this.
    parser.add_argument('-n', '--name', metavar='target test script name/path')
    parser.add_argument('-t', '--testdir', metavar='target test directory paths', nargs='*')
    parser.add_argument('-l', '--libext', metavar='Library extension paths', nargs='*')
    parser.add_argument('-e', '--encoding', metavar='.sitelibs file encoding')
    args = parser.parse_args()
    # Execute target.
    kwargs = {}
    if args.testdir:
        kwargs['test_paths'] = args.testdir
    if args.libext:
        kwargs['sitelib_paths'] = args.libext
    if args.encoding:
        kwargs['rcfile_encoding'] = args.encoding
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
                        metavar='ACTION: ( {} )'.format(', '.join(actions)),
                        choices=actions)
    # Parse & execute.
    args = parser.parse_args(sys.argv[1:2])
    action_funcs[args.action]()
