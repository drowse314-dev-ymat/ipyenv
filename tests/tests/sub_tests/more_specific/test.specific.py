# encoding: utf-8

import target_toplevel
from subpkg import target_inner

with open('./testlog', 'ab') as f:
    f.write(('i am sub_tests/more_specific/test.specific\n').encode('utf-8'))
