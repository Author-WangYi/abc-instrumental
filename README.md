# abc-instrumental

把 ABC 记谱（`.abc`）里的**人声声部改由乐器演奏** —— 也就是把「人声谱」改写成「纯器乐谱」的形态。

面向的链路是 **YuE / ACE 这类「ABC 旋律条件 → 音频」的重绘（repaint）模型**：
你想让人声歌重绘成纯音乐，但改了标签还是出人声；把两轨合并成单轨，旋律直接崩掉。

**结论**：问题不在你的改法，在入口选错了。有效的做法只有一种 —— **搬移内容，不是删除或改名。**

---

## 为什么会失败

ABC 是一门**记谱**格式，它没有「这个声部由人唱还是由乐器演奏」这个字段。
`V: Vocal`、`name="Vocal Melody"`、`snm="Vocal"` 全是自由文本，模型没有任何理由把它当作
「唱 / 不唱」的布尔位。能表达唱不唱的，只有 **这一轨里有没有音符**。

实测两份谱的量化对比：

| 指标 | 人声歌 | 纯器乐 |
|---|---|---|
| 声部数 | 2（Vocal + Ins） | **2（Vocal + Ins）** |
| Vocal 轨有声小节 | **90 / 111（81%）** | **0 / 117（0%）** |
| Vocal 轨音符数 | 316 | **0** |
| Ins 轨有声小节 | 21 / 111（19%） | **116 / 117（99%）** |
| Ins 轨音符数 | 97 | 932 |
| Ins 轨音域跨度 | 12 半音 | 31 半音 |

注意第二行：**纯器乐谱同样声明了 `V: Vocal`**，只是那条轨从头到尾 0 个音符。
所以「有没有 Vocal 轨」根本不是判据，「哪一轨有音符」才是。

于是四种改法的结果也就自洽了：

| 改法 | 结果 | 被排除的变量 |
|---|---|---|
| 只改声部名（`Vocal` → `Lead`），音符不动 | 仍然出人声 | 声部名、标签 |
| 压成单轨，把旋律填进器乐轨空小节 | 仍然出人声，且**旋律彻底崩坏** | 单轨更干净不成立 |
| 每对 Vocal/Ins 块前后对调 | 与原来完全一样 | 轨的位置、顺序 |
| **保留两轨，Vocal 清成休止，旋律并入 Ins** | ✅ 成功 | — |

---

## 安装

只需要 Python 3.8+，**无第三方依赖**。

```bash
git clone https://github.com/Author-WangYi/abc-instrumental.git && cd abc-instrumental
python scripts/abc_instrumentalize.py --help
```

作为 **Agent Skill** 使用时，把整个目录放到 `~/.claude/skills/`（或 `~/.workbuddy/skills/`）下即可，
`SKILL.md` 会被自动加载。

---

## 用法

### 1. 先量化，确认输入形态

```bash
python scripts/abc_analyze.py examples/pop_vocal.abc
```

```
文件：pop_vocal.abc
拍号 3/4 ／ 调号 C ／ 默认音长 L:1/16 ／ 速度 1/4=106
声部数：2（Vocal、Ins）
  [Vocal] 小节 111 ／ 有声小节 90（81%）／ 音符 316 ／ 音域 B4–F6（18 半音）
  [Ins] 小节 111 ／ 有声小节 21（19%）／ 音符 97 ／ 音域 G5–G6（12 半音）
```

Vocal 轨有声小节占比 70~90% → 典型人声谱，需要改。

### 2. 转成器乐版

```bash
python scripts/abc_instrumentalize.py examples/pop_vocal.abc
# → examples/pop_vocal.instrumental.abc
```

常用选项：

```bash
--voice-first            # 两轨同时有内容时保留人声（默认保留器乐）
--program 41             # 插入 %%MIDI program 41（小提琴）；1 钢琴 57 小号 74 长笛
-o out.abc               # 指定输出路径
--stdout                 # 只打印到终端，不写文件（方便直接复制粘贴）
```

### 3. 校验达标

```bash
python scripts/abc_analyze.py examples/pop_vocal.instrumental.abc --check
```

```
文件：pop_vocal.instrumental.abc
拍号 3/4 ／ 调号 C ／ 默认音长 L:1/16 ／ 速度 1/4=106
声部数：2（Vocal、Ins）
  [Vocal] 小节 111 ／ 有声小节 0（0%）／ 音符 0 ／ 音域 -–-（0 半音）
  [Ins] 小节 111 ／ 有声小节 109（98%）／ 音符 409 ／ 音域 B4–G6（20 半音）
  校验：达标（人声轨 0 个有声小节，器乐轨覆盖 98%）
```

达标返回 0，不达标返回 1，可以直接放进 CI 或脚本链里。

---

## 模式

`--mode` 默认 `move`。

| 模式 | 作用 | 生产可用 |
|---|---|---|
| `move` | 保留两轨，Vocal 清成等长休止，旋律并入器乐轨 | ✅ 唯一验证有效 |
| `relabel` | 只改声部标签，音符零改动 | ❌ 对照实验：实测无效 |
| `merge` | 压成单轨 | ❌ 对照实验：实测破坏旋律 |
| `swap` | 两轨块前后对调 | ❌ 对照实验：验证轨序不参与角色绑定 |

三个对照模式保留下来，是为了以后换模型 / 换链路时能快速重跑同一组实验。
**不要**用它们产出正式文件。

---

## 冲突小节：唯一需要人判断的地方

两轨在**同一小节都有内容**时，无法折叠成一条旋律，必须二选一。

- 默认保留**器乐** —— riff、伴奏走向通常比挂在人声上的长音更有信息量。
- 人声那一小节是在**收句**时（长音终结、句尾落音），用 `--voice-first`。

判断依据是「哪一条在承担句子收束」，**不是**「哪一条音符多」。
脚本会打印冲突处数；可以两个版本都生成，逐处比对再拼定稿。

---

## 已知代价

1. **会丢几个音。** 冲突处的 Vocal 原音被挤掉，通常是弱起或长音。
2. **偏薄。** 输出是「主旋律 + 零星 riff」，不是完整编曲 ——
   因为人声谱的 Ins 轨在 verse/chorus 常常整段是 `Z4`，伴奏本来就没被转写进 ABC。
   想要厚，先做音轨分离拿 instrumental stem 再转谱，那是另一条路。
3. **调号要合法。** `K:D#m` 这类理论调（8 个升号）个别解析器会报错或错判音高，
   等音的 `K:Ebm` 更安全，音符一个不用改。

---

## 目录结构

```
.
├── SKILL.md                        Agent Skill 入口（含工作流说明）
├── README.md
├── scripts/
│   ├── abc_instrumentalize.py      四种改写模式，默认 move
│   └── abc_analyze.py              声部结构统计 + --check 校验
├── tests/
│   └── test_cli.py                 7 个回归测试，无第三方依赖
├── examples/
│   ├── pop_vocal.abc               人声谱（Vocal 81% 有声）
│   ├── pure_instrumental.abc       纯器乐谱（Vocal 0%，达标范本）
│   ├── pop_vocal_2.abc             待处理的人声谱
│   └── pop_vocal_3.abc             待处理的人声谱
└── references/
    └── investigation-log.md        四轮排除的完整记录
```

## 测试

```bash
python tests/test_cli.py
```

## License

MIT
