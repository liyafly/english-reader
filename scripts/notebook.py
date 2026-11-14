#!/usr/bin/env python3
"""难句本、单词本、卡句定位（第三版）。不单独运行，由 build.py 转发：

  python3 build.py sentences [项目] [--anki] [--pdf] [--out 目录]
        难句本.md、难句本.tsv（只支持第三版的项目）。--anki 另出 难句本-anki.tsv（开头带 Anki 的文件头）；
        --pdf 另出 难句本.pdf（A5，排法和排版程序同 build.py pdf）
  python3 build.py words     [项目] [--anki] [--out 目录]
        单词本.md、单词本.tsv（三种格式的项目都行）。--anki 另出 单词本-anki.tsv
  python3 build.py stuck     [项目] [--json]
        卡句.txt 里的每一句在原文里找：命中、多处、近似、找不到、太短。只读，不改 卡句.txt，退出码总是 0
  难句本、单词本的 .md 和 .pdf 写进 成品/，.tsv 写进 成品/导入/（旧项目平铺在根目录，见 build.out_path）

build.py 载入项目（P 填好）后调用 run(子命令, 其余参数, build)，build 就是 build.py 模块，这里直接用它的
parse_chapter、source_path、stuck_words、load_tags、Words 这些。check 在项目有 卡句.txt 时调用 locate_stuck(build)。
难句本的数据由 sentence_book(build) 给出，md、tsv 和 PDF 共用（结构见那个函数）。只用 Python 标准库。
"""
import difflib
import hashlib
import json
import math
import re
import sys
from collections import Counter

REREAD = "拆完的句子，按正常速度再读两三遍。"           # 回读的话，印在难句本开头
SB_INTRO = f"先看「一、自己拆」：读原句，答下面的问题。再翻到「二、对照」。编号开头是章号，没读到的章先跳过。{REREAD}"
SB_COLUMNS = ("id", "原句", "注", "试", "答", "主干", "断句", "顺读", "卡点", "译", "结构", "出处", "类型")
WB_COLUMNS = ("id", "词", "音标", "词性", "释义", "原句", "原句译", "章", "类型", "掌握", "级别")
SB_ANKI = ("#separator:tab\n#html:false\n#columns:" + "\t".join(SB_COLUMNS) + "\n#guid column:1\n#tags column:11\n")
WB_ANKI = ("#separator:tab\n#html:false\n#columns:" + "\t".join(WB_COLUMNS) + "\n#guid column:1\n")
SB_FILES = ("难句本.md", "难句本.tsv", "难句本-anki.tsv")
WB_FILES = ("单词本.md", "单词本.tsv", "单词本-anki.tsv")
ANSWER_LABELS = ("怎么拆", "卡点", "译")           # 对照里抄的表后项；句型、延伸、赏析留在讲义里
UNKNOWN = "标签不认识"                               # 主标签不在 结构标签.tsv 里（或没写）的句子放在最后这一组
RESULTS = ("命中", "多处", "近似", "找不到", "太短")
MIN_WORDS = 4                                        # 少于这么多英文词、又不能唯一定位的，报太短
NEAR = 0.85                                          # 近似：difflib 相似度的下限
NEAR_FLOOR = 0.5                                     # 近似的预筛：窗口里至少有这么多比例的词和卡句的词相同
QUOTES = "\"'“”‘’「」『』"
LEAD = re.compile(r"(?:[-*•]\s+|\d+[.、)）]\s*|>\s*)")      # 卡句.txt 行首的列表记号、引用记号
# 卡句.txt 的单元行：「第 2 章」「第二章」「# 第 2 部分」「[2]」；不带 # 的后面可以跟标题（「第 2 章 The Open Road」）
UNIT_LINE = re.compile(r"(#*)\s*(?:第\s*([0-9]+|[零〇一二两三四五六七八九十百]+)\s*(?:章|部分|篇)|\[\s*([0-9]+)\s*\])(.*)")
EN_WORD = re.compile(r"[A-Za-zÀ-ɏ]+(?:['’\-][A-Za-zÀ-ɏ]+)*")   # 同 build.py 的 EN_WORD
OLD_FORMAT = "这个项目是第一、二版的格式（设置.json 里没有 \"format\": 3）"


def run(name, args, build):
    """build.py 的转发入口：name 是 sentences、words、stuck；args 是其余参数（项目目录已经拿掉）；build 是 build.py 模块。"""
    cmds = {"sentences": cmd_sentences, "words": cmd_words, "stuck": cmd_stuck}
    if name not in cmds:
        sys.exit(f"notebook.py 不认识的子命令：{name}")
    return cmds[name](list(args), build)


# ---------- 共用 ----------

def field(s):
    """TSV 的一格：制表符、换行换成空格，连续空白并成一个。"""
    return re.sub(r"\s+", " ", str(s or "")).strip()


def plain(md):
    """去掉 Markdown 的反引号和粗体星号（TSV 里放纯文本）。"""
    return str(md or "").replace("**", "").replace("`", "")


def cell(s):
    """Markdown 表格的一格：竖线转义，换行换成空格。"""
    return field(s).replace("|", "\\|")


def clip(s, width=90):
    s = field(s)
    return s if len(s) <= width else s[:width - 1].rstrip() + "…"


def scope_text(build, nums):
    """标题里的范围：「（第 1–2 章）」「（第 1、3 章）」；只有一篇时不写。"""
    if build.P.single or not nums:
        return ""
    nums, U = sorted(nums), build.P.unit
    if len(nums) == 1:
        return f"（第 {nums[0]} {U}）"
    if nums == list(range(nums[0], nums[-1] + 1)):
        return f"（第 {nums[0]}–{nums[-1]} {U}）"
    return f"（第 {'、'.join(map(str, nums))} {U}）"


def where_name(build, n):
    """出处里的书名加单元名：「The Wind in the Willows 第 2 章」；只有一篇、又没写篇名时只写书名。"""
    place = build.unit_name(n)
    return build.P.title if place == build.P.title else f"{build.P.title} {place}"


def take_flags(args, flags, name, out=False, build=None):
    """拿出开关（--anki 这类）和「--out 目录」。别的参数报错退出。返回 (开关集合, 输出目录)。"""
    out_dir = None
    if out:
        out_dir, args = build.take_out(args)
    got = {a for a in args if a in flags}
    bad = [a for a in args if a not in flags]
    if bad:
        allowed = "、".join(flags + (("--out 目录",) if out else ()))
        sys.exit(f"{name} 不认识的参数：{' '.join(bad)}（只接项目目录和 {allowed}）")
    return got, out_dir


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(path)


def tsv(rows, head=""):
    return head + "".join("\t".join(field(c) for c in r) + "\n" for r in rows)


