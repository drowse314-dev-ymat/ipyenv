# encoding: utf-8

import unittest
import target_toplevel
from subpkg import target_inner


class TestWithoutMain(unittest.TestCase):

    def test_in_testcase(self):
        with open('./testlog', 'ab') as f:
            f.write(('i am sub_tests/test_inner_withoutmain\n').encode('utf-8'))
