#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abc-analyze —— 统计 ABC 谱的声部结构，并校验「器乐化」是否达标。

判据只有一条，但很硬：
    人声轨有声小节 0%，器乐轨接近 100%。
纯器乐谱长这样；人声谱的人声轨通常是 70~90% 有声。

用法：
    python scripts/abc_analyze.py a.abc b.abc      # 打印统计
    python scripts/abc_analyze.py out.abc --check  # 达标返回 0，否则返回 1
"""

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

音级表 = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
声部行 = re.compile(r'^V:\s*(\S+)(.*)$')
音符 = re.compile(r'(\^+|_+|=)?([A-Ga-g])([,\']*)(\d*)(/?\d*)')
人声别名 = {'vocal', 'voice', 'vox', 'vocals', 'voci', '人声', '唱', '演唱'}
括号内容 = re.compile(r'\[[^\]]*\]|"[^"]*"|\{[^}]*\}|![^!]*!')


def 是人声声部(名):
    return 名.strip().lower() in 人声别名


def 读谱(路径):
    with open(路径, 'r', encoding='utf-8-sig') as f:
        原始 = f.read().splitlines()
    头部 = {}
    声部 = []
    当前 = None
    for 行 in 原始:
        s = 行.strip()
        if not s or s.startswith('%'):
            continue
        匹配 = 声部行.match(s)
        if 匹配:
            当前 = {'名': 匹配.group(1), '音乐': []}
            声部.append(当前)
            continue
        if len(s) >= 2 and s[1] == ':' and s[0].isalpha():
            头部.setdefault(s[0], s[2:].strip())
            continue
        if 当前 is not None:
            当前['音乐'].append(s)
    合并 = {}
    for 段 in 声部:
        合并.setdefault(段['名'], []).extend(段['音乐'])
    return 头部, 合并


def 取小节(音乐行):
    串 = ''.join(音乐行)
    小节 = []
    for 片 in 串.split('|'):
        片 = 片.strip()
        if not 片:
            continue
        多休止 = re.fullmatch(r'Z(\d*)', 片)
        if 多休止:
            次数 = int(多休止.group(1)) if 多休止.group(1) else 1
            小节.extend(['Z'] * max(次数, 1))
        else:
            小节.append(片)
    return 小节


def 是空小节(小节):
    return re.fullmatch(r'[zZ0-9]+', 小节) is not None


def 分析声部(小节列表):
    结果 = {'小节数': len(小节列表), '有声小节': 0, '音符数': 0,
            '最低': None, '最高': None, '总音长': 0.0, '变音': 0, '休止数': 0}
    for 小节 in 小节列表:
        if 是空小节(小节):
            continue
        净 = 括号内容.sub('', 小节)
        有音符 = False
        for 匹配 in 音符.finditer(净):
            升降, 字母, 八度记, 长度串, 斜杠 = 匹配.groups()
            长 = float(长度串) if 长度串 else 1.0
            if 斜杠:
                长 = 长 / float(斜杠.strip('/') or 2)
            音高 = 12 * 5 + 音级表[字母.upper()]
            if 字母.islower():
                音高 += 12
            音高 += 12 * 八度记.count("'")
            音高 -= 12 * 八度记.count(',')
            结果['音符数'] += 1
            结果['总音长'] += 长
            结果['最低'] = 音高 if 结果['最低'] is None else min(结果['最低'], 音高)
            结果['最高'] = 音高 if 结果['最高'] is None else max(结果['最高'], 音高)
            if 升降:
                结果['变音'] += 1
            有音符 = True
        结果['休止数'] += len(re.findall(r'[zx]', 净))
        if 有音符:
            结果['有声小节'] += 1
    return 结果


def 音名(音高):
    if 音高 is None:
        return '-'
    名 = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return '%s%d' % (名[音高 % 12], 音高 // 12 - 1)


def 报告(路径):
    头部, 声部表 = 读谱(路径)
    print('=' * 66)
    print('文件：%s' % os.path.basename(路径))
    print('拍号 %s ／ 调号 %s ／ 默认音长 L:%s ／ 速度 %s'
          % (头部.get('M', '?'), 头部.get('K', '?'), 头部.get('L', '?'), 头部.get('Q', '?')))
    print('声部数：%d（%s）' % (len(声部表), '、'.join(声部表.keys())))
    结果表 = {}
    for 名, 音乐 in 声部表.items():
        统计 = 分析声部(取小节(音乐))
        结果表[名] = 统计
        占比 = 100.0 * 统计['有声小节'] / 统计['小节数'] if 统计['小节数'] else 0.0
        跨度 = (统计['最高'] - 统计['最低']) if 统计['最低'] is not None else 0
        平均长 = 统计['总音长'] / 统计['音符数'] if 统计['音符数'] else 0.0
        print('  [%s] 小节 %d ／ 有声小节 %d（%.0f%%）／ 音符 %d ／ 音域 %s–%s（%d 半音）'
              % (名, 统计['小节数'], 统计['有声小节'], 占比, 统计['音符数'],
                 音名(统计['最低']), 音名(统计['最高']), 跨度))
        print('       平均音长 %.1f 个默认音长 ／ 变音记号 %d ／ 休止符 %d'
              % (平均长, 统计['变音'], 统计['休止数']))
    return 结果表


def 校验(结果表, 最低覆盖=0.5):
    """人声轨必须 0 有声小节，器乐轨覆盖率不低于 最低覆盖。"""
    问题 = []
    人声_有声 = 0
    器乐最大覆盖 = 0.0
    for 名, 统计 in 结果表.items():
        占比 = 100.0 * 统计['有声小节'] / 统计['小节数'] if 统计['小节数'] else 0.0
        if 是人声声部(名):
            人声_有声 += 统计['有声小节']
            if 统计['有声小节']:
                问题.append('人声轨 [%s] 仍有 %d 个有声小节（应全为休止）' % (名, 统计['有声小节']))
        else:
            器乐最大覆盖 = max(器乐最大覆盖, 占比 / 100.0)
            if 占比 / 100.0 < 最低覆盖:
                问题.append('器乐轨 [%s] 覆盖率仅 %.0f%%（应 ≥ %.0f%%）'
                            % (名, 占比, 最低覆盖 * 100))
    return 问题, 人声_有声, 器乐最大覆盖


def 主流程():
    分析器 = argparse.ArgumentParser(
        prog='abc_analyze',
        description='统计 ABC 谱的声部结构，并校验器乐化是否达标。')
    分析器.add_argument('文件', nargs='+', help='一个或多个 .abc 文件')
    分析器.add_argument('--check', action='store_true',
                        help='按「人声轨 0%% 有声、器乐轨高覆盖」校验，不达标返回 1')
    分析器.add_argument('--min-cover', type=float, default=0.5, metavar='R',
                        help='器乐轨最低有声覆盖率，默认 0.5')
    参数 = 分析器.parse_args()

    全部通过 = True
    for 路径 in 参数.文件:
        if not os.path.isfile(路径):
            print('找不到文件：%s' % 路径)
            return 2
        结果表 = 报告(路径)
        if 参数.check:
            问题, 人声_有声, 覆盖 = 校验(结果表, 参数.min_cover)
            if 问题:
                全部通过 = False
                print('  校验：不达标')
                for 条 in 问题:
                    print('    - %s' % 条)
            else:
                print('  校验：达标（人声轨 0 个有声小节，器乐轨覆盖 %.0f%%）' % (覆盖 * 100))
    return 0 if 全部通过 else 1


if __name__ == '__main__':
    sys.exit(主流程())