def dedupe_ids(ids):
    """id 重复时（同一个原句讲了两次、同一单元同一个词出现两次），第二个起加 -2、-3。"""
    seen, out = Counter(), []
    for i in ids:
        seen[i] += 1
        out.append(i if seen[i] == 1 else f"{i}-{seen[i]}")
    return out


class Source:
    """一个单元的原文：按段落（空行隔开）切句（source.py 的 split_sentences），再取比对用的词串（build.stuck_words，
    卡句的归一化）。sent_of[k] 是第 k 个词在第几句。句子里的空白并成一个空格，所以每句都是 source_text 的一段。"""

    def __init__(self, build, n):
        self.n = n
        raw = build.source_path(n).read_text(encoding="utf-8").replace("\ufeff", "")
        self.sentences, self.heading = [], set()        # heading：标题行（source.py 的 is_heading）切出来的句子序号
        is_heading = build.sibling("source").is_heading
        for p in re.split(r"\n[ \t\r\f\v]*\n", raw):
            head = is_heading(p)
            for s in build.en_sentences(p):
                if head:
                    self.heading.add(len(self.sentences))
                self.sentences.append(s)
        self.tokens, self.sent_of = [], []
        for k, s in enumerate(self.sentences):
            w = build.stuck_words(s)
            self.tokens += w
            self.sent_of += [k] * len(w)

    def find(self, words):
        """words（词串）在本单元词串里每一处的起点。"""
        k, t = len(words), self.tokens
        if not k:
            return []
        first = words[0]
        return [i for i in range(len(t) - k + 1) if t[i] == first and t[i:i + k] == words]

    def covering(self, start, k):
        """词串 [start, start+k) 跨的句子序号：(第一句, 最后一句)。"""
        return self.sent_of[start], self.sent_of[start + k - 1]


def sources(build):
    """{单元号: Source}，只放有原文的单元，用到时才读。"""
    cache = {}

    def get(n):
        if n not in cache:
            cache[n] = Source(build, n) if build.source_path(n).exists() else None
        return cache[n]
    return get


def chapters_of(build):
    """有讲义的单元，各自 parse_chapter；格式有问题的单元给一条提醒（照常汇总）。"""
    chapters, warns = [], []
    for n in build.available():
        ch = build.parse_chapter(n)
        chapters.append(ch)
        if ch["errors"]:
            warns.append(f"{build.unit_name(n)}有 {len(ch['errors'])} 个格式问题，汇总可能不全：先跑 check")
    return chapters, warns


# ---------- 难句本 ----------

def trunk(chunks):
    """主干：断句表里的粗体按顺序用 … 连起来；同一行里只隔着空白的两处粗体（**It** **was**）算一处，用空格连；
    只隔着撇号的（**you**’**ll have to go**）原样连上（you’ll have to go）。"""
    parts = []
    for c in chunks:
        md, last = c.get("md", ""), None
        for m in re.finditer(r"\*\*(.+?)\*\*", md):
            gap = md[last:m.start()] if last is not None else None
            if gap is not None and not gap.strip():
                parts[-1] += " " + m.group(1)
            elif gap in ("'", "’"):
                parts[-1] += gap + m.group(1)
            else:
                parts.append(m.group(1))
            last = m.end()
    return " … ".join(parts)


def notes_text(notes):
    return "；".join(f"{w} {g}" for w, g in notes)


def item_text(block, label):
    """表后某一项（卡点、译……）的文字，续行接在后面；没有就是 ""。"""
    for x in block["items"]:
        if x["label"] == label:
            return " ".join([x["text"]] + x["sub"]).strip()
    return ""


def sentence_id(build, quote):
    """句子卡的 id：slug 加原句归一化（build.stuck_words：NFKC、弯引号换直的、小写、只留词）后 SHA-1 的前 8 位。
    和句子的编号、标签、所在单元都无关，重新编号后不变。"""
    key = " ".join(build.stuck_words(quote))
    return f"{build.P.slug}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]}"


def sentence_book(build):
    """难句本的数据，md、tsv 和 PDF 共用。返回 dict：
      title（书名）、scope（「（第 1–2 章）」或 ""）、units（有讲义的单元号）、warnings（提醒，逐条打印）、
      skipped（标签是词汇、不收的卡句个数）、
      entries：全部收进来的句子，按单元号、原文里的位置排（tsv 的 id 去重按这个顺序）；
      groups：[{tag, definition, how, items: [entry…], see: [entry…]}…]，按 结构标签.tsv 的行序，没有句子也没有
        另见的组不出；items 是主标签在这组的句子（组内按单元号、原文位置），see 是第二个标签在这组的句子（另见）。
        主标签不在表里的句子放在最后一组，tag 是 UNKNOWN，definition、how 是 ""。
    entry：{n（单元号）、i（句号）、stuck（是不是卡句）、label（显示的编号「2-1」「2-卡1」）、anchor（锚点用的
      「2-1」「2-k1」，题面是 q-…，对照是 a-…）、block（parse_chapter 给的句子块，原样）、tags、main（主标签）、
      pos（原句在本单元原文里的位置，找不到是 inf）、id（tsv 的 id）、type（tsv 的类型）、source（出处）}。
    题面用 block 的 quote、notes、try["q"]；对照用 tags、mark、notes、try、chunks、gloss、items（怎么拆、卡点、译）。"""
    chapters, warns = chapters_of(build)
    tags = build.load_tags()
    order = [t["tag"] for t in tags if t["tag"] != build.VOCAB]
    info = {t["tag"]: t for t in tags}
    src = sources(build)
    entries, skipped = [], 0
    for ch in chapters:
        n, S = ch["n"], src(ch["n"])
        for blocks, stuck in ((ch["sentences"], False), (ch.get("extra") or [], True)):
            for b in blocks:
                if build.VOCAB in b.get("tags", []):
                    skipped += 1
                    continue
                hits = S.find(build.stuck_words(b["quote"])) if S else []
                mark = b.get("mark") if b.get("mark") in build.MARKS else "没说"
                e = {"n": n, "i": b["i"], "stuck": stuck, "block": b, "tags": list(b.get("tags", [])),
                     "label": f"{n}-{'卡' if stuck else ''}{b['i']}", "anchor": f"{n}-{'k' if stuck else ''}{b['i']}",
                     "pos": hits[0] if hits else math.inf,
                     "type": f"卡句·{mark}" if stuck else (b.get("kind") or "精讲"),
                     "source": f"{where_name(build, n)} {'卡句' if stuck else '句'} {b['i']}"}
                e["main"] = e["tags"][0] if e["tags"] else ""
                entries.append(e)
    entries.sort(key=lambda e: (e["n"], e["pos"], e["stuck"], e["i"]))
    raw = [sentence_id(build, e["block"]["quote"]) for e in entries]
    for e, r, i in zip(entries, raw, dedupe_ids(raw)):
        e["id"] = i
    # 加过后缀的才算重复（不能看 id 末尾是不是 -数字：8 位哈希可能全是数字）
    dup = [e["label"] for e, r in zip(entries, raw) if e["id"] != r]
    if dup:
        warns.append(f"原句和前面的句子相同：{'、'.join(dup)}（id 加了 -2 这样的后缀）")
    groups = []
    for tag in order:
        items = [e for e in entries if e["main"] == tag]
        see = [e for e in entries if e["main"] != tag and tag in e["tags"][1:]]
        if items or see:
            groups.append({"tag": tag, "definition": info[tag]["definition"], "how": info[tag]["how"],
                           "items": items, "see": see})
    lost = [e for e in entries if e["main"] not in order]
    if lost:
        groups.append({"tag": UNKNOWN, "definition": "", "how": "", "items": lost, "see": []})
        warns.append(f"主标签不在 结构标签.tsv 里（或没写）：{'、'.join(e['label'] for e in lost)}，"
                     f"放在最后的「{UNKNOWN}」组；先跑 check")
    nums = [ch["n"] for ch in chapters]
    return {"title": build.P.title, "scope": scope_text(build, nums), "units": nums, "entries": entries,
            "groups": groups, "warnings": warns, "skipped": skipped}


