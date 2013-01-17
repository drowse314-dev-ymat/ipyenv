# encoding: utf-8

import os
import sys
import re
import logging
import argparse


TARGET_DIR = os.path.realpath('./tests')
RE_TEST_SCRIPT_NAME = re.compile('^[Tt]est.*\.py$')


# Create logger only for this script.
def create_logger(level=logging.INFO):
    logger = logging.getLogger('ipyenv:test-runner')
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter('ipyenv/test-runner(%(levelname)s): %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
logger = create_logger()


def get_module_from_path(target_filename):
    """Copied & simplified from our ipyenv.py!"""

    path_components = os.path.split(target_filename)
    local_name = path_components[-1]
    dir_path = os.path.sep.join(path_components[:-1])
    module_name = os.path.extsep.join(local_name.split(os.path.extsep)[:-1])

    # Temporarily append path...
    if dir_path not in sys.path:
        append_path = True
        sys.path.append(dir_path)
    else:
        append_path = False
    module = __import__(module_name)
    if append_path:
        sys.path.remove(dir_path)

    return module


def run_testsuites(testfile_paths, verbosity):
    """Copied & simplified from our ipyenv.py!"""
    import unittest
    loader = unittest.TestLoader()
    suites = []
    for testfile_path in testfile_paths:
        logger.info('load test suites from: {}'.format(testfile_path))
        test_module = get_module_from_path(testfile_path)
        suites.append(loader.loadTestsFromModule(test_module))
    aggregated = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=verbosity).run(aggregated)

def collect_tests_as_paths(target=TARGET_DIR):
    test_paths = []
    for root, dirs, files in os.walk(target):
        if root != target:
            continue
        for filename in files:
            if RE_TEST_SCRIPT_NAME.search(filename):
                test_paths.append(os.path.sep.join((root, filename)))
    return test_paths

def run(verbosity=1):
    test_paths = collect_tests_as_paths()
    run_testsuites(test_paths, verbosity)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbosity', type=int, default=1)
    args = parser.parse_args()
    run(args.verbosity)
