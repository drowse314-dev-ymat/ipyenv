# encoding: utf-8

import sys
import os
import re
import logging


# Config logger.
logging.basicConfig(format='ipyenv(%(levelname)s): %(message)s')


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
        sys.path = self._orig_paths
        self._orig_paths = None
        del self._orig_paths

    @property
    def ext_paths(self):
        """Not to modify manually this property."""
        return self._ext_paths


def _find_sitelibrc(sitelib_abspath):
    """Find .sitelibrc path in given directory."""
    rcfile_path = os.sep.join((sitelib_abspath, '.sitelibs'))
    if not (os.path.exists(rcfile_path) and os.path.isfile(rcfile_path)):
        return None
    return rcfile_path

# Regular exp. for newline characters.
RE_NEWLINES = re.compile('[(?:\n)(?:\r\n)(?:\r)]+')

def _resolve_rcpath(path_repr, sitelib_dir_path):
    path_repr = RE_NEWLINES.sub('', path_repr)
    path_repr = path_repr.replace('/', os.sep)
    return os.sep.join((sitelib_dir_path, path_repr))

def _load_sitelib(sitelib_dir, rcfile_encoding):
    """Load .sitelibs rc file & extract library paths to extend."""
    if not (os.path.exists(sitelib_dir) and os.path.isdir(sitelib_dir)):
        logging.error('sitelib directory "{}" not found'.format(sitelib_dir))
        return []
    sitelib_dir = os.path.realpath(sitelib_dir)
    # Get .sitelibs.
    rcfile_path = _find_sitelibrc(sitelib_dir)
    if rcfile_path is None:
        logging.error('.sitelibs in "{}" not found'.format(sitelib_dir))
        return []
    # Read out .sitelibs.
    library_paths = []
    with open(rcfile_path, 'rb') as rcfile:
        for line in rcfile:
            library_paths.append(_resolve_rcpath(line.decode(rcfile_encoding),
                                                 sitelib_dir))
    return list(set(library_paths))


class LibraryEnvironment(PathEnvironment):
    """
    Context manager for appending on the fly
    modules/packeges import paths."""

    def __init__(self, sitelib_paths=('./sitelib',), rcfile_encoding='utf-8'):
        # Load .sitelib files.
        library_paths = []
        for sitelib_dir in sitelib_paths:
            library_paths.extend(_load_sitelib(sitelib_dir, rcfile_encoding))
        PathEnvironment.__init__(self, library_paths)