def block_md(b, build):
    """对照里的一个句子块：结构、标记、注、试，断句表，答、怎么拆、卡点、译（照讲义的写法）。"""
    out = [f"- **结构**：{'、'.join(b.get('tags', []))}"]
    if b.get("mark"):
        out.append(f"- **标记**：{b['mark']}")
    if b.get("notes"):
        out.append(f"- **注**：{notes_text(b['notes'])}")
    t = b.get("try") or {}
    if t.get("q"):
        out.append(f"- **试**：{t['q']}")
    out += ["", "| 断句 | 顺读 |", "| --- | --- |"]
    for c, g in zip(b.get("chunks", []), b.get("gloss", [])):
        out.append(f"| {build.INDENT * c['depth']}{cell(c['md'])} | {cell(g)} |")
    post = ([f"- **答**：{t['a']}"] if t.get("a") else [])
    for x in b.get("items", []):
        if x["label"] not in ANSWER_LABELS:
            continue
        post.append(f"- **{x['label']}**：{x['text']}".rstrip())
        steps = x["label"] == "怎么拆"
        post += [f"  {k}. {line}" if steps else f"  {line}" for k, line in enumerate(x["sub"], 1)]
    return out + ([""] + post if post else [])


def book_md(book, build):
    """难句本.md：前半「一、自己拆」只有原句、注、试，后半「二、对照」是讲解；两半用锚点互相跳。
    题面的几行用行尾的反斜杠换行（CommonMark 的硬换行），不然多数阅读器会把它们连成一段。"""
    out = [f"# 难句本：{book['title']}{book['scope']}", "", SB_INTRO, "", "## 一、自己拆", ""]
    if not book["entries"]:
        out += ["（还没有句子：难句本收各单元的长难句和卡句，标签是词汇的卡句不收。）", ""]
    for g in book["groups"]:
        items, see = g["items"], g["see"]
        out += [f"### {g['tag']}（{len(items)} 句）" if items else f"### {g['tag']}（另见 {len(see)} 句）", ""]
        if g["definition"] and items:          # 只有另见的组：只印组名和另见行
            out += [f"{g['definition']}。读法：{g['how']}。", ""]
        for k, e in enumerate(items, 1):
            b, a = e["block"], e["anchor"]
            lines = [f'{k}. <a id="q-{a}"></a>{b["quote"]}']
            if b.get("notes"):
                lines.append(f"   注：{notes_text(b['notes'])}")
            q = (b.get("try") or {}).get("q")
            lines.append(f"   {'试：' + q + '　' if q else ''}[对照](#a-{a})　〔{e['label']}〕")
            out += [line + "\\" for line in lines[:-1]] + lines[-1:]
        if items:
            out.append("")
        if see:
            out += ["另见：" + "、".join(f"[{e['label']}](#q-{e['anchor']})" for e in see), ""]
    out += ["## 二、对照", ""]
    for g in book["groups"]:
        if not g["items"]:
            continue
        out += [f"### {g['tag']}", ""]
        for e in g["items"]:
            a = e["anchor"]
            out += [f'#### <a id="a-{a}"></a>{e["label"]}　{e["block"]["title"]}', ""]
            out += block_md(e["block"], build)
            out += ["", f"[回到题面](#q-{a})", ""]
    return "\n".join(out).rstrip("\n") + "\n"


def book_rows(book):
    """难句本.tsv 的行（13 列，见 SB_COLUMNS），顺序同难句本.md：按组，组内按单元号、原文位置。"""
    rows = []
    for g in book["groups"]:
        for e in g["items"]:
            b = e["block"]
            t = b.get("try") or {}
            drill = not e["stuck"] and e["type"] == "练习"
            rows.append([e["id"], b["quote"], notes_text(b.get("notes", [])), plain(t.get("q")), plain(t.get("a")),
                         trunk(b.get("chunks", [])), " / ".join(c["text"] for c in b.get("chunks", [])),
                         "／".join(b.get("gloss", [])), "" if drill else plain(item_text(b, "卡点")),
                         "" if drill else plain(item_text(b, "译")),
                         " ".join(x.replace(" ", "") for x in e["tags"]), e["source"], e["type"]])
    return rows


def cmd_sentences(args, build):
    flags, out_dir = take_flags(args, ("--anki", "--pdf"), "sentences", out=True, build=build)
    if build.P.format < 3:
        print(f"{OLD_FORMAT}，难句本要第三版：第三版的句子块才有结构标签和断句表。"
              "升级要重写句子块（README「从第二版升级」）；单词本（build.py words）第一、二版也能用。")
        return 1
    if not build.available():
        sys.exit(build.no_units())
    book = sentence_book(build)
    for w in book["warnings"]:
        print(f"  ! {w}")
    rows = book_rows(book)
    build.flat_note()
    write(build.out_path(out_dir, SB_FILES[0]), book_md(book, build))
    write(build.out_path(out_dir, SB_FILES[1]), tsv(rows))
    if "--anki" in flags:
        write(build.out_path(out_dir, SB_FILES[2]), tsv(rows, SB_ANKI))
    elif build.out_path(out_dir, SB_FILES[2]).exists():
        print(f"  ! {SB_FILES[2]} 是以前加 --anki 生成的，这次没有更新")
    see = sum(len(g["see"]) for g in book["groups"])
    print(f"难句本 {len(rows)} 句，{sum(1 for g in book['groups'] if g['items'])} 组"
          + (f"，另见 {see} 处" if see else "") + (f"；标签是词汇的卡句 {book['skipped']} 句不收" if book["skipped"] else ""))
    if "--pdf" in flags:
        if not book["entries"]:
            print(f"难句本里没有句子，不出 {SB_PDF}")
            return 0
        build.font_warnings()
        book_pdf(book, build, build.out_path(out_dir, SB_PDF))
    return 0


