# encoding: utf-8

import unittest
import target_toplevel
from subpkg import target_inner


class TestInModule(unittest.TestCase):

    def test_in_testcase(self):
        with open('./testlog', 'ab') as f:
            f.write(('i am test_moduletype\n').encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
