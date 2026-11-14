#!/usr/bin/env python3
"""摸底：篇幅、句长、长句和拆句候选、高于读者水平的词占多少、读法建议、读前词候选。

用法：
  profile.py 项目目录            读 项目/原文/第NN章.txt（单元名 章/部分/篇 取 设置.json 的 unit），
                                 读者水平取 项目/设置.json 的 level（没有就 B1），单元标题取 units；
                                 项目/源稿/第NN章.md（旧项目是 讲义/）存在时读其中「## 读前」→「### 本章的词」；
                                 项目/卡句.txt 存在时，拆句候选里标出卡句
  profile.py 某个.txt            单个文本（在 项目/原文/ 里时同样读 设置.json、前面单元的讲义和 卡句.txt）
  可选：--level B1  --top 30（「高一级」「高两级及以上」每类打印几个，0=全部）
        --tsv 候选词.tsv（定计划用：全部高于读者水平和未定级的词，带级别、次数、单元数）
        --sent-tsv 拆句候选.tsv（定计划用：全部拆句候选，列是 单元、词数、高于水平词数、从属词、逗号、原句）

统计口径：
  - 词数：英文词（字母串，可含撇号、连字符；spring-cleaning、didn’t 各算一个）。
  - 句子：. ! ? … 后接空白、再接大写字母或开引号处切开；Mr. Mrs. Dr. St. 等缩写和单字母缩写不切。
    段落边界也是句子边界。没有句末标点、不超过 12 词的段落当作标题行，不计入句子和句长。
  - 级别：取自 lexicon.py 的 level_info。CEFR-J（A1–B2）和 Octanove（C1–C2）词表定级，先按 ECDICT 变形表、
    不规则表、后缀规则还原成原形再查（fellows → fellow，trotted → trot）；两个表都没收的按 ECDICT 的 COCA
    名次估级，标“估”；名次也没有的是“未定级”。一个词有几个词性时取最低一级。
    连字符词：整体有级别就整体算；去掉连字符是个有级别的词就按它算（W-e-ll → well，to-day → today）；
    否则拆开逐段算，口吃的前缀（W-w-what 的 w）不算；拆开后有一段未定级，整个复合词算一个未定级词
    （good-natured）。
    不计入级别统计：单个字母（a、I、O 除外）；撇号前面断开的缩约残片（’ll、’s、’ve、’re、’d、’t、’m）；
    标题行里的罗马数字（II、IV）。
    专有名词：句中（不在句首、不在开引号后）大写开头的词，单列，不算生词。句首大写的词，在别处以大写出现在
    句中、且大写次数不少于小写次数的也算专名（小写有级别的，大写次数要多于小写：句首的 Toad 是专名）。
    段内的换行（诗行）在级别统计里当句子边界，行首大写算句首。
  - 高于读者水平的词次占比，分母是计入级别统计的全部词次（含专名）：
      下限 = 词表定级、高于读者的；中间 = 下限 + 估级、高于读者的；上限 = 中间 + 未定级的。
  - 长句：词数达到 rules.json 的 profile.long_sentence_words（30）的句子。给句数、占句数的比例、这些句子的词数
    占全部句子词数（不含标题行）的比例。句子的词数同句长统计。
  - 拆句候选：词数不低于 rules.json 的 v3.sentence.min_words 里读者那一档（A2 18，B1 22，B2 28，C1 32；没列的
    水平用最小的一档）的句子，按词数从多到少排，词数相同的按从属词个数从多到少排，再相同的按原文顺序；
    列 profile.drill_top 句。每句给：词数；高于读者水平的词次（口径同下面的中间值：词表定级和估级的，不含专名
    和未定级；取不到级别数据时是 —）；从属词个数（SUBORDINATORS 里的词，按整词、不分大小写数，that’s 这类
    缩约不算；很粗，只用来排序和参考，不进建议）；逗号个数；开头约 40 个字符。全书的列表多一栏单元。
    卡句.txt 里在范围内唯一命中的句子标 ★卡句（归一化和比对同 build.py check 的卡句定位；多处、近似、找不到的不标）；
    排在前 profile.drill_top 句以外的卡句候选接在列表后面。
  - 读法建议（rules.json 的 profile.above_pct、profile.long_pct）：词 = 高于读者水平的词次占比的中间值，
    句 = 长句占句数的比例，两个数都按显示的一位小数比。
      词 ≤ above_pct[0]：句 ≤ long_pct[0] 可以直接读；句 > long_pct[0] 适合练拆句。
      above_pct[0] < 词 ≤ above_pct[1]：句 ≤ long_pct[1] 配讲义读；句 > long_pct[1] 配讲义读、记卡句。
      词 > above_pct[1]：偏难，主要难在词。
    建议只是提示，读不读、怎么读由用户定。
  - 读前词候选（每个单元）：本单元出现次数够（rules.json 的 profile.preread_min_count；原文不足
    counts.short_words 词的用 short，词数按 build.py check 的算法：空白切开、含字母的算一个）；词表定级或
    估级高于读者，或未定级；去掉专名，去掉前面单元讲义「### 本章的词」列过的（讲义文件存在时才读）。
    按次数排（次数相同时有级别的在前、级别高的在前，未定级的在后），列 profile.preread_top 个。
    多单元时每个词注明在几个单元出现过；单元的讲义已经列了的标〔讲义已列〕。
  - 高一级 / 高两级及以上：词表定级或估级比读者高一级、高两级及以上的词型（估级的标“估”）。
  - 级别数据取不到（lexicon.LexiconError）时只给篇幅、句长、长句和拆句候选（高于水平的词次是 —），并说明原因，
    不给读法建议，不退出。--sent-tsv 照写，高于水平词数一栏空着。
"""
import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # 不在 skill 目录里留 __pycache__
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from source import WORD_RE, is_heading, setup_stdout, split_sentences  # noqa: E402
from lexicon import IRREGULAR, LEVELS, RANK, UNRATED, Lexicon, LexiconError, rule_candidates  # noqa: E402

RULES = HERE / "rules.json"
DEFAULT_RULES = {"above_pct": [5, 10], "preread_min_count": {"long": 3, "short": 2}, "preread_top": 15,
                 "long_sentence_words": 30, "long_pct": [5, 15], "drill_top": 12}
