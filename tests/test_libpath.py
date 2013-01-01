# encoding: utf-8

import unittest
import sys
import os


# Add project root path for our module.
sys.path.append(os.path.abspath('../')) # works well in IronPython.
sys.path.append(os.path.abspath('.'))   # works well in the others.
import ipyenv

# Cancel logging.
import logging
ipyenv.create_logger(logging.CRITICAL)


class BaseEnviromnetTest(unittest.TestCase):
    """Assert PathEnviroment basic functionalities work."""

    def test_env_scope(self):
        """Path environment scope is transient."""
        pathname = 'i am dummy'
        env = ipyenv.PathEnvironment((pathname, ))
        self.assertFalse(pathname in sys.path)
        with env:
            self.assertIn(pathname, sys.path)
        self.assertFalse(pathname in sys.path)


class LibraryEnvironmentTest(unittest.TestCase):
    """
    Assert import paths work with given
    `sitelib` named directory.
    """

    def setUp(self):
        self.env = ipyenv.LibraryEnvironment(
            sitelib_paths=(os.sep.join((os.path.dirname(os.path.realpath(__file__)),
                                        'sitelib')),)
        )

    def tearDown(self):
        """We must remove all module entries imported in this test case..."""
        ext_paths = self.env.ext_paths
        for module_name in list(sys.modules.keys()):
            try:
                module_source = sys.modules[module_name].__file__
            except AttributeError:
                continue
            for ext_path in ext_paths:
                if module_source.startswith(ext_path):
                    del sys.modules[module_name]
                    break

    def test_toplevel(self):
        """Refer to the top-level module."""
        with self.assertRaises(ImportError):
            import toplevel_module
        with self.env:
            import toplevel_module
            self.assertEqual(toplevel_module.label(),
                             'i am sitelib/toplevel_module.')

    def test_flat_pkg(self):
        """Refer to modules in single tiered package."""
        with self.assertRaises(ImportError):
            import flat_pkg
        with self.assertRaises(ImportError):
            from flat_pkg import inner_module
        with self.env:
            import flat_pkg
            from flat_pkg import inner_module
            self.assertEqual(inner_module.label(),
                             'i am sitelib/flat_pkg/inner_module.')

    def test_hrch_pkg(self):
        """Refer to modules in hierarchical package."""
        with self.assertRaises(ImportError):
            import hrch_pkg
        with self.assertRaises(ImportError):
            from hrch_pkg import inner_module
        with self.assertRaises(ImportError):
            from hrch_pkg import subpkg
        with self.assertRaises(ImportError):
            import hrch_pkg.subpkg.inner_module
        with self.env:
            import hrch_pkg
            from hrch_pkg import inner_module
            self.assertEqual(inner_module.label(),
                             'i am sitelib/hrch/inner_module.')
            from hrch_pkg import subpkg
            import hrch_pkg.subpkg.inner_module as sub_inner_module
            self.assertEqual(sub_inner_module.label(),
                             'i am sitelib/hrch/subpkg/inner_module.')


class RCTest(LibraryEnvironmentTest):
    """
    Assert .ipyenvrc works with LibraryEnvironment.
    """

    def setUp(self):
        self.env = ipyenv.ConfiguredLibraryEnvironment(
                       config_path='./ipyenvrc_for_test'
                   )


class PartialRCTest(unittest.TestCase):
    """
    Assert .ipyenvrc works with partial configuration.
    """

    def test_partial_config(self):
        env = ipyenv.ConfiguredLibraryEnvironment(
                  config_path='./ipyenvrc_for_test_partial'
              )


if __name__ == '__main__':
    unittest.main(verbosity=1)
