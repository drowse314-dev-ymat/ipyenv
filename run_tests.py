# encoding: utf-8

import subprocess
import os
import sys
import re


TARGET_DIR = os.path.realpath('./tests')
RE_TEST_SCRIPT_NAME = re.compile('^[Tt]est.*\.py$')


def execute_test(filepath):
    subprocess.call([sys.executable, filepath])

def run():
    for root, dirs, files in os.walk(TARGET_DIR):
        if root != TARGET_DIR:
            continue
        for filename in files:
            if RE_TEST_SCRIPT_NAME.search(filename):
                execute_test(os.path.sep.join((root, filename)))


if __name__ == '__main__':
    run()
