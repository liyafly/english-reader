"""scripts/profile.py 的单元测试：demo 的篇幅和句长、变形归并、切词残片、占比区间和建议、读前词候选、
单元数、TSV、取不到级别数据时的降级；第三版的长句、拆句候选、卡句标记、--sent-tsv、两头的读法建议。

运行：python3 -m unittest tests/test_profile.py
不联网。用 fixtures/demo_snapshot/：2026-11-13 从 demo/ 原样复制的 设置.json、两章原文和两章讲义（只读）。
demo 以后再改，这里的预期值不跟着变；要更新就重新复制一份快照，再按快照核对预期值。
要放 卡句.txt 的用例把快照复制到临时目录再改，不动快照本身。
"""
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEMO = ROOT / "tests" / "fixtures" / "demo_snapshot"  # demo/ 的冻结副本，测试不读 demo/
sys.path.insert(0, str(SCRIPTS))

# 标准库也有 profile 模块，按文件路径载入，免得撞名
_spec = importlib.util.spec_from_file_location("er_profile", SCRIPTS / "profile.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

import lexicon as L  # noqa: E402
import source as S  # noqa: E402

_LEX = None


def lex():
    global _LEX
    if _LEX is None:
        _LEX = L.Lexicon(cache_dir=Path(tempfile.gettempdir()) / "lexicon-test-unused", offline=True)
    return _LEX


def run_main(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        P.main([str(a) for a in argv])
    return out.getvalue(), err.getvalue()


def profile_paras(paras_by_unit):
    units = [("u%d" % i, paras, i + 1) for i, paras in enumerate(paras_by_unit)]
    prof = P.Profiler(lex(), units)
    return [prof.unit(paras) for _, paras, _ in units]


CH1_LISTED = ["scull", "luncheon", "paw", "fling", "meadow", "hedge"]
CH2_LISTED = ["cart", "paddock", "bunk", "locker", "trudge", "murmur", "ditch"]


class TestDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units, cls.project, cls.unit = P.read_units(DEMO)
        prof = P.Profiler(lex(), cls.units)
        cls.stats = [prof.unit(paras) for _, paras, _ in cls.units]
        cls.listed = P.lecture_lists(cls.project, cls.unit)
        cls.rules, cls.short_words = P.load_rules()

    def test_length_numbers_unchanged(self):
        ch1, ch2 = self.stats
        self.assertEqual((ch1.words, len(ch1.sent_lens), ch1.paras, ch1.headings), (4350, 238, 94, 2))
        self.assertEqual((ch2.words, len(ch2.sent_lens), ch2.paras), (4280, 261, 72))

    def test_inflections_go_to_lemma(self):
        keys = {}
        for st in self.stats:
            for (kind, lv, key), d in st.types.items():
                keys.setdefault(key, set()).update(d["forms"])
        for form, lemma in (("fellows", "fellow"), ("cushions", "cushion"), ("trotted", "trot")):
            with self.subTest(form=form):
                self.assertIn(form, keys.get(lemma, set()))
                self.assertNotIn(form, keys)

    def test_no_fragments(self):
        for st in self.stats:
            keys = {k for (_, _, k) in st.types}
            for junk in ("w", "e", "ll", "s", "d", "t", "m", "ve", "re", "ii"):
                self.assertNotIn(junk, keys)
        well = self.stats[0].types[("list", "A1", "well")]
        self.assertIn("w-e-ll", well["forms"])  # W-e-ll → well

    def test_unrated_top10_clean(self):
        for st in self.stats:
            un = sorted(P.by_lemma(st, "B1", lambda k, lv, rd: k == P.NONE).items(), key=lambda x: -x[1]["n"])
            top = [k for k, _ in un[:10]]
            self.assertEqual(len(top), 10)
            for k in top:
                self.assertFalse(P.junk_key(k), k)
                self.assertGreater(len(k), 1)
        top1 = [k for k, _ in sorted(P.by_lemma(self.stats[0], "B1", lambda k, lv, rd: k == P.NONE).items(),
                                     key=lambda x: (-x[1]["n"], x[0]))[:3]]
        self.assertEqual(top1, ["hullo", "moorhens", "weir"])

    def test_range_and_advice(self):
        for st in self.stats:
            lo, mid, hi, total = P.above_range(st, "B1")
            self.assertLess(lo, mid)
            self.assertLess(mid, hi)
            self.assertEqual(total, st.total_tokens())
            m = P.pct_value(mid, total)
            self.assertTrue(5 < m <= 10, m)
        # 两头的建议：第 1 章长句 18.5% 落在第 4 行，第 2 章 14.2% 落在第 3 行
        keys = []
        for st in self.stats:
            lo, mid, hi, total = P.above_range(st, "B1")
            lp = P.long_stats(st, self.rules["long_sentence_words"])[1]
            keys.append(P.advice_key(P.pct_value(mid, total), lp, self.rules["above_pct"], self.rules["long_pct"]))
        self.assertEqual(keys, ["both", "guide"])
        # 读者高一档，占比只会更低
        self.assertLess(P.above_range(self.stats[0], "B2")[1], P.above_range(self.stats[0], "B1")[1])

    def test_toad_is_proper_noun(self):
        ch2 = self.stats[1]
        self.assertGreaterEqual(ch2.types[("proper", P.PROPER_NAME, "Toad")]["n"], 40)
        cands = {k for k, _, _ in P.preread_candidates(ch2, "B1", self.rules, self.short_words)[0]}
        self.assertNotIn("toad", cands)

    def test_lecture_words(self):
        self.assertEqual(P.lecture_words(DEMO / "讲义" / "第01章.md"), CH1_LISTED)
        self.assertEqual(P.lecture_words(DEMO / "讲义" / "第02章.md"), CH2_LISTED)
        self.assertEqual(sorted(self.listed), [1, 2])

    def test_preread_ch2_against_lecture(self):
        ch2 = self.stats[1]
        before = P.listed_keys(self.listed[1], lex())
        rows, need = P.preread_candidates(ch2, "B1", self.rules, self.short_words, before)
        self.assertEqual(need, 3)
        keys = [k for k, _, _ in rows]
        top = keys[:self.rules["preread_top"]]
        # 讲义选的 7 个词都在前 15 个里；fad 只出现 2 次（fad、fads），够不上门槛，讲义已换成 murmur
        for w in CH2_LISTED:
            self.assertIn(w, top)
        self.assertNotIn("fad", keys)
        # 次数相同时未定级的排在有级别的后面
        self.assertGreater(keys.index("good-natured"), keys.index("locker"))
        self.assertEqual(P.by_lemma(ch2, "B1")["fad"]["n"], 2)
        # 第 1 章讲义列过的词不再出现；其中 scull、paw 在第 2 章也够 3 次，是被去重拿掉的
        for w in CH1_LISTED:
            self.assertNotIn(w, keys)
        full = {k for k, _, _ in P.preread_candidates(ch2, "B1", self.rules, self.short_words)[0]}
        self.assertTrue({"scull", "paw"} <= full)

    def test_british_spelling_ch2(self):
        """英式拼写按美式写法定级：coloured → colored（color/colour A1），parlour → parlor（估 B2），
        gipsy → gypsy（Octanove C1）。改之前 coloured 估成 C2、进了读前词候选，parlour、gipsy 未定级。"""
        ch2 = self.stats[1]
        found = {key: (kind, lv, d) for (kind, lv, key), d in ch2.types.items()}
        kind, lv, d = found["colour"]
        self.assertEqual((kind, lv), (P.LIST, "A1"))
        self.assertIn("coloured", d["forms"])
        self.assertNotIn("coloured", found)
        self.assertEqual(found["parlour"][:2], (P.EST, "B2"))
        self.assertEqual(found["gipsy"][:2], (P.LIST, "C1"))
        unrated = P.by_lemma(ch2, "B1", lambda k, lv, rd: k == P.NONE)
        for w in ("gipsy", "parlour", "coloured"):
            self.assertNotIn(w, unrated)
        cands = {k for k, _, _ in P.preread_candidates(ch2, "B1", self.rules, self.short_words)[0]}
        self.assertNotIn("coloured", cands)
        self.assertNotIn("colour", cands)

    def test_unit_spread(self):
        out, _ = run_main(DEMO)
        self.assertIn("出现单元数最多的词", out)
        self.assertRegex(out, r"scull（[^）]*） +C2 估 +2/2 单元")


class TestTokens(unittest.TestCase):
    def test_clitic_fragments_skipped(self):
        st, = profile_paras([["We ’ll see what he ’s got. It was the 1920’s, and x marks the spot."]])
        keys = {k for (_, _, k) in st.types}
        for junk in ("ll", "s", "x"):
            self.assertNotIn(junk, keys)
        self.assertEqual(sum(st.skipped.values()), 4)
        self.assertEqual(st.words, 16)  # 词数照旧

    def test_stutter_and_compounds(self):
        st, = profile_paras([["“W-w-what?” said the good-natured man. He came to-day."]])
        keys = {k for (_, _, k) in st.types}
        self.assertIn("what", keys)
        self.assertIn("today", keys)
        self.assertIn("good-natured", keys)  # 拆开有一段未定级：整个算一个未定级词
        self.assertNotIn("natured", keys)
        self.assertNotIn("w", keys)

    def test_poem_line_capitals_not_proper(self):
        st, = profile_paras([["Ducks’ tails, drakes’ tails,\nYellow feet a-quiver,\nYellow bills all out of sight"]])
        proper = {k for (kind, _, k) in st.types if kind == "proper"}
        self.assertNotIn("Yellow", proper)

    def test_roman_numeral_heading(self):
        st, = profile_paras([["II", "The Open Road", "The Mole said nothing."]])
        self.assertNotIn("ii", {k for (_, _, k) in st.types})
        self.assertEqual(st.skipped["II"], 1)

    def test_short_text_threshold(self):
        para = "The paddock was green. " + "The dog ran. " * 50 + "They left the paddock."
        st, = profile_paras([[para]])
        rules, short_words = P.load_rules()
        self.assertLess(st.check_words, short_words)
        rows, need = P.preread_candidates(st, "B1", rules, short_words)
        self.assertEqual(need, 2)
        self.assertIn("paddock", [k for k, _, _ in rows])
        long_st, = profile_paras([[para + " The cat sat." * 400]])
        rows, need = P.preread_candidates(long_st, "B1", rules, short_words)
        self.assertEqual(need, 3)
        self.assertNotIn("paddock", [k for k, _, _ in rows])


class TestRules(unittest.TestCase):
    def test_rules_json_profile_block(self):
        data = json.loads((SCRIPTS / "rules.json").read_text(encoding="utf-8"))
        self.assertEqual(list(data)[:2], ["_说明", "profile"])
        self.assertTrue(any(line.startswith("profile：") for line in data["_说明"]))
        self.assertEqual(data["profile"]["above_pct"], [5, 10])
        rules, short_words = P.load_rules()
        self.assertEqual((rules["above_pct"], rules["preread_top"], short_words), ([5, 10], 15, 1200))
        self.assertEqual(rules["preread_min_count"], {"long": 3, "short": 2})
        # 第三版加的三个键和 v3.sentence.min_words
        self.assertEqual((rules["long_sentence_words"], rules["long_pct"], rules["drill_top"]), (30, [5, 15], 12))
        self.assertEqual(rules[P.SENT_MIN_WORDS], {"A2": 18, "B1": 22, "B2": 28, "C1": 32})
        self.assertEqual(rules[P.SENT_MIN_WORDS], data["v3"]["sentence"]["min_words"])

    def test_advice_boundaries(self):
        a, l = [5, 10], [5, 15]
        self.assertEqual(P.advice_key(5.0, 5.0, a, l), "easy")
        self.assertEqual(P.advice_key(5.0, 5.1, a, l), "drill")
        self.assertEqual(P.advice_key(5.1, 15.0, a, l), "guide")
        self.assertEqual(P.advice_key(10.0, 15.1, a, l), "both")
        self.assertEqual(P.advice_key(10.1, 0.0, a, l), "words")
        # 词 ≤5% 时句看 long_pct 的第一道门槛：10% 已经算长句多
        self.assertEqual(P.advice_key(4.0, 10.0, a, l), "drill")
        # 门槛读 rules，不写死
        self.assertEqual(P.advice_key(4.0, 10.0, a, [12, 20]), "easy")
        self.assertEqual(P.advice_key(8.0, 18.0, a, [12, 20]), "guide")

    def test_five_advice_texts(self):
        """五种建议各一例。"""
        a, l = [5, 10], [5, 15]
        cases = [
            ((3.0, 4.0), "可以直接读，讲义帮着扫清个别句子。"),
            ((3.0, 12.0), "词不难，长句多：适合拿来练拆句。"),
            ((7.0, 10.0), "建议配讲义读。"),
            ((7.0, 18.0), "词和句子都有难度：配讲义读，把卡住的句子记进 卡句.txt。"),
            ((12.0, 2.0), "偏难，主要难在词：练拆句的效果会打折。可以降一档、换一篇，或者精读。"),
        ]
        for (w, s), text in cases:
            with self.subTest(w=w, s=s):
                self.assertEqual(P.advice(w, s, a, l), text)
        self.assertEqual(len({t for _, t in cases}), 5)
        # 词 >10% 时句不看
        self.assertEqual(P.advice(12.0, 40.0, a, l), cases[4][1])

    def test_missing_profile_block_uses_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rules.json"
            p.write_text('{"counts": {"short_words": 1000}}', encoding="utf-8")
            with redirect_stderr(io.StringIO()) as err:
                rules, short_words = P.load_rules(p)
            self.assertEqual((rules["above_pct"], short_words), ([5, 10], 1000))
            self.assertIn("没有 profile 组", err.getvalue())
            self.assertEqual((rules["long_sentence_words"], rules["long_pct"], rules["drill_top"]), (30, [5, 15], 12))
            self.assertEqual(rules[P.SENT_MIN_WORDS], P.DEFAULT_MIN_WORDS)


class TestMain(unittest.TestCase):
    def test_full_output(self):
        out, err = run_main(DEMO)
        self.assertEqual(err, "")
        for s in ("段 94   句 238", "词 4,350", "下限", "中间", "上限", "建议（按中间值", "读前词候选",
                  "高一级（B2）", "高两级及以上（C1、C2）", "未定级（前 10", "## 全书（2 个单元）",
                  "去掉前面单元讲义列过的（第 1 章）"):
            self.assertIn(s, out)
        for s in ("未收", "Oxford", "会用候选", "认得候选"):
            self.assertNotIn(s, out)
        ch2 = out.split("## 第 2 章")[1].split("## 全书")[0]
        pre = ch2.split("读前词候选")[1].split("高一级")[0]
        for w in CH1_LISTED:
            self.assertNotRegex(pre, r"\n  %s[（ ]" % w)

    def test_tsv(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "候选.tsv"
            run_main(DEMO, "--tsv", p)
            lines = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "词\t级别\t依据\t档\t次数\t单元数\t例句")
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in lines[1:]}
        self.assertEqual(rows["scull"][1:6], ["C2", "估级", "高两级及以上", "13", "2"])
        self.assertEqual(rows["cart"][5], "1")
        self.assertEqual(rows["hullo"][1:4], ["未定级", "未定级", "未定级"])
        self.assertNotIn("Toad", rows)

    def test_single_file_reads_earlier_lecture(self):
        out, _ = run_main(DEMO / "原文" / "第02章.txt")
        self.assertIn("去掉前面单元讲义列过的（第 1 章）", out)
        self.assertNotIn("## 全书", out)
        self.assertNotIn("单元  ", out.split("读前词候选")[1].split("高一级")[0])  # 单个文件不列单元数

    def test_level_option(self):
        out, _ = run_main(DEMO, "--level", "b2")
        self.assertIn("读者 B2", out)
        self.assertIn("高于读者水平（C1 及以上）", out)
        with self.assertRaises(SystemExit):
            run_main(DEMO, "--level", "C2")

    def test_degrade_without_level_data(self):
        with tempfile.TemporaryDirectory() as d:
            tsv = Path(d) / "x.tsv"
            with mock.patch.object(P, "Lexicon", side_effect=L.LexiconError("缺少级别数据：ecdict-subset.tsv.gz")):
                out, _ = run_main(DEMO, "--tsv", tsv)
            self.assertFalse(tsv.exists())
        self.assertIn("取不到级别数据（缺少级别数据：ecdict-subset.tsv.gz）", out)
        self.assertIn("段 94   句 238（另有标题行 2 个，不计入句子）   词 4,350", out)
        self.assertIn("句长：平均 18.3 词，中位数 13 词", out)
        self.assertIn("## 全书（2 个单元）", out)
        self.assertIn("没有写", out)
        for s in ("下限", "读前词候选", "高一级", "建议（"):
            self.assertNotIn(s, out)

    def test_degrade_keeps_long_sentences(self):
        """取不到级别数据：长句统计和拆句候选照出，高于水平的词数是 —，--sent-tsv 照写、那一栏空着。"""
        with tempfile.TemporaryDirectory() as d:
            st_tsv = Path(d) / "句.tsv"
            with mock.patch.object(P, "Lexicon", side_effect=L.LexiconError("缺少级别数据：ecdict-subset.tsv.gz")):
                out, err = run_main(DEMO, "--sent-tsv", st_tsv)
            lines = st_tsv.read_text(encoding="utf-8").splitlines()
        self.assertEqual(err, "")
        self.assertIn("长句（30 词以上）：44 句，占 18.5%；这些句子的词数占全文 45.4%", out)
        self.assertIn("长句（30 词以上）：37 句，占 14.2%；这些句子的词数占全文 38.6%", out)
        self.assertIn("拆句候选（22 词以上，共 70 句，按词数和从属词多少排，列前 12 句）：", out)
        self.assertRegex(out, r"\n    84       —       3     5  When the floods are on in February, and …\n")
        self.assertIn("  单元  词数  高于B1  从属词  逗号  开头", out)  # 全书的表多一栏单元
        self.assertEqual(len(lines), 1 + 70 + 60)
        self.assertEqual(lines[1].split("\t")[:5], ["1", "84", "", "3", "5"])

    def test_shares_splitter_with_source(self):
        self.assertIs(P.split_sentences, S.split_sentences)
        self.assertIs(P.is_heading, S.is_heading)


def chapter(out, n):
    """run_main 输出里第 n 章那一节。"""
    sec = out.split("## 第 %d 章" % n)[1]
    return sec.split("\n", 1)[1].split("\n## ")[0]  # 去掉标题那一行的其余部分


def fake_stats(above, other, long_n, short_n):
    """造一个 Stats：above 个高于 B1 的词次（词表定级 C1），other 个 A1 词次；long_n 句 35 词、short_n 句 10 词。"""
    st = P.Stats()
    st.tok[(P.LIST, "C1")] = above
    st.tok[(P.LIST, "A1")] = other
    st.sent_lens = [(35, "x")] * long_n + [(10, "y")] * short_n
    st.sent_info = [{"levels": None, "unit": 1, "stuck": False} for _ in st.sent_lens]
    return st


class TestLongSentences(unittest.TestCase):
    """第三版：长句、拆句候选、--sent-tsv。"""

    @classmethod
    def setUpClass(cls):
        cls.units, cls.project, _ = P.read_units(DEMO)
        prof = P.Profiler(lex(), cls.units)
        cls.stats = [prof.unit(paras) for _, paras, _ in cls.units]
        P.tag_sentences(cls.units, cls.stats, cls.project)
        cls.rules, _ = P.load_rules()
        cls.out, cls.err = run_main(DEMO)

    def test_demo_numbers(self):
        """demo 的长句统计：第 1 章 238 句里 44 句、18.5%、45.4%；第 2 章 261 句里 37 句、14.2%、38.6%。"""
        got = [(len(st.sent_lens),) + P.long_stats(st, 30) for st in self.stats]
        self.assertEqual(got, [(238, 44, 18.5, 45.4), (261, 37, 14.2, 38.6)])
        self.assertIn("长句（30 词以上）：44 句，占 18.5%；这些句子的词数占全文 45.4%", chapter(self.out, 1))
        self.assertIn("长句（30 词以上）：37 句，占 14.2%；这些句子的词数占全文 38.6%", chapter(self.out, 2))
        self.assertIn("长句（30 词以上）：81 句，占 16.2%；这些句子的词数占全文 42.0%",
                      self.out.split("## 全书")[1])

    def test_threshold_inclusive(self):
        """词数达到门槛就算长句：30 词算，29 词不算。"""
        st = P.Stats()
        st.sent_lens = [(30, "a"), (29, "b"), (10, "c"), (31, "d")]
        self.assertEqual(P.long_stats(st, 30), (2, 50.0, 61.0))
        self.assertEqual(P.long_stats(P.Stats(), 30), (0, 0.0, 0.0))

    def test_old_lines_unchanged_and_placement(self):
        """原有的篇幅、句长行不变；长句和拆句候选接在「最长的三句」后面、级别表前面。"""
        ch1 = chapter(self.out, 1).strip("\n").splitlines()
        self.assertEqual(ch1[:8], [
            "段 94   句 238（另有标题行 2 个，不计入句子）   词 4,350",
            "句长：平均 18.3 词，中位数 13 词",
            "句长分布：1–10 词 95 句（39.9%）  11–20 词 71 句（29.8%）  21–30 词 31 句（13.0%）  31–40 词 22 句（9.2%）"
            "  41+ 词 19 句（8.0%）",
            "最长的三句：",
            "  1. 84 词：When the floods are on in February, and …",
            "  2. 83 词：But the Mole was bent on enjoying everything, …",
            "  3. 71 词：By the side of the river he trotted …",
            "长句（30 词以上）：44 句，占 18.5%；这些句子的词数占全文 45.4%",
        ])
        self.assertEqual(ch1[8], "拆句候选（22 词以上，共 70 句，按词数和从属词多少排，列前 12 句）：")
        self.assertEqual(ch1[9], "  词数  高于B1  从属词  逗号  开头")
        self.assertEqual(ch1[10], "    84       7       3     5  When the floods are on in February, and …")
        self.assertEqual(ch1[22], "")
        self.assertTrue(ch1[23].startswith("级别 "), ch1[23])
        self.assertEqual(self.err, "")

    def test_advice_line(self):
        self.assertIn("建议（按中间值 7.4%，长句占 18.5%）：词和句子都有难度：配讲义读，把卡住的句子记进 卡句.txt。"
                      "只是提示，读不读、怎么读由用户定。", chapter(self.out, 1))
        self.assertIn("建议（按中间值 7.8%，长句占 14.2%）：建议配讲义读。只是提示，读不读、怎么读由用户定。",
                      chapter(self.out, 2))

    def test_candidates_order_and_limit(self):
        ch2 = P.drill_candidates(self.stats[1], "B1", 22)
        self.assertEqual(len(ch2), 60)
        self.assertTrue(all(r["words"] >= 22 for r in ch2))
        keys = [(-r["words"], -r["subs"], r["order"]) for r in ch2]
        self.assertEqual(keys, sorted(keys))
        # 词数相同的按从属词多的在前：两句 44 词，5 个从属词的在 0 个的前面
        same = [r for r in ch2 if r["words"] == 44]
        self.assertEqual([r["subs"] for r in same], [5, 0])
        self.assertTrue(same[0]["sent"].startswith("“Now, look here, Toad!”"))
        rows = [ln for ln in chapter(self.out, 2).split("开头\n")[1].split("\n\n")[0].splitlines()]
        self.assertEqual(len(rows), 12)  # profile.drill_top

    def test_min_words_by_level(self):
        rules = self.rules
        self.assertEqual([P.min_words_for(rules, lv) for lv in ("A2", "B1", "B2", "C1")], [18, 22, 28, 32])
        self.assertEqual(P.min_words_for(rules, "A1"), 18)  # 没列的水平用最小的一档
        out, _ = run_main(DEMO, "--level", "B2")
        self.assertIn("拆句候选（28 词以上", out)
        self.assertIn("  词数  高于B2  从属词  逗号  开头", out)
        self.assertEqual(len(P.drill_candidates(self.stats[0], "B2", 28)),
                         sum(1 for n, _ in self.stats[0].sent_lens if n >= 28))

    def test_above_count_per_sentence(self):
        """一句里高于读者水平的词次：口径同中间值（词表定级和估级的），专名、未定级不算。"""
        st, = profile_paras([["The cat was ambiguous and meticulous about the river. The dog ran."]])
        r1, r2 = st.sent_info
        self.assertEqual((P.above_in(r1["levels"], "B1"), P.above_in(r1["levels"], "B2")), (2, 1))
        self.assertEqual(P.above_in(r2["levels"], "B1"), 0)
        c = Counter({(P.LIST, "B2"): 2, (P.EST, "C1"): 1, (P.NONE, P.UNRATED): 3, (P.PROPER, P.PROPER_NAME): 4,
                     (P.LIST, "A1"): 10})
        self.assertEqual((P.above_in(c, "B1"), P.above_in(c, "B2"), P.above_in(None, "B1")), (3, 1, None))

    def test_per_sentence_levels_add_up(self):
        """每句的级别计数加上标题行的，等于整个单元的：句长按整段切、级别按诗行切，两边对得上。"""
        prof = P.Profiler(lex(), self.units)
        for (_, paras, _), st in zip(self.units, self.stats):
            total = Counter()
            for info in st.sent_info:
                total.update(info["levels"])
            total.update(prof.unit([p for p in paras if P.is_heading(p)]).tok)
            self.assertEqual(total, st.tok)
        st, = profile_paras([["Ducks’ tails, drakes’ tails,\nYellow feet a-quiver. The meticulous Mole\nslept."]])
        self.assertEqual(len(st.sent_lens), 2)
        total = Counter()
        for info in st.sent_info:
            total.update(info["levels"])
        self.assertEqual(total, st.tok)

    def test_subordinators_and_commas(self):
        s = "When he saw THAT the boat, which was old, had sunk, that’s what he said, although as before."
        self.assertEqual(P.subordinator_count(s), 7)  # When THAT which what although as before；that’s 不算
        st, = profile_paras([[s + " " + "and the dog ran " * 5 + "home."]])
        r, = P.drill_candidates(st, "B1", 22)
        self.assertEqual((r["subs"], r["commas"]), (7, 4))

    def test_opening(self):
        s = "Their way lay, as before, across country by narrow lanes, and in the afternoon"
        self.assertEqual(P.opening(s), "Their way lay, as before, across country …")
        self.assertLessEqual(P.width(P.opening(s)), P.OPENING_WIDTH + 2)
        self.assertEqual(P.opening("Short one."), "Short one.")

    def test_sent_tsv(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "拆句候选.tsv"
            out, _ = run_main(DEMO, "--sent-tsv", p)
            lines = p.read_text(encoding="utf-8").splitlines()
        self.assertIn("拆句候选已写入 %s（130 行）" % p, out)
        self.assertEqual(lines[0], "单元\t词数\t高于水平词数\t从属词\t逗号\t原句")
        self.assertEqual(len(lines), 131)
        rows = [ln.split("\t") for ln in lines[1:]]
        self.assertTrue(all(len(r) == 6 for r in rows))
        self.assertEqual(rows[0][:5], ["1", "84", "7", "3", "5"])
        self.assertTrue(rows[0][5].startswith("When the floods are on in February,"))
        self.assertEqual([r[0] for r in rows].count("1"), 70)
        self.assertEqual(rows[70][:2], ["2", "96"])  # 按单元，单元内同屏幕上的顺序

    def test_no_sentences(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            P.print_sentences(P.Stats(), "B1", self.rules)
            st, = profile_paras([["The cat sat. The dog ran."]])
            P.tag_sentences([("u", [], 1)], [st], None)
            P.print_sentences(st, "B1", self.rules)
        self.assertEqual(buf.getvalue(), "长句（30 词以上）：0 句，占 0.0%；这些句子的词数占全文 0.0%\n"
                                         "拆句候选（22 词以上）：没有。\n")


class TestAdviceOutput(unittest.TestCase):
    """print_range 按两头给建议：五种各一例，走到输出那一行。"""

    def test_five_cases_printed(self):
        rules, _ = P.load_rules()
        cases = [  # (高于 B1 的词次, 其余词次, 长句数, 短句数) → 建议
            ((3, 97, 1, 99), "可以直接读"),       # 词 3%，句 1%
            ((3, 97, 10, 90), "适合拿来练拆句"),   # 词 3%，句 10%
            ((7, 93, 10, 90), "建议配讲义读。"),    # 词 7%，句 10%
            ((7, 93, 20, 80), "记进 卡句.txt"),    # 词 7%，句 20%
            ((15, 85, 0, 10), "主要难在词"),       # 词 15%
        ]
        for args, text in cases:
            with self.subTest(args=args):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    P.print_range(fake_stats(*args), "B1", rules)
                line = [ln for ln in buf.getvalue().splitlines() if ln.startswith("建议（")][0]
                self.assertIn(text, line)
                self.assertTrue(line.endswith("只是提示，读不读、怎么读由用户定。"), line)
                self.assertIn("长句占 %.1f%%" % (100.0 * args[2] / (args[2] + args[3])), line)


class TestStuck(unittest.TestCase):
    """卡句.txt 的读法和 ★卡句 标记（只标范围内唯一命中的）。"""

    STUCK = "\n".join([
        "# 读的时候卡住的句子。",
        "",
        "第 2 章",
        "The old grey horse, dreaming, as he plodded along ｜词都认识",
        "- “Naturally a voluble animal, and always mastered” |有生词：voluble",
        "# 第 1 章",
        "1. The Mole begged as a favour",
        "the Rat",
        "[2]",
        "> you’ll have to go straight to the police station",
        "Toad",
        "this sentence is not in the book at all",
    ])

    def test_read_stuck(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "卡句.txt"
            p.write_text("\ufeff" + self.STUCK, encoding="utf-8")
            got = P.read_stuck(p)
        self.assertEqual([u for u, _ in got], [2, 2, 1, 1, 2, 2, 2])
        self.assertEqual(got[0][1], "the old grey horse dreaming as he plodded along".split())
        self.assertEqual(got[1][1], "naturally a voluble animal and always mastered".split())
        self.assertEqual(got[2][1], "the mole begged as a favour".split())
        self.assertEqual(got[4][1], "you'll have to go straight to the police station".split())

    def test_read_stuck_units(self):
        """单元行可以写中文数字；单元号不在项目里的按全书找（同 build.py stuck）；行首 2、 和两头的引号去掉。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "卡句.txt"
            p.write_text("第二章\nTen words here\n第 9 章\nsome words\n# 第 1 章\n2、 “quoted words” ｜有生词\n",
                         encoding="utf-8")
            got = P.read_stuck(p, known={1, 2})
            self.assertEqual(P.read_stuck(p)[1][0], 9)  # 不给 known 时照写
        self.assertEqual(got, [(2, ["ten", "words", "here"]), (None, ["some", "words"]), (1, ["quoted", "words"])])
        self.assertEqual(P.source_units(DEMO), {1, 2})

    def test_norm_words(self):
        self.assertEqual(P.norm_words("Good-Nature’s\u00ad “quite”\u200b ＴＯ-DAY"), ["good", "nature's", "quite", "to", "day"])
        self.assertEqual(P.norm_words("police-station"), P.norm_words("police station"))
        # 和 build.py stuck 的归一化一致
        _b = importlib.util.spec_from_file_location("er_build_for_profile", SCRIPTS / "build.py")
        B = importlib.util.module_from_spec(_b)
        _b.loader.exec_module(B)
        for s in ("Good-Nature’s\u00ad “quite”\u200b ＴＯ-DAY", "the 1920’s, and x marks—the spot!", "Ça va, Café?",
                  "you’ll have to go straight to the police-station"):
            with self.subTest(s=s):
                self.assertEqual(P.norm_words(s), B.stuck_words(s))

    def test_locate(self):
        idx = [(1, "a b c d a b".split(), [0, 0, 1, 1, 2, 2]), (2, "c d e f".split(), [0, 0, 1, 1])]
        self.assertEqual(P.locate_stuck([(None, ["b", "c"])], idx), {(0, 0)})  # 跨两句取开头那句
        self.assertEqual(P.locate_stuck([(None, ["a", "b"])], idx), set())  # 一个单元里两处
        self.assertEqual(P.locate_stuck([(None, ["c", "d"])], idx), set())  # 两个单元各一处
        self.assertEqual(P.locate_stuck([(2, ["c", "d"])], idx), {(1, 0)})  # 写了单元行只找那个单元
        self.assertEqual(P.locate_stuck([(3, ["c", "d"])], idx), set())  # 单元不在范围里
        self.assertEqual(P.locate_stuck([(None, ["x"])], idx), set())

    def test_marks_in_output(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "proj"
            shutil.copytree(DEMO, proj)
            (proj / P.STUCK_FILE).write_text(self.STUCK, encoding="utf-8")
            out, err = run_main(proj)
            single, _ = run_main(proj / "原文" / "第02章.txt")
        self.assertEqual(err, "")
        ch1, ch2 = chapter(out, 1), chapter(out, 2)
        # 第 1 章：唯一命中的标上；the Rat 多处，不标
        self.assertRegex(ch1, r"\n    66       5       2     4  The Mole begged as a favour to be …   ★卡句\n")
        self.assertEqual(ch1.count("★卡句"), 1)
        # 第 2 章：police station 命中 “Now, look here, Toad!” 那句（在前 12 句里）；另两句排在 12 句以外，接在后面
        self.assertIn("\n    44       2       5     4  “Now, look here, Toad!” said the Rat …   ★卡句\n", ch2)
        self.assertIn("He led the way to the stable-yard …\n  （下面 2 句是卡句，排在前 12 句以外）\n"
                      "    42       4       1     2  Naturally a voluble animal, and always …   ★卡句\n"
                      "    28       2       2     5  The old grey horse, dreaming, as he …   ★卡句\n", ch2)
        self.assertEqual(ch2.count("★卡句"), 3)  # Toad 多处、书里没有的那行不标
        self.assertEqual(out.split("## 全书")[1].count("★卡句"), 4)
        # 单个文件：同样读项目的 卡句.txt，只标这个文件里的
        self.assertEqual(single.count("★卡句"), 3)

    def test_unreadable_stuck_file(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "proj"
            shutil.copytree(DEMO, proj)
            (proj / P.STUCK_FILE).write_bytes(b"\xff\xfe\x00bad")
            out, err = run_main(proj)
        self.assertIn("拆句候选里不标卡句", err)
        self.assertNotIn("★卡句", out)
        self.assertIn("长句（30 词以上）：44 句", out)


if __name__ == "__main__":
    unittest.main()
