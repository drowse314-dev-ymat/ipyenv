# encoding: utf-8

import target_toplevel
from subpkg import target_inner

with open('./testlog', 'ab') as f:
    f.write(('i am TestAtTop\n').encode('utf-8'))
