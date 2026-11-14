"""notebook.py：难句本（build.py sentences）、单词本（words）、卡句定位（stuck）和 check 的卡句提示。
在 skill 根目录运行：python3 -m unittest discover -s tests

夹具（fixtures/）：
  v3_精读.md、v3_轻读.md   第三版的两个单元（test_build_v3 的夹具），引文都出自 原文.txt
  卡句.txt                 依次是命中、多处、近似、找不到、太短、直引号各一行（第 7–12 行），放在第 1 章
测的是：分组顺序和 结构标签.tsv 一致、每句只出现一次、另见行；tsv 13 列、没有制表符和换行、
重新编号后 id 不变；--anki 的文件头；单词本.tsv 11 列、读前词都找到原句；stuck 的六种结果；check 的卡句提示。
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
SKILL = HERE.parent
BUILD = SKILL / "scripts" / "build.py"
SOURCE = (FIX / "原文.txt").read_text(encoding="utf-8")
V3L = (FIX / "v3_轻读.md").read_text(encoding="utf-8")
V3J = (FIX / "v3_精读.md").read_text(encoding="utf-8")
STUCK = (FIX / "卡句.txt").read_text(encoding="utf-8")
TITLE = "The Wind in the Willows"
TAG_ORDER = [l.split("\t")[0] for l in (SKILL / "reference" / "结构标签.tsv").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")][1:]
SB_HEAD = ("#separator:tab\n#html:false\n#columns:id\t原句\t注\t试\t答\t主干\t断句\t顺读\t卡点\t译\t结构\t出处\t类型\n"
           "#guid column:1\n#tags column:11\n")
WB_HEAD = ("#separator:tab\n#html:false\n#columns:id\t词\t音标\t词性\t释义\t原句\t原句译\t章\t类型\t掌握\t级别\n"
           "#guid column:1\n")
LEVEL = re.compile(r"(?:(?:A1|A2|B1|B2|C1|C2)(?:，估)?|未定级)?")


def load_build():
    spec = importlib.util.spec_from_file_location("er_build_notebook", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load_build()


def make_project(root, units, fmt=3, slug="willows", default_mode="轻读", stuck=None, source=SOURCE):
    """units：[(单元号, 讲义, mode 或 None)]。fmt=None 时不写 format（第一、二版）；default_mode=None 是第一版。"""
    if root.exists():
        shutil.rmtree(root)
    (root / "原文").mkdir(parents=True)
    (root / "讲义").mkdir(parents=True)
    cfg = {"title": TITLE, "author": "Kenneth Grahame", "unit": "章", "units": [], "level": "B1", "genre": "小说"}
    if fmt is not None:
        cfg["format"] = fmt
    if slug:
        cfg["slug"] = slug
    if default_mode is not None:
        cfg["default_mode"] = default_mode
    for n, text, mode in units:
        cfg["units"].append({"n": n, "title": "The River Bank", **({"mode": mode} if mode else {})})
        (root / "原文" / f"第{n:02d}章.txt").write_text(source, encoding="utf-8")
        (root / "讲义" / f"第{n:02d}章.md").write_text(text, encoding="utf-8")
    (root / "设置.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    if stuck is not None:
        (root / "卡句.txt").write_text(stuck, encoding="utf-8")
    return root


def run(cmd, root, *args):
    r = subprocess.run([sys.executable, str(BUILD), cmd, str(root), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def sub(text, old, new, count=1):
    assert old in text, f"夹具里找不到：{old[:40]}"
    return text.replace(old, new, count)


def block(text, head):
    m = re.search(rf"^### {re.escape(head)}.*?(?=^### |^## |\Z)", text, flags=re.M | re.S)
    assert m, f"没有「### {head}」"
    return m.group(0)


def in_block(text, head, old, new):
    b = block(text, head)
    return text.replace(b, sub(b, old, new), 1)


def groups(part):
    """难句本一半里的各组：{组名: 那一组的文字}，按出现顺序。"""
    out = {}
    for m in re.finditer(r"^### (.+?)(?:（[^）]*）)?\n(.*?)(?=^### |\Z)", part, flags=re.M | re.S):
        out[m.group(1)] = m.group(2)
    return out


def tsv_rows(text):
    return [l.split("\t") for l in text.splitlines() if not l.startswith("#")]


def sha_id(quote, slug="willows"):
    return f"{slug}-" + hashlib.sha1(" ".join(B.stuck_words(quote)).encode("utf-8")).hexdigest()[:8]


def quote_of(text, head):
    return re.search(r"^> (.+)$", block(text, head), flags=re.M).group(1)


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


# ---------- 难句本 ----------

class TestSentences(unittest.TestCase):
    """第 1 章是精读夹具，第 2 章是轻读夹具（两章的原文都是 原文.txt）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(Path(cls.tmp.name) / "项目", [(1, V3J, "精读"), (2, V3L, None)])
        cls.code, cls.out = run("sentences", cls.root, "--anki")
        cls.md = (cls.root / "成品" / "复习" / "难句本.md").read_text(encoding="utf-8")
        cls.tsv = (cls.root / "成品" / "导入" / "难句本.tsv").read_text(encoding="utf-8")
        cls.anki = (cls.root / "成品" / "导入" / "难句本-anki.tsv").read_text(encoding="utf-8")
        cls.q, _, cls.a = cls.md.partition("\n## 二、对照\n")
        cls.rows = {r[11].replace(TITLE + " ", ""): r for r in tsv_rows(cls.tsv)}     # 出处（去掉书名）→ 行

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runs(self):
        self.assertEqual(self.code, 0, self.out)
        self.assertIn("难句本 11 句，8 组，另见 5 处；标签是词汇的卡句 2 句不收", self.out)
        self.assertIn("! 原句和前面的句子相同：2-3", self.out)       # 两章用同一份原文，「He was bowled over」讲了两次

    def test_head(self):
        self.assertTrue(self.md.startswith(f"# 难句本：{TITLE}（第 1–2 章）\n\n先看「一、自己拆」：读原句，答下面的问题。"
                                           "再翻到「二、对照」。编号开头是章号，没读到的章先跳过。拆完的句子，按正常速度再读两三遍。\n\n## 一、自己拆\n"))

    def test_group_order(self):
        heads = list(groups(self.q))
        self.assertEqual(heads, ["主谓隔开", "it 占位", "后置修饰", "多层从句", "非谓语", "独立结构", "并列", "固定框架", "指代"])
        self.assertEqual(heads, [t for t in TAG_ORDER if t in heads])
        self.assertEqual(list(groups(self.a)), [h for h in heads if h != "并列"])     # 只有另见的组，对照里不出
        self.assertIn("### 多层从句（3 句）\n\n从句里还有从句。读法：一个引导词开一层，先把最外面一层读完。\n", self.q)
        self.assertIn("### 并列（另见 3 句）\n\n另见：", self.q)          # 只有另见的组：不印定义和读法
        self.assertNotIn("几个谓语或几个分句并排", self.q)

    def test_each_sentence_once(self):
        want = ["1-1", "1-2", "1-3", "1-4", "1-5", "1-卡2", "2-1", "2-2", "2-3", "2-4", "2-卡2"]
        labels = re.findall(r"〔(.+?)〕", self.q)
        self.assertEqual(sorted(labels), sorted(want))
        self.assertEqual(len(labels), len(set(labels)))
        answers = re.findall(r'^#### <a id="a-[^"]+"></a>(\S+)　', self.a, flags=re.M)
        self.assertEqual(sorted(answers), sorted(want))
        self.assertNotIn("bewitched", self.md)            # 标签是词汇的卡句（两章的卡句 1）不收
        self.assertEqual(len(self.rows), 11)

    def test_see_also(self):
        g = groups(self.q)
        self.assertEqual(g["并列"].strip().splitlines()[-1], "另见：[1-1](#q-1-1)、[1-5](#q-1-5)、[2-1](#q-2-1)")
        self.assertEqual(g["it 占位"].strip().splitlines()[-1], "另见：[2-4](#q-2-4)")
        self.assertEqual(g["指代"].strip().splitlines()[-1], "另见：[2-3](#q-2-3)")
        self.assertEqual(self.q.count("另见："), 3)
        self.assertNotIn("另见", self.a)

    def test_order_in_group(self):
        g = groups(self.q)
        self.assertEqual(re.findall(r"〔(.+?)〕", g["多层从句"]), ["1-2", "1-4", "2-3"])
        self.assertEqual(re.findall(r"〔(.+?)〕", g["指代"]), ["1-卡2", "2-4"])

    def test_anchors(self):
        q_ids = re.findall(r'<a id="q-([^"]+)"></a>', self.q)
        a_ids = re.findall(r'<a id="a-([^"]+)"></a>', self.a)
        self.assertEqual(sorted(q_ids), sorted(a_ids))
        self.assertEqual(sorted(re.findall(r"\[对照\]\(#a-([^)]+)\)", self.q)), sorted(a_ids))
        self.assertEqual(sorted(re.findall(r"\[回到题面\]\(#q-([^)]+)\)", self.a)), sorted(q_ids))
        self.assertIn("2-k2", q_ids)                    # 卡句的锚点用 k，显示的编号用「卡」

    def test_question_side(self):
        """题面只有原句、注、试；几行之间用行尾的反斜杠硬换行。"""
        self.assertNotIn("| 断句 | 顺读 |", self.q)
        self.assertNotIn("卡点", self.q)
        quote = quote_of(V3J, "1. 定语一层套一层")
        self.assertIn(f'1. <a id="q-1-1"></a>{quote}\\\n   注：imperiously 不容分说地\\\n'
                      "   试：whose 引出的从句修饰哪个词？　[对照](#a-1-1)　〔1-1〕\n", self.q)
        self.assertIn("   试：真正的主语从哪个词开始？　[对照](#a-2-1)　〔2-1〕\n", self.q)

    def test_answer_side(self):
        a11 = self.a.split('<a id="a-1-1"></a>')[1].split("####")[0]
        self.assertTrue(a11.startswith("1-1　定语一层套一层：which、owned by、whose\n\n- **结构**：后置修饰、并列\n"))
        self.assertIn("| · · whose residences are nearer to the sun and air. | 它们的住处离阳光和空气更近。 |\n", a11)
        self.assertIn("- **答**：animals\n- **怎么拆**：\n  1. `in his case` 是插进来的", a11)
        self.assertIn("- **卡点**：`answered to` 不是“回答”。", a11)
        for label in ("句型", "延伸", "赏析"):                 # 留在讲义里
            self.assertNotIn(f"- **{label}**", a11)
        a22 = self.a.split('<a id="a-2-2"></a>')[1].split("####")[0]
        self.assertIn("- **答**：he\n", a22)
        self.assertNotIn("卡点", a22)
        self.assertNotIn("**译**", a22)
        self.assertIn("- **标记**：词都认识\n", self.a.split('<a id="a-2-k2"></a>')[1].split("####")[0])

    def test_tsv_shape(self):
        self.assertTrue(self.tsv.endswith("\n"))
        self.assertNotIn("\r", self.tsv)
        lines = self.tsv.splitlines()
        self.assertEqual(len(lines), 11)
        self.assertFalse(any(l.startswith("#") for l in lines))          # 默认没有表头
        for l in lines:
            self.assertEqual(len(l.split("\t")), 13, l)
            self.assertNotIn("  ", l)

    def test_tsv_ids(self):
        ids = [r[0] for r in tsv_rows(self.tsv)]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^willows-[0-9a-f]{8}(-\d+)?$")
        self.assertEqual(self.rows["第 2 章 句 1"][0], sha_id(quote_of(V3L, "1. small wonder")))
        same = sha_id(quote_of(V3J, "2. 被动句的 by"))
        self.assertEqual((self.rows["第 1 章 句 2"][0], self.rows["第 2 章 句 3"][0]), (same, same + "-2"))

    def test_tsv_rows(self):
        r = self.rows["第 2 章 句 1"]
        self.assertEqual(r[1], quote_of(V3L, "1. small wonder"))
        self.assertEqual(r[2:6], ["bolt 猛冲", "真正的主语从哪个词开始？", "that", "It was"])
        self.assertTrue(r[6].startswith("It was small wonder, / then, / that he suddenly flung down"))
        self.assertTrue(r[7].startswith("难怪（这件事）——／所以说，／"))
        self.assertEqual(r[8], "small wonder 不是“小小的奇迹”，是“难怪，不足为奇”。")     # 反引号去掉
        self.assertTrue(r[9].startswith("所以难怪他突然"))
        self.assertEqual(r[10:], ["it占位 并列", f"{TITLE} 第 2 章 句 1", "精讲"])
        self.assertEqual(self.rows["第 1 章 句 1"][5], "Something … was calling … he made for")
        self.assertEqual(self.rows["第 1 章 句 5"][5],
                         "Green turf sloped down … brown snaky tree-roots gleamed … shoulder … tumble … filled")
        drill = self.rows["第 2 章 句 2"]
        self.assertEqual((drill[8], drill[9], drill[12]), ("", "", "练习"))
        self.assertEqual(self.rows["第 2 章 卡句 2"][12], "卡句·词都认识")
        self.assertEqual(self.rows["第 1 章 卡句 2"][12], "卡句·没说")
        self.assertNotIn("**", self.tsv)
        self.assertNotIn("· ", self.tsv)

    def test_anki(self):
        self.assertTrue(self.anki.startswith(SB_HEAD))
        self.assertEqual(self.anki[len(SB_HEAD):], self.tsv)


class TestSentenceVariants(Temp):
    def test_trunk_apostrophe(self):
        """主干：两处粗体之间只隔着撇号时原样连上；隔着空白用空格连；隔着别的字用 … 连。"""
        nb = load_build().sibling("notebook")
        self.assertEqual(nb.trunk([{"md": "**you**’**ll have to go** straight"}]), "you’ll have to go")
        self.assertEqual(nb.trunk([{"md": "**you**'**ll go**"}]), "you'll go")
        self.assertEqual(nb.trunk([{"md": "**It** **was** small, **he** **said**"}]), "It was … he said")

    def test_order_by_position(self):
        """组内按原文位置：第 1 章卡句 2（But it could hardly be a star）在原文里比句 5（Green turf）靠前。"""
        text = in_block(V3J, "2. 两个 it", "- **结构**：指代", "- **结构**：主谓隔开")
        root = make_project(self.dir / "p", [(1, text, "精读")])
        self.assertEqual(run("sentences", root)[0], 0)
        q = (root / "成品" / "复习" / "难句本.md").read_text(encoding="utf-8").split("## 二、对照")[0]
        self.assertEqual(re.findall(r"〔(.+?)〕", groups(q)["主谓隔开"]), ["1-卡2", "1-5"])

    def test_numeric_hash_not_duplicate(self):
        """8 位哈希全是数字（willows-64721759）不算加过后缀；真的同一个原句讲了两次才报。"""
        root = make_project(self.dir / "n", [(1, V3L, None)])
        b = load_build()
        b.load_project(root)
        nb = b.sibling("notebook")
        ids = iter(range(64721759, 64721800))
        with mock.patch.object(nb, "sentence_id", side_effect=lambda build, q: f"willows-{next(ids)}"):
            book = nb.sentence_book(b)
        self.assertTrue(all(re.fullmatch(r"willows-\d{8}", e["id"]) for e in book["entries"]))
        self.assertFalse([w for w in book["warnings"] if "原句和前面的句子相同" in w])
        with mock.patch.object(nb, "sentence_id", return_value="willows-64721759"):
            book = nb.sentence_book(b)
        self.assertEqual(book["entries"][1]["id"], "willows-64721759-2")
        self.assertTrue([w for w in book["warnings"] if "原句和前面的句子相同" in w])

    def test_id_stable_after_renumber(self):
        """去掉轻读的句 2、后面的句子往前编号，再挪到第 3 章：同一个原句的 id 不变。"""
        root = make_project(self.dir / "a", [(2, V3L, None)])
        run("sentences", root)
        before = {r[1]: r[0] for r in tsv_rows((root / "成品" / "导入" / "难句本.tsv").read_text(encoding="utf-8"))}
        text = V3L.replace(block(V3L, "2. 句首的分词"), "")
        text = sub(sub(text, "### 3. who", "### 2. who"), "### 4. allude", "### 3. allude")
        root = make_project(self.dir / "b", [(3, text, None)])
        self.assertEqual(run("sentences", root)[0], 0)
        after = {r[1]: r[0] for r in tsv_rows((root / "成品" / "导入" / "难句本.tsv").read_text(encoding="utf-8"))}
        self.assertEqual(len(after), len(before) - 1)
        for quote, i in after.items():
            self.assertEqual(i, before[quote])
        self.assertIn(f"{TITLE} 第 3 章 句 3", (root / "成品" / "导入" / "难句本.tsv").read_text(encoding="utf-8"))

    def test_unknown_tag(self):
        text = in_block(V3L, "2. 句首的分词", "- **结构**：非谓语", "- **结构**：分词")
        root = make_project(self.dir / "p", [(1, text, None)])
        code, out = run("sentences", root)
        self.assertEqual(code, 0, out)
        self.assertIn("主标签不在 结构标签.tsv 里（或没写）：1-2", out)
        q = (root / "成品" / "复习" / "难句本.md").read_text(encoding="utf-8").split("## 二、对照")[0]
        self.assertEqual(list(groups(q))[-1], "标签不认识")
        self.assertEqual(re.findall(r"〔(.+?)〕", groups(q)["标签不认识"]), ["1-2"])

    def test_pdf_without_renderer_and_stale_anki(self):
        # 排版程序指到一个不存在的文件：先出 md、tsv，排 PDF 时说明排版程序不对、退出，不启动任何程序
        root = make_project(self.dir / "p", [(1, V3L, None)])
        run("sentences", root, "--anki")
        env = {**os.environ, "ER_CHROME": str(self.dir / "没有这个程序")}
        env.pop("ER_ALLOW_GUI_BROWSER", None)
        r = subprocess.run([sys.executable, str(BUILD), "sentences", str(root), "--pdf"], capture_output=True, text=True, env=env)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("环境变量 ER_CHROME 指的", out)
        self.assertIn("难句本-anki.tsv 是以前加 --anki 生成的，这次没有更新", out)
        self.assertTrue((root / "成品" / "复习" / "难句本.md").exists())
        self.assertFalse((root / "成品" / "复习" / "难句本.pdf").exists())

    def test_out_dir_and_bad_args(self):
        root = make_project(self.dir / "p", [(1, V3L, None)])
        code, out = run("sentences", root, "--out", str(self.dir / "导出"))
        self.assertEqual(code, 0, out)
        self.assertTrue((self.dir / "导出" / "导入" / "难句本.tsv").exists())
        self.assertFalse((root / "成品" / "导入" / "难句本.tsv").exists())
        code, out = run("sentences", root, "--json")
        self.assertNotEqual(code, 0)
        self.assertIn("sentences 不认识的参数：--json", out)

    def test_old_format_refused(self):
        root = make_project(self.dir / "p", [(1, (FIX / "轻读.md").read_text(encoding="utf-8"), None)], fmt=None,
                            stuck="第 1 章\nThe Mole was bewitched, entranced, fascinated.\n")
        for cmd, what in (("sentences", "难句本要第三版"), ("stuck", "卡句定位要第三版")):
            code, out = run(cmd, root)
            self.assertEqual(code, 1, out)
            self.assertIn("这个项目是第一、二版的格式（设置.json 里没有 \"format\": 3）", out)
            self.assertIn(what, out)
        self.assertFalse((root / "成品" / "复习" / "难句本.md").exists())


# ---------- 单词本 ----------

class TestWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = make_project(Path(cls.tmp.name) / "项目", [(1, V3J, "精读"), (2, V3L, None)])
        cls.code, cls.out = run("words", cls.root, "--anki")
        cls.tsv = (cls.root / "成品" / "导入" / "单词本.tsv").read_text(encoding="utf-8")
        cls.md = (cls.root / "成品" / "复习" / "单词本.md").read_text(encoding="utf-8")
        cls.anki = (cls.root / "成品" / "导入" / "单词本-anki.tsv").read_text(encoding="utf-8")
        cls.rows = tsv_rows(cls.tsv)
        cls.by_id = {r[0]: r for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shape(self):
        self.assertEqual(self.code, 0, self.out)
        self.assertNotIn("没找到", self.out)              # 读前词都找到了原句，词条的原文都找到了
        self.assertIn("单词本 30 条：读前 6，词条 12，注 12", self.out)
        self.assertTrue(self.tsv.endswith("\n"))
        self.assertNotIn("\r", self.tsv)
        for r in self.rows:
            self.assertEqual(len(r), 11, r)
            self.assertRegex(r[10], f"^{LEVEL.pattern}$")
        self.assertEqual(len(self.by_id), len(self.rows))

    def test_preread(self):
        forms = {"scull": "sculled", "bank": "bank", "fellow": "fellows", "trot": "trotted",
                 "luncheon-basket": "luncheon-basket", "row": "row"}
        pre = [r for r in self.rows if r[8] == "读前"]
        self.assertEqual([r[1] for r in pre], list(forms))
        flat = re.sub(r"\s+", " ", SOURCE)
        for r in pre:
            self.assertIn(forms[r[1]], r[5], r)
            self.assertIn(r[5], flat)                     # 原文里的一整句
            self.assertEqual((r[6], r[7], r[9]), ("", "2", ""))
        self.assertNotEqual(self.by_id["willows-c02-bank"][5], "The River Bank")      # 标题行不算
        self.assertEqual(self.by_id["willows-c02-scull"][1:5], ["scull", "/skʌl/", "v.", "用短桨划船"])

    def test_usage(self):
        r = self.by_id["willows-c02-make_for"]
        self.assertEqual(r[1:5], ["make for", "", "", "朝……走去"])          # 短语没有音标和词性
        self.assertTrue(r[5].startswith("Something up above was calling him imperiously, and he made for"))
        self.assertTrue(r[5].endswith("nearer to the sun and air."))
        self.assertEqual(r[6:10], ["他朝那条又陡又小的隧道奔去", "2", "词条", "会用"])
        r = self.by_id["willows-c01-mean"]
        self.assertEqual(r[2:5], ["/miːn/", "adj.", "①（英式）小气的，吝啬的 ②刻薄的，不友好的"])
        self.assertIn("I’m a mean beast and cut it very fine!", r[5])
        self.assertEqual(self.by_id["willows-c01-forbear"][3:5], ["v.", "（正式）克制，忍住（不做）"])
        self.assertEqual(self.by_id["willows-c01-forbear"][9], "认得")

    def test_notes(self):
        r = self.by_id["willows-c02-bolt"]
        self.assertEqual(r[1:5], ["bolt", "", "", "猛冲"])
        self.assertEqual(r[5], quote_of(V3L, "1. small wonder"))
        self.assertEqual(r[6:10], ["", "2", "注", ""])
        self.assertIn("willows-c02-allude_to", self.by_id)
        self.assertIn("willows-c01-be_prepared_to_do", self.by_id)
        self.assertEqual(self.by_id["willows-c01-bewitch"][5], "The Mole was bewitched, entranced, fascinated.")

    def test_md(self):
        self.assertTrue(self.md.startswith(f"# 单词本：{TITLE}（第 1–2 章）\n"))
        self.assertIn("## 第 1 章　The River Bank\n\n| 词 | 音标 | 词性 | 释义 | 类型 | 掌握 | 原句 |\n", self.md)
        self.assertEqual(self.md.count("\n| ") - 2 * 2, len(self.rows))       # 每节一行表头、一行分隔

    def test_anki(self):
        self.assertTrue(self.anki.startswith(WB_HEAD))
        self.assertEqual(self.anki[len(WB_HEAD):], self.tsv)


class TestWordsOldFormats(Temp):
    def test_first_version(self):
        """第一版（没有 default_mode、没有读前）：只有词条。"""
        root = make_project(self.dir / "p", [(1, (FIX / "精读.md").read_text(encoding="utf-8"), None)],
                            fmt=None, default_mode=None, slug=None)
        code, out = run("words", root)
        self.assertEqual(code, 0, out)
        rows = tsv_rows((root / "成品" / "导入" / "单词本.tsv").read_text(encoding="utf-8"))
        self.assertTrue(rows)
        self.assertEqual({r[8] for r in rows}, {"词条"})
        self.assertTrue(all(r[0].startswith("the-wind-in-the-willows-c01-") for r in rows))     # 没写 slug 从书名取

    def test_second_version(self):
        root = self.dir / "demo"
        shutil.copytree(FIX / "demo_snapshot", root)
        code, out = run("words", root)
        self.assertEqual(code, 0, out)
        rows = tsv_rows((root / "成品" / "导入" / "单词本.tsv").read_text(encoding="utf-8"))
        pre = [r for r in rows if r[8] == "读前"]
        self.assertTrue(pre)
        self.assertTrue(all(r[5] for r in pre), [r[1] for r in pre if not r[5]])


# ---------- 卡句定位 ----------

class TestStuck(Temp):
    def setUp(self):
        super().setUp()
        self.root = make_project(self.dir / "p", [(1, V3L, None)], stuck=STUCK)

    def locate(self, text=None):
        B.load_project(self.root)
        return B.sibling("notebook").locate_stuck(B, text)

    def test_six_results(self):
        got = {x["line"]: x for x in self.locate()}
        self.assertEqual({k: x["result"] for k, x in got.items()},
                         {7: "命中", 8: "多处", 9: "近似", 10: "找不到", 11: "太短", 12: "命中"})
        hit = got[7]
        self.assertEqual((hit["unit"], hit["sentence"], hit["mark"], hit["mark_words"]),
                         (1, "The Mole was bewitched, entranced, fascinated.", "有生词", ["bewitched", "entranced"]))
        self.assertEqual(hit["text"], "The Mole was bewitched, entranced, fascinated.")      # 行首的「- 」去掉
        self.assertEqual((got[8]["unit"], got[8]["sentence"], len(got[8]["places"])), (None, "", 2))
        near = got[9]
        self.assertTrue(0.85 <= near["score"] < 1, near)
        self.assertTrue(near["sentence"].startswith("As he gazed, something bright and small seemed to twinkle"))
        self.assertEqual((got[10]["unit"], got[10]["sentence"], got[10]["mark"]), (None, "", "词都认识"))
        self.assertEqual((got[11]["count"], len(got[11]["places"])), (2, 2))
        quote = got[12]                                      # 直引号、直撇号，半角 |
        self.assertEqual(quote["sentence"], "“Oh, it’s all very well to talk,” said the Mole rather pettishly, "
                                            "he being new to a river and riverside life and its ways.")
        self.assertEqual(quote["mark"], "词都认识")
        for x in got.values():
            self.assertEqual(x["scope"], 1)

    def test_command(self):
        code, out = run("stuck", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("第 7 行　命中　第 1 章　6 词　", out)
        self.assertIn("　有生词：bewitched, entranced　讲了：卡句 1\n", out)
        self.assertIn("第 8 行　多处（2 处）", out)
        self.assertIn("第 9 行　近似（相似度 0.", out)
        self.assertIn("    原文：As he gazed, something bright and small seemed to twinkle", out)
        self.assertIn("第 10 行　找不到（第 1 章）", out)
        self.assertIn("第 11 行　太短（2 个词）", out)
        self.assertRegex(out, r"第 12 行　命中　第 1 章　24 词　.*　词都认识　讲了：卡句 2\n")
        lines = out.strip().splitlines()
        self.assertEqual(lines[-2], "命中 2，多处 1，近似 1，找不到 1，太短 1")
        self.assertEqual(lines[-1], "卡句 6 句：词都认识 2，有生词 1，没说 3。多数没说卡在哪，看不出是词还是句子。")
        self.assertEqual((self.root / "卡句.txt").read_text(encoding="utf-8"), STUCK)     # 只读

    def test_json(self):
        code, out = run("stuck", self.root, "--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual([x["result"] for x in data["items"]], ["命中", "多处", "近似", "找不到", "太短", "命中"])
        self.assertEqual(data["items"][0]["covered"], "卡句 1")
        self.assertEqual(data["items"][0]["words"], 6)
        self.assertTrue(data["summary"].startswith("卡句 6 句："))

    def test_no_file(self):
        (self.root / "卡句.txt").unlink()
        code, out = run("stuck", self.root)
        self.assertEqual(code, 0)
        self.assertIn("项目里没有 卡句.txt", out)
        B.load_project(self.root)
        self.assertEqual(B.sibling("notebook").locate_stuck(B), [])

    def test_not_utf8(self):
        (self.root / "卡句.txt").write_bytes("第 1 章\n读不懂：The Mole was bewitched, entranced\n".encode("gb18030"))
        code, out = run("stuck", self.root)
        self.assertEqual(code, 0)
        self.assertIn("不是 UTF-8 编码", out)
        self.assertIn("问题 0 个", run("check", self.root)[1])        # check 照常跑完

    def test_cross_sentence_and_short_unique(self):
        got = self.locate("unpacking the basket. It never is\ncontemptuous Mole\n")
        self.assertEqual(got[0]["result"], "命中")
        self.assertTrue(got[0]["sentence"].startswith("Packing the basket was not quite such pleasant work"))
        self.assertIn("跨了 2 句，取第一句；下一句是「It never is.」", got[0]["notes"])
        self.assertEqual(got[1]["result"], "命中")            # 不到 4 个词，但只有一处
        self.assertEqual(got[0]["scope"], None)             # 没有单元行：全书找

    def test_unit_lines(self):
        nb = B.sibling("notebook")
        text = ("# 第 1 章\nthe bottom of the boat\n[2]\nthe bottom of the boat\n第一章\na b c d\n"
                "## 第 1 部分\na b c d\n第 9 章\na b c d\n# 注释：第 1 章\na b c d\n第 2 章：The Open Road\na b c d\n"
                "# 第 1 章的句子还没贴完\na b c d\n")
        got = nb.parse_stuck_file(text, [1, 2])
        self.assertEqual([x["scope"] for x in got], [1, 2, 1, 1, None, None, 2, 2])
        self.assertEqual(got[4]["notes"], ["第 9 行的单元行「第 9 章」不在项目里（或没有原文），全书找"])
        # 「# 注释：第 1 章」「# 第 1 章的句子还没贴完」是注释，不是单元行；不带 # 的单元行后面可以跟标题
        self.assertEqual(len(got), 8)

    def test_marks_and_cleanup(self):
        nb = B.sibling("notebook")
        got = nb.parse_stuck_file("- > “The Mole was bewitched” ｜有生词\n1. word word word word |有生词: a，b、c ; d\n"
                                  "* word word word word ｜不太懂\n'word word word word'\nword | word ｜词都认识\n", [1])
        self.assertEqual([(x["text"], x["mark"], x["mark_words"]) for x in got],
                         [("The Mole was bewitched", "有生词", []), ("word word word word", "有生词", ["a", "b", "c", "d"]),
                          ("word word word word", "没说", []), ("word word word word", "没说", []),
                          ("word | word", "词都认识", [])])
        self.assertEqual(got[2]["notes"], ["认不出的标记「不太懂」，按没说（写成 ｜词都认识、｜有生词 或 ｜有生词：词, 词）"])
        self.assertEqual(got[3]["notes"], [])

    def test_scope_across_units(self):
        self.root = make_project(self.dir / "q", [(1, V3L, None), (2, V3L, None)])
        got = self.locate("The Mole was bewitched, entranced\n第 2 章\nThe Mole was bewitched, entranced\n")
        self.assertEqual(got[0]["result"], "多处")
        self.assertEqual([p["unit"] for p in got[0]["places"]], [1, 2])
        self.assertEqual((got[1]["result"], got[1]["unit"]), ("命中", 2))

    OTHER = ("Toad sat straight down in the middle of the dusty road. "
             "He walked down the long road and then he walked down the long road again.\n")

    def two_units(self):
        self.root = make_project(self.dir / "q", [(1, V3L, None), (2, V3L, None)])
        (self.root / "原文" / "第02章.txt").write_text(self.OTHER, encoding="utf-8")

    def test_wrong_unit_line(self):
        # 单元行写错：第 1 章里找不到，全书再找；命中照常给结果，加一条提示
        self.two_units()
        got = self.locate("第 1 章\nToad sat straight down in the middle\n")
        self.assertEqual((got[0]["result"], got[0]["unit"]), ("命中", 2))
        self.assertIn("不在第 1 章，在第 2 章", got[0]["notes"])
        self.assertEqual(self.locate("第 2 章\nToad sat straight down in the middle\n")[0]["notes"], [])

    def test_wrong_unit_line_many(self):
        # 单元行写错、别的章有两处以上：照旧报找不到，提示别的章有几处
        self.root = make_project(self.dir / "q", [(1, V3L, None), (2, V3L, None), (3, V3L, None)])
        (self.root / "原文" / "第01章.txt").write_text(self.OTHER, encoding="utf-8")
        got = self.locate("第 1 章\nThe Mole was bewitched, entranced\n")
        self.assertEqual(got[0]["result"], "找不到")
        self.assertIn("别的章有 2 处", got[0]["notes"])

    def test_twice_in_one_sentence(self):
        # 短语在同一句里出现两次：只算一处，命中
        self.two_units()
        got = self.locate("walked down the long road\n")
        self.assertEqual((got[0]["result"], got[0]["unit"]), ("命中", 2))
        self.assertTrue(got[0]["sentence"].startswith("He walked down the long road and then"))

    def test_extra_bar_and_no_words(self):
        # 行尾多一个 ｜：标记取前一段；没有英文词的行跳过，不进小结
        nb = B.sibling("notebook")
        got = nb.parse_stuck_file("Toad sat straight down in the road ｜ 词都认识 ｜\n｜词都认识\n“”\n", [1])
        self.assertEqual([(x["text"], x["mark"]) for x in got], [("Toad sat straight down in the road", "词都认识")])

    def test_summary(self):
        nb = B.sibling("notebook")
        marks = lambda *m: [{"mark": x} for x in m]
        self.assertEqual(nb.stuck_summary(marks("词都认识", "词都认识", "词都认识", "有生词", "没说")),
                         "卡句 5 句：词都认识 3，有生词 1，没说 1。多数卡在句子上。")
        self.assertTrue(nb.stuck_summary(marks("有生词", "有生词", "有生词", "词都认识")).endswith("多数卡在词上。"))
        self.assertTrue(nb.stuck_summary(marks("有生词", "词都认识")).endswith("卡在词上和卡在句子上的差不多。"))
        self.assertEqual(nb.stuck_summary([]), "卡句.txt 里没有句子。")


class TestCheckHint(Temp):
    """check 的卡句提示：定位到本单元、讲义里没讲的才报（build.py 的 stuck_hints 调 locate_stuck）。"""

    def hints(self, text, mode):
        root = make_project(self.dir / "p", [(1, text, mode)], stuck=STUCK)
        code, out = run("check", root)
        self.assertIn("问题 0 个", out)
        return [l for l in out.splitlines() if " 卡句：" in l]

    def test_hint_for_uncovered(self):
        # 精读夹具的卡句 1 讲了第 7 行；第 12 行（Oh, it’s all very well …）没讲。多处、近似、找不到、太短都不报
        self.assertEqual(self.hints(V3J, "精读"), ["提示 第 1 章 卡句：卡句.txt 第 12 行「\"Oh, it's all very well to tal…」"
                                                   "定位到本章，讲义里没讲（写进长难句或「## 卡句」）"])

    def test_no_hint_when_covered(self):
        self.assertEqual(self.hints(V3L, None), [])        # 轻读夹具的卡句 1、2 正好是第 7、12 行


# ---------- 难句本.pdf 的 HTML：只生成 HTML、用拼出来的「读回文字」测页码，不启动任何程序 ----------

class TestBookPdf(Temp):
    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ENGLISH_READER_FONTS", None)
        self.root = make_project(self.dir / "项目", [(1, V3J, "精读"), (2, V3L, None)])
        self.b = load_build()
        self.b.load_project(self.root)
        self.nb = self.b.sibling("notebook")
        self.book = self.nb.sentence_book(self.b)
        self.page = self.nb.book_html(self.book, self.b)
        body = self.page.split("<body>")[1]
        self.intro = body.split("</section>")[0]
        self.q = body.split('<section class="post sba-sec"')[0][len(self.intro):]
        self.a = body.split('<section class="post sba-sec"')[1]

    def tearDown(self):
        self.env.stop()
        super().tearDown()

    def test_intro_page(self):
        self.assertTrue(self.intro.startswith('<section class="front sbi" style="page:sb-intro">'))
        self.assertIn(f'<h1 class="fh">{TITLE}</h1><p class="sbs">第 1–2 章</p>', self.intro)
        self.assertEqual(re.findall(r"<li>(.*?)</li>", self.intro), list(self.nb.SB_USAGE))
        self.assertIn(self.nb.REREAD, self.intro)
        self.assertNotIn('class="cover"', self.page)

    def test_groups_start_pages(self):
        # 有句子的组各占一节（新的一页），只有另见的「并列」接在前一组后面；组的顺序同 结构标签.tsv
        secs = self.q.split('<section class="post sbq-sec" style="page:sb-q">')[1:]
        with_items = [g["tag"] for g in self.book["groups"] if g["items"]]
        self.assertEqual(len(secs), len(with_items))
        self.assertEqual([re.search(r'<h3 class="sgt"[^>]*>(.+?)（', s).group(1) for s in secs], with_items)
        self.assertIn("并列（另见 3 句）", secs[with_items.index("独立结构")])
        see_only = secs[with_items.index("独立结构")].split("并列（另见 3 句）", 1)[1]
        self.assertNotIn('class="sgd"', see_only)                       # 只有另见的组：不印定义和读法
        self.assertNotIn('class="sgr"', see_only)
        self.assertIn('class="sbsee"', see_only)
        heads = re.findall(r'<h3 class="sgt"[^>]*>(.+?)（', self.q)
        self.assertEqual(heads, [t for t in TAG_ORDER if t in heads])
        self.assertIn('<h2 class="sk">一、自己拆</h2>', secs[0])
        self.assertIn('<p class="sgd">主语和谓语之间插了长修饰，谓语来得晚。</p>', self.q)
        self.assertIn('<p class="sgr"><span class="sbk">读法</span>', self.q)

    def test_question_side(self):
        self.assertNotIn('<b class="core">', self.q)          # 原句照讲义的样子，不标粗
        self.assertNotIn('class="cg', self.q)
        self.assertIn('<p class="orig">It was small wonder, then, that he suddenly flung down his brush', self.q)
        self.assertIn('<p class="sbt"><span class="sbk">试</span>真正的主语从哪个词开始？</p>'
                      '<p class="sbz"><span class="sbk">注</span><span class="c">bolt</span> 猛冲</p>', self.q)
        self.assertIn('另见：<a href="#q-2-4">2-4</a>', self.q)

    def test_links_both_ways(self):
        qs = re.findall(r'<li id="q-([\w-]+)">.*?<a class="sbl-a" href="#a-([\w-]+)">〔(.+?)〕</a></li>', self.q)
        self.assertEqual(len(qs), len(self.book["entries"]))
        self.assertTrue(all(x == y for x, y, _ in qs))
        back = re.findall(r'<article class="sent v3" id="a-([\w-]+)"><div class="pt"></div><div class="sth"><h4 class="st">'
                          r'<a class="sn" href="#q-([\w-]+)">', self.a)
        self.assertEqual(sorted(back), sorted((x, x) for x, _, _ in qs))
        self.assertIn(("1-k2", "1-k2", "1-卡2"), qs)          # 卡句的锚点是 k，显示的编号是 卡

    def test_answer_side(self):
        self.assertTrue(self.a.startswith(' style="page:sb-a"><div class="pt"></div><h2 class="sk">二、对照</h2>'))
        a21 = self.a.split('id="a-2-1"')[1].split("</article>")[0]
        for s in ('<span class="tg">it 占位</span><span class="tg">并列</span>', '<div class="cg below keep">',
                  '<b class="core">It</b> <b class="core">was</b> small wonder,', '<p class="nts">',
                  '<p class="sbtry"><span class="sbk">试</span>真正的主语从哪个词开始？　<span class="sbk">答</span><span class="c">that</span></p>',
                  '<div class="tag">卡点</div>', '<div class="tag">译</div>'):
            self.assertIn(s, a21)
        order = [a21.index(s) for s in ('class="sth"', 'class="cg', 'class="nts"', 'class="sbtry"', ">卡点<", ">译<")]
        self.assertEqual(order, sorted(order))
        a11 = self.a.split('id="a-1-1"')[1].split("</article>")[0]
        self.assertIn('<div class="tag">怎么拆</div>', a11)
        for lab in ("句型", "举一反三", "赏析"):                 # 句型、延伸、赏析留在讲义里
            self.assertNotIn(f'<div class="tag">{lab}</div>', a11)
        self.assertIn('<span class="tg tgm">没说</span>', self.a.split('id="a-1-k2"')[1].split("</article>")[0])
        self.assertNotIn("并列（", self.a)                      # 只有另见的组不进对照

    def test_page_css(self):
        css = self.page.split("<style>")[1].split("</style>")[0]
        self.assertIn(f'@page sb-q{{@top-left{{content:"{TITLE} · 难句本"}}@top-right{{content:"自己拆"}}}}', css)
        self.assertIn(f'@page sb-a{{@top-left{{content:"{TITLE} · 难句本"}}@top-right{{content:"对照"}}}}', css)
        self.assertIn(self.b.PDF_CSS, css)
        self.assertIn(self.b.PDF_CSS_V3, css)
        self.assertIn("@page{size:148mm 210mm;margin:18mm 15mm 16mm;", css)      # A5、页边同讲义

    def test_page_numbers(self):
        self.assertNotIn("对照见第", self.page)
        pages = {g["tag"]: 9 + k for k, g in enumerate(self.book["groups"]) if g["items"]}
        page = self.nb.book_html(self.book, self.b, pages)
        self.assertIn('<a class="sbp" href="#ag-1">对照见第 9 页</a>', page)
        self.assertEqual(page.count("对照见第"), len(pages))
        self.assertIn('<h3 class="sgt" id="ag-1">主谓隔开（1 句）</h3>', page)

    def fake_words(self):
        """拼出来的「读回文字」：题面各页的页眉是 自己拆，对照各页是 对照。"""
        qh = re.sub(r"\s+", "", f"{TITLE} · 难句本自己拆")
        ah = re.sub(r"\s+", "", f"{TITLE} · 难句本对照")
        p = lambda text, head="": {"head": head, "text": re.sub(r"\s+", "", text), "fill": 0.8}
        groups = [g for g in self.book["groups"] if g["items"]]
        words = [p("难句本")] + [p(f"{g['tag']}（{len(g['items'])} 句）", qh) for g in groups]
        words += [p("二、对照" + "".join(f"{g['tag']}（{len(g['items'])} 句）" for g in groups[:3]), ah), p("…", ah)]
        words += [p(f"{g['tag']}（{len(g['items'])} 句）", ah) for g in groups[3:]]
        return words, groups

    def test_answer_pages(self):
        words, groups = self.fake_words()
        got = self.nb.answer_pages(words, self.book, self.b)
        n = 1 + len(groups)
        self.assertEqual(got, {g["tag"]: n + 1 if k < 3 else n + 3 + (k - 3) for k, g in enumerate(groups)})
        self.assertIsNone(self.nb.answer_pages(words[:-1], self.book, self.b))      # 有一组找不到：都不印
        self.assertIsNone(self.nb.answer_pages(None, self.book, self.b))

    def test_book_pdf_two_passes(self):
        words, _ = self.fake_words()
        target = self.dir / "out" / "难句本.pdf"
        with mock.patch.object(self.b, "render_pdf") as render, mock.patch.object(self.b, "pdf_words", return_value=words), \
                redirect_stdout(StringIO()) as out:
            self.nb.book_pdf(self.book, self.b, target)
        self.assertEqual(render.call_count, 2)
        self.assertNotIn("对照见第", render.call_args_list[0].args[0])
        self.assertIn("对照见第", render.call_args_list[1].args[0])
        self.assertEqual(render.call_args_list[1].args[1], target)
        self.assertIn(str(target), out.getvalue())

    def test_book_pdf_without_words(self):
        with mock.patch.object(self.b, "render_pdf") as render, mock.patch.object(self.b, "pdf_words", return_value=None), \
                redirect_stdout(StringIO()) as out:
            self.nb.book_pdf(self.book, self.b, self.dir / "难句本.pdf")
        self.assertEqual(render.call_count, 1)
        self.assertIn("题面不印「对照见第 N 页」", out.getvalue())

    def test_sentences_pdf_path(self):
        # sentences --pdf：照常出 md、tsv，再交给 book_pdf（这里换掉排版，不启动程序）
        with mock.patch.object(self.b, "render_pdf") as render, mock.patch.object(self.b, "pdf_words", return_value=None), \
                redirect_stdout(StringIO()):
            code = self.nb.run("sentences", ["--pdf"], self.b)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "成品" / "复习" / "难句本.md").exists())
        self.assertEqual(render.call_args.args[1], self.b.P.root / "成品" / "复习" / "难句本.pdf")
        self.assertIn('<section class="front sbi"', render.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