# ---------- 难句本.pdf ----------
# 和 build.py pdf 同一套排法：A5、同样的字体和页边，句子块用 build.py 的断句网格、标签小框；排版只走 build.render_pdf
# （renderer.py 装的 chrome-headless-shell）。第一页是书名、范围和三行用法（没有封面）；「一、自己拆」每组从新的一页起，
# 只有另见的组接在前一组后面；「二、对照」另起一页。题面每句点到对照，对照的编号点回题面。
# 读得回 PDF 的文字时（build.pdf_words），排第二遍，题面每组标题旁印「对照见第 N 页」；读不回就不印。

SB_PDF = "难句本.pdf"
SB_USAGE = ("先看「一、自己拆」：读原句，答下面的问题。", "再翻到「二、对照」，看断句表、答案和讲解。", "编号开头是章号，没读到的章先跳过。", REREAD)

SB_CSS = """
@page sb-intro{margin-top:18mm}
section.sbi{padding-top:4mm}
.sbi .ck{font:500 7.8pt/1 var(--sans);letter-spacing:.4em;color:var(--soft);margin-top:30mm}
.sbi h1.fh{font:600 24pt/1.15 var(--en);color:var(--g);margin:5mm 0 3mm}
.sbi .sbs{font:500 11pt/1.4 var(--sans);color:var(--ink);letter-spacing:.08em}
.sbi .rule{width:20mm;height:1.2pt;background:var(--r);margin:9mm 0 6mm}
.sbi ol.sbu{margin:0;padding-left:1.3em;font-size:9.6pt;line-height:1.9;color:var(--ink2)}
.sbi ol.sbu li::marker{color:var(--r)}
.sbi .sbc{margin-top:6mm;font:8pt/1.8 var(--sans);color:var(--soft)}
.sgh{display:flex;align-items:baseline;gap:3mm;margin:0 0 1.6mm;break-after:avoid}
h3.sgt{font:600 12pt/1.35 var(--sans);color:var(--g);margin:0}
.sbp{margin-left:auto;font:8pt/1.4 var(--sans);color:var(--soft);white-space:nowrap}
.sbp::after{content:" →";color:var(--r)}
p.sgd{font-size:9.2pt;line-height:1.6;color:var(--ink)}
p.sgr{font-size:9pt;line-height:1.6;color:var(--ink2);margin:0 0 4mm}
.sgr .sbk{margin-right:1.6mm}
ol.sbl{list-style:none;margin:0;padding:0}
ol.sbl>li{display:grid;grid-template-columns:5.4mm 1fr auto;column-gap:1.6mm;margin:0 0 4mm;break-inside:avoid}
.sbl .sbn{font:600 10pt/1.55 var(--en);color:var(--g)}
.sbl .orig{font-size:10pt;line-height:1.55;margin:0 0 1.2mm;padding-left:3mm}
.sbl .sbt,.sbl .sbz{font-size:8.8pt;line-height:1.5;color:var(--ink2);padding-left:3mm}
.sbl .sbz{color:var(--soft)}
.sbk{font:600 7.4pt/1 var(--sans);color:var(--g);letter-spacing:.06em;margin-right:2mm}
a.sbl-a{font:8pt/1.55 var(--en);color:var(--r);white-space:nowrap}
p.sbsee{font-size:8.6pt;color:var(--soft);margin:0 0 4mm}
p.sbsee a{color:var(--g)}
.sba-sec h3.sgt{margin:5mm 0 2.6mm;break-after:avoid}
.sba-sec>h2.sk+h3.sgt{margin-top:0}
/* 组标题不单独落在页末（实排时三组的标题和第一句分在两页）：对照里的 .pt 没用，去掉，标题行不和组标题分开 */
.sba-sec article.sent>.pt{display:none}
.sba-sec h3.sgt+article.sent>.sth{break-before:avoid}
.sba-sec h4.st{font:600 10pt/1.4 var(--sans);color:var(--ink);margin:0}
.sba-sec h4.st .sn{font:600 11pt var(--en);color:var(--g);margin-right:1mm}
p.sbtry{font-size:9pt;line-height:1.55;margin:0 0 1.9mm}
p.sbtry .c{color:var(--g)}
"""


def try_line(t, b, answer=False):
    """「试：问题」一行；对照里后面加「答：答案」。b 是 build 模块。"""
    t = t or {}
    if not t.get("q"):
        return ""
    a = f'　<span class="sbk">答</span><span class="c">{b.esc(t["a"])}</span>' if answer and t.get("a") else ""
    return f'<p class="{"sbtry" if answer else "sbt"}"><span class="sbk">试</span>{b.pinline(t["q"])}{a}</p>'


