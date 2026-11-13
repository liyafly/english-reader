"""scripts/lexicon.py 的单元测试：音标换算与比对、词形还原的清理规则、级别（含英式拼写）、讲义解析、
熟词生义、标签说法的核对、来源降级。

运行：python3 -m unittest tests/test_lexicon.py
不联网。系统词典的实测只在 macOS 上、且装了「牛津英汉汉英词典」时跑，其他环境自动跳过。
夹具里的系统词典 HTML 和 Wiktionary JSON 是照结构自己编的，不含词典原文。
讲义用 fixtures/demo_snapshot/（2026-11-13 从 demo/ 原样复制），不读 demo/：demo 以后再改，这里的预期值不跟着变。
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "demo_snapshot"
sys.path.insert(0, str(SCRIPTS))

import lexicon as L  # noqa: E402

_LEX = None


def lex():
    global _LEX
    if _LEX is None:
        # 离线：不会往缓存目录写东西，目录也不会被建出来
        _LEX = L.Lexicon(cache_dir=Path(tempfile.gettempdir()) / "lexicon-test-unused", offline=True)
    return _LEX


# demo 讲义的快照：第 1 章读前 6 个词、词的用法 10 个词条；第 2 章读前 7 个词、词的用法 3 个词条
DEMO_CH1 = (SNAPSHOT / "讲义" / "第01章.md").read_text(encoding="utf-8")
DEMO_CH2 = (SNAPSHOT / "讲义" / "第02章.md").read_text(encoding="utf-8")

# 2026-11-13 本机「牛津英汉汉英词典」的英式音标（原样），给第 1 章 12 个带音标的行做比对夹具
MAC_IPA = {
    "scull": ["skʌl"],
    "luncheon": ["ˈlʌn(t)ʃ(ə)n"],
    "paw": ["pɔː"],
    "fling": ["flɪŋ"],
    "meadow": ["ˈmɛdəʊ"],
    "hedge": ["hɛdʒ"],
    "prepared": ["prɪˈpɛːd"],
    "mean": ["miːn"],
    "forbear": ["fəˈbɛː", "fɔːˈbɛː"],
    "presently": ["ˈprɛzntli"],
    "interfere": ["ˌɪntəˈfɪə"],
    "dwell": ["dwɛl"],
}
EXPECTED_STATUS = {
    "scull": "一致", "luncheon": "一致", "paw": "一致", "fling": "一致", "meadow": "仅写法不同", "hedge": "仅写法不同",
    "prepared": "仅写法不同", "mean": "一致", "forbear": "仅写法不同",
    "presently": "仅写法不同", "interfere": "一致", "dwell": "仅写法不同",
}


class TestIpaTable(unittest.TestCase):
    def test_table(self):
        cases = {
            "kat": "kæt",          # cat
            "hɛː": "heə",          # hair
            "bəːd": "bɜːd",        # bird
            "prʌɪs": "praɪs",      # price
            "fɔːˈbɛː": "fɔːˈbeə",  # forbear
            "fɔːˈbɛə": "fɔːˈbeə",  # Wiktionary 的 forbear
            "ˈlʌn(t)ʃ(ə)n": "ˈlʌn(t)ʃ(ə)n",  # luncheon：没有要换的
            "dwɛl": "dwel",
            "naʊ": "naʊ",          # aʊ 里的 a 不动
            "taɪm": "taɪm",        # aɪ 里的 a 不动
            "ˈfʌɪə": "ˈfaɪə",
            "/kat/": "kæt",        # 斜线去掉
        }
        for src, want in cases.items():
            with self.subTest(src=src):
                self.assertEqual(L.to_oxford(src)[0], want)

    def test_changes_reported(self):
        conv, changes = L.to_oxford("ˈprɛzntli")
        self.assertEqual(conv, "ˈprezntli")
        self.assertEqual(changes, ["ɛ→e"])

    def test_ecdict_notation(self):
        self.assertEqual(L.to_oxford("fɒ:'bєә", "ecdict")[0], "fɔːˈbeə")
        self.assertEqual(L.to_oxford("'nʌmbә", "ecdict")[0], "ˈnʌmbə")

    def test_variants(self):
        self.assertEqual(L.ipa_variants("ˈlʌn(t)ʃ(ə)n"), {"ˈlʌnʃn", "ˈlʌntʃn", "ˈlʌnʃən", "ˈlʌntʃən"})
        self.assertEqual(L.ipa_variants("fɔːˈbeə(r)"), {"fɔːˈbeə", "fɔːˈbeər"})


class TestCompare(unittest.TestCase):
    def test_fixture_words(self):
        cases = [
            ("/kæt/", ["kat"], "仅写法不同"),
            ("/heə/", ["hɛː"], "仅写法不同"),
            ("/bɜːd/", ["bəːd"], "仅写法不同"),
            ("/praɪs/", ["prʌɪs"], "仅写法不同"),
            ("/fɔːˈbeə/", ["fəˈbɛː", "fɔːˈbɛː"], "仅写法不同"),
            ("/ˈlʌntʃən/", ["ˈlʌn(t)ʃ(ə)n"], "一致"),
            ("/fɔːˈbeə(r)/", ["fɔːˈbɛː"], "仅写法不同"),
            ("/miːn/", ["miːn"], "一致"),
            ("/ˈɡʊd/", ["ˈgʊd"], "一致"),  # ɡ 和 g 不分
        ]
        for mine, theirs, want in cases:
            with self.subTest(mine=mine):
                self.assertEqual(L.compare_ipa(mine, theirs, "macos")[0], want)

    def test_mismatch_and_hints(self):
        st, note, _ = L.compare_ipa("/raʊ/", ["rəʊ"], "macos")
        self.assertEqual(st, "不一致")
        st, note, _ = L.compare_ipa("/kat/", ["kat"], "macos")  # 照抄了系统词典的写法
        self.assertEqual(st, "不一致")
        self.assertIn("/kæt/", note)
        st, note, _ = L.compare_ipa("/fɔ:'beə/", ["fɔːˈbɛː"], "macos")
        self.assertEqual(st, "不一致")
        self.assertIn("ASCII 冒号", note)
        self.assertIn("ASCII 撇号", note)

    def test_other_states(self):
        self.assertEqual(L.compare_ipa("/fɔːˈbeə/", ["fɒ:'bєә"], "ecdict")[0], "参考")
        self.assertIn("相同", L.compare_ipa("/fɔːˈbeə/", ["fɒ:'bєә"], "ecdict")[1])
        self.assertEqual(L.compare_ipa("/fɔːˈbeə/", [], None)[0], "未核对")
        self.assertEqual(L.compare_ipa("", ["kat"], "macos")[0], "未核对")
        self.assertEqual(L.compare_ipa("/fɔːˈbeə/", ["fɔːˈbɛə"], "wiktionary")[0], "仅写法不同")


class TestLectureFixture(unittest.TestCase):
    def test_parse_demo_ch1(self):
        items = L.parse_lecture(DEMO_CH1)
        self.assertEqual(len(items), 16)
        self.assertTrue(all(it["raw"] is None for it in items))
        pre = [it for it in items if it["section"] == "读前"]
        self.assertEqual([(it["headword"], it["phon"], it["pos"]) for it in pre], [
            ("scull", "/skʌl/", "v."), ("luncheon", "/ˈlʌntʃən/", "n."), ("paw", "/pɔː/", "n."),
            ("fling", "/flɪŋ/", "v."), ("meadow", "/ˈmedəʊ/", "n."), ("hedge", "/hedʒ/", "n.")])
        self.assertEqual(pre[1]["gloss"], "午餐（正式说法）")
        items = [it for it in items if it["section"] == "词的用法"]
        self.assertEqual(len(items), 10)
        got = [(it["headword"], it["word"], it["phon"], it["pos"], it["master"]) for it in items]
        self.assertEqual(got, [
            ("all very well", "", "", "phr.", "会用"),
            ("be prepared to do", "prepared", "/prɪˈpeəd/", "adj.", "会用"),
            ("mean", "", "/miːn/", "adj.", "会用"),
            ("forbear", "", "/fɔːˈbeə/", "v.", "认得"),
            ("presently", "", "/ˈprezntli/", "adv.", "认得"),
            ("interfere with", "interfere", "/ˌɪntəˈfɪə/", "vi.", "认得"),
            ("there’s no denying", "", "", "phr.", "会用"),
            ("dwell on", "dwell", "/dwel/", "vi.", "会用"),
            ("take to", "", "", "phr.", "会用"),
            ("might have done", "", "", "phr.", "会用"),
        ])

    def test_entry_texts(self):
        items = {it["headword"]: it for it in L.parse_lecture(DEMO_CH1) if it["section"] == "词的用法"}
        mean = items["mean"]
        self.assertTrue(mean["first_of_entry"])
        self.assertEqual(mean["entry_texts"][0], ("首行", "英式英语里 mean 常指“小气，舍不得花钱”，不只是“刻薄”。"))
        self.assertIn(("辨析", "说“小气”，美式英语用 cheap；stingy（口语）英美都用。"), mean["entry_texts"])
        names = [n for n, _ in mean["entry_texts"]]
        self.assertEqual(names, ["首行", "搭配", "辨析", "例"])  # 原文、译、掌握、词典不在里面
        self.assertEqual([n for n, _ in items["forbear"]["entry_texts"]], ["首行", "词族", "辨析"])

    def test_two_dict_items_share_entry_texts(self):
        md = "## 词的用法\n\n- **x**：英式说法。\n  词典：alpha /ˈælfə/ n. 甲\u3000beta /ˈbiːtə/ n. 乙\n  掌握：认得\n"
        a, b = L.parse_lecture(md)
        self.assertEqual((a["word"], a["first_of_entry"]), ("alpha", True))
        self.assertEqual((b["word"], b["first_of_entry"]), ("beta", False))
        self.assertIs(a["entry_texts"], b["entry_texts"])

    def test_demo_ch1_ipa_against_recorded_macos(self):
        for it in L.parse_lecture(DEMO_CH1):
            if not it["phon"]:
                continue
            w = L.lookup_word(it)
            with self.subTest(word=w):
                self.assertEqual(L.compare_ipa(it["phon"], MAC_IPA[w], "macos")[0], EXPECTED_STATUS[w])

    def test_preread_section(self):
        md = """# 第 2 章讲解

## 读前

背景。

- **the Mole**：鼹鼠

### 本章的词

- **scull** /skʌl/ v. 用桨划船
- **take to** phr. 开始喜欢
- **meadow**：草地（格式不对）

## 理解
"""
        items = L.parse_lecture(md)
        self.assertEqual(len(items), 3)
        self.assertEqual((items[0]["headword"], items[0]["phon"], items[0]["pos"], items[0]["gloss"]),
                         ("scull", "/skʌl/", "v.", "用桨划船"))
        self.assertEqual((items[1]["headword"], items[1]["phon"], items[1]["pos"]), ("take to", "", "phr."))
        self.assertIsNotNone(items[2]["raw"])
        self.assertTrue(all(it["section"] == "读前" for it in items))

    def test_phrase_core(self):
        self.assertEqual(L.phrase_core("be prepared to do"), "prepared to")
        self.assertEqual(L.phrase_core("might have done"), "might have")
        self.assertEqual(L.phrase_core("there’s no denying"), "there's no denying")
        self.assertEqual(L.phrase_core("take to"), "take to")


class TestLemmaRules(unittest.TestCase):
    def test_three_rules(self):
        rows = {
            # 规则 1：number 比 numb 常见，不算 numb 的比较级
            "numb": (9000, 0, "r:number/d:numbed", ""),
            "number": (200, 0, "s:numbers/0:numb/1:r", ""),
            # 一个变形有几个原形：取常见的
            "do": (18, 0, "3:does/p:did", ""),
            "doe": (20000, 0, "s:does", ""),
            # 规则 2：链压平；中间是有名次的词时停下
            "find": (95, 0, "p:found/d:found", ""),
            "found": (2600, 0, "0:find/1:pd/p:founded/d:founded", ""),
            "child": (100, 0, "s:children", ""),
            "children": (0, 0, "0:child/1:s/s:childrens", ""),
            # 规则 3：循环
            "xa": (0, 0, "0:xb", ""),
            "xb": (0, 0, "0:xa", ""),
        }
        m = L.build_lemma_map(rows)
        self.assertNotIn("number", m)
        self.assertEqual(m["numbed"], "numb")
        self.assertEqual(m["does"], "do")
        self.assertEqual(m["found"], "find")
        self.assertEqual(m["founded"], "found")   # 不压到 find
        self.assertEqual(m["childrens"], "child")  # children 没有名次，压平
        self.assertNotIn("xa", m)
        self.assertNotIn("xb", m)

    def test_listed_lemma_preferred(self):
        rows = {
            # 几个原形：词表收了、词性也对的优先（distill 是动词）
            "distil": (17042, 0, "i:distilling", ""), "distill": (23567, 0, "i:distilling", ""),
            # 反例：词表收了但词性不对（-ed 要动词，premier 只是名词、形容词），照旧取常见的 premiere
            "premier": (7616, 0, "d:premiered", ""), "premiere": (6832, 0, "d:premiered", ""),
            # 变形自己的 0:原形/1:类型 也算类型：bath 只是名词，bathed 归 bathe
            "bath": (3000, 0, "d:bathed", ""), "bathe": (9000, 0, "", ""), "bathed": (0, 0, "0:bathe/1:pd", ""),
        }
        listed = {"distill": [("verb", "C2", "Octanove", "verb")],
                  "premier": [("adjective", "C1", "Octanove", "adjective"), ("noun", "C1", "Octanove", "noun")],
                  "bath": [("noun", "A1", "CEFR-J", "noun")], "bathe": [("verb", "B1", "CEFR-J", "verb")]}
        m = L.build_lemma_map(rows, listed)
        self.assertEqual((m["distilling"], m["premiered"], m["bathed"]), ("distill", "premiere", "bathe"))
        m = L.build_lemma_map(rows)  # 不给词表：只按名次
        self.assertEqual((m["distilling"], m["premiered"], m["bathed"]), ("distil", "premiere", "bath"))

    def fake(self, cefr, ecdict):
        """只带词表和 ECDICT 行的 Lexicon，不读数据文件：测后缀规则怎么挑原形。"""
        lx = L.Lexicon.__new__(L.Lexicon)
        lx.cefr = {k: [(fam, "B1", "CEFR-J", fam)] for k, fam in cefr.items()}
        lx.ecdict = {k: (r, 0, "", "") for k, r in ecdict.items()}
        lx.lemmas = {}
        return lx

    def test_rule_candidates_tiers(self):
        # 词表里的 mile 胜过 ECDICT 里有名次的 mil（规则顺序上 -es 在 -s 前面）
        self.assertEqual(self.fake({"mile": "noun"}, {"mil": 19799}).lemma_candidates("miles"),
                         [("mile", "后缀规则 -s")])
        # 反例：词表收了但词性不对的不要（mil 只是形容词，-s 要名词或动词），取 ECDICT 里的 mile
        self.assertEqual(self.fake({"mil": "adjective"}, {"mile": 500}).lemma("miles"), "mile")
        # 反例：都不在词表里，有名次的胜过没名次的，不论规则顺序
        self.assertEqual(self.fake({}, {"glim": 0, "glime": 900}).lemma("glimes"), "glime")
        self.assertEqual(self.fake({}, {"glim": 900, "glime": 0}).lemma("glimes"), "glim")
        # 同一档取名次靠前的：hope 比 hop 常见
        self.assertEqual(self.fake({"hop": "verb", "hope": "verb"}, {"hop": 5000, "hope": 300}).lemma("hopes"), "hope")

    def test_real_data(self):
        self.assertEqual(lex().lemma("miles"), "mile")  # 改之前：mil
        self.assertEqual(lex().lemma_candidates("miles"), [("mile", "后缀规则 -s")])
        i = lex().level_info("miles")
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("B1", "list", "mile"))  # 改之前：估 C2，按 mil
        self.assertEqual(lex().lemmas["premiered"], "premiere")  # 词表里的 premier 词性不对
        self.assertEqual(lex().lemma("numbs"), "numb")  # 改之前：number
        self.assertEqual(lex().lemmas["does"], "do")
        self.assertEqual(lex().lemma("trotted"), "trot")

    def test_rule_candidates_kept(self):
        self.assertIn(("stop", {"verb"}, "-ed"), L.rule_candidates("stopped"))
        self.assertEqual(L.IRREGULAR["flung"], "fling")


class TestLevels(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(L.est_level(999), "A1")
        self.assertEqual(L.est_level(1000), "A2")
        self.assertEqual(L.est_level(3999), "B1")
        self.assertEqual(L.est_level(7999), "B2")
        self.assertEqual(L.est_level(13999), "C1")
        self.assertEqual(L.est_level(14000), "C2")
        self.assertEqual(L.EST_THRESHOLDS[0], (1000, "A1"))

    def test_listed(self):
        lv, src = lex().level("interfere")
        self.assertEqual(lv, "B2")
        self.assertTrue(src.startswith("CEFR-J"))
        lv, src = lex().level("mean")
        self.assertEqual(lv, "A1")
        self.assertIn("多个词性取最低", src)
        self.assertEqual(lex().level("mean", "adj.")[0], "A2")
        self.assertEqual(lex().level("prepared", "adj")[0], "B1")

    def test_lemmatized(self):
        self.assertEqual(lex().level("children")[0], "A1")
        self.assertIn("child", lex().level("children")[1])
        self.assertEqual(lex().lemmas["does"], "do")  # 不是 doe 的复数
        self.assertEqual(lex().lemmas["trotted"], "trot")
        self.assertEqual(lex().level_info("number")["lemma"], "number")
        self.assertEqual(lex().level_info("fellows")["lemma"], "fellow")
        self.assertEqual(lex().level_info("didn’t")["level"], "A1")

    def test_estimated_and_unrated(self):
        i = lex().level_info("presently")
        self.assertEqual((i["level"], i["kind"]), ("B2", "estimate"))
        self.assertTrue(i["source"].startswith("估"))
        i = lex().level_info("trotted")
        self.assertEqual(i["kind"], "estimate")
        self.assertEqual(i["lemma"], "trot")
        self.assertEqual(lex().level("qzxqzx"), (L.UNRATED, "CEFR-J、Octanove 和 ECDICT 子集都没有"))
        self.assertIsNone(lex().classify("qzxqzx"))
        self.assertEqual(lex().classify("children")[:2], ("child", "A1"))

    def test_suggest(self):
        def info(lv, kind="list"):
            return {"level": lv, "kind": kind}
        self.assertEqual(L.suggest(info("B2"), "B1", [])[1], "会用")
        self.assertEqual(L.suggest(info("C1"), "B1", [])[1], "认得")
        self.assertEqual(L.suggest(info("B2"), "B1", ["formal"])[1], "认得")
        self.assertEqual(L.suggest(info("B2"), "B1", ["formal or literary"])[1], "认得")
        self.assertEqual(L.suggest(info("B2"), "B1", ["informal"])[1], "会用")
        self.assertEqual(L.suggest(info("B2", "estimate"), "B1", [])[0], "会用（估）")
        self.assertEqual(L.suggest(info("A2"), "B1", [])[0], "会用（不高于读者）")
        self.assertEqual(L.suggest(info(L.UNRATED, "none"), "B1", []), ("—（未定级）", None))


class TestBritishSpelling(unittest.TestCase):
    def test_variant_rules(self):
        cases = {
            "coloured": "colored", "parlour": "parlor", "gipsy": "gypsy", "travelled": "traveled", "centre": "center",
            "centred": "centered", "centres": "centers", "realise": "realize", "realisation": "realization",
            "analysed": "analyzed", "catalogue": "catalog", "grey": "gray", "programme": "program",
            "programmes": "programs", "plough": "plow", "ploughed": "plowed", "marvellous": "marvelous",
            "traveller": "traveler", "colourful": "colorful",
        }
        for w, am in cases.items():
            with self.subTest(word=w):
                self.assertEqual(L.american_variants(w)[0][0], am)
        self.assertEqual(L.american_variants("coloured"), [("colored", ["-our → -or"])])
        self.assertEqual(L.american_variants("gipsy"), [("gypsy", ["例外表 gipsy → gypsy"])])

    def test_no_variants(self):
        # -our 前面不到两个字母、re 前面是元音、单音节的 -ll-、美式写法是另一个词的
        for w in ("four", "hour", "your", "our", "more", "here", "fire", "are", "killed", "filled", "smaller",
                  "timbre", "called"):
            with self.subTest(word=w):
                self.assertEqual(L.american_variants(w), [])

    def test_positive_levels(self):
        i = lex().level_info("coloured")  # 改之前：估 C2（ECDICT 名次 22,818）
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("A1", "list", "colour"))
        self.assertTrue(i["how"].startswith("英式拼写 coloured → colored"), i["how"])
        self.assertIn("英式拼写 coloured → colored（-our → -or）", i["source"])
        self.assertEqual(i["american"], "colored")
        i = lex().level_info("parlour")  # 改之前：未定级
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("B2", "estimate", "parlour"))
        self.assertEqual(i["how"], "英式拼写 parlour → parlor")
        self.assertTrue(i["source"].startswith("估，ECDICT 名次 6,423"))
        i = lex().level_info("gipsy")  # 改之前：未定级
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("C1", "list", "gipsy"))
        self.assertEqual(i["how"], "英式拼写 gipsy → gypsy")
        self.assertTrue(i["source"].startswith("Octanove"))
        # 原词已经能定级的不走美式写法
        i = lex().level_info("travelled")
        self.assertEqual((i["level"], i["kind"], i["lemma"], i["american"]), ("A1", "list", "travel", ""))
        i = lex().level_info("centre")  # CEFR-J 收了 center/centre
        self.assertEqual((i["level"], i["kind"], i["how"]), ("A2", "list", ""))
        i = lex().level_info("centred")  # 改之前：未定级
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("A2", "list", "centre"))
        # 都是估级：美式名次好一倍以上才换（plough 28,832 → plow 8,039）
        i = lex().level_info("ploughed")
        self.assertEqual((i["level"], i["kind"], i["lemma"]), ("C1", "estimate", "plough"))
        self.assertIn("英式拼写 ploughed → plowed", i["how"])

    def test_negative_levels_unchanged(self):
        want = {"four": ("A1", "CEFR-J（number）"), "hour": ("A1", "CEFR-J（noun）"),
                "your": ("A1", "CEFR-J（determiner）"), "here": ("A1", "CEFR-J（adverb）"),
                "are": ("A1", "CEFR-J（be-verb）"),
                "more": ("A1", "CEFR-J（determiner、pronoun）；多个词性取最低：adverb B1、determiner A1、pronoun A1"),
                "fire": ("A1", "CEFR-J（noun）；多个词性取最低：noun A1、verb B2")}
        for w, (lv, src) in want.items():
            with self.subTest(word=w):
                i = lex().level_info(w)
                self.assertEqual((i["level"], i["source"], i["lemma"], i["american"]), (lv, src, w, ""))
        i = lex().level_info("timbre")  # 不能按 timber 定级
        self.assertEqual((i["level"], i["kind"], i["american"]), ("C2", "estimate", ""))

    def test_rank_uses_american(self):
        self.assertEqual(lex().rank("colour"), lex().rank("color"))
        self.assertEqual(lex().rank("parlour"), lex().rank("parlor"))
        self.assertEqual(lex().rank("four"), lex().freq("four"))


class TestPosMissing(unittest.TestCase):
    def test_level_info_flag(self):
        i = lex().level_info("common", "n")  # 词表里 common 只有形容词
        self.assertTrue(i["pos_missing"])
        self.assertEqual(i["level"], "A2")
        self.assertFalse(lex().level_info("common", "adj")["pos_missing"])
        self.assertFalse(lex().level_info("common")["pos_missing"])
        i = lex().level_info("paddock", "n")  # 完全不在词表里：照旧估级
        self.assertEqual((i["kind"], i["pos_missing"]), ("estimate", False))


EC_HTML = """<?xml version="1.0" encoding="UTF-8"?><html><head></head><body>\
<d:entry id="t1" d:title="testword" class="entry"><span class="hwg x_xh0">\
<span d:dhw="1" role="text" class="hw">testword </span>\
<span dialect="BrE" class="prx"><span class="gp tg_prx"> | </span><span class="gp tg_prx">BrE </span>\
<span class="ph">ˈtɛstwəːd<d:prn></d:prn></span><span class="gp tg_prx">, </span></span>\
<span dialect="AmE" class="prx"><span class="gp tg_prx">AmE </span><span class="ph">ˈtɛstwərd</span></span></span>\
<span class="gramb x_xd0"><span class="x_xdh"><span d:pos="1" class="ps">intransitive verb </span></span>\
<span class="semb x_xd1 hasSn"><span class="gp x_xdh sn ty_label tg_semb">① </span>\
<span class="trg x_xd2"><span class="lev">formal </span><span class="trans">测试一 </span><span class="trans ty_pinyin">cèshì</span></span>\
<span class="exg x_xd2 hasSn"><span class="x_xdh"><span class="sn">▸ </span><span class="ex">an example of it </span></span>\
<span class="trg x_xd3"><span class="lev">informal </span><span class="trans">例子</span></span></span></span>\
<span class="semb x_xd1 hasSn"><span class="gp x_xdh sn ty_label tg_semb">② </span>\
<span class="exg x_xd2"><span class="x_xdh"><span class="reg">British </span><span class="lev">euphemistic </span>\
<span class="con">to testword with sb </span></span><span class="trg x_xd3"><span class="trans">对某人测试</span></span></span></span>\
</span>\
<span class="pvb x_xo0"><span class="pvsec x_xo1"><span class="pvg x_xoh"><span class="pv">testword on </span></span>\
<span class="gramb x_xo2"><span class="x_xdh"><span class="ps">transitive verb </span></span>\
<span class="semb x_xo3"><span class="trg"><span class="lev">literary </span><span class="trans">老想着</span></span></span></span></span></span>\
</d:entry></body></html>"""

ODE_HTML = """<html><body><d:entry id="t2" d:title="testword" class="entry"><span class="hg x_xh0">\
<span role="text" class="hw">testword<span class="gp ty_hom tg_hw"> 1 </span></span>\
<span dialect="BrE" class="prx"> | <span class="ph t_IPA">ˈtɛstwəːd</span> | </span></span>\
<span class="sg"><span class="se1 x_xd0"><span class="x_xdh"><span role="text" class="posg">\
<span class="pos"><span class="gp tg_pos">verb </span></span>\
<span class="infg"><span class="inf">testwords </span><span dialect="BrE" class="prx"> | <span class="ph t_IPA">ˈtɛstwəːdz</span> |</span></span>\
</span></span>\
<span class="msDict x_xd1 t_core"><span role="text" class="lg"><span class="reg">dated </span></span>\
<span class="df">do a test</span><span class="eg"><span class="ex">he testworded it</span>\
<span class="lg"><span class="reg">informal</span></span></span></span></span></span>\
<span class="subEntryBlock x_xo0 t_phrases"><span class="subEntry x_xo1"><span class="l x_xoh">testword away</span>\
<span class="msDict x_xo2 t_core"><span class="lg"><span class="reg">literary </span></span><span class="df">test lazily</span>\
</span></span></span></d:entry></body></html>"""


class TestDictionaryParsing(unittest.TestCase):
    def test_ec(self):
        r = L.parse_ec_entry(EC_HTML)
        self.assertEqual(r["headword"], "testword")
        self.assertEqual(len(r["blocks"]), 1)  # 短语动词里的 gramb 不算
        b = r["blocks"][0]
        self.assertEqual(b["pos"], "intransitive verb")
        self.assertEqual(b["ipa_raw"], ["ˈtɛstwəːd"])
        self.assertEqual(b["senses"][0]["labels"], ["formal"])  # 例句里的 informal 不算
        self.assertEqual(b["senses"][0]["text"], "测试一")
        self.assertEqual(b["senses"][1]["labels"], ["British", "euphemistic"])
        self.assertTrue(b["senses"][1]["text"].startswith("to testword with sb"))
        self.assertEqual(b["labels"], [])  # 不是每个义项都有的标签，不算整条词的
        hit = L.find_phrase(r["root"], "testword on")
        self.assertEqual(hit["where"], "短语动词")
        self.assertEqual(L._phrase_labels(hit["block"], False), ["literary"])

    def test_ode(self):
        r = L.parse_ode_entry(ODE_HTML)
        self.assertEqual(r["headword"], "testword")
        b = r["blocks"][0]
        self.assertEqual(b["pos"], "verb")
        self.assertEqual(b["ipa_raw"], ["ˈtɛstwəːd"])  # 变形里的音标不算
        self.assertEqual(b["labels"], ["dated"])  # 例句的 informal、短语的 literary 都不算
        hit = L.find_phrase(r["root"], "testword away")
        self.assertEqual(hit["where"], "短语")
        self.assertEqual(L._phrase_labels(hit["block"], True), ["literary"])

    def test_all_labels(self):
        found = [(L.MAC_EC, L.parse_ec_entry(EC_HTML)), (L.MAC_ODE, L.parse_ode_entry(ODE_HTML))]
        e = lex()._merge_mac("testword", None, found)
        # 每个义项的标签都算（formal 只在义项①，British、euphemistic 只在义项②）；短语动词、例句、短语的不算
        self.assertEqual(set(e["all_labels"]), {"formal", "British", "euphemistic", "dated"})
        self.assertEqual(e["labels"], ["dated"])  # 整条词的标签照旧
        hits = L.find_phrase_all(L.parse_ec_entry(EC_HTML)["root"], "testword with")
        self.assertEqual([h["where"] for h in hits], ["搭配"])
        self.assertEqual(L._phrase_all_labels(hits[0], False), ["British", "euphemistic"])

    def test_wiktionary(self):
        data = [{"word": "testword",
                 "phonetics": [{"text": "/ˈtɛstwɜːd/", "audio": "https://example.org/testword-uk.mp3"},
                               {"text": "/ˈtɛstwɝd/", "audio": "https://example.org/testword-us.mp3"},
                               {"text": "[ˈtɛst.wɜːd]"}],
                 "meanings": [{"partOfSpeech": "verb", "definitions": [{"definition": "(formal) To test."},
                                                                       {"definition": "To try."}]},
                              {"partOfSpeech": "noun", "definitions": [{"definition": "A word for tests."}]}]}]
        e = L.parse_wiktionary("testword", data)
        self.assertEqual(e["ipa_br_raw"], ["ˈtɛstwɜːd"])
        self.assertEqual(e["ipa_br"], ["ˈtestwɜːd"])
        self.assertEqual(e["pos"], ["verb", "noun"])
        self.assertEqual(e["labels"], ["formal"])
        self.assertEqual(e["kind"], "wiktionary")
        self.assertEqual(e["all_labels"], ["formal"])
        self.assertEqual(len(L.parse_wiktionary("testword", data, "v")["senses"]), 2)


class _NoMac:
    available = False
    error = "测试里关掉了"


class TestFallback(unittest.TestCase):
    def make(self, settings=None):
        td = tempfile.TemporaryDirectory(prefix="lexicon-proj-")
        self.addCleanup(td.cleanup)
        d = Path(td.name)
        if settings is not None:
            import json
            (d / "设置.json").write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        lx = L.Lexicon(cache_dir=d / ".cache", project=d, offline=True)
        lx._mac = _NoMac()
        return lx

    def test_no_mac_falls_to_ecdict(self):
        e = self.make().entry("forbear")
        self.assertEqual(e["kind"], "ecdict")
        self.assertEqual(e["source"], "ECDICT（参考）")
        self.assertTrue(any("macOS 系统词典不可用" in n for n in e["notes"]))
        for k in ("headword", "ipa_br", "ipa_br_raw", "pos", "labels", "senses", "source"):
            self.assertIn(k, e)

    def test_nothing_available(self):
        e = self.make().entry("qzxqzx")
        self.assertEqual((e["kind"], e["source"]), (None, "未核对"))
        e = self.make().entry("forbear", source="macos")
        self.assertEqual(e["source"], "未核对")

    def test_local_dictionaries_placeholder(self):
        lx = self.make({"level": "B1", "dictionaries": [{"path": "/tmp/x.mdx"}]})
        self.assertEqual(lx.local_dictionaries(), [{"path": "/tmp/x.mdx", "status": "不支持，下一轮实现"}])
        e = lx.entry("forbear")
        self.assertTrue(any("不支持，下一轮实现" in n for n in e["notes"]))

    def test_check_rows_without_sources(self):
        lx = self.make()
        rows = L.check_rows(lx, L.parse_lecture(DEMO_CH1), "B1")
        self.assertEqual(len(rows), 16)
        by = {r["word"]: r for r in rows}
        self.assertEqual(by["forbear"]["status"], "参考")
        self.assertEqual(by["take to"]["status"], "未核对")
        self.assertTrue(by["forbear"]["suggest"].startswith("认得"))  # C2（估）比 B1 高三级
        self.assertEqual(by["all very well"]["suggest"], "—（未定级）")
        # 只有 ECDICT 或没有来源：讲义写了标签说法的 7 行都是“标签未核对”，不报 !标签
        marked = [r["word"] for r in rows if "标签未核对" in r["marks"]]
        self.assertEqual(marked, ["luncheon", "all very well", "mean", "forbear", "presently", "interfere", "dwell"])
        self.assertFalse([r for r in rows if "标签" in r["flags"]])
        self.assertTrue(any(n.startswith("标签未核对：讲义（词典行）说「口语」") for n in by["all very well"]["notes"]))
        self.assertTrue(any("ECDICT（参考）" in n for n in by["mean"]["notes"] if n.startswith("标签未核对")))

    def test_ch2_common_is_new_sense(self):
        rows = L.check_rows(self.make(), L.parse_lecture(DEMO_CH2), "B1")
        self.assertEqual(len(rows), 10)
        common = next(r for r in rows if r["word"] == "common")
        self.assertEqual(common["suggest"], "—（熟词生义：词表没有这个词性）")
        self.assertNotIn("掌握", common["flags"])  # 改之前：会用（不高于读者），标 !掌握
        self.assertEqual(common["level_plain"], "A2")
        self.assertFalse([r for r in rows if r["flags"]])


@unittest.skipUnless(sys.platform == "darwin", "只在 macOS 上跑")
class TestMacLive(unittest.TestCase):
    def setUp(self):
        mac = L.MacDictionary()
        if not (mac.available and mac.has(L.MAC_EC)):
            self.skipTest("系统词典不可用：%s" % (mac.error or "没有「%s」" % L.MAC_EC))

    def test_demo_ch1_with_macos(self):
        lx = lex()
        rows = L.check_rows(lx, L.parse_lecture(DEMO_CH1), "B1", source="macos")
        self.assertEqual(len(rows), 16)
        for r in rows:
            with self.subTest(word=r["word"]):
                self.assertIn(r["status"], ("一致", "仅写法不同"))
                self.assertTrue(r["source"].startswith("macOS"))
        # 系统词典里 presently 没有地区标签，all very well（well 词条的例句）没有 informal 一类的标签
        self.assertEqual([r["word"] for r in rows if "标签" in r["flags"]], ["all very well", "presently"])
        self.assertFalse([r for r in rows if r["marks"]])

    def test_demo_ch2_with_macos(self):
        rows = L.check_rows(lex(), L.parse_lecture(DEMO_CH2), "B1", source="macos")
        self.assertEqual(len(rows), 10)
        self.assertFalse([r for r in rows if r["flags"] or r["marks"]])
        common = next(r for r in rows if r["word"] == "common")
        self.assertEqual(common["suggest"], "—（熟词生义：词表没有这个词性）")

    def test_entry_shape(self):
        e = lex().entry("forbear", "v", source="macos")
        self.assertIn("fɔːˈbeə", e["ipa_br"])
        self.assertIn("formal", e["labels"])
        self.assertTrue(any("克制" in s["text"] for s in e["senses"]))


# 2026-11-13 本机系统词典给的标签（两本词典、所有义项合在一起；短语按短语那一块），只录标签，不录释义
RECORDED_WORDS = {
    "scull": [], "luncheon": ["formal"], "paw": ["informal"], "fling": [], "meadow": [], "hedge": ["figurative"],
    "prepared": [], "mean": ["mainly British", "dated", "US", "informal", "British English", "North American English"],
    "forbear": ["formal"], "presently": [], "interfere": ["British", "euphemistic", "British English"],
    "dwell": ["formal or literary", "figurative", "formal", "literary", "technical"],
}
RECORDED_PHRASES = {  # 短语 → (标签, 在哪个词条里找到)
    "all very well": ([], "well"), "be prepared to do": ([], "prepared"),
    "interfere with": (["British", "euphemistic"], "interfere"), "there’s no denying": ([], "deny"),
    "dwell on": ([], "dwell"), "take to": ([], "take"), "might have done": ([], "might"),
}


def recorded_entry(word, pos=None, source=None):
    w = word.strip()
    base = {"headword": w, "ipa_br": [], "ipa_br_raw": [], "pos": [], "labels": [], "senses": [], "kind": "macos",
            "notes": [], "blocks": [], "phrase": None}
    if w in RECORDED_PHRASES:
        labels, inn = RECORDED_PHRASES[w]
        return dict(base, pos=["phrase"], all_labels=labels, source="macOS（录下的标签，%s 词条）" % inn,
                    phrase={"found": True, "core": L.phrase_core(w), "in": inn, "where": "短语", "text": w, "hits": []})
    if w in RECORDED_WORDS:
        return dict(base, all_labels=RECORDED_WORDS[w], source="macOS（录下的标签）")
    return L.empty_entry(w)


class TestLabelClaims(unittest.TestCase):
    def claims(self, text, bracket_only=False):
        return [(c["fams"], c["terms"]) for c in L.find_claims(text, bracket_only)]

    def test_terms(self):
        cases = {
            "英式英语里常这样说": [(("British",), "英式")], "英国英语": [(("British",), "英国英语")],
            "美式": [(("US",), "美式")], "主要是北美用法": [(("US",), "北美")], "美国英语": [(("US",), "美国英语")],
            "很正式": [(("formal",), "正式")], "书面词": [(("formal",), "书面")],
            "旧式说法": [(("old",), "旧式")], "已经过时": [(("old",), "过时")], "老式的说法": [(("old",), "老式")],
            "口语里": [(("informal",), "口语")], "非正式": [(("informal",), "非正式")],  # 不算“正式”
            "委婉说法": [(("euphemistic",), "委婉")], "俚语": [(("slang",), "俚语")], "文学作品里": [(("literary",), "文学")],
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.claims(text), want)

    def test_negation_and_or(self):
        self.assertEqual(self.claims("这个意思不是英式用法"), [])
        self.assertEqual(self.claims("不算口语"), [])
        self.assertEqual(self.claims("不只是英式用法"), [(("British",), "英式")])  # “不只是”不是否定
        self.assertEqual(self.claims("①（正式或文学）居住", True), [(("formal", "literary"), "正式或文学")])
        self.assertEqual(self.claims("（英式，口语）", True), [(("British",), "英式"), (("informal",), "口语")])

    def test_bracket_only(self):
        self.assertEqual(self.claims("正式的；官方的", True), [])  # 释义本身，不是标签
        self.assertEqual(self.claims("午餐（正式说法）", True), [(("formal",), "正式")])
        self.assertEqual(self.claims("书面语", True), [(("formal",), "书面")])
        self.assertEqual(self.claims("正式的；官方的"), [(("formal",), "正式")])  # 首行、用法行不限括号

    def test_segments(self):
        self.assertEqual(L.split_segments("作“目前”讲主要是北美用法，英式英语多说 at present 或 currently。"),
                         ["作“目前”讲主要是北美用法", "英式英语多说 at present 或 currently"])
        self.assertEqual(L.split_segments("今天的英式英语里，interfere with sb 可指猥亵儿童；说“招惹某人”用 bother sb。"),
                         ["今天的英式英语里，interfere with sb 可指猥亵儿童", "说“招惹某人”用 bother sb"])
        self.assertEqual(L.split_segments("英式英语里 mean 常指“小气，舍不得花钱”，不只是“刻薄”。"),
                         ["英式英语里 mean 常指“小气，舍不得花钱”", "不只是“刻薄”"])

    def test_target(self):
        t = L.claim_target
        self.assertIsNone(t(lex(), "美式英语用 cheap", "mean", "mean"))
        self.assertIsNone(t(lex(), "比 mention 书面", "dwell on", "dwell"))
        self.assertIsNone(t(lex(), "英式英语多说 at present 或 currently", "presently", "presently"))
        self.assertEqual(t(lex(), "英式英语里 mean 常指“小气”", "mean", "mean"), "word")
        self.assertEqual(t(lex(), "书面词", "forbear", "forbear"), "head")
        self.assertEqual(t(lex(), "过去式 forbore 很书面", "forbear", "forbear"), "word")  # 按原形认
        self.assertEqual(t(lex(), "今天的英式英语里，interfere with sb 可指", "interfere with", "interfere"), "phrase")
        self.assertEqual(t(lex(), "dwell 作“居住”讲很书面", "dwell on", "dwell"), "word")
        self.assertEqual(t(lex(), "后面接 that 从句，很正式", "deny", "deny"), "head")  # 虚词不算

    def test_judge(self):
        j = L.judge_claim
        self.assertEqual(j(("British",), {"kind": "macos", "all_labels": ["mainly British"]})[0], "一致")
        self.assertEqual(j(("US",), {"kind": "macos", "all_labels": ["mainly British"]})[0], "缺")
        self.assertEqual(j(("US",), {"kind": "macos", "all_labels": ["North American English"]})[0], "一致")
        self.assertEqual(j(("US",), {"kind": "macos", "all_labels": ["chiefly N. Amer."]})[0], "一致")
        self.assertEqual(j(("formal",), {"kind": "macos", "all_labels": ["informal"]})[0], "缺")
        self.assertEqual(j(("informal",), {"kind": "macos", "all_labels": ["colloquial"]})[0], "一致")
        self.assertEqual(j(("formal", "literary"), {"kind": "macos", "all_labels": ["literary"]})[0], "一致")
        self.assertEqual(j(("old",), {"kind": "macos", "all_labels": ["dated"]})[0], "一致")
        self.assertEqual(j(("euphemistic",), {"kind": "macos", "all_labels": ["British", "euphemistic"]})[0], "一致")
        self.assertEqual(j(("slang",), {"kind": "wiktionary", "all_labels": []})[0], "未核对")
        self.assertEqual(j(("slang",), {"kind": "wiktionary", "all_labels": ["slang"]})[0], "一致")
        self.assertEqual(j(("formal",), {"kind": "ecdict", "all_labels": []})[0], "未核对")
        self.assertEqual(j(("formal",), L.empty_entry("x"))[0], "未核对")

    def recorded_rows(self, md):
        with mock.patch.object(lex(), "entry", side_effect=recorded_entry):
            return L.check_rows(lex(), L.parse_lecture(md), "B1")

    def test_demo_ch1_recorded(self):
        rows = self.recorded_rows(DEMO_CH1)
        by = {r["word"]: r for r in rows}
        self.assertEqual([r["word"] for r in rows if r["label_claims"]],
                         ["luncheon", "all very well", "mean", "forbear", "presently", "interfere", "dwell"])
        self.assertEqual([r["word"] for r in rows if "标签" in r["flags"]], ["all very well", "presently"])
        self.assertFalse([r for r in rows if r["marks"]])
        note = next(n for n in by["presently"]["notes"] if n.startswith("!标签"))
        self.assertTrue(note.startswith("!标签：讲义（首行、词典行）说「北美」，词典没有 US、North American 一类的标签"), note)
        self.assertIn("词典的标签：无", note)
        self.assertIn("来源 macOS（录下的标签）", note)
        note = next(n for n in by["all very well"]["notes"] if n.startswith("!标签"))
        self.assertIn("讲义（词典行）说「口语」", note)
        self.assertIn("来源 macOS（录下的标签，well 词条）", note)
        # mean 的“美式英语用 cheap”“stingy（口语）”说的是别的词；interfere with 按短语那一块核对（British、euphemistic）
        self.assertNotIn("标签", by["mean"]["flags"])
        self.assertNotIn("标签", by["interfere"]["flags"])
        out = io.StringIO()
        with redirect_stdout(out):
            L.print_check(rows, "B1", "第01章.md", "")
        self.assertIn("标 ! 的 3 行。标签说法：讲义写了的 7 行，!标签 2 条，标签未核对 0 条。", out.getvalue())
        self.assertIn("| **!掌握/标签** | 词的用法 | presently |", out.getvalue())

    def test_phrase_headword_without_phrase_entry(self):
        md = "## 词的用法\n\n- **dwell on**：今天的英式英语里，dwell on 很常见。\n  词典：dwell /dwel/ vi. 居住\n  掌握：会用\n"

        def no_phrase(word, pos=None, source=None):
            return L.empty_entry(word) if " " in word else recorded_entry(word, pos, source)
        with mock.patch.object(lex(), "entry", side_effect=no_phrase):
            row, = L.check_rows(lex(), L.parse_lecture(md), "B1")
        self.assertEqual(row["marks"], ["标签未核对"])
        self.assertTrue(any("词典里没找到短语 dwell on" in n for n in row["notes"]))

    def test_demo_ch2_recorded(self):
        rows = self.recorded_rows(DEMO_CH2)
        self.assertFalse([r for r in rows if r["label_claims"]])


class TestNoScraping(unittest.TestCase):
    def test_no_oxford_site_or_browser_ua(self):
        for p in [SCRIPTS / "lexicon.py", SCRIPTS / "profile.py"] + sorted((SCRIPTS / "data").glob("*.py")):
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertNotIn("oxfordlearnersdictionaries", text)
                self.assertNotIn("BROWSER_UA", text)
        self.assertFalse((SCRIPTS / "oxford.py").exists())


if __name__ == "__main__":
    unittest.main()
