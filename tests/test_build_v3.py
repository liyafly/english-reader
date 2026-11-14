"""build.py 第三版（设置.json 写 "format": 3）的解析和检查。在 skill 根目录运行：python3 -m unittest discover -s tests

夹具（fixtures/）：
  v3_轻读.md   第三版轻读单元：精讲 2 句、练习 2 句（一套编号）、理解 2 题、词条 2 条、复述 1 题、卡句 2 句（词汇 + 有生词、
               独立结构 + 词都认识），完全合规；引文都出自 原文.txt
  v3_精读.md   第三版精读单元：第一版 精读.md 的长难句换成 5 个句子块（不写主干，怎么拆可选），末尾加卡句 2 句
               （词汇 + 有生词、指代 + 没说）；别的栏目和 精读.md 一样
S1–S17 是 check 的第三版规则编号（见 build.py）。每条至少一个反例：在合规的夹具上改一处，确认 check 报出来。
第一、二版的项目不受影响：demo_snapshot 和第一版夹具的 check 输出、合订 讲义.md 逐字节不变（TestV2Unchanged）。
"""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SKILL = HERE.parent
BUILD = SKILL / "scripts" / "build.py"
SOURCE = (FIX / "原文.txt").read_text(encoding="utf-8")
V3L = (FIX / "v3_轻读.md").read_text(encoding="utf-8")
V3J = (FIX / "v3_精读.md").read_text(encoding="utf-8")
LIGHT = (FIX / "轻读.md").read_text(encoding="utf-8")          # 第二版的轻读夹具
INTENSIVE = (FIX / "精读.md").read_text(encoding="utf-8")      # 第一版的精读夹具
PREFACE = (FIX / "前言.md").read_text(encoding="utf-8")
TAG_ROWS = (("it 占位", "it 先占住主语的位置，真的在后面", "**It** is hard **to say no**."),
            ("后置修饰", "名词后面跟一串修饰", "the man **who lives next door**"),
            ("多层从句", "从句里还有从句", "I know **what he said when he left**."),
            ("非谓语", "doing、done、to do 短语作状语或补语", "**Smiling**, she left."),
            ("独立结构", "分词自己带主语", "**The work done**, we went home."),
            ("并列", "几个谓语或几个分句并排", "He **came**, **saw** and **left**."),
            ("固定框架", "两个词隔着一段话相互呼应", "It is **not so much** the money **as** the time."),
            ("指代", "代词指什么要回前文找", "I lost a pen and found **it** later."),
            ("主谓隔开", "主语和谓语之间插了长修饰", "**The man**, tired after the long walk, **sat** down."))
TAG_TABLE = ("## 句子结构\n\n本书长难句用到的结构。例句是自造的。\n\n| 标签 | 意思 | 例子 |\n| --- | --- | --- |\n"
             + "".join(f"| {a} | {b} | {c} |\n" for a, b, c in TAG_ROWS))
PREFACE_V3 = PREFACE.rstrip("\n") + "\n\n" + TAG_TABLE
PAD = "这一句只是为了把长度撑过上限"


def sub(text, old, new="", count=1):
    """把 old 换成 new；old 必须在 text 里（夹具改了而测试没跟上时立刻报错）。"""
    assert old in text, f"夹具里找不到：{old[:40]}"
    return text.replace(old, new, count)


def section(text, name):
    """「## name」一节（含标题行，到下一个「## 」或文件末尾）。"""
    m = re.search(rf"^## {re.escape(name)}\n.*?(?=^## |\Z)", text, flags=re.M | re.S)
    assert m, f"没有「## {name}」"
    return m.group(0)


def block(text, head):
    """「### head…」一个句子块（含标题行，到下一个「### 」「## 」或文件末尾）。"""
    m = re.search(rf"^### {re.escape(head)}.*?(?=^### |^## |\Z)", text, flags=re.M | re.S)
    assert m, f"没有「### {head}」"
    return m.group(0)


def in_block(text, head, old, new=""):
    """只在「### head」那个句子块里把 old 换成 new。"""
    b = block(text, head)
    return text.replace(b, sub(b, old, new), 1)


S1, S2, S3, S4 = "1. small wonder", "2. 句首的分词", "3. who、as、what", "4. allude to it"   # 轻读夹具的长难句
K1, K2 = "1. 三个过去分词", "2. he being new"                                               # 轻读夹具的卡句
J1, J3, J5, JK2 = "1. 定语一层套一层", "3. not so much", "5. 先找 filled", "2. 两个 it"       # 精读夹具


def load_build():
    spec = importlib.util.spec_from_file_location("er_build_v3", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "项目"

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, units, default_mode="轻读", preface=None, source=SOURCE, extra=None, fmt=3):
        """units：[(单元号, 讲义, mode 或 None, 标题)]。fmt=None 时 设置.json 里不写 format（第一、二版）。"""
        if self.root.exists():
            shutil.rmtree(self.root)
        (self.root / "原文").mkdir(parents=True)
        (self.root / "讲义").mkdir(parents=True)
        cfg = {"title": "The Wind in the Willows", "author": "Kenneth Grahame", "unit": "章", "units": [],
               "level": "B1", "genre": "小说", "appreciation": True, "writing": True, "fonts": None}
        if fmt is not None:
            cfg["format"] = fmt
        if default_mode is not None:
            cfg["default_mode"] = default_mode
        for n, text, mode, title in units:
            u = {"n": n, "title": title}
            if mode is not None:
                u["mode"] = mode
            cfg["units"].append(u)
            (self.root / "原文" / f"第{n:02d}章.txt").write_text(source, encoding="utf-8")
            (self.root / "讲义" / f"第{n:02d}章.md").write_text(text, encoding="utf-8")
        cfg.update(extra or {})
        (self.root / "设置.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if preface is not None:
            (self.root / "讲义" / "前言.md").write_text(preface, encoding="utf-8")
        return self.root

    def light(self, text, **kw):
        self.project([(1, text, None, "The River Bank")], **kw)

    def intensive(self, text, **kw):
        self.project([(1, text, "精读", "The River Bank")], **kw)

    def run_build(self, cmd, *args, build=BUILD):
        r = subprocess.run([sys.executable, str(build), cmd, str(self.root), *args], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def check(self):
        code, out = self.run_build("check")
        m = re.search(r"问题 (\d+) 个", out)
        self.assertIsNotNone(m, out)
        return int(m.group(1)), out

    def assertClean(self):
        n, out = self.check()
        self.assertEqual(n, 0, out)
        return out

    def assertReports(self, *fragments, count=None):
        n, out = self.check()
        for f in fragments:
            self.assertIn(f, out)
        if count is not None:
            self.assertEqual(n, count, out)
        return out

    def assertHints(self, *fragments, absent=()):
        """问题 0 个；提示里有 fragments，输出里没有 absent。"""
        n, out = self.check()
        self.assertEqual(n, 0, out)
        hints = "\n".join(l for l in out.splitlines() if l.startswith("提示 "))
        for f in fragments:
            self.assertIn(f, hints, out)
        for f in absent:
            self.assertNotIn(f, out)
        return out


# ---------- 合规的夹具 ----------

class TestFixtures(Base):
    def test_light_fixture_clean(self):
        self.light(V3L)
        out = self.assertClean()
        self.assertIn("核对引文 10 处，问题 0 个", out)
        self.assertNotIn("篇幅", out)

    def test_intensive_fixture_clean(self):
        self.intensive(V3J)
        self.assertIn("核对引文 44 处，问题 0 个", self.assertClean())

    def test_both_with_preface(self):
        # 结构行里的「非谓语」不算语法术语（第一版前言的语法术语表里没有它），结构标签另查句子结构表
        self.project([(1, V3J, "精读", "The River Bank"), (2, V3L, None, "The River Bank (轻读)")], preface=PREFACE_V3)
        out = self.assertClean()
        self.assertNotIn("句子结构：", out.replace("提示 全部单元 句子结构", ""))
        self.assertNotIn("非谓语", out)

    def test_md(self):
        self.project([(1, V3J, "精读", "The River Bank"), (2, V3L, None, "The Open Road")], preface=PREFACE_V3)
        code, out = self.run_build("md")
        self.assertEqual(code, 0, out)
        md = (self.root / "成品" / "讲义.md").read_text(encoding="utf-8")
        self.assertIn("- [第 2 章　The Open Road](#ch2)\n", md)
        self.assertIn('<a id="ch2"></a>\n\n## 第 2 章\n\n### 读前\n', md)
        self.assertIn("\n### 卡句\n\n#### 1. 三个过去分词", md)
        self.assertIn("| **It** **was** small wonder, | 难怪（这件事）—— |\n", md)     # 断句表原样

    def test_spec_examples(self):
        """reference/句子.md 里的句子块例子（demo 第 2 章的三句）贴进第 2 章，句子块本身没有问题。
        读前、理解、词的用法、复述用 demo_snapshot 的第二版第 2 章：只剩数量的问题（例子只有精讲、练习各 1 句）。"""
        spec = (SKILL / "reference" / "句子.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```markdown\n(.*?)```", spec, flags=re.S)
        sent = next(b for b in blocks if b.startswith("## 长难句"))
        stuck = next(b for b in blocks if b.startswith("## 卡句"))
        v2 = (FIX / "demo_snapshot" / "讲义" / "第02章.md").read_text(encoding="utf-8")
        unit = ("# 第 2 章讲解\n\n" + section(v2, "读前") + sent.rstrip("\n") + "\n\n" + section(v2, "理解")
                + section(v2, "词的用法") + section(v2, "复述").rstrip("\n") + "\n\n" + stuck)
        src = (FIX / "demo_snapshot" / "原文" / "第02章.txt").read_text(encoding="utf-8")
        self.light(unit, source=src)
        n, out = self.check()
        problems = [l for l in out.splitlines() if l.startswith("第 1 章 ")]
        self.assertTrue(all(re.search(r"格式：(理解|精讲句|练习句)需要", l) for l in problems), out)
        self.assertNotIn("卡句 1", "\n".join(problems))

    def test_md_refuses_format_errors(self):
        self.project([(1, V3J, "精读", ""), (2, sub(V3L, "## 卡句", "## 补充句"), None, "")])
        code, out = self.run_build("md")
        self.assertNotEqual(code, 0)
        self.assertIn("格式有问题，先运行 check", out)


# ---------- 设置和分流 ----------

class TestSettings(Base):
    def test_bad_format(self):
        self.light(V3L, fmt=4)
        code, out = self.run_build("check")
        self.assertNotEqual(code, 0)
        self.assertIn("设置.json 的 format 只能写 3", out)
        self.light(V3L, fmt="3")
        self.assertIn("设置.json 的 format 要写数字 3，不加引号", self.run_build("check")[1])

    def test_v3_unit_without_format_uses_v2_rules(self):
        self.light(V3L, fmt=None)
        self.assertReports("小节顺序不对：应为读前、理解、长难句、词的用法、复述，补充句放在最后",
                           "句 1：未知标签「结构」", "不认识的小节「## 卡句」")

    def test_v2_unit_with_format_3(self):
        self.light(LIGHT)
        self.assertReports("「## 补充句」第三版改叫「## 卡句」", "句 1：第三版不写「主干」，断句表里的粗体就是主干",
                           "句 1：缺少断句表", "小节顺序不对：应为读前、长难句、理解、词的用法、复述，卡句放在最后")

    def test_format_2_written_out(self):
        self.light(LIGHT, fmt=2)
        self.assertEqual(self.check()[0], 0)

    def test_slug(self):
        b = load_build()
        self.light(V3L)
        b.load_project(self.root)
        self.assertEqual((b.P.format, b.P.slug), (3, "the-wind-in-the-willows"))
        self.light(V3L, extra={"slug": "willows"})
        b.load_project(self.root)
        self.assertEqual(b.P.slug, "willows")
        self.light(V3L, extra={"title": "柳林风声"})
        b.load_project(self.root)
        self.assertEqual(b.P.slug, "book")
        self.light(LIGHT, fmt=None)
        b.load_project(self.root)
        self.assertEqual(b.P.format, 2)


class TestV2Unchanged(Base):
    """第二版的分流不变：demo_snapshot 的 check 输出和合订 讲义.md、第一版夹具和混用项目的合订 讲义.md 和改动前逐字节相同。
    sha256 是改动前的 build.py 生成的。"""
    SNAP_MD = "9f98f2bcd74ddf4e4b88516e184946d24517c7b4af05b141e6b29b2bd1848ea0"
    MIXED_MD = "826cc1e3f93eea190949846a0eb90da276d0f3dfd02c4f25ad908febbbe361b1"

    def md_sha(self):
        code, out = self.run_build("md")
        self.assertEqual(code, 0, out)
        return hashlib.sha256((self.root / "成品" / "讲义.md").read_bytes()).hexdigest()

    def test_demo_snapshot(self):
        shutil.copytree(FIX / "demo_snapshot", self.root)
        code, out = self.run_build("check")
        self.assertEqual((code, out), (0, "核对引文 52 处，问题 0 个\n"))
        self.assertEqual(self.md_sha(), self.SNAP_MD)

    def test_v1_two_chapters(self):
        ch2 = re.sub(r"\A# .*", "# 第 2 章讲解", INTENSIVE)
        self.project([(1, INTENSIVE, None, "The River Bank"), (2, ch2, None, "The River Bank (copy)")],
                     default_mode=None, preface=PREFACE, fmt=None)
        code, out = self.run_build("check")
        self.assertEqual(out, "第 2 章 格式：自测最后两题（且只有这两题）要以「回头看（第 N 章）：」开头\n核对引文 88 处，问题 1 个\n"
                              "  其中 格式和引文 1，禁用语 0，长度 0，直引号 0，术语 0，语法术语 0\n")
        self.run_build("md")
        self.assertEqual((self.root / "成品" / "讲义.md").read_bytes(), (FIX / "合订_精读两章_第一版.md").read_bytes())

    def test_mixed_v1_v2(self):
        self.project([(1, INTENSIVE, "精读", "The River Bank"), (2, LIGHT, None, "The Open Road")], preface=PREFACE, fmt=None)
        self.assertEqual(self.md_sha(), self.MIXED_MD)


# ---------- 栏目和数量 ----------

class TestSections(Base):
    def test_order(self):
        s = section(V3L, "理解")
        self.light(sub(V3L.replace(s, ""), "## 长难句\n", s + "## 长难句\n"))
        self.assertReports("小节顺序不对：应为读前、长难句、理解、词的用法、复述，卡句放在最后")

    def test_stuck_must_be_last(self):
        s = section(V3L, "卡句")
        self.light(sub(V3L.replace(s, ""), "## 复述\n", s + "## 复述\n"))
        self.assertReports("小节顺序不对")

    def test_missing_and_unknown(self):
        self.light(V3L.replace(section(V3L, "复述"), "") + "\n## 自测\n\n1. 题\n")
        self.assertReports("缺少「## 复述」", "不认识的小节「## 自测」")

    def test_extra_renamed(self):
        self.light(sub(V3L, "## 卡句", "## 补充句"))
        self.assertReports("「## 补充句」第三版改叫「## 卡句」")
        self.intensive(sub(V3J, "## 卡句", "## 补充句"))
        self.assertReports("「## 补充句」第三版改叫「## 卡句」")

    def test_intensive_stuck_last(self):
        s = section(V3J, "卡句")
        self.intensive(sub(V3J.replace(s, ""), "## 词的用法\n", s.rstrip("\n") + "\n\n## 词的用法\n"))
        self.assertReports("「## 卡句」要放在最后")

    def test_intensive_other_sections_still_checked(self):
        self.intensive(V3J.replace(section(V3J, "自测"), ""))
        self.assertReports("缺少「## 自测」")

    def test_stuck_numbering_and_order(self):
        self.light(in_block(V3L, K2, "### 2.", "### 3."))
        self.assertReports("卡句编号不连续")
        k1, k2 = block(V3L, K1), block(V3L, K2)
        swapped = k2.replace("### 2.", "### 1.").rstrip("\n") + "\n\n" + k1.replace("### 1.", "### 2.")
        self.light(sub(V3L, k1 + k2, swapped.rstrip("\n") + "\n"))
        self.assertReports("卡句未按原文出现顺序排列")

    def test_sentence_order(self):
        b1, b2 = block(V3L, S1), block(V3L, S2)
        swapped = b2.replace("### 2.", "### 1.") + b1.replace("### 1.", "### 2.")
        self.light(sub(V3L, b1 + b2, swapped))
        self.assertReports("长难句未按原文出现顺序排列")


class TestCounts(Base):
    def test_jing_count(self):
        text = in_block(V3L, S4, block(V3L, S4)[block(V3L, S4).index("- **卡点**"):], "\n")     # 句 4 变成练习句
        self.light(text)
        self.assertReports("精讲句需要 2 句（原文", "现在 1 句", count=1)

    def test_lian_count(self):
        self.light(in_block(V3L, S2, "- **答**：he\n", "- **答**：he\n- **卡点**：Jumping 的动作是 he 做的。\n- **译**：他四条腿一齐蹦起来。\n"))
        self.assertReports("精讲句需要 2 句（原文", "现在 3 句", "练习句需要 2–3 句（原文", "现在 1 句", count=2)

    THIRD = ("### 5. 四个并列的谓语\n\n"
             "> The Rat brought the boat alongside the bank, made her fast, helped the still awkward Mole safely ashore, "
             "and swung out the luncheon-basket.\n\n"
             "- **结构**：并列\n- **试**：和 brought 并列的下一个谓语是哪个词？\n\n"
             "| 断句 | 顺读 |\n| --- | --- |\n"
             "| **The Rat** **brought** the boat alongside the bank, | 河鼠把船靠到岸边， |\n"
             "| **made** her fast, | 把它（船）拴牢， |\n"
             "| **helped** the still awkward Mole safely ashore, | 扶着还笨手笨脚的鼹鼠稳稳上了岸， |\n"
             "| and **swung out** the luncheon-basket. | 又把野餐篮甩了出来。 |\n\n"
             "- **答**：made\n\n")

    def test_third_practice_allowed(self):
        # 原文里在句 4 后面的一句写成练习句 5：练习 3 句，在 2–3 之内
        self.light(sub(V3L, "## 理解\n", self.THIRD + "## 理解\n"))
        self.assertClean()
        four = self.THIRD.replace("### 5.", "### 6.")
        self.light(sub(V3L, "## 理解\n", self.THIRD + four + "## 理解\n"))
        self.assertReports("练习句需要 2–3 句（原文", "现在 4 句")

    def test_usage_and_comprehension(self):
        self.light(sub(V3L, V3L[V3L.index("- **take to**"):V3L.index("## 复述")], "\n"))
        self.assertReports("词汇用法需要 2–3 条（原文", "现在 1 条")
        self.light(sub(V3L, "2. 河鼠说起野树林里的居民时，口气有什么变化？说明了什么？\n",
                       "2. 河鼠说起野树林里的居民时，口气有什么变化？说明了什么？\n3. 船翻以后河鼠怎么说？\n"))
        self.assertReports("理解需要 2 题（原文", "理解题和答案数量不一致")

    def test_intensive_count(self):
        self.intensive(sub(V3J, block(V3J, J5)))
        self.assertReports("精讲句需要 5–6 句（原文", "现在 4 句")


# ---------- 句子块：每条规则一个反例 ----------

class TestS1Tags(Base):
    def test_missing(self):
        self.light(sub(V3L, "- **结构**：it 占位、并列\n"))
        self.assertReports("句 1：缺少「结构」", count=1)

    def test_count(self):
        self.light(sub(V3L, "- **结构**：it 占位、并列", "- **结构**：it 占位、并列、插入"))
        self.assertReports("句 1：「结构」写 1–2 个标签，现在 3 个", count=1)

    def test_unknown_tag(self):
        self.light(sub(V3L, "- **结构**：it 占位、并列", "- **结构**：it占位、并列"))
        self.assertReports("句 1：「it占位」不是结构标签", count=1)

    def test_vocab_only_on_stuck(self):
        self.light(sub(V3L, "- **结构**：非谓语", "- **结构**：词汇"))
        self.assertReports("句 2：「词汇」只给卡句用", count=1)

    def test_vocab_alone(self):
        self.light(sub(V3L, "- **结构**：词汇", "- **结构**：词汇、省略"))
        self.assertReports("卡句 1：「词汇」要单独用", count=1)


class TestS2Table(Base):
    def test_header(self):
        self.light(in_block(V3L, S1, "| 断句 | 顺读 |", "| 英文 | 中文 |"))
        self.assertReports("句 1：断句表的表头要写成「| 断句 | 顺读 |」", count=1)

    def test_missing_table(self):
        b = block(V3L, S2)
        table = b[b.index("| 断句 | 顺读 |"):b.index("- **答**")]
        self.light(sub(V3L, table))
        self.assertReports("句 2：缺少断句表")

    def test_at_least_two_rows(self):
        self.light(sub(V3L, "| **The Mole** **was** bewitched, | 鼹鼠着了魔， |\n| entranced, fascinated. | 出了神，入了迷。 |",
                       "| **The Mole** **was** bewitched, entranced, fascinated. | 鼹鼠着了魔，出了神，入了迷。 |"))
        self.assertReports("卡句 1：断句表至少 2 行，现在 1 行", count=1)

    def test_two_cells(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · then, | 所以说， | 多一格 |"))
        self.assertReports("句 1 断句表第 2 行要有两格（断句、顺读），现在 3 格")

    def test_separator(self):
        self.light(in_block(V3L, S1, "| --- | --- |\n"))
        self.assertReports("句 1：断句表第二行要是分隔行")

    def test_one_table_only(self):
        self.light(in_block(V3L, S1, "| · then, | 所以说， |\n", "| · then, | 所以说， |\n\n"))
        self.assertReports("句 1：只能有一张断句表")


class TestS3Join(Base):
    def test_word_changed(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · so, | 所以说， |"))
        self.assertReports("句 1 断句第 2 行和原句对不上：这一行从「so,」起和原句不同，原句这里是「then, that h」", count=1)

    def test_shows_first_difference(self):
        # 从第一个不同的字起，两边各给 12 个字符
        self.light(sub(V3L, "| · then, | 所以说， |", "| · then, thot | 所以说， |"))
        self.assertReports("句 1 断句第 2 行和原句对不上：这一行从「ot」起和原句不同，原句这里是「at he sudden」", count=1)

    def test_straight_apostrophe(self):
        self.light(sub(V3L, "| “Oh, it’s all very well to talk,” |", "| “Oh, it's all very well to talk,” |"))
        self.assertReports("断句第 1 行和原句对不上：这里是直撇号，原句是弯撇号（「's all very」）", count=1)
        self.light(sub(V3L, "| “Oh, it’s all very well to talk,” |", "| \"Oh, it’s all very well to talk,” |"))
        self.assertReports("断句第 1 行和原句对不上：这里是直引号，原句是弯引号", count=1)

    def test_tail_missing(self):
        self.light(sub(V3L, "| · without even waiting to put on his coat. | 连外套都没等穿上。 |\n"))
        self.assertReports("句 1 断句：各行连起来比原句少了后面的「without even waiting to」", count=1)

    def test_whitespace_ignored(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · then , | 所以说， |"))
        self.assertClean()


class TestS4Depth(Base):
    def test_max_depth(self):
        self.light(sub(V3L, "| · · to see what the row was about. |", "| · · · to see what the row was about. |"))
        self.assertReports("句 3 断句第 6 行缩进 3 层，最多 2 层", count=1)

    def test_needs_top_row(self):
        self.light(sub(V3L, "| **he** **pursued** his way", "| · he pursued his way"))
        self.assertReports("句 2 断句：至少要有一行顶格")

    def test_first_row(self):
        self.light(sub(V3L, "| · Jumping off", "| · · Jumping off"))
        self.assertReports("句 2 断句第 1 行最多缩进 1 层", count=1)

    def test_step(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · · then, | 所以说， |"))
        self.assertReports("句 1 断句第 2 行比上一行深了 2 层，一次最多深 1 层", count=1)


class TestS5Bold(Base):
    def test_bold_only_top_rows(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · **then**, | 所以说， |"))
        self.assertReports("句 1 断句第 2 行：粗体只标顶格行", count=1)

    def test_needs_bold(self):
        self.light(sub(V3L, "| **The Mole** **was** bewitched, |", "| The Mole was bewitched, |"))
        self.assertReports("卡句 1 断句：没有粗体", count=1)

    def test_one_bold_is_hint(self):
        self.light(sub(V3L, "| **The Mole** **was** bewitched, |", "| **The Mole** was bewitched, |"))
        self.assertHints("提示 第 1 章 断句：卡句 1 断句只有 1 处粗体")

    def test_bold_words(self):
        # 主语只标中心词和前面的冠词、形容词，谓语只标动词：一处粗体最多 v3.sentence.bold_words 个词
        self.light(sub(V3L, "| **He** **was bowled over** in an instant |", "| **He was bowled over in** an instant |"))
        self.assertReports("句 3 断句第 1 行：粗体「He was bowled over in」5 个词，最多 4 个", count=1)
        self.light(sub(V3L, "| **He** **was bowled over** in an instant |", "| **He was bowled over** in an instant |"))
        self.assertHints("句 3 断句只有 1 处粗体")                # 4 个词不报，只是主语和谓语没分开标

    def test_bold_punctuation(self):
        self.light(sub(V3L, "| **It** **was** small wonder, |", "| **It** **was small wonder,** |"))
        self.assertReports("句 1 断句第 1 行：粗体「was small wonder,」里有标点", count=1)


class TestS6S7Rows(Base):
    MERGED = ("| · in the joy of living | 带着活着的快乐 |\n| · and the delight of spring without its cleaning, | 和不用大扫除的春天的欢喜， |",
              "| · in the joy of living and the delight of spring without its cleaning, | 带着快乐和春天的欢喜， |")

    def test_chunk_words_hint(self):
        self.light(sub(V3L, *self.MERGED))
        self.assertHints("提示 第 1 章 断句：句 2 断句第 2 行超过 10 词（每行 1–10 词）")

    def test_gloss_empty(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · then, |  |"))
        self.assertReports("句 1 顺读第 2 行是空的", count=1)

    def test_gloss_length_hint(self):
        self.light(sub(V3L, "| · then, | 所以说， |", "| · then, | 所以说，这里的 then 是承接上文的意思， |"))
        self.assertHints("提示 第 1 章 断句：句 1 顺读第 2 行超过 18 字")


class TestS8Try(Base):
    def test_missing_try(self):
        self.light(sub(V3L, "- **试**：who 引出的从句，谓语是哪个词？\n"))
        self.assertReports("句 3：缺少「试」", count=1)

    def test_missing_answer(self):
        self.light(sub(V3L, "- **答**：trotted\n"))
        self.assertReports("句 3：缺少「答」", count=1)

    def test_answer_in_source(self):
        self.assertNotIn("galloped", SOURCE)
        self.light(sub(V3L, "- **答**：trotted", "- **答**：galloped"))
        self.assertReports("句 3 答「galloped」在本章原文里找不到", count=1)

    def test_answer_whole_words(self):
        # 答按整词比：原文里只有 trotted，「trotte」是它的一部分，不算找到
        self.assertIn("trotte", SOURCE)
        self.assertNotRegex(SOURCE, r"(?<![A-Za-z])trotte(?![A-Za-z])")
        self.light(sub(V3L, "- **答**：trotted", "- **答**：trotte"))
        self.assertReports("句 3 答「trotte」在本章原文里找不到（照原文抄，按整词比）", count=1)

    def test_answer_edge_not_letter(self):
        # 答的头一个字符不是字母时不查前边界，末一个不是字母时不查后边界
        phrase_in = load_build().phrase_in
        text = "“You’ll have to go,” said the Rat. Go on (quickly)."
        self.assertTrue(phrase_in("’ll have to go", text))
        self.assertFalse(phrase_in("ou’ll have to go", text))         # 头一个是字母，照样查边界
        self.assertTrue(phrase_in("(quickly", text))
        self.assertTrue(phrase_in("go,”", text))
        self.assertFalse(phrase_in("have to g", text))

    def test_answer_words(self):
        self.light(sub(V3L, "- **答**：that\n", "- **答**：that he suddenly flung down his brush on the floor\n"))
        self.assertReports("句 1 答 10 词，最多 8 词", count=1)

    def test_answer_from_other_sentence(self):
        # 指代题的答案可以取自本单元别的句子
        self.light(sub(V3L, "- **答**：trotted", "- **答**：an elderly rabbit at the gap"))
        self.assertClean()

    def test_vocab_stuck_has_no_try(self):
        self.light(sub(V3L, "- **注**：bewitch 迷住；entrance 使出神；fascinate 使着迷\n",
                       "- **注**：bewitch 迷住；entrance 使出神；fascinate 使着迷\n- **试**：主语是谁？\n"))
        self.assertReports("卡句 1：标签是词汇的卡句不写「试」和「答」", count=1)


class TestS9Notes(Base):
    def test_count(self):
        self.light(sub(V3L, "fascinate 使着迷", "fascinate 使着迷；Mole 鼹鼠；was 是"))
        self.assertReports("卡句 1：注最多 4 个，现在 5 个", count=1)

    def test_word_in_sentence(self):
        self.light(sub(V3L, "- **注**：bolt 猛冲", "- **注**：dash 猛冲"))
        self.assertReports("句 1 注里的「dash」不在原句里", count=1)

    def test_lemma_and_placeholder(self):
        text = sub(V3L, "- **注**：bolt 猛冲", "- **注**：bolted 猛冲")                  # 按原形比：变形也认
        text = sub(text, "- **注**：allude to 提到，暗指", "- **注**：allude to sth 提到，暗指")   # sth 不比
        self.light(text)
        self.assertClean()

    def test_gloss_chars(self):
        self.light(sub(V3L, "- **注**：bolt 猛冲", "- **注**：bolt 猛地冲了出去，像逃跑一样"))
        self.assertReports("句 1 注「bolt」的释义 12 字，最多 10 字", count=1)

    def test_format(self):
        self.light(sub(V3L, "- **注**：bolt 猛冲", "- **注**：bolt猛冲"))
        self.assertReports("句 1：注要写成「词 释义；词 释义」：「bolt猛冲」")


class TestS10Words(Base):
    def test_hint_and_exemptions(self):
        self.light(V3L)
        out = self.assertHints("提示 第 1 章 词：句 1 原句里这些词高于读者水平 B1，读前、词条和注里都没有：flung（B2，估）",
                               absent=["bolted（"])                          # bolted 在注里
        line = next(l for l in out.splitlines() if "词：句 3 原句里" in l)
        self.assertNotIn("mole", line)                                      # 句中大写的 Mole 是专名
        self.assertNotIn("trotted", line)                                   # 读前词 trot
        self.light(sub(V3L, "- **注**：bolt 猛冲", "- **注**：bolt 猛冲；fling 扔"))
        self.assertHints(absent=["词：句 1 原句里"])

    def test_earlier_notes_count(self):
        """前面的句子注过的词，后面的句子不再提示；后面的注不往前算。"""
        self.light(in_block(V3L, S2, "- **试**：", "- **注**：hedge 树篱\n- **试**："))
        out = self.assertHints("词：句 3 原句里这些词高于读者水平 B1，读前、词条和注里都没有：contemptuous（C2）、chaffing（C2，估）、peeped（B2）")
        self.assertNotIn("hedge", "\n".join(l for l in out.splitlines() if "句 2 原句里" in l or "句 3 原句里" in l))
        self.light(in_block(V3L, S3, "- **试**：", "- **注**：hedge 树篱\n- **试**："))
        self.assertHints("词：句 2 原句里这些词高于读者水平 B1，读前、词条和注里都没有：meadow（B2，估）、hedge（B2）")


class TestS11Kinds(Base):
    def test_light_one_of_two(self):
        b = block(V3L, S1)
        self.light(sub(V3L, b[b.index("- **译**"):]))
        self.assertReports("句 1：精讲句要有卡点和译，练习句两样都不写；现在只有「卡点」", count=1)

    def test_intensive_needs_both(self):
        b = block(V3J, J3)
        self.intensive(sub(V3J, b[b.index("- **译**"):b.index("- **句型**")]))
        self.assertReports("句 3：精读的长难句都是精讲句，缺少「译」", count=1)


class TestS12Labels(Base):
    def test_no_core(self):
        self.light(sub(V3L, "- **注**：bolt 猛冲\n", "- **注**：bolt 猛冲\n- **主干**：It was small wonder that he bolted.\n"))
        self.assertReports("句 1：第三版不写「主干」，断句表里的粗体就是主干", count=1)

    def test_light_no_split(self):
        self.light(sub(V3L, "- **答**：possible trouble ahead\n", "- **答**：possible trouble ahead\n- **怎么拆**：\n  1. it 指前面的麻烦。\n"))
        self.assertReports("句 4：轻读的长难句不写「怎么拆」", count=1)

    def test_stuck_no_pattern(self):
        self.intensive(in_block(V3J, JK2, "- **译**：可在这么个地方", "- **句型**：`too … for …`\n- **译**：可在这么个地方"))
        self.assertReports("卡句 2：卡句不写「句型」")

    def test_intensive_steps(self):
        more = "".join(f"  {k}. 第 {k} 步。\n" for k in range(3, 7))
        self.intensive(in_block(V3J, J1, "等于 which is owned by animals。\n", "等于 which is owned by animals。\n" + more))
        self.assertReports("句 1：「怎么拆」写 1–5 步，现在 6 步", count=1)


class TestHalfColon(Base):
    def test_half_width_colon(self):
        self.light(sub(V3L, "- **答**：trotted", "- **答**: trotted"))
        out = self.assertReports("句 3：「答」后面紧跟全角冒号「：」，不用半角「:」、不空格")
        self.assertNotIn("无法识别的行", out)


class TestS13Positions(Base):
    def test_pre_label_after_table(self):
        text = sub(V3L, "- **试**：who 引出的从句，谓语是哪个词？\n\n")
        self.light(sub(text, "- **答**：trotted\n", "- **答**：trotted\n- **试**：who 引出的从句，谓语是哪个词？\n"))
        self.assertReports("句 3：「试」要写在断句表前面")

    def test_post_label_before_table(self):
        b = block(V3L, S4)
        crux = b[b.index("- **卡点**"):b.index("- **译**")]
        text = sub(V3L, crux)
        self.light(sub(text, "- **试**：allude to it 的 it 指什么？\n", "- **试**：allude to it 的 it 指什么？\n" + crux))
        self.assertReports("句 4：「卡点」要写在断句表后面")

    def test_pre_order(self):
        self.light(sub(V3L, "- **结构**：it 占位、并列\n- **注**：bolt 猛冲\n", "- **注**：bolt 猛冲\n- **结构**：it 占位、并列\n"))
        self.assertReports("句 1：断句表前面的项依次是结构、标记、注、试", count=1)

    def test_post_order(self):
        b = block(V3L, S4)
        crux, trans = b[b.index("- **卡点**"):b.index("- **译**")], b[b.index("- **译**"):].rstrip("\n") + "\n"
        self.light(sub(V3L, crux + trans, trans + crux))
        self.assertReports("句 4：断句表后面的项依次是答、怎么拆、卡点、译、句型、延伸、赏析", count=1)

    def test_split_between_answer_and_crux(self):
        # 精读夹具：怎么拆在答和卡点之间；放到答前面或译后面都不行
        b = block(V3J, J1)
        steps = b[b.index("- **怎么拆**"):b.index("- **卡点**")]
        text = sub(V3J, steps)
        self.intensive(sub(text, "- **答**：animals\n", steps + "- **答**：animals\n"))
        self.assertReports("句 1：断句表后面的项依次是答、怎么拆、卡点、译、句型、延伸、赏析", count=1)
        self.intensive(sub(text, "- **句型**：`名词 + 过去分词短语`", steps + "- **句型**：`名词 + 过去分词短语`"))
        self.assertReports("句 1：断句表后面的项依次是答、怎么拆、卡点、译、句型、延伸、赏析", count=1)

    def test_pattern_extension_appreciation_order(self):
        b = block(V3J, J1)
        ext, appr = b[b.index("- **延伸**"):b.index("- **赏析**")], b[b.index("- **赏析**"):].rstrip("\n") + "\n"
        self.intensive(sub(V3J, ext + appr, appr + ext))
        self.assertReports("句 1：断句表后面的项依次是答、怎么拆、卡点、译、句型、延伸、赏析", count=1)

    def test_unknown_and_duplicate(self):
        self.light(sub(V3L, "- **答**：he\n", "- **答**：he\n- **背景**：鼹鼠刚出门。\n"))
        self.assertReports("句 2：未知的项「背景」")
        self.light(sub(V3L, "- **注**：bolt 猛冲\n", "- **注**：bolt 猛冲\n- **注**：fling 扔\n"))
        self.assertReports("句 1：「注」只能写一次")


class TestS14Stuck(Base):
    def test_needs_mark(self):
        self.light(sub(V3L, "- **标记**：词都认识\n"))
        self.assertReports("卡句 2：卡句要写「标记」（词都认识、有生词、没说，三选一）", count=1)

    def test_bad_mark(self):
        self.light(sub(V3L, "- **标记**：词都认识", "- **标记**：都认识"))
        self.assertReports("卡句 2：「标记」只能是词都认识、有生词、没说，不是「都认识」", count=1)

    def test_needs_translation(self):
        self.light(in_block(V3L, K1, "- **译**：鼹鼠看呆了，像着了魔一样，挪不开眼。\n"))
        self.assertReports("卡句 1：缺少「译」", count=1)

    def test_needs_crux_unless_vocab(self):
        b = block(V3L, K2)
        self.light(sub(V3L, b[b.index("- **卡点**"):b.index("- **译**")]))
        self.assertReports("卡句 2：缺少「卡点」", count=1)
        self.light(in_block(V3L, K1, "- **译**：", "- **卡点**：三个词都是“着迷”。\n- **译**："))
        self.assertReports("卡句 1：标签是词汇的卡句不写「卡点」", count=1)

    def test_new_words_need_notes(self):
        self.light(sub(V3L, "- **标记**：词都认识", "- **标记**：有生词"))
        self.assertReports("卡句 2：标记是有生词，要写「注」", count=1)
        self.light(sub(V3L, "- **注**：bewitch 迷住；entrance 使出神；fascinate 使着迷\n"))
        self.assertReports("卡句 1：标签是词汇，要写「注」", count=1)

    def test_mark_on_sentence_optional(self):
        self.light(sub(V3L, "- **结构**：it 占位、并列\n", "- **结构**：it 占位、并列\n- **标记**：词都认识\n"))
        self.assertClean()
        self.light(sub(V3L, "- **结构**：it 占位、并列\n", "- **结构**：it 占位、并列\n- **标记**：会\n"))
        self.assertReports("句 1：「标记」只能是词都认识、有生词、没说，不是「会」", count=1)


class TestS15MinWords(Base):
    def test_hint_below_level(self):
        self.light(V3L, extra={"level": "B2"})                 # B2 读者 28 词；句 4 27 词，卡句 2 21 词不查
        out = self.assertHints("提示 第 1 章 选句：句 4 原句 27 词，B2 读者的长难句一般选 28 词以上的")
        self.assertNotIn("卡句 2 原句 21 词", out)
        self.assertEqual(out.count("长难句一般选"), 1, out)


class TestS16Variety(Base):
    def test_hint(self):
        text = sub(V3L, "- **结构**：非谓语", "- **结构**：指代")
        text = sub(text, "- **结构**：多层从句、指代", "- **结构**：指代")
        self.light(text)
        self.assertHints("提示 第 1 章 选句：长难句 4 句，主标签只有 2 种（it 占位、指代），4 句以上时至少 3 种")

    def test_second_tag_not_counted(self):
        self.light(V3L)
        self.assertHints(absent=["主标签只有"])


class TestS17NoteIsPreread(Base):
    def test_hint(self):
        self.light(sub(V3L, "- **结构**：多层从句、指代\n", "- **结构**：多层从句、指代\n- **注**：trot 小跑\n"))
        self.assertHints("提示 第 1 章 词：句 3 注里的「trot」已经是本章的读前词")


# ---------- 两种模式共用的检查在第三版里的样子 ----------

class TestLint(Base):
    def test_banned_in_gloss_and_translation_not_checked(self):
        w = next(l.split("\t")[0] for l in (SKILL / "reference" / "禁用语.txt").read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith(("#", "re:")))
        text = sub(V3L, "| 所以说， |", f"| {w} |")
        self.light(text)
        self.assertClean()
        self.light(sub(V3L, "- **卡点**：`small wonder`", f"- **卡点**：{w}，`small wonder`"))
        self.assertReports(f"句 1 卡点「{w}」")

    def test_straight_quotes(self):
        self.light(sub(V3L, "| 所以说， |", "| 所以说\"， |"))
        self.assertReports("直引号：句 1 顺读：")
        # 断句栏和答是照原文抄的：原文里有直引号时不报
        src = SOURCE.replace("“Oh, it’s all very well", "“Oh, it's all very well")
        text = V3L.replace("“Oh, it’s all very well", "“Oh, it's all very well")
        self.light(text, source=src)
        self.assertClean()

    def test_try_length(self):
        self.light(sub(V3L, "- **试**：Jumping off 是谁做的？", "- **试**：Jumping off 是谁做的？" + PAD * 2))
        self.assertReports("句 2 试：", "试上限 30")
        self.intensive(sub(V3J, "- **试**：和 not so much 呼应的是哪个词？", "- **试**：和 not so much 呼应的是哪个词？" + PAD * 2))
        self.assertReports("句 3 试：", "试上限 30")         # 精读和轻读共用 v3.sentence.try_chars

    def test_crux_limit_by_mode(self):
        longer = "- **卡点**：读到 `that held up` 容易以为谓语来了。" + "这一句的意思是" * 12   # 105 字：轻读超（100），精读不超（120）
        line = lambda text, head: re.search(r"^- \*\*卡点\*\*：.*$", block(text, head), flags=re.M).group(0)
        self.light(in_block(V3L, S4, line(V3L, S4), longer))
        self.assertReports("句 4 卡点：105 字，卡点上限 100")
        self.intensive(in_block(V3J, J5, line(V3J, J5), longer))
        n, out = self.check()
        self.assertNotIn("卡点上限", out)

    def test_bold_table_cell_not_a_quote(self):
        # 断句栏整格是粗体时，不当成「| *引文* |」去原文里找
        self.light(sub(V3L, "| **The Mole** **was** bewitched, | 鼹鼠着了魔， |\n| entranced, fascinated. | 出了神，入了迷。 |",
                       "| **The Mole** **was** | 鼹鼠 |\n| bewitched, entranced, fascinated. | 着了魔，出了神，入了迷。 |"))
        self.assertClean()


class TestTagTable(Base):
    def test_missing_tag_is_problem(self):
        no_split = PREFACE_V3.replace("| 并列 | 几个谓语或几个分句并排 | He **came**, **saw** and **left**. |\n", "")
        self.light(V3L, preface=no_split)
        out = self.assertReports("第 1 章 句子结构：句 1用了「并列」，前言的句子结构表里没有", count=1)
        self.assertIn("其中 格式和引文 0，禁用语 0，长度 0，直引号 0，术语 0，语法术语 0，句子结构 1", out)

    def test_unused_tag_is_hint(self):
        self.light(V3L, preface=PREFACE_V3)
        self.assertHints("提示 全部单元 句子结构：前言的句子结构表里有「主谓隔开」，讲义一次没用到",
                         absent=["表里有「并列」", "「词汇」"])

    def test_no_table_is_hint(self):
        self.light(V3L, preface=PREFACE)
        self.assertHints("提示 全部单元 句子结构：前言.md 里没有「## 句子结构」表")
        self.light(V3L)          # 没有前言：也是一条提示
        self.assertHints("提示 全部单元 句子结构：没有 讲义/前言.md：第三版的前言要有「## 句子结构」表")
        self.light(V3L, fmt=None)          # 第一、二版不提示
        self.assertNotIn("没有 讲义/前言.md", self.check()[1])


class TestGrammarTermsV3(Base):
    def test_tag_and_try_count_as_used(self):
        # 独立结构只在卡句 2 的「结构」里，分词短语只在句 2 的「试」里：都算用到，不提示；主干第三版不再是模板术语
        text = in_block(V3L, K2, "是独立结构，", "")
        text = in_block(text, S2, "Jumping off 是谁做的？", "Jumping off 这个分词短语是谁做的？")
        self.light(text, preface=PREFACE_V3)
        self.assertHints("表里有「倒装」", absent=["表里有「独立结构」", "表里有「分词短语」"])

    def test_tag_alone_is_not_missing(self):
        # 「结构」里的标签不算讲解用了术语：表里没有「独立结构」也不报
        no_abs = PREFACE_V3.replace("| 独立结构 | 分词自己带主语，不借主句的 | **The work done**, we went home. |\n", "", 1)
        self.assertNotEqual(no_abs, PREFACE_V3)
        self.light(in_block(V3L, K2, "是独立结构，", ""), preface=no_abs)
        self.assertHints(absent=["用了「独立结构」"])

    def test_zhugan_not_template_term_in_v3(self):
        no_zg = PREFACE_V3.replace("| 主干 |", "| 主语 |", 1)
        self.assertNotEqual(no_zg, PREFACE_V3)
        self.light(in_block(V3L, S2, "Jumping off 是谁做的？", "主干后面 Jumping off 是谁做的？"), preface=no_zg)
        self.assertHints(absent=["用了「主干」"])
        self.light(LIGHT, preface=no_zg, fmt=None)           # 第一、二版照旧查主干
        n, out = self.check()
        self.assertIn("用了「主干」，前言的语法术语表里没有", out)


class TestPostEstimate(Base):
    def test_over_limit_is_hint(self):
        b = block(V3L, S1)
        rows = b[b.index("| · then,"):b.index("\n\n- **答**")] + "\n"
        heavy = sub(V3L, rows, rows * 6)                     # 断句表多出 30 行（S3 会报对不上，这里只看篇幅提示）
        self.light(heavy)
        n, out = self.check()
        self.assertRegex(out, r"提示 第 1 章 篇幅：估计读后约 \d\.\d 页，上限 3 页；估计和实排差 0.1 页上下，以 PDF 实排为准")

    def test_estimate(self):
        b = load_build()
        self.light(V3L)
        b.load_project(self.root)
        est = b.load_rules()["v3"]["light"]["md_estimate"]
        self.assertAlmostEqual(b.post_estimate_v3(b.parse_chapter(1), est), 2.50, delta=0.1)     # 校准后的参数、下置排法


# ---------- 数据（给难句本、单词本、PDF 用）和位置名 ----------

class TestData(Base):
    def test_blocks(self):
        b = load_build()
        self.light(V3L)
        b.load_project(self.root)
        ch = b.parse_chapter(1)
        self.assertEqual(ch["errors"], [])
        self.assertEqual(ch["format"], 3)
        self.assertIs(ch["stuck"], ch["extra"])
        s1, s2, s3, s4 = ch["sentences"]
        k1, k2 = ch["extra"]
        self.assertEqual([s["kind"] for s in (s1, s2, s3, s4, k1, k2)], ["精讲", "练习", "练习", "精讲", "卡句", "卡句"])
        self.assertEqual(s1["tags"], ["it 占位", "并列"])
        self.assertEqual((s1["mark"], k1["mark"], k2["mark"]), (None, "有生词", "词都认识"))
        self.assertEqual(s1["notes"], [("bolt", "猛冲")])
        self.assertEqual(s4["notes"], [("allude to", "提到，暗指")])
        self.assertEqual(s3["try"], {"q": "who 引出的从句，谓语是哪个词？", "a": "trotted"})
        self.assertIsNone(k1["try"])
        self.assertEqual(s1["chunks"][0], {"depth": 0, "text": "It was small wonder,", "bold": ["It", "was"],
                                           "md": "**It** **was** small wonder,"})
        self.assertEqual([c["depth"] for c in s3["chunks"]], [0, 1, 2, 2, 2, 2])
        self.assertEqual(s1["chunks"][1]["text"], "then,")
        self.assertEqual(len(s1["gloss"]), len(s1["chunks"]))
        self.assertEqual(s1["gloss"][1], "所以说，")
        self.assertEqual([it["label"] for it in s1["items"]], ["卡点", "译"])
        self.assertEqual(s2["items"], [])
        self.assertEqual(s1["quote"][:20], "It was small wonder,")

    def test_intensive_blocks(self):
        b = load_build()
        self.intensive(V3J)
        b.load_project(self.root)
        ch = b.parse_chapter(1)
        self.assertEqual(ch["errors"], [])
        self.assertEqual({s["kind"] for s in ch["sentences"]}, {"精讲"})
        self.assertEqual([it["label"] for it in ch["sentences"][0]["items"]], ["怎么拆", "卡点", "译", "句型", "延伸", "赏析"])
        self.assertEqual(len(ch["sentences"][0]["items"][0]["sub"]), 2)
        self.assertTrue(ch["grammar_title"])

    def test_locations(self):
        b = load_build()
        self.light(V3L)
        b.load_project(self.root)
        locs = [loc for loc, _ in b.located_lines(b.parse_chapter(1))]
        for want in ("句 3 断句", "句 3 顺读", "句 3 试", "句 4 注", "卡句 2 卡点", "卡句 1 断句表", "卡句 小节标题", "理解答案 2 译"):
            self.assertIn(want, locs)
        pairs = list(b.located_lines(b.parse_chapter(1)))
        self.assertIn(("句 1 断句", "· then,"), pairs)
        self.assertIn(("句 1 顺读", "所以说，"), pairs)

    def test_tags_file(self):
        b = load_build()
        tags = b.load_tags()
        self.assertEqual([t["tag"] for t in tags],
                         ["主谓隔开", "it 占位", "后置修饰", "多层从句", "非谓语", "独立结构", "插入", "并列", "省略", "倒装",
                          "固定框架", "指代", "词汇"])
        self.assertTrue(all(t["definition"] and t["how"] and t["example"] for t in tags))


# ---------- rules.json 只增不改 ----------

class TestRules(unittest.TestCase):
    ORIGINAL = "5b78c2c694c59c5e5b5059415c213224b3cc8b6d3c9d999cf685b0cf2c8c78b8"     # 第三版以前的 rules.json，不含说明文字

    def test_only_additions(self):
        """第三版只加了 v3 和 profile 的三个键，以前的值没改。以「_」开头的说明文字不算。"""
        def values(o):
            if isinstance(o, dict):
                return {k: values(v) for k, v in o.items() if not k.startswith("_")}
            return [values(v) for v in o] if isinstance(o, list) else o
        old = values(json.loads((SKILL / "scripts" / "rules.json").read_text(encoding="utf-8")))
        del old["v3"]
        for k in ("long_sentence_words", "long_pct", "drill_top"):
            del old["profile"][k]
        self.assertEqual(hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), self.ORIGINAL)

    def test_v3_values(self):
        rules = json.loads((SKILL / "scripts" / "rules.json").read_text(encoding="utf-8"))
        p, v3 = rules["profile"], rules["v3"]
        self.assertEqual((p["long_sentence_words"], p["long_pct"], p["drill_top"]), (30, [5, 15], 12))
        s = v3["sentence"]
        self.assertEqual((s["tags"], s["chunk_words"], s["chunk_depth"], s["bold_words"], s["gloss_chars"], s["notes"],
                          s["note_chars"], s["answer_words"], s["try_chars"], s["steps_intensive"]),
                         ([1, 2], [1, 10], 2, 4, 18, [0, 4], 10, 8, 30, [1, 5]))
        self.assertEqual(s["min_words"], {"A2": 18, "B1": 22, "B2": 28, "C1": 32})
        self.assertEqual(s["tag_variety"], {"min_sentences": 4, "min_tags": 3})
        c = v3["light"]["counts"]
        self.assertEqual(c["long"], {"读前词": [5, 8], "人物": [0, 5], "精讲句": [2, 2], "练习句": [2, 3], "理解": [2, 2],
                                     "词条": [2, 3], "复述": [1, 1]})
        self.assertEqual(c["short"], {"读前词": [3, 5], "人物": [0, 5], "精讲句": [1, 1], "练习句": [1, 2], "理解": [2, 2],
                                      "词条": [2, 2], "复述": [1, 1]})
        self.assertEqual(v3["light"]["max_chars"], {"卡点": 100})        # 试的上限两种模式共用，在 v3.sentence.try_chars
        self.assertEqual(v3["light"]["md_estimate"]["每页行数"], 31)        # 按实排校准
        self.assertEqual(v3["light"]["pdf"], {"post_pages": 3})


# ---------- 卡句.txt 的提示、sentences / words / stuck 的转发 ----------

STUB = '''
def run(name, args, build):
    print("RUN", name, " ".join(args), build.P.format, build.P.slug, len(build.parse_chapter(1)["sentences"]))
    return 0


def locate_stuck(build):
    return [
        {"line": 4, "text": "The Mole was bewitched", "result": "命中", "unit": 1,
         "sentence": "The Mole was bewitched, entranced, fascinated."},
        {"line": 5, "text": "As he gazed, something bright and small", "result": "命中", "unit": 1,
         "sentence": "As he gazed, something bright and small seemed to twinkle down in the heart of it, vanished, "
                     "then twinkled once more like a tiny star."},
        {"line": 6, "text": "allude to it; so he dropped", "result": "命中", "unit": 1,
         "sentence": "The Mole knew well that it is quite against animal-etiquette to dwell on possible trouble ahead, "
                     "or even to allude to it; so he dropped the subject."},
        {"line": 7, "text": "The Rat said nothing", "result": "多处", "unit": None, "sentence": ""},
        {"line": 8, "text": "something in chapter two", "result": "命中", "unit": 2, "sentence": "Something."},
    ]
'''


class TestNotebook(Base):
    def skill_copy(self, stub=True):
        """skill 的副本（scripts 里的 .py 和 rules.json、reference/）；stub=True 时放一个假的 notebook.py。"""
        root = Path(self.tmp.name) / "skill"
        if not root.exists():
            (root / "scripts").mkdir(parents=True)
            for f in ("build.py", "lexicon.py", "source.py", "rules.json"):
                shutil.copy(SKILL / "scripts" / f, root / "scripts" / f)
            shutil.copytree(SKILL / "reference", root / "reference")
        nb = root / "scripts" / "notebook.py"
        if stub:
            nb.write_text(STUB, encoding="utf-8")
        elif nb.exists():
            nb.unlink()
        return root / "scripts" / "build.py"

    def test_not_implemented(self):
        self.light(V3L)
        build = self.skill_copy(stub=False)
        for cmd in ("sentences", "words", "stuck"):
            code, out = self.run_build(cmd, build=build)
            self.assertNotEqual(code, 0)
            self.assertIn(f"build.py {cmd} 还没实现：要同目录的 notebook.py", out)

    def test_forwarding(self):
        self.light(V3L, extra={"slug": "willows"})
        build = self.skill_copy()
        code, out = self.run_build("sentences", "--anki", "--pdf", build=build)
        self.assertEqual((code, out), (0, "RUN sentences --anki --pdf 3 willows 4\n"))
        r = subprocess.run([sys.executable, str(build), "words", "--anki", str(self.root)], capture_output=True, text=True)
        self.assertEqual(r.stdout, "RUN words --anki 3 willows 4\n")

    def test_stuck_hints(self):
        self.light(V3L)
        (self.root / "卡句.txt").write_text("第 1 章\n", encoding="utf-8")
        out = self.run_build("check", build=self.skill_copy())[1]
        hints = [l for l in out.splitlines() if "卡句：" in l]
        # 第 4 行讲在卡句 1，第 6 行是句 4 的一段；第 7 行不是命中，第 8 行的单元没有讲义：都不报
        self.assertEqual(hints, ["提示 第 1 章 卡句：卡句.txt 第 5 行「As he gazed, something bright…」定位到本章，"
                                 "讲义里没讲（写进长难句或「## 卡句」）"], out)
        self.assertIn("问题 0 个", out)

    def test_stuck_file_without_notebook(self):
        self.light(V3L)
        (self.root / "卡句.txt").write_text("第 1 章\n", encoding="utf-8")
        out = self.run_build("check", build=self.skill_copy(stub=False))[1]
        self.assertIn("提示 全部单元 卡句：有 卡句.txt，但还没有 scripts/notebook.py，卡句讲了没有没查", out)

    def test_no_stuck_file_no_hint(self):
        self.light(V3L)
        self.assertNotIn("卡句：", self.run_build("check", build=self.skill_copy())[1])

    def test_stuck_words(self):
        b = load_build()
        self.assertEqual(b.stuck_words("good-nature"), b.stuck_words("good nature"))
        self.assertEqual(b.stuck_words("“Oh, it’s all­ very well”"), ["oh", "it's", "all", "very", "well"])
        self.assertEqual(b.stuck_words("ﬁne​ day"), ["fine", "day"])


if __name__ == "__main__":
    unittest.main()
