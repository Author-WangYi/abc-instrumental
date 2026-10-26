#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小回归测试：不需要任何第三方依赖。

    python tests/test_skills.py
"""

import importlib.util
import os
import sys
import tempfile
import unittest

根 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
脚本目录 = os.path.join(根, 'scripts')
示例目录 = os.path.join(根, 'examples')


def 载入(名):
    路径 = os.path.join(脚本目录, 名 + '.py')
    规格 = importlib.util.spec_from_file_location(名, 路径)
    模块 = importlib.util.module_from_spec(规格)
    规格.loader.exec_module(模块)
    return 模块


工具 = 载入('abc_instrumentalize')
分析 = 载入('abc_analyze')


def 跑(路径, **选项):
    with open(路径, 'r', encoding='utf-8-sig') as f:
        行列表 = f.read().splitlines()
    模式 = 选项.pop('mode', 'move')
    生成 = {
        'move': 工具.生成_搬移,
        'relabel': 工具.生成_改标签,
        'merge': 工具.生成_合并,
        'swap': 工具.生成_换序,
    }[模式]
    输出, 计数 = 生成(行列表, *选项.values()) if 选项 else 生成(行列表)
    return 输出, 计数


def 读输出(输出):
     """把生成的行列表落到临时文件，再用分析器读回来，避免头部/注释里的字母被当成音符。"""
     with tempfile.TemporaryDirectory() as 临时目录:
         出口 = os.path.join(临时目录, 'out.abc')
         with open(出口, 'w', encoding='utf-8', newline='\n') as f:
             f.write('\n'.join(输出) + '\n')
         return 分析.读谱(出口)[1]


def 音符总数(声部表):
    return sum(分析.分析声部(分析.取小节(m))['音符数'] for m in 声部表.values())


class 搬移测试(unittest.TestCase):
    def setUp(self):
        self.人声谱 = os.path.join(示例目录, 'pop_vocal_2.abc')

    def test_人声轨被清空且器乐轨覆盖全曲(self):
        输出, 冲突 = 跑(self.人声谱)
        声部表 = 读输出(输出)
        结果 = {名: 分析.分析声部(分析.取小节(音乐)) for 名, 音乐 in 声部表.items()}
        人声 = 结果['Vocal']
        器乐 = 结果['Ins']
        self.assertEqual(人声['有声小节'], 0, 'Vocal 轨应当全是休止')
        self.assertEqual(人声['音符数'], 0, 'Vocal 轨不应残留音符')
        self.assertGreaterEqual(器乐['有声小节'] / 器乐['小节数'], 0.9,
                                '器乐轨应覆盖九成以上小节')
        self.assertGreater(冲突, 0, '这份谱存在两轨同时有内容的小节')

    def test_两轨都还在(self):
        输出, _ = 跑(self.人声谱)
        文本 = '\n'.join(输出)
        self.assertIn('V: Vocal', 文本)
        self.assertIn('V: Ins', 文本)

    def test_小节总数不变(self):
        原谱 = 分析.读谱(self.人声谱)[1]
        输出, _ = 跑(self.人声谱)
        新谱 = 读输出(输出)
        for 名 in ('Vocal', 'Ins'):
            原长 = len(分析.取小节(原谱[名]))
            新长 = len(分析.取小节(新谱[名]))
            self.assertEqual(原长, 新长, '%s 轨小节数不该变化' % 名)


class 对照模式测试(unittest.TestCase):
    def setUp(self):
        self.人声谱 = os.path.join(示例目录, 'pop_vocal.abc')

    def test_改标签不动音符(self):
        原音符 = 音符总数(分析.读谱(self.人声谱)[1])
        输出, _ = 跑(self.人声谱, mode='relabel')
        self.assertEqual(原音符, 音符总数(读输出(输出)))

    def test_换序保留全部音符(self):
        原音符 = 音符总数(分析.读谱(self.人声谱)[1])
        输出, _ = 跑(self.人声谱, mode='swap')
        self.assertEqual(原音符, 音符总数(读输出(输出)))


class 校验器测试(unittest.TestCase):
    def test_纯音乐谱达标(self):
        结果 = 分析.报告(os.path.join(示例目录, 'pure_instrumental.abc'))
        问题, _, _ = 分析.校验(结果)
        self.assertEqual(问题, [])

    def test_人声谱不达标(self):
        结果 = 分析.报告(os.path.join(示例目录, 'pop_vocal.abc'))
        问题, _, _ = 分析.校验(结果)
        self.assertTrue(问题)


if __name__ == '__main__':
    unittest.main(verbosity=2)
