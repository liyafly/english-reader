#!/usr/bin/env python3
"""词级与词典：CEFR 级别、词形还原、词条核对（第二版，替代第一版的 oxford.py）。

用法：
  lexicon.py level WORD… [--pos v]          给级别和来源
  lexicon.py entry WORD [--pos v] [--json] [--source macos|wiktionary|ecdict]
                                            查词条：英式音标（原样和换算后）、词性、语体标签、义项
  lexicon.py check 讲义.md [--level B1] [--source …]
                                            核对「## 词的用法」每条的「词典：」行和「## 读前」→「### 本章的词」
                                            的 `- **word** /ipa/ pos. 释义` 行；不给 --level 时读项目的 设置.json，没有就 B1
共同参数：--cache DIR（默认 项目/.cache/lexicon/，找不到项目时 ./.cache/lexicon/）
          --refresh（联网来源不用缓存）  --offline（不联网）

级别（离线；数据在 scripts/data/，出处、许可、生成方法见 scripts/data/README.md）：
  1. CEFR-J Vocabulary Profile 1.5（A1–B2）和 Octanove Vocabulary Profile C1/C2 1.0。先查原词，再查原形
     （ECDICT 变形表 → 不规则表 → 后缀规则），原词和原形都收了时取低的一级（同级用原词）。
     一个词有几个词性：给了 pos 就按 pos；没给取最低一级，并在来源里写明。
  2. 两个表都没收：按 ECDICT 子集里的 COCA 名次估级，来源以“估”开头，门槛见 EST_THRESHOLDS。
  3. 名次也没有：未定级（UNRATED）。不给“会用/认得”建议。
  英式拼写：ECDICT 的名次来自美国语料。原词没进词表（估级或未定级）时，试美式写法（american_variants：-our → -or、
  -ise → -ize、-yse → -yze、辅音后的 -re → -er、变形里的 -ll- → -l-、-ogue → -og，外加 BRIT_EXCEPTIONS 小例外表），
  美式写法在数据里存在、且结果明显更好（进了词表，或名次好一倍以上）才用；how 和来源写「英式拼写 coloured → colored」，
  原形尽量还写英式（colour）。名次（rank）同理。

词条（按顺序试，结果注明来源）：
  设置.json 的 dictionaries（本地词典文件：这一版只留位置，返回“不支持，下一轮实现”）
  → macOS 系统词典（牛津英汉汉英词典取英式音标、词性、语体标签、中文义项；Oxford Dictionary of English
    取音标和标签。用的是 DictionaryServices 的未公开接口，非 macOS 或调用失败时自动跳过）
  → dictionaryapi.dev（数据来自 Wiktionary，CC BY-SA 3.0；没有语体标签字段，标签从释义文字里找）
  → ECDICT 子集的音标（只作参考）→ 都没有：未核对。

音标：讲义用 Oxford Learner's 和国内教材的写法。其他来源先按 IPA_TABLE 换算再比；括号里的可省音
（(ə)、(t)、(r)）有和没有两种读法都算。结果：一致、仅写法不同、不一致、参考、未核对。

会用/认得（check）：比读者高一级 → 会用；高两级及以上，或整条词带 formal、literary、old-fashioned、
dated 等标签 → 认得；估级的注明“估”；未定级不给建议。词典行写的词性词表里没有（common n.，词表只有形容词）：
熟词生义，不拿别的词性的级别给建议，写「—（熟词生义：词表没有这个词性）」，不标 !掌握（level_info 的 pos_missing）。

标签说法（check）：词条首行、搭配/辨析/注意/例/词族行、词典行、读前释义里的“英式”“美式/北美”“正式/书面”
“旧式/过时/老式”“口语/非正式”“委婉”“俚语”“文学”（LABEL_CLAIMS），词典这个词条任何义项都没有对应标签的标 !标签
（短语词头按短语那一块；词条的 all_labels）。词典行和释义只认括号里的；一小段话提到了别的英文词（“美式英语用
cheap”），算说那个词，不核对；前面是“不是”“不算”的不报。只有系统词典能判“没有”；Wiktionary 没找到、只有 ECDICT
或没有来源时标“标签未核对”。
"""
import argparse
import csv
import gzip
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True  # 不在 skill 目录里留 __pycache__

# ================================================================ 常量

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
RANK = {lv: i + 1 for i, lv in enumerate(LEVELS)}
UNRATED = "未定级"

# ECDICT 名次（COCA，frq 列的值）估级：名次 < 门槛 → 该级；子集里其余的 → EST_TOP
EST_THRESHOLDS = ((1000, "A1"), (2000, "A2"), (4000, "B1"), (8000, "B2"), (14000, "C1"))
EST_TOP = "C2"

# “认得”的语体标签（informal 不算）
FORMALISH_RE = re.compile(r"(?<![a-z-])(formal|literary|poetic(?:al)?|old-fashioned|dated|archaic|old use)\b", re.I)

STATUSES = ("一致", "仅写法不同", "不一致", "参考", "未核对")
SOURCES = ("macos", "wiktionary", "ecdict")

DATA_DIR = Path(__file__).resolve().parent / "data"
CEFRJ_FILE = "cefrj-vocabulary-profile-1.5.csv"
OCTANOVE_FILE = "octanove-vocabulary-profile-c1c2-1.0.csv"
ECDICT_FILE = "ecdict-subset.tsv.gz"

MAC_EC = "牛津英汉汉英词典"
MAC_ODE = "Oxford Dictionary of English"
WIKT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
USER_AGENT = "english-reader/3.0"
REQUEST_INTERVAL = 1.0  # 两次联网请求至少间隔几秒

SETTINGS_FILE = "设置.json"


class LexiconError(Exception):
    """级别数据缺失或读不了。"""


# ================================================================ 词性

POS_FAMILY = {
    "n": "noun", "noun": "noun", "plural noun": "noun",
    "v": "verb", "vt": "verb", "vi": "verb", "verb": "verb", "vern": "verb",
    "transitive verb": "verb", "intransitive verb": "verb", "be-verb": "verb", "do-verb": "verb",
    "have-verb": "verb", "modal auxiliary": "verb", "modal verb": "verb", "auxiliary verb": "verb",
    "aux": "verb", "modal": "verb", "phrasal verb": "verb",
    "adj": "adjective", "a": "adjective", "adjective": "adjective",
    "adv": "adverb", "adverb": "adverb",
    "prep": "preposition", "preposition": "preposition",
    "conj": "conjunction", "conjunction": "conjunction",
    "pron": "pronoun", "pronoun": "pronoun",
    "det": "determiner", "determiner": "determiner", "article": "determiner",
    "num": "number", "number": "number", "numeral": "number",
    "int": "exclamation", "interj": "exclamation", "exclam": "exclamation",
    "interjection": "exclamation", "exclamation": "exclamation",
    "infinitive-to": "infinitive marker",
    "phr": "phrase", "phrase": "phrase", "idiom": "phrase",
    "abbr": "abbreviation", "abbreviation": "abbreviation",
}


def pos_family(p):
    """n / v. / vi / noun / 'intransitive verb' / be-verb … → noun、verb、adjective 等；认不出的原样返回（小写）。"""
    if not p:
        return None
    p = re.sub(r"\s+", " ", str(p).strip().lower().rstrip("."))
    if p in POS_FAMILY:
        return POS_FAMILY[p]
    for key in ("verb", "noun", "adjective", "adverb", "preposition", "pronoun", "conjunction"):
        if key in p:
            return key
    return p


def transitivity(p):
    """'vt'/'transitive verb' → 't'，'vi'/'intransitive verb' → 'i'，其他 None。"""
    p = (p or "").strip().lower().rstrip(".")
    if p in ("vt", "transitive verb"):
        return "t"
    if p in ("vi", "intransitive verb"):
        return "i"
    return None


# ================================================================ 词形：不规则表和后缀规则（第一版沿用，作兜底）

IRREGULAR_VERBS = """
be am is are was were been being|have has had having|do does did done|go goes went gone
say said|make made|get got gotten|know knew known|think thought|take took taken|see saw seen
come came|give gave given|find found|tell told|become became|leave left|feel felt|bring brought
begin began begun|keep kept|hold held|write wrote written|stand stood|hear heard|mean meant
meet met|run ran|pay paid|sit sat|speak spoke spoken|lie lay lain|lead led|grow grew grown
lose lost|fall fell fallen|send sent|build built|understand understood|draw drew drawn
break broke broken|spend spent|rise rose risen|drive drove driven|buy bought|wear wore worn
choose chose chosen|seek sought|throw threw thrown|catch caught|deal dealt|win won
forget forgot forgotten|lay laid|sell sold|fight fought|eat ate eaten|teach taught
sing sang sung|swim swam swum|drink drank drunk|ring rang rung|sink sank sunk|shrink shrank shrunk
spring sprang sprung|fly flew flown|hide hid hidden|ride rode ridden|shake shook shaken
steal stole stolen|strike struck stricken|swear swore sworn|tear tore torn|bear bore borne born
wake woke woken|weave wove woven|freeze froze frozen|forgive forgave forgiven|bite bit bitten
blow blew blown|beat beaten|bend bent|bind bound|bleed bled|breed bred|burn burnt|dig dug
dream dreamt|feed fed|flee fled|fling flung|forbid forbade forbidden|forbear forbore forborne
grind ground|hang hung|kneel knelt|lean leant|leap leapt|learn learnt|light lit|shine shone
shoot shot|slay slew slain|sleep slept|slide slid|sling slung|slink slunk|smell smelt|speed sped
spell spelt|spill spilt|spin spun|spit spat|spoil spoilt|stick stuck|sting stung
stride strode stridden|strive strove striven|swell swollen|swing swung|sweep swept
tread trod trodden|undertake undertook undertaken|wind wound|withdraw withdrew withdrawn
wring wrung|weep wept|creep crept|cling clung|dwell dwelt|arise arose arisen|awake awoke awoken
behold beheld|bid bade|overcome overcame|mislead misled|shed|stink stank stunk|sew sewn
show shown|sow sown|mow mown|saw sawn|swear swore|lend lent|build built|can could|will would
shall should|may might|forsake forsook forsaken|befall befell befallen|beget begot begotten
"""
IRREGULAR_OTHER = {
    "men": "man", "women": "woman", "children": "child", "feet": "foot", "teeth": "tooth",
    "mice": "mouse", "geese": "goose", "oxen": "ox", "lives": "life", "wives": "wife",
    "knives": "knife", "leaves": "leaf", "halves": "half", "selves": "self", "wolves": "wolf",
    "shelves": "shelf", "loaves": "loaf", "thieves": "thief", "calves": "calf",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad", "further": "far",
    "furthest": "far", "farther": "far", "farthest": "far", "elder": "old", "eldest": "old",
    "an": "a", "o": "oh", "these": "this", "those": "that", "others": "other",
    "lying": "lie", "dying": "die", "tying": "tie",
}


def _build_irregular():
    table = dict(IRREGULAR_OTHER)
    for group in IRREGULAR_VERBS.replace("\n", "|").split("|"):
        forms = group.split()
        for f in forms[1:]:
            table.setdefault(f, forms[0])
    return table


IRREGULAR = _build_irregular()

# (后缀, 替换, 原形须有的词性, 说明)；替换为 * 表示去掉双写的辅音（stopped → stop）
SUFFIX_RULES = [
    ("ies", "y", {"noun", "verb"}, "-ies"), ("ied", "y", {"verb"}, "-ied"),
    ("iest", "y", {"adjective", "adverb"}, "-iest"), ("ier", "y", {"adjective", "adverb"}, "-ier"),
    ("ily", "y", {"adjective"}, "-ly"),
    ("es", "", {"noun", "verb"}, "-es"), ("s", "", {"noun", "verb"}, "-s"),
    ("ed", "e", {"verb"}, "-ed"), ("ed", "", {"verb"}, "-ed"), ("ed", "*", {"verb"}, "-ed"),
    ("ing", "e", {"verb"}, "-ing"), ("ing", "", {"verb"}, "-ing"), ("ing", "*", {"verb"}, "-ing"),
    ("est", "e", {"adjective", "adverb"}, "-est"), ("est", "", {"adjective", "adverb"}, "-est"),
    ("est", "*", {"adjective", "adverb"}, "-est"),
    ("er", "e", {"adjective", "adverb"}, "-er"), ("er", "", {"adjective", "adverb"}, "-er"),
    ("er", "*", {"adjective", "adverb"}, "-er"),
    ("ically", "ic", {"adjective"}, "-ly"), ("ly", "", {"adjective"}, "-ly"),
    ("ly", "le", {"adjective"}, "-ly"),
]
DERIVATIONAL = {"-ly"}  # 派生，不算变形：定级时不拆（presently ≠ present）
CLITIC_SPECIAL = {"can't": "can", "won't": "will", "shan't": "shall", "ain't": "be"}