def book_html(book, build, pages=None):
    """难句本.pdf 的 HTML。pages：{组名: 对照里这组起始的页码}，有就在题面每组标题旁印「对照见第 N 页」。"""
    b = build
    title = book["title"]
    head = f"{title} · 难句本"
    n_groups = sum(1 for g in book["groups"] if g["items"])
    intro = (f'<section class="front sbi" style="page:sb-intro"><div class="ck">难句本</div><h1 class="fh">{b.esc(title)}</h1>'
             + (f'<p class="sbs">{b.esc(book["scope"].strip("（）"))}</p>' if book["scope"] else "")
             + '<div class="rule"></div><ol class="sbu">' + "".join(f"<li>{b.pinline(x)}</li>" for x in SB_USAGE) + "</ol>"
             f'<p class="sbc">{len(book["entries"])} 句，按结构分 {n_groups} 组</p></section>')
    # 一、自己拆：每组一页；只有另见的组接在前一组后面
    secs = []
    for k, g in enumerate(book["groups"], 1):
        items, see = g["items"], g["see"]
        page = (pages or {}).get(g["tag"]) if items else None
        h = [f'<div class="sgh"><h3 class="sgt" id="qg-{k}">{b.esc(g["tag"])}（{len(items)} 句）</h3>'
             + (f'<a class="sbp" href="#ag-{k}">对照见第 {page} 页</a>' if page else "") + "</div>"
             if items else f'<div class="sgh"><h3 class="sgt" id="qg-{k}">{b.esc(g["tag"])}（另见 {len(see)} 句）</h3></div>']
        if g["definition"] and items:          # 只有另见的组：只印组名和另见行
            h.append(f'<p class="sgd">{b.pinline(g["definition"])}。</p>')
        if g["how"] and items:
            h.append(f'<p class="sgr"><span class="sbk">读法</span>{b.pinline(g["how"])}。</p>')
        lis = []
        for j, e in enumerate(items, 1):
            s, a = e["block"], e["anchor"]
            z = (f'<p class="sbz"><span class="sbk">注</span>'
                 + " · ".join(f'<span class="c">{b.esc(w)}</span> {b.pinline(x)}' for w, x in s.get("notes") or []) + "</p>"
                 if s.get("notes") else "")
            lis.append(f'<li id="q-{a}"><span class="sbn">{j}</span><div><p class="orig">{b.esc(s["quote"])}</p>'
                       f'{try_line(s.get("try"), b)}{z}</div><a class="sbl-a" href="#a-{a}">〔{b.esc(e["label"])}〕</a></li>')
        if lis:
            h.append(f'<ol class="sbl">{"".join(lis)}</ol>')
        if see:
            h.append('<p class="sbsee">另见：' + "、".join(f'<a href="#q-{e["anchor"]}">{b.esc(e["label"])}</a>' for e in see)
                     + "</p>")
        if items or not secs:
            secs.append([])
        secs[-1] += h
    q = "".join(f'<section class="post sbq-sec" style="page:sb-q"><div class="pt"></div>'
                + ('<h2 class="sk">一、自己拆</h2>' if k == 0 else "") + "".join(h) + "</section>"
                for k, h in enumerate(secs))
    # 二、对照：另起一页，组的顺序相同
    a = []
    for k, g in enumerate(book["groups"], 1):
        if not g["items"]:
            continue
        a.append(f'<h3 class="sgt" id="ag-{k}">{b.esc(g["tag"])}（{len(g["items"])} 句）</h3>')
        for e in g["items"]:
            s = e["block"]
            items = [it for it in s["items"] if it["label"] in ANSWER_LABELS]
            a.append(f'<article class="sent v3" id="a-{e["anchor"]}"><div class="pt"></div>'
                     + b.sent_title_v3(s, b.esc(e["label"]), "h4", f'#q-{e["anchor"]}')
                     + b.grid_html(s) + b.notes_html(s.get("notes")) + try_line(s.get("try"), b, True)
                     + "\n".join(b.items_html(items)) + "</article>")
    ans = (f'<section class="post sba-sec" style="page:sb-a"><div class="pt"></div><h2 class="sk">二、对照</h2>'
           + "".join(a) + "</section>")
    css = (f'@page sb-q{{@top-left{{content:{b.css_str(head)}}}@top-right{{content:"自己拆"}}}}'
           f'@page sb-a{{@top-left{{content:{b.css_str(head)}}}@top-right{{content:"对照"}}}}')
    if not b.FONT_DIR:
        b.FONT_DIR.append(b.font_dir())
    return (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{b.esc(title)} 难句本</title>'
            f"<style>{b.pdf_font_css(b.FONT_DIR[0])}{b.PDF_CSS}{b.PDF_CSS_V2}{b.PDF_CSS_V3}{SB_CSS}{b.font_override_css()}\n{css}</style>"
            f"<body>{intro}{q}{ans}</body></html>")


def answer_pages(words, book, build):
    """读回的 PDF 文字里，「二、对照」各组起始的页码：{组名: 页码}。只看页眉是「书名 · 难句本 对照」的页，
    按组的顺序往后找组标题（「主谓隔开（3 句）」）。有一组找不到就返回 None（题面一律不印页码）。"""
    if not words:
        return None
    head = build.page_key(f"{book['title']} · 难句本" + "对照")
    idx = [i for i, p in enumerate(words) if p["head"] == head]
    out, k = {}, 0
    for g in book["groups"]:
        if not g["items"]:
            continue
        key = build.page_key(f"{g['tag']}（{len(g['items'])} 句）")
        hit = next((j for j in idx[k:] if key in words[j]["text"]), None)
        if hit is None:
            return None
        out[g["tag"]] = hit + 1
        k = idx.index(hit)
    return out


