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


class TestEnvironmentTest(unittest.TestCase):
    """
    Assert TestRunner works, for setting up paths
    for targets & execute tests files.
    """

    def setUp(self):
        self.test_runner = ipyenv.TestRunner(
            test_paths=(os.sep.join((os.path.dirname(os.path.realpath(__file__)),
                                     'tests')),),
            sitelib_paths=(os.sep.join((os.path.dirname(os.path.realpath(__file__)),
                                        'sitelib')),)
        )

    def tearDown(self):
        """We must remove all module entries imported in this test case..."""
        ext_paths = self.test_runner.ext_paths
        for module_name in list(sys.modules.keys()):
            try:
                module_source = sys.modules[module_name].__file__
            except AttributeError:
                continue
            for ext_path in ext_paths:
                if module_source.startswith(ext_path):
                    del sys.modules[module_name]
                    break

    def test_run_all_tests(self):
        """
        Run tests recursively in given directories, with
        corrct configs.
        """
        # Assert by log entry...
        test_log_path = './testlog'
        self.test_runner.execute_all()
        executed = []
        with open(test_log_path, 'rt') as f:
            for line in f:
                executed.append(line)
        os.remove(test_log_path)
        # Assert all tests invoked.
        tests_expected = [
            'TestAtTop',
            'test_toplevel',
            'test_moduletype',
            'sub_tests/test_inner',
            'sub_tests/testinner2',
            'sub_tests/more_specific/TestSpecific',
            'sub_tests/more_specific/test_specific',
        ]
        for test_label in tests_expected:
            self.assertIn('i am ' + test_label + '\n',
                          executed)

    def test_run_specific(self):
        """
        Run tests by given path to the file with corrct configs.
        """
        # Assert by log entry...
        test_log_path = './testlog'
        self.test_runner.execute_by_path('./tests/tests/TestAtTop.py')
        self.test_runner.execute_by_path('./tests/tests/sub_tests/test_inner.py')
        self.test_runner.execute_by_path('./tests/tests/sub_tests/more_specific/test_specific.py')
        executed = []
        with open(test_log_path, 'rt') as f:
            for line in f:
                executed.append(line)
        os.remove(test_log_path)
        # Assert all tests invoked.
        tests_expected = [
            'TestAtTop',
            'sub_tests/test_inner',
            'sub_tests/more_specific/test_specific',
        ]
        for test_label in tests_expected:
            self.assertIn('i am ' + test_label + '\n',
                          executed)


class RCTest(TestEnvironmentTest):
    """
    Assert .ipyenvrc works with TestRunner.
    """

    def setUp(self):
        self.test_runner = ipyenv.ConfiguredTestRunner(
                               config_path='./ipyenvrc_for_test'
                            )


class RCTest(TestEnvironmentTest):
    """
    Assert .ipyenvrc works with partial configuration.
    """

    def test_partial_config(self):
        test_runner = ipyenv.ConfiguredTestRunner(
                               config_path='./ipyenvrc_for_test_partial'
                      )

    def test_section_lacking_config(self):
        test_runner = ipyenv.ConfiguredTestRunner(
                               config_path='./ipyenvrc_for_test_lackingsection'
                      )


if __name__ == '__main__':
    unittest.main(verbosity=1)