# 单音节、单元音、单辅音结尾（scrap、hop）：加 -ed/-ing/-er/-est 时要双写，所以 scraped 不会来自 scrap
CVC_RE = re.compile(r"[^aeiou]*[aeiou][^aeiouwxy]")


def rule_candidates(w):
    """按后缀规则列出可能的原形：[(原形, 原形须有的词性, 依据)]，不查词表。"""
    out = []
    for suf, rep, need, how in SUFFIX_RULES:
        if not w.endswith(suf) or len(w) - len(suf) < 2:
            continue
        stem = w[: -len(suf)]
        if suf == "s" and w.endswith("ss"):
            continue
        if rep == "*":
            if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiouy":
                cand = stem[:-1]
            else:
                continue
        else:
            if rep == "" and suf in ("ed", "ing", "er", "est") and CVC_RE.fullmatch(stem):
                continue
            cand = stem + rep
        out.append((cand, need, how))
    return out


def norm_word(w):
    """查表用的键：小写、弯撇号变直撇号、空白归一。"""
    w = unicodedata.normalize("NFC", str(w or "")).replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", w).strip().lower()


# ================================================================ 英式拼写 → 美式拼写
# ECDICT 的名次来自美国语料（COCA），英式拼写常常名次很差或干脆没有；CEFR-J 多数并列两种写法（color/colour），
# 但不全（parlour、gipsy 只收了美式）。原词查不到、或名次明显差时，试美式写法。

# 小例外表：(英式开头, 美式开头, 后面还能接的)；只换词首这一段
BRIT_EXCEPTIONS = (
    ("grey", "gray", r"(?:s|ed|ing|er|est|ish|ness|ly)?"),
    ("gipsy", "gypsy", r"(?:'s)?"), ("gipsies", "gypsies", ""),
    ("plough", "plow", r"(?:s|ed|ing|man|men|share|shares)?"),
    ("programme", "program", r"(?:s)?"),
    ("pyjama", "pajama", r"(?:s)?"), ("jewellery", "jewelry", ""), ("aeroplane", "airplane", r"(?:s)?"),
    ("moustache", "mustache", r"(?:s|d)?"), ("sceptic", "skeptic", r"(?:s|al|ally|ism)?"),
    ("mould", "mold", r"(?:s|ed|ing|y|er|ier|iest)?"), ("smoulder", "smolder", r"(?:s|ed|ing)?"),
    ("defence", "defense", r"(?:s|less)?"), ("offence", "offense", r"(?:s)?"), ("pretence", "pretense", r"(?:s)?"),
)
# 美式写法恰好是另一个词的，不换（timbre ≠ timber）
NOT_BRITISH = {"timbre", "timbres"}
_VOWELS = set("aeiouy")


def _brit_our(w):
    m = re.search(r"(?<=[a-z]{2})our(?=[a-z]*$)", w)
    return w[:m.start()] + "or" + w[m.end():] if m else None


def _brit_ise(w):
    m = re.fullmatch(r"([a-z]{3,})is(e|es|ed|ing|er|ers|ation|ations)", w)
    return m.group(1) + "iz" + m.group(2) if m else None


def _brit_yse(w):
    m = re.fullmatch(r"([a-z]{2,})ys(e|es|ed|ing|er|ers)", w)
    return m.group(1) + "yz" + m.group(2) if m else None


def _brit_re(w):
    """辅音 + re 结尾：centre → center，centres → centers，centred → centered。more、here、fire、are 不动。"""
    m = re.fullmatch(r"([a-z]{2,}[bcdgkmnptv])re(s|d)?", w)
    if not m:
        return None
    tail = {"s": "s", "d": "ed"}.get(m.group(2) or "", "")
    return m.group(1) + "er" + tail


def _brit_ll(w):
    """变形里的 -ll-：travelled → traveled，traveller → traveler，marvellous → marvelous。
    ll 前面是元音、再前面还有元音（多音节）才换，killed、filled、smaller 不动。"""
    m = re.fullmatch(r"([a-z]+)ll(ed|ing|er|ers|or|ors|ous)", w)
    if not m:
        return None
    stem = m.group(1)
    if stem[-1] not in _VOWELS or not (set(stem[:-1]) & _VOWELS):
        return None
    return stem + "l" + m.group(2)


def _brit_ogue(w):
    m = re.fullmatch(r"([a-z]{2,})ogue(s|d)?", w)
    if not m:
        return None
    return m.group(1) + "og" + {"s": "s", "d": "ed"}.get(m.group(2) or "", "")


BRIT_RULES = (("-our → -or", _brit_our), ("-ise → -ize", _brit_ise), ("-yse → -yze", _brit_yse),
              ("-re → -er", _brit_re), ("-ll- → -l-", _brit_ll), ("-ogue → -og", _brit_ogue))


def american_variants(word):
    """英式拼写 → 可能的美式写法：[(美式, [规则])]，规则用得多的排前面。不查词表，用的人自己确认美式写法存在。
    例外表命中就只给例外表的结果。four、hour、your（-our 前面不到两个字母）和 more、here、fire、are
    （re 前面是元音）不会产生候选。"""
    w = norm_word(word)
    if not w or " " in w or w in NOT_BRITISH:
        return []
    for brit, am, tail in BRIT_EXCEPTIONS:
        if w.startswith(brit) and re.fullmatch(tail, w[len(brit):]):
            return [(am + w[len(brit):], ["例外表 %s → %s" % (brit, am)])]
    steps = []
    cur, used = w, []
    for name, fn in BRIT_RULES:
        new = fn(cur)
        if new and new != cur:
            cur = new
            used = used + [name]
            steps.append((cur, used))
    return list(reversed(steps))


# ================================================================ 数据

INF = float("inf")
FORM_KEYS = set("pdi3rts")  # ECDICT exchange 的变形类型


def read_profile_csv(path, source):
    """CEFR-J / Octanove 的 CSV → {词: [(词性族, 级别, 来源, 原词性)]}；headword 里的 / 是并列写法。"""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            lv = (row.get("CEFR") or "").strip().upper()
            if lv not in RANK:
                continue
            raw_pos = (row.get("pos") or "").strip()
            fam = pos_family(raw_pos) or ""
            for hw in (row.get("headword") or "").split("/"):
                key = norm_word(hw)
                if key:
                    rec = (fam, lv, source, raw_pos)
                    lst = out.setdefault(key, [])
                    if rec not in lst:
                        lst.append(rec)
    return out


def read_ecdict_subset(path):
    """ecdict-subset.tsv.gz → {词: (frq, bnc, exchange, phonetic)}。"""
    rows = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        rd = csv.reader(f, delimiter="\t")
        header = next(rd, None)
        if not header or header[:5] != ["word", "frq", "bnc", "exchange", "phonetic"]:
            raise LexiconError("%s 的表头不对：%r" % (path, header))
        for r in rd:
            if len(r) < 5 or not r[0]:
                continue
            try:
                rows[r[0]] = (int(r[1] or 0), int(r[2] or 0), r[3], r[4])
            except ValueError:
                continue
    return rows


def exchange_items(ex):
    for item in (ex or "").split("/"):
        k, sep, v = item.partition(":")
        if sep and v.strip():
            yield k.strip(), norm_word(v)


# ECDICT 变形类型 → 原形该有的词性（判断词表里的原形对不对得上）
FORM_POS = {"p": {"verb"}, "d": {"verb"}, "i": {"verb"}, "3": {"verb"}, "s": {"noun"},
            "r": {"adjective", "adverb"}, "t": {"adjective", "adverb"}}


def listed_fits(listed_rows, need):
    """词表里的这个词有没有需要的词性：listed_rows 是 CEFR-J/Octanove 的 [(词性族, …)]；need 为空时收了就算。"""
    if not listed_rows:
        return False
    return not need or any(r[0] in need for r in listed_rows)


def build_lemma_map(rows, listed=None):
    """ECDICT 的 exchange → {变形: 原形}，做三条清理：

    1. 假变形：变形本身比“原形”还常见（COCA 名次更靠前）就不算（number 不算 numb 的比较级，
       ground 不算 grind 的过去式）。一个变形有几个原形时，先挑 CEFR-J/Octanove 词表收了、词性也对得上的
       （listed 给了才挑：distilling 取词表里的动词 distill；premiered 不取 premier，词表里它只是名词、
       形容词），再取最常见的原形（does → do，不是 doe），没有名次的排最后。
    2. 压平链条：A → B → C 记成 A → C。中间的 B 如果本身是有名次的词（found、better），就停在 B，
       免得 founded → found → find。
    3. 去掉循环：A → B → … → A 的都不要。
    """
    def rank(w):
        r = rows.get(w)
        return r[0] if r and r[0] > 0 else INF

    cands = {}  # 变形 → {原形: 变形类型}
    for w, (_, _, ex, _) in rows.items():
        items = list(exchange_items(ex))
        for k, v in items:
            if k in FORM_KEYS and v != w:
                cands.setdefault(v, {}).setdefault(w, set()).add(k)
            elif k == "0" and v != w:
                types = "".join(t for kk, t in items if kk == "1")  # 1:dp → 过去分词、过去式
                cands.setdefault(w, {}).setdefault(v, set()).update(types)
    edges = {}
    for form, lemmas in cands.items():
        ok = [l for l in lemmas if not rank(form) < rank(l)]
        if listed and len(ok) > 1:
            fit = [l for l in ok
                   if listed_fits(listed.get(l), set().union(*(FORM_POS.get(t, set()) for t in lemmas[l])))]
            ok = fit or ok
        if ok:
            edges[form] = min(ok, key=lambda l: (rank(l), l))
    final = {}
    for form, target in edges.items():
        path = [form]
        cur = target
        while cur in edges and rank(cur) == INF and cur not in path:
            path.append(cur)
            cur = edges[cur]
        if cur in path:
            continue
        final[form] = cur
    return final


def est_level(rank):
    """COCA 名次 → 估计的级别。"""
    for limit, lv in EST_THRESHOLDS:
        if rank < limit:
            return lv
    return EST_TOP


# ================================================================ 项目、设置、缓存

def find_project(start, depth=4):
    """从 start 往上找含 设置.json 的目录（最多 depth 层）。"""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    for d in [p] + list(p.parents)[:depth]:
        if (d / SETTINGS_FILE).is_file():
            return d
    return None


