# encoding: utf-8

import unittest
import sys
import os

# Add project root path for our module.
sys.path.append(os.path.abspath('../')) # works well in IronPython.
sys.path.append(os.path.abspath('.'))   # works well in the others.
import ipyenv


class RWFreeNamedTempFileTest(unittest.TestCase):
    """Assert `ipyenv.RWFreeNamedTempFile` class works."""

    def test_file_context(self):
        """Assert the temporary file available on enter, removed on exit."""
        with ipyenv.RWFreeNamedTempFile(source='', target_dir='./') as filename:
            self.assertTrue(os.path.exists(filename))
        self.assertFalse(os.path.exists(filename))

    def test_file_unlocked(self):
        """Assert the temporary file is not locked for R/W operation."""
        with ipyenv.RWFreeNamedTempFile(source='...', target_dir='./') as filename:
            with open(filename, 'rb') as f:
                self.assertTrue(bool(f.read()))
            with open(filename, 'wb') as f:
                f.write('...'.encode('utf-8'))

    def test_file_content(self):
        """Assert the temporary file content is set as `source` parameter."""
        my_source = 'i am the content/\nje suis le continu'
        with ipyenv.RWFreeNamedTempFile(source=my_source, target_dir='./',
                                            encoding='utf-8') as filename:
            with open(filename, 'rb') as f:
                self.assertEqual(f.read().decode('utf-8'), my_source)


class ExecContextTest(unittest.TestCase):
    """
    Assert `ipyenv.py exec` makes a proper context in execution.
    """

    def test_globals_isolated(self):
        """
        Global variables are isolated.
        Alse for avoiding a regression:
            In the past implementation, `execfile`/py2 relays to `exec`/py3
            when NameError raised by the deprecation of `execfile` in py3,
            which makes a confision in the case NameError raised in the
            execution context of `execfile`. 
        """
        outer_var = 'my var'
        script = """
# encoding: utf-8
print(outer_var)
        """
        with ipyenv.RWFreeNamedTempFile(source=script) as tempf:
            with self.assertRaises(NameError):
                ipyenv._execute_file(tempf)

    def test_available_vars(self):
        """
        Assert some globals are available:
            sys, __name__, __file__
        """
        script = """
#encoding: utf-8
sys
__name__
__file__
"""
        with ipyenv.RWFreeNamedTempFile(source=script) as tempf:
            ipyenv._execute_file(tempf)


if __name__ == '__main__':
    unittest.main(verbosity=4)
