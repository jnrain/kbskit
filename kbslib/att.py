#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# weiyu / kbslib / attachment extractor
#
# Copyright (C) 2013 Wang Xuerui <idontknw.wang-at-gmail-dot-com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals, division, print_function

import sys
import struct
import mmap

# Constants.
if __name__ != '__main__':
    from .sitecfg import KBS_ENCODING
else:
    from sitecfg import KBS_ENCODING

ATTACHMENT_PADDING = b'\x00\x00\x00\x00\x00\x00\x00\x00'
SIZE_STRUCT = struct.Struct(b'>I')


# 函数式编程风格的寻找附件算法
# 基本上是根据 KBS 相关代码（libBBS/article.c 大概 2100 行往后）改写的
def find_atts(s):
    # Python 里就不写尾递归了。。反正 trivial
    start = 0
    while True:
        fname, start_idx, end_idx = _find_one_att(s, start)
        if end_idx is None:
            break

        yield fname, start_idx, end_idx
        start = end_idx


def _find_one_att(s, start):
    # 寻找标志附件开始的 pad
    pad_idx = s.find(ATTACHMENT_PADDING, start)
    if pad_idx == -1:
        # 找不到了，退出
        return None, None, None

    # 提取 null-terminated 的文件名
    fname_start_idx = pad_idx + 8
    fname_end_idx = s.find(b'\x00', fname_start_idx)
    if fname_end_idx == -1:
        # 不正常：文件名根本没有被终结！
        # 当作没有有效附件
        return None, None, None

    # 给文件名转码
    bytes_fname = s[fname_start_idx:fname_end_idx]
    att_fname = bytes_fname.decode(KBS_ENCODING, 'replace')

    # 提取 uint32_be 的附件大小
    size_idx = fname_end_idx + 1
    size = SIZE_STRUCT.unpack(s[size_idx:size_idx + 4])[0]

    # 验证附件长度
    att_start_idx = size_idx + 4
    att_end_idx = att_start_idx + size
    if att_end_idx > len(s):
        # 至今为止的总长加上附件长度超过了字符串长度
        return None, None, None

    return (att_fname, att_start_idx, att_end_idx, )


def main(argv):
    if len(argv) < 2:
        print(
                'usage: %s <posts to extract attachments from>' % (
                    argv[0],
                    ),
                file=sys.stderr,
                )
        return 1

    for fname in argv[1:]:
        with open(fname, 'rb') as fp:
            mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
            for att_name, att_idx, att_end_idx in find_atts(mm):
                print('%s: %s [%d:%d]' % (
                    fname,
                    att_name,
                    att_idx,
                    att_end_idx,
                    ))

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))


# vim:set ai et ts=4 sw=4 sts=4 fenc=utf-8:
