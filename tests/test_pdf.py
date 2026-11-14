"""build.py 的 PDF 部分：轻读版式、精读单元的读前和补充句、按模式写的封面和“怎么用”页、目录页码的锚点、找排版程序。
在 skill 根目录运行：python3 -m unittest discover -s tests

大部分测试只生成 HTML，或者用拼出来的「读回文字」测锚点，不启动任何程序；找排版程序、启动命令的测试都换掉了 subprocess.run，
摆的是假的程序文件。TestRealPdf 真的出 PDF，会运行 chrome-headless-shell（没有界面），平时跳过；要跑时设环境变量
ER_PDF_TEST=1（还要 macOS、renderer.py install 装好的 chrome-headless-shell 和 swift；只用它，不用本机带界面的浏览器）：
  ER_PDF_TEST=1 python3 -m unittest discover -s tests

夹具（fixtures/）：
  原文.txt、精读.md、轻读.md、前言.md     见 test_build.py
  pdf_精读两章_第一版.html               第一版 build.py 对「两章都是 精读.md、带 前言.md」的项目生成的合订本 HTML
                                        （带排紧、栏目排紧、赏析点跨页和目录页码）。第一版的项目新代码必须排得一模一样
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
BUILD = HERE.parent / "scripts" / "build.py"
RENDERER = HERE.parent / "scripts" / "renderer.py"
SOURCE = (FIX / "原文.txt").read_text(encoding="utf-8")
INTENSIVE = (FIX / "精读.md").read_text(encoding="utf-8")
LIGHT = (FIX / "轻读.md").read_text(encoding="utf-8")
PREFACE = (FIX / "前言.md").read_text(encoding="utf-8")
V1_UNIT_SHA = "ef6e9692074a774962c4d65292c7d88f2af3264ec483e7f19913ff4495218a99"     # 第一版：第 2 章分章、不排紧的 HTML


def section(text, name):
    """「## name」一节（含标题行）。"""
    m = re.search(rf"^## {re.escape(name)}\n.*?(?=^## |\Z)", text, flags=re.M | re.S)
    assert m, f"没有「## {name}」"
    return m.group(0)


def retitle(text, n):
    return re.sub(r"\A# .*", f"# 第 {n} 章讲解", text)


def intensive_v2(n=1):
    """精读讲义，前面加上轻读夹具的读前，最后加上它的补充句（引文都出自同一份原文）。"""
    text = retitle(INTENSIVE, n)
    head, rest = text.split("\n", 1)
    return head + "\n\n" + section(LIGHT, "读前") + rest.lstrip("\n").rstrip("\n") + "\n\n" + section(LIGHT, "补充句")


def plain(html_text):
    """去掉标签和空白，只留文字。"""
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", html_text))


def load_build():
    """每个测试一份新的 build 模块（P、FONT_DIR、CHROME 这些模块级的状态不互相影响）。"""
    spec = importlib.util.spec_from_file_location("er_build_pdf", BUILD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class PdfBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "项目"
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ENGLISH_READER_FONTS", None)      # 字体目录会写进 HTML；测试一律用系统字体
        os.environ.pop("ER_CHROME", None)
        os.environ.pop("ER_ALLOW_GUI_BROWSER", None)
        self.b = load_build()
        # 本机真装没装 chrome-headless-shell 都不影响测试：装的位置换成测试的临时目录（一开始是空的）
        self.renderer = self.b.sibling("renderer")
        self.shell_root = mock.patch.object(self.renderer, "ROOT", Path(self.tmp.name) / "renderer-cache")
        self.shell_root.start()

    def tearDown(self):
        self.shell_root.stop()
        self.env.stop()
        self.tmp.cleanup()

    def project(self, units, default_mode=None, preface=None, fmt=None):
        """units：[(单元号, 讲义, mode 或 None, 标题)]。default_mode=None 时 设置.json 里不写这个键（第一版的写法）。
        fmt=3 时写 "format": 3（第三版）。"""
        (self.root / "原文").mkdir(parents=True, exist_ok=True)
        (self.root / "讲义").mkdir(parents=True, exist_ok=True)
        cfg = {"title": "The Wind in the Willows", "author": "Kenneth Grahame", "unit": "章", "units": [],
               "level": "B1", "genre": "小说", "appreciation": True, "writing": True, "fonts": None}
        if default_mode is not None:
            cfg["default_mode"] = default_mode
        if fmt is not None:
            cfg["format"] = fmt
        for n, text, mode, title in units:
            cfg["units"].append({"n": n, "title": title, **({"mode": mode} if mode else {})})
            (self.root / "原文" / f"第{n:02d}章.txt").write_text(SOURCE, encoding="utf-8")
            (self.root / "讲义" / f"第{n:02d}章.md").write_text(text, encoding="utf-8")
        (self.root / "设置.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if preface is not None:
            (self.root / "讲义" / "前言.md").write_text(preface, encoding="utf-8")
        self.b.load_project(self.root)
        nums = self.b.available()
        self.chs = self.b.load_units(nums)
        self.matches = {n: self.b.sentence_hits(c) for n, c in self.chs.items()}
        return [self.chs[n] for n in nums]

    def html(self, chapters, pages=None, tight=None, sect=None, unkeep=None, book=None):
        return self.b.page_html(chapters, self.matches, pages, tight or {}, sect or {}, unkeep or {}, book)

    def front_text(self, html_text):
        """封面和“怎么用”页的文字（目录之前）。"""
        return plain(html_text.split('<nav class="front toc">')[0].split("<body>")[1])

    def body_of(self, html_text, n):
        """第 n 单元的 HTML：从它的第一个 section 起到下一个单元之前。"""
        start = html_text.index(f'style="page:c{n}-')
        start = html_text.rindex("<section", 0, start)
        nxt = html_text.find(f'style="page:c{n + 1}-', start)
        return html_text[start:html_text.rindex("<section", 0, nxt) if nxt > 0 else len(html_text)]


# ---------- 第一版的项目：排出来和第一版一模一样 ----------

class TestV1Unchanged(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, INTENSIVE, None, "The River Bank"), (2, retitle(INTENSIVE, 2), None, "The River Bank (copy)")],
                                     preface=PREFACE)

    def test_book_html_identical_to_v1(self):
        tight, sect, unkeep = {1: {1: 1, 2: 2}, 2: {3: 1}}, {1: {"open", "words", "gram", "essay", "write", "ans"}, 2: {"words"}}, {1: {1, 3}}
        got = self.html(self.chapters, [4, 5, 6, 36], tight, sect, unkeep, True)
        self.assertEqual(got, (FIX / "pdf_精读两章_第一版.html").read_text(encoding="utf-8"))

    def test_unit_html_identical_to_v1(self):
        got = self.html([self.chs[2]], book=False)
        self.assertEqual(hashlib.sha256(got.encode()).hexdigest(), V1_UNIT_SHA)

    def test_no_v2_markup(self):
        got = self.html(self.chapters, book=True)
        for s in ("section.pre", self.b.PRE_MARK, "c1-pre", "读后"):
            self.assertNotIn(s, got)


# ---------- 轻读单元 ----------

class TestLightLayout(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, LIGHT, None, "The River Bank")], default_mode="轻读")
        self.page = self.html(self.chapters, book=False)
        self.unit = self.body_of(self.page, 1)

    def test_preread_is_first_page(self):
        self.assertTrue(self.unit.startswith('<section class="pre" id="ch1" style="page:c1-pre">'), self.unit[:120])
        pre = self.unit.split('<section class="post"')[0]
        self.assertIn(self.b.PRE_MARK, pre)
        for s in ("背景", "人物", "本章的词", "the Mole", "the Badger", "luncheon-basket", "/skʌl/", "野餐篮"):
            self.assertIn(s, pre)
        self.assertEqual(pre.count('<td class="pw">'), 6)
        for s in ("理解", "长难句", "答案"):       # 读后的东西一样不进读前页
            self.assertNotIn(f'<h2 class="sk">{s}</h2>', pre)

    def test_post_starts_new_page_in_order(self):
        post = self.unit.split('<section class="post"', 1)[1]
        self.assertTrue(post.startswith(' style="page:c1-post"'))
        marks = ['<h2 class="sk">理解</h2>', '<h2 class="sk">长难句</h2>', '<h2 class="sk">词的用法</h2>',
                 '<h2 class="sk" id="c1-retell">复述</h2>', '<h2 class="sk" id="c1-extra">补充句</h2>', '<div class="lans"']
        where = [post.index(m) for m in marks]
        self.assertEqual(where, sorted(where))

    def test_sentences_like_intensive(self):
        post = self.unit.split('<section class="post"', 1)[1]
        self.assertIn('<b class="core">', post)             # 主干在原句里加粗
        self.assertIn('<div class="b alert"><div class="tag">卡点</div>', post)
        self.assertIn('id="c1-s1"', post)
        self.assertIn('id="c1-x1"', post)                   # 补充句单独编号
        for lab in ("句型", "举一反三", "赏析"):
            self.assertNotIn(f'<div class="tag">{lab}</div>', post)

    def test_answers(self):
        ans = self.unit.split('<div class="lans"', 1)[1]
        comp = self.chs[1]["comprehension"]
        self.assertEqual(ans.count('<li id="c1-a'), len(comp["questions"]))
        self.assertIn(self.b.WAIT, ans)
        self.assertIn(comp["answers"][0]["quotes"][0][:30], ans)
        self.assertIn(self.chs[1]["retell"]["refs"][0][:40], ans)
        post = self.unit.split('<div class="lans"', 1)[0]
        self.assertNotIn(self.chs[1]["retell"]["refs"][0][:40], post)      # 参考只在答案里

    def test_hints(self):
        for h in self.chs[1]["retell"]["prompts"][0]["hints"]:
            self.assertIn(f'<span class="hk">{h}</span>', self.unit)

    def test_no_intensive_parts(self):
        for s in ("自测", "语法", "本章地图", "精讲句", "c1-open"):
            self.assertNotIn(s, self.unit)

    def test_page_css(self):
        css = self.page.split("<style>")[1].split("</style>")[0]
        self.assertIn("@page c1-pre{margin-top:18mm}", css)
        self.assertIn('@page c1-post{@top-left{content:"The Wind in the Willows · 第 1 章"}@top-right{content:"读后"}}', css)
        self.assertNotIn("c1-open", css)
        self.assertIn("section.pre", css)

    def test_single_cover(self):
        cover = self.page.split("<body>")[1].split("</section>")[0]
        self.assertIn("读前 · 理解 · 句子 · 词汇 · 复述", cover)


# ---------- 精读单元的读前和补充句 ----------

class TestIntensiveV2(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, intensive_v2(1), "精读", "The River Bank")], default_mode="轻读")
        self.unit = self.body_of(self.html(self.chapters, book=False), 1)

    def test_preread_before_opener(self):
        self.assertTrue(self.unit.startswith('<section class="pre" id="ch1" style="page:c1-pre">'))
        self.assertIn('<section class="open" id="c1-open" style="page:c1-open">', self.unit)
        self.assertLess(self.unit.index("c1-pre"), self.unit.index("c1-open"))
        self.assertEqual(self.unit.count('id="ch1"'), 1)

    def test_extra_before_quiz(self):
        order = [self.unit.index(s) for s in ('id="c1-write"', 'id="c1-extra"', 'id="c1-quiz"')]
        self.assertEqual(order, sorted(order))
        extra = self.unit.split('id="c1-extra"')[1].split('id="c1-quiz"')[0]
        self.assertIn('id="c1-x1"', extra)
        self.assertIn('<b class="core">', extra)
        self.assertIn('<span class="mk">补 1</span>', self.unit)        # 章首页的地图里也列出来

    def test_page_css_has_extra_head(self):
        css = self.html(self.chapters, book=False).split("<style>")[1]
        self.assertIn('@top-right{content:"补充句"}', css)

    def test_one_bookmark_heading(self):
        # PDF 书签按 h1–h6 生成：单元名的 h1 只在读前页；章首页的单元名用 div，样子和 h1.oh 一样
        self.assertEqual(self.unit.count("<h1"), 1)
        self.assertIn('<h1 class="oh">第 1 章 <span class="ut">The River Bank</span></h1>', self.unit)
        self.assertIn('<div class="oh">第 1 章</div><p class="og">', self.unit)
        css = self.html(self.chapters, book=False).split("<style>")[1]
        self.assertIn("div.oh{font:600 15pt/1.3 var(--sans);color:var(--ink);margin:2.5mm 0 1mm}", css)
        self.assertIn(".open.tight div.oh{margin:1.6mm 0 .6mm}", css)

    def test_v1_opener_keeps_h1(self):
        chapters = self.project([(1, INTENSIVE, None, "The River Bank")])
        unit = self.body_of(self.html(chapters, book=False), 1)
        self.assertIn('<h1 class="oh">第 1 章</h1>', unit)
        self.assertNotIn('<div class="oh">', unit)


# ---------- 封面、“怎么用”页、目录 ----------

class TestFront(PdfBase):
    INTENSIVE_WORDS = ("精读", "语法", "自测", "精讲", "赏析", "写作", "举一反三", "回头看")

    def test_all_light_has_no_intensive_words(self):
        chapters = self.project([(1, LIGHT, None, "The River Bank"), (2, retitle(LIGHT, 2), None, "Again")], default_mode="轻读")
        front = self.front_text(self.html(chapters, book=True))
        for w in self.INTENSIVE_WORDS:
            self.assertNotIn(w, front)
        self.assertIn("读前·理解·句子·词汇·复述", front)
        self.assertIn("每章先看读前一页，再读原文，读完看读后。", front)
        self.assertIn("长难句4句·词条", front)

    def test_mixed(self):
        chapters = self.project([(1, intensive_v2(1), "精读", "The River Bank"), (2, retitle(LIGHT, 2), None, "The Open Road")],
                                default_mode="轻读", preface=PREFACE)
        page = self.html(chapters, pages=[4, 5, 6, 37], book=True)
        front = self.front_text(page)
        self.assertIn("语法专题1个", front)                 # 只数精读单元
        self.assertIn("自测10题", front)
        self.assertIn("理解3题", front)
        self.assertIn("读完看读后（精读的章是讲解）", front)
        self.assertIn("第2章是轻读", front)
        self.assertIn("第1章是精读，讲解依次是章首页、精讲句", front)
        toc = page.split('<nav class="front toc">')[1].split("</nav>")[0]
        self.assertIn('href="#ch1"', toc)
        self.assertIn('href="#ch2"', toc)
        self.assertIn("精读 · 精讲", toc)
        self.assertIn("轻读 · 理解 3 题", toc)
        self.assertIn("The Open Road", toc)
        for p in ("6", "37"):
            self.assertIn(f'<span class="tp">{p}</span>', toc)

    def test_intensive_only_with_preread(self):
        chapters = self.project([(1, intensive_v2(1), None, "The River Bank")])
        front = self.front_text(self.html(chapters, book=True))
        self.assertIn("读前·句子·词汇·语法·赏析·写作", front)
        self.assertIn("先看读前一页，再读原文，读完看讲解。", front)
        self.assertNotIn("读后", front)


# ---------- 第二版的项目：第三版改 PDF 以前生成的 HTML（sha256），新代码必须排得一模一样 ----------

class TestV2Unchanged(PdfBase):
    LIGHT_UNIT = "fe8712c3d1d3ef6634ad07ebff767ddc2162505dab7d1aee9221a9ef06dbcc08"
    LIGHT_UNIT_TIGHT = "e1bf389e275ccc18261d678f977ebf46fc1e4cc1e69b1cd508531733eb97dd5c"
    MIXED_BOOK = "ccd8df64a1cdb254896332a668783e2a6b54b64cfb52683a777779ec920011dc"
    INTENSIVE_UNIT = "68785e32c5c288c3665691f09034f7304ab935f0b802013d1f12ab6b134242e7"
    DEMO_BOOK = "b35797a6d0fc9c09e4021126f4cace3f771c4a5fe2f1dc506650636d8cd02b0e"     # fixtures/demo_snapshot 的合订本

    def sha(self, text):
        return hashlib.sha256(text.encode()).hexdigest()

    def test_light_unit(self):
        chapters = self.project([(1, LIGHT, None, "The River Bank")], default_mode="轻读")
        self.assertEqual(self.sha(self.html(chapters, book=False)), self.LIGHT_UNIT)
        self.assertEqual(self.sha(self.html(chapters, sect={1: {"post", "pre"}}, book=False)), self.LIGHT_UNIT_TIGHT)

    def test_mixed_book(self):
        chapters = self.project([(1, intensive_v2(1), "精读", "The River Bank"), (2, retitle(LIGHT, 2), None, "The Open Road")],
                                default_mode="轻读", preface=PREFACE)
        got = self.html(chapters, pages=[4, 5, 6, 37], tight={1: {2: 1}}, sect={1: {"pre", "words"}, 2: {"post"}}, book=True)
        self.assertEqual(self.sha(got), self.MIXED_BOOK)
        self.assertNotIn(".cg{", got)                    # 第三版的样式不进第一、二版的页面

    def test_intensive_unit(self):
        chapters = self.project([(1, intensive_v2(1), None, "The River Bank")])
        self.assertEqual(self.sha(self.html(chapters, book=False)), self.INTENSIVE_UNIT)

    def test_demo_snapshot_book(self):
        self.b.FONT_DIR.append(None)
        self.b.load_project(FIX / "demo_snapshot")
        nums = self.b.available()
        chs = self.b.load_units(nums)
        matches = {n: self.b.sentence_hits(c) for n, c in chs.items()}
        got = self.b.page_html([chs[n] for n in nums], matches, [4, 5, 6, 20], {}, {}, {}, True)
        self.assertEqual(self.sha(got), self.DEMO_BOOK)


# ---------- 第三版 ----------

V3L = (FIX / "v3_轻读.md").read_text(encoding="utf-8")
V3J = (FIX / "v3_精读.md").read_text(encoding="utf-8")
TAG_TABLE = ("## 句子结构\n\n本书长难句用到的结构。例句是自造的。\n\n| 标签 | 意思 | 例子 |\n| --- | --- | --- |\n"
             "| it 占位 | it 先占住主语的位置，真的在后面 | **It** is hard **to say no**. |\n"
             "| 并列 | 几个谓语或几个分句并排 | He **came**, **saw** and **left**. |\n")
PREFACE_V3 = PREFACE.rstrip("\n") + "\n\n" + TAG_TABLE


def tries(text):
    """讲义里「试」的问题。"""
    return re.findall(r"^- \*\*试\*\*：(.+)$", text, flags=re.M)


class TestV3Light(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, V3L, None, "The River Bank")], default_mode="轻读", fmt=3)
        self.b.V3_PDF[:] = [{"chunk_layout": "对排", "keep_rows": 12}]      # 这一组看对排的网格；下置见 test_below_layout
        self.page = self.html(self.chapters, book=False)
        self.unit = self.body_of(self.page, 1)
        self.post = self.unit.split('<section class="post"', 1)[1].split('<section class="post stuck"')[0]
        self.stuck = self.unit.split('<section class="post stuck"', 1)[1]

    def test_order(self):
        # 读前一页 → 读后（长难句、理解、词的用法、复述）→ 答案区 → 卡句另起一页
        marks = ['<section class="pre"', '<h2 class="sk">长难句</h2>', '<p class="reread">', '<h2 class="sk">理解</h2>',
                 '<h2 class="sk">词的用法</h2>', '<h2 class="sk" id="c1-retell">复述</h2>', '<div class="lans"',
                 '<div class="ah">长难句 · 整句和译</div>', '<div class="ah">理解</div>',
                 '<section class="post stuck" style="page:c1-stuck" id="c1-extra">', '<h2 class="sk">卡句</h2>']
        where = [self.unit.index(m) for m in marks]
        self.assertEqual(where, sorted(where))
        self.assertNotIn(self.b.EXTRA, self.page.split("</style>")[1])

    def test_overview_in_answers(self):
        """答案区：精讲句的整句骨架（断句表连回整句，粗体照排）排在译前面；练习句没有。"""
        ans = self.post.split('<div class="ah">长难句 · 整句和译</div>', 1)[1].split('<div class="ah">理解</div>')[0]
        self.assertEqual(ans.count('<p class="ov">'), 2)
        self.assertIn('<p class="ov"><b class="core">It</b> <b class="core">was</b> small wonder,', ans)
        self.assertLess(ans.index('<p class="ov">'), ans.index("</p><p>"))

    def test_grid(self):
        self.assertEqual(self.post.count('<div class="cg keep">'), 4)
        self.assertIn('<div class="cr d0"><div class="ce"><b class="core">It</b> <b class="core">was</b> small wonder,</div>'
                      '<div class="cz">难怪（这件事）——</div></div>', self.post)
        self.assertIn('<div class="cr d1"><div class="ce">then,</div><div class="cz">所以说，</div></div>', self.post)
        self.assertIn('<div class="cr d2"><div class="ce">who trotted along the side of the hedge</div>', self.post)
        css = self.page.split("<style>")[1]
        self.assertIn(".cr{display:grid;grid-template-columns:58% 42%;", css)
        self.assertIn(".cr.d1 .ce,.cr.d2 .ce{border-left:.5pt solid var(--gl);padding-left:.75em}", css)

    def test_tag_and_mark_boxes(self):
        self.assertIn('<span class="tgs"><span class="tg">it 占位</span><span class="tg">并列</span></span></div>', self.post)
        self.assertIn('<span class="tgs"><span class="tg">词汇</span><span class="tg tgm">有生词</span></span>', self.stuck)
        self.assertIn('<span class="tg tgm">词都认识</span>', self.stuck)
        # 小框不在 h3 里（PDF 书签取 h3 的文字）
        for h3 in re.findall(r"<h3.*?</h3>", self.unit):
            self.assertNotIn('class="tg', h3)

    def test_no_quote_try_answer(self):
        self.assertNotIn('class="orig', self.unit)              # 原句不单独排，断句表就是原句
        for q in tries(V3L):
            self.assertNotIn(q, self.unit)
        self.assertNotIn('<div class="tag">试</div>', self.unit)
        self.assertNotIn('<div class="tag">答</div>', self.unit)
        self.assertNotIn("possible trouble ahead</p>", self.unit)

    def test_no_core_match(self):
        with mock.patch.object(self.b, "core_match", side_effect=AssertionError("第三版不用 core_match")):
            self.html(self.chapters, book=True)

    def test_notes_line(self):
        self.assertIn('</div><p class="nts"><span class="ntl">注</span><span class="c">bolt</span> 猛冲</p>', self.post)
        self.assertIn('<span class="c">bewitch</span> 迷住 · <span class="c">entrance</span> 使出神', self.stuck)

    def test_translation_in_answers(self):
        ans = self.post.split('<div class="lans"', 1)[1]
        before = self.post.split('<div class="lans"', 1)[0]
        t1 = "所以难怪他突然把刷子往地上一扔"
        self.assertIn(t1, ans)
        self.assertNotIn(t1, before)
        self.assertNotIn('<div class="tag">译</div>', before)
        lt = ans.split('<ol class="ql al lt">', 1)[1].split("</ol>")[0]
        self.assertEqual(re.findall(r'<li id="c1-t(\d)"><a class="qn" href="#c1-s(\d)">', lt), [("1", "1"), ("4", "4")])
        self.assertIn('<div class="b alert"><div class="tag">卡点</div>', before)

    def test_stuck_keeps_translation(self):
        self.assertIn('id="c1-x1"', self.stuck)
        self.assertIn('<div class="b trans"><div class="tag">译</div><div class="kai"><p>鼹鼠看呆了', self.stuck)
        self.assertIn('<div class="b alert"><div class="tag">卡点</div>', self.stuck)

    def test_reread(self):
        self.assertEqual(self.unit.count(self.b.REREAD), 1)
        self.assertIn(f'</article><p class="reread">{self.b.REREAD}</p><h2 class="sk">理解</h2>', self.post)

    def test_page_css(self):
        css = self.page.split("<style>")[1].split("</style>")[0]
        self.assertIn('@page c1-post{@top-left{content:"The Wind in the Willows · 第 1 章"}@top-right{content:"读后"}}', css)
        self.assertIn('@page c1-stuck{@top-left{content:"The Wind in the Willows · 第 1 章"}@top-right{content:"卡句"}}', css)

    def test_tight(self):
        unit = self.body_of(self.html(self.chapters, sect={1: {"post"}}, book=False), 1)
        self.assertIn('<section class="post tight" style="page:c1-post"', unit)
        self.assertIn('<section class="post stuck" style="page:c1-stuck"', unit)

    def test_keep_rows(self):
        self.b.V3_PDF[:] = [{"chunk_layout": "对排", "keep_rows": 5}]
        post = self.body_of(self.html(self.chapters, book=False), 1)
        cgs = re.findall(r'<div class="cg( keep)?">((?:<div class="cr .*?</div></div>)+)</div>', post)
        self.assertEqual([(bool(k), body.count('<div class="cr ')) for k, body in cgs][:4],
                         [(False, 7), (True, 5), (False, 6), (True, 5)])

    def test_below_layout(self):
        self.b.V3_PDF.clear()
        self.assertEqual(self.b.v3_pdf(), {"chunk_layout": "下置", "keep_rows": 16})     # rules.json 定的是下置（实排：对排折行 10/48 行）
        self.b.V3_PDF.clear()
        self.assertEqual({**self.b.V3_PDF_DEFAULT}, {"chunk_layout": "下置", "keep_rows": 16})     # rules.json 没写时的默认，和 rules.json 一致
        post = self.body_of(self.html(self.chapters, book=False), 1)
        self.assertNotIn('class="cz"', post)
        self.assertIn('<div class="cg below keep"><div class="cr d0"><span class="cn">①</span><div class="ce"><b class="core">It</b>', post)
        self.assertIn('<p class="gz"><span class="gn">①</span>难怪（这件事）——／<span class="gn">②</span>所以说，／', post)

    def test_bad_layout_value(self):
        rules = json.loads(self.b.RULES.read_text(encoding="utf-8"))
        rules["v3"]["pdf"]["chunk_layout"] = "上下"
        self.b.V3_PDF.clear()
        with mock.patch.object(self.b, "load_rules", return_value=rules):
            with self.assertRaises(SystemExit) as e:
                self.b.v3_pdf()
        self.assertIn("只能是 对排 / 下置", str(e.exception.code))

    def test_layout_reads_stuck_page_apart(self):
        # 卡句页的页眉是「卡句」，不算进读后的页数
        mark = self.b.page_key(self.b.PRE_MARK)
        post = re.sub(r"\s+", "", self.b.running_head(1) + "读后")
        stuck = re.sub(r"\s+", "", self.b.running_head(1) + "卡句")
        pages = [pg("封面"), pg("01第1章" + mark), pg("长难句", post), pg("…", post), pg("做完再看答案长难句·译", post, 0.5),
                 pg("卡句1", stuck), pg("…", stuck)]
        self.assertEqual(self.b.unit_layout(pages, self.chapters)[1], {"pre": 1, "post": 2, "total": 3, "own": True})
        self.assertEqual(self.b.post_cap(), 3)