DEFAULT_SHORT_WORDS = 1200
DEFAULT_MIN_WORDS = {"A2": 18, "B1": 22, "B2": 28, "C1": 32}  # rules.json 的 v3.sentence.min_words 读不到时用
SENT_MIN_WORDS = "sentence_min_words"  # load_rules 把 v3.sentence.min_words 放进 rules 的这个键

# 从属词：只用来给拆句候选排序，很粗（as、that、when 也常不是从属词），不进建议
SUBORDINATORS = frozenset("which who whom whose that where when while as although though because since if unless "
                          "until till whether what how why before after".split())
STUCK_FILE = "卡句.txt"
OPENING_WIDTH = 40  # 拆句候选的「开头」一栏截到多宽

LIST, EST, NONE, PROPER = "list", "estimate", "none", "proper"  # 定级依据
KIND_NAME = {LIST: "词表", EST: "估级", NONE: "未定级"}
PROPER_NAME = "专名"
READER_LEVELS = LEVELS[:-1]  # 读者水平 A1–C1（C2 读者没有“高于水平”的词）

OPENERS = set("“‘\"'([—–")  # 这些后面的大写词算句首（破折号后常是另起的一句：fellows!—At least）
MERGE_RULES = {"-s", "-es", "-ies", "-ed", "-ied", "-ing"}  # 未定级词只按这些后缀并词形（-er、-ly 容易并错）
APHERESIS = {"em": "them", "tis": "it", "twas": "it", "tween": "between", "neath": "beneath"}
KEEP_SINGLE = {"a", "i", "o"}  # 能单独成词的字母；其余单个字母不计入级别统计
CLITIC_FRAGS = {"s", "d", "t", "m", "ll", "ve", "re", "n", "em"}  # 撇号前面断开时留下的缩约残片
ROMAN_RE = re.compile(r"(?=[IVXLCDM]{2,}$)M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})")
LECTURE_WORDS_RE = re.compile(r"^###\s+本\S{1,3}的词\s*$")


# ---------------------------------------------------------------- 读入

UNIT_FILE_RE = re.compile(r"第(\d+)(.+)\.txt")


def read_units(path):
    """返回 (单元列表 [(显示名, 段落, 编号或 None)], 项目目录或 None, 单元名)。"""
    p = Path(path)
    project = None
    if p.is_dir():
        src_dir = p / "原文" if (p / "原文").is_dir() else p
        if (src_dir.resolve().parent / "设置.json").is_file():
            project = src_dir.resolve().parent
        cfg = load_config(project)
        unit = (cfg or {}).get("unit") or "章"
        files, skipped = [], []
        for f in src_dir.glob("*.txt"):
            m = UNIT_FILE_RE.fullmatch(f.name)
            if m and m.group(2) == unit:
                files.append((int(m.group(1)), f))
            else:
                skipped.append(f.name)
        files.sort()
        if skipped:
            print("注意：%s 里这些文件不是 第NN%s.txt，没有统计：%s" % (src_dir, unit, "、".join(sorted(skipped))),
                  file=sys.stderr)
        if not files:
            raise SystemExit("错误：%s 下没有 第NN%s.txt" % (src_dir, unit))
    elif p.is_file():
        if (p.resolve().parent.parent / "设置.json").is_file():
            project = p.resolve().parent.parent
        cfg = load_config(project)
        unit = (cfg or {}).get("unit") or "章"
        m = UNIT_FILE_RE.fullmatch(p.name)
        files = [(int(m.group(1)) if m else None, p)]
    else:
        raise SystemExit("错误：找不到 %s" % path)
    titles = {}
    for u in (cfg or {}).get("units", []):
        try:
            titles[int(u.get("n"))] = u.get("title") or ""
        except (TypeError, ValueError):
            pass
    units = []
    for n, f in files:
        text = f.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        paras = [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]
        if n is None:
            name = f.name
        else:
            name = "第 %d %s" % (n, UNIT_FILE_RE.fullmatch(f.name).group(2))
            if titles.get(n):
                name += " " + titles[n]
        units.append((name, paras, n))
    return units, project, unit


