#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abc-instrumental —— 把 ABC 记谱里的「人声」声部改由乐器演奏。

默认模式 move：保留两个声部，把 Vocal 轨整轨清空成等长休止，
旋律全部搬进器乐轨。这是唯一在 YuE 系重绘链路上验证有效的改法。

用法见 README.md，或：
    python scripts/abc_instrumentalize.py --help
"""

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

声部匹配 = re.compile(r'^V:\s*(\S+)(.*)$')
人声别名 = {'vocal', 'voice', 'vox', 'vocals', 'voci', '人声', '唱', '演唱'}
目标声部名 = 'Lead'
目标显示名 = 'Lead Melody'

模式后缀 = {
    'move': '.instrumental',
    'relabel': '.relabel',
    'merge': '.merge',
    'swap': '.swap',
}

模式说明 = {
    'move': '搬移：Vocal 轨清空成休止，旋律并入器乐轨（唯一验证有效的模式）',
    'relabel': '只改声部标签，音符零改动（对照用，实测无效）',
    'merge': '压成单轨（对照用，实测会破坏旋律，别用于生产）',
    'swap': '两轨块前后对调（对照用，用于验证链路是否按轨序绑定角色）',
}


def 是字段行(行):
    return len(行) >= 2 and 行[1] == ':' and 行[0].isalpha()


def 是人声声部(名):
    return 名.strip().lower() in 人声别名


def 改声明行(行):
    匹配 = 声部匹配.match(行.strip())
    if not 匹配 or not 是人声声部(匹配.group(1)):
        return 行
    尾部 = 匹配.group(2)
    尾部 = 尾部.replace('Vocal Melody', 目标显示名)
    尾部 = 尾部.replace('"Vocal"', '"%s"' % 目标声部名)
    尾部 = 尾部.replace("'Vocal'", "'%s'" % 目标声部名)
    尾部 = re.sub(r'(?i)vocal', 目标声部名, 尾部)
    return 'V: %s%s' % (目标声部名, 尾部)


def 切段(行列表):
    """把源码切成「头部 + 若干声部段」，每段保留声明行、控制行（K: M: 等）、音乐行。"""
    头部 = []
    段 = []
    当前 = None
    for 行 in 行列表:
        s = 行.strip()
        if not s:
            continue
        if s.startswith('%'):
            if 当前 is not None and 当前['音乐']:
                当前 = {'声部': '', '声明': '', '控制': [s], '音乐': []}
                段.append(当前)
            elif 当前 is not None:
                当前['控制'].append(s)
            else:
                头部.append(s)
            continue
        匹配 = 声部匹配.match(s)
        if 匹配:
            当前 = {'声部': 匹配.group(1), '声明': s, '控制': [], '音乐': []}
            段.append(当前)
            continue
        if 当前 is None:
            头部.append(s)
            continue
        if 是字段行(s):
            当前['控制'].append(s)
        else:
            当前['音乐'].append(s)
    return 头部, 段


def 取小节(音乐行):
    """把音乐行按 | 切成小节，Z4 之类的多小节休止展开成 4 个 Z，方便逐小节对齐。"""
    串 = ''.join(音乐行)
    结果 = []
    for 片 in 串.split('|'):
        片 = 片.strip()
        if not 片:
            continue
        多休止 = re.fullmatch(r'Z(\d*)', 片)
        if 多休止:
            次数 = int(多休止.group(1)) if 多休止.group(1) else 1
            结果.extend(['Z'] * max(次数, 1))
        else:
            结果.append(片)
    return 结果


def 是全休止(小节):
    return re.fullmatch(r'[zZ0-9]+', 小节) is not None


def 压缩休止(小节列表):
    """把连续的空小节折回 Z / Zn，输出更接近手写谱。"""
    结果 = []
    i = 0
    while i < len(小节列表):
        if 小节列表[i] == 'Z':
            j = i
            while j < len(小节列表) and 小节列表[j] == 'Z':
                j += 1
            次数 = j - i
            结果.append('Z' if 次数 == 1 else 'Z%d' % 次数)
            i = j
        else:
            结果.append(小节列表[i])
            i += 1
    return 结果


def 收集段落(段):
    """拆出「有音乐的段」和每个段前该写哪些控制行（K:、M: 等）。"""
    声明表 = []
    实段 = []
    前置控制 = []
    待挂 = []
    for 段项 in 段:
        if not 段项['音乐']:
            if 段项['声明']:
                声明表.append(段项['声明'])
            待挂.extend(段项['控制'])
            continue
        实段.append(段项)
        前置控制.append(list(待挂))
        待挂 = []
    return 声明表, 实段, 前置控制, 待挂


def 配对(实段, i):
    """判断第 i 段是不是「人声段 + 紧随其后的器乐段」这一对。"""
    甲 = 实段[i]
    if 是人声声部(甲['声部']) and i + 1 < len(实段) and not 是人声声部(实段[i + 1]['声部']):
        return 甲, 实段[i + 1], i + 2
    return None, 甲, i + 1


def 对齐(器乐小节, 人声小节):
    长 = max(len(器乐小节), len(人声小节))
    return (器乐小节 + ['Z'] * (长 - len(器乐小节)),
            人声小节 + ['Z'] * (长 - len(人声小节)),
            长)


def 生成_改标签(行列表):
    return [改声明行(行) for 行 in 行列表], 0


def 生成_合并(行列表):
    头部, 段 = 切段(行列表)
    _, 实段, 前置控制, 待挂 = 收集段落(段)
    输出 = list(头部) + list(待挂)
    输出.append('V: %s clef=treble name="%s" snm="%s"' % (目标声部名, 目标显示名, 目标声部名))
    未合并 = 0
    i = 0
    while i < len(实段):
        人声段, 器乐段, i = 配对(实段, i)
        前置 = 前置控制[i - 2] if 人声段 else 前置控制[i - 1]
        控制 = list(前置) + list(器乐段['控制'])
        if 人声段 is not None:
            for 行 in 人声段['控制']:
                if 行 not in 控制:
                    控制.append(行)
        器乐小节 = 取小节(器乐段['音乐'])
        人声小节 = 取小节(人声段['音乐']) if 人声段 else []
        if 人声小节:
            if len(人声小节) != len(器乐小节):
                未合并 += 1
                print('  [提示] 两轨小节数不一致（人声 %d / 器乐 %d），已按长的一方补休止对齐'
                      % (len(人声小节), len(器乐小节)))
            器乐小节, 人声小节, _ = 对齐(器乐小节, 人声小节)
            合并小节 = []
            for 器乐格, 人声格 in zip(器乐小节, 人声小节):
                if 是全休止(器乐格) and not 是全休止(人声格):
                    合并小节.append(人声格)
                else:
                    合并小节.append(器乐格)
        else:
            合并小节 = 器乐小节
        输出.extend(控制)
        输出.append('|'.join(合并小节) + '|')
    return 输出, 未合并


def 生成_换序(行列表):
    头部, 段 = 切段(行列表)
    声明表, 实段, 前置控制, 待挂 = 收集段落(段)
    输出 = list(头部) + list(reversed(声明表)) + list(待挂)
    i = 0
    while i < len(实段):
        起始 = i
        人声段, 器乐段, i = 配对(实段, i)
        if 人声段 is not None:
            本次 = [(器乐段, i - 1), (人声段, 起始)]
        else:
            本次 = [(器乐段, 起始)]
        for 段项, 前置序 in 本次:
            输出.extend(前置控制[前置序])
            输出.append(段项['声明'])
            输出.extend(段项['控制'])
            输出.append(''.join(段项['音乐']))
    return 输出, 0


def 生成_搬移(行列表, 人声优先=False):
    """保留两个声部，但把内容搬运到器乐轨：Vocal 轨清空为等长休止，旋律并入 Ins 轨。

    这复刻了「纯器乐谱」的形态：Vocal 有声小节 0%，Ins 覆盖全曲。
    两轨同时有内容的小节无法折叠成单条旋律，按 人声优先 决定取舍。
    """
    头部, 段 = 切段(行列表)
    声明表, 实段, 前置控制, 待挂 = 收集段落(段)
    输出 = list(头部) + 声明表
    i = 0
    冲突数 = 0
    while i < len(实段):
        人声段, 器乐段, i = 配对(实段, i)
        器乐小节 = 取小节(器乐段['音乐'])
        人声小节 = 取小节(人声段['音乐']) if 人声段 else []
        if 人声小节:
            器乐小节, 人声小节, 长 = 对齐(器乐小节, 人声小节)
            新器乐 = []
            for 器乐格, 人声格 in zip(器乐小节, 人声小节):
                if 是全休止(器乐格) and not 是全休止(人声格):
                    新器乐.append(人声格)
                elif not 是全休止(器乐格) and not 是全休止(人声格):
                    冲突数 += 1
                    新器乐.append(人声格 if 人声优先 else 器乐格)
                else:
                    新器乐.append(器乐格)
            新空轨 = ['Z'] * 长
        else:
            新器乐 = 器乐小节
            新空轨 = ['Z'] * len(器乐小节)
        # 空出来的人声轨：保留原名与原控制行（调号/拍号），音乐换成等长休止
        人声名 = 人声段['声部'] if 人声段 else 'Vocal'
        人声前置 = 前置控制[i - 2] if 人声段 else []
        输出.extend(人声前置)
        输出.append('V: %s' % 人声名)
        输出.extend(人声段['控制'] if 人声段 else [])
        输出.append('|'.join(压缩休止(新空轨)) + '|')
        输出.extend(前置控制[i - 1])
        输出.append('V: %s' % 器乐段['声部'])
        输出.extend(器乐段['控制'])
        输出.append('|'.join(压缩休止(新器乐)) + '|')
    输出.extend(待挂)
    return 输出, 冲突数


def 插入音色(行列表, 音色号):
    """在第一个 V: 行之前插入 %%MIDI program，给整首定一个 GM 音色。"""
    if 音色号 is None:
        return 行列表
    for 序, 行 in enumerate(行列表):
        if 声部匹配.match(行.strip()):
            return 行列表[:序] + ['%%MIDI program %d' % 音色号] + 行列表[序:]
    return 行列表 + ['%%MIDI program %d' % 音色号]


def 解析参数():
    分析器 = argparse.ArgumentParser(
        prog='abc_instrumentalize',
        description='把 ABC 记谱里的人声声部改由乐器演奏。默认模式 move 为唯一验证有效的改法。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例：
  python abc_instrumentalize.py song.abc
  python abc_instrumentalize.py song.abc --voice-first
  python abc_instrumentalize.py song.abc --program 41 -o out.abc
  python abc_instrumentalize.py song.abc --stdout
''')
    分析器.add_argument('输入', help='输入 .abc 文件路径')
    分析器.add_argument('--mode', '-m', choices=sorted(模式后缀), default='move',
                        help='处理模式，默认 move（搬移）')
    分析器.add_argument('--voice-first', '--人声优先', dest='人声优先', action='store_true',
                        help='两轨同时有内容时保留人声（默认保留器乐）')
    分析器.add_argument('--program', type=int, default=None, metavar='N',
                        help='插入 %%%%MIDI program N，换音色：1 钢琴 / 41 小提琴 / 57 小号 / 74 长笛')
    分析器.add_argument('--output', '-o', default=None, help='输出路径，默认 <原名><模式后缀>.abc')
    分析器.add_argument('--stdout', action='store_true', help='只打印到终端，不写文件')
    # 兼容旧参数
    分析器.add_argument('--搬移', dest='旧_搬移', action='store_true', help=argparse.SUPPRESS)
    分析器.add_argument('--合并', dest='旧_合并', action='store_true', help=argparse.SUPPRESS)
    分析器.add_argument('--换序', dest='旧_换序', action='store_true', help=argparse.SUPPRESS)
    分析器.add_argument('--改标签', dest='旧_改标签', action='store_true', help=argparse.SUPPRESS)
    参数 = 分析器.parse_args()
    if 参数.旧_合并:
        参数.mode = 'merge'
    elif 参数.旧_换序:
        参数.mode = 'swap'
    elif 参数.旧_改标签:
        参数.mode = 'relabel'
    elif 参数.旧_搬移:
        参数.mode = 'move'
    return 参数


def 主流程():
    参数 = 解析参数()
    if not os.path.isfile(参数.输入):
        print('找不到文件：%s' % 参数.输入)
        return 2
    with open(参数.输入, 'r', encoding='utf-8-sig') as f:
        行列表 = f.read().splitlines()

    if 参数.mode == 'move':
        输出行, 计数 = 生成_搬移(行列表, 参数.人声优先)
    elif 参数.mode == 'relabel':
        输出行, 计数 = 生成_改标签(行列表)
    elif 参数.mode == 'merge':
        输出行, 计数 = 生成_合并(行列表)
    else:
        输出行, 计数 = 生成_换序(行列表)

    输出行 = 插入音色(输出行, 参数.program)
    文本 = '\n'.join(输出行) + '\n'

    if 参数.stdout:
        sys.stdout.write(文本)
        return 0

    根, 后缀 = os.path.splitext(参数.输入)
    目标路径 = 参数.output or ('%s%s%s' % (根, 模式后缀[参数.mode], 后缀 or '.abc'))
    with open(目标路径, 'w', encoding='utf-8', newline='\n') as f:
        f.write(文本)

    print('模式：%s —— %s' % (参数.mode, 模式说明[参数.mode]))
    if 参数.mode == 'move':
        print('两轨同时有内容的小节：%d 处（已按%s保留）' % (计数, '人声' if 参数.人声优先 else '器乐'))
    elif 参数.mode == 'merge':
        print('小节数不一致的段落：%d 处' % 计数)
    print('已写出：%s' % 目标路径)
    return 0


if __name__ == '__main__':
    sys.exit(主流程())