class TestV3Intensive(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, V3J, "精读", "The River Bank")], default_mode="轻读", fmt=3)
        self.page = self.html(self.chapters, book=False)
        self.unit = self.body_of(self.page, 1)
        self.sent = self.unit.split('<section class="sec-sent" style="page:c1-sent">', 1)[1].split("</section>")[0]

    def test_blocks(self):
        self.assertEqual(self.sent.count('<article class="sent v3"'), 5)
        self.assertEqual(self.sent.count('<div class="cg below keep">'), 5)       # rules.json 定的下置
        self.assertNotIn('class="orig', self.unit)
        for q in tries(V3J):
            self.assertNotIn(q, self.sent + self.unit.split('id="c1-extra"', 1)[1].split("</section>")[0])
        self.assertIn('<b class="core">Something</b> up above <b class="core">was calling</b> him imperiously,', self.sent)

    def test_translation_and_extras_stay_in_block(self):
        s1 = self.sent.split('id="c1-s2"')[0]
        order = [s1.index(x) for x in ('class="cg', 'class="nts"', '<div class="tag">怎么拆</div>', '<div class="tag">卡点</div>',
                                       '<div class="tag">译</div>', '<div class="tag">句型</div>', '<div class="tag">举一反三</div>',
                                       '<div class="tag">赏析</div>')]
        self.assertEqual(order, sorted(order))
        self.assertIn('<ol class="steps"><li>', s1)
        self.assertTrue(self.sent.endswith(f'</article><p class="reread">{self.b.REREAD}</p>'))

    def test_tight_sentence(self):
        unit = self.body_of(self.html(self.chapters, tight={1: {2: 2}}, book=False), 1)
        self.assertIn('<article class="sent v3 tight tight2" id="c1-s2">', unit)

    def test_section_name(self):
        self.assertIn('<h2 class="sk">长难句</h2>', self.unit)                # 第三版的精读：栏名「长难句」，不是「精讲句」
        self.assertIn('@top-right{content:"长难句"}', self.page)
        self.assertNotIn("精讲句", self.unit)

    def test_stuck_section(self):
        extra = self.unit.split('id="c1-extra"', 1)[1].split("</section>")[0]
        self.assertIn('<h2 class="sk">卡句</h2>', extra)
        self.assertIn('<span class="tg tgm">没说</span>', extra)
        self.assertIn("鼹鼠看呆了", extra)                          # 卡句的译排在块里
        self.assertIn('<span class="mk">卡 1</span>', self.unit)     # 章首页的地图
        self.assertIn("赏析 · 写作 · 卡句 · 自测", self.unit)
        self.assertIn('@top-right{content:"卡句"}', self.page)
        self.assertNotIn(self.b.EXTRA, self.page.split("</style>")[1])


class TestV3Front(PdfBase):
    def setUp(self):
        super().setUp()
        self.chapters = self.project([(1, V3J, "精读", "The River Bank"), (2, retitle(V3L, 2), None, "The Open Road")],
                                     default_mode="轻读", preface=PREFACE_V3, fmt=3)
        self.page = self.html(self.chapters, pages=[4, 5, 6, 7, 40], book=True)
        self.howto = self.page.split('<section class="front howto v2">', 1)[1].split("</section>")[0]

    def test_howto(self):
        text = plain(self.howto)
        self.assertIn("第2章是轻读，读后依次是长难句、理解、词的用法、复述，答案在最后，精讲句的译也在那里。", text)
        self.assertIn(plain(self.b.REREAD), text)
        self.assertIn("卡句.txt", text)
        self.assertIn("难句本", text)
        self.assertIn("PDF不印试，先在难句本里自己拆。", text)
        self.assertIn("第1章是精读，讲解依次是章首页、长难句、词的用法", text)       # 第三版的精读栏名是长难句
        self.assertNotIn("深色加粗的词连起来就是主干", text)
        self.assertIn('<div class="cg below keep">', self.howto)       # 断句表的图例（下置）
        self.assertIn("下面是顺读，编号对应各块。", text)
        self.assertNotIn('class="abbr"', self.howto)                   # 缩写表挪到目录页末尾
        self.assertIn('<div class="src tabbr"><div class="fsub">缩写</div>', self.page.split('<nav class="front toc">')[1])
        self.assertIn("例句取自第1章句3", text)
        self.assertIn('<span class="tg">固定框架</span>', self.howto)

    def test_reread_once_when_preface_has_it(self):
        # 前言开头的出处说明照 写法.md 写了回读的话，「怎么用」页的说明就不再重复
        (self.root / "讲义" / "前言.md").write_text(PREFACE_V3.replace("。", "。" + self.b.REREAD, 1), encoding="utf-8")
        page = self.html(self.chapters, book=True)
        howto = plain(page.split('<section class="front howto v2">', 1)[1].split("</section>")[0])
        self.assertEqual(howto.count(plain(self.b.REREAD)), 1)

    def test_stuck_page_can_tighten(self):
        light = next(c for c in self.chapters if c["mode"] == "轻读")
        self.assertEqual(self.b.sec_labels(light), {"post": "读后", "stuck": "卡句"})

    def test_cover_and_toc(self):
        front = self.front_text(self.page)
        self.assertIn("卡句4句", front)
        toc = self.page.split('<nav class="front toc">')[1].split("</nav>")[0]
        self.assertIn("卡句 2 句", toc)
        self.assertIn("长难句 4 句 · 理解 2 题 · 词条", toc)           # 第三版轻读：长难句在理解前面
        self.assertIn("精读 · 长难句 5 句 · 词条", toc)                  # 第三版精读：精讲写成长难句
        self.assertNotIn("精讲", toc)
        self.assertIn("<b>句子结构</b>", toc)
        self.assertNotIn(self.b.EXTRA, self.page.split("</style>")[1])

    def test_tag_page(self):
        fp = self.page.split('<section class="front fpage tags" id="front3">', 1)[1].split("</section>")[0]
        self.assertTrue(fp.startswith('<h1 class="fh">句子结构</h1>'))
        self.assertIn('<table class="t3 gloss">', fp)
        self.assertIn("<td>it 占位</td>", fp)

    def test_css(self):
        css = self.page.split("<style>")[1].split("</style>")[0]
        self.assertIn(self.b.PDF_CSS_V3, css)
        self.assertIn(self.b.PDF_CSS_V2, css)


# ---------- 锚点：从读回的文字里找各单元的首页 ----------

def pg(text="", head="", fill=0.9):
    return {"head": head, "text": text, "fill": fill}


