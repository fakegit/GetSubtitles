# coding: utf-8

import sys

# system encoding
if sys.stdout.encoding == 'cp936':
    is_gbk = True
else:
    is_gbk = False

# set prefix
prefix = '├ '
