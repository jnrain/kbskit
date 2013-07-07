#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# weiyu / kbslib / legacy attachment migrator
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
import os
import re
import ast
import locale

# Constants.
if __name__ != '__main__':
    from .sitecfg import KBS_ENCODING
else:
    from sitecfg import KBS_ENCODING

UPLOAD_TAG_RE = re.compile(br'\[upload=(\d+)\]\[/upload\]')

LEGACYPIC_TMPL = b'[legacypic:%s%s]%s[/legacypic]'
LEGACYAUDIO_TMPL = b'[legacyaudio:%s%s]%s[/legacyaudio]'
LEGACYFILE_TMPL = b'[legacyfile:%s%s]%s[/legacyfile]'

PIC_EXTS = {'.jpg', '.jpeg', '.jfif', '.gif', '.png', '.mng', '.bmp', }
AUDIO_EXTS = {'.mp3', '.ogg', '.wma', '.wav', '.flac', '.ape', '.aac', }


def get_att_info(fp):
    for l in fp:
        yield ast.literal_eval(l)


def gen_legacyatt_tag(fname, cksum):
    # 搞出扩展名，然后选一个合适语义的标签
    # 因为常见扩展名就那几种，就不搞 MIME 了
    ext = os.path.splitext(fname)[1].lower()
    extl = ext.lower()
    if extl in PIC_EXTS:
        tmpl = LEGACYPIC_TMPL
    elif extl in AUDIO_EXTS:
        tmpl = LEGACYAUDIO_TMPL
    else:
        tmpl = LEGACYFILE_TMPL

    return tmpl % (cksum, ext, fname, )


def upload_transformer_factory_factory(atts):
    def upload_transformer_factory(fname, result_wrapper):
        post_atts = atts[fname]
        result_wrapper[0] = set()

        def _transformer_(match):
            att_idx = int(match.group(1)) - 1  # 0-based

            # 告诉外边的世界帖子里的 upload 标签都是哪几个
            # 因为没有用 upload 标签标注的附件按照 KBS 渲染行为
            # 需要在文末另行追加相应标签
            result_wrapper[0].add(att_idx)

            s_idx, att_name, cksum = post_atts[att_idx]
            return gen_legacyatt_tag(att_name, cksum)
        return _transformer_
    return upload_transformer_factory


def main(argv):
    ENC = locale.getpreferredencoding()

    if len(argv) < 2:
        print(
                'usage: %s <stdout dump(s) of att.py>' % (
                    argv[0],
                    ),
                file=sys.stderr,
                )
        return 1

    atts = {}
    for fname in argv[1:]:
        print('reading att list: %s' % (fname, ))

        with open(fname, 'rb') as fp:
            for post_file, att_name, s_idx, e_idx, cksum in get_att_info(fp):
                if post_file not in atts:
                    atts[post_file] = []

                atts[post_file].append((s_idx, att_name, cksum, ))

    print('sorting att list')
    for post_file in atts:
        atts[post_file].sort()

    # 首先做一个标签变换函数的工厂
    transformer_factory = upload_transformer_factory_factory(atts)

    for post_file in atts:
        print('migrating: %s' % (post_file, ))
        post_atts = atts[post_file]
        num_atts = len(post_atts)

        with open(post_file, 'rb') as fp:
            post_content = fp.read()

        # 做个接收替换结果的容器，然后生产标签转换函数
        explicit_atts_container = [None]
        transform_fn = transformer_factory(post_file, explicit_atts_container)
        # 必须在执行之后提取这个结果的引用，否则先设置引用再被更新的话就悲剧了
        explicit_atts = explicit_atts_container[0]

        # 在第一个附件之前截断文章
        # \x00 * 8 + 文件名 + \x00 + uint32be 文件大小是要往前跳过的内容
        first_att = post_atts[0]
        article_end = first_att[0] - 13 - len(first_att[1])

        result = UPLOAD_TAG_RE.sub(transform_fn, post_content[:article_end])
        if len(explicit_atts) < num_atts:
            # 有附件没有通过 upload 标签暴露。那就在文末加上
            implicit_atts = set(xrange(num_atts)).difference(explicit_atts)
            implicit_atts_str = b'\n'.join(
                    gen_legacyatt_tag(fname, cksum)
                    for att_idx, (s_idx, fname, cksum) in enumerate(post_atts)
                    if att_idx in implicit_atts
                    )
            result += implicit_atts_str + b'\n'

        os.rename(post_file, post_file + b'.old')
        with open(post_file, 'wb') as fp:
            fp.write(result)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))


# vim:set ai et ts=4 sw=4 sts=4 fenc=utf-8:
