"""build.py 的 check、md（PDF 部分的测试在 test_pdf.py）。在 skill 根目录运行：python3 -m unittest discover -s tests

夹具（fixtures/）：
  原文.txt                   demo 第 1 章的原文（每个测试项目里各单元的原文都用它）
  精读.md                    第一版 demo 的第 1 章讲义（精读，没有读前）
  轻读.md                    按第二版写的轻读单元，完全合规；引文都出自 原文.txt
  前言.md                    第一版 demo 的前言
  合订_精读两章_第一版.md     第一版 build.py 对「两章都是 精读.md」的项目生成的 讲义.md，用来比对逐字节相同
每条新规则一个反例：在合规的夹具上改一处，确认 check 报出对应的提示。
check 的结果分「问题」（计数、决定退出码）和「提示」（以「提示 」开头的行，不计数）。轻读夹具在 B1 读者下有 3 条提示
（bank、fellow 不高于 B1，复述参考里的 meadow 高于 B1），问题是 0 个。
"""
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
INTENSIVE = (FIX / "精读.md").read_text(encoding="utf-8")
LIGHT = (FIX / "轻读.md").read_text(encoding="utf-8")
PREFACE = (FIX / "前言.md").read_text(encoding="utf-8")
PAD = "这一句只是为了把长度撑过上限"            # 撑长度用
FORMAL_ROW = "| 形式主语 | it 先占住主语的位置，真主语放在后面 | **It** is hard **to say no**. |\n"
PREFACE_FORMAL = PREFACE.replace("| 被动 |", FORMAL_ROW + "| 被动 |", 1)     # 前言的术语表补上轻读夹具用到的「形式主语」


def sub(text, old, new="", count=1):
    """把 old 换成 new；old 必须在 text 里（夹具改了而测试没跟上时立刻报错）。"""
    assert old in text, f"夹具里找不到：{old[:40]}"
    return text.replace(old, new, count)


def section(text, name):
    """「## name」一节（含标题行，到下一个「## 」或文件末尾）。"""
    m = re.search(rf"^## {re.escape(name)}\n.*?(?=^## |\Z)", text, flags=re.M | re.S)
    assert m, f"没有「## {name}」"
    return m.group(0)


def move_before(text, name, before):
    """把「## name」一节挪到「## before」前面。"""
    s = section(text, name)
    text = text.replace(s, "")
    return sub(text, f"## {before}\n", s + f"## {before}\n")


def with_review(text, n):
    """精读讲义的最后两道自测题改成「回头看（第 n 章）：…」。"""
    text = sub(text, "9. 翻译：不可否认", f"9. 回头看（第 {n} 章）：翻译：不可否认")
    return sub(text, "10. 河鼠的船撞上岸以后", f"10. 回头看（第 {n} 章）：河鼠的船撞上岸以后")


def first_banned():
    """禁用语.txt 里第一个不是正则的说法。"""
    for line in (SKILL / "reference" / "禁用语.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and not line.startswith("re:"):
            return line.split("\t")[0]
    raise AssertionError("禁用语.txt 里没有字面说法")


# 短文里另加的几段（按段首认）：让轻读夹具的每个读前词在短文里也出现 2 次（短文的门槛，rules.json 的 profile.preread_min_count）
SHORT_EXTRA = ("The River Bank", "A broad glistening muzzle", "When the Rat had rubbed him down", "The Badger trotted forward",
               "“Well, well,” said the Rat, “I suppose", "The afternoon sun was getting low")


def short_source():
    """短文（不足 1,200 词）：原文里含有轻读夹具引文的段落，加上 SHORT_EXTRA 那几段，按原顺序。"""
    quotes = re.findall(r"^> (.+)$", LIGHT, flags=re.M) + re.findall(r"原文：\*(.+?)\*\s*$", LIGHT, flags=re.M)
    paras = [p for p in SOURCE.split("\n\n") if any(q in re.sub(r"\s+", " ", p) for q in quotes) or p.startswith(SHORT_EXTRA)]
    return "\n\n".join(paras) + "\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "项目"

    def tearDown(self):
        self.tmp.cleanup()

    def project(self, units, default_mode=None, preface=None, source=SOURCE, extra=None):
        """units：[(单元号, 讲义, mode 或 None, 标题)]。default_mode=None 时 设置.json 里不写这个键（第一版的写法）。"""
        (self.root / "原文").mkdir(parents=True, exist_ok=True)
        (self.root / "讲义").mkdir(parents=True, exist_ok=True)
        cfg = {"title": "The Wind in the Willows", "author": "Kenneth Grahame", "unit": "章", "units": [],
               "level": "B1", "genre": "小说", "appreciation": True, "writing": True, "fonts": None}
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

    def run_build(self, cmd, *args):
        r = subprocess.run([sys.executable, str(BUILD), cmd, str(self.root), *args], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def check(self):
        code, out = self.run_build("check")
        m = re.search(r"问题 (\d+) 个", out)
        self.assertIsNotNone(m, out)
        return int(m.group(1)), out

    def assertClean(self):
        n, out = self.check()
        self.assertEqual(n, 0, out)

    def assertReports(self, *fragments, count=None):
        n, out = self.check()
        for f in fragments:
            self.assertIn(f, out)
        if count is not None:
            self.assertEqual(n, count, out)
        return out

    def assertHints(self, *fragments, absent=()):
        """问题 0 个；提示里有 fragments，没有 absent。返回输出。"""
        n, out = self.check()
        self.assertEqual(n, 0, out)
        hints = "\n".join(l for l in out.splitlines() if l.startswith("提示 "))
        for f in fragments:
            self.assertIn(f, hints, out)
        for f in absent:
            self.assertNotIn(f, out)
        return out


class LightCase(Base):
    """单个轻读单元（default_mode = 轻读）。"""
    def light(self, text, source=SOURCE):
        self.project([(1, text, None, "The River Bank")], default_mode="轻读", source=source)


# ---------- 设置 ----------

class TestSettings(Base):
    def test_no_default_mode_means_intensive(self):
        self.project([(1, LIGHT, None, "")])          # 没有 default_mode 键：按精读查，轻读的讲义就缺精读的栏目
        self.assertReports("缺少「## 自测」", "需要恰好一个「## 语法：…」")

    def test_default_mode_light(self):
        self.project([(1, LIGHT, None, "")], default_mode="轻读")
        self.assertClean()

    def test_unit_mode_overrides_default(self):
        self.project([(1, LIGHT, "轻读", ""), (2, INTENSIVE, None, "")], default_mode="精读")
        self.assertClean()
        self.project([(1, INTENSIVE, "精读", ""), (2, LIGHT, None, "")], default_mode="轻读")
        self.assertClean()

    def test_plain_int_units_use_default(self):
        self.project([(1, LIGHT, None, "")], default_mode="轻读", extra={"units": [1]})
        self.assertClean()

    def test_bad_default_mode(self):
        self.project([(1, LIGHT, None, "")], default_mode="泛读")
        code, out = self.run_build("check")
        self.assertNotEqual(code, 0)
        self.assertIn("default_mode 只能是 轻读 / 精读，不是「泛读」", out)

    def test_bad_unit_mode(self):
        self.project([(1, LIGHT, "细读", "")])
        code, out = self.run_build("check")
        self.assertNotEqual(code, 0)
        self.assertIn("第 1 章的 mode 只能是 轻读 / 精读，不是「细读」", out)


# ---------- 轻读：合规的夹具 ----------

class TestLightOK(LightCase):
    def test_fixture_is_clean(self):
        self.light(LIGHT)
        self.assertClean()

    def test_extra_sentences_not_counted(self):
        # 补充句自成一套编号，不占长难句的数量：长文长难句定为 2 句，这里 2 句长难句 + 3 句补充句也不报
        extra = section(LIGHT, "补充句")
        one = extra.split("\n", 1)[1]
        text = LIGHT + one.replace("### 1.", "### 2.") + one.replace("### 1.", "### 3.")
        self.light(text)
        self.assertClean()

    def test_short_text_tier(self):
        src = short_source()
        words = sum(1 for t in src.split() if re.search(r"[A-Za-z]", t))
        self.assertLess(words, 1200)
        self.light(LIGHT, source=src)       # 长文的数量放到短文里：读前词 6 > 5，理解 3 > 2，词条 4 > 3
        self.assertReports(f"读前的词需要 3–5 个（原文 {words} 词），现在 6 个",
                           f"理解需要 2 题（原文 {words} 词），现在 3 题",
                           f"词汇用法需要 3 条（原文 {words} 词），现在 4 条", count=3)
        text = sub(LIGHT, "- **row** /rəʊ/ v. 划船\n")
        text = sub(text, "3. 船翻以后鼹鼠道歉，河鼠为什么说 What’s a little wet to a Water Rat?\n")
        text = sub(text, "3. 他不想让鼹鼠难堪，把落水说成小事一桩，好让鼹鼠宽心。\n   原文：*What’s a little wet to a Water Rat?*\n"
                         "   译：一点水对河鼠算得了什么？\n")
        text = sub(text, text[text.index("- **there’s no denying**"):text.index("## 复述")], "\n")
        self.light(text, source=src)
        self.assertClean()


# ---------- 轻读：每条规则一个反例 ----------

class TestLightStructure(LightCase):
    def test_missing_section(self):
        self.light(LIGHT.replace(section(LIGHT, "复述"), ""))
        self.assertReports("缺少「## 复述」")

    def test_section_order(self):
        self.light(move_before(LIGHT, "长难句", "理解"))
        self.assertReports("小节顺序不对：应为读前、理解、长难句、词的用法、复述，补充句放在最后")

    def test_extra_must_be_last(self):
        self.light(move_before(LIGHT, "补充句", "复述"))
        self.assertReports("小节顺序不对")

    def test_unknown_section(self):
        self.light(LIGHT + "\n## 自测\n\n1. 题\n\n**答案**\n\n1. 答\n")
        self.assertReports("不认识的小节「## 自测」")

    def test_duplicate_section(self):
        self.light(LIGHT + "\n" + section(LIGHT, "复述"))
        self.assertReports("「## 复述」只能有一个")


class TestPreread(LightCase):
    BG = "《柳林风声》1908 年在英国出版，写河边几只小动物的日子。他们像当年英国乡间的绅士一样过日子：划船、野餐、串门。spring-cleaning 是英国人家每年春天的大扫除。"

    def test_background_missing(self):
        self.light(sub(LIGHT, self.BG + "\n\n"))
        self.assertReports("读前缺少背景")

    def test_background_one_paragraph(self):
        self.light(sub(LIGHT, self.BG, self.BG + "\n\n第二段背景。"))
        self.assertReports("读前的背景只写一段，现在 2 段")

    def test_background_length(self):
        self.light(sub(LIGHT, self.BG, self.BG + PAD * 3))
        self.assertReports("读前 背景：", "读前背景上限 120")

    def test_people_count(self):
        more = "".join(f"- **Animal {k}**：别的动物\n" for k in range(2))
        self.light(sub(LIGHT, "- **the Badger**：獾，住在野树林深处\n", "- **the Badger**：獾，住在野树林深处\n" + more))
        self.assertReports("读前的人物最多 5 个（原文", "现在 6 个")

    def test_person_length(self):
        self.light(sub(LIGHT, "獾，住在野树林深处", "獾，住在野树林深处，不爱见生人，也不爱热闹，朋友们都有点怕他"))
        self.assertReports("读前 人物 the Badger：", "读前人物（每条）上限 25")

    def test_person_format(self):
        self.light(sub(LIGHT, "- **the Otter**：水獭，河鼠的熟人", "- the Otter：水獭，河鼠的熟人"))
        self.assertReports("读前的人物要写成「- **人名**：身份」")

    def test_words_heading_missing(self):
        self.light(sub(LIGHT, "### 本章的词\n\n"))
        self.assertReports("读前缺少「### 本章的词」")

    def test_word_line_format(self):
        self.light(sub(LIGHT, "- **bank** /bæŋk/ n. 河岸", "- **bank**：河岸"))
        self.assertReports("读前的词要写成「- **word** /音标/ 词性. 释义」")

    def test_word_needs_ipa(self):
        self.light(sub(LIGHT, "- **bank** /bæŋk/ n. 河岸", "- **bank** n. 河岸"))
        self.assertReports("读前的词「bank」：要写音标")

    def test_phrase_no_ipa(self):
        self.light(sub(LIGHT, "- **bank** /bæŋk/ n. 河岸", "- **bank** /bæŋk/ phr. 河岸"))
        self.assertReports("读前的词「bank」：短语不写音标")

    def test_word_pos(self):
        self.light(sub(LIGHT, "- **bank** /bæŋk/ n. 河岸", "- **bank** /bæŋk/ noun. 河岸"))
        self.assertReports("读前的词「bank」：词性只用")

    def test_word_count(self):
        self.light(sub(sub(LIGHT, "- **row** /rəʊ/ v. 划船\n"), "- **fellow** /ˈfeləʊ/ n. 家伙，伙计\n"))
        self.assertReports("读前的词需要 5–8 个（原文", "现在 4 个")

    def test_word_gloss_length(self):
        self.light(sub(LIGHT, "n. 家伙，伙计", "n. 家伙，伙计；朋友之间的随便叫法，也可以指人"))
        self.assertReports("读前词 fellow：", "读前词释义上限 15")

    def test_word_duplicates_usage(self):
        self.light(sub(LIGHT, "- **row** /rəʊ/ v. 划船\n", "- **row** /rəʊ/ v. 划船\n- **forbear** /fɔːˈbeə/ v. 忍住不做\n"))
        self.assertReports("读前的词「forbear」又写成了词条「forbear」")

    def test_word_duplicates_usage_dict_head(self):
        text = sub(LIGHT, "- **forbear**：forbear to do", "- **forbear to do**：forbear to do")
        text = sub(text, "词典：/fɔːˈbeə/", "词典：forbear /fɔːˈbeə/")
        text = sub(text, "- **row** /rəʊ/ v. 划船\n", "- **row** /rəʊ/ v. 划船\n- **forbear** /fɔːˈbeə/ v. 忍住不做\n")
        self.light(text)
        self.assertReports("读前的词「forbear」又写成了词条「forbear to do」")

    def test_word_listed_twice(self):
        self.light(sub(LIGHT, "- **row** /rəʊ/ v. 划船\n", "- **row** /rəʊ/ v. 划船\n- **Bank** /bæŋk/ n. 银行\n"))
        self.assertReports("读前的词「Bank」列了两次")

    def test_word_listed_in_earlier_unit(self):
        self.project([(1, LIGHT, None, ""), (2, LIGHT, None, "")], default_mode="轻读")
        self.assertReports("第 2 章 格式：读前的词「scull」在第 1 章的读前已经列过")


class TestComprehension(LightCase):
    A1 = ("1. 春天的气息钻进了他的地下小屋，他再也待不住，大扫除也不想做了。\n"
          "   原文：*Spring was moving in the air above and in the earth below and around him*\n"
          "   译：春意在上面的空气里涌动，也在他身下和四周的泥土里涌动\n")

    def test_count(self):
        text = sub(LIGHT, "2. 河鼠说起野树林里的居民时，口气有什么变化？说明了什么？\n")
        text = sub(text, "3. 船翻以后鼹鼠道歉，河鼠为什么说 What’s a little wet to a Water Rat?\n")
        text = sub(text, text[text.index("2. 说到松鼠"):text.index("## 长难句")], "\n")
        self.light(text)
        self.assertReports("理解需要 2–3 题（原文", "现在 1 题")

    def test_answers_marker(self):
        self.light(sub(LIGHT, "**答案**\n"))
        self.assertReports("理解缺少「**答案**」")

    def test_question_answer_mismatch(self):
        self.light(sub(LIGHT, "3. 船翻以后鼹鼠道歉，河鼠为什么说 What’s a little wet to a Water Rat?\n"))
        self.assertReports("理解题和答案数量不一致")

    def test_answer_needs_one_quote(self):
        self.light(sub(LIGHT, self.A1, "1. 春天的气息钻进了他的地下小屋，他再也待不住，大扫除也不想做了。\n"))
        self.assertReports("理解答案 1：要有 1 处「原文：*…*」，现在 0 处")

    def test_answer_needs_text(self):
        self.light(sub(LIGHT, "1. 春天的气息钻进了他的地下小屋，他再也待不住，大扫除也不想做了。\n", "1. \n"))
        self.assertReports("理解答案 1：先用一两句中文回答")

    def test_question_length(self):
        self.light(sub(LIGHT, "1. 鼹鼠为什么扔下刷子跑出了家门？",
                       "1. 鼹鼠本来在家里忙着春季大扫除，刷了一上午的墙，为什么突然扔下刷子、连外套都没穿就跑出了家门？他当时心里在想什么？" + PAD * 2))
        self.assertReports("理解 1：", "理解题上限 60")

    def test_answer_length(self):
        self.light(sub(LIGHT, "大扫除也不想做了。", "大扫除也不想做了。" + "外面的鸟叫、花开和阳光都在召唤他，地下的小屋一下子显得又暗又闷。" * 4))
        self.assertReports("理解答案 1：", "理解答案上限 120")

    def test_quote_word_limit(self):
        long = ("Green turf sloped down to either edge, brown snaky tree-roots gleamed below the surface of the quiet water, "
                "while ahead of them the silvery shoulder and foamy tumble of a weir, arm-in-arm with a restless dripping "
                "mill-wheel, that held up in its turn a grey-gabled millhouse, filled the air with a soothing murmur of sound")
        self.light(sub(LIGHT, "*Spring was moving in the air above and in the earth below and around him*", f"*{long}*"))
        self.assertReports("理解答案 1 原文：", "理解引文上限 40 词")

    def test_translation_right_after_quote(self):
        self.light(sub(LIGHT, "around him*\n   译：", "around him*\n\n   译："))
        self.assertReports("理解：原文「Spring was moving in the」下一行缺少「译：」")


class TestLightSentences(LightCase):
    def test_no_pattern_label(self):
        self.light(sub(LIGHT, "- **背景**：前一句", "- **句型**：`It is against … to do.`\n- **背景**：前一句"))
        self.assertReports("句 2：轻读的长难句只许主干、怎么拆、卡点、译、背景，不写「句型」")

    def test_needs_crux(self):
        self.light(sub(LIGHT, "- **卡点**：`it is quite against", "- **背景**：`it is quite against"))
        self.assertReports("句 2：缺少「卡点」")

    def test_needs_core(self):
        self.light(sub(LIGHT, "- **主干**：It was small wonder that he flung down his brush and bolted out of the house.\n"))
        self.assertReports("句 1：缺少「主干」")

    def test_split_steps_at_most_three(self):
        self.light(sub(LIGHT, "flung down、said、bolted out。\n",
                       "flung down、said、bolted out。\n  3. 第三步。\n  4. 第四步。\n"))
        self.assertReports("句 1：「怎么拆」写 1–3 步，现在 4 步")

    def test_count(self):
        s2 = LIGHT[LIGHT.index("### 2. it is against"):LIGHT.index("## 词的用法")]
        self.light(sub(LIGHT, s2))
        self.assertReports("长难句需要 2 句（原文", "现在 1 句")

    def test_order(self):
        s1 = LIGHT[LIGHT.index("### 1. small wonder"):LIGHT.index("### 2. it is against")]
        s2 = LIGHT[LIGHT.index("### 2. it is against"):LIGHT.index("## 词的用法")]
        swapped = s2.replace("### 2.", "### 1.").rstrip("\n") + "\n\n" + s1.replace("### 1.", "### 2.")
        self.light(sub(LIGHT, s1 + s2, swapped))
        self.assertReports("长难句未按原文出现顺序排列")

    def test_numbering(self):
        self.light(sub(LIGHT, "### 2. it is against", "### 3. it is against"))
        self.assertReports("长难句编号不连续")


class TestLightUsage(LightCase):
    def test_at_most_one_usage_line(self):
        self.light(sub(LIGHT, "  例：She has taken to walking to work.\n",
                       "  例：She has taken to walking to work.\n  辨析：tire of sth 是“厌倦”。\n"))
        self.assertReports("词条 take to：轻读的词条用法写 0–1 行（搭配、辨析、词族、例、注意选一种），现在 2 行")

    def test_needs_level(self):
        self.light(sub(LIGHT, "  掌握：认得\n"))
        self.assertReports("词条 forbear：缺少「掌握：会用」或「掌握：认得」")

    def test_needs_dict(self):
        self.light(sub(LIGHT, "  词典：phr. 朝……走去\n"))
        self.assertReports("词条 make for：需要词典和原文引文")

    def test_needs_quote(self):
        self.light(sub(LIGHT, "  原文：*he made for the steep little tunnel*\n  译：他朝那条又陡又小的隧道奔去\n"))
        self.assertReports("词条 make for：需要词典和原文引文")

    def test_count(self):
        self.light(sub(LIGHT, LIGHT[LIGHT.index("- **forbear**"):LIGHT.index("## 复述")], "\n"))
        self.assertReports("词汇用法需要 3–4 条（原文", "现在 2 条")


class TestRetell(LightCase):
    PROMPT = "用 5–8 句英文复述鼹鼠这一天在河上的经历，提示词：scull, bank, trot, take to"

    def test_needs_hints(self):
        self.light(sub(LIGHT, self.PROMPT, "用 5–8 句英文复述鼹鼠这一天在河上的经历。"))
        self.assertReports("复述缺少「提示词：…」")

    def test_needs_reference(self):
        ref = section(LIGHT, "复述").split("参考：", 1)[1].split("\n", 1)[0]
        self.light(sub(LIGHT, "参考：" + ref + "\n"))
        self.assertReports("复述缺少「参考：…」")

    def test_hint_count(self):
        self.light(sub(LIGHT, "提示词：scull, bank, trot, take to", "提示词：scull, bank"))
        self.assertReports("复述的提示词要 3–5 个，现在 2 个")

    def test_hint_from_vocab(self):
        self.light(sub(LIGHT, "提示词：scull, bank, trot, take to", "提示词：scull, bank, meadow, take to"))
        self.assertReports("复述的提示词「meadow」不在本章的读前词和词条里")

    def test_question_length(self):
        self.light(sub(LIGHT, "用 5–8 句英文复述鼹鼠这一天在河上的经历",
                       "用 5–8 句英文复述鼹鼠这一天在河上的经历：他怎么离开家，怎么认识河鼠，船怎么翻的，最后又怎么住进了河鼠的家，"
                       "每句话尽量用上一个本章学过的词，写完再对照参考" + PAD * 2))
        self.assertReports("复述：", "复述题上限 80")

    def test_reference_word_limit(self):
        self.light(sub(LIGHT, "on the river.\n", "on the river. " + "The river is his new friend, and every day is full of fun. " * 3 + "\n"))
        self.assertReports("复述 参考：", "复述参考上限 100 词")


class TestExtra(LightCase):
    EXTRA = section(LIGHT, "补充句")

    def test_numbering(self):
        self.light(sub(LIGHT, "### 1. he being new", "### 3. he being new"))
        self.assertReports("补充句编号不连续")

    def test_labels(self):
        self.light(sub(LIGHT, "- **译**：“哼，你说得倒轻巧。”",
                       "- **延伸**：独立结构偏书面。\n- **译**：“哼，你说得倒轻巧。”"))
        self.assertReports("补充句 1：补充句只许主干、怎么拆、卡点、译、背景，不写「延伸」")

    def test_needs_crux(self):
        self.light(sub(LIGHT, "- **卡点**：`he being new to a river`", "- **背景**：`he being new to a river`"))
        self.assertReports("补充句 1：缺少「卡点」")

    def test_order(self):
        later = ("### 1. 后面的一句\n\n> The Mole knew well that it is quite against animal-etiquette to dwell on possible trouble "
                 "ahead, or even to allude to it; so he dropped the subject.\n\n- **主干**：The Mole knew.\n- **卡点**：it 指后面。\n"
                 "- **译**：鼹鼠很清楚。\n\n")
        body = self.EXTRA.split("\n", 1)[1].replace("### 1.", "### 2.")
        self.light(sub(LIGHT, self.EXTRA, "## 补充句\n\n" + later + body.lstrip("\n")))
        self.assertReports("补充句未按原文出现顺序排列")


# ---------- 两种模式共用的规则 ----------

class TestShared(LightCase):
    def test_quote_must_be_in_source(self):
        self.light(sub(LIGHT, "*explained the Rat in a hesitating sort of way*", "*explained the Rat in a hesitant sort of way*"))
        self.assertReports("引文原文里找不到：explained the Rat in a hesitant sort of way")

    def test_cite_needs_stars(self):
        self.light(sub(LIGHT, "原文：*explained the Rat in a hesitating sort of way*", "原文：explained the Rat in a hesitating sort of way"))
        self.assertReports("理解：「原文：」后面的引文要写成 *…*")

    def test_blockquote_needs_translation(self):
        self.light(sub(LIGHT, "### 本章的词", "> A brown little face, with whiskers.\n\n### 本章的词"))
        self.assertReports("读前：引文后面缺少「译：」")

    def test_straight_quotes(self):
        self.light(sub(LIGHT, "The Mole stops his spring-cleaning", "The Mole won't do his spring-cleaning"))
        self.assertReports("复述 参考：", "里有 ASCII 引号，改成弯引号")

    def test_star_inside_bold(self):
        self.light(sub(LIGHT, "- **the Otter**：", "- **the *Otter***："))
        self.assertReports("粗体里有星号")

    def test_banned_in_prose(self):
        w = first_banned()
        self.light(sub(LIGHT, "- **卡点**：`small wonder` 不是", f"- **卡点**：{w}，`small wonder` 不是"))
        self.assertReports(f"句 1 卡点「{w}」")

    def test_banned_not_checked_in_translations(self):
        w = first_banned()
        text = sub(LIGHT, "- **译**：所以难怪", f"- **译**：{w}，所以难怪")                     # 长难句的译
        text = sub(text, "   译：河鼠吞吞吐吐地解释道", f"   译：河鼠吞吞吐吐地解释道，{w}")          # 理解答案的译
        text = sub(text, "  译：他朝那条又陡又小的隧道奔去", f"  译：他朝那条又陡又小的隧道奔去，{w}")  # 词条的译
        self.light(text)
        self.assertClean()

    def test_term_table(self):
        self.light(sub(LIGHT, "不是指前面说的事。", "不是指前面说的事。这里是反讽（irony）。"))
        self.assertReports("术语表里 irony 叫「讽刺」")

    def test_term_clash_across_units(self):
        light = sub(LIGHT, "不是指前面说的事。", "不是指前面说的事。苇秆（reed-stems）。")
        self.project([(1, INTENSIVE, "精读", ""), (2, light, "轻读", "")])
        self.assertReports("全部单元 术语：（reed-stems）前面用了不同的中文名：「芦苇」")


# ---------- 精读 ----------

class TestIntensive(Base):
    def intensive(self, text):
        self.project([(1, text, None, "The River Bank")])     # 没有 default_mode：按精读（第一版的项目）

    def test_v1_demo_clean(self):
        self.intensive(INTENSIVE)
        self.assertClean()

    def test_preread_and_extra(self):
        text = sub(INTENSIVE, "## 长难句\n", section(LIGHT, "读前") + "## 长难句\n", 1)
        self.intensive(text.rstrip("\n") + "\n\n" + section(LIGHT, "补充句"))
        self.assertClean()

    def test_preread_must_be_first(self):
        self.intensive(sub(INTENSIVE, "## 词的用法\n", section(LIGHT, "读前") + "## 词的用法\n"))
        self.assertReports("「## 读前」要放在最前面")

    def test_preread_rules_apply(self):
        pre = sub(sub(section(LIGHT, "读前"), "- **row** /rəʊ/ v. 划船\n"), "- **fellow** /ˈfeləʊ/ n. 家伙，伙计\n")
        self.intensive(sub(INTENSIVE, "## 长难句\n", pre + "## 长难句\n", 1))
        self.assertReports("读前的词需要 5–8 个（原文", "现在 4 个")

    def test_preread_vs_usage(self):
        pre = sub(section(LIGHT, "读前"), "- **row** /rəʊ/ v. 划船\n", "- **row** /rəʊ/ v. 划船\n- **dwell** /dwel/ v. 老想着\n")
        self.intensive(sub(INTENSIVE, "## 长难句\n", pre + "## 长难句\n", 1))
        self.assertReports("读前的词「dwell」又写成了词条「dwell on」")

    def test_extra_must_be_last(self):
        self.intensive(sub(INTENSIVE, "## 词的用法\n", section(LIGHT, "补充句") + "\n## 词的用法\n"))
        self.assertReports("「## 补充句」要放在最后")

    def test_extra_uses_light_labels(self):
        extra = sub(section(LIGHT, "补充句"), "- **译**：“哼", "- **句型**：`be new to sth`\n- **译**：“哼")
        self.intensive(INTENSIVE.rstrip("\n") + "\n\n" + extra)
        self.assertReports("补充句 1：补充句只许主干、怎么拆、卡点、译、背景，不写「句型」")

    def test_still_needs_split(self):
        steps = INTENSIVE[INTENSIVE.index("- **怎么拆**：\n  1. `and` 前后"):INTENSIVE.index("- **卡点**：`answered to`")]
        self.intensive(sub(INTENSIVE, steps))
        self.assertReports("句 1：缺少「怎么拆」", count=1)

    def test_extension_and_appreciation_optional(self):
        text = sub(INTENSIVE, INTENSIVE[INTENSIVE.index("- **延伸**：名词后面"):INTENSIVE.index("- **赏析**：一条鼹鼠")])
        text = sub(text, text[text.index("- **赏析**：本章开头鼹鼠"):text.index("### 3. not so much")])
        self.intensive(text)
        self.assertClean()

    def essay_points(self, keep):
        """赏析只留前 keep 个点。"""
        ess = section(INTENSIVE, "赏析")
        points = re.split(r"(?=^### )", ess, flags=re.M)
        return sub(INTENSIVE, ess, "".join(points[:1 + keep]))

    def test_essay_lower_bound_relaxed(self):
        self.intensive(self.essay_points(3))
        self.assertClean()
        self.intensive(self.essay_points(2))
        self.assertReports("赏析需要 3–7 个有引文的分析点（原文", "现在 2 个", count=1)

    def quiz(self, k):
        """自测只留前 k 题和对应答案。"""
        q = section(INTENSIVE, "自测")
        qs, ans = q.split("**答案**")
        keep = lambda part: "\n".join(l for l in part.splitlines() if not re.match(r"(\d+)\. ", l) or int(l.split(".")[0]) <= k)
        return sub(INTENSIVE, q, keep(qs) + "**答案**" + keep(ans) + "\n")

    def test_quiz_lower_bound_relaxed(self):
        self.intensive(self.quiz(5))
        self.assertClean()
        self.intensive(self.quiz(4))
        self.assertReports("自测需要 5–11 题（原文", "现在 4 题", count=1)

    def test_banned_in_translation_and_prose(self):
        w = first_banned()
        self.intensive(sub(INTENSIVE, "- **译**：说到底，", f"- **译**：{w}，说到底，"))
        self.assertClean()
        self.intensive(sub(INTENSIVE, "- **卡点**：`not so much A as B`", f"- **卡点**：{w}，`not so much A as B`"))
        self.assertReports(f"句 3 卡点「{w}」", count=1)


# ---------- 混用和回头看 ----------

class TestMixed(Base):
    def test_mixed_check_and_md(self):
        # 轻读夹具的句 1 用了「形式主语」，第一版的前言表里没有（语法术语的检查见 TestGrammarTerms），这里补上
        self.project([(1, INTENSIVE, "精读", "The River Bank"), (2, LIGHT, None, "The Open Road")],
                     default_mode="轻读", preface=PREFACE_FORMAL)
        self.assertClean()
        code, out = self.run_build("md")
        self.assertEqual(code, 0, out)
        md = (self.root / "成品" / "讲义-全本.md").read_text(encoding="utf-8")
        self.assertIn("- [第 1 章　分词短语，先找它挂在谁身上](#ch1)\n- [第 2 章　The Open Road](#ch2)\n", md)
        self.assertIn('<a id="ch2"></a>\n\n## 第 2 章\n\n### 读前\n', md)

    def test_md_light_without_title(self):
        self.project([(1, INTENSIVE, "精读", "The River Bank"), (2, LIGHT, "轻读", "")])
        code, out = self.run_build("md")
        self.assertEqual(code, 0, out)
        self.assertIn("- [第 2 章](#ch2)\n", (self.root / "成品" / "讲义-全本.md").read_text(encoding="utf-8"))

    def test_first_intensive_unit_needs_no_review(self):
        # 第 2 章是第一个精读单元：不要求回头看（第一版会要求第 2 章起都要）
        self.project([(1, LIGHT, "轻读", ""), (2, INTENSIVE, "精读", "")])
        self.assertClean()

    def test_first_intensive_unit_must_not_review(self):
        self.project([(1, LIGHT, "轻读", ""), (2, with_review(INTENSIVE, 1), "精读", "")])
        self.assertReports("第 2 章的自测不要回头看题", "回头看要指前面的精读章，第 1 章是轻读")

    def test_later_intensive_unit_needs_review(self):
        self.project([(1, INTENSIVE, "精读", ""), (2, LIGHT, "轻读", ""), (3, INTENSIVE, "精读", "")])
        self.assertReports("第 3 章 格式：自测最后两题（且只有这两题）要以「回头看（第 N 章）：」开头", count=1)

    def test_review_of_earlier_intensive_unit(self):
        self.project([(1, INTENSIVE, "精读", ""), (2, LIGHT, "轻读", ""), (3, with_review(INTENSIVE, 1), "精读", "")])
        self.assertClean()

    def test_review_must_not_point_to_light_unit(self):
        self.project([(1, INTENSIVE, "精读", ""), (2, LIGHT, "轻读", ""), (3, with_review(INTENSIVE, 2), "精读", "")])
        self.assertReports("回头看要指前面的精读章，第 2 章是轻读", count=2)

    def test_review_must_point_backwards(self):
        self.project([(1, INTENSIVE, "精读", ""), (2, with_review(INTENSIVE, 2), "精读", "")])
        self.assertReports("回头看要指前面的章（章号小于 2）", count=2)


# ---------- 问题和提示 ----------

ROW = "- **row** /rəʊ/ v. 划船\n"          # 轻读夹具读前的最后一个词；在它后面加词


def add_preread(text, *lines):
    return sub(text, ROW, ROW + "".join(lines))


class TestHints(Base):
    def test_hints_listed_not_counted(self):
        self.project([(1, LIGHT, None, "")], default_mode="轻读")
        code, out = self.run_build("check")
        self.assertEqual(code, 0, out)
        self.assertIn("核对引文 10 处，问题 0 个\n提示 3 个（估计出来的，逐条看，有理由不改的在 制作记录/计划与检查.md 记一句）\n", out)
        lines = [l for l in out.splitlines() if l.startswith("提示 第 1 章 ")]
        self.assertEqual(len(lines), 3, out)
        self.assertIn("提示 第 1 章 读前：读前词 bank（A1）不高于读者水平 B1", lines)
        self.assertLess(out.index("提示 第 1 章"), out.index("核对引文"))

    def test_hint_line_after_problem_breakdown(self):
        self.project([(1, sub(LIGHT, "hesitating sort of way*", "hesitant sort of way*"), None, "")], default_mode="轻读")
        code, out = self.run_build("check")
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"问题 1 个\n  其中 格式和引文 1，[^\n]*，语法术语 0\n提示 3 个（")

    def test_no_hint_line_when_none(self):
        self.project([(1, INTENSIVE, None, "")], preface=PREFACE)
        code, out = self.run_build("check")
        self.assertEqual(code, 0, out)
        self.assertNotIn("提示", out)


class TestPrereadCount(LightCase):
    def test_too_few(self):
        self.light(add_preread(LIGHT, "- **forepaw** /ˈfɔːpɔː/ n. 前爪\n"))      # forepaw、forepaws 各 1 次
        self.assertReports("第 1 章 格式：读前词 forepaw 在本章原文里只出现 2 次，至少 3 次", count=1)

    def test_irregular_forms_by_lemma(self):
        self.light(add_preread(LIGHT, "- **fling** /flɪŋ/ v. 猛扔\n"))           # fling 1 次，flung 4 次
        self.assertClean()

    def test_hyphenated_words_count_parts(self):
        self.light(add_preread(LIGHT, "- **luncheon** /ˈlʌntʃən/ n. 午餐\n"))    # 只在 luncheon-basket 里，6 次
        self.assertClean()

    def test_phrase_consecutive_lemmas(self):
        self.light(add_preread(LIGHT, "- **go on** phr. 接着做\n"))              # go on 1 次，went on 2 次
        self.assertClean()
        self.light(add_preread(LIGHT, "- **dwell on** phr. 老想着\n"))
        self.assertReports("读前词 dwell on 在本章原文里只出现 1 次，至少 3 次", count=1)

    def test_short_text_threshold(self):
        text = sub(sub(LIGHT, ROW, "- **dwell on** phr. 老想着\n"), "- **fellow** /ˈfeləʊ/ n. 家伙，伙计\n")
        self.light(text, source=short_source())
        self.assertReports("读前词 dwell on 在本章原文里只出现 1 次，至少 2 次")

    def test_intensive_preread_counted(self):
        pre = add_preread(section(LIGHT, "读前"), "- **dwell on** phr. 老想着\n")
        self.project([(1, sub(INTENSIVE, "## 长难句\n", pre + "## 长难句\n", 1), None, "")])
        out = self.assertReports("读前词 dwell on 在本章原文里只出现 1 次，至少 3 次")
        self.assertIn("提示 第 1 章 读前：读前词 bank（A1）不高于读者水平 B1", out)


class TestNoLexicon(LightCase):
    """取不到词级数据（skill 的副本里没有 scripts/data/）：次数照查，按后缀规则归并；级别不查，给一条提示。"""
    def run_build(self, cmd, *args):
        scripts = Path(self.tmp.name) / "skill" / "scripts"
        if not scripts.exists():
            scripts.mkdir(parents=True)
            for f in ("build.py", "lexicon.py", "source.py", "rules.json"):
                shutil.copy(SKILL / "scripts" / f, scripts / f)
        r = subprocess.run([sys.executable, str(scripts / "build.py"), cmd, str(self.root), *args], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_counts_without_levels(self):
        self.light(LIGHT)       # sculled、sculls、trotted、fellows 按后缀规则也归得回去
        n, out = self.check()
        self.assertEqual(n, 0, out)
        self.assertIn("提示 全部单元 词级：取不到词级数据（", out)
        self.assertIn("提示 1 个（", out)
        self.assertNotIn("不高于读者水平", out)
        self.assertNotIn("复述参考里的", out)

    def test_irregular_forms_not_merged(self):
        self.light(add_preread(LIGHT, "- **go on** phr. 接着做\n"))              # went on 归不到 go on
        self.assertReports("读前词 go on 在本章原文里只出现 1 次，至少 3 次", count=1)


class TestPrereadLevel(LightCase):
    def test_not_above_reader(self):
        self.light(LIGHT)
        self.assertHints("提示 第 1 章 读前：读前词 bank（A1）不高于读者水平 B1",
                         "提示 第 1 章 读前：读前词 fellow（B1）不高于读者水平 B1",
                         absent=[f"读前词 {w}（" for w in ("scull", "trot", "luncheon-basket", "row")])   # C2 估、C1 估、未定级、B2（按 v.）

    def test_reader_level(self):
        self.project([(1, LIGHT, None, "")], default_mode="轻读", extra={"level": "A2"})
        out = self.assertReports("读前词 bank（A1）不高于读者水平 A2")
        self.assertNotIn("读前词 fellow（", out)


class TestAnswerSentences(LightCase):
    A3 = "3. 他不想让鼹鼠难堪，把落水说成小事一桩，好让鼹鼠宽心。\n"

    def test_three_sentences(self):
        self.light(sub(LIGHT, self.A3, "3. 他不想让鼹鼠难堪。他把落水说成小事一桩。这样鼹鼠就宽心了。\n"))
        self.assertReports("理解答案 3：写了 3 句，答案写 1–2 句中文（原文、译文不算）", count=1)

    def test_translation_not_counted(self):
        # 下面的译文「一点水对河鼠算得了什么？」不算一句
        self.light(sub(LIGHT, self.A3, "3. 他不想让鼹鼠难堪。他把落水说成小事一桩，好让鼹鼠宽心。\n"))
        self.assertClean()

    def test_last_sentence_without_mark(self):
        self.light(sub(LIGHT, self.A3, "3. 他不想让鼹鼠难堪！他把落水说成小事一桩？好让鼹鼠宽心\n"))
        self.assertReports("理解答案 3：写了 3 句", count=1)


class TestRetellSentences(LightCase):
    TAIL = "and soon he takes to life on the river."

    def test_b1_too_many(self):
        self.light(sub(LIGHT, self.TAIL, self.TAIL + " He is happy. He sleeps well."))
        self.assertReports("复述参考写了 9 句，B1 读者写 5–8 句", count=1)

    def test_b1_too_few(self):
        ref = section(LIGHT, "复述").split("参考：", 1)[1].split("\n", 1)[0]
        self.light(sub(LIGHT, ref, "The Mole runs out into the sunshine. He meets the Water Rat. They go out in the boat. "
                                   "The boat goes over."))
        self.assertReports("复述参考写了 4 句，B1 读者写 5–8 句", count=1)

    def test_abbreviation_does_not_split(self):
        self.light(sub(LIGHT, self.TAIL, self.TAIL + " Mr. Toad does not come."))        # 8 句；在 Mr. 处切开就是 9 句
        self.assertClean()

    def test_a2(self):
        self.project([(1, LIGHT, None, "")], default_mode="轻读", extra={"level": "A2"})
        self.assertReports("复述参考写了 7 句，A2 读者写 3–5 句")

    def test_b2_words_only(self):
        self.project([(1, sub(LIGHT, self.TAIL, self.TAIL + " He is happy. He sleeps well."), None, "")],
                     default_mode="轻读", extra={"level": "B2"})
        n, out = self.check()
        self.assertEqual(n, 0, out)
        self.assertNotIn("复述参考写了", out)


class TestRetellWords(LightCase):
    MEADOW = "提示 第 1 章 复述：复述参考里的 meadow（B2，估）高于读者水平，也不是读前的词或词条"
    FORGIVES = "and forgives him."
    FORBEARS = "and forbears to scold him."

    def test_above_level(self):
        self.light(LIGHT)
        self.assertHints(self.MEADOW, absent=["复述参考里的 otter", "复述参考里的 scull"])    # 句中大写的 Otter 是专名；sculls 是读前词

    def test_preread_word_exempt(self):
        self.light(add_preread(LIGHT, "- **meadow** /ˈmedəʊ/ n. 草地\n"))
        self.assertHints(absent=["复述参考里的 meadow"])

    def test_usage_lemma_and_phrase_exempt(self):
        text = sub(LIGHT, self.FORGIVES, self.FORBEARS)
        no_usage = sub(text, text[text.index("- **forbear**"):text.index("- **there’s no denying**")])
        self.light(no_usage)
        self.assertHints("复述参考里的 forbears（C2，估）高于读者水平")
        self.light(text)                                   # 词条 forbear：forbears 归到 forbear
        self.assertHints(absent=["复述参考里的 forbears"])
        self.light(sub(text, "- **forbear**：forbear to do", "- **forbear to do**：forbear to do"))     # 短语拆开的词也算
        self.assertHints(absent=["复述参考里的 forbears"])

    def test_sentence_initial_names(self):
        text = sub(LIGHT, "The Mole stops his spring-cleaning", "Mole stops his spring-cleaning")      # 原文里 Mole 都大写：专名
        text = sub(text, "The Water Rat sculls over", "Presently the Water Rat sculls over")          # presently 原文里是小写
        self.light(text)
        self.assertHints("复述参考里的 presently（B2，估）", absent=["复述参考里的 mole"])


class TestGrammarTerms(Base):
    MISSING = "第 1 章 语法术语：句 1 怎么拆用了「形式主语」，前言的语法术语表里没有"
    PASSIVE_ROW = "| 被动 | be + 过去分词，主语是承受动作的一方 | The window **was broken**. |\n"
    CRUX = "不是指前面说的事。"

    def light(self, text, preface=PREFACE_FORMAL, units=1):
        self.project([(n, text, None, "") for n in range(1, units + 1)], default_mode="轻读", preface=preface)

    def test_missing_term(self):
        self.light(LIGHT, PREFACE)
        out = self.assertReports(self.MISSING, count=1)
        self.assertIn("，语法术语 1", out)

    def test_each_term_once(self):
        self.light(LIGHT, PREFACE, units=2)
        n, out = self.check()
        self.assertEqual(out.count("用了「形式主语」"), 1, out)
        self.assertIn(self.MISSING, out)

    def test_no_table_no_check(self):
        no_table = PREFACE.split("## 语法术语")[0] + "## 这本书" + PREFACE.split("## 这本书", 1)[1]
        self.light(LIGHT, no_table)
        self.assertHints(absent=["语法术语："])
        self.light(LIGHT, None)
        self.assertHints(absent=["语法术语："])

    def test_unused_terms_are_hints(self):
        self.light(LIGHT)
        self.assertHints("提示 全部单元 语法术语：前言的语法术语表里有「系动词」，讲义一次没用到",
                         absent=["表里有「形式主语」", "表里有「主干」", "表里有「从句」"])     # 主干：长难句的标签也算用到

    def test_skipped_lines(self):
        # 例、译（含长难句的「- **译**：」）、参考行和反引号里的术语不算
        text = sub(LIGHT, "the nearest café.", "the nearest café.（形式宾语）")
        text = sub(text, "- **卡点**：`small wonder` 不是", "- **卡点**：`small wonder 插入语` 不是")
        text = sub(text, "   译：河鼠吞吞吐吐地解释道", "   译：河鼠吞吞吐吐地解释道（虚拟）")
        text = sub(text, "- **译**：所以难怪", "- **译**：（强调句）所以难怪")
        text = sub(text, "on the river.\n", "on the river.（倒装）\n")
        self.light(text)
        self.assertClean()

    def test_longest_term_first(self):
        # 表里有宾语、从句，没有宾语从句：整个算「宾语从句」
        self.light(sub(LIGHT, self.CRUX, self.CRUX + "that 后面是宾语从句。"))
        self.assertReports("句 2 卡点用了「宾语从句」，前言的语法术语表里没有", count=1)

    def test_plain_chinese(self):
        no_passive = sub(PREFACE_FORMAL, self.PASSIVE_ROW)
        self.light(sub(LIGHT, self.CRUX, self.CRUX + "鼹鼠只是被动地跟着，伴随着一阵风。"), no_passive)
        self.assertClean()
        self.light(sub(LIGHT, self.CRUX, self.CRUX + "这里是被动。"), no_passive)
        self.assertReports("句 2 卡点用了「被动」", count=1)


class TestPostEstimate(LightCase):
    def test_within_limit(self):
        self.light(LIGHT)
        self.assertHints(absent=["篇幅"])

    def test_over_limit_is_hint(self):
        one = section(LIGHT, "补充句").split("\n", 1)[1]
        self.light(LIGHT + one.replace("### 1.", "### 2.") + one.replace("### 1.", "### 3."))     # PDF 实排：读后 4 页
        self.assertHints("提示 第 1 章 篇幅：估计读后约 3.2 页，上限 3 页；以 PDF 实排为准")


# ---------- 合订、PDF、命令 ----------

class TestCommands(Base):
    def test_md_identical_to_v1_for_intensive_project(self):
        ch2 = re.sub(r"\A# .*", "# 第 2 章讲解", INTENSIVE)
        self.project([(1, INTENSIVE, None, "The River Bank"), (2, ch2, None, "The River Bank (copy)")], preface=PREFACE)
        code, out = self.run_build("md")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.root / "成品" / "讲义-全本.md").read_bytes(), (FIX / "合订_精读两章_第一版.md").read_bytes())

    def test_csv_command_removed(self):
        self.project([(1, INTENSIVE, None, "")])
        code, out = self.run_build("csv")
        self.assertNotEqual(code, 0)
        self.assertIn("python3 build.py check", out)       # 打印用法
        self.assertNotIn("csv", out.lower())


class TestRanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("er_build", BUILD)
        cls.b = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.b)
        cls.rules = cls.b.load_rules()

    def test_light_long_and_short(self):
        long, short = self.b.count_ranges(4300, self.rules, "轻读"), self.b.count_ranges(800, self.rules, "轻读")
        self.assertEqual(long, {"读前词": (5, 8), "人物": (0, 5), "理解": (2, 3), "长难句": (2, 2), "词条": (3, 4), "复述": (1, 1)})
        self.assertEqual(short, {"读前词": (3, 5), "人物": (0, 5), "理解": (2, 2), "长难句": (1, 2), "词条": (3, 3), "复述": (1, 1)})
        self.assertEqual(self.b.count_ranges(1200, self.rules, "轻读")["理解"], (2, 3))     # 1,200 词算长文

    def test_intensive_relaxed(self):
        long, short = self.b.count_ranges(4300, self.rules), self.b.count_ranges(800, self.rules)
        self.assertEqual((long["赏析点"], long["自测"]), ((3, 7), (5, 11)))
        self.assertEqual((short["赏析点"], short["自测"]), ((2, 4), (4, 7)))
        self.assertEqual((long["精讲句"], long["词条"]), ((5, 6), (9, 10)))       # 没动：按每千词算

    def test_post_estimate_calibration(self):
        # 第二版的估页。build.py pdf 实排（系统字体）：第二版 demo 第 2 章读后 3 页、第三页排到 0.69；轻读夹具读后 3 页、第三页排到 0.50
        # demo/ 已是第三版，这里读冻结的第二版副本 fixtures/demo_snapshot；第三版的校准在 test_snapshot_v3.py
        est = self.rules["light"]["md_estimate"]
        self.b.load_project(FIX / "demo_snapshot")
        self.assertAlmostEqual(self.b.post_estimate(self.b.parse_chapter(2), est), 2.69, delta=0.1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "原文").mkdir()
            (root / "讲义").mkdir()
            (root / "原文" / "第01章.txt").write_text(SOURCE, encoding="utf-8")
            (root / "讲义" / "第01章.md").write_text(LIGHT, encoding="utf-8")
            (root / "设置.json").write_text(json.dumps({"title": "T", "level": "B1", "default_mode": "轻读", "units": [1]}),
                                           encoding="utf-8")
            self.b.load_project(root)
            self.assertAlmostEqual(self.b.post_estimate(self.b.parse_chapter(1), est), 2.50, delta=0.1)

    def test_sentence_counting(self):
        self.assertEqual(self.b.zh_sentences("他想家。嘴上不提，心里放不下！"), 2)
        self.assertEqual(self.b.zh_sentences("“走吧。”他说"), 2)
        self.assertEqual(len(self.b.en_sentences("Mr. Toad has a car. Dr. Rat says no! Is it fast? Yes.")), 4)

    def test_suffix_forms(self):
        f = self.b.suffix_forms
        for word, base in (("trotted", "trot"), ("sculls", "scull"), ("ditches", "ditch"), ("hurried", "hurry"),
                           ("trudging", "trudge"), ("murmured", "murmur"), ("used", "use")):
            self.assertIn(base, f(word), word)
        self.assertEqual(f("bus"), {"bus"})


if __name__ == "__main__":
    unittest.main()