def load_settings(project):
    if not project:
        return {}
    try:
        with open(Path(project) / SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def default_cache(project=None):
    return (Path(project) if project else Path.cwd()) / ".cache" / "lexicon"


# ================================================================ 音标

# 来源写法 → Oxford Learner's / 国内教材写法，按顺序替换；另外 /a/（不在 aɪ、aʊ 里）→ /æ/
IPA_TABLE = (
    ("ʌɪ", "aɪ"),
    ("ɛː", "eə"),
    ("ɛə", "eə"),
    ("ɛ", "e"),
    ("əː", "ɜː"),
)
A_RE = re.compile(r"a(?![ɪʊ])")

# ECDICT 的老写法（ASCII 撇号重音、冒号长音、西里尔字母 ә/є、ɒ: 表示 ɔː、ɔ 表示 ɒ、ei/ai/au/əu 等双元音），
# 按顺序做正则替换。ECDICT 的写法本来就混杂，换算后也只作参考。
ECDICT_FIX = ((r"'", "ˈ"), (r",", "ˌ"), (r":", "ː"), (r"ә", "ə"), (r"є", "e"), (r"ɚ", "ər"),
              (r"ɔ(?!ː)", "ɒ"), (r"ɒː", "ɔː"), (r"əu", "əʊ"), (r"ou", "əʊ"), (r"ei", "eɪ"), (r"ai", "aɪ"),
              (r"au", "aʊ"), (r"[ɔɒ]i", "ɔɪ"), (r"iə", "ɪə"), (r"uə", "ʊə"))


def ipa_strip(s):
    """去掉首尾斜线/方括号、空白、音节点和连音符。"""
    s = unicodedata.normalize("NFC", str(s or "")).strip()
    s = s.strip("/[] \t")
    s = re.sub(r"\s+", "", s)
    return s.replace(".", "").replace("‿", "")


def ipa_key(s):
    """比较用：ɡ/g 不分，ɹ 当 r，ɫ 当 l。"""
    return s.replace("ɡ", "g").replace("ɹ", "r").replace("ɫ", "l")


def to_oxford(ipa, kind=None):
    """把来源的英式音标换成 Oxford Learner's 写法。返回 (换算后, [做了的替换])。"""
    s = ipa_strip(ipa)
    changes = []
    if kind == "ecdict":
        for a, b in ECDICT_FIX:
            s = re.sub(a, b, s)
    for a, b in IPA_TABLE:
        if a in s:
            s = s.replace(a, b)
            changes.append("%s→%s" % (a, b))
    if A_RE.search(s):
        s = A_RE.sub("æ", s)
        changes.append("a→æ")
    return s, changes


def ipa_variants(s, limit=256):
    """括号里的可省音有和没有两种都算：ˈlʌn(t)ʃ(ə)n → {ˈlʌnʃn, ˈlʌntʃn, ˈlʌnʃən, ˈlʌntʃən}。"""
    out = {""}
    for part in re.split(r"(\([^()]*\))", s):
        if part.startswith("(") and part.endswith(")"):
            inner = part[1:-1]
            out = {o + x for o in out for x in ("", inner)}
        else:
            out = {o + part for o in out}
        if len(out) > limit:
            break
    return {o.replace("(", "").replace(")", "") for o in out}


def compare_ipa(lecture, raw_list, kind):
    """讲义音标和来源的英式音标比。返回 (状态, 说明, 对上的来源音标)。

    kind: 'macos' / 'wiktionary' / 'local' → 一致、仅写法不同、不一致；'ecdict' → 参考；None → 未核对。
    一致：讲义和来源原样相同，且来源原样就是 Oxford Learner's 写法；仅写法不同：来源换算后才相同；
    讲义照抄来源写法（/kat/）而换算后对不上（/kæt/），算不一致。"""
    if kind is None:
        return "未核对", "没有可用的词典来源", ""
    if not lecture:
        return "未核对", "讲义没写音标", ""
    if not raw_list:
        return ("参考" if kind == "ecdict" else "未核对"), "来源里没有这个词的音标", ""
    mine = ipa_variants(ipa_key(ipa_strip(lecture)))
    if kind == "ecdict":
        for raw in raw_list:
            conv, _ = to_oxford(raw, "ecdict")
            if mine & ipa_variants(ipa_key(conv)):
                return "参考", "与 ECDICT 音标相同（ECDICT 只作参考，不算核对过）", raw
        return "参考", "与 ECDICT 音标不同（ECDICT 只作参考，不算核对过）", raw_list[0]
    hit = None
    for raw in raw_list:
        conv, changes = to_oxford(raw, kind)
        if mine & ipa_variants(ipa_key(conv)):
            if mine & ipa_variants(ipa_key(ipa_strip(raw))):
                return "一致", "", raw
            hit = hit or (raw, changes)
    if hit:
        return "仅写法不同", "换算 " + "、".join(hit[1]), hit[0]
    note = []
    for raw in raw_list:  # 讲义照抄了来源的写法（/kat/），没换成 Oxford Learner's 写法（/kæt/）
        if mine & ipa_variants(ipa_key(ipa_strip(raw))):
            note.append("讲义用的是来源写法 /%s/，按 Oxford Learner's 写法应为 /%s/" % (raw, to_oxford(raw, kind)[0]))
            break
    s = ipa_strip(lecture)
    if ":" in s:
        note.append("讲义用了 ASCII 冒号 :（应为 ː）")
    if "'" in s:
        note.append("讲义用了 ASCII 撇号 '（重音应为 ˈ）")
    return "不一致", "；".join(note), ""


# ================================================================ HTML 小解析器（系统词典的词条是 XHTML）

class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    def classes(self):
        return set((self.attrs.get("class") or "").split())

    def has(self, *names):
        return bool(self.classes() & set(names))

    def iter(self, stop=()):
        """深度优先遍历；class 在 stop 里的节点和它的子树都跳过（根节点除外）。"""
        stack = [self]
        first = True
        while stack:
            n = stack.pop()
            if not first and stop and n.classes() & set(stop):
                continue
            first = False
            yield n
            stack.extend(c for c in reversed(n.children) if isinstance(c, Node))

    def find_all(self, cls=None, tag=None, stop=()):
        return [n for n in self.iter(stop) if (cls is None or cls in n.classes()) and (tag is None or n.tag == tag)]

    def find(self, cls=None, tag=None, stop=()):
        for n in self.iter(stop):
            if (cls is None or cls in n.classes()) and (tag is None or n.tag == tag):
                return n
        return None

    def ancestors(self):
        a = self.parent
        while a is not None:
            yield a
            a = a.parent

    def inside(self, *names, until=None):
        for a in self.ancestors():
            if a is until:
                return False
            if a.has(*names):
                return True
        return False

    def text(self, skip=()):
        out = []

        def walk(n):
            for c in n.children:
                if isinstance(c, Node):
                    if skip and c.classes() & set(skip):
                        continue
                    walk(c)
                else:
                    out.append(c)
        walk(self)
        return re.sub(r"\s+", " ", "".join(out)).strip()


VOID_TAGS = {"br", "img", "meta", "link", "hr", "input", "col", "area", "base", "wbr"}


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID_TAGS:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(text):
    b = _TreeBuilder()
    b.feed(text)
    b.close()
    return b.root


def _dedupe(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _clean_label(s):
    s = re.sub(r"\s+", " ", s or "").strip().strip("()[],;: ").strip()
    return s


def _common_labels(sense_label_lists):
    """每个义项都有的标签（整条词的标签）。"""
    if not sense_label_lists:
        return []
    common = set(sense_label_lists[0])
    for lst in sense_label_lists[1:]:
        common &= set(lst)
    return [l for l in sense_label_lists[0] if l in common]


# ================================================================ macOS 系统词典

class MacDictionary:
    """用 ctypes 调 DictionaryServices。DCSCopyAvailableDictionaries 等是未公开接口，
    系统升级可能失效：任何一步失败都只是 available=False，不抛异常。"""

    _DS_PATH = "/System/Library/Frameworks/CoreServices.framework/Frameworks/DictionaryServices.framework/DictionaryServices"
    _UTF8 = 0x08000100

    def __init__(self):
        self.available = False
        self.error = ""
        self._dicts = {}
        if sys.platform != "darwin":
            self.error = "不是 macOS"
            return
        try:
            self._load()
            self.available = bool(self._dicts)
            if not self.available:
                self.error = "没有找到系统词典"
        except Exception as e:  # noqa: BLE001  任何失败都降级
            self.error = "%s: %s" % (type(e).__name__, e)
            self._dicts = {}

    def _load(self):
        import ctypes
        import ctypes.util
        vp = ctypes.c_void_p
        cf_path = ctypes.util.find_library("CoreFoundation")
        if not cf_path:
            raise OSError("找不到 CoreFoundation")
        CF = ctypes.cdll.LoadLibrary(cf_path)
        DS = ctypes.cdll.LoadLibrary(self._DS_PATH)
        for name, res, args in (
                ("CFStringCreateWithCString", vp, [vp, ctypes.c_char_p, ctypes.c_uint32]),
                ("CFStringGetLength", ctypes.c_long, [vp]),
                ("CFStringGetCString", ctypes.c_bool, [vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
                ("CFSetGetCount", ctypes.c_long, [vp]),
                ("CFSetGetValues", None, [vp, ctypes.POINTER(vp)]),
                ("CFArrayGetCount", ctypes.c_long, [vp]),
                ("CFArrayGetValueAtIndex", vp, [vp, ctypes.c_long]),
                ("CFRelease", None, [vp])):
            f = getattr(CF, name)
            f.restype, f.argtypes = res, args
        for name, res, args in (
                ("DCSCopyAvailableDictionaries", vp, []),
                ("DCSDictionaryGetName", vp, [vp]),
                ("DCSCopyRecordsForSearchString", vp, [vp, vp, vp, vp]),
                ("DCSRecordCopyData", vp, [vp, ctypes.c_long])):
            f = getattr(DS, name)
            f.restype, f.argtypes = res, args
        self._ct, self._CF, self._DS = ctypes, CF, DS
        dset = DS.DCSCopyAvailableDictionaries()
        if not dset:
            return
        self._dset = dset  # 词典对象归这个集合所有，留着不释放
        n = CF.CFSetGetCount(dset)
        arr = (vp * n)()
        CF.CFSetGetValues(dset, arr)
        for d in arr:
            name = self._str(DS.DCSDictionaryGetName(d))
            if name:
                self._dicts[name] = d

    def _str(self, cf):
        if not cf:
            return None
        n = self._CF.CFStringGetLength(cf) * 4 + 1
        buf = self._ct.create_string_buffer(n)
        if not self._CF.CFStringGetCString(cf, buf, n, self._UTF8):
            return None
        return buf.value.decode("utf-8", "replace")

    def names(self):
        return sorted(self._dicts)

    def has(self, name):
        return name in self._dicts

    def lookup(self, name, query):
        """返回该词典里 query 的全部记录（词条 HTML 列表）；词典不在或查不到返回 []。"""
        d = self._dicts.get(name)
        if d is None or not query:
            return []
        CF, DS = self._CF, self._DS
        try:
            s = CF.CFStringCreateWithCString(None, query.encode("utf-8"), self._UTF8)
            if not s:
                return []
            try:
                recs = DS.DCSCopyRecordsForSearchString(d, s, None, None)
            finally:
                CF.CFRelease(s)
            if not recs:
                return []
            out = []
            try:
                for i in range(CF.CFArrayGetCount(recs)):
                    data = DS.DCSRecordCopyData(CF.CFArrayGetValueAtIndex(recs, i), 0)
                    if data:
                        try:
                            html = self._str(data)
                        finally:
                            CF.CFRelease(data)
                        if html:
                            out.append(html)
            finally:
                CF.CFRelease(recs)
            return out
        except Exception:  # noqa: BLE001
            return []


def _headword(root, hw_container_cls):
    box = root.find(hw_container_cls)
    hw = (box or root).find("hw")
    if hw is None:
        ent = root.find(tag="d:entry")
        return (ent.attrs.get("d:title", "") if ent is not None else "").strip()
    return hw.text(skip=("ty_hom",)).strip()


def _ipa_from(prx_nodes):
    out = []
    for prx in prx_nodes:
        if prx.attrs.get("dialect", "BrE") != "BrE":
            continue
        for ph in prx.find_all("ph"):
            t = ph.text(skip=("gp",))
            if t and t not in out:
                out.append(t)
    return out


def _labels_ec(node, stop):
    """牛津英汉汉英：lg（括号里的一组，如 mainly British、formal or literary）、lev（语体）、reg（地区）。"""
    out = []

    def walk(n):
        for c in n.children:
            if not isinstance(c, Node):
                continue
            cl = c.classes()
            if cl & set(stop):
                continue
            if "lg" in cl:
                out.append(_clean_label(c.text(skip=("gp",))))
                continue
            if cl & {"lev", "reg"}:
                out.append(_clean_label(c.text(skip=("gp",))))
                continue
            walk(c)
    walk(node)
    return _dedupe(out)


def _labels_ode(node, stop):
    """Oxford Dictionary of English：reg（语体，如 formal、dated、literary）和 ge（地区）。"""
    out = []
    for n in node.iter(stop):
        if n is not node and n.has("reg", "ge"):
            out.append(_clean_label(n.text(skip=("gp",))))
    return _dedupe(out)


EC_STOP = ("exg", "pvb", "infg", "etym", "xrg")
ODE_STOP = ("eg", "subEntryBlock", "infg", "etym", "xrg", "note")


def parse_ec_entry(html):
    """牛津英汉汉英词典的一条记录 → {headword, blocks:[{pos, ipa_raw, labels, senses}]}。"""
    root = parse_html(html)
    hw = _headword(root, "hwg")
    hwg = root.find("hwg")
    ipa_main = _ipa_from([c for c in (hwg.children if hwg else []) if isinstance(c, Node) and c.has("prx")])
    blocks = []
    grambs = [g for g in root.find_all("gramb", stop=("pvb",))]
    for g in grambs or [root]:
        header = next((c for c in g.children if isinstance(c, Node) and c.has("x_xdh")), None)
        pos = ""
        ipa = ipa_main
        head_labels = []
        if header is not None:
            ps = header.find("ps")
            pos = ps.text(skip=("gp",)) if ps is not None else ""
            own = _ipa_from(header.find_all("prx", stop=("infg",)))
            ipa = own or ipa_main
            head_labels = _labels_ec(header, EC_STOP)
        senses = []
        for sb in g.find_all("semb", stop=EC_STOP):
            labs = _labels_ec(sb, EC_STOP)
            trans = [t.text(skip=("gp",)) for t in sb.find_all("trans", stop=EC_STOP) if not t.has("ty_pinyin")]
            ind = [i.text(skip=("gp",)) for i in sb.find_all("ind", stop=EC_STOP)]
            lead = ""
            if not trans:  # 以短语开头的义项（② to interfere with sth 弄坏某物）：短语和译文都在第一个 exg 里
                exg = next((c for c in sb.children if isinstance(c, Node) and c.has("exg")), None)
                head = next((c for c in exg.children if isinstance(c, Node) and c.has("x_xdh")), None) \
                    if exg is not None else None
                if head is not None:
                    phr = head if head.has("ex", "con") else (head.find("con") or head.find("ex"))
                    lead = phr.text(skip=("gp",)) if phr is not None else ""
                    labs = _dedupe(labs + _labels_ec(head, ()))
                    trg = [c for c in exg.children if isinstance(c, Node) and c.has("trg")]
                    for t in trg:
                        trans += [x.text(skip=("gp",)) for x in t.find_all("trans") if not x.has("ty_pinyin")]
                        ind += [x.text(skip=("gp",)) for x in t.find_all("ind")]
                        labs = _dedupe(labs + _labels_ec(t, ()))
            text = "；".join(_dedupe(t.strip() for t in trans))
            if lead:
                text = "%s：%s" % (lead, text) if text else lead
            senses.append({"pos": pos, "labels": labs, "ind": "；".join(_dedupe(ind)), "text": text})
        labels = _dedupe(head_labels + _common_labels([s["labels"] for s in senses]))
        blocks.append({"pos": pos, "ipa_raw": ipa, "labels": labels, "senses": senses})
    return {"headword": hw, "blocks": blocks, "root": root}


def parse_ode_entry(html):
    """Oxford Dictionary of English 的一条记录 → {headword, blocks:[{pos, ipa_raw, labels, senses}]}。"""
    root = parse_html(html)
    hw = _headword(root, "hg")
    hg = root.find("hg")
    ipa_main = _ipa_from([c for c in (hg.children if hg else []) if isinstance(c, Node) and c.has("prx")])
    blocks = []
    sg = root.find("sg")
    se1s = sg.find_all("se1", stop=("subEntryBlock",)) if sg is not None else []
    for se in se1s or [sg or root]:
        header = next((c for c in se.children if isinstance(c, Node) and c.has("x_xdh")), None)
        pos = ""
        ipa = ipa_main
        head_labels = []
        if header is not None:
            p = header.find("pos")
            pos = p.text() if p is not None else ""  # ODE 的词性文字在 span.gp.tg_pos 里
            own = _ipa_from(header.find_all("prx", stop=("infg",)))
            ipa = own or ipa_main
            head_labels = _labels_ode(header, ODE_STOP)
        senses = []
        for ms in se.find_all("msDict", stop=ODE_STOP):
            labs = _labels_ode(ms, ODE_STOP)
            df = " ".join(d.text(skip=("gp",)) for d in ms.find_all("df", stop=ODE_STOP))
            if not df:
                xr = ms.find("xrg", stop=("eg",))
                df = xr.text(skip=("gp",)) if xr is not None else ""
            senses.append({"pos": pos, "labels": labs, "ind": "", "text": df.strip()})
        labels = _dedupe(head_labels + _common_labels([s["labels"] for s in senses]))
        blocks.append({"pos": pos, "ipa_raw": ipa, "labels": labels, "senses": senses})
    return {"headword": hw, "blocks": blocks, "root": root}


# ---------------------------------------------------------------- 短语

PHRASE_EDGE_FILLERS = {"be", "to"}
PHRASE_TAIL_FILLERS = {"do", "doing", "done", "sth", "sb", "something", "somebody", "someone",
                       "one's", "oneself", "it"}
PHRASE_STOP = {"a", "an", "the", "to", "of", "in", "on", "at", "by", "for", "with", "from", "up", "down",
               "out", "off", "over", "into", "be", "have", "has", "had", "do", "it", "its", "it's", "there",
               "there's", "no", "not", "all", "very", "so", "as", "and", "or", "that", "this", "one",
               "one's", "sb", "sth", "is", "was"}
# 短语出现在哪种节点里：(class, 说明, 优先级)
PHRASE_HEADS = {"pv": ("短语动词", 3), "l": ("短语", 3), "idm": ("习语", 3), "f": ("固定说法", 2),
                "con": ("搭配", 1), "ex": ("例句", 0)}
PHRASE_BLOCKS = ("pvsec", "subEntry", "exg", "eg", "msDict", "semb", "se2")


def phrase_core(phrase):
    """'be prepared to do' → 'prepared to'；'might have done' → 'might have'。"""
    toks = norm_word(phrase).replace("…", " ").split()
    while toks and toks[0] in PHRASE_EDGE_FILLERS and len(toks) > 1:
        toks.pop(0)
    while toks and toks[-1] in PHRASE_TAIL_FILLERS and len(toks) > 1:
        toks.pop()
    return " ".join(toks)


def find_phrase(root, core):
    """在词条树里找短语，返回 {where, text, block} 或 None。"""
    if not core:
        return None
    pat = re.compile(r"(?<![a-z'])" + re.escape(core) + r"(?![a-z'])")
    best = None
    for n in root.iter():
        cl = n.classes()
        hit = [c for c in cl if c in PHRASE_HEADS]
        if not hit:
            continue
        full = n.text()  # 不跳过 span.gp：短语里的词有时包在 gp 里（rf > gp：take）
        if not pat.search(norm_word(full)):
            continue
        where, prio = PHRASE_HEADS[hit[0]]
        if best is None or prio > best[0]:
            block = next((a for a in n.ancestors() if a.has(*PHRASE_BLOCKS)), None)
            best = (prio, {"where": where, "text": full.strip(" ;,:"), "block": block})
            if prio >= 3:
                break
    return best[1] if best else None


def find_phrase_all(root, core):
    """短语在词条树里出现的每一处里，优先级最高的那些：[{where, text, block, node}]。
    interfere with 在牛津英汉里是几个义项下的搭配，其中一个带 British、euphemistic：都要看到。"""
    if not core:
        return []
    pat = re.compile(r"(?<![a-z'])" + re.escape(core) + r"(?![a-z'])")
    found = []
    for n in root.iter():
        hit = [c for c in n.classes() if c in PHRASE_HEADS]
        if not hit or not pat.search(norm_word(n.text())):
            continue
        where, prio = PHRASE_HEADS[hit[0]]
        block = next((a for a in n.ancestors() if a.has(*PHRASE_BLOCKS)), None)
        found.append((prio, {"where": where, "text": n.text().strip(" ;,:"), "block": block, "node": n}))
    if not found:
        return []
    top = max(p for p, _ in found)
    return [h for p, h in found if p == top]


def _phrase_all_labels(hit, ode):
    """短语这一块里所有义项的标签（并集，不是共有的），加上它所在义项本身的标签。"""
    block = hit["block"]
    out = []
    if block is not None:
        if ode:
            out += _labels_ode(block, tuple(s for s in ODE_STOP if not block.has(s)))
        else:
            out += _labels_ec(block, tuple(s for s in EC_STOP if not block.has(s)))
    sense = next((a for a in hit["node"].ancestors() if a.has("msDict" if ode else "semb") and a is not block), None)
    if sense is not None:
        out += _labels_ode(sense, ODE_STOP) if ode else _labels_ec(sense, EC_STOP)
    return _dedupe(out)


def _phrase_labels(block, ode):
    if block is None:
        return []
    if ode:
        stop = tuple(s for s in ODE_STOP if not block.has(s))
        return _labels_ode(block, stop)
    stop = tuple(s for s in EC_STOP if not block.has(s))
    senses = block.find_all("semb", stop=stop)
    if len(senses) > 1:
        return _common_labels([_labels_ec(s, stop) for s in senses])
    return _labels_ec(block, stop)


def _phrase_text(block, ode):
    if block is None:
        return ""
    if ode:
        return " ".join(d.text(skip=("gp",)) for d in block.find_all("df"))[:200]
    return "；".join(_dedupe(t.text(skip=("gp",)) for t in block.find_all("trans") if not t.has("ty_pinyin")))[:200]


# ================================================================ Lexicon

def empty_entry(word, notes=None):
    return {"headword": word, "ipa_br": [], "ipa_br_raw": [], "pos": [], "labels": [], "senses": [],
            "source": "未核对", "kind": None, "notes": list(notes or []), "blocks": [], "phrase": None,
            "all_labels": []}


class Lexicon:
    """级别（离线）和词条（多来源）。

    level(word, pos=None) -> (级别或 UNRATED, 来源)
    level_info(word, pos=None) -> dict（级别、来源、kind=list/estimate/none、原形、名次；
        pos_missing：给的词性词表里没有、按别的词性定的级；american：按哪个美式写法定的级，没用美式是 ""）
    entry(word, pos=None, source=None) -> {headword, ipa_br, ipa_br_raw, pos, labels, senses, source, …,
        all_labels：所有义项的标签合在一起（短语是短语出现的那几块）}
    classify(word) -> (原形, 级别, 依据) 或 None（给第一版 profile.py 用的兼容接口；含估级，未定级为 None）
    """

    def __init__(self, data_dir=None, cache_dir=None, project=None, refresh=False, offline=False,
                 delay=REQUEST_INTERVAL):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.project = Path(project) if project else None
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache(self.project)
        self.refresh = refresh
        self.offline = offline
        self.delay = max(float(delay), REQUEST_INTERVAL)
        self.settings = load_settings(self.project)
        self._last_request = 0.0
        self._mac = None
        self._level_cache = {}
        self._load_levels()

    # ------------------------------------------------------------ 数据
    def _load_levels(self):
        paths = {n: self.data_dir / n for n in (CEFRJ_FILE, OCTANOVE_FILE, ECDICT_FILE)}
        missing = [n for n, p in paths.items() if not p.is_file()]
        if missing:
            raise LexiconError("缺少级别数据：%s（应在 %s）" % ("、".join(missing), self.data_dir))
        try:
            self.cefr = read_profile_csv(paths[CEFRJ_FILE], "CEFR-J")
            for k, v in read_profile_csv(paths[OCTANOVE_FILE], "Octanove").items():
                lst = self.cefr.setdefault(k, [])
                lst.extend(r for r in v if r not in lst)
            self.ecdict = read_ecdict_subset(paths[ECDICT_FILE])
        except (OSError, ValueError, csv.Error, EOFError) as e:
            raise LexiconError("读不了级别数据（%s）" % e)
        self.lemmas = build_lemma_map(self.ecdict, self.cefr)

    def freq(self, w):
        r = self.ecdict.get(w)
        return r[0] if r and r[0] > 0 else None

    # ------------------------------------------------------------ 词形还原
    def lemma_candidates(self, word):
        """[(原形, 依据)]：ECDICT 变形表 → 不规则表（同样去掉假变形）→ 后缀规则（只对 ECDICT 不认识的词）。
        后缀规则拆出几个可能的原形时，先挑词表收了、词性对得上的，再挑 ECDICT 子集里有名次的，都没有才挑
        子集里没名次的；同一档里取名次靠前的，名次相同按规则顺序（miles → mile，不是 ECDICT 里的 mil）。"""
        w = norm_word(word)
        out = []
        l = self.lemmas.get(w)
        if l:
            out.append((l, "ECDICT 变形表"))
        irr = IRREGULAR.get(w)
        if not out and irr and irr != w:
            fw, fl = self.freq(w) or INF, self.freq(irr) or INF
            if not fw < fl:
                out.append((irr, "不规则表"))
        if not out and w not in self.ecdict:
            tiers = ([], [], [])  # 词表收了且词性对；ECDICT 有名次；ECDICT 有这一行但没名次
            seen = set()
            for i, (cand, need, how) in enumerate(rule_candidates(w)):
                if how in DERIVATIONAL or cand == w or cand in seen:
                    continue
                seen.add(cand)
                rows = self.cefr.get(cand)
                if rows:  # 词表收了、词性不对：不要（和以前一样，不再退到 ECDICT）
                    if listed_fits(rows, need):
                        tiers[0].append((self.freq(cand) or INF, i, cand, how))
                elif cand in self.ecdict:
                    tiers[1 if self.freq(cand) else 2].append((self.freq(cand) or INF, i, cand, how))
            for tier in tiers:
                if tier:
                    _, _, cand, how = min(tier)
                    out.append((cand, "后缀规则 " + how))
                    break
        return out

    def lemma(self, word):
        c = self.lemma_candidates(word)
        return c[0][0] if c else norm_word(word)

    def rank(self, word):
        """COCA 名次（原词或原形里最靠前的）；没有返回 None。给未定级词排序、估级用。
        英式拼写查不到、或名次明显差（比美式写法差一倍以上）时，用美式写法的名次（colour → color）。"""
        w = norm_word(word)
        r = self._rank_plain(w)
        for am, _ in american_variants(w):
            if am != w and self._known(am):
                ra = self._rank_plain(am)
                if ra and (r is None or ra * 2 <= r):
                    return ra
        return r

    def _rank_plain(self, w):
        ranks = [r for r in [self.freq(w)] + [self.freq(l) for l, _ in self.lemma_candidates(w)] if r]
        return min(ranks) if ranks else None

    def _known(self, w):
        """数据里有这个写法：CEFR-J / Octanove 收了，或 ECDICT 子集有这一行，或是 ECDICT 变形表里的变形。"""
        return w in self.cefr or w in self.ecdict or w in self.lemmas

    # ------------------------------------------------------------ 级别
    def level(self, word, pos=None):
        i = self.level_info(word, pos)
        return i["level"], i["source"]

    def level_info(self, word, pos=None):
        key = (norm_word(word), pos_family(pos) if pos else None)
        if key in self._level_cache:
            return dict(self._level_cache[key])
        info = self._level_info(*key)
        self._level_cache[key] = info
        return dict(info)

    def _level_info(self, w, fam):
        """先按原词查；没定级（估级或未定级）时试美式写法，取更好的结果。"""
        info = self._level_info_plain(w, fam)
        if info["kind"] == "list" or not w:
            return info
        return self._american_level(w, fam, info) or info

    def _american_level(self, w, fam, info):
        """美式写法比原词好：原词未定级而美式有级别、原词估级而美式在词表里、都是估级而原词名次差一倍以上。
        美式写法必须在数据里存在。how 和来源写明「英式拼写 coloured → colored」；原形尽量还用英式（colour）。"""
        for am, rules in american_variants(w):
            if am == w or not self._known(am):
                continue
            alt = self._level_info_plain(am, fam)
            if alt["kind"] == "none":
                continue
            better = (info["kind"] == "none" or alt["kind"] == "list"
                      or bool(alt["rank"] and info["rank"] and alt["rank"] * 2 <= info["rank"]))
            if not better:
                continue
            alt = dict(alt)
            note = "英式拼写 %s → %s" % (w, am)
            alt["word"] = w
            alt["american"] = am
            alt["how"] = note + ("；" + alt["how"] if alt["how"] else "")
            head, sep, rest = alt["source"].partition("；")
            alt["source"] = "%s；%s（%s）%s" % (head, note, "、".join(rules), sep + rest if sep else "")
            alt["lemma"] = self._british_lemma(w, am, alt["lemma"])
            return alt
        return None

    def _british_lemma(self, w, am, am_lemma):
        """美式写法的原形换回英式：coloured → colored → color，原形写 colour（coloured 按 -ed 拆出的 colour
        的美式写法正是 color）。找不到对应的英式原形就用美式的。"""
        if am_lemma == am:
            return w
        cands = [c for c, _, _ in rule_candidates(w)] + ([IRREGULAR[w]] if w in IRREGULAR else [])
        for c in cands:
            if c == am_lemma or any(v == am_lemma for v, _ in american_variants(c)):
                return c
        return am_lemma

    def _level_info_plain(self, w, fam):
        if fam == "phrase":
            fam = None
        info = {"word": w, "level": UNRATED, "source": "", "kind": "none", "lemma": w, "how": "",
                "rank": None, "estimated": False, "pos_missing": False, "american": ""}
        if not w:
            info["source"] = "空词"
            return info
        cands = [(w, "")] + self.lemma_candidates(w)
        opts = []
        for cand, how in cands:
            rows = self.cefr.get(cand)
            if rows and all(o[0] != cand for o in opts):
                opts.append((cand, how, rows))
        if opts:
            return self._pick_listed(w, fam, opts, info)
        if "'" in w:  # 缩约形式：didn't → did，Mole's → mole
            if w in CLITIC_SPECIAL:
                base = CLITIC_SPECIAL[w]
            elif w.endswith("n't"):
                base = w[:-3]
            else:
                base = re.sub(r"'(s|ll|re|ve|d|m)$", "", w)
            if base and base != w:
                sub = self._level_info(base, fam)
                if sub["kind"] != "none":
                    sub["word"] = w
                    sub["how"] = "缩约形式" + ("；" + sub["how"] if sub["how"] else "")
                    sub["source"] += "；%s 按 %s 算" % (w, base)
                    return sub
        best = None
        for cand, how in cands:
            r = self.freq(cand)
            if r and (best is None or r < best[0]):
                best = (r, cand, how)
        if best:
            r, cand, how = best
            info.update(level=est_level(r), kind="estimate", estimated=True, lemma=cand, how=how, rank=r)
            via = "" if cand == w else "（按 %s 算，%s）" % (cand, how)
            info["source"] = "估，ECDICT 名次 %s%s" % (format(r, ","), via)
            return info
        info["source"] = "CEFR-J、Octanove 和 ECDICT 子集都没有"
        return info

    def _pick_listed(self, w, fam, opts, info):
        note = ""
        use = opts
        if fam:
            matched = [(c, h, [r for r in rows if r[0] == fam]) for c, h, rows in opts]
            matched = [m for m in matched if m[2]]
            if matched:
                use = matched
            else:
                note = "词表里没有 %s 词性，按其他词性取最低" % fam
                info["pos_missing"] = True  # check 据此不给“会用/认得”建议（熟词生义）

        def min_lv(rows):
            return min(RANK[r[1]] for r in rows)

        best = min(use, key=lambda o: min_lv(o[2]))  # 同级时 min 取第一个，即原词
        cand, how, rows = best
        lv = LEVELS[min_lv(rows) - 1]
        top = [r for r in rows if r[1] == lv]
        src = "、".join(_dedupe(r[2] for r in top))
        poses = _dedupe(r[3] or "?" for r in top)
        detail = []
        if cand != w:
            detail.append("%s → %s（%s）" % (w, cand, how))
        if not fam and len({(r[3], r[1]) for r in rows}) > 1:
            detail.append("%s多个词性取最低：" % (cand + " " if cand != w else "")
                          + "、".join("%s %s" % (r[3] or "?", r[1]) for r in rows))
        if note:
            detail.append(note)
        source = "%s（%s）" % (src, "、".join(poses))
        if detail:
            source += "；" + "；".join(detail)
        info.update(level=lv, kind="list", lemma=cand, how=how, source=source, rank=self.rank(cand))
        return info

    def classify(self, word):
        """第一版 profile.py 的接口：(原形, 级别, 依据) 或 None。估级也返回级别，依据写“估”。"""
        i = self.level_info(word)
        if i["kind"] == "none":
            return None
        how = i["how"] or ("原形" if i["kind"] == "list" else "")
        if i["kind"] == "estimate":
            how = "估" + ("（%s）" % how if how else "")
        return i["lemma"], i["level"], how

    # ------------------------------------------------------------ 词条
    def entry(self, word, pos=None, source=None):
        """依次试本地词典文件（未实现）→ macOS → dictionaryapi.dev → ECDICT 音标（参考）→ 未核对。
        source 指定只用一个来源（macos / wiktionary / ecdict）。查短语时 word 里带空格。"""
        word = (word or "").strip()
        notes = []
        if not word:
            return empty_entry(word, ["空词"])
        dicts = self.settings.get("dictionaries") or []
        if dicts and source is None:
            notes.append("设置.json 的 dictionaries 配了 %d 个本地词典文件：不支持，下一轮实现" % len(dicts))
        order = [source] if source else list(SOURCES)
        for s in order:
            if s not in SOURCES:
                raise ValueError("来源只能是 %s" % "、".join(SOURCES))
            try:
                res = {"macos": self._entry_macos, "wiktionary": self._entry_wiktionary,
                       "ecdict": self._entry_ecdict}[s](word, pos, notes)
            except Exception as e:  # noqa: BLE001  任何来源出错都跳到下一个
                notes.append("%s 出错，已跳过（%s: %s）" % (s, type(e).__name__, e))
                res = None
            if res:
                res["notes"] = notes + res.get("notes", [])
                return res
        return empty_entry(word, notes)

    def local_dictionaries(self):
        """设置.json 的 dictionaries：这一版只留位置。"""
        dicts = self.settings.get("dictionaries") or []
        return [{"path": d.get("path") if isinstance(d, dict) else d, "status": "不支持，下一轮实现"} for d in dicts]

    # ---------------------------------------------------------------- macOS
    def mac(self):
        if self._mac is None:
            self._mac = MacDictionary()
        return self._mac

    def _entry_macos(self, word, pos, notes):
        mac = self.mac()
        if not mac.available:
            notes.append("macOS 系统词典不可用（%s），已跳过" % mac.error)
            return None
        if not (mac.has(MAC_EC) or mac.has(MAC_ODE)):
            notes.append("系统里没有「%s」和「%s」，已跳过" % (MAC_EC, MAC_ODE))
            return None
        if " " in word:
            return self._phrase_macos(word, notes)
        found = []  # (词典名, parsed)
        for name, parser in ((MAC_EC, parse_ec_entry), (MAC_ODE, parse_ode_entry)):
            recs = [parser(h) for h in mac.lookup(name, word)]
            exact = [r for r in recs if norm_word(r["headword"]).rstrip("-") == norm_word(word)]
            for r in exact or recs:
                found.append((name, r))
        if not found:
            return None
        return self._merge_mac(word, pos, found)

    def _merge_mac(self, word, pos, found):
        fam = pos_family(pos) if pos else None
        blocks = []
        for name, r in found:
            for b in r["blocks"]:
                blocks.append(dict(b, dict=name, headword=r["headword"]))
        notes = []
        use = blocks
        if fam and fam != "phrase":
            m = [b for b in blocks if pos_family(b["pos"]) == fam]
            if m:
                use = m
            else:
                notes.append("系统词典里没有 %s 词性的词条，按全部词条比" % fam)
        raw = _dedupe(i for b in use for i in b["ipa_raw"])
        if not raw:
            raw = _dedupe(i for b in blocks for i in b["ipa_raw"])
        ec = [b for b in use if b["dict"] == MAC_EC]
        senses = [s for b in (ec or use) for s in b["senses"]]
        hw = next((b["headword"] for b in blocks if b["dict"] == MAC_EC), blocks[0]["headword"] if blocks else word)
        if norm_word(hw) != norm_word(word):
            notes.append("词典词头是 %s" % hw)
        names = _dedupe(b["dict"] for b in blocks)
        return {
            "headword": hw,
            "ipa_br": _dedupe(to_oxford(i, "macos")[0] for i in raw),
            "ipa_br_raw": raw,
            "pos": _dedupe(b["pos"] for b in blocks if b["pos"]),
            "labels": _dedupe(l for b in use for l in b["labels"]),
            "senses": senses,
            "source": "macOS：" + "、".join(names),
            "kind": "macos",
            "notes": notes,
            "blocks": [{k: b[k] for k in ("dict", "headword", "pos", "ipa_raw", "labels")} for b in blocks],
            "phrase": None,
            # 两本词典、全部词性、每个义项的标签合在一起：核对讲义里的“英式”“正式”这类说法用（任何义项有就算）
            "all_labels": _dedupe(l for b in blocks
                                  for l in list(b["labels"]) + [x for s in b["senses"] for x in s["labels"]]),
        }

    def _phrase_macos(self, phrase, notes):
        mac = self.mac()
        core = phrase_core(phrase)
        words = core.split()
        content = [w for w in words if w not in PHRASE_STOP] or words
        content.sort(key=lambda w: -(self.rank(w) or 10 ** 9))  # 少见的词先查
        hits = []
        every = []  # 每本词典里短语出现的每一块（同一优先级）的标签
        for name, parser, ode in ((MAC_EC, parse_ec_entry, False), (MAC_ODE, parse_ode_entry, True)):
            if not mac.has(name):
                continue
            for q in [phrase, core] + content:
                hit = None
                for html in mac.lookup(name, q):
                    r = parser(html)
                    h = find_phrase(r["root"], core)
                    if h:
                        hit = (name, r["headword"], h, ode)
                        every.extend(_phrase_all_labels(x, ode) for x in find_phrase_all(r["root"], core))
                        break
                if hit:
                    hits.append(hit)
                    break
        if not hits:
            notes.append("系统词典里没找到短语 %s" % core)
            return None
        labels = _dedupe(l for _, _, h, ode in hits for l in _phrase_labels(h["block"], ode))
        senses = [{"pos": "", "labels": _phrase_labels(h["block"], ode), "ind": "", "text": _phrase_text(h["block"], ode)}
                  for _, _, h, ode in hits]
        first = hits[0]
        return {
            "headword": phrase, "ipa_br": [], "ipa_br_raw": [], "pos": ["phrase"], "labels": labels,
            "senses": senses,
            "source": "macOS：" + "、".join("%s（%s 词条）" % (n, hw) for n, hw, _, _ in hits),
            "kind": "macos", "notes": [], "blocks": [],
            "phrase": {"found": True, "core": core, "in": first[1], "where": first[2]["where"],
                       "text": first[2]["text"],
                       "hits": [{"dict": n, "in": hw, "where": h["where"], "text": h["text"]} for n, hw, h, _ in hits]},
            "all_labels": _dedupe(l for labs in [labels] + every for l in labs),
        }

    # ---------------------------------------------------------------- dictionaryapi.dev
    def _wikt_fetch(self, word, notes):
        safe = re.sub(r"[^a-z0-9_.'-]", "_", norm_word(word)) or "_"
        path = self.cache_dir / "wiktionary" / (safe + ".json")
        if path.is_file() and not self.refresh:
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                pass
        if self.offline:
            notes.append("离线，跳过 dictionaryapi.dev")
            return None
        url = WIKT_URL + urllib.parse.quote(word.strip())
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        data, err = None, ""
        for attempt in range(2):  # 临时错误（断线、5xx）再试一次
            wait = self.delay * (attempt + 1) - (time.time() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.time()
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = {"status": 200, "data": json.loads(r.read().decode("utf-8", "replace"))}
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    data = {"status": 404, "data": None}
                    break
                err = "HTTP %d" % e.code
                if e.code < 500 and e.code != 429:
                    break
            except (urllib.error.URLError, OSError, ValueError) as e:
                err = str(getattr(e, "reason", e))
        if data is None:
            notes.append("dictionaryapi.dev 取不到（%s），已跳过" % err)
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass
        return data

    def _entry_wiktionary(self, word, pos, notes):
        data = self._wikt_fetch(word, notes)
        if not data or data.get("status") != 200 or not isinstance(data.get("data"), list):
            if data and data.get("status") == 404:
                notes.append("dictionaryapi.dev 查不到 %s" % word)
            return None
        return parse_wiktionary(word, data["data"], pos)

    # ---------------------------------------------------------------- ECDICT
    def _entry_ecdict(self, word, pos, notes):
        r = self.ecdict.get(norm_word(word))
        if not r or not r[3]:
            return None
        raw = [p.strip() for p in re.split(r"[;；]", r[3]) if p.strip()]
        return {
            "headword": word, "ipa_br": _dedupe(to_oxford(p, "ecdict")[0] for p in raw), "ipa_br_raw": raw,
            "pos": [], "labels": [], "senses": [], "source": "ECDICT（参考）", "kind": "ecdict",
            "notes": ["ECDICT 的音标来源混杂，只作参考，不算核对过"], "blocks": [], "phrase": None,
            "all_labels": [],
        }


WIKT_LABEL_RE = re.compile(
    r"\((?:[^()]*?\b)?(formal|literary|poetic|dated|archaic|obsolete|old-fashioned|euphemistic|informal|"
    r"slang|rare|humorous|derogatory|offensive)\b[^()]*\)", re.I)


def parse_wiktionary(word, data, pos=None):
    """dictionaryapi.dev 的 JSON → 词条。英式音标取带 -uk 录音的，以及不含 ɹ ɚ ɝ 的音位写法。"""
    fam = pos_family(pos) if pos and pos_family(pos) != "phrase" else None
    uk, other, poses, senses, labels = [], [], [], [], []
    hw = word
    for e in data:
        if not isinstance(e, dict):
            continue
        hw = e.get("word") or hw
        phon = [(p.get("text") or "", p.get("audio") or "") for p in e.get("phonetics") or [] if isinstance(p, dict)]
        if e.get("phonetic"):
            phon.append((e["phonetic"], ""))
        for text, audio in phon:
            t = text.strip()
            if not t.startswith("/"):
                continue  # [ ] 是严式标音
            if re.search(r"-(uk|gb)\.mp3$", audio):
                uk.append(t.strip("/"))
            elif not re.search(r"[ɹɚɝ]", t) and not re.search(r"-(us|au|ca|nz)\.mp3$", audio):
                other.append(t.strip("/"))
        for m in e.get("meanings") or []:
            p = m.get("partOfSpeech") or ""
            if p:
                poses.append(p)
            if fam and pos_family(p) != fam:
                continue
            for d in m.get("definitions") or []:
                text = d.get("definition") or ""
                labs = _dedupe(x.group(1).lower() for x in WIKT_LABEL_RE.finditer(text))
                labels.extend(labs)
                senses.append({"pos": p, "labels": labs, "ind": "", "text": text})
    raw = _dedupe(uk + other)
    if not raw and not senses:
        return None
    return {
        "headword": hw, "ipa_br": _dedupe(to_oxford(i, "wiktionary")[0] for i in raw), "ipa_br_raw": raw,
        "pos": _dedupe(poses), "labels": _dedupe(labels), "senses": senses,
        "source": "Wiktionary（dictionaryapi.dev）", "kind": "wiktionary",
        "notes": ["Wiktionary 没有语体标签字段，标签是从释义文字里找的"] if labels else [],
        "blocks": [], "phrase": None, "all_labels": _dedupe(labels),
    }


# ================================================================ 讲义解析

POS_ABBR = r"(?:n|v|vt|vi|adj|adv|prep|conj|pron|det|num|int|interj|exclam|aux|modal|phr|abbr)"
POS_SEQ = POS_ABBR + r"\.(?:\s*(?:/|&|,)\s*" + POS_ABBR + r"\.)*"
DICT_ITEM_RE = re.compile(
    r"^(?:(?P<word>[A-Za-z][A-Za-z'’.\- ]*?)\s+)?(?:(?P<phon>/[^/]+/)\s*)?(?P<pos>" + POS_SEQ + r")\s*(?P<gloss>.*)$")
PREREAD_ITEM_RE = re.compile(
    r"^-\s+\*\*(?P<head>[^*]+?)\*\*\s*(?:(?P<phon>/[^/]+/)\s*)?(?P<pos>" + POS_SEQ + r")\s*(?P<gloss>.*)$")


def _section(lines, title_re, level=2):
    """返回某个标题下到同级或更高一级标题为止的行。"""
    start = None
    for i, ln in enumerate(lines):
        if re.match(title_re, ln):
            start = i + 1
            break
    if start is None:
        return None
    out = []
    stop = re.compile(r"^#{1,%d}\s" % level)
    for ln in lines[start:]:
        if stop.match(ln):
            break
        out.append(ln)
    return out


USAGE_LINE_RE = re.compile(r"^\s+(搭配|辨析|注意|例|词族)[：:]\s*(.*)$")


def parse_lecture(md_text):
    """讲义 → 待核对的行：[{section, headword, word, phon, pos, gloss, master, raw, entry_texts, first_of_entry}]。

    「## 词的用法」：`- **词头**：…` 下面缩进的「词典：」行，几个词典项之间用全角空格或 3 个以上空格分开；
    「## 读前」→「### 本章的词」：`- **word** /ipa/ pos. 释义`，短语可以不写音标。
    entry_texts 是词条首行（冒号后面）和 搭配、辨析、注意、例、词族 行：[(行名, 文字)]，核对标签说法用；
    同一词条拆出的几行共用一份，first_of_entry 标出第一行。读前的词没有 entry_texts，标签说法只看释义。"""
    lines = md_text.splitlines()
    items = []
    pre = _section(lines, r"^##\s+读前\s*$", 2)
    if pre is not None:
        words = _section(pre, r"^###\s+本章的词\s*$", 3)
        for ln in words or []:
            if not re.match(r"^\s*-\s", ln):
                continue
            m = PREREAD_ITEM_RE.match(ln.strip())
            if m:
                items.append({"section": "读前", "headword": m.group("head").strip(), "word": "",
                              "phon": (m.group("phon") or "").strip(), "pos": m.group("pos").strip(),
                              "gloss": m.group("gloss").strip(), "master": None, "raw": None,
                              "entry_texts": [], "first_of_entry": True})
            else:
                head = re.match(r"^\s*-\s+\*\*([^*]+)\*\*", ln)
                items.append({"section": "读前", "headword": head.group(1).strip() if head else ln.strip(),
                              "word": "", "phon": "", "pos": "", "gloss": "", "master": None,
                              "raw": ln.strip(), "entry_texts": [], "first_of_entry": True})
    use = _section(lines, r"^##\s+词的用法\s*$", 2)
    if use is not None:
        cur = None
        for ln in use:
            m = re.match(r"^-\s+\*\*(.+?)\*\*\s*[：:]\s*(.*)$", ln)
            if m:
                cur = {"headword": m.group(1).strip(), "dict": None, "master": None,
                       "texts": [("首行", m.group(2).strip())] if m.group(2).strip() else []}
                items.append(cur)
                continue
            if cur is None:
                continue
            m = re.match(r"^\s+词典[：:]\s*(.*)$", ln)
            if m and cur["dict"] is None:
                cur["dict"] = m.group(1).strip()
                continue
            m = re.match(r"^\s+掌握[：:]\s*(.*)$", ln)
            if m and cur["master"] is None:
                cur["master"] = m.group(1).strip()
                continue
            m = USAGE_LINE_RE.match(ln)
            if m and m.group(2).strip():
                cur["texts"].append((m.group(1), m.group(2).strip()))
        expanded = []
        for it in items:
            if "section" in it:
                expanded.append(it)
                continue
            parts = [p.strip() for p in re.split(r"　+|\s{3,}", it["dict"] or "") if p.strip()]
            base = {"section": "词的用法", "headword": it["headword"], "master": it["master"],
                    "entry_texts": it["texts"]}
            if not parts:
                expanded.append(dict(base, word="", phon="", pos="", gloss="", raw="（缺词典行）",
                                     first_of_entry=True))
            for i, p in enumerate(parts):
                m = DICT_ITEM_RE.match(p)
                if m:
                    expanded.append(dict(base, word=(m.group("word") or "").strip(),
                                         phon=(m.group("phon") or "").strip(), pos=m.group("pos").strip(),
                                         gloss=m.group("gloss").strip(), raw=None, first_of_entry=i == 0))
                else:
                    expanded.append(dict(base, word="", phon="", pos="", gloss="", raw=p, first_of_entry=i == 0))
        items = expanded
    return items


# ================================================================ 标签说法（讲义里的“英式”“正式”… ↔ 词典标签）

# (族, 讲义里的说法, 词典里该有的标签（给人看）, 词典标签的正则)
LABEL_CLAIMS = (
    ("British", r"英式|英国英语", "British", r"\bbrit(?:ish)?\b|\bbre\b|\buk\b"),
    ("US", r"美式|北美|美国英语", "US、North American", r"\bus\b|\bu\.s\.|\bn(?:orth|\.)\s*amer|\bamerican\b|\bame\b"),
    ("formal", r"(?<![非不])正式|书面", "formal、literary、written", r"(?<![a-z-])formal\b|\bliterary\b|\bwritten\b"),
    ("old", r"旧式|过时|老式", "old-fashioned、dated、archaic、old use",
     r"\bold-fashioned\b|\bdated\b|\barchaic\b|\bold use\b"),
    ("informal", r"口语|非正式", "informal、spoken、colloquial", r"\binformal\b|\bspoken\b|\bcolloquial\b"),
    ("euphemistic", r"委婉", "euphemistic", r"\beuphemis"),
    ("slang", r"俚语", "slang", r"\bslang\b"),
    ("literary", r"文学", "literary", r"\bliterary\b"),
)
CLAIM_ZH = [(fam, re.compile(zh)) for fam, zh, _, _ in LABEL_CLAIMS]
CLAIM_WANT = {fam: want for fam, _, want, _ in LABEL_CLAIMS}
CLAIM_EN = {fam: re.compile(en, re.I) for fam, _, _, en in LABEL_CLAIMS}
# 说法前面的否定：“不是英式用法”“不算口语”不报
CLAIM_NEG_RE = re.compile(r"(?:不是|不算|并非|并不|不属于|算不上|谈不上|不再是)[^，,。；;：:、]{0,4}$")
CLAIM_OR_RE = re.compile(r"\s*(?:或者|或是|或|/)\s*")  # “正式或文学”：一个满足就行
# 词典行和读前释义里，说法要在括号里（（口语）、（正式说法）），或后面跟着这些字（正式说法、书面语），
# 免得把释义本身（正式的）当成标签
CLAIM_SUFFIX_RE = re.compile(r"(?:的说法|说法|用法|用语|词|语|口吻|色彩|场合)")
SEG_OPEN, SEG_CLOSE = "“「『（(《", "”」』）)》"
SEG_SPLIT = set("，,；;。！？!?：:")
SEG_TOPIC_RE = re.compile(r"(?:里|中)$")
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
# 判断一段话说的是哪个词时不算的英文：虚词、占位词、词性缩写
SCOPE_IGNORE = PHRASE_STOP | PHRASE_TAIL_FILLERS | {
    "but", "if", "when", "then", "than", "nor", "yet", "who", "whom", "whose", "which", "what", "these", "those",
    "they", "them", "he", "him", "his", "she", "her", "we", "us", "you", "your", "me", "my", "our", "their",
    "doing", "sb's", "sth's", "someone's", "somebody's", "etc", "vt", "vi", "adj", "adv", "prep", "conj", "pron",
    "phr", "det", "num", "aux", "abbr"}
CLAIM_WHERE_ORDER = ("首行", "搭配", "辨析", "注意", "例", "词族", "词典行", "释义")


def _bracket_depth(text, pos):
    d = 0
    for ch in text[:pos]:
        if ch in "（(":
            d += 1
        elif ch in "）)" and d:
            d -= 1
    return d


def split_segments(text):
    """按逗号、分号、句号、冒号切成小段；引号和括号里的不切。“今天的英式英语里，interfere with sb …”这种
    以“里”“中”结尾、没有英文的话头，并到下一段。"""
    parts, buf, depth = [], [], 0
    for ch in text:
        if ch in SEG_OPEN:
            depth += 1
        elif ch in SEG_CLOSE and depth:
            depth -= 1
        if ch in SEG_SPLIT and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    out, carry = [], ""
    for seg in (p.strip() for p in parts):
        if not seg:
            continue
        if carry:
            seg, carry = carry + "，" + seg, ""
        if SEG_TOPIC_RE.search(seg) and not EN_WORD_RE.search(seg):
            carry = seg
            continue
        out.append(seg)
    if carry:
        out.append(carry)
    return out


def find_claims(text, bracket_only=False):
    """一段讲义文字里的标签说法：[{fams, terms, seg}]。fams 是一组里的族（“正式或文学”→ formal、literary，
    满足一个就行）；seg 是说法所在的那一小段。前面有“不是”“不算”的不算。bracket_only：只认括号里的，
    或后面跟着“说法”“语”“词”等字的（词典行、读前释义用）。"""
    out = []
    for seg in ([text] if bracket_only else split_segments(text)):
        hits = []
        for fam, zh in CLAIM_ZH:
            for m in zh.finditer(seg):
                if CLAIM_NEG_RE.search(seg[:m.start()]):
                    continue
                if bracket_only and not (_bracket_depth(seg, m.start()) or CLAIM_SUFFIX_RE.match(seg, m.end())):
                    continue
                hits.append((m.start(), m.end(), fam, m.group()))
        hits.sort()
        groups = []
        for h in hits:
            if groups and groups[-1][-1][1] > h[0]:
                continue  # 重叠
            if groups and CLAIM_OR_RE.fullmatch(seg[groups[-1][-1][1]:h[0]]):
                groups[-1].append(h)
            else:
                groups.append([h])
        for g in groups:
            out.append({"fams": tuple(_dedupe(x[2] for x in g)), "terms": "或".join(_dedupe(x[3] for x in g)),
                        "seg": seg})
    return out


def claim_target(lex, seg, headword, word):
    """这一小段说的是谁：'phrase' 短语词头；'word' 查的那个词；'head' 没提英文词（默认说词头）；
    None 说的是别的词（“美式英语用 cheap”“比 mention 书面”），不核对。"""
    low = norm_word(seg)
    head = norm_word(headword)
    if " " in head:
        core = phrase_core(headword)
        if core and re.search(r"(?<![a-z'])" + re.escape(core) + r"(?![a-z'])", low):
            return "phrase"
    toks = [t for t in (norm_word(x) for x in EN_WORD_RE.findall(seg)) if len(t) > 1 and t not in SCOPE_IGNORE]
    if not toks:
        return "head"
    targets = {norm_word(word)} | ({head} if " " not in head else set())
    lemmas = targets | {lex.lemma(t) for t in targets}
    if any(t in lemmas or lex.lemma(t) in lemmas for t in toks):
        return "word"
    return None


def row_claims(lex, it, word):
    """一行要核对的标签说法：[{fams, terms, where, seg, target}]。
    词条首行和用法行只算在词条的第一行（提到了本行查的词时算在本行）；词典项和读前释义算在本行。"""
    out = []
    head_is_phrase = " " in norm_word(it["headword"])
    for where, text in it.get("entry_texts") or []:
        for c in find_claims(text):
            t = claim_target(lex, c["seg"], it["headword"], word)
            if t is None or (t != "word" and not it.get("first_of_entry", True)):
                continue
            out.append(dict(c, where=where, target=t))
    gloss = it.get("gloss") or ""
    if gloss:
        where = "释义" if it["section"] == "读前" else "词典行"
        tgt = "word" if it.get("word") else "head"
        for c in find_claims(gloss, bracket_only=True):
            out.append(dict(c, where=where, target=tgt))
    for c in out:
        if c["target"] == "head":
            c["target"] = "phrase" if head_is_phrase else "word"
    return out


def judge_claim(fams, e):
    """(结果, 词典的标签)：结果是 一致 / 缺 / 未核对。只有系统词典能说“缺”；Wiktionary 没有语体标签字段，
    找到了算一致，找不到算未核对；ECDICT 和没有来源都是未核对。"""
    kind = (e or {}).get("kind")
    labels = list((e or {}).get("all_labels") or (e or {}).get("labels") or [])
    if kind not in ("macos", "wiktionary"):
        return "未核对", labels
    if any(CLAIM_EN[f].search(l) for f in fams for l in labels):
        return "一致", labels
    return ("缺" if kind == "macos" else "未核对"), labels


def check_label_claims(lex, it, word, e, ph, is_phrase):
    """返回 (问题说明 [], 未核对说明 [], 说法条数)。e 是本行查到的词条，ph 是短语词头另查的短语词条（没有为 None）。"""
    claims = row_claims(lex, it, word)
    bad, unk = {}, {}
    for c in claims:
        src, extra = e, ""
        if c["target"] == "phrase" and not is_phrase:
            if ph is not None and (ph.get("phrase") or ph.get("kind") in ("macos", "wiktionary")):
                src = ph
            else:
                extra = "词典里没找到短语 %s，按 %s 的词条核对" % (it["headword"], word)
        res, labels = judge_claim(c["fams"], src)
        if res == "一致":
            continue
        if extra and res == "缺":
            res = "未核对"
        key = (c["fams"], c["target"])
        bucket = bad if res == "缺" else unk
        b = bucket.setdefault(key, {"terms": [], "where": [], "labels": labels, "src": src, "extra": extra})
        b["terms"] = _dedupe(b["terms"] + [c["terms"]])
        b["where"] = _dedupe(b["where"] + [c["where"]])

    def where_text(b):
        return "、".join(sorted(b["where"], key=lambda w: CLAIM_WHERE_ORDER.index(w)
                                if w in CLAIM_WHERE_ORDER else 99))

    def src_text(b):
        s = (b["src"] or {}).get("source") or "未核对"
        return s

    bad_notes, unk_notes = [], []
    for (fams, _), b in bad.items():
        bad_notes.append("标签：讲义（%s）说「%s」，词典没有 %s 一类的标签；词典的标签：%s；来源 %s" % (
            where_text(b), "、".join(b["terms"]), "，或 ".join(CLAIM_WANT[f] for f in fams),
            "、".join(b["labels"]) or "无", src_text(b)))
    for (fams, _), b in unk.items():
        kind = (b["src"] or {}).get("kind")
        if b["extra"]:
            why = b["extra"] + "，没有对应的标签"
        elif kind == "wiktionary":
            why = "Wiktionary 的释义里没找到 %s（它没有语体标签字段，没找到不等于没有）" % "，或 ".join(
                CLAIM_WANT[f] for f in fams)
        elif kind == "ecdict":
            why = "来源只有 ECDICT（参考），没有语体标签"
        else:
            why = "没有可用的词典来源"
        unk_notes.append("标签未核对：讲义（%s）说「%s」，%s" % (where_text(b), "、".join(b["terms"]), why))
    return bad_notes, unk_notes, len(claims)


# ================================================================ 核对

def main_pos(p):
    return re.split(r"\s*[/&,]\s*", (p or "").strip())[0].rstrip(".")


def lookup_word(item):
    w = item.get("word") or item["headword"]
    if "/" in w:
        w = w.split("/")[0]
    return w.strip()


def formal_labels(labels):
    return [l for l in labels if FORMALISH_RE.search(l)]


def suggest(info, reader, labels):
    """返回 (建议, 核心词)。核心词是 会用 / 认得 / None。"""
    lv = info["level"]
    if lv == UNRATED:
        return "—（未定级）", None
    est = "（估）" if info["kind"] == "estimate" else ""
    formal = formal_labels(labels)
    d = RANK[lv] - RANK[reader]
    if formal:
        return "认得%s（%s）" % (est, formal[0]), "认得"
    if d >= 2:
        return "认得" + est, "认得"
    if d == 1:
        return "会用" + est, "会用"
    return "会用%s（不高于读者）" % est, "会用"


def preread_hint(info, reader):
    lv = info["level"]
    if lv == UNRATED:
        return "—（未定级）", False
    est = "（估）" if info["kind"] == "estimate" else ""
    d = RANK[lv] - RANK[reader]
    if d >= 2:
        return "高两级及以上" + est, False
    if d == 1:
        return "高一级" + est, False
    return "不高于读者" + est, True


def pos_check(lecture_pos, e):
    """返回 (结论, 说明)。"""
    lp = main_pos(lecture_pos)
    fam = pos_family(lp)
    if not lp or fam == "phrase" or not e.get("pos") or e.get("kind") in (None, "ecdict"):
        return "—", ""
    dict_pos = [p for p in e["pos"] if p]
    same = [p for p in dict_pos if pos_family(p) == fam]
    if not same:
        return "不一致", "讲义 %s.，词典 %s" % (lp, "、".join(dict_pos))
    t = transitivity(lp)
    if t:
        ts = {transitivity(p) for p in same}
        if None not in ts and t not in ts:
            return "不一致", "讲义 %s.，词典只有 %s" % (lp, "、".join(same))
    return "一致", "、".join(same)


def check_rows(lex, items, reader, source=None):
    rows = []
    for it in items:
        row = {"section": it["section"], "headword": it["headword"], "word": "", "phon": it["phon"],
               "pos": it["pos"], "master": it["master"] or ("—" if it["section"] == "读前" else "（缺）"),
               "dict_ipa": "", "status": "未核对", "pos_ok": "—", "source": "", "labels": "",
               "level": "", "level_plain": "", "level_src": "", "suggest": "", "notes": [], "flags": [],
               "marks": [], "label_claims": 0}
        if it["raw"]:
            row.update(word=it["raw"])
            row["notes"].append("缺词典行" if it["raw"] == "（缺词典行）" else "格式不认识，没有核对")
            row["flags"].append("格式")
            rows.append(row)
            continue
        word = lookup_word(it)
        lp = main_pos(it["pos"])
        is_phrase = pos_family(lp) == "phrase" or " " in word
        row["word"] = word
        e = lex.entry(word, None if is_phrase else lp, source=source)
        labels = list(e["labels"])
        phrase_labels = False
        ph = None
        # 词头是短语、查的是其中一个词（dwell on → dwell）：再找短语，标签按短语算
        if not is_phrase and " " in it["headword"] and norm_word(it["headword"]) != norm_word(word):
            ph = lex.entry(it["headword"], source=source or (e["kind"] if e["kind"] in SOURCES else None))
            if ph.get("phrase"):
                p = ph["phrase"]
                row["notes"].append("短语 %s：%s 词条的%s「%s」" % (p["core"], p["in"], p["where"], p["text"]))
                labels = list(ph["labels"])
                phrase_labels = True
            elif ph["kind"] and ph["kind"] != "ecdict":
                row["notes"].append("短语 %s：%s" % (it["headword"], ph["source"]))
                labels = list(ph["labels"]) or labels
            else:
                row["notes"].append("词典里没找到短语 %s，标签按 %s 算" % (it["headword"], word))
        # 状态
        if is_phrase and not it["phon"]:
            if e.get("phrase"):
                p = e["phrase"]
                row["status"] = "一致"
                row["notes"].append("短语，无音标可比；%s 词条的%s「%s」" % (p["in"], p["where"], p["text"]))
            elif e["kind"] in ("macos", "wiktionary"):
                row["status"] = "一致"
                row["notes"].append("短语，无音标可比；%s 有这个词条" % e["source"])
            else:
                row["status"] = "未核对"
                row["notes"].append("词典里没找到这个短语")
        else:
            st, note, _ = compare_ipa(it["phon"], e["ipa_br_raw"], e["kind"])
            row["status"] = st
            if note:
                row["notes"].append(note)
            if e["ipa_br_raw"]:
                pairs = []
                for raw in e["ipa_br_raw"]:
                    conv = to_oxford(raw, e["kind"])[0]
                    pairs.append("/%s/" % raw if conv == ipa_strip(raw) else "/%s/ → /%s/" % (raw, conv))
                row["dict_ipa"] = "；".join(pairs)
        if row["status"] == "不一致":
            row["flags"].append("音标")
        pk, pnote = pos_check(it["pos"], e)
        row["pos_ok"] = pk + ("（%s）" % pnote if pnote else "")
        if pk == "不一致":
            row["flags"].append("词性")
        row["source"] = e["source"]
        cell = []
        if labels:
            cell.append(("短语：" if phrase_labels else "") + "、".join(labels))
        if e["kind"] == "macos" and not is_phrase:
            covered = set(e["labels"])
            sense_labs = ["%d. %s" % (i + 1, "/".join(s["labels"])) for i, s in enumerate(e["senses"])
                          if s["labels"] and not set(s["labels"]) <= covered]
            if sense_labs:
                cell.append("%s义项 %s" % (word + " 的" if phrase_labels else "", "，".join(sense_labs[:6])))
        row["labels"] = "；".join(cell)
        # 级别和建议
        info = lex.level_info(word if not is_phrase else (it["headword"] if " " in it["headword"] else word),
                              None if is_phrase else lp)
        row["level"] = info["level"] if info["kind"] != "estimate" else info["level"] + "（估）"
        row["level_plain"] = info["level"]
        row["level_src"] = info["source"]
        if it["section"] == "读前":
            hint, low = preread_hint(info, reader)
            row["suggest"] = hint
            if low:
                row["flags"].append("级别")
        elif info.get("pos_missing") and not is_phrase:
            # 熟词生义：词典行写的词性词表里没有（common n.，词表只有形容词），别的词性的级别不能拿来建议
            row["suggest"] = "—（熟词生义：词表没有这个词性）"
        else:
            sug, core = suggest(info, reader, labels)
            row["suggest"] = sug
            if core and it["master"] and it["master"] in ("会用", "认得") and it["master"] != core:
                row["flags"].append("掌握")
        # 讲解里的标签说法（英式、正式、旧式……）要在词典里看得到
        bad, unk, n_claims = check_label_claims(lex, it, word, e, ph, is_phrase)
        row["label_claims"] = n_claims
        if bad:
            row["flags"].append("标签")
            row["notes"].extend("!" + n for n in bad)
        if unk:
            row["marks"].append("标签未核对")
            row["notes"].extend(unk)
        for n in e.get("notes", []):
            if n not in row["notes"] and not n.startswith("设置.json 的 dictionaries"):  # 表头已经说了
                row["notes"].append(n)
        rows.append(row)
    return rows


def md_cell(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def print_check(rows, reader_desc, name, src_note):
    print("# 词典核对：%s（读者 %s）\n" % (name, reader_desc))
    if src_note:
        print(src_note + "\n")
    cols = ["", "栏目", "词头", "查词", "讲义音标", "词典音标（原样 → 换算）", "状态", "词性", "来源", "标签",
            "级别", "掌握", "建议", "备注"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "|".join(["---"] * len(cols)) + "|")
    for r in rows:
        flag = "**!" + "/".join(r["flags"]) + "**" if r["flags"] else ""
        if r.get("marks"):
            flag = (flag + " " if flag else "") + "/".join(r["marks"])
        lvl = r["level_plain"] + ("：" + r["level_src"] if r["level_src"] else "")
        vals = [flag, r["section"], r["headword"], r["word"], r["phon"], r["dict_ipa"], r["status"],
                (r["pos"] + " " if r["pos"] else "") + r["pos_ok"], r["source"], r["labels"], lvl, r["master"],
                r["suggest"], "；".join(r["notes"])]
        print("| " + " | ".join(md_cell(v) for v in vals) + " |")
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    lab_rows = sum(1 for r in rows if r.get("label_claims"))
    lab_bad = sum(1 for r in rows if "标签" in r["flags"])
    lab_unk = sum(1 for r in rows if "标签未核对" in r.get("marks", []))
    print("\n共 %d 行：%s。标 ! 的 %d 行。标签说法：讲义写了的 %d 行，!标签 %d 条，标签未核对 %d 条。" % (
        len(rows), "，".join("%s %d" % (k, v) for k, v in counts.items() if v), sum(1 for r in rows if r["flags"]),
        lab_rows, lab_bad, lab_unk))
    if counts["未核对"]:
        print("有 %d 行未核对（没有可用的来源，或讲义没写音标），交付时要说明。" % counts["未核对"])
    if counts["参考"]:
        print("有 %d 行只有 ECDICT 的音标作参考，不算核对过。" % counts["参考"])
    print("说明：音标先把来源写法换成 Oxford Learner's 写法（ʌɪ→aɪ，ɛː/ɛə→eə，ɛ→e，əː→ɜː，"
          "不在 aɪ、aʊ 里的 a→æ）再比，括号里的可省音有和没有都算；原样就对上是“一致”，换算后才对上是“仅写法不同”。")
    print("建议：比读者高一级 → 会用；高两级及以上，或整条词（短语词头按短语）带 formal、literary、"
          "old-fashioned、dated 等标签 → 认得；估级的注明“估”；未定级不给建议；词典行写的词性词表里没有的"
          "（熟词生义）不给建议。读前的词只看是否高于读者。")
    print("标签说法：词条首行、搭配/辨析/注意/例/词族行、词典行和读前释义里的“英式”“美式/北美”“正式/书面”"
          "“旧式/过时/老式”“口语/非正式”“委婉”“俚语”“文学”，词典这个词条任何义项（短语词头按短语那一块）"
          "都没有对应标签的标 !标签。词典行和释义只认括号里的说法；一小段话里提到了别的英文词的，算说那个词，"
          "不核对；前面是“不是”“不算”的不算。只有系统词典能判“没有”，Wiktionary、ECDICT 或没有来源时标“标签未核对”。")


# ================================================================ 命令

def setup_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def make_lexicon(args, start):
    project = find_project(start)
    cache = Path(args.cache) if args.cache else default_cache(project)
    try:
        return Lexicon(cache_dir=cache, project=project, refresh=args.refresh, offline=args.offline)
    except LexiconError as e:
        raise SystemExit("错误：%s" % e)


def cmd_level(args):
    lex = make_lexicon(args, Path.cwd())
    for w in args.words:
        lv, src = lex.level(w, args.pos)
        print("%-18s %-4s %s" % (w, lv, src))


def fmt_entry(e, n_senses=5):
    out = ["%s    [%s]" % (e["headword"], e["source"])]
    if e["ipa_br_raw"]:
        conv = ["/%s/" % x for x in e["ipa_br"]]
        raw = ["/%s/" % x for x in e["ipa_br_raw"]]
        out.append("  英式音标  %s%s" % ("，".join(conv), "" if conv == raw else "    （原样 %s）" % "，".join(raw)))
    if e["pos"]:
        out.append("  词性      %s" % "，".join(e["pos"]))
    out.append("  标签      %s" % ("，".join(e["labels"]) or "—"))
    shown = e["senses"] if not n_senses else e["senses"][:n_senses]
    for i, s in enumerate(shown, 1):
        extra = " ".join(x for x in (s.get("pos", ""), "(%s)" % ", ".join(s["labels"]) if s.get("labels") else "",
                                     "[%s]" % s["ind"] if s.get("ind") else "") if x)
        out.append("  %d. %s%s" % (i, extra + " " if extra else "", s.get("text") or "—"))
    if len(shown) < len(e["senses"]):
        out.append("  ……另有 %d 个义项" % (len(e["senses"]) - len(shown)))
    if e.get("phrase"):
        p = e["phrase"]
        out.append("  短语      %s：%s 词条的%s「%s」" % (p["core"], p["in"], p["where"], p["text"]))
    for n in e.get("notes", []):
        out.append("  注意      %s" % n)
    return "\n".join(out)


def cmd_entry(args):
    lex = make_lexicon(args, Path.cwd())
    e = lex.entry(args.word, args.pos, source=args.source)
    if args.json:
        print(json.dumps(e, ensure_ascii=False, indent=2))
    else:
        print(fmt_entry(e, args.senses))


def cmd_check(args):
    p = Path(args.file)
    if not p.is_file():
        raise SystemExit("错误：找不到 %s" % args.file)
    lex = make_lexicon(args, p)
    if args.level:
        reader, desc = args.level.upper(), "%s，取自 --level" % args.level.upper()
    else:
        lv = str(lex.settings.get("level") or "").upper()
        reader, desc = (lv, "%s，取自 设置.json" % lv) if lv else ("B1", "B1，默认")
    if reader not in RANK:
        raise SystemExit("错误：读者水平只能是 %s，现在是 %r" % ("/".join(LEVELS), reader))
    items = parse_lecture(p.read_text(encoding="utf-8"))
    if not items:
        raise SystemExit("错误：讲义里没有「## 词的用法」的词条，也没有「## 读前」→「### 本章的词」")
    rows = check_rows(lex, items, reader, source=args.source)
    note = ""
    if args.source:
        note = "只用来源：%s。" % args.source
    elif lex.settings.get("dictionaries"):
        note = "设置.json 的 dictionaries（本地词典文件）这一版不支持，下一轮实现；用的是内置来源。"
    print_check(rows, desc, p.name, note)


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="词级与词典：级别、词条、讲义核对")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cache", help="缓存目录（默认 项目/.cache/lexicon/，找不到项目时 ./.cache/lexicon/）")
    common.add_argument("--refresh", action="store_true", help="联网来源不用缓存，重新取")
    common.add_argument("--offline", action="store_true", help="不联网（跳过 dictionaryapi.dev）")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    a = sub.add_parser("level", parents=[common], help="给级别（CEFR-J / Octanove / ECDICT 估级）")
    a.add_argument("words", nargs="+")
    a.add_argument("--pos", help="n / v / adj / adv …")
    b = sub.add_parser("entry", parents=[common], help="查词条")
    b.add_argument("word")
    b.add_argument("--pos", help="n / v / adj / adv …（音标和标签优先取这个词性的词条）")
    b.add_argument("--json", action="store_true", help="输出 JSON")
    b.add_argument("--source", choices=SOURCES, help="只用这一个来源")
    b.add_argument("--senses", type=int, default=5, help="打印前几个义项（0=全部）")
    c = sub.add_parser("check", parents=[common], help="核对讲义的词典行和读前的词")
    c.add_argument("file")
    c.add_argument("--level", help="读者水平 A1–C2（默认读项目的 设置.json，没有就 B1）")
    c.add_argument("--source", choices=SOURCES, help="只用这一个来源")
    args = ap.parse_args(argv)
    {"level": cmd_level, "entry": cmd_entry, "check": cmd_check}[args.cmd](args)


# 模块级的便捷接口：level(word, pos=None)、entry(word)
_DEFAULT = None


def _default():
    global _DEFAULT
    if _DEFAULT is None:
        project = find_project(Path.cwd())
        _DEFAULT = Lexicon(project=project)
    return _DEFAULT


def level(word, pos=None):
    """(级别或“未定级”, 来源)。"""
    return _default().level(word, pos)


def entry(word, pos=None, source=None):
    """{headword, ipa_br, ipa_br_raw, pos, labels, senses, source, kind, notes, blocks, phrase}。"""
    return _default().entry(word, pos, source)


if __name__ == "__main__":
    main()