def book_pdf(book, build, target):
    """排 难句本.pdf：排一遍，读回各组对照的页码，读得回就带上页码再排一遍。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    build.render_pdf(book_html(book, build), target)
    pages = answer_pages(build.pdf_words(target), book, build)
    if pages:
        build.render_pdf(book_html(book, build, pages), target)
        if answer_pages(build.pdf_words(target), book, build) != pages:
            print("  ! 对照的页码和第二遍排版不一致，请检查")
    else:
        print("  ! 没能从 PDF 里读回各组对照的页码，题面不印「对照见第 N 页」")
    print(target)


# ---------- 卡句定位 ----------

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


def parse_mark(tail):
    """行尾「｜」后面的标记 → (标记, [用户列的生词], 提示或 "")。认不出的按没说，给一条提示。"""
    t = tail.strip()
    if t in ("词都认识", "有生词", "没说", ""):
        return t or "没说", [], ""
    m = re.fullmatch(r"有生词\s*[：:]\s*(.*)", t)
    if m:
        return "有生词", [w.strip() for w in re.split(r"[,，、;；]", m.group(1)) if w.strip()], ""
    return "没说", [], f"认不出的标记「{t}」，按没说（写成 ｜词都认识、｜有生词 或 ｜有生词：词, 词）"


def parse_stuck_file(text, units):
    """卡句.txt 的内容 → [{line, text, mark, mark_words, scope, notes}…]。units：项目里有原文的单元号。
    # 开头的行、空行跳过；「第 N 章」（章、部分、篇，前面可以有 #）或「[N]」是单元行（见 UNIT_LINE），管到下一个单元行；
    别的行一行一句：去掉行首的 - * 1. > 和两头的引号，最后一个 ｜ 或 | 后面是标记。scope 是单元号，全书找是 None。"""
    out, scope, scope_note = [], None, ""
    for k, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().lstrip("\ufeff")
        m = UNIT_LINE.fullmatch(line)
        if m and (not m.group(4).strip() or (not m.group(1) and re.match(r"[\s：:]", m.group(4)))):
            n = cn_int(m.group(2)) if m.group(2) else int(m.group(3))
            scope, scope_note = (n, "") if n in units else (None, f"第 {k} 行的单元行「{line}」不在项目里（或没有原文），全书找")
            continue
        if not line or line.startswith("#"):
            continue
        mark, words, notes = "没说", [], [scope_note] if scope_note else []
        cut = max(line.rfind("|"), line.rfind("｜"))
        if cut >= 0 and not line[cut + 1:].strip():          # 行尾多写了一个 ｜：标记在前一段
            line = line[:cut].rstrip()
            cut = max(line.rfind("|"), line.rfind("｜"))
        if cut >= 0:
            mark, words, why = parse_mark(line[cut + 1:])
            notes += [why] if why else []
            line = line[:cut].strip()
        for _ in range(2):
            line = LEAD.sub("", line, count=1) if LEAD.match(line) else line
        line = line.strip()
        if len(line) > 1 and line[0] in QUOTES and line[-1] in QUOTES:
            line = line[1:-1].strip()
        if not EN_WORD.search(line):                         # 没有英文词（只剩标记、标题之类）：跳过，不进小结
            continue
        out.append({"line": k, "text": line, "mark": mark, "mark_words": words, "scope": scope, "notes": notes})
    return out


def nearest(words, srcs):
    """近似：在各单元的词串里滑动窗口（长度和卡句一样，或多一个、少一个词），窗口和卡句的词串（用空格连成字符串）
    比 difflib 的相似度，取最高的、不低于 NEAR 的一处。先按相同的词数预筛，只有过了的窗口才算相似度。
    返回 (相似度, Source, 起点, 窗口长度) 或 None。"""
    L, target, need = len(words), " ".join(words), Counter(words)
    floor = math.ceil(L * NEAR_FLOOR)
    sm = difflib.SequenceMatcher(None, "", target, autojunk=False)
    best = None
    for S in srcs:
        toks = S.tokens
        for w in (L, L - 1, L + 1):
            if w < 1 or w > len(toks):
                continue
            win = Counter(toks[:w])
            over = sum(min(win[t], c) for t, c in need.items())
            for i in range(len(toks) - w + 1):
                if i:
                    old, new = toks[i - 1], toks[i + w - 1]
                    if win[old] <= need[old]:
                        over -= 1
                    win[old] -= 1
                    win[new] += 1
                    if win[new] <= need[new]:
                        over += 1
                if over < floor:
                    continue
                sm.set_seq1(" ".join(toks[i:i + w]))
                if sm.real_quick_ratio() < NEAR or sm.quick_ratio() < NEAR:
                    continue
                r = sm.ratio()
                if r >= NEAR and (best is None or r > best[0]):
                    best = (r, S, i, w)
    return best


def locate_one(x, srcs, build):
    """卡句.txt 的一行在 srcs（Source 的列表）里找。结果见 locate_stuck。"""
    words = build.stuck_words(x["text"])
    r = {**x, "notes": list(x["notes"]), "result": "", "unit": None, "sentence": "", "places": [], "score": None,
         "count": len(words)}
    hits, seen = [], set()
    for S in srcs:
        for i in S.find(words):
            if (S.n, S.sent_of[i]) not in seen:                 # 同一句里出现两次只算一处
                seen.add((S.n, S.sent_of[i]))
                hits.append((S, i))
    places = [{"unit": S.n, "sentence": S.sentences[S.sent_of[i]]} for S, i in hits]
    if len(hits) == 1:
        S, i = hits[0]
        a, b = S.covering(i, len(words))
        r.update(result="命中", unit=S.n, sentence=S.sentences[a])
        if b > a:
            r["notes"].append(f"跨了 {b - a + 1} 句，取第一句；下一句是「{clip(S.sentences[a + 1], 60)}」")
    elif len(words) < MIN_WORDS:
        r.update(result="太短", places=places)
    elif hits:
        r.update(result="多处", places=places)
    else:
        near = nearest(words, srcs)
        if near:
            score, S, i, w = near
            k = Counter(S.sent_of[i:i + w]).most_common(1)[0][0]     # 窗口里词最多的那一句
            r.update(result="近似", unit=S.n, sentence=S.sentences[k], score=round(score, 3))
        else:
            r["result"] = "找不到"
    return r


def locate_stuck(build, text=None):
    """卡句.txt 里每一句在原文里的位置。build 是 build.py 模块（P 已填好）；text 不给就读项目的 卡句.txt。
    返回 [{line（卡句.txt 的行号）, text（句子，去掉了标记和行首记号）, result（命中、多处、近似、找不到、太短）,
    unit（命中、近似时是单元号，别的是 None）, sentence（命中、近似时是定位到的原文句子，别的是 ""）,
    mark（词都认识、有生词、没说）, mark_words（用户列的生词）, scope（单元行给的单元号，全书找是 None）,
    places（多处、太短时每一处的 {unit, sentence}）, score（近似的相似度）, count（比对用的词数）,
    notes（提示：跨句、认不出的标记、单元行不对）}…]。没有 卡句.txt 时返回 []。"""
    if text is None:
        path = build.P.root / "卡句.txt"
        if not path.exists():
            return []
        text = path.read_bytes().decode("utf-8", errors="replace")     # 不是 UTF-8 的也不让 check 中断（stuck 另外报）
    get = sources(build)
    have = [n for n in build.unit_nums() if get(n)]
    out = []
    for x in parse_stuck_file(text, have):
        if x["scope"] not in have:
            out.append(locate_one(x, [get(n) for n in have], build))
            continue
        r = locate_one(x, [get(x["scope"])], build)
        if r["result"] in ("找不到", "近似") and len(have) > 1:        # 单元行可能写错了：全书再找
            g = locate_one(x, [get(n) for n in have if n != x["scope"]], build)
            if g["result"] == "命中" or (r["result"] == "找不到" and g["result"] == "近似"):
                g["notes"].append(f"不在{build.unit_name(x['scope'])}，在{build.unit_name(g['unit'])}")
                r = g
            elif g["result"] == "多处":
                r["notes"].append(f"别的{build.P.unit}有 {len(g['places'])} 处")
        out.append(r)
    return out


def covered_by(ch, text, sentence, build):
    """讲了没有：本单元哪个句子块（长难句「句 N」、卡句「卡句 N」）的原句包含卡句，或者原句和定位到的句子互相包含
    （同 build.stuck_covered）。没讲返回 ""。"""
    tw, sw = build.stuck_words(text), build.stuck_words(sentence)
    for blocks, tag in ((ch.get("sentences") or [], "句"), (ch.get("extra") or [], "卡句")):
        for s in blocks:
            qw = build.stuck_words(s["quote"])
            if build.has_run(qw, tw) or (sw and (build.has_run(sw, qw) or build.has_run(qw, sw))):
                return f"{tag} {s['i']}"
    return ""


def stuck_summary(items):
    """最后一行：「卡句 5 句：词都认识 3，有生词 1，没说 1。多数卡在句子上。」（哪一头占六成以上）"""
    n = len(items)
    if not n:
        return "卡句.txt 里没有句子。"
    c = Counter(x["mark"] for x in items)
    if c["词都认识"] >= 0.6 * n:
        tail = "多数卡在句子上。"
    elif c["有生词"] >= 0.6 * n:
        tail = "多数卡在词上。"
    elif c["没说"] >= 0.5 * n:
        tail = "多数没说卡在哪，看不出是词还是句子。"
    else:
        tail = "卡在词上和卡在句子上的差不多。"
    return f"卡句 {n} 句：词都认识 {c['词都认识']}，有生词 {c['有生词']}，没说 {c['没说']}。{tail}"


def cmd_stuck(args, build):
    flags, _ = take_flags(args, ("--json",), "stuck")
    if build.P.format < 3:
        print(f"{OLD_FORMAT}，卡句定位要第三版。第一、二版的项目照旧把用户卡住的句子写进「## 补充句」。")
        return 1
    path = build.P.root / "卡句.txt"
    if not path.exists():
        print(f"项目里没有 卡句.txt（{path}）：用户读的时候卡住的句子记在这里，一行一句。")
        return 0
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        print(f"{path} 不是 UTF-8 编码：另存成 UTF-8 再跑。")
        return 0
    items = locate_stuck(build)
    chapters = {ch["n"]: ch for ch in chapters_of(build)[0]}
    wl = build.Words(build.P.root)
    reader = wl.reader()
    why = (f"取不到词级数据（{wl.why}）" if not wl.lex else
           f"设置.json 的 level 不是 {'、'.join(wl.lx.LEVELS)} 之一" if reader is None else "")
    cases = {}
    for x in items:
        x["words"] = build.word_count(x["sentence"]) if x["sentence"] else None
        x["above"] = None
        x["covered"] = None
        if not x["sentence"]:
            continue
        n = x["unit"]
        if reader is not None:
            if n not in cases:
                case = cases[n] = Counter()
                for t in EN_WORD.findall(build.source_text(n)):
                    case[re.sub(r"['’]s$", "", t).lower()] += 1 if t[0].isupper() else -1
            x["above"] = build.above_words(x["sentence"], wl, reader, set(), cases[n])
        x["covered"] = covered_by(chapters[n], x["text"], x["sentence"], build) if n in chapters else None
    summary = stuck_summary(items)
    if "--json" in flags:
        print(json.dumps({"items": items, "summary": summary, "level": build.P.level, "level_note": why},
                         ensure_ascii=False, indent=1))
        return 0
    for x in items:
        print(stuck_line(x, build, why))
    if items:
        tally = Counter(x["result"] for x in items)
        print("，".join(f"{r} {tally[r]}" for r in RESULTS))
    print(summary)
    return 0


def stuck_line(x, build, why):
    """stuck 输出的一句：第一行是行号、结果、单元、句长、高于读者水平的词、标记、讲了没有；下面缩进几行是原文、各处、提示。"""
    mark = x["mark"] + (f"：{', '.join(x['mark_words'])}" if x["mark_words"] else "")
    head = f"第 {x['line']} 行　{x['result']}"
    sub = []
    if x["result"] in ("命中", "近似"):
        if x["result"] == "近似":
            head += f"（相似度 {x['score']:.2f}）"
        above = (f"高于水平的词没查（{why}）" if why else
                 f"高于 {build.P.level}：{'、'.join(x['above']) if x['above'] else '没有'}")
        covered = ("还没有讲义" if x["covered"] is None else f"讲了：{x['covered']}" if x["covered"] else "没讲")
        head += f"　{build.unit_name(x['unit'])}　{x['words']} 词　{above}　{mark}　{covered}"
        sub.append(f"原文：{x['sentence']}")
        if x["result"] == "近似":
            sub.append("给用户看这一句，确认了再用（常见原因是版本不同、抄错）；引文照原文抄")
    elif x["result"] == "多处":
        head += f"（{len(x['places'])} 处）　{mark}　请用户多贴几个词，或写上单元行"
        sub += [f"{build.unit_name(p['unit'])}：{clip(p['sentence'])}" for p in x["places"]]
    elif x["result"] == "太短":
        head += f"（{x['count']} 个词）　{mark}　请用户多贴几个词（{MIN_WORDS} 个以上），能唯一定位就行"
        sub += [f"{build.unit_name(p['unit'])}：{clip(p['sentence'])}" for p in x["places"]]
    else:
        scope = build.unit_name(x["scope"]) if x["scope"] else "全书"
        head += f"（{scope}）　{mark}　问用户是哪一{build.P.unit}、是不是别的版本；仍找不到的只在对话里讲"
    sub.insert(0, f"卡句：{clip(x['text'])}")
    sub += [f"! {n}" for n in x["notes"]]
    return "\n".join([head] + [f"    {s}" for s in sub])


# ---------- 单词本 ----------

def dict_parts(d, build):
    """词条的「词典」行 → (音标, 词性, 释义)：开头可以有词头（prepared /…/ adj. …），音标写在 /…/ 里，
    词性是 adj.、v.、phr. 这样的缩写（可以几个连写），释义是后面的部分。"""
    s = d.strip()
    head = build.dict_head(s)
    if head:
        s = s[s.index("/"):]
    ipa = pos = ""
    m = re.match(r"(/[^/]+/)\s*", s)
    if m:
        ipa, s = m.group(1), s[m.end():]
    m = re.match(r"([a-z]+\.(?:\s*[&/,，、]\s*[a-z]+\.)*)\s*", s)
    if m:
        pos, s = m.group(1), s[m.end():]
    return ipa, pos, s.strip()


def is_phrase(head, pos):
    return pos.rstrip(".") == "phr" or bool(re.search(r"\s", head.strip()))


def head_pattern(head, wl, build):
    """词头 → 比对用的 [原形集合或 None…]；None 是 sb、sth 这类占位词（原文里可以是 1–4 个词）。"""
    return [None if t.lower() in build.PLACEHOLDERS else wl.keys(t) for t in EN_WORD.findall(head)]


def match_at(toks, i, want):
    """want 从 toks[i] 开始对得上吗。toks 是各词的原形集合。"""
    if not want:
        return True
    if want[0] is None:
        return any(match_at(toks, i + k, want[1:]) for k in range(1, 5) if i + k <= len(toks))
    return i < len(toks) and bool(want[0] & toks[i]) and match_at(toks, i + 1, want[1:])


def first_sentence(head, sent_toks, S, wl, build):
    """本单元原文里第一个含这个词（按原形，带连字符的词也按拆开的各段比；短语按连续的几个词）的句子，标题行不算；
    没有是 ""。sent_toks：S 的各句、每句各词的原形集合。"""
    want = head_pattern(head, wl, build)
    if not [w for w in want if w is not None]:
        return ""
    for k, (toks, s) in enumerate(zip(sent_toks, S.sentences)):
        if k not in S.heading and any(match_at(toks, i, want) for i in range(len(toks))):
            return s
    return ""


def fragment_sentence(frag, S, build):
    """「原文：」引的那一段所在的整句（跨句的把几句连起来）；原文里找不到就返回 ""。"""
    words = build.stuck_words(frag)
    hits = S.find(words) if S else []
    if not hits:
        return ""
    a, b = S.covering(hits[0], len(words))
    return " ".join(S.sentences[a:b + 1])


def level_of(wl, word, pos=""):
    """lexicon.py 离线词表给的级别：「B2」「C1，估」「未定级」；取不到词级数据时是 ""。"""
    if not wl.lex:
        return ""
    p = pos.split(".")[0].strip() if pos else None
    lv = wl.level(word, None if p in (None, "", "phr") else p)
    return lv[2] if lv else wl.lx.UNRATED


def word_rows(build):
    """单词本的行，按单元，单元里依次是读前、词条、注（同一个词出现几次就是几行，不合并）。
    返回 ([{n, head, ipa, pos, gloss, sentence, trans, type, mastery, level}…], [提醒…])。"""
    chapters, warns = chapters_of(build)
    wl = build.Words(build.P.root)
    if not wl.lex:
        warns.append(f"取不到词级数据（{wl.why}）：级别一列空着，读前词按简单的后缀规则找原句")
    get = sources(build)
    rows = []
    for ch in chapters:
        n, S = ch["n"], get(ch["n"])
        sent_toks = [[wl.keys(t).union(*(wl.keys(p) for p in t.split("-") if p)) for t in EN_WORD.findall(s)]
                     for s in S.sentences] if (ch["preread"] and S) else []
        for w in (ch["preread"] or {}).get("words", []):
            sent = first_sentence(w["head"], sent_toks, S, wl, build) if S else ""
            if not sent:
                warns.append(f"{build.unit_name(n)}的读前词 {w['head']} 在原文里没找到原句")
            phrase = is_phrase(w["head"], w["pos"])
            rows.append({"n": n, "head": w["head"], "ipa": "" if phrase else w["ipa"],
                         "pos": "" if phrase or not w["pos"] else w["pos"] + ".", "gloss": w["gloss"],
                         "sentence": sent, "trans": "", "type": "读前", "mastery": "",
                         "level": level_of(wl, w["head"], w["pos"])})
        for u in ch["usage"]:
            ipa, pos, gloss = dict_parts(u["dict"], build)
            phrase = is_phrase(u["head"], pos)
            frag = u["quotes"][0] if u["quotes"] else ""
            sent = fragment_sentence(frag, S, build) if frag else ""
            if frag and not sent:
                warns.append(f"{build.unit_name(n)}的词条 {u['head']}：「原文」那一段在原文里没找到，原句一列照抄那一段")
            rows.append({"n": n, "head": u["head"], "ipa": "" if phrase else ipa, "pos": "" if phrase else pos,
                         "gloss": gloss or u["text"], "sentence": sent or frag,
                         "trans": u["trans"][0] if u["trans"] else "", "type": "词条", "mastery": u["level"],
                         "level": level_of(wl, build.dict_head(u["dict"]) or u["head"], pos)})
        for b in (ch.get("sentences") or []) + (ch.get("extra") or []):
            for word, gloss in b.get("notes") or []:
                rows.append({"n": n, "head": word, "ipa": "", "pos": "", "gloss": gloss, "sentence": b["quote"],
                             "trans": "", "type": "注", "mastery": "", "level": level_of(wl, word)})
    ids = dedupe_ids([f"{build.P.slug}-c{r['n']:02d}-" + re.sub(r"\s+", "_", r["head"].strip().lower()) for r in rows])
    for r, i in zip(rows, ids):
        r["id"] = i
    return rows, warns


def words_md(build, rows):
    """单词本.md：按单元分节，每节一张表（词、音标、词性、释义、类型、掌握、原句）。"""
    nums = sorted({r["n"] for r in rows}) or build.available()
    out = [f"# 单词本：{build.P.title}{scope_text(build, nums)}", "",
           f"读前的词、词条和句子里注过的词，按{build.P.unit}排；同一个词在两处出现就是两行。只是汇总，不记学没学会。", ""]
    if not rows:
        out += ["（还没有词。）", ""]
    titles = dict(build.P.units)
    for n in nums:
        mine = [r for r in rows if r["n"] == n]
        if not mine:
            continue
        name = build.unit_name(n)
        title = titles.get(n, "")
        out += [f"## {name}" + (f"　{title}" if title and title != name else ""), "",
                "| 词 | 音标 | 词性 | 释义 | 类型 | 掌握 | 原句 |", "| --- | --- | --- | --- | --- | --- | --- |"]
        out += [f"| {cell(r['head'])} | {cell(r['ipa'])} | {cell(r['pos'])} | {cell(r['gloss'])} | {r['type']} | "
                f"{cell(r['mastery'])} | {cell(r['sentence'])} |" for r in mine]
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def cmd_words(args, build):
    flags, out_dir = take_flags(args, ("--anki",), "words", out=True, build=build)
    if not build.available():
        sys.exit(build.no_units())
    rows, warns = word_rows(build)
    for w in warns:
        print(f"  ! {w}")
    table = [[r["id"], r["head"], r["ipa"], r["pos"], r["gloss"], r["sentence"], r["trans"], r["n"], r["type"],
              r["mastery"], r["level"]] for r in rows]
    build.flat_note()
    write(build.out_path(out_dir, WB_FILES[0]), words_md(build, rows))
    write(build.out_path(out_dir, WB_FILES[1]), tsv(table))
    if "--anki" in flags:
        write(build.out_path(out_dir, WB_FILES[2]), tsv(table, WB_ANKI))
    elif build.out_path(out_dir, WB_FILES[2]).exists():
        print(f"  ! {WB_FILES[2]} 是以前加 --anki 生成的，这次没有更新")
    c = Counter(r["type"] for r in rows)
    print(f"单词本 {len(rows)} 条：读前 {c['读前']}，词条 {c['词条']}，注 {c['注']}")
    return 0


if __name__ == "__main__":
    print("\n\n".join(__doc__.split("\n\n")[:2]))
    print("\n这个文件由 build.py 转发，不单独运行：用上面的 python3 build.py … 命令。")
    sys.exit(2)