class TestAnchors(PdfBase):
    def heads(self, n, label):
        return re.sub(r"\s+", "", self.b.running_head(n) + label)

    def test_v1_style_uses_map(self):
        chapters = self.project([(1, INTENSIVE, None, ""), (2, retitle(INTENSIVE, 2), None, "")], preface=PREFACE)
        pages = [pg("封面"), pg("怎么用"), pg("目录"), pg("语法术语讲解"), pg("这本书和这一章的人物"),
                 pg("01第1章本章地图")] + [pg("x", self.heads(1, "精讲句"))] * 3 + [pg("02第2章本章地图")] + [pg("y")] * 2
        self.assertEqual(self.b.unit_pages(pages, chapters), {1: (6, 6), 2: (10, 10)})
        self.assertEqual(self.b.toc_pages(pages, chapters, ["语法术语", "这本书和这一章的人物"]), [4, 5, 6, 10])

    def test_mixed_units(self):
        chapters = self.project([(1, intensive_v2(1), "精读", ""), (2, retitle(LIGHT, 2), None, "")], default_mode="轻读")
        mark = self.b.page_key(self.b.PRE_MARK)
        post = self.heads(2, "读后")
        pages = ([pg("封面"), pg("怎么用"), pg("目录")]
                 + [pg("01第1章" + mark + "背景"), pg("01第1章本章地图")] + [pg("x", self.heads(1, "精讲句"))] * 2
                 + [pg("02第2章" + mark), pg("理解…本章地图", post), pg("…", post), pg("做完再看答案理解1", post, 0.5)])
        self.assertEqual(self.b.unit_pages(pages, chapters), {1: (4, 5), 2: (8, None)})
        self.assertEqual(self.b.toc_pages(pages, chapters, []), [4, 8])
        lay = self.b.unit_layout(pages, chapters)
        self.assertEqual(lay[1], {"pre": 1})
        self.assertEqual(lay[2], {"pre": 1, "post": 2, "total": 3, "own": True})
        stats = self.b.section_stats(pages, chapters)
        self.assertEqual(stats[(2, "pre")], (1, 0))
        self.assertEqual(stats[(2, "post")], (3, 0))
        self.assertEqual(stats[(1, "pre")], (1, 0))

    def test_answers_inline_and_overflow(self):
        chapters = self.project([(1, LIGHT, None, "")], default_mode="轻读")
        post = self.heads(1, "读后")
        mark = self.b.page_key(self.b.PRE_MARK)
        pages = [pg("封面"), pg(mark), pg(mark + "接上页的词"), pg("理解", post), pg("…", post), pg("复述做完再看答案", post, 0.2)]
        lay = self.b.unit_layout(pages, chapters)[1]
        self.assertEqual((lay["pre"], lay["post"], lay["total"], lay["own"]), (2, 3, 3, False))
        stats = self.b.section_stats(pages, chapters)
        self.assertEqual(stats[(1, "pre")], (2, 1))           # 读前两页：要排紧
        self.assertEqual(stats[(1, "post")], (3, 1))          # 读后三页没超上限（rules.json 的 light.pdf.post_pages = 3），只算最后一页只剩几行

    def test_missing_unit(self):
        chapters = self.project([(1, LIGHT, None, ""), (2, retitle(LIGHT, 2), None, "")], default_mode="轻读")
        pages = [pg("封面"), pg(self.b.page_key(self.b.PRE_MARK))]
        self.assertEqual(self.b.unit_pages(pages, chapters), {1: (2, None)})
        self.assertIsNone(self.b.toc_pages(pages, chapters, []))
        self.assertEqual(self.b.unit_pages(None, chapters), {})


# ---------- 找排版程序、启动 ----------