def load_config(project):
    if project is None:
        return None
    cfg = project / "设置.json"
    if not cfg.is_file():
        return None
    try:
        with open(cfg, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit("错误：读不了 %s（%s）" % (cfg, e))


def load_rules(path=RULES):
    """rules.json 的 profile 组、counts.short_words，以及 v3.sentence.min_words（放在 rules[SENT_MIN_WORDS]）；
    读不到时用默认值并说明。"""
    rules = dict(DEFAULT_RULES)
    rules[SENT_MIN_WORDS] = dict(DEFAULT_MIN_WORDS)
    short_words = DEFAULT_SHORT_WORDS
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("注意：读不了 %s（%s），门槛用默认值。" % (path, e), file=sys.stderr)
        return rules, short_words
    prof = data.get("profile")
    if isinstance(prof, dict):
        rules.update({k: v for k, v in prof.items() if not k.startswith("_")})
    else:
        print("注意：%s 里没有 profile 组，门槛用默认值。" % path, file=sys.stderr)
    try:
        short_words = int(data["counts"]["short_words"])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        mw = {k: int(v) for k, v in data["v3"]["sentence"]["min_words"].items() if not k.startswith("_")}
        if mw:
            rules[SENT_MIN_WORDS] = mw
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return rules, short_words


def lecture_words(path):
    """讲义「## 读前」→「### 本章的词」下每行 `- **word** …` 的词头。"""
    out = []
    in_pre = in_words = False
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(#+)\s", ln)
        if m:
            depth = len(m.group(1))
            if depth <= 2:
                in_pre, in_words = depth == 2 and re.match(r"^##\s+读前\s*$", ln) is not None, False
            elif depth == 3:
                in_words = in_pre and LECTURE_WORDS_RE.match(ln) is not None
            continue
        if in_words:
            m = re.match(r"^\s*-\s+\*\*([^*]+)\*\*", ln)
            if m:
                out.append(m.group(1).strip())
    return out


def lecture_lists(project, unit):
    """项目/源稿/第NN章.md（旧项目是 讲义/）里列过的读前词：{编号: [词头]}；源稿目录不存在时是空的。"""
    listed = {}
    d = next((Path(project) / n for n in ("源稿", "讲义") if (Path(project) / n).is_dir()), None) if project else None
    if d is not None and d.is_dir():
        for f in d.glob("第*%s.md" % unit):
            m = re.fullmatch(r"第(\d+)%s\.md" % re.escape(unit), f.name)
            if m:
                listed[int(m.group(1))] = lecture_words(f)
    return listed


# 卡句.txt：格式和归一化同 notebook.py 的卡句定位。这里只用来在拆句候选里标 ★卡句，
# 完整的定位（多处、近似、找不到、太短、标记）由 build.py stuck 做；读法和它对齐，比对只认唯一命中。
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u2060\ufeff\u00ad]")  # 零宽字符、软连字符
NORM_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")  # 连字符不算词内：good-nature 和 good nature 一样
STUCK_UNIT_RE = re.compile(r"#*\s*(?:第\s*([0-9]+|[零〇一二两三四五六七八九十百]+)\s*(?:章|部分|篇)|\[\s*([0-9]+)\s*\])\s*")
STUCK_LEAD_RE = re.compile(r"(?:[-*•]\s+|\d+[.、)）]\s*|>\s*)")  # 行首的列表记号、引用记号
STUCK_QUOTES = "\"'“”‘’「」『』"


def norm_words(text):
    """比对用的词串，同 build.py 的 stuck_words：NFKC，去零宽字符和软连字符，弯引号换直的，转小写，取英文词，
    连字符拆开，标点不比。"""
    t = _ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFKC", text))
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return NORM_WORD_RE.findall(t.lower())


def cn_int(s):
    """「12」「十二」「二十」→ 整数。"""
    if s.isdigit():
        return int(s)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    total = cur = 0
    for c in s:
        if c in digits:
            cur = digits[c]
        elif c in "十百":
            total += (cur or 1) * (10 if c == "十" else 100)
            cur = 0
    return total + cur


def read_stuck(path, known=None):
    """卡句.txt → [(单元号或 None, 词串)]。# 开头的行和空行跳过；单元行（第 N 章，前面可有 #；或 [N]）管到下一个
    单元行，单元号不在 known（项目里有原文的单元）里的按全书找；行首的 - * 1. > 和两头的引号去掉；最后一个 ｜ 或 |
    后面是标记，这里不用。读不了时说明一句，当作没有。"""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        print("注意：读不了 %s（%s），拆句候选里不标卡句。" % (path, e), file=sys.stderr)
        return []
    out, unit = [], None
    for raw in text.splitlines():
        ln = raw.strip()
        m = STUCK_UNIT_RE.fullmatch(ln)
        if m:
            unit = cn_int(m.group(1)) if m.group(1) else int(m.group(2))
            if known is not None and unit not in known:
                unit = None
            continue
        if not ln or ln.startswith("#"):
            continue
        cut = max(ln.rfind("｜"), ln.rfind("|"))
        if cut >= 0:
            ln = ln[:cut].strip()
        for _ in range(2):
            ln = STUCK_LEAD_RE.sub("", ln, count=1) if STUCK_LEAD_RE.match(ln) else ln
        ln = ln.strip()
        if len(ln) > 1 and ln[0] in STUCK_QUOTES and ln[-1] in STUCK_QUOTES:
            ln = ln[1:-1].strip()
        words = norm_words(ln)
        if words:
            out.append((unit, words))
    return out


def source_units(project):
    """项目/原文/ 里有哪些单元号（文件名 第NN<unit>.txt，unit 取 设置.json）。"""
    d = Path(project) / "原文"
    unit = (load_config(Path(project)) or {}).get("unit") or "章"
    out = set()
    if d.is_dir():
        for f in d.glob("*.txt"):
            m = UNIT_FILE_RE.fullmatch(f.name)
            if m and m.group(2) == unit:
                out.add(int(m.group(1)))
    return out


def sentence_words(st):
    """一个单元的比对词串和每个词所在的句子（st.sent_lens 的下标）。"""
    words, owner = [], []
    for i, (_, sent) in enumerate(st.sent_lens):
        ws = norm_words(sent)
        words += ws
        owner += [i] * len(ws)
    return words, owner


def locate_stuck(entries, indexed):
    """entries：read_stuck 的结果；indexed：[(单元号, 词串, 所在句子)]。
    返回 {(第几个单元, 句子下标)}：只收在范围内（写了单元行的只找那个单元，没写的找全部单元）唯一命中的，
    取包含命中段开头的那一句。"""
    hits = set()
    for unit, q in entries:
        found = []
        for ui, (n, words, owner) in enumerate(indexed):
            if unit is not None and n != unit:
                continue
            m = len(q)
            for i in range(len(words) - m + 1):
                if words[i] == q[0] and words[i:i + m] == q:
                    found.append((ui, owner[i]))
                    if len(found) > 1:
                        break
            if len(found) > 1:
                break
        if len(found) == 1:
            hits.add(found[0])
    return hits


def tag_sentences(units, stats, project):
    """给每句记上单元（编号，没有编号的用显示名），标出 卡句.txt 里唯一命中的句子。"""
    for (name, _, n), st in zip(units, stats):
        for info in st.sent_info:
            info["unit"] = n if n is not None else name
    path = Path(project) / STUCK_FILE if project else None
    if path is None or not path.is_file():
        return
    known = source_units(project) | {n for _, _, n in units if n is not None}
    entries = read_stuck(path, known)
    if not entries:
        return
    indexed = [(n,) + sentence_words(st) for (_, _, n), st in zip(units, stats)]
    for ui, si in locate_stuck(entries, indexed):
        stats[ui].sent_info[si]["stuck"] = True


# ---------------------------------------------------------------- 分词

def tokens(sentence, heading=False):
    """[(词, 起, 止, 是否句首或开引号后)]"""
    out = []
    prev_end = 0
    for i, m in enumerate(WORD_RE.finditer(sentence)):
        gap = sentence[prev_end:m.start()]
        tok = m.group(0)
        if gap.endswith(("’", "'")) and tok.lower() in APHERESIS:  # ’em → them
            tok = APHERESIS[tok.lower()]
            initial = False
        else:
            initial = heading or i == 0 or bool(OPENERS & set(gap))
        out.append((tok, m.start(), m.end(), initial))
        prev_end = m.end()
    return out


def is_I(tok):
    """I、I’m 之类，以及感叹词 O：总是大写，但不是专名。"""
    return tok in ("I", "O") or re.fullmatch(r"I['’](m|ll|d|ve)", tok) is not None


def strip_poss(tok):
    return re.sub(r"['’]s$", "", tok)


def is_fragment(sentence, s, tok):
    """单个字母（a、I、O 除外），或撇号前面断开的缩约残片（we ’ll 的 ll、1920’s 的 s）。"""
    low = tok.lower()
    if len(low) == 1 and low not in KEEP_SINGLE:
        return True
    return low in CLITIC_FRAGS and s > 0 and sentence[s - 1] in "’'"


def junk_key(key):
    """未定级列表里不该出现的切词残片（分词时已经挡掉，这里再兜一次底）。"""
    return len(key) <= 1 or key in CLITIC_FRAGS


def level_sentences(para):
    """级别统计用的切句：段内的换行（诗行，source.py 只在 <br/> 处留换行）先切开，行首大写算句首。
    句长统计不用它，仍按整段切。"""
    return [sent for line in para.split("\n") for sent in split_sentences(line)]


def check_word_count(paras):
    """build.py check 的词数：按空白切开、含字母的才算一个词。分长文短文用。"""
    return sum(1 for p in paras for tok in p.split() if re.search(r"[A-Za-z]", tok))


# ---------------------------------------------------------------- 统计

class Stats:
    def __init__(self):
        self.paras = 0
        self.headings = 0
        self.words = 0
        self.check_words = 0
        self.sent_lens = []  # (词数, 句子)
        # 和 sent_lens 一一对应：levels 是这句里 (依据, 级别) → 词次（没有级别数据时 None），unit 是单元，
        # stuck 是不是 卡句.txt 里唯一命中的句子
        self.sent_info = []
        self.tok = Counter()  # (依据, 级别) → 词次；依据 list / estimate / none / proper
        self.types = {}  # (依据, 级别, 键) → {"n": 次数, "forms": set, "first": (句子, 起, 止)}
        self.skipped = Counter()  # 不计入级别统计的残片 → 次数

    def add(self, kind, lv, key, form, sent, s, e):
        self.tok[(kind, lv)] += 1
        d = self.types.get((kind, lv, key))
        if d is None:
            d = self.types[(kind, lv, key)] = {"n": 0, "forms": set(), "first": (sent, s, e)}
        d["n"] += 1
        d["forms"].add(form)

    def merge(self, other):
        self.paras += other.paras
        self.headings += other.headings
        self.words += other.words
        self.check_words += other.check_words
        self.sent_lens += other.sent_lens
        self.sent_info += other.sent_info
        self.tok.update(other.tok)
        self.skipped.update(other.skipped)
        for k, d in other.types.items():
            mine = self.types.get(k)
            if mine is None:
                self.types[k] = {"n": d["n"], "forms": set(d["forms"]), "first": d["first"]}
            else:
                mine["n"] += d["n"]
                mine["forms"] |= d["forms"]

    def total_tokens(self):
        return sum(self.tok.values())


def length_stats(paras):
    """只算篇幅和句长（不要级别数据）。"""
    st = Stats()
    st.paras = len(paras)
    for para in paras:
        head = is_heading(para)
        st.headings += head
        st.words += len(WORD_RE.findall(para))
        if head:
            continue
        for sent in split_sentences(para):
            toks = tokens(sent)
            if toks:
                st.sent_lens.append((len(toks), sent))
                st.sent_info.append({"levels": None, "unit": None, "stuck": False})
    st.check_words = check_word_count(paras)
    return st


class Profiler:
    def __init__(self, lex, units):
        self.lex = lex
        self.rate_cache = {}
        self.piece_cache = {}
        # 第一遍：句中大写出现过的词、以小写出现过的词
        self.proper_seen, self.lower_seen = Counter(), Counter()
        for unit in units:
            for para in unit[1]:
                head = is_heading(para)
                for sent in level_sentences(para):
                    for tok, _, _, initial in tokens(sent, head):
                        if tok[0].isupper():
                            if not initial and not is_I(tok):
                                self.proper_seen[strip_poss(tok)] += 1
                        else:
                            self.lower_seen[strip_poss(tok).lower()] += 1

    def rated(self, low):
        return self.rate(low)[0] != NONE

    def rate(self, low):
        """小写词 → (依据, 级别, 键)。键：有级别的是 lexicon 给的原形；未定级的按 unrated_key 并词形。"""
        r = self.rate_cache.get(low)
        if r is None:
            info = self.lex.level_info(low)
            if info["kind"] in (LIST, EST):
                r = (info["kind"], info["level"], info["lemma"])
            else:
                r = (NONE, UNRATED, self.unrated_key(strip_poss(low)))
            self.rate_cache[low] = r
        return r

    def unrated_key(self, low):
        """未定级词的词型：不规则变形归到原形；规则变形只有在原形也以小写出现在文中、且同样未定级时才并过去
        （weirs → weir）。"""
        if low in IRREGULAR:
            return IRREGULAR[low]
        for cand, _, how in rule_candidates(low):
            if how not in MERGE_RULES:
                continue
            if cand != low and self.lower_seen[cand] and self.lex.level_info(cand)["kind"] == NONE:
                return cand
        return low

    def pieces(self, tok):
        """普通词 → [(依据, 级别, 键, 词形)]；空列表表示整个词都是残片。"""
        low = tok.lower()
        res = self.piece_cache.get(low)
        if res is None:
            res = self.piece_cache[low] = self._pieces(low)
        return res

    def _pieces(self, low):
        whole = self.rate(low)
        if whole[0] != NONE or "-" not in low:
            return [whole + (low,)]
        parts = [x for x in low.split("-") if x]
        if not parts:
            return []
        joined = self.rate("".join(parts))
        if joined[0] != NONE:  # W-e-ll → well，to-day → today
            return [joined + (low,)]
        last = parts[-1]
        kept = [x for x in parts[:-1] if not (last.startswith(x) and len(x) < len(last))] + [last]  # W-w-what
        kept = [x for x in kept if len(x) > 1 or x in KEEP_SINGLE]
        rated = [self.rate(x) + (x,) for x in kept]
        if any(r[0] == NONE for r in rated):  # good-natured：整个复合词算一个未定级词
            return [(NONE, UNRATED, strip_poss(low), low)]
        return rated

    def unit(self, paras):
        st = length_stats(paras)
        per_sent = [Counter() for _ in st.sent_lens]  # 每句的 (依据, 级别) → 词次，给拆句候选用
        for info, c in zip(st.sent_info, per_sent):
            info["levels"] = c
        sent_no = 0
        for para in paras:
            head = is_heading(para)
            # 段内第几个词 → 属于 sent_lens 的第几句。级别统计按 level_sentences 切（诗行另切），句长按整段切，
            # 两边都只在空白处切开，段内的词序一样，所以按词的序号对得上。标题行不计入句子，是空的。
            owner = []
            if not head:
                for sent in split_sentences(para):
                    k = len(tokens(sent))
                    if k:
                        owner += [sent_no] * k
                        sent_no += 1
            k = -1
            for sent in level_sentences(para):
                for tok, s, e, initial in tokens(sent, head):
                    k += 1
                    here = per_sent[owner[min(k, len(owner) - 1)]] if owner else None
                    if (head and ROMAN_RE.fullmatch(tok)) or is_fragment(sent, s, tok):
                        st.skipped[tok] += 1
                        continue
                    adds = None
                    if tok[0].isupper() and not is_I(tok) and not (tok.isupper() and len(tok) > 1
                                                                    and self.rated(tok.lower())):
                        base = strip_poss(tok)
                        if not initial:
                            adds = [(PROPER, PROPER_NAME, base, tok)]
                        else:
                            # 句首：在句中大写出现过，且次数不少于小写（有级别的词要多于小写：Toad、Mole）→ 专名
                            up, low = self.proper_seen[base], self.lower_seen[base.lower()]
                            if up > 0 and (up > low if self.rated(tok.lower()) else up >= low):
                                adds = [(PROPER, PROPER_NAME, base, tok)]
                    if adds is None:
                        adds = self.pieces(tok)
                        if not adds:
                            st.skipped[tok] += 1
                    for kind, lv, key, form in adds:
                        st.add(kind, lv, key, form, sent, s, e)
                        if here is not None:
                            here[(kind, lv)] += 1
        return st


# ---------------------------------------------------------------- 口径

def above_range(st, reader):
    """(下限, 中间, 上限, 分母)：高于读者水平的词次。"""
    r = RANK[reader]
    lo = sum(n for (k, lv), n in st.tok.items() if k == LIST and RANK[lv] > r)
    est = sum(n for (k, lv), n in st.tok.items() if k == EST and RANK[lv] > r)
    none = sum(n for (k, _), n in st.tok.items() if k == NONE)
    return lo, lo + est, lo + est + none, st.total_tokens()


def pct_value(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


ADVICE = {
    "easy": "可以直接读，讲义帮着扫清个别句子。",
    "drill": "词不难，长句多：适合拿来练拆句。",
    "guide": "建议配讲义读。",
    "both": "词和句子都有难度：配讲义读，把卡住的句子记进 卡句.txt。",
    "words": "偏难，主要难在词：练拆句的效果会打折。可以降一档、换一篇，或者精读。",
}


def advice_key(word_pct, long_pct, above_th, long_th):
    """读法建议。word_pct：高于读者水平的词次占比（中间值）；long_pct：长句占句数的比例。
    above_th = profile.above_pct [a, b]，long_th = profile.long_pct [c, d]：
      词 ≤ a：句 ≤ c → easy，否则 drill；a < 词 ≤ b：句 ≤ d → guide，否则 both；词 > b → words（句不看）。"""
    a, b = above_th
    c, d = long_th
    if word_pct <= a:
        return "easy" if long_pct <= c else "drill"
    if word_pct <= b:
        return "guide" if long_pct <= d else "both"
    return "words"


def advice(word_pct, long_pct, above_th, long_th):
    return ADVICE[advice_key(word_pct, long_pct, above_th, long_th)]


def long_stats(st, threshold):
    """(长句数, 占句数 %, 长句的词数占全部句子词数 %)。长句：词数 ≥ threshold；句子和词数同句长统计（不含标题行）。"""
    lens = [n for n, _ in st.sent_lens]
    longs = [n for n in lens if n >= threshold]
    return len(longs), pct_value(len(longs), len(lens)), pct_value(sum(longs), sum(lens))


def min_words_for(rules, reader):
    """拆句候选的句长下限：v3.sentence.min_words 里读者那一档；没列的水平（A1）用最小的一档。"""
    mw = rules.get(SENT_MIN_WORDS) or DEFAULT_MIN_WORDS
    return int(mw[reader]) if reader in mw else min(int(v) for v in mw.values())


def above_in(levels, reader):
    """一句里高于读者水平的词次，口径同中间值（词表定级和估级的）；没有级别数据时 None。"""
    if levels is None:
        return None
    r = RANK[reader]
    return sum(n for (k, lv), n in levels.items() if k in (LIST, EST) and RANK[lv] > r)


def subordinator_count(sent):
    """从属词个数：按整词、不分大小写数 SUBORDINATORS 里的词。"""
    return sum(1 for w in WORD_RE.findall(sent) if w.lower() in SUBORDINATORS)


def drill_candidates(st, reader, min_words):
    """拆句候选：词数 ≥ min_words 的句子，按词数、从属词个数从多到少排，再按原文顺序。
    [{"words", "above"（None = 没有级别数据）, "subs", "commas", "sent", "unit", "stuck"}]"""
    rows = []
    for i, ((n, sent), info) in enumerate(zip(st.sent_lens, st.sent_info)):
        if n < min_words:
            continue
        rows.append({"words": n, "above": above_in(info["levels"], reader), "subs": subordinator_count(sent),
                     "commas": sent.count(","), "sent": sent, "unit": info["unit"], "stuck": info["stuck"],
                     "order": i})
    rows.sort(key=lambda r: (-r["words"], -r["subs"], r["order"]))
    return rows


def level_label(kind, lv):
    if kind == EST:
        return lv + " 估"
    return lv


def is_candidate(kind, lv, reader):
    """高于读者水平（词表定级或估级），或未定级。"""
    return kind == NONE or (kind in (LIST, EST) and RANK[lv] > RANK[reader])


def by_lemma(st, reader, keep=is_candidate):
    """同一个键合并（极少数词形分到了不同级别）：键 → {n, kind, lv, forms, first}，级别取次数多的那个。"""
    out = {}
    for (kind, lv, key), d in st.types.items():
        if kind == PROPER or not keep(kind, lv, reader):
            continue
        if kind == NONE and junk_key(key):
            continue
        cur = out.get(key)
        if cur is None:
            out[key] = {"n": d["n"], "kind": kind, "lv": lv, "forms": set(d["forms"]), "first": d["first"],
                        "best": d["n"]}
        else:
            cur["n"] += d["n"]
            cur["forms"] |= d["forms"]
            if d["n"] > cur["best"]:
                cur.update(kind=kind, lv=lv, best=d["n"], first=d["first"])
    return out


def preread_candidates(st, reader, rules, short_words, listed_before=(), listed_here=()):
    """读前词候选：[(键, 信息, 本单元讲义已列)]，按次数排，全部返回（打印时截前 N 个）。"""
    mc = rules.get("preread_min_count") or DEFAULT_RULES["preread_min_count"]
    need = mc["short"] if st.check_words < short_words else mc["long"]
    rows = []
    for key, d in by_lemma(st, reader).items():
        if d["n"] < need or key in listed_before:
            continue
        rows.append((key, d, key in listed_here))
    # 次数相同时：有级别的在前（级别高的更前），未定级的在后（里面常混着复合词、方言）
    rows.sort(key=lambda x: (-x[1]["n"], x[1]["kind"] == NONE, -RANK.get(x[1]["lv"], 0), x[0]))
    return rows, need


def listed_keys(heads, lex):
    """讲义里列过的词头 → 用来比对的键（原样小写和 lexicon 的原形）。"""
    out = set()
    for h in heads:
        low = h.strip().lower().replace("’", "'")
        out.add(low)
        out.add(h.strip().lower())
        if " " not in low:
            out.add(lex.lemma(low))
    return out


def level_groups(st, reader):
    r = RANK[reader]
    near, far = [], []
    for key, d in by_lemma(st, reader, lambda k, lv, rd: k in (LIST, EST) and RANK[lv] > RANK[rd]).items():
        (near if RANK[d["lv"]] == r + 1 else far).append((key, d))
    order = lambda x: (-x[1]["n"], RANK[x[1]["lv"]], x[0])  # noqa: E731
    return sorted(near, key=order), sorted(far, key=order)


def level_names(reader):
    r = RANK[reader]
    a = LEVELS[r] if r < len(LEVELS) else "—"
    b = "、".join(LEVELS[r + 1:])
    return a, b or "—"


# ---------------------------------------------------------------- 输出

def pct(a, b):
    return "%5.1f%%" % (100.0 * a / b) if b else "    —"


def snippet(sent, s, e, width=120):
    """截到 width 字符，保证这个词在里面。"""
    if len(sent) <= width:
        return sent
    left = max(0, min(s - width // 3, len(sent) - width + 1))
    out = sent[left:left + width - 1]
    if left > 0:
        out = "…" + out[1:]
    if left + width - 1 < len(sent):
        out = out[:-1] + "…"
    return out


def first_words(sent, n=8):
    ws = sent.split()
    return " ".join(ws[:n]) + (" …" if len(ws) > n else "")


def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def ljust(s, n):
    return s + " " * max(0, n - width(s))


def rjust(s, n):
    return " " * max(0, n - width(s)) + s


def short(key, n=30):
    return key if len(key) <= n else key[:n - 1] + "…"


def word_with_forms(key, d, limit=4):
    forms = sorted(f for f in d["forms"] if f != key)
    return short(key) + ("（%s）" % "、".join(forms[:limit]) if forms else "")


def print_length(st):
    n_sent = len(st.sent_lens)
    print("段 %d   句 %d%s   词 %s" % (st.paras, n_sent,
                                      "（另有标题行 %d 个，不计入句子）" % st.headings if st.headings else "",
                                      format(st.words, ",")))
    if n_sent:
        lens = [x[0] for x in st.sent_lens]
        print("句长：平均 %.1f 词，中位数 %g 词" % (sum(lens) / n_sent, statistics.median(lens)))
        buckets = [("1–10", 1, 10), ("11–20", 11, 20), ("21–30", 21, 30), ("31–40", 31, 40), ("41+", 41, 10 ** 6)]
        print("句长分布：" + "  ".join("%s 词 %d 句（%s）" % (name, c, pct(c, n_sent).strip())
                                     for name, lo, hi in buckets
                                     for c in [sum(1 for x in lens if lo <= x <= hi)]))
        print("最长的三句：")
        for i, (n, s) in enumerate(sorted(st.sent_lens, key=lambda x: -x[0])[:3], 1):
            print("  %d. %d 词：%s" % (i, n, first_words(s)))


def opening(sent, limit=OPENING_WIDTH):
    """句子开头：按空白切开的词，累计宽度不超过 limit；截了的后面加 …。"""
    out = ""
    for w in sent.split():
        nxt = out + " " + w if out else w
        if out and width(nxt) > limit:
            return out + " …"
        out = nxt
    return out


def print_sentences(st, reader, rules, with_unit=False):
    """长句一行，拆句候选一张表（接在句长后面）。with_unit：全书的表多一栏单元。"""
    if not st.sent_lens:
        return
    thr = int(rules.get("long_sentence_words") or DEFAULT_RULES["long_sentence_words"])
    n, p_sent, p_words = long_stats(st, thr)
    print("长句（%d 词以上）：%d 句，占 %.1f%%；这些句子的词数占全文 %.1f%%" % (thr, n, p_sent, p_words))
    mw = min_words_for(rules, reader)
    rows = drill_candidates(st, reader, mw)
    if not rows:
        print("拆句候选（%d 词以上）：没有。" % mw)
        return
    top = int(rules.get("drill_top") or DEFAULT_RULES["drill_top"])
    shown = rows[:top]
    extra = [r for r in rows[top:] if r["stuck"]]  # 排在后面的卡句也列出来
    print("拆句候选（%d 词以上，共 %d 句，按词数和从属词多少排%s）：" % (
        mw, len(rows), "，列前 %d 句" % len(shown) if len(shown) < len(rows) else ""))
    cols = ([("单元", 4)] if with_unit else []) + [("词数", 4), ("高于" + reader, 6), ("从属词", 6), ("逗号", 4)]
    print("  " + "  ".join(rjust(h, w) for h, w in cols) + "  开头")

    def row(r):
        vals = ([str(r["unit"])] if with_unit else []) + [
            str(r["words"]), "—" if r["above"] is None else str(r["above"]), str(r["subs"]), str(r["commas"])]
        print("  " + "  ".join(rjust(v, w) for v, (_, w) in zip(vals, cols)) + "  " + opening(r["sent"])
              + ("   ★卡句" if r["stuck"] else ""))

    for r in shown:
        row(r)
    if extra:
        print("  （下面 %d 句是卡句，排在前 %d 句以外）" % (len(extra), len(shown)))
        for r in extra:
            row(r)


def print_levels(st, reader):
    total = st.total_tokens()
    r = RANK[reader]
    types = Counter((k, lv) for k, lv, _ in st.types)
    print()

    def row(name, a, b, c, p, t):
        print(ljust(name, 9) + "".join(rjust(x, 9) for x in (a, b, c, p, t)))

    row("级别", "词表", "估级", "合计", "占比", "词型")
    for lv in LEVELS:
        a, b = st.tok[(LIST, lv)], st.tok[(EST, lv)]
        row(lv + (" ↑" if RANK[lv] > r else ""), format(a, ","), format(b, ","), format(a + b, ","),
            pct(a + b, total).strip(), format(types[(LIST, lv)] + types[(EST, lv)], ","))
    for name, key in (("未定级 ↑", (NONE, UNRATED)), (PROPER_NAME, (PROPER, PROPER_NAME))):
        row(name, "", "", format(st.tok[key], ","), pct(st.tok[key], total).strip(), format(types[key], ","))
    lt = sum(n for (k, _), n in st.tok.items() if k == LIST)
    et = sum(n for (k, _), n in st.tok.items() if k == EST)
    row("合计", format(lt, ","), format(et, ","), format(total, ","), "", format(len(st.types), ","))
    note = "↑ = 高于读者水平；未定级只算进上限"
    if st.skipped:
        note += "。另有 %d 个单字母、缩约残片、标题行罗马数字没有计入（%s）" % (
            sum(st.skipped.values()), "、".join(k for k, _ in st.skipped.most_common(5)))
    print("（%s）" % note)


def print_range(st, reader, rules):
    lo, mid, hi, total = above_range(st, reader)
    a, _ = level_names(reader)
    print("\n高于读者水平（%s 及以上）的词次占比：下限 %.1f%%（只算词表定级的）  中间 %.1f%%（加上估级的）"
          "  上限 %.1f%%（再加上未定级的）" % (a, pct_value(lo, total), pct_value(mid, total), pct_value(hi, total)))
    m = pct_value(mid, total)
    _, lp, _ = long_stats(st, int(rules.get("long_sentence_words") or DEFAULT_RULES["long_sentence_words"]))
    print("建议（按中间值 %.1f%%，长句占 %.1f%%）：%s只是提示，读不读、怎么读由用户定。"
          % (m, lp, advice(m, lp, rules.get("above_pct") or DEFAULT_RULES["above_pct"],
                           rules.get("long_pct") or DEFAULT_RULES["long_pct"])))


def print_proper_unrated(st, reader):
    props = sorted(((k, d["n"]) for (c, _, k), d in st.types.items() if c == PROPER), key=lambda x: (-x[1], x[0]))
    if props:
        print("\n专名（前 15）：" + "，".join("%s %d" % x for x in props[:15]))
    un = sorted(by_lemma(st, reader, lambda k, lv, rd: k == NONE).items(), key=lambda x: (-x[1]["n"], x[0]))
    if un:
        print("未定级（前 10，共 %d 个词型）：" % len(un)
              + "，".join("%s %d" % (word_with_forms(k, d, 2), d["n"]) for k, d in un[:10]))


def print_word_rows(rows, unit_count=None, marks=None):
    for key, d in rows:
        sent, s, e = d["first"]
        lab = level_label(d["kind"], d["lv"]) if d["kind"] != NONE else UNRATED
        uc = "  %d 单元" % unit_count[key] if unit_count is not None else ""
        mk = "  〔讲义已列〕" if marks and key in marks else ""
        print("  %s %s ×%-3d%s%s  %s" % (ljust(word_with_forms(key, d), 24), ljust(lab, 6), d["n"], uc, mk,
                                          snippet(sent, s, e)))


def print_preread(st, reader, rules, short_words, before, here, unit_count, before_names):
    rows, need = preread_candidates(st, reader, rules, short_words, before, here)
    top = int(rules.get("preread_top") or DEFAULT_RULES["preread_top"])
    shown = rows[:top]
    excl = "，去掉前面单元讲义列过的（%s）" % "、".join(before_names) if before_names else ""
    print("\n读前词候选：本单元出现 ≥%d 次，高于读者水平或未定级，去掉专名%s；共 %d 个%s：" % (
        need, excl, len(rows), "，列前 %d 个" % len(shown) if len(shown) < len(rows) else ""))
    if not shown:
        print("  （没有）")
    print_word_rows([(k, d) for k, d, _ in shown], unit_count, {k for k, _, m in shown if m})


def print_groups(st, reader, top, unit_count=None):
    near, far = level_groups(st, reader)
    a, b = level_names(reader)
    for label, lst in (("高一级（%s）" % a, near), ("高两级及以上（%s）" % b, far)):
        shown = lst if not top else lst[:top]
        print("\n%s，共 %d 个词型%s：" % (label, len(lst), "，列前 %d 个" % len(shown) if len(shown) < len(lst) else ""))
        print_word_rows(shown, unit_count)


def print_spread(total, reader, unit_count, n_units, limit=15):
    rows = [(k, d) for k, d in by_lemma(total, reader).items() if unit_count[k] >= 2]
    rows.sort(key=lambda x: (-unit_count[x[0]], -x[1]["n"], x[0]))
    print("\n出现单元数最多的词（高于读者水平或未定级，去掉专名；共 %d 个在两个以上单元出现%s）：" % (
        len(rows), "，列前 %d 个" % limit if len(rows) > limit else ""))
    if not rows:
        print("  （没有）")
    for k, d in rows[:limit]:
        lab = level_label(d["kind"], d["lv"]) if d["kind"] != NONE else UNRATED
        print("  %s %s %d/%d 单元  共 ×%d" % (ljust(word_with_forms(k, d), 24), ljust(lab, 6), unit_count[k],
                                             n_units, d["n"]))


def write_tsv(path, st, reader, unit_count):
    near, far = level_groups(st, reader)
    un = sorted(by_lemma(st, reader, lambda k, lv, rd: k == NONE).items(), key=lambda x: (-x[1]["n"], x[0]))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [("高一级", near), ("高两级及以上", far), (UNRATED, un)]
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("词\t级别\t依据\t档\t次数\t单元数\t例句\n")
        for band, lst in rows:
            for key, d in lst:
                sent, s, e = d["first"]
                f.write("%s\t%s\t%s\t%s\t%d\t%d\t%s\n" % (
                    key, d["lv"], KIND_NAME[d["kind"]], band, d["n"], unit_count[key],
                    snippet(sent, s, e).replace("\t", " ")))
    n = sum(len(x[1]) for x in rows)
    print("候选词已写入 %s（%d 行）" % (p, n))


def write_sent_tsv(path, stats, reader, rules):
    """全部拆句候选：单元、词数、高于水平词数（没有级别数据时空着）、从属词、逗号、原句。
    stats 是各单元的统计（先跑过 tag_sentences）；按单元，单元内的顺序同屏幕上的表。"""
    mw = min_words_for(rules, reader)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("单元\t词数\t高于水平词数\t从属词\t逗号\t原句\n")
        for st in stats:
            for r in drill_candidates(st, reader, mw):
                f.write("%s\t%d\t%s\t%d\t%d\t%s\n" % (
                    r["unit"], r["words"], "" if r["above"] is None else r["above"], r["subs"], r["commas"],
                    re.sub(r"\s+", " ", r["sent"]).strip()))
                n += 1
    print("拆句候选已写入 %s（%d 行）" % (p, n))


NOTE = ("说明：句子按规则切分，引号里的问句/感叹句后面接小写词时不切，破折号打断的对话不切，"
        "缩写表以外的“X.”后接大写词会被误切；专有名词按大写判断，句首的专名和句中的普通词大写会有少量误判。"
        "估级只看词频，动物、乡村一类的具体名词估得偏高；未定级里常混着复合词、方言和拟声词，看一眼列表再判断。")


def report_lengths_only(units, project, title, reader, reason, rules, tsv, sent_tsv=None):
    print("# 摸底：%s（读者 %s）\n" % (title, reader))
    print("注意：取不到级别数据（%s）。这次只给篇幅、句长、长句和拆句候选（高于水平的词数是 —）；"
          "级别、高于水平的占比、读法建议和候选词要等数据补齐后再跑。\n" % reason)
    stats = [length_stats(paras) for _, paras, _ in units]
    tag_sentences(units, stats, project)
    total = Stats()
    for (name, _, _), st in zip(units, stats):
        total.merge(st)
        print("## %s\n" % name)
        print_length(st)
        print_sentences(st, reader, rules)
        print()
    if len(units) > 1:
        print("## 全书（%d 个单元）\n" % len(units))
        print_length(total)
        print_sentences(total, reader, rules, with_unit=True)
        print()
    if tsv:
        print("没有写 %s：没有级别数据。" % tsv)
    if sent_tsv:
        write_sent_tsv(sent_tsv, stats, reader, rules)


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="摸底：篇幅、句长、长句和拆句候选、高于读者水平的词占多少、读法建议、读前词候选")
    ap.add_argument("path", help="项目目录（含 设置.json、原文/）或单个 .txt")
    ap.add_argument("--level", help="读者水平 A2/B1/B2/C1（默认读 设置.json，没有就 B1）")
    ap.add_argument("--top", type=int, default=30, help="「高一级」「高两级及以上」每类打印前几个（0=全部）")
    ap.add_argument("--tsv", help="把候选词写成 TSV（定计划用）：词、级别、依据、档、次数、单元数、例句")
    ap.add_argument("--sent-tsv", help="把全部拆句候选写成 TSV（定计划用）：单元、词数、高于水平词数、从属词、逗号、原句")
    ap.add_argument("--cache", help=argparse.SUPPRESS)  # 第一版的参数；级别数据离线，用不到缓存
    ap.add_argument("--refresh", action="store_true", help=argparse.SUPPRESS)  # 同上
    args = ap.parse_args(argv)

    units, project, unit = read_units(args.path)
    cfg = load_config(project)
    reader = (args.level or (cfg or {}).get("level") or "B1").upper()
    if reader not in READER_LEVELS:
        raise SystemExit("错误：读者水平只能是 %s–%s，现在是 %r" % (READER_LEVELS[0], READER_LEVELS[-1], reader))
    title = (cfg or {}).get("title") or Path(args.path).name
    rules, short_words = load_rules()

    try:
        lex = Lexicon(project=project, offline=True)  # 只用离线的级别数据
        prof = Profiler(lex, units)
        stats = [prof.unit(paras) for _, paras, _ in units]
    except LexiconError as e:
        report_lengths_only(units, project, title, reader, e, rules, args.tsv, args.sent_tsv)
        return
    tag_sentences(units, stats, project)

    unit_count = Counter()
    for st in stats:
        for key in {k for (kind, _, k) in st.types if kind != PROPER}:
            unit_count[key] += 1
    multi = len(units) > 1
    uc = unit_count if multi else None

    listed = lecture_lists(project, unit)  # 讲义里列过的读前词：编号 → 词头

    print("# 摸底：%s（读者 %s）\n" % (title, reader))
    total = Stats()
    for (name, paras, n), st in zip(units, stats):
        total.merge(st)
        print("## %s\n" % name)
        print_length(st)
        print_sentences(st, reader, rules)
        print_levels(st, reader)
        print_range(st, reader, rules)
        print_proper_unrated(st, reader)
        before_n = sorted(k for k in listed if n is not None and k < n and listed[k])
        before = listed_keys([h for k in before_n for h in listed[k]], lex)
        here = listed_keys(listed.get(n, []) if n is not None else [], lex)
        before_names = ["第 %d %s" % (k, unit) for k in before_n]
        print_preread(st, reader, rules, short_words, before, here, uc, before_names)
        print_groups(st, reader, args.top, uc)
        print()
    if multi:
        print("## 全书（%d 个单元）\n" % len(units))
        print_length(total)
        print_sentences(total, reader, rules, with_unit=True)
        print_levels(total, reader)
        print_range(total, reader, rules)
        print_proper_unrated(total, reader)
        print_spread(total, reader, unit_count, len(units))
        print_groups(total, reader, args.top, uc)
        print()
    print(NOTE)
    if args.tsv:
        write_tsv(args.tsv, total, reader, unit_count)
    if args.sent_tsv:
        write_sent_tsv(args.sent_tsv, stats, reader, rules)


if __name__ == "__main__":
    main()