GUARD = """import runpy, subprocess, sys
def refuse(cmd, *a, **k):
    raise SystemExit("测试里不许启动外部程序：%r" % (cmd,))
subprocess.Popen = refuse
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""     # 跑 build.py 命令行，但一个外部程序也启动不了（万一代码有错也不会启动浏览器）


class TestChrome(PdfBase):
    """找排版程序的顺序：ER_CHROME → chrome-headless-shell → （ER_ALLOW_GUI_BROWSER=1 才）本机带界面的浏览器。
    摆出来的程序文件都是假的，subprocess.run 也换掉了：一个程序都不启动。"""

    def fake_shell(self, version="157.0.8103.78"):
        """在临时目录里摆一个“装好的” chrome-headless-shell（假的，不运行）。"""
        exe = self.renderer.ROOT / version / "chrome-headless-shell-mac-arm64" / "chrome-headless-shell"
        exe.parent.mkdir(parents=True)
        exe.write_text("#!/bin/sh\nexit 1\n")
        exe.chmod(0o755)
        return exe

    def gui_machine(self, apps=("Google Chrome.app/Contents/MacOS/Google Chrome",)):
        """假的家目录，~/Applications 里摆着带界面的浏览器（空文件）；临时目录以外的文件（真的 /Applications）一律当作没有，
        PATH 里也找不到。返回 (patch 列表, 摆的浏览器路径列表)。"""
        home = Path(self.tmp.name) / "home"
        made = []
        for app in apps:
            exe = home / "Applications" / app
            exe.parent.mkdir(parents=True)
            exe.write_text("")
            made.append(exe)
        tmp = self.tmp.name
        patches = [mock.patch.object(self.b.Path, "home", return_value=home),
                   mock.patch("pathlib.Path.is_file", lambda p: str(p).startswith(tmp) and os.path.isfile(p)),
                   mock.patch.object(self.b.shutil, "which", return_value=None)]
        for x in patches:
            x.start()
            self.addCleanup(x.stop)
        return made

    def find(self):
        """find_chrome()，顺带收下它打印的字：(结果或 SystemExit, 打印的字)。"""
        buf = StringIO()
        with redirect_stdout(buf):
            try:
                got = self.b.find_chrome()
            except SystemExit as e:
                got = e
        return got, buf.getvalue()

    # ER_CHROME

    def test_er_chrome_executable(self):
        os.environ["ER_CHROME"] = sys.executable
        self.assertEqual(self.b.find_chrome(), sys.executable)

    def test_er_chrome_app_bundle(self):
        exe = Path(self.tmp.name) / "Some Browser.app" / "Contents" / "MacOS" / "Some Browser"
        exe.parent.mkdir(parents=True)
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        os.environ["ER_CHROME"] = str(exe.parents[2])
        with mock.patch.object(self.b.sys, "platform", "darwin"):
            got, said = self.find()
        self.assertEqual(got, str(exe))
        self.assertIn(self.b.GUI_WARNING, said)                # 指的是带界面的浏览器：先说一声

    def test_er_chrome_wrong(self):
        os.environ["ER_CHROME"] = str(Path(self.tmp.name) / "nope")
        with self.assertRaises(SystemExit) as cm:
            self.b.find_chrome()
        self.assertIn("ER_CHROME", str(cm.exception.code))

    def test_er_chrome_beats_shell(self):
        self.fake_shell()
        os.environ["ER_CHROME"] = sys.executable
        self.assertEqual(self.find()[0], sys.executable)

    # chrome-headless-shell

    def test_shell_before_gui(self):
        shell = self.fake_shell()
        self.gui_machine()
        os.environ["ER_ALLOW_GUI_BROWSER"] = "1"               # 允许了也先用 chrome-headless-shell
        got, said = self.find()
        self.assertEqual(got, str(shell))
        self.assertIn("chrome-headless-shell 157.0.8103.78", said)
        self.assertNotIn(self.b.GUI_WARNING, said)

    def test_newest_shell_version(self):
        self.fake_shell("150.0.7000.1")
        new = self.fake_shell("157.0.8103.78")
        self.assertEqual(self.find()[0], str(new))

    def test_default_never_uses_gui(self):
        self.gui_machine()                                      # 本机有 Chrome，但没装 chrome-headless-shell
        for value in (None, "0", "yes", ""):
            if value is None:
                os.environ.pop("ER_ALLOW_GUI_BROWSER", None)
            else:
                os.environ["ER_ALLOW_GUI_BROWSER"] = value
            got, said = self.find()
            self.assertIsInstance(got, SystemExit, value)
            msg = str(got.code)
            for s in ("PDF 要用没有界面的排版程序 chrome-headless-shell，先运行一次：python3 ", str(RENDERER), " install",
                      f"约 {self.renderer.APPROX_MB} MB", "装在 ~/Library/Caches/english-reader/", "check、md 不受影响",
                      "ER_ALLOW_GUI_BROWSER=1"):
                self.assertIn(s, msg)
            self.assertNotIn(self.b.GUI_WARNING, said)

    def test_no_renderer_launches_nothing(self):
        self.gui_machine()
        out = Path(self.tmp.name) / "讲义.pdf"
        calls, run = self.fake_run()
        with mock.patch.object(self.b.subprocess, "run", run), mock.patch.object(self.b.sys, "platform", "darwin"):
            with self.assertRaises(SystemExit) as cm:
                self.b.chrome(f"--print-to-pdf={out}", "file:///book.html")
        self.assertIn("renderer.py", str(cm.exception.code))
        self.assertEqual(calls, [])                             # 什么都没启动
        self.assertEqual(self.b.CHROME, [])

    # 本机带界面的浏览器：只在 ER_ALLOW_GUI_BROWSER=1 时用

    def test_gui_only_when_allowed(self):
        app, = self.gui_machine()
        os.environ["ER_ALLOW_GUI_BROWSER"] = "1"
        got, said = self.find()
        self.assertEqual(got, str(app))
        self.assertEqual(said.strip().splitlines()[0], "用本机浏览器排版，可能会抢前台和键盘输入。")

    def test_gui_candidates_in_order(self):
        edge, = self.gui_machine(("Microsoft Edge.app/Contents/MacOS/Microsoft Edge",))
        os.environ["ER_ALLOW_GUI_BROWSER"] = "1"
        with mock.patch.object(self.b, "CHROME_APPS", ("Nope.app/Contents/MacOS/Nope",) + self.b.CHROME_APPS[2:]):
            self.assertEqual(self.find()[0], str(edge))

    def test_gui_allowed_but_none(self):
        self.gui_machine(())
        os.environ["ER_ALLOW_GUI_BROWSER"] = "1"
        got, said = self.find()
        self.assertIsInstance(got, SystemExit)
        msg = str(got.code)
        for s in ("Google Chrome", "Chromium", "Microsoft Edge", "Brave", "ER_CHROME", "renderer.py", "install"):
            self.assertIn(s, msg)

    # 启动

    def fake_run(self, write=True, code=0, stderr="", hang=False):
        """代替 subprocess.run：记下命令；write 时像浏览器一样写出 --print-to-pdf 指的文件；hang 时像卡住一样超时。"""
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            if cmd[0] == "pkill":
                return subprocess.CompletedProcess(cmd, 0, "", "")
            out = next((a.split("=", 1)[1] for a in cmd if a.startswith("--print-to-pdf=")), None)
            if write and out:
                Path(out).write_bytes(b"%PDF-1.4 fake")
            if hang:
                raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
            return subprocess.CompletedProcess(cmd, code, "", stderr)
        return calls, run

    def launch(self, exe, **kw):
        """用 exe 当排版程序打印一次（不真的启动）：返回 (启动命令列表, 目标文件, 配置目录)。"""
        out, profile = Path(self.tmp.name) / "out" / "讲义.pdf", Path(self.tmp.name) / "profile"
        out.parent.mkdir()
        out.write_bytes(b"OLD")
        calls, run = self.fake_run(**kw)
        self.b.CHROME[:] = [str(exe)]
        with mock.patch.object(self.b, "CHROME_PROFILE", profile), mock.patch.object(self.b.sys, "platform", "darwin"), \
                mock.patch.object(self.b.subprocess, "run", run):
            try:
                self.b.chrome("--no-pdf-header-footer", f"--print-to-pdf={out}", "file:///book.html")
            finally:
                self.calls = calls
        return calls, out, profile

    def test_app_bundle(self):
        app = Path("/Applications/Google Chrome.app")
        self.assertEqual(self.b.app_bundle(app / "Contents" / "MacOS" / "Google Chrome"), app)
        self.assertIsNone(self.b.app_bundle(Path(self.tmp.name) / "chrome-headless-shell"))
        self.assertIsNone(self.b.app_bundle("/chrome"))

    def test_app_launched_in_background(self):
        # macOS 上 .app 里的浏览器经 open 后台启动：不带到前台、隐藏、新实例、等它退出；专用配置目录
        app = Path(self.tmp.name) / "Some Browser.app"
        calls, out, profile = self.launch(app / "Contents" / "MacOS" / "Some Browser")
        self.assertEqual(len(calls), 1)
        cmd = calls[0]
        self.assertEqual(cmd[:5], ["open", "-g", "-j", "-n", "-W"])
        self.assertEqual(cmd[cmd.index("-a") + 1], str(app.resolve()))
        rest = cmd[cmd.index("--args") + 1:]
        self.assertEqual(rest[0], f"--user-data-dir={profile}")
        self.assertIn("--headless=new", rest)
        self.assertIn("file:///book.html", rest)
        self.assertTrue(profile.is_dir())                        # 第一次用到时建好
        self.assertEqual(out.read_bytes(), b"%PDF-1.4 fake")      # 临时文件换成了目标文件
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["讲义.pdf"])

    def test_app_no_output_is_error(self):
        app = Path(self.tmp.name) / "Some Browser.app"
        with self.assertRaises(SystemExit) as cm:
            self.launch(app / "Contents" / "MacOS" / "Some Browser", write=False)
        self.assertIn("浏览器没有生成 PDF", str(cm.exception.code))
        out = Path(self.tmp.name) / "out" / "讲义.pdf"
        self.assertEqual(out.read_bytes(), b"OLD")                # 原来的文件不动

    def test_shell_runs_directly(self):
        # chrome-headless-shell 没有界面：直接运行，不经 open；不要 --headless=new；专用配置目录；不读钥匙串
        exe = Path(self.tmp.name) / "157.0.8103.78" / "chrome-headless-shell-mac-arm64" / "chrome-headless-shell"
        calls, out, profile = self.launch(exe)
        self.assertEqual(len(calls), 1)
        cmd = calls[0]
        self.assertEqual(cmd[0], str(exe))
        self.assertNotIn("open", cmd)
        self.assertEqual(cmd[1], f"--user-data-dir={profile}")
        self.assertFalse([a for a in cmd if a.startswith("--headless")], cmd)
        for flag in ("--disable-gpu", "--allow-file-access-from-files", "--no-first-run", "--hide-scrollbars",
                     "--use-mock-keychain", "--disable-cookie-encryption", "--no-pdf-header-footer"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[-1], "file:///book.html")
        target = next(a.split("=", 1)[1] for a in cmd if a.startswith("--print-to-pdf="))
        self.assertNotEqual(Path(target), out.resolve())          # 先打印到同目录的临时文件
        self.assertEqual(Path(target).parent, out.parent.resolve())
        self.assertTrue(profile.is_dir())
        self.assertEqual(out.read_bytes(), b"%PDF-1.4 fake")
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["讲义.pdf"])

    def test_shell_error_keeps_old_file(self):
        exe = Path(self.tmp.name) / "chrome-headless-shell"
        with self.assertRaises(SystemExit) as cm:
            self.launch(exe, code=1, stderr="Teardown watchdog expired")     # 写了文件但退出码不是 0：不算
        msg = str(cm.exception.code)
        for s in ("排版程序没有生成 PDF", "退出码 1", "Teardown watchdog expired", str(exe)):
            self.assertIn(s, msg)
        out = Path(self.tmp.name) / "out" / "讲义.pdf"
        self.assertEqual(out.read_bytes(), b"OLD")
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["讲义.pdf"])      # 临时文件删了

    def test_shell_timeout(self):
        exe = Path(self.tmp.name) / "chrome-headless-shell"
        with self.assertRaises(SystemExit) as cm:
            self.launch(exe, hang=True)
        self.assertIn("120 秒", str(cm.exception.code))
        profile = Path(self.tmp.name) / "profile"
        self.assertEqual(self.calls[-1], ["pkill", "-f", f"user-data-dir={profile}"])
        out = Path(self.tmp.name) / "out" / "讲义.pdf"
        self.assertEqual(out.read_bytes(), b"OLD")
        self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["讲义.pdf"])

    def test_other_bare_executable_keeps_flags(self):
        # ER_CHROME 指的别的命令行程序（不是 chrome-headless-shell）：照旧用 CHROME_FLAGS，也用专用配置目录
        exe = Path(self.tmp.name) / "chromium"
        calls, out, profile = self.launch(exe)
        self.assertEqual(calls[0][:2], [str(exe), f"--user-data-dir={profile}"])
        self.assertIn("--headless=new", calls[0])
        self.assertNotIn("--use-mock-keychain", calls[0])

    # 命令行

    def test_cli_light_project_no_longer_refused(self):
        self.project([(1, INTENSIVE, "精读", ""), (2, retitle(LIGHT, 2), "轻读", "")])
        env = {**os.environ, "ER_CHROME": str(Path(self.tmp.name) / "nope")}
        r = subprocess.run([sys.executable, str(BUILD), "pdf", str(self.root)], capture_output=True, text=True, env=env)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ER_CHROME", out)
        self.assertNotIn("还没做", out)
        self.assertNotIn("Traceback", out)

    def test_cli_without_renderer_says_install(self):
        # 家目录换成空的临时目录（没装 chrome-headless-shell），不设 ER_CHROME、ER_ALLOW_GUI_BROWSER：
        # 本机的 Chrome 不用，在排版之前说明怎么装；外部程序一律不许启动
        self.project([(1, LIGHT, "轻读", "")])
        home = Path(self.tmp.name) / "empty-home"
        home.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("ER_CHROME", "ER_ALLOW_GUI_BROWSER")}
        env["HOME"] = str(home)
        r = subprocess.run([sys.executable, "-c", GUARD, str(BUILD), "pdf", str(self.root)],
                           capture_output=True, text=True, env=env)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PDF 要用没有界面的排版程序 chrome-headless-shell", out)
        self.assertIn(f"{RENDERER} install", out.replace("'", ""))
        self.assertNotIn("不许启动外部程序", out)
        self.assertNotIn("主干高亮", out)                         # 在排版之前就停下
        self.assertNotIn("Traceback", out)
        self.assertFalse((self.root / "成品" / "讲义.pdf").exists())


# ---------- 真的出一份 PDF（本机没有浏览器或 swift 就跳过） ----------

def outline_titles(pdf):
    """PDF 书签和文档信息里的 /Title（Chrome 写的这些字典没有压缩）：中文是带 FEFF 的 UTF-16BE 十六进制串。"""
    out = []
    for m in re.finditer(rb"/Title\s*(?:<([0-9A-Fa-f]+)>|\(((?:\\.|[^\\)])*)\))", Path(pdf).read_bytes()):
        raw = bytes.fromhex(m.group(1).decode()) if m.group(1) else m.group(2)
        out.append(raw[2:].decode("utf-16-be") if raw.startswith(b"\xfe\xff") else raw.decode("latin-1"))
    return out


def have_tools():
    """renderer.py 装好了 chrome-headless-shell，还有 pdftotext 或 swift。只看 chrome-headless-shell，不找带界面的浏览器。"""
    b = load_build()
    if not b.sibling("renderer").installed():
        return False
    return bool(shutil.which("pdftotext") or shutil.which("swiftc") or Path("/usr/bin/swiftc").exists())


@unittest.skipUnless(os.environ.get("ER_PDF_TEST") == "1" and sys.platform == "darwin" and have_tools(),
                     "真出 PDF 会运行 chrome-headless-shell：设 ER_PDF_TEST=1 才跑"
                     "（还要 macOS、renderer.py install 装好的 chrome-headless-shell 和 swift）")
class TestRealPdf(PdfBase):
    """只用 chrome-headless-shell：PdfBase 去掉了 ER_CHROME、ER_ALLOW_GUI_BROWSER，build.py 找不到它就不排。"""

    def test_mixed_book(self):
        chapters = self.project([(1, INTENSIVE, "精读", "The River Bank"), (2, retitle(LIGHT, 2), "轻读", "The Open Road")],
                                default_mode="轻读", preface=PREFACE)
        r = subprocess.run([sys.executable, str(BUILD), "pdf", str(self.root)], capture_output=True, text=True)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertIn("排版程序：chrome-headless-shell", out)
        self.assertNotIn("用本机浏览器排版", out)
        self.assertIn("第 2 章（轻读）：读前 1 页", out)
        pages = self.b.pdf_words(self.root / "成品" / "讲义.pdf")
        up = self.b.unit_pages(pages, chapters)
        self.assertEqual(sorted(up), [1, 2])
        toc = next(p["text"] for p in pages if p["text"].startswith("目录"))
        for n in (1, 2):
            self.assertIn(f"第{n}章", toc)
            self.assertIn(str(up[n][0]), toc)
        first, after = pages[up[2][0] - 1], pages[up[2][0]]       # 轻读单元的第一页是读前，只有读前；下一页起是读后
        q1 = self.b.page_key(self.chs[2]["comprehension"]["questions"][0])[:12]
        self.assertIn(self.b.page_key(self.b.PRE_MARK), first["text"])
        self.assertNotIn(q1, first["text"])
        self.assertEqual(first["head"], "")
        self.assertTrue(after["head"].endswith("读后"))
        self.assertIn(q1, after["text"])
        titles = outline_titles(self.root / "成品" / "讲义.pdf")       # 第一版的精读单元（没有读前）：书签是章首页那一个
        self.assertEqual([t for t in titles if t.startswith("第 ")], ["第 1 章", "第 2 章 The Open Road"], titles)

    def test_bookmarks_one_per_unit(self):
        # 有读前的精读单元：书签只有读前页那一个（以前章首页另有一个「第 1 章」）
        self.project([(1, intensive_v2(1), "精读", "The River Bank"), (2, retitle(LIGHT, 2), "轻读", "The Open Road")],
                     default_mode="轻读")
        r = subprocess.run([sys.executable, str(BUILD), "pdf", str(self.root)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        titles = outline_titles(self.root / "成品" / "讲义.pdf")
        self.assertEqual([t for t in titles if t.startswith("第 ")], ["第 1 章 The River Bank", "第 2 章 The Open Road"], titles)
        self.assertIn("精讲句", titles)


if __name__ == "__main__":
    unittest.main()
