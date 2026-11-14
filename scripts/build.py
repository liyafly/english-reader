#!/usr/bin/env python3
"""英语讲义：格式检查、合订 Markdown、A5 小册子 PDF。只用 Python 标准库；PDF 另要 chrome-headless-shell 和 swift（只支持 macOS）。

  python3 build.py check [项目]                         核对格式和引文；另查禁用语、长度、直引号、术语、语法术语、
                                                        读前词的次数、理解答案和复述参考的句数。结果分「问题」（决定退出码）
                                                        和「提示」（估计出来的：词的级别、读后大约几页、术语表里没用到的）
  python3 build.py md    [项目] [--out 目录]             前言和各单元原样合订成 讲义-全本.md（单元标题降一级，正文不改）；
                                                        只有一个单元时不生成（源稿/第NN章.md 就是全文，前言单独看）
  python3 build.py pdf   [项目] [单元号…|all] [--out 目录]
                            不写单元号 = 合订本 讲义-全本.pdf；写单元号 = 分章 讲义-第NN章.pdf；
                            all = 合订本加各单元的分章（只有一个单元时只出 讲义-全本.pdf）
  python3 build.py sentences [项目] [--pdf] [--anki]     难句本.md、难句本.tsv（第三版的项目）
  python3 build.py words     [项目] [--anki]             单词本.md、单词本.tsv
  python3 build.py stuck     [项目] [--json]             卡句.txt 里的句子在原文里的位置（只读）
                            这三个由同目录的 notebook.py 做，build.py 只转发
  python3 build.py fonts     [项目]                     列出本机字体（按宋体、楷体、黑体、英文大致分组）；
                                                        给了项目再列它的 PDF 四种字体各用什么，本机没有的标「!」
  python3 build.py tidy      [项目]                     旧名字改成新的：讲义/ → 源稿/，输出挪进 成品/ 并改名（只挪不覆盖）
  项目目录可以写在其他参数前后（pdf all demo、pdf demo all 都行）。输出默认放在项目的 成品/ 里，给了 --out 就放到那个目录
  （里面照样有 导入/）。旧项目的根目录里已有 讲义.md、难句本.md 这些输出、又没有 成品/ 的，照旧输出到根目录、用旧名字；
  只有 讲义/ 没有 源稿/ 的旧项目，照旧读 讲义/。build.py tidy 把这些都改成新的。

项目目录（不写就是当前目录）。下面的「章」是 设置.json 里的 unit（章 / 部分 / 篇），文件名跟着变，如 第01部分.md、第01篇.txt：
  README.md       一屏的说明，链接到成品（人写，脚本不读）
  设置.json        title、author、unit、units、default_mode、level、genre、appreciation、writing、fonts
                  fonts：PDF 的字体。null 用系统字体；字符串是放 BookSong、BookKai 的目录；对象是各用什么字体：
                  {"宋体": …, "楷体": …, "黑体": …, "英文": …, "目录": …}（键也可写 song、kai、hei、en、dir，都可不写），
                  值是系统字体的 family 名、字体文件（.otf/.ttf/.ttc），或它们的列表（回退链）
                  每个单元是轻读还是精读：units 里写 "mode"，没写的用 default_mode；没有 default_mode 键时按精读（第一版的项目）
                  "format": 3 是第三版（句子块带结构标签和断句表，末尾是「## 卡句」）；没有这个键按第一、二版查，规则不变。
                  slug：难句本、单词本导出卡片的 id 前缀，不写就从 title 里取
  卡句.txt         第三版：读的时候卡住的句子（可以没有）。check 提示定位到了、讲义里却没讲的
  原文/第NN章.txt…  每个单元一份纯文本，段落之间空一行；引文核对的底本
  源稿/前言.md      可选：第一个「## 」之前是出处和缩写，之后每个「## 标题」在合订本前部各占一页
  源稿/第NN章.md…   每个单元一份讲义的源稿（人写、人改的都在这里）
  成品/            输出（脚本写，不要手改），文件名自带类别：讲义-全本.pdf、讲义-全本.md、讲义-第NN章.pdf…、
                  难句本.md、难句本.pdf、单词本.md；导入/：难句本.tsv、单词本.tsv、…-anki.tsv
  制作记录/         计划与检查.md（计划、台账、检查和审稿记录）、审稿/（人写，脚本不读）

合订本：封面、怎么用、目录、前言各页，然后各单元。封面、怎么用、目录按各单元的模式写。
第一、二版的精读单元：读前（有才排）、章首页（地图）、精讲句、词的用法、语法、赏析、写作、补充句（有才排）、自测、答案，各从新页开始。
第一、二版的轻读单元：读前一页；读后从新页起，理解、长难句、词的用法、复述、补充句（有才排）接着排，最后是答案。
  读前超过一页、读后（不含答案）超过 rules.json 的上限（light.pdf.post_pages）时提示，照常出 PDF。
第三版：句子块先印整句，再排断句网格（rules.json 的 v3.pdf.chunk_layout：对排或下置），标签小框，不印试和答；
  轻读的读后依次是长难句、理解、词的用法、复述，答案区先排「长难句 · 整句和译」；卡句另起一页，不算读后的页数。
排版打印用没有界面的 chrome-headless-shell（Google 官方，不是 App，不抢前台和键盘），先运行一次 renderer.py install 装好；
  环境变量 ER_CHROME 可以另指排版程序。本机带界面的 Chrome（Chromium、Edge、Brave）只在设了 ER_ALLOW_GUI_BROWSER=1 时用。
排紧和目录页码要读回 PDF 的文字：有 pdftotext 用它，没有就用 swift + PDFKit（装 Xcode 命令行工具就有）；
  都没有也能出 PDF，只是不自动排紧、目录没有页码。
数量规则和长度上限在同目录的 rules.json；禁用语和术语表在 ../reference/。
"""
import difflib
import hashlib
import html
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent           # scripts/
SKILL = HERE.parent
RULES = HERE / "rules.json"
BANNED = SKILL / "reference" / "禁用语.txt"
TERMS = SKILL / "reference" / "术语.tsv"
TEMPLATE = SKILL / "reference" / "前言模板.md"     # 「## 语法术语」表的第一列是要查的语法术语
LEGACY_TERMS = ["主干"]     # 第三版从模板里删掉的术语；第一、二版的项目照旧查
TAGS = SKILL / "reference" / "结构标签.tsv"       # 第三版：句子块「结构」能用的标签，行序是难句本的分组顺序
# 本机带界面的浏览器（只在 ER_ALLOW_GUI_BROWSER=1 时用）：按这个顺序在 /Applications、~/Applications 里找
CHROME_APPS = ("Google Chrome.app/Contents/MacOS/Google Chrome", "Chromium.app/Contents/MacOS/Chromium",
               "Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "Brave Browser.app/Contents/MacOS/Brave Browser")
UNITS = ("章", "部分", "篇")
LABELS = ["主干", "怎么拆", "卡点", "背景", "译", "句型", "延伸", "赏析"]
CITE = ("原文", "书中")                # 引原文的行：规范名「原文：」，旧名「书中：」
CITE_RE = "|".join(CITE)
USE_KEYS = ["词典", "掌握", *CITE, "译", "搭配", "辨析", "词族", "例", "注意"]
LEVELS = ("会用", "认得")
ESSAY = ("赏析", "文学赏析")            # 赏析一节：规范名「## 赏析」，旧名「## 文学赏析」
MODES = ("轻读", "精读")
PRE, EXTRA = "读前", "补充句"           # 两种模式都可以有：开头的「## 读前」（轻读必有），末尾的「## 补充句」
LIGHT_SECS = (PRE, "理解", "长难句", "词的用法", "复述")      # 轻读单元的小节，名字和顺序固定；最后可以再有补充句
LIGHT_LABELS = ("主干", "怎么拆", "卡点", "译", "背景")       # 轻读的长难句、两种模式的补充句只许这几个标签
POS = ("n", "v", "vt", "vi", "adj", "adv", "prep", "conj", "pron", "phr")   # 读前的词用的词性缩写
# 第三版（设置.json 的 "format": 3）
STUCK = "卡句"                                                # 第三版末尾的「## 卡句」（第一、二版叫补充句）
V3_LIGHT_SECS = (PRE, "长难句", "理解", "词的用法", "复述")     # 第三版轻读：长难句提到理解前面；最后可以再有卡句
V3_PRE = ("结构", "标记", "注", "试")                          # 句子块里写在断句表前面的项，按这个顺序
V3_POST = ("答", "怎么拆", "卡点", "译", "句型", "延伸", "赏析")   # 写在断句表后面的项，按这个顺序
V3_EXTRAS = ("怎么拆", "句型", "延伸", "赏析")                  # 只有精读的长难句可以写；轻读的精讲句可以写怎么拆
MARKS = ("词都认识", "有生词", "没说")                          # 「标记」：卡句的读者说卡在哪
VOCAB = "词汇"                                                # 只给卡句用的标签：结构不难，卡在词上
TABLE_HEAD = ["断句", "顺读"]                                   # 断句表的表头
INDENT = "· "                                                 # 断句栏行首的缩进记号（U+00B7 加一个空格），一个是一层
PLACEHOLDERS = {"sb", "sth", "sb's", "sth's", "one's", "oneself", "someone", "something"}   # 注的短语里的占位词


# ---------- 项目 ----------

class Project:
    """当前项目。load_project() 读 设置.json 填好，各处直接读 P。"""
    root = docs = src = out = None
    flat = False               # 旧项目：输出平铺在项目根目录（根目录已有输出、没有 成品/）
    title = author = level = genre = ""
    unit = "章"
    units = []                 # [(单元号, 标题)]，标题没写就是 ""
    modes = {}                 # {单元号: "轻读" / "精读"}
    default_mode = "精读"       # 设置.json 的 default_mode；没有这个键时按精读（第一版的项目）
    appreciation = writing = True      # 只对精读单元起作用
    fonts = None               # 设置.json 里的 fonts
    single = False             # unit 是「篇」且只有一个单元：不写「第 1 篇」
    review = None              # 自测题开头的「回头看（第 N 章）：」
    format = 2                 # 设置.json 的 format：3 是第三版；没有这个键是 2（第一、二版，规则不变）
    slug = "book"              # 导出卡片的 id 前缀：设置.json 的 slug，没写就从 title 里取


P = Project()


def load_project(path):
    root = Path(path).expanduser().resolve()
    conf = root / "设置.json"
    if not conf.exists():
        sys.exit(f"找不到 {conf}：项目目录里要有 设置.json")
    try:
        cfg = json.loads(conf.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"设置.json 不是合法的 JSON：{e}")
    # 源稿/ 是第三版的目录名；只有 讲义/ 的旧项目照旧读 讲义/（build.py tidy 可以改名）
    legacy_docs = not (root / DOCS_DIR).exists() and (root / OLD_DOCS_DIR).is_dir()
    P.root, P.docs, P.src = root, root / (OLD_DOCS_DIR if legacy_docs else DOCS_DIR), root / "原文"
    P.flat = not (root / OUT_DIR).exists() and any((root / name).exists() for name in FLAT_NAMES)
    P.out = root if P.flat else root / OUT_DIR
    P.title = str(cfg.get("title") or "").strip()
    if not P.title:
        sys.exit("设置.json 缺少 title")
    P.author = str(cfg.get("author") or "").strip()
    P.unit = str(cfg.get("unit") or "章").strip()
    if P.unit not in UNITS:
        sys.exit(f"设置.json 的 unit 只能是 {' / '.join(UNITS)}，不是「{P.unit}」")
    P.level, P.genre = str(cfg.get("level") or "").strip(), str(cfg.get("genre") or "").strip()
    P.appreciation = cfg.get("appreciation", True) is not False
    P.writing = cfg.get("writing", True) is not False
    P.fonts = cfg.get("fonts")
    P.default_mode = cfg.get("default_mode", "精读")      # 第一版的项目没有这个键，按精读
    if P.default_mode not in MODES:
        sys.exit(f"设置.json 的 default_mode 只能是 {' / '.join(MODES)}，不是「{P.default_mode}」")
    P.modes = {}
    if cfg.get("units"):
        try:
            rows = [(int(u), "", None) if isinstance(u, (int, str))
                    else (int(u["n"]), str(u.get("title") or "").strip(), u.get("mode")) for u in cfg["units"]]
        except (KeyError, TypeError, ValueError):
            sys.exit("设置.json 的 units 要写成 [{\"n\": 1, \"title\": \"…\", \"mode\": \"轻读\"}, …]（mode 可以不写）")
        for n, _, mode in rows:
            if mode is not None and mode not in MODES:
                sys.exit(f"设置.json 里第 {n} {P.unit}的 mode 只能是 {' / '.join(MODES)}，不是「{mode}」")
            if mode:
                P.modes[n] = mode
        P.units = sorted((n, t) for n, t, _ in rows)
    else:      # 没写 units：按 原文/第NN章.txt 推出单元号
        found = (re.fullmatch(rf"第(\d+){re.escape(P.unit)}", f.stem) for f in P.src.glob("*.txt"))
        P.units = sorted((int(m.group(1)), "") for m in found if m)
    if not P.units:
        sys.exit(f"没有单元：设置.json 里没写 units，原文/ 里也没有 第01{P.unit}.txt 这样的文件")
    P.modes = {n: P.modes.get(n, P.default_mode) for n, _ in P.units}
    P.single = P.unit == "篇" and len(P.units) == 1
    P.review = re.compile(rf"回头看（第\s*(\d+)\s*{re.escape(P.unit)}）：\s*")
    P.format = cfg.get("format", 2)
    if isinstance(P.format, str) and P.format.strip() in ("2", "3"):
        sys.exit(f"设置.json 的 format 要写数字 {P.format.strip()}，不加引号：\"format\": {P.format.strip()}")
    if isinstance(P.format, bool) or P.format not in (2, 3):
        sys.exit(f"设置.json 的 format 只能写 3（第三版）；第一、二版的项目不写这个键，不是「{P.format}」")
    P.slug = str(cfg.get("slug") or "").strip() or slug_of(P.title)


# 目录名：源稿/ 是人写的讲义（旧项目叫 讲义/），成品/ 是脚本生成的
DOCS_DIR, OLD_DOCS_DIR = "源稿", "讲义"
OUT_DIR = "成品"
# 生成的文件在 成品/ 里的路径：文件名自带类别，单独发出去也认得；只有 TSV 进 导入/。
# 键是文件的逻辑名（也是平铺的旧项目在根目录用的名字）。分章 PDF 是 讲义-第NN章.pdf，见 unit_pdf_path
OUT_PLACE = {"讲义.md": "讲义-全本.md", "讲义.pdf": "讲义-全本.pdf",
             "难句本.md": "难句本.md", "难句本.pdf": "难句本.pdf", "单词本.md": "单词本.md",
             "难句本.tsv": "导入/难句本.tsv", "难句本-anki.tsv": "导入/难句本-anki.tsv",
             "单词本.tsv": "导入/单词本.tsv", "单词本-anki.tsv": "导入/单词本-anki.tsv"}
FLAT_NAMES = (*OUT_PLACE, "分章")       # 平铺的旧项目：根目录里有这些，又没有 成品/
# 成品/ 的上一种布局（讲义.md、分章/、复习/）：tidy 挪成现在的名字
OLD_OUT = {"讲义.md": "讲义-全本.md", "讲义.pdf": "讲义-全本.pdf",
           "复习/难句本.md": "难句本.md", "复习/难句本.pdf": "难句本.pdf", "复习/单词本.md": "单词本.md"}


def out_path(out_dir, name):
    """生成的文件 name（逻辑名，见 OUT_PLACE）写到哪：平铺的旧项目直接放 out_dir，否则按 OUT_PLACE。"""
    return out_dir / name if P.flat else out_dir / OUT_PLACE[name]


def unit_pdf_path(out_dir, nums):
    """分章 PDF：成品/讲义-第01章.pdf（几个单元一起是 讲义-第01-02章.pdf）；平铺的旧项目是 分章/第01章.pdf。"""
    stem = f"第{'-'.join(f'{n:02d}' for n in nums)}{P.unit}"
    return out_dir / "分章" / f"{stem}.pdf" if P.flat else out_dir / f"讲义-{stem}.pdf"


def old_layout():
    """项目里还是旧名字的东西：讲义/（源稿）、成品/ 里上一种布局的文件。给 tidy 和提示用。"""
    out = P.root / OUT_DIR
    left = [f"{OLD_DOCS_DIR}/"] if P.docs.name == OLD_DOCS_DIR else []
    if out.is_dir():
        left += [f"{OUT_DIR}/{k}" for k in OLD_OUT if (out / k).exists()]
        left += [f"{OUT_DIR}/分章/{f.name}" for f in sorted((out / "分章").glob("*.pdf"))]
    return left


def flat_note():
    if P.flat:
        print(f"（旧项目：输出照旧放在项目根目录。build.py tidy 可以挪进 {OUT_DIR}/）")
    elif old_layout():
        print(f"（项目里还有旧名字：{'、'.join(old_layout()[:3])}{' 等' if len(old_layout()) > 3 else ''}。"
              f"build.py tidy 可以改成新的：{DOCS_DIR}/、{OUT_DIR}/讲义-全本.pdf 这样）")


def slug_of(title):
    """title 里的英文字母和数字，小写，用 - 连起来；取不出来就是 book。"""
    return "-".join(w.lower() for w in re.findall(r"[A-Za-z0-9]+", title)) or "book"


def unit_mode(n):
    """单元的模式：「轻读」或「精读」。"""
    return P.modes.get(int(n), P.default_mode)


def font_dir():
    """中文字体目录（BookSong 书宋、BookKai 书楷）：设置.json 的 fonts，其次环境变量 ENGLISH_READER_FONTS。
    都没有，或目录里没有 BookSong-Regular.otf，就用系统字体（宋体、楷体）。fonts 写成对象时，目录是它的「目录」键。"""
    for where, value in (("设置.json 的 fonts", font_spec(P.fonts)["dir"]),
                         ("环境变量 ENGLISH_READER_FONTS", os.environ.get("ENGLISH_READER_FONTS"))):
        if not value:
            continue
        d = project_path(value)
        if (d / "BookSong-Regular.otf").exists():
            return d
        print(f"  ! {where} 指的 {d} 里没有 BookSong-Regular.otf，跳过")
    return None


# ---------- PDF 的字体：设置.json 的 fonts 写成对象 ----------
# {"宋体": …, "楷体": …, "黑体": …, "英文": …, "目录": …}，键也可以写 song、kai、hei、en、dir，都可以不写。
# 值是系统字体的 family 名或字体文件（.otf/.ttf/.ttc），也可以是它们的列表（回退链）。
FONT_ROLES = (("song", "宋体"), ("kai", "楷体"), ("hei", "黑体"), ("en", "英文"))
FONT_KEYS = {"宋体": "song", "song": "song", "楷体": "kai", "kai": "kai", "黑体": "hei", "hei": "hei",
             "英文": "en", "en": "en", "目录": "dir", "dir": "dir"}
FONT_FILES = (".otf", ".ttf", ".ttc")
# 没写的用这些，和 PDF_CSS 里写死的一样。StudySong、StudyKai 是字体目录里的书宋、书楷，没有目录时不起作用
FONT_DEFAULTS = {"song": ["StudySong", "Songti SC"], "kai": ["StudyKai", "Kaiti SC", "STKaiti"],
                 "hei": ["PingFang SC", "Heiti SC"], "en": ["Iowan Old Style", "Charter", "Georgia"]}
FONT_OWN = {"StudySong", "StudyKai"}            # 不是系统字体，不查本机有没有
FONT_GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}


def project_path(value):
    """设置.json 里写的路径：~ 展开，相对路径从项目目录算。"""
    d = Path(str(value).strip()).expanduser()
    return d if d.is_absolute() else (P.root or Path.cwd()) / d


def font_spec(fonts):
    """拆开 fonts：{"dir": 目录（原样的字符串）或 None, "roles": {角色: [("name", 名字) / ("file", Path)]}, "problems": [说明]}。
    目录字符串和 null 是原来的写法，只有 dir。有问题的项不用（回到默认），说明放进 problems。"""
    spec = {"dir": None, "roles": {}, "problems": []}
    bad = spec["problems"].append
    if fonts is None or isinstance(fonts, str):
        spec["dir"] = fonts or None
        return spec
    if not isinstance(fonts, dict):
        bad("fonts 要写字体目录、对象（{\"宋体\": …, \"楷体\": …, \"黑体\": …, \"英文\": …}）或 null")
        return spec
    seen = {}
    for key, value in fonts.items():
        role = FONT_KEYS.get(key.strip())
        if role is None:
            bad(f"fonts 里不认识「{key}」：只认 宋体、楷体、黑体、英文、目录（或 song、kai、hei、en、dir）")
            continue
        if role in seen:
            bad(f"fonts 里「{seen[role]}」和「{key}」是同一项，只写一个")
            continue
        seen[role] = key
        if value is None:
            continue
        if role == "dir":
            if not isinstance(value, str) or not value.strip():
                bad(f"fonts 的「{key}」要写一个目录")
            elif not project_path(value).is_dir():
                bad(f"fonts 的「{key}」：目录 {project_path(value)} 不存在")
            else:
                spec["dir"] = value
            continue
        items = value if isinstance(value, list) else [value]
        if not items or not all(isinstance(v, str) and v.strip() for v in items):
            bad(f"fonts 的「{key}」要写字体名、字体文件路径（.otf/.ttf/.ttc），或它们的列表")
            continue
        chain = []
        for v in (v.strip() for v in items):
            if v.lower().endswith(FONT_FILES):
                f = project_path(v)
                if f.is_file():
                    chain.append(("file", f))
                else:
                    bad(f"fonts 的「{key}」：字体文件 {f} 不存在")
            elif "/" in v or "\\" in v:
                bad(f"fonts 的「{key}」：{v} 像路径，但不是 .otf/.ttf/.ttc 文件")
            else:
                chain.append(("name", v))
        if chain:
            spec["roles"][role] = chain
    return spec


def font_family(name):
    """CSS 的 font-family 里的一项：通用族名（serif 等）不加引号，其他加引号、转义。"""
    return name if name.lower() in FONT_GENERIC else css_str(name)


def font_override_css():
    """fonts 写成对象、写了宋体/楷体/黑体/英文时，接在默认 CSS 后面的覆盖：重设 :root 的字体变量、页眉页脚、.zq。
    英文字体在中文字体前面（英文字体没有中文字形，中文落到后面的中文字体）。没写这四项时是空串，默认输出不变。"""
    roles = font_spec(P.fonts)["roles"]
    if not roles:
        return ""
    faces, fam = [], {}
    for role, _ in FONT_ROLES:
        names = []
        for k, (kind, v) in enumerate(roles.get(role, [("name", n) for n in FONT_DEFAULTS[role]]), 1):
            if kind == "file":
                face = f"er-{role}-{k}"
                faces.append(f'@font-face{{font-family:"{face}";src:url({css_str(v.as_uri())});font-style:normal}}')
                names.append(css_str(face))
            else:
                names.append(font_family(v))
        fam[role] = names

    def stack(*roles, head=(), tail="serif"):
        """几个角色的字体连成一串，末尾补通用族名（已经以通用族名结尾就不补）。"""
        names = list(head) + [n for r in roles for n in fam[r]]
        return ",".join(names + ([] if names[-1] in FONT_GENERIC else [tail]))
    en_song, hei = stack("en", "song"), stack("hei", tail="sans-serif")
    return ("\n/* 设置.json 的 fonts */\n" + "".join(f + "\n" for f in faces)
            + f':root{{--en:{en_song};--body:{en_song};--kai:{stack("en", "kai")};'
              f'--sans:{stack("hei", head=[css_str("Helvetica Neue")], tail="sans-serif")}}}\n'
            + f"@page{{@top-left{{font-family:{hei}}}@top-right{{font-family:{hei}}}"
              f"@bottom-center{{font-family:{stack('en')}}}}}\n"
            + f".zq{{font-family:{stack('song')}}}\n"
            + f".kai .zq,.ctr .zq,.qtr .zq,p.tr .zq{{font-family:{stack('kai')}}}\n"
            + "h1 .zq,h2 .zq,h3 .zq,b .zq,.og .zq,.gh .zq,.eh .zq,ul.map .zq{font-family:inherit}\n")


def font_roles_now():
    """各角色现在用的字体：[(角色名, [名字或文件路径], 是不是 设置.json 写的)]。"""
    spec = font_spec(P.fonts)
    out = []
    for role, label in FONT_ROLES:
        if role in spec["roles"]:
            out.append((label, [str(v) for _, v in spec["roles"][role]], True))
        else:
            out.append((label, FONT_DEFAULTS[role], False))
    return out


def font_warnings():
    """排 PDF 前提示：fonts 写错的地方、本机找不到的字体名（Chrome 会静默换成别的字体）。取不到字体列表时不提示本机有没有。"""
    spec = font_spec(P.fonts)
    for msg in spec["problems"]:
        print(f"  ! 设置.json 的 {msg}，这一项用默认字体")
    if not spec["roles"]:
        return
    mine = [(label, names) for label, names, set_here in font_roles_now() if set_here]
    lost = font_lost([n for _, names in mine for n in names])
    for label, names in mine:
        for n in names:
            if n in lost:
                print(f"  ! 设置.json 的 fonts：{label}「{n}」本机没有，排出来会换成别的字体（build.py fonts 看本机有哪些）")


def unit_stem(n):
    """单元的文件名（不带扩展名）：第01章、第02部分、第01篇。"""
    return f"第{int(n):02d}{P.unit}"


def unit_path(n):
    return P.docs / f"{unit_stem(n)}.md"


def source_path(n):
    return P.src / f"{unit_stem(n)}.txt"


def no_units():
    return f"{P.docs} 里没有讲义（{unit_stem(1)}.md 这样的文件）"


def unit_nums():
    return [n for n, _ in P.units]


def available():
    return [n for n in unit_nums() if unit_path(n).exists()]


def unit_name(n):
    """「第 3 章」。只有一篇时不写「第 1 篇」：用篇名，没写篇名就用书名。"""
    if P.single:
        return dict(P.units).get(n) or P.title
    return f"第 {n} {P.unit}"


def running_head(n):
    """页眉左边：「书名 · 第 N 章」；只有一篇时只写书名。"""
    return P.title if P.single else f"{P.title} · 第 {n} {P.unit}"


def cn_num(k):
    digits = "零一二三四五六七八九"
    if not 0 < k < 100:
        return str(k)
    tens, ones = divmod(k, 10)
    return (("" if tens == 1 else digits[tens]) + "十" if tens else "") + (digits[ones] if ones else "")


# ---------- 解析 ----------
#
# parse_chapter(n) 返回的 ch（两种模式共有的键）：
#   n、mode（轻读 / 精读）、errors（格式问题）、raw（讲义全文）、note（一级标题和第一个「## 」之间的文字）、
#   secs（{小节标题: 正文}，标题按文件里写的）、order（小节标题按出现顺序，去掉首尾空白）、
#   preread（「## 读前」，没有就是 None）：{background: [段落…], people: [{name, role}…], words: [{head, ipa, pos, gloss}…]}、
#   sentences（长难句）、extra（补充句）：[{i, title, quote, items: [{label, text, sub: [行…]}…]}…]、
#   usage（词条）：[{head, text, dict, level, quotes, tags, trans, notes: [(标签, 内容)…]}…]。
# 精读另有：grammar_label、grammar_title、grammar、n_writing、writing_title、writing、has_essay、essay_label、essay、quiz、answers。
# 轻读另有：comprehension：{questions: [题…], answers: [{text, quotes, tags, trans}…]}；
#           retell（没有「## 复述」就是 None）：{prompts: [{question, hints: [提示词…]}…], refs: [参考…]}。
# 第三版（P.format == 3）的 ch 另有 format: 3；extra 放「## 卡句」的句子块（stuck 是同一个列表）。
#   sentences、extra 里每个句子块除了 i、title、quote、items，还有（见 parse_blocks_v3）：
#   kind（精讲 / 练习 / 卡句）、tags（结构标签，第一个是主标签）、mark（标记，没写是 None）、notes（[(词, 释义)…]）、
#   try（{q, a}，没写试和答是 None）、chunks（断句栏：[{depth, text, bold: [粗体片段…], md}…]，text 不带「· 」和星号，
#   md 是带星号的原样）、gloss（顺读栏，和 chunks 等长）。items 只放断句表后面的怎么拆、卡点、译、句型、延伸、赏析。

WORD_LINE = re.compile(r"- \*\*([^*]+?)\*\*\s+(?:(/[^/]+/)\s+)?([A-Za-z]+)\.\s*(.*)$")    # - **word** /ipa/ v. 释义
PERSON_LINE = re.compile(r"- \*\*(.+?)\*\*：(.+)$")                                     # - **人名**：身份


def cite_tag(line):
    """「原文：…」「书中：…」开头的行返回标签（按文件里写的显示），别的返回 None。"""
    return next((t for t in CITE if line.startswith(t + "：")), None)


def parse_chapter(n):
    """读一个单元的讲义，按这个单元的模式（设置.json）解析。格式问题记在 ch["errors"]；结构见本节开头。"""
    text = unit_path(n).read_text(encoding="utf-8")
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    head, order = parts[0], list(zip(parts[1::2], parts[2::2]))
    ch = {"n": int(n), "mode": unit_mode(n), "errors": [], "sentences": [], "usage": [], "secs": dict(order),
          "order": [t.strip() for t, _ in order], "preread": None, "extra": []}
    sec = {t.strip(): b for t, b in order}
    if P.format >= 3:                    # 第三版：句子块换成新写法，补充句改叫卡句（第一、二版走下面的老路，一行不改）
        ch["format"] = 3
        (parse_light_v3 if ch["mode"] == "轻读" else parse_intensive_v3)(ch, sec)
    elif ch["mode"] == "轻读":
        parse_light(ch, sec)
    else:
        parse_intensive(ch, sec)
    ch["note"] = "\n".join(l for l in head.splitlines()[1:] if l.strip())
    ch["raw"] = text
    return ch


def parse_intensive(ch, sec):
    """精读单元：第一版的六栏；最前面可以有「## 读前」，最后可以有「## 补充句」。"""
    secs, err = ch["secs"], ch["errors"].append
    if PRE in sec:
        if ch["order"][0] != PRE:
            err(f"「## {PRE}」要放在最前面")
        ch["preread"] = parse_preread(ch, sec[PRE])
    for want in ("长难句", "词的用法", "自测"):
        if want not in secs:
            err(f"缺少「## {want}」")
    # 语法：规范名「## 语法：题目」，旧名「## 本章语法：题目」；标签按文件里写的显示
    gram = [k for k in secs if k.split("：", 1)[0] in ("语法", "本章语法", f"本{P.unit}语法") and "：" in k]
    if len(gram) != 1:
        err("需要恰好一个「## 语法：…」")
    ch["grammar_label"] = gram[0].split("：", 1)[0] if gram else "语法"
    ch["grammar_title"] = gram[0].split("：", 1)[1] if gram else ""
    ch["grammar"] = secs.get(gram[0], "") if gram else ""
    # 写作：没有这一节的单元，PDF 里就不排
    writ = [k for k in secs if k.startswith("写作：")]
    ch["n_writing"] = len(writ)
    ch["writing_title"] = writ[0].split("：", 1)[1].strip() if writ else ""
    ch["writing"] = secs.get(writ[0], "") if writ else ""
    # 赏析：规范名「## 赏析」，旧名「## 文学赏析」
    ess = [k for k in secs if k.strip() in ESSAY]
    if len(ess) > 1:
        err("「## 赏析」只能有一个")
    ch["has_essay"] = bool(ess)
    ch["essay_label"] = ess[0].strip() if ess else ESSAY[0]
    ch["essay"] = secs.get(ess[0], "") if ess else ""
    ch["sentences"] = parse_sentences(ch, secs.get("长难句", ""))
    ch["usage"] = parse_usage(ch, secs.get("词的用法", ""))
    quiz = secs.get("自测", "")
    q, _, a = quiz.partition("**答案**")
    ch["quiz"] = re.findall(r"^\d+\. (.+)$", q, flags=re.M)
    ch["answers"] = re.findall(r"^\d+\. (.+)$", a, flags=re.M)
    if len(ch["quiz"]) != len(ch["answers"]) or not ch["quiz"]:
        err("自测题和答案数量不一致")
    if EXTRA in sec:
        if ch["order"][-1] != EXTRA:
            err(f"「## {EXTRA}」要放在最后")
        ch["extra"] = parse_sentences(ch, sec[EXTRA], EXTRA)
    for t in (PRE, EXTRA):
        if ch["order"].count(t) > 1:
            err(f"「## {t}」只能有一个")


def parse_light(ch, sec):
    """轻读单元：读前、理解、长难句、词的用法、复述，名字和顺序固定；最后可以有补充句。"""
    err, order = ch["errors"].append, ch["order"]
    names = LIGHT_SECS + (EXTRA,)
    for t in order:
        if t not in names:
            err(f"不认识的小节「## {t}」（轻读的小节依次是{'、'.join(LIGHT_SECS)}，最后可以有{EXTRA}）")
    for t in names:
        if order.count(t) > 1:
            err(f"「## {t}」只能有一个")
    for t in LIGHT_SECS:
        if t not in order:
            err(f"缺少「## {t}」")
    got = [t for i, t in enumerate(order) if t in names and t not in order[:i]]
    if got != [t for t in names if t in got]:
        err(f"小节顺序不对：应为{'、'.join(LIGHT_SECS)}，{EXTRA}放在最后")
    ch["preread"] = parse_preread(ch, sec[PRE]) if PRE in sec else None
    ch["comprehension"] = (parse_comprehension(ch, sec["理解"]) if "理解" in sec
                           else {"questions": [], "answers": []})
    ch["sentences"] = parse_sentences(ch, sec.get("长难句", ""))
    ch["usage"] = parse_usage(ch, sec.get("词的用法", ""))
    ch["retell"] = parse_retell(ch, sec["复述"]) if "复述" in sec else None
    ch["extra"] = parse_sentences(ch, sec[EXTRA], EXTRA) if EXTRA in sec else []


def parse_sentences(ch, body, kind="长难句"):
    """长难句或补充句（kind）：「### N. 考点」、空一行、「> 原句」，下面是「- **标签**：…」和缩进的续行。
    精读的长难句：标签在 LABELS 里，必有怎么拆、译（主干、卡点在 check 里查）。
    轻读的长难句、两种模式的补充句：只许 LIGHT_LABELS，必有主干、卡点、译；怎么拆可选，步数在 check 里查。"""
    err = ch["errors"].append
    extra = kind == EXTRA
    light = extra or ch["mode"] == "轻读"
    tag = f"{EXTRA} " if extra else "句 "
    out = []
    for chunk in re.split(r"^### ", body, flags=re.M)[1:]:
        m = re.match(r"(\d+)\. (.+)\n\n> (.+)\n", chunk)
        if not m:
            err(f"{EXTRA if extra else '句子'}格式不对：「{chunk[:30]}」")
            continue
        s = {"i": int(m.group(1)), "title": m.group(2), "quote": m.group(3), "items": []}
        for line in chunk[m.end():].splitlines():
            top = re.match(r"- \*\*(.+?)\*\*：(.*)$", line)
            if top:
                if top.group(1) not in LABELS:
                    err(f"{tag}{s['i']}：未知标签「{top.group(1)}」")
                elif light and top.group(1) not in LIGHT_LABELS:
                    err(f"{tag}{s['i']}：{EXTRA if extra else '轻读的长难句'}只许{'、'.join(LIGHT_LABELS)}，"
                        f"不写「{top.group(1)}」")
                s["items"].append({"label": top.group(1), "text": top.group(2), "sub": []})
            elif re.match(r"  \d+\. ", line) and s["items"]:
                s["items"][-1]["sub"].append(re.sub(r"^  \d+\. ", "", line))
            elif line.startswith("  ") and s["items"]:
                s["items"][-1]["sub"].append(line.strip())
            elif line.strip():
                err(f"{tag}{s['i']}：无法识别的行「{line[:30]}」")
        labels = [it["label"] for it in s["items"]]
        for need in (("主干", "卡点", "译") if light else ("怎么拆", "译")):
            if need not in labels:
                err(f"{tag}{s['i']}：缺少「{need}」")
        out.append(s)
    if [s["i"] for s in out] != list(range(1, len(out) + 1)):
        err(f"{EXTRA if extra else '长难句'}编号不连续，或有句子格式不对")
    return out


def parse_usage(ch, body):
    """词的用法：「- **词**：首行」，下面每行两个空格缩进，以 USE_KEYS 里的标签开头。"""
    out = []
    for m in re.finditer(r"^- \*\*(.+?)\*\*：(.+)\n((?:  .*\n?)*)", body, flags=re.M):
        # quotes、tags、trans 一一对应（tags 是这一行写的「原文」或「书中」，没写译文的是 ""）；
        # level 是「会用」「认得」或 ""；notes 里没有掌握和译
        u = {"head": m.group(1), "text": m.group(2), "quotes": [], "tags": [], "trans": [], "level": "", "dict": "", "notes": []}
        prev = ""
        for line in m.group(3).splitlines():
            k, _, v = line.strip().partition("：")
            if k not in USE_KEYS or not v:
                ch["errors"].append(f"词条 {u['head']}：无法识别的行「{line.strip()[:30]}」")
            elif k == "词典":
                u["dict"] = v
            elif k == "掌握":
                if u["level"]:
                    ch["errors"].append(f"词条 {u['head']}：「掌握」只能写一行")
                elif v.strip() not in LEVELS:
                    ch["errors"].append(f"词条 {u['head']}：「掌握」只能是会用或认得，不是「{v.strip()}」")
                else:
                    u["level"] = v.strip()
            elif k in CITE:
                u["quotes"].append(v.strip().strip("*"))
                u["tags"].append(k)
                u["trans"].append("")
            elif k == "译":
                if prev not in CITE:
                    ch["errors"].append(f"词条 {u['head']}：「译」要紧跟在「原文」下一行")
                else:
                    u["trans"][-1] = v.strip()
            else:
                u["notes"].append((k, v))
            prev = k
        out.append(u)
    return out


def parse_preread(ch, body):
    """「## 读前」（两种模式同一种写法）：背景一段；可选的人物列表「- **人名**：身份」；
    「### 本章的词」下每行一个词「- **word** /音标/ 词性. 释义」，短语「- **phrase** phr. 释义」。"""
    err = ch["errors"].append
    pre = {"background": [], "people": [], "words": []}
    parts = re.split(r"^### (.+)$", body, flags=re.M)
    para, stray = [], []       # stray：写在人物列表里、长得像读前词的行（漏了「### 本章的词」）
    for line in parts[0].splitlines() + [""]:
        if line.strip() and not line.startswith(("- ", "> ", "译：")):
            para.append(line.strip())
            continue
        if para:
            pre["background"].append("\n".join(para))
            para = []
        if line.startswith("- "):
            m = PERSON_LINE.match(line)
            if m:
                pre["people"].append({"name": m.group(1).strip(), "role": m.group(2).strip()})
            elif WORD_LINE.match(line):
                stray.append(line)
            else:
                err(f"读前的人物要写成「- **人名**：身份」：「{line[:30]}」")
    if not pre["background"]:
        err("读前缺少背景（列表前面写一段）")
    elif len(pre["background"]) > 1:
        err(f"读前的背景只写一段，现在 {len(pre['background'])} 段")
    want, found = f"本{P.unit}的词", False
    titles = (want, "本章的词")
    if stray and any(t.strip() in titles for t in parts[1::2]):
        err(f"读前的词要写在「### {want}」下面：「{stray[0][:30]}」")
    # 写错地方的读前词照常当读前词查（数量、和词条重复、复述的提示词），不再逐行报成人物写错
    for title, sub in [(None, "\n".join(stray))] + list(zip(parts[1::2], parts[2::2])):
        if title is not None:
            if title.strip() not in titles:
                err(f"读前里不认识的小标题「### {title.strip()}」（只有「### {want}」）")
                continue
            if found:
                err(f"「### {want}」只能有一个")
            found = True
        for line in sub.splitlines():
            if not line.strip():
                continue
            m = WORD_LINE.match(line)
            if not m:
                err(f"读前的词要写成「- **word** /音标/ 词性. 释义」，短语写成「- **phrase** phr. 释义」：「{line.strip()[:30]}」")
                continue
            head, ipa, pos, gloss = m.group(1).strip(), m.group(2) or "", m.group(3), m.group(4).strip()
            pre["words"].append({"head": head, "ipa": ipa, "pos": pos, "gloss": gloss})
            if pos not in POS:
                err(f"读前的词「{head}」：词性只用 {' '.join(p + '.' for p in POS)}，不是「{pos}.」")
            elif pos == "phr" and ipa:
                err(f"读前的词「{head}」：短语不写音标")
            elif pos != "phr" and not ipa:
                err(f"读前的词「{head}」：要写音标（/…/）；短语写 phr.")
            if not gloss:
                err(f"读前的词「{head}」：缺少本{P.unit}里的意思")
    if not found:
        err(f"读前缺少「### {want}」")
    return pre


def parse_comprehension(ch, body):
    """「## 理解」：「1. 题目」…；「**答案**」下每题「1. 一两句中文」，缩进的「原文：*…*」和紧跟的「译：…」。"""
    err = ch["errors"].append
    comp = {"questions": [], "answers": []}
    q, sep, a = body.partition("**答案**")
    if not sep:
        err("理解缺少「**答案**」")
    for line in q.splitlines():
        m = re.match(r"\d+\. (.+)$", line)
        if m:
            comp["questions"].append(m.group(1).strip())
        elif line.startswith(" ") and line.strip() and comp["questions"]:
            comp["questions"][-1] += "\n" + line.strip()
        elif line.strip():
            err(f"理解：无法识别的行「{line.strip()[:30]}」")
    cur, prev = None, ""
    for line in a.splitlines():
        m, s = re.match(r"\d+\. (.*)$", line), line.strip()
        if m:
            cur = {"text": [m.group(1).strip()], "quotes": [], "tags": [], "trans": []}
            comp["answers"].append(cur)
            prev = ""
        elif not s:
            continue
        elif line.startswith(" ") and cur:
            tag = cite_tag(s)
            if tag:
                cur["quotes"].append(s[len(tag) + 1:].strip().strip("*"))
                cur["tags"].append(tag)
                cur["trans"].append("")
            elif s.startswith("译："):
                if prev in CITE:
                    cur["trans"][-1] = s[2:].strip()
                else:
                    err(f"理解答案 {len(comp['answers'])}：「译」要紧跟在「原文」下一行")
            else:
                cur["text"].append(s)
            prev = tag or s.partition("：")[0]
        else:
            err(f"理解答案：无法识别的行「{s[:30]}」")
    for x in comp["answers"]:
        x["text"] = "\n".join(t for t in x["text"] if t)
    if sep and len(comp["questions"]) != len(comp["answers"]):
        err("理解题和答案数量不一致")
    return comp


def parse_retell(ch, body):
    """「## 复述」：一行「题目，提示词：word1, word2, word3」，一行「参考：English reference.」。
    别的行（如 A2 的引导问题）不查。"""
    err = ch["errors"].append
    r = {"prompts": [], "refs": []}
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("参考："):
            r["refs"].append(s[3:].strip())
        elif "提示词：" in s:
            q, _, h = s.partition("提示词：")
            hints = [x.strip(" *`。.") for x in re.split(r"[,，、;；]", h)]
            r["prompts"].append({"question": q.strip().rstrip("，,：:；; "), "hints": [x for x in hints if x]})
    if not r["prompts"]:
        err("复述缺少「提示词：…」（写成「题目，提示词：word1, word2, word3」）")
    if not r["refs"]:
        err("复述缺少「参考：…」")
    elif r["prompts"] and len(r["refs"]) != len(r["prompts"]):
        err(f"复述的「参考：」一题一行：现在 {len(r['prompts'])} 题、{len(r['refs'])} 行参考")
    return r


def source_text(n):
    """原文/NN.txt：段落之间空一行。段内的换行和连续空白并成一个空格，段落之间用一个空格连起来。"""
    t = source_path(n).read_text(encoding="utf-8").replace("﻿", "")
    paras = (re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n[ \t\r\f\v]*\n", t))
    return " ".join(p for p in paras if p)


def word_count(text):
    """英文词数：按空白切开、含字母的才算一个词（破折号、数字不算）。"""
    return sum(1 for tok in text.split() if re.search(r"[A-Za-z]", tok))


# ---------- 检查规则 ----------

def load_rules():
    try:
        return json.loads(RULES.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"找不到 {RULES}")
    except ValueError as e:
        sys.exit(f"rules.json 不是合法的 JSON：{e}")


def light_rules(rules):
    """rules.json 的 light 组：轻读单元和两种模式的「读前」「补充句」用。"""
    lr = rules.get("light")
    if not isinstance(lr, dict):
        sys.exit(f"{RULES} 里缺少 light 组（轻读单元、读前和补充句的数量与长度规则）")
    return lr


def light_post_pages(rules=None):
    """PDF 里轻读读后（不含答案）的页数上限：rules.json 的 light.pdf.post_pages，没写就是 3。"""
    lr = (rules or load_rules()).get("light") or {}
    return int((lr.get("pdf") or {}).get("post_pages", 3))


def post_cap():
    """PDF 里轻读读后（不含答案和卡句）的页数上限：第三版读 v3.light.pdf.post_pages，第一、二版读 light.pdf.post_pages。"""
    if P.format >= 3:
        lr = (load_rules().get("v3") or {}).get("light") or {}
        return int((lr.get("pdf") or {}).get("post_pages", 3))
    return light_post_pages()


def count_ranges(words, rules, mode="精读"):
    """按原文词数算数量规则。精读返回 {"精讲句": (最少, 最多), "词条": …, "赏析点": …, "自测": …}；
    轻读（mode="轻读"，读前也用它）返回 {"读前词": …, "人物": …, "理解": …, "长难句": …, "词条": …, "复述": …}。
    两种模式都按 counts.short_words 分长文、短文。"""
    c = rules["counts"] if mode == "精读" else light_rules(rules)["counts"]
    group = c["short"] if words < rules["counts"]["short_words"] else c["long"]
    out = {}
    for key, r in group.items():
        if key.startswith("_"):
            continue
        lo, hi = r["range"]
        if "per_1000" in r:      # 目标 = 每千词几个 × 词数，四舍五入后限在 target 里；允许上下差 slack，且不出 range
            t = min(max(math.floor(r["per_1000"] * words / 1000 + 0.5), r["target"][0]), r["target"][1])
            lo, hi = max(lo, t - r["slack"][0]), min(hi, t + r["slack"][1])
        out[key] = (lo, hi)
    return out


def span(lo, hi):
    """「2–3」；上下限相同时只写「2」。"""
    return f"{lo}" if lo == hi else f"{lo}–{hi}"


def need_count(ch, what, got, rng, words, unit_word):
    """数量不在 rng = (最少, 最多) 里就记一条：「理解需要 2–3 题（原文 4350 词），现在 1 题」。"""
    lo, hi = rng
    if lo <= got <= hi:
        return
    need = f"最多 {hi}" if lo == 0 else f"需要 {span(lo, hi)}"
    ch["errors"].append(f"{what}{need} {unit_word}（原文 {words} 词），现在 {got} {unit_word}")


def load_banned():
    """禁用语.txt：说法<TAB>类别<TAB>怎么改；说法以 re: 开头的是正则；# 开头是注释。改法写「同上」的沿用上一行的。"""
    rows, last = [], ""
    if not BANNED.exists():
        return rows
    for line in BANNED.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        pat, cat, fix = (line.split("\t") + ["", ""])[:3]
        fix = fix.strip()
        if fix in ("", "同上"):
            fix = last
        last = fix
        try:
            rx = re.compile(pat[3:] if pat.startswith("re:") else re.escape(pat))
        except re.error as e:
            sys.exit(f"禁用语.txt 里的正则写错了：{pat}（{e}）")
        rows.append((pat, cat.strip(), fix, rx))
    return rows


def norm_en(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def norm_word(s):
    """比对词头用：小写，弯撇号换成直的，去掉首尾标点和反引号、星号。"""
    return norm_en(s.replace("’", "'").replace("‘", "'")).strip(" `*.,;:!?，。；：")


def dict_head(d):
    """「词典」行开头写的词头，如「prepared /prɪˈpeəd/ adj. …」里的 prepared；没写词头返回 ""。"""
    m = re.match(r"\s*([A-Za-z][A-Za-z’' -]*?)\s*/", d)
    return m.group(1) if m else ""


def usage_vocab(ch):
    """本单元词条的词头和「词典」行的词头：{比对用的写法: 词条名}。"""
    out = {}
    for u in ch["usage"]:
        for h in (u["head"], dict_head(u["dict"])):
            if h:
                out.setdefault(norm_word(h), u["head"])
    return out


def load_terms():
    """术语.tsv：中文<TAB>English。返回 ({中文: {english…}}, {english: {中文…}})，英文一律小写。"""
    zh2en, en2zh = {}, {}
    if TERMS.exists():
        for line in TERMS.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            zh, _, en = line.partition("\t")
            zh, en = zh.strip(), norm_en(en)
            if zh and en:
                zh2en.setdefault(zh, set()).add(en)
                en2zh.setdefault(en, set()).add(zh)
    return zh2en, en2zh


def located_lines(ch):
    """讲义逐行配上位置，产出 (位置, 行)。位置如「句 3 赏析」「词条 lest 辨析」「语法·三步找主干」「赏析点 2」「自测 5」「答案 5」，
    以及「读前 背景」「读前 人物 Mole」「读前词 scull」「理解 2」「理解答案 2 译」「复述 参考」「补充句 1 卡点」。
    第三版的长难句和卡句另见 located_lines_v3。"""
    if ch.get("format", 2) >= 3:
        yield from located_lines_v3(ch)
        return
    kind, base, label, k_essay, in_ans, pre_words = "", "开头", "", 0, False, False
    for line in ch["raw"].splitlines():
        if line.startswith("# "):
            yield "标题", line
            continue
        m = re.match(r"## (.+)$", line)
        if m:
            name = m.group(1).strip()
            kind = ("sent" if name == "长难句" else "extra" if name == EXTRA else "words" if name == "词的用法"
                    else "quiz" if name == "自测" else "pre" if name == PRE else "comp" if name == "理解"
                    else "retell" if name == "复述"
                    else "essay" if name in ESSAY else "write" if name.startswith("写作：")
                    else "gram" if "：" in name and name.split("：", 1)[0] in ("语法", "本章语法", f"本{P.unit}语法") else "other")
            base = {"sent": "长难句", "extra": EXTRA, "words": "词的用法", "quiz": "自测", "essay": ch.get("essay_label", ESSAY[0]),
                    "write": "写作", "gram": "语法", "pre": PRE, "comp": "理解", "retell": "复述"}.get(kind, name)
            label, in_ans, pre_words = "", False, False
            yield f"{base} 小节标题", line
            continue
        if kind in ("sent", "extra"):
            m = re.match(r"### (\d+)\.", line)
            if m:
                base, label = f"{EXTRA if kind == 'extra' else '句'} {m.group(1)}", ""
                yield f"{base} 标题", line
                continue
            m = re.match(r"- \*\*(.+?)\*\*：", line)
            if m:
                label = m.group(1)
        elif kind == "words":
            m = re.match(r"- \*\*(.+?)\*\*：", line)
            if m:
                base, label = f"词条 {m.group(1)}", ""
            elif line.startswith("  ") and "：" in line:
                label = line.strip().split("：", 1)[0]
        elif kind in ("gram", "write") and line.startswith("### "):
            base = f"{'语法' if kind == 'gram' else '写作'}·{line[4:].strip()}"
        elif kind == "essay" and line.startswith("### "):
            k_essay += 1
            base = f"赏析点 {k_essay}"
        elif kind == "quiz":
            if line.strip() == "**答案**":
                in_ans = True
            m = re.match(r"(\d+)\. ", line)
            if m:
                base = f"{'答案' if in_ans else '自测'} {m.group(1)}"
        elif kind == "pre":
            m = re.match(r"- \*\*(.+?)\*\*", line)
            if line.startswith("### "):
                pre_words, base = True, "读前的词"
            elif m:
                base = f"读前词 {m.group(1)}" if pre_words else f"读前 人物 {m.group(1)}"
            elif line.strip():
                base = "读前的词" if pre_words else "读前 背景"
        elif kind == "comp":
            if line.strip() == "**答案**":
                in_ans = True
            m = re.match(r"(\d+)\. ", line)
            if m:
                base, label = f"{'理解答案' if in_ans else '理解'} {m.group(1)}", ""
            elif line.startswith(" ") and "：" in line:
                label = line.strip().split("：", 1)[0]
        elif kind == "retell":
            base = "复述 参考" if line.startswith("参考：") else "复述"
        yield f"{base} {label}".strip(), line


def is_translation(loc, line):
    """译文行：「译：…」「- **译**：…」，以及长难句「译」一项的续行。译文要忠实原文，不查禁用语。
    第三版断句表的顺读栏也算译文。"""
    return (bool(re.match(r"\s*(?:译：|- \*\*译\*\*：)", line)) or loc.endswith(" 译")
            or (P.format >= 3 and loc.endswith(" 顺读")))


def prose(line):
    """只留讲解文字：「> 」引文行整行不要；反引号里的内容、单星号斜体（原文：*…*、表格里的引文）去掉。"""
    if line.startswith(">"):
        return ""
    s = re.sub(r"`[^`]*`", " ", line)
    return re.sub(r"(?<!\*)\*(?!\*)[^*]+?\*(?!\*)", " ", s)


def plain_len(md):
    """栏目长度：去掉 Markdown 记号（# 标题、列表和引用记号、粗体斜体、反引号、表格竖线和分隔行）后，不算空白的字符数。"""
    s = re.sub(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*$", "", md, flags=re.M)
    s = re.sub(r"^#+ ", "", s, flags=re.M)
    s = re.sub(r"^\s*(?:[-*] |\d+\. |> )", "", s, flags=re.M)
    s = s.replace("*", "").replace("`", "").replace("|", "")
    return len(re.sub(r"\s+", "", s))


def sentence_items(sentences, tag="句"):
    """长难句或补充句里要限长的栏目。"""
    for s in sentences:
        b = f"{tag} {s['i']}"
        yield "句子标题", f"{b} 标题", s["title"]
        for it in s["items"]:
            lab, whole = it["label"], "\n".join([it["text"], *it["sub"]])
            if lab == "怎么拆":
                for k, step in enumerate(it["sub"], 1):
                    yield "怎么拆（每一步）", f"{b} 怎么拆第 {k} 步", step
            elif lab == "译":
                # 译文的上限随原句变长：取 max(译, 译_每个原文词 × 原句词数)
                yield lab, f"{b} {lab}", whole, len([w for w in s["quote"].split() if re.search("[A-Za-z]", w)])
            elif lab in ("主干", "卡点"):
                yield lab, f"{b} {lab}", whole
            elif lab == "延伸":
                yield "延伸（整项）", f"{b} 延伸", whole
            elif lab == "赏析":
                yield "句子赏析", f"{b} 赏析", whole


def length_items(ch):
    """要限长的栏目：产出 (栏目, 位置, Markdown 文字)。栏目名和 rules.json 的 max_chars、light.max_chars 对应。"""
    pre = ch.get("preread")
    if pre:
        for p in pre["background"]:
            yield "读前背景", "读前 背景", p
        for p in pre["people"]:
            yield "读前人物（每条）", f"读前 人物 {p['name']}", p["role"]
        for w in pre["words"]:
            yield "读前词释义", f"读前词 {w['head']}", w["gloss"]
    if ch["mode"] == "轻读":
        for k, q in enumerate(ch["comprehension"]["questions"], 1):
            yield "理解题", f"理解 {k}", q
        for k, a in enumerate(ch["comprehension"]["answers"], 1):
            yield "理解答案", f"理解答案 {k}", a["text"]
    yield from sentence_items(ch["sentences"])
    for u in ch["usage"]:
        yield "词条首行", f"词条 {u['head']}", u["text"]
        for k, v in u["notes"]:
            yield "词条用法行", f"词条 {u['head']} {k}", v
    if ch["mode"] == "轻读":
        for p in (ch["retell"] or {}).get("prompts", []):
            yield "复述题", "复述", p["question"]
    else:
        if ch["grammar"].strip():
            yield "语法一节", "语法", ch["grammar"]
        for k, (t, body) in enumerate(essay_points(ch["essay"])[1], 1):
            yield "赏析点", f"赏析点 {k}「{t}」", t + "\n" + body
        if ch["writing"].strip():
            yield "写作一节", "写作", ch["writing"]
        for k, q in enumerate(ch["quiz"], 1):
            yield "自测题", f"自测 {k}", q
        for k, a in enumerate(ch["answers"], 1):
            yield "答案", f"答案 {k}", a
    yield from sentence_items(ch["extra"], EXTRA)


def word_items(ch):
    """按英文词数限长的栏目（rules.json 的 light.max_words）：理解答案的引文、复述的参考。"""
    if ch["mode"] != "轻读":
        return
    for k, a in enumerate(ch["comprehension"]["answers"], 1):
        for q in a["quotes"]:
            yield "理解引文", f"理解答案 {k} 原文", q
    for r in (ch["retell"] or {}).get("refs", []):
        yield "复述参考", "复述 参考", r


TERM = re.compile(r"([㐀-鿿]+)(?:\*\*)?（([A-Za-z][^（）㐀-鿿]*)）")
# 「中文（English）」里的中文名：前面紧挨的一串汉字，去掉「这是」「叫」「一种」这类引出词之前的部分（只用于不查表的那一项）
NAME_CUT = re.compile(r"^.*(?:叫做|称为|就是|也是|都是|叫|是|这种|那种|一种|这个|那个|一个|一则|一组|一句|把|即)")


def lint(ch, rules, banned, terms, seen):
    """新增的四类检查：禁用语、长度、直引号、术语。产出 (类别, 说明)。
    禁用语不查译文行（is_translation）。seen 收集不在术语表里的「中文（English）」，全部单元查完再比（term_clashes）。"""
    zh2en, en2zh = terms
    limits = {**rules.get("max_chars", {}), **rules.get("light", {}).get("max_chars", {})}
    v3 = ch.get("format", 2) >= 3
    if v3:
        limits.update(v3_limits(rules, ch["mode"]))
    for loc, line in located_lines(ch):
        if v3 and loc.endswith((" 断句", " 答")):      # 第三版：断句栏和「答」是照原文抄的引文，不查
            continue
        s = prose(line)
        if not s.strip():
            continue
        if not is_translation(loc, line):
            for pat, cat, fix, rx in banned:
                for m in rx.finditer(s):
                    yield "禁用语", f"{loc}「{m.group(0)}」（{cat}）→ {fix}"
        if re.search(r"['\"]", s):
            k = re.search(r"['\"]", s).start()
            yield "直引号", f"{loc}：「{s[max(0, k - 12):k + 12].strip()}」里有 ASCII 引号，改成弯引号"
        for m in TERM.finditer(s):
            run, raw = m.group(1), m.group(2).strip()
            en, why = norm_en(raw), []
            tail = max((z for z in zh2en if run.endswith(z)), key=len, default=None)
            if tail and en not in zh2en[tail]:
                why.append(f"术语表里「{tail}」是 {' / '.join(sorted(zh2en[tail]))}")
            if en in en2zh and not any(z in run for z in en2zh[en]):
                why.append(f"术语表里 {raw} 叫「{'」或「'.join(sorted(en2zh[en]))}」")
            if why:
                yield "术语", f"{loc}「{run}（{raw}）」：{'；'.join(why)}"
            if en not in en2zh:
                seen.setdefault(en, []).append((NAME_CUT.sub("", run) or run, raw, f"{unit_name(ch['n'])} {loc}"))
    for field, loc, text, *words in (length_items_v3(ch) if v3 else length_items(ch)):
        cap = limits.get(field)
        if cap and words and limits.get(field + "_每个原文词"):
            cap = max(cap, math.ceil(limits[field + "_每个原文词"] * words[0]))
        if cap and plain_len(text) > cap:
            yield "长度", f"{loc}：{plain_len(text)} 字，{field}上限 {cap}"
    wcaps = rules.get("light", {}).get("max_words", {})
    for field, loc, text in word_items(ch):
        cap = wcaps.get(field)
        if cap and word_count(text) > cap:
            yield "长度", f"{loc}：{word_count(text)} 词，{field}上限 {cap} 词"


def term_clashes(seen):
    """全部单元合起来：同一个括号英文前面用了两个互不包含的中文名。"""
    for en, occ in seen.items():
        names = {}
        for name, raw, where in occ:
            names.setdefault(name, where)
        keys = list(names)
        if any(a not in b and b not in a for i, a in enumerate(keys) for b in keys[i + 1:]):
            yield f"（{occ[0][1]}）前面用了不同的中文名：" + "、".join(f"「{k}」（{names[k]}）" for k in keys)


def check_quote_trans(ch, skip=("长难句", EXTRA)):
    """长难句、补充句（skip 里的小节）以外，每段「> 原文」下面紧跟（可以隔一个空行）一行「译：」；「对照：」恰好两部分。"""
    for sec, body in ch["secs"].items():
        if sec.strip() in skip:
            continue
        short = sec.split("：")[0]
        lines = body.splitlines()
        for i, l in enumerate(lines):
            if l.startswith("> "):
                nxt = next((x for x in lines[i + 1:] if x.strip()), "")
                if not nxt.startswith("译："):
                    ch["errors"].append(f"{short}：引文后面缺少「译：」：「{l[2:32]}」")
            elif l.startswith("对照：") and len(l[3:].split(" / ")) != 2:
                ch["errors"].append(f"{short}：「对照：」要用「 / 」分成恰好两句：「{l[3:30]}」")


def check_cite_lines(ch):
    """每一行「原文：」（或「书中：」）：引文写成 *…*（不然核对不到）；下一行紧跟「译：」，中间不空行。
    词的用法里的「译：」由 parse_usage 和词条的检查管，这里只查 *…*。"""
    for sec, body in ch["secs"].items():
        short = sec.strip().split("：")[0]
        lines = body.splitlines()
        for i, l in enumerate(lines):
            s = l.strip()
            tag = cite_tag(s)
            if not tag:
                continue
            q = s[len(tag) + 1:].strip()
            if not re.fullmatch(r"\*[^*]+\*", q):
                ch["errors"].append(f"{short}：「{tag}：」后面的引文要写成 *…*：「{q[:24]}」")
            if short != "词的用法" and not (i + 1 < len(lines) and lines[i + 1].strip().startswith("译：")):
                ch["errors"].append(f"{short}：{tag}「{q.strip('*')[:24]}」下一行缺少「译：」")


def check_order(ch, sentences, text, what):
    positions = [text.find(s["quote"]) for s in sentences]
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        ch["errors"].append(f"{what}未按原文出现顺序排列")


def check_steps(ch, sentences, tag, rules):
    """轻读的长难句、两种模式的补充句：「怎么拆」可选，写了就是 light.per_item 里的步数。"""
    lo, hi = light_rules(rules)["per_item"]["怎么拆（步）"]
    for s in sentences:
        for it in s["items"]:
            if it["label"] == "怎么拆":
                k = len(it["sub"]) or int(bool(it["text"].strip()))
                if not lo <= k <= hi:
                    ch["errors"].append(f"{tag} {s['i']}：「怎么拆」写 {span(lo, hi)} 步，现在 {k} 步")


def check_preread(ch, words, rules, listed):
    """读前（两种模式同一套）：读前的词、人物的数量；读前的词不和本单元的词条重复，也不和前面单元的读前重复。
    listed：前面单元读前列过的词 → 单元号；查完把本单元的词加进去。"""
    pre, err = ch["preread"], ch["errors"].append
    rng = count_ranges(words, rules, "轻读")
    need_count(ch, "读前的词", len(pre["words"]), rng["读前词"], words, "个")
    need_count(ch, "读前的人物", len(pre["people"]), rng["人物"], words, "个")
    vocab, mine = usage_vocab(ch), set()
    for w in pre["words"]:
        k = norm_word(w["head"])
        if k in mine:
            err(f"读前的词「{w['head']}」列了两次")
        elif k in listed:
            err(f"读前的词「{w['head']}」在{unit_name(listed[k])}的读前已经列过")
        if k in vocab:
            err(f"读前的词「{w['head']}」又写成了词条「{vocab[k]}」：读前管认得，词条管用法，只留一处")
        mine.add(k)
    for k in mine:
        listed.setdefault(k, ch["n"])


def check_light(ch, words, rules, text):
    """轻读单元的数量和内容（读前在 check_preread，补充句在 check_extra）。"""
    err = ch["errors"].append
    per = light_rules(rules)["per_item"]
    rng = count_ranges(words, rules, "轻读")
    comp = ch["comprehension"]
    need_count(ch, "理解", len(comp["questions"]), rng["理解"], words, "题")
    lo, hi = per["理解引文"]
    srng = per.get("理解答案句数")
    for k, a in enumerate(comp["answers"], 1):
        got = zh_sentences(a["text"])
        if not a["text"]:
            err(f"理解答案 {k}：先用一两句中文回答，再引原文")
        elif srng and not srng[0] <= got <= srng[1]:
            err(f"理解答案 {k}：写了 {got} 句，答案写 {span(*srng)} 句中文（原文、译文不算）")
        if not lo <= len(a["quotes"]) <= hi:
            err(f"理解答案 {k}：要有 {span(lo, hi)} 处「原文：*…*」，现在 {len(a['quotes'])} 处")
    need_count(ch, "长难句", len(ch["sentences"]), rng["长难句"], words, "句")
    check_steps(ch, ch["sentences"], "句", rules)
    need_count(ch, "词汇用法", len(ch["usage"]), rng["词条"], words, "条")
    lo, hi = per["词条用法行"]
    for u in ch["usage"]:
        if not u["dict"] or not u["quotes"]:
            err(f"词条 {u['head']}：需要词典和原文引文")
        if not u["level"]:
            err(f"词条 {u['head']}：缺少「掌握：会用」或「掌握：认得」")
        if not lo <= len(u["notes"]) <= hi:
            err(f"词条 {u['head']}：轻读的词条用法写 {span(lo, hi)} 行（{'、'.join(USE_KEYS[-5:])}选一种），"
                f"现在 {len(u['notes'])} 行")
        for q, tag, t in zip(u["quotes"], u["tags"], u["trans"]):
            if not t:
                err(f"词条 {u['head']}：{tag}「{q[:24]}」下一行缺少「译：」")
    r = ch["retell"]
    if r:
        if r["prompts"]:
            need_count(ch, "复述", len(r["prompts"]), rng["复述"], words, "题")
        vocab = {**usage_vocab(ch), **{norm_word(w["head"]): w["head"] for w in (ch["preread"] or {}).get("words", [])}}
        lo, hi = per["提示词"]
        for p in r["prompts"]:
            if not lo <= len(p["hints"]) <= hi:
                err(f"复述的提示词要 {span(lo, hi)} 个，现在 {len(p['hints'])} 个")
            for h in p["hints"]:
                if norm_word(h) not in vocab:
                    err(f"复述的提示词「{h}」不在本{P.unit}的读前词和词条里")
        rng = light_rules(rules).get("retell_sentences", {}).get(P.level)      # A2、B1 查句数；B2 起只查词数
        if rng:
            for ref in r["refs"]:
                k = len(en_sentences(ref))
                if not rng[0] <= k <= rng[1]:
                    err(f"复述参考写了 {k} 句，{P.level} 读者写 {span(*rng)} 句")
    check_quote_trans(ch)
    check_order(ch, ch["sentences"], text, "长难句")


def check_intensive(ch, words, rules, text, jing):
    """精读单元：第一版的规则。赏析点、自测的下限放宽（rules.json）；句子里的延伸、赏析可选；
    回头看按精读单元算：第一个精读单元不要，之后的精读单元最后两题要，且只指前面的精读单元。jing：全部精读单元号。"""
    n, name, U = ch["n"], unit_name(ch["n"]), P.unit
    rng = count_ranges(words, rules)
    for key, what, got in (("精讲句", "精讲句", len(ch["sentences"])), ("词条", "词汇用法", len(ch["usage"])),
                           ("自测", "自测", len(ch["quiz"]))):
        lo, hi = rng[key]
        if not lo <= got <= hi:
            unit_word = {"精讲句": "句", "词条": "条", "自测": "题"}[key]
            ch["errors"].append(f"{what}需要 {lo}–{hi} {unit_word}（原文 {words} 词），现在 {got} {unit_word}")
    review = [P.review.match(q) for q in ch["quiz"]]
    first = jing[0]
    if n == first and any(review):
        ch["errors"].append(f"{name}的自测不要回头看题")
    if n != first and (len(review) < 2 or not all(review[-2:]) or any(review[:-2])):
        ch["errors"].append(f"自测最后两题（且只有这两题）要以「回头看（第 N {U}）：」开头")
    for q, m in zip(ch["quiz"], review):
        k = int(m.group(1)) if m else 0
        if m and not (k < n and k in unit_nums()):
            ch["errors"].append(f"回头看要指前面的{U}（{U}号小于 {n}）：「{q[:24]}」")
        elif m and k not in jing:
            ch["errors"].append(f"回头看要指前面的精读{U}，{unit_name(k)}是轻读：「{q[:24]}」")
        elif not m and "回头看" in q:
            ch["errors"].append(f"回头看的写法应为「回头看（第 N {U}）：」：「{q[:24]}」")
    if ch["n_writing"] > 1 or (P.writing and not ch["n_writing"]):
        ch["errors"].append("需要恰好一个「## 写作：…」" if P.writing else "「## 写作：…」最多一个")
    elif ch["n_writing"]:
        if not re.search(r"^> .+", ch["writing"], flags=re.M):
            ch["errors"].append("写作里至少要引一句原文（> …）")
        if not re.search(r"^### 练习\s*$", ch["writing"], flags=re.M):
            ch["errors"].append("写作里缺少「### 练习」")
        if not re.search(r"^参考：.+", ch["writing"], flags=re.M):
            ch["errors"].append("写作里缺少「参考：…」（PDF 里排在答案页）")
    check_quote_trans(ch)
    label = ch["essay_label"]
    if P.appreciation and not ch["has_essay"]:
        ch["errors"].append("缺少「## 赏析」")
    if ch["has_essay"]:
        points = re.split(r"^### ", ch["essay"], flags=re.M)[1:]
        lo, hi = rng["赏析点"]
        if P.appreciation and not lo <= len(points) <= hi:
            ch["errors"].append(f"{label}需要 {lo}–{hi} 个有引文的分析点（原文 {words} 词），现在 {len(points)} 个")
        for point in points:
            if not re.search(rf"^> .+|(?:{CITE_RE})：\*.+?\*", point, flags=re.M):
                ch["errors"].append(f"{label}存在缺少原文依据的分析点：「{point.splitlines()[0][:24]}」")
    for s in ch["sentences"]:            # 延伸、赏析可选
        labels = {it["label"] for it in s["items"]}
        for need in ("主干", "卡点"):
            if need not in labels:
                ch["errors"].append(f"句 {s['i']}：缺少「{need}」")
    for u in ch["usage"]:
        if not u["dict"] or not u["quotes"] or len(u["notes"]) < 2:
            ch["errors"].append(f"词条 {u['head']}：需要词典、原文引文和至少两项用法说明")
        if not u["level"]:
            ch["errors"].append(f"词条 {u['head']}：缺少「掌握：会用」或「掌握：认得」")
        for q, tag, t in zip(u["quotes"], u["tags"], u["trans"]):
            if not t:
                ch["errors"].append(f"词条 {u['head']}：{tag}「{q[:24]}」下一行缺少「译：」")
    check_order(ch, ch["sentences"], text, "精讲句")


def check_extra(ch, text, rules):
    """补充句（两种模式同一套）：自成一套编号（parse 里查），不计入数量；怎么拆的步数；按原文顺序。"""
    if ch["extra"]:
        check_steps(ch, ch["extra"], EXTRA, rules)
        check_order(ch, ch["extra"], text, EXTRA)


# ----- 读前词的次数和级别、复述参考、语法术语、读后篇幅 -----
#
# 靠估计得出的（词的级别、读后大约几页、术语表里没用到的术语）是「提示」：不计入问题数，不影响退出码。

EN_WORD = re.compile(r"[A-Za-zÀ-ɏ]+(?:['’\-][A-Za-zÀ-ɏ]+)*")     # 一个英文词，同 source.py 的 WORD_RE


def sibling(name):
    """同目录的 lexicon.py、source.py（按路径载入，不改 sys.path，也不在 scripts/ 里留 __pycache__）。"""
    key = f"english_reader_{name}"
    if key not in sys.modules:
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


def en_sentences(text):
    """英文按 . ! ? 切句（source.py 的 split_sentences：Mr. Mrs. Dr. St. 这类缩写不切）。"""
    return sibling("source").split_sentences(text)


def zh_sentences(text):
    """中文按 。！？ 数句子；末尾没有句号的一截也算一句。"""
    return sum(1 for p in re.split(r"[。！？]+", text) if re.search(r"[A-Za-z0-9㐀-鿿]", p))


def suffix_forms(w):
    """取不到词级数据时的词形归并：原词，加上去掉 -s、-es、-ies、-ed、-ied、-ing 后可能的原形（词干至少 3 个字母）。"""
    out = {w}
    for suf, add in (("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("d", ""), ("ing", ""), ("ing", "e")):
        stem = w[:-len(suf)]
        if w.endswith(suf) and len(stem) >= 3:
            out.add(stem + add)
            if suf in ("ed", "ing") and stem[-1] == stem[-2] and stem[-1] not in "aeiou":     # stopped → stop
                out.add(stem[:-1])
    return out


class Words:
    """读前词和复述参考用的词形归并、词级（lexicon.py，只用离线的词表）。
    取不到词级数据时 lex 是 None、why 写原因：词形按 suffix_forms 归并，级别一律不查。"""

    def __init__(self, root):
        self.lx = self.lex = None
        self.why = ""
        try:
            self.lx = sibling("lexicon")
            self.lex = self.lx.Lexicon(project=root, offline=True)
        except Exception as e:       # 缺数据（LexiconError）、lexicon.py 读不了：次数照查，级别跳过
            self.lex, self.why = None, str(e) or type(e).__name__
        self.cache = {}

    def keys(self, word):
        """比对用的原形集合：有词级数据是 {lex.lemma(词)}，没有就是 suffix_forms。所有格的 ’s 先去掉。"""
        w = re.sub(r"'s$", "", norm_word(word))
        if w not in self.cache:
            self.cache[w] = {self.lex.lemma(w)} if self.lex else suffix_forms(w)
        return self.cache[w]

    def reader(self):
        """读者水平（设置.json 的 level）的级数；取不到词级数据或 level 写得不对时是 None（不查级别）。"""
        return self.lx.RANK.get(P.level) if self.lex else None

    def level(self, word, pos=None):
        """(级别, 级数, 「B2」或「B2，估」)；未定级返回 None。只用 level_info 的 kind 是 list（词表）和 estimate（估级）的。"""
        i = self.lex.level_info(word, pos)
        if i["kind"] not in ("list", "estimate"):
            return None
        return i["level"], self.lx.RANK[i["level"]], i["level"] + ("，估" if i["kind"] == "estimate" else "")


def phrase_hits(head, toks, words):
    """head（词或短语）在原文里出现几次。toks：原文各词的原形集合，按原文顺序；短语按连续几个词逐个比原形。"""
    want = [words.keys(t) for t in EN_WORD.findall(head)]
    if not want:
        return None
    k = len(want)
    return sum(1 for i in range(len(toks) - k + 1) if all(want[j] & toks[i + j] for j in range(k)))


def check_preread_words(ch, text, words, rules, wl, hint):
    """读前的词（两种模式）：按原形在本单元原文里数够次数（rules.json 的 profile.preread_min_count，长文、短文按
    counts.short_words 分），不够是问题；词表定级或估级、又不高于读者水平的，是提示。words：本单元原文的词数。"""
    mc = {"long": 3, "short": 2, **(rules.get("profile") or {}).get("preread_min_count", {})}
    need = mc["short"] if words < rules["counts"]["short_words"] else mc["long"]
    # 带连字符的词也按拆开的各段算（luncheon-basket 里有 luncheon，water-meadows 里有 meadow），和 profile.py 一致
    toks = [wl.keys(t).union(*(wl.keys(p) for p in t.split("-") if p)) for t in EN_WORD.findall(text)]
    reader = wl.reader()
    for w in ch["preread"]["words"]:
        got = phrase_hits(w["head"], toks, wl)
        if got is not None and got < need:
            ch["errors"].append(f"读前词 {w['head']} 在本{P.unit}原文里只出现 {got} 次，至少 {need} 次")
        lv = wl.level(w["head"], w["pos"]) if reader else None
        if lv and lv[1] <= reader:
            hint("读前", f"读前词 {w['head']}（{lv[2]}）不高于读者水平 {P.level}")


def check_retell_words(ch, text, wl, hint):
    """复述参考里的词，按原形看级别：高于读者水平（词表定级或估级）、又不是本单元读前的词或词条（短语、带连字符的词
    拆开的各词也算），也不是专名的，是提示。专名：句中大写；句首大写的词在本单元原文里大写的次数多于小写也算。每个词只报一次。"""
    reader = wl.reader()
    refs = (ch["retell"] or {}).get("refs", [])
    if not reader or not refs:
        return
    heads = [w["head"] for w in (ch["preread"] or {}).get("words", [])]
    heads += [h for u in ch["usage"] for h in (u["head"], dict_head(u["dict"])) if h]
    known = set().union(*(wl.keys(p) for h in heads for t in EN_WORD.findall(h) for p in [t] + t.split("-") if p))
    case = Counter()      # 原文里每个词大写（+1）和小写（−1）的次数差
    for t in EN_WORD.findall(text):
        case[re.sub(r"['’]s$", "", t).lower()] += 1 if t[0].isupper() else -1
    told = set()
    for ref in refs:
        for sent in en_sentences(ref):
            for i, t in enumerate(EN_WORD.findall(sent)):
                base = re.sub(r"['’]s$", "", t)
                if base[0].isupper() and (i > 0 or case[base.lower()] > 0):
                    continue
                lv = wl.level(base)
                keys = wl.keys(base)
                if not lv or lv[1] <= reader or keys & known or min(keys) in told:
                    continue
                told.add(min(keys))
                hint("复述", f"复述参考里的 {base.lower()}（{lv[2]}）高于读者水平，也不是读前的词或词条")


def table_terms(md):
    """Markdown 里「## 语法术语」一节表格的第一列（去掉表头）；「系动词、表语」拆成两个。没有这一节或节里没有表格返回 None。"""
    m = re.search(r"^## 语法术语[ \t]*\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S)
    rows = [l.strip() for l in (m.group(1) if m else "").splitlines() if l.strip().startswith("|")]
    rows = [r for r in rows if not re.fullmatch(r"[|:\-\s]+", r)]       # 去掉分隔行
    if len(rows) < 2:
        return None
    cells = (re.sub(r"[*`]", "", r.strip("|").split("|")[0]) for r in rows[1:])
    return [t.strip() for c in cells for t in re.split(r"[、，,/／]", c) if t.strip()]


# 扫描语法术语时整行不看的：引文、原文、译文、例句、参考（复述和写作）；长难句「译」一项（is_translation）另外跳过
TERM_SKIP = re.compile(r"\s*(?:> |(?:原文|书中|译|例|参考)：)")
# 普通中文里的说法，不算语法术语：「被动地」「伴随着」
TERM_PLAIN = re.compile(r"被动(?=地)|伴随(?=着)")


def check_grammar_terms(chapters):
    """语法术语（两种模式）：前言.md 有「## 语法术语」表时才查。术语清单是 reference/前言模板.md 表的第一列；
    讲解用了、项目的表里没有的，是问题（每个术语报一次，写第一次出现的位置）；项目的表里有、全部单元一次没用到的，是提示。
    讲解文字去掉引文行、原文/译/例/参考行和反引号、斜体里的内容，术语按从长到短匹配（「定语从句」不再算「从句」）。
    返回 ([(单元名, 说明)…], [说明…])。"""
    pre = P.docs / "前言.md"
    table = table_terms(pre.read_text(encoding="utf-8")) if pre.exists() else None
    if table is None:          # 没有这张表（B2 以上可以不附）：整条不查
        return [], []
    known = (table_terms(TEMPLATE.read_text(encoding="utf-8")) if TEMPLATE.exists() else None) or []
    if P.format < 3:
        known = list(dict.fromkeys(known + LEGACY_TERMS))
    terms = sorted(set(known) | set(table), key=len, reverse=True)
    if not terms:
        return [], []
    rx = re.compile("|".join(re.escape(t) for t in terms))
    first, tagged = {}, set()
    for ch in chapters:
        for loc, line in located_lines(ch):
            if TERM_SKIP.match(line) or is_translation(loc, line):
                continue
            if P.format >= 3 and loc.endswith(" 结构"):      # 结构标签另查句子结构表；标签里的术语只算用到，不报缺
                tagged.update(m.group(0) for m in rx.finditer(prose(line)))
                continue
            if P.format >= 3 and loc.endswith((" 标记", " 断句", " 答")):
                continue
            for m in rx.finditer(TERM_PLAIN.sub("　", prose(line))):
                first.setdefault(m.group(0), (ch["n"], loc))
    missing = [(unit_name(n), f"{loc}用了「{t}」，前言的语法术语表里没有") for t, (n, loc) in first.items()
               if t in known and t not in table]
    unused = [f"前言的语法术语表里有「{t}」，讲义一次没用到" for t in dict.fromkeys(table)
              if t not in first and t not in tagged]
    return missing, unused


def post_paragraphs(ch):
    """轻读的读后（理解题、长难句、词的用法、复述题和提示词、补充句，不含答案）排成的段落：
    返回 (段落文字列表, 小节标题数, 句子块数, 词条块数)。估篇幅用。"""
    paras = [x for q in ch["comprehension"]["questions"] for x in q.split("\n")]
    for s in ch["sentences"] + ch["extra"]:
        paras += [s["title"], s["quote"]]
        for it in s["items"]:
            paras += ([it["text"]] if it["text"].strip() else []) + it["sub"]
    for u in ch["usage"]:
        paras += [f"{u['head']} {u['dict']}", u["text"]]
        for q, t in zip(u["quotes"], u["trans"]):
            paras += [q] + ([t] if t else [])
        paras += [v for _, v in u["notes"]]
    body = next((b for t, b in ch["secs"].items() if t.strip() == "复述"), "")
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("参考："):
            paras += list(s.partition("提示词：")[::2]) if "提示词：" in s else [s]
    heads = len(LIGHT_SECS) - 1 + bool(ch["extra"])         # 读后的小节标题：理解、长难句、词的用法、复述，补充句
    return paras, heads, len(ch["sentences"]) + len(ch["extra"]), len(ch["usage"])


def post_estimate(ch, est):
    """按字数估计轻读的读后排成 A5 大约几页（rules.json 的 light.md_estimate）。
    折合字数 = 中文字（含全角标点）+ 英文词 × 英文词折合字数 + 段落、小节标题、句子块、词条块各自的固定开销；页数 = 折合字数 ÷ 每页字数。"""
    paras, heads, sents, uses = post_paragraphs(ch)
    chars = sum(len(CJK.findall(p)) + est["英文词折合字数"] * len(EN_WORD.findall(p)) for p in paras)
    chars += (est["每段另加"] * len(paras) + est["每个小节标题"] * heads + est["每个句子块"] * sents
              + est["每个词条块"] * uses)
    return chars / est["每页字数"]


def check_post_length(ch, rules, hint):
    """轻读：估计的读后页数超过 light.pdf.post_pages 是提示（以 PDF 实排为准）。"""
    est = light_rules(rules).get("md_estimate")
    if not est:
        return
    pages, cap = round(post_estimate(ch, est), 1), light_post_pages(rules)
    if pages > cap:
        hint("篇幅", f"估计读后约 {pages} 页，上限 {cap} 页；以 PDF 实排为准")


# ---------- 第三版（设置.json 的 "format": 3）：解析和检查 ----------
#
# 第一、二版的项目不走这里（P.format == 2），上面的老代码照旧。
# S1–S17 是 check 的第三版规则编号，测试按它分组；没写“提示”的都是问题。

def load_tags():
    """reference/结构标签.tsv：[{tag, definition, how, example}…]，按文件里的行序（难句本的分组顺序）。
    # 开头的行是注释，第一列是「标签」的那行是表头。"""
    if not TAGS.exists():
        sys.exit(f"找不到 {TAGS}（第三版句子块的结构标签）")
    out = []
    for line in TAGS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = [c.strip() for c in (line.split("\t") + ["", "", ""])[:4]]
        if cells[0] and cells[0] != "标签":
            out.append({"tag": cells[0], "definition": cells[1], "how": cells[2], "example": cells[3]})
    return out


def v3_rules(rules):
    """rules.json 的 v3 组。"""
    v3 = rules.get("v3")
    if not isinstance(v3, dict):
        sys.exit(f"{RULES} 里缺少 v3 组（第三版的规则）")
    return v3


def v3_counts(words, rules):
    """第三版轻读的数量（v3.light.counts）：{栏目: (最少, 最多)}，按 counts.short_words 分长文、短文。"""
    c = v3_rules(rules)["light"]["counts"]
    group = c["short"] if words < rules["counts"]["short_words"] else c["long"]
    return {k: tuple(v) for k, v in group.items() if not k.startswith("_")}


def v3_preread_rules(rules):
    """给 check_preread 用的 rules：读前词、人物的数量换成 v3.light.counts 的（写成 count_ranges 认的 {"range": …}）。"""
    c = v3_rules(rules)["light"]["counts"]
    light = dict(light_rules(rules))
    light["counts"] = {g: {k: {"range": c[g][k]} for k in ("读前词", "人物")} for g in ("long", "short")}
    return {**rules, "light": light}


def v3_limits(rules, mode):
    """第三版另加或改了的长度上限：「试」两种模式共用 v3.sentence.try_chars；轻读另按 v3.light.max_chars
    （卡点收到 100），精读照旧用 max_chars 的。译照旧是 max(译, 译_每个原文词 × 原句词数)。"""
    v3 = v3_rules(rules)
    out = {"试": v3["sentence"]["try_chars"]}
    if mode == "轻读":
        out.update({k: v for k, v in v3["light"].get("max_chars", {}).items() if not k.startswith("_")})
    return out


def split_row(line):
    """Markdown 表格的一行拆成格：去掉两头的竖线，按没转义的 | 切开，每格去掉两头空白，\\| 还原成 |。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def is_sep_row(line):
    """表格的分隔行「| --- | --- |」。"""
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-+:?", c) for c in cells)


NOTE_ITEM = re.compile(r"([A-Za-z’'][A-Za-z’'\-]*(?: [A-Za-z’'\-]+)*)\s+(.+)$")     # 注的一条：英文（词或短语）、空格、释义


def parse_notes(text):
    """「注」：词 释义；词 释义。返回 ([(词, 释义)…], [写不对的条目…])。词是开头的英文（可以是短语），
    释义是后面的部分，要有中文。"""
    out, bad = [], []
    for part in re.split(r"[；;]", text):
        p = part.strip()
        if not p:
            continue
        m = NOTE_ITEM.match(p)
        if m and CJK.search(m.group(2)):
            out.append((m.group(1).strip(), m.group(2).strip()))
        else:
            bad.append(p)
    return out, bad


def parse_light_v3(ch, sec):
    """第三版的轻读单元：读前、长难句、理解、词的用法、复述，名字和顺序固定；最后可以有卡句。"""
    err, order = ch["errors"].append, ch["order"]
    names = V3_LIGHT_SECS + (STUCK,)
    for t in order:
        if t == EXTRA:
            err(f"「## {EXTRA}」第三版改叫「## {STUCK}」")
        elif t not in names:
            err(f"不认识的小节「## {t}」（轻读的小节依次是{'、'.join(V3_LIGHT_SECS)}，最后可以有{STUCK}）")
    for t in names:
        if order.count(t) > 1:
            err(f"「## {t}」只能有一个")
    for t in V3_LIGHT_SECS:
        if t not in order:
            err(f"缺少「## {t}」")
    got = [t for i, t in enumerate(order) if t in names and t not in order[:i]]
    if got != [t for t in names if t in got]:
        err(f"小节顺序不对：应为{'、'.join(V3_LIGHT_SECS)}，{STUCK}放在最后")
    ch["preread"] = parse_preread(ch, sec[PRE]) if PRE in sec else None
    ch["sentences"] = parse_blocks_v3(ch, sec.get("长难句", ""))
    ch["comprehension"] = (parse_comprehension(ch, sec["理解"]) if "理解" in sec
                           else {"questions": [], "answers": []})
    ch["usage"] = parse_usage(ch, sec.get("词的用法", ""))
    ch["retell"] = parse_retell(ch, sec["复述"]) if "复述" in sec else None
    ch["extra"] = parse_blocks_v3(ch, sec[STUCK], STUCK) if STUCK in sec else []
    ch["stuck"] = ch["extra"]


def parse_intensive_v3(ch, sec):
    """第三版的精读单元：栏目照第二版，长难句换成第三版的句子块（全是精讲句），末尾的补充句改叫卡句。
    长难句先换成空的、卡句和补充句先拿掉，交给 parse_intensive 解析和查别的栏目；再单独解析句子块。"""
    err = ch["errors"].append
    rest = {k: ("" if k.strip() == "长难句" else v) for k, v in ch["secs"].items() if k.strip() not in (STUCK, EXTRA)}
    tmp = dict(ch, secs=rest)            # errors 是同一个列表
    parse_intensive(tmp, {k: v for k, v in sec.items() if k not in (STUCK, EXTRA)})
    ch.update({k: v for k, v in tmp.items() if k != "secs"})
    if EXTRA in sec:
        err(f"「## {EXTRA}」第三版改叫「## {STUCK}」")
    ch["sentences"] = parse_blocks_v3(ch, ch["secs"].get("长难句", ""))
    ch["extra"] = []
    if STUCK in sec:
        if ch["order"][-1] != STUCK:
            err(f"「## {STUCK}」要放在最后")
        if ch["order"].count(STUCK) > 1:
            err(f"「## {STUCK}」只能有一个")
        ch["extra"] = parse_blocks_v3(ch, sec[STUCK], STUCK)
    ch["stuck"] = ch["extra"]


def parse_blocks_v3(ch, body, kind="长难句"):
    """第三版的句子块（长难句或卡句，kind）：「### N. 标题」、空一行、「> 原句」；下面是断句表前的结构、标记、注、试，
    一张「| 断句 | 顺读 |」表，表后的答、怎么拆、卡点、译、句型、延伸、赏析。项都写成「- **项**：…」，
    怎么拆、卡点等可以有两个空格缩进的续行（怎么拆的步子写成「  1. …」）。
    这里只查写法：项的名字、写在表前还是表后、先后、表头、每行两格、编号（S2、S13，S12 的主干）；
    内容的规则在 check_blocks_v3。kind（精讲、练习）按有没有卡点和译定：精读一律是精讲。"""
    err = ch["errors"].append
    stuck = kind == STUCK
    tag = f"{STUCK} " if stuck else "句 "
    out = []
    for chunk in re.split(r"^### ", body, flags=re.M)[1:]:
        m = re.match(r"(\d+)\. (.+)\n\n> (.+)\n", chunk)
        if not m:
            err(f"{STUCK if stuck else '句子'}格式不对：「{chunk[:30]}」")
            continue
        b = f"{tag}{m.group(1)}"
        s = {"i": int(m.group(1)), "title": m.group(2), "quote": m.group(3), "items": [], "kind": "",
             "tags": [], "mark": None, "notes": [], "try": None, "chunks": [], "gloss": [],
             "labels": [], "table": False}          # labels：[(项, 表前 / 表后)…]，按文件里的顺序
        lines = chunk[m.end():].splitlines()
        first = next((k for k, l in enumerate(lines) if l.startswith("|")), len(lines))
        last = first
        while last < len(lines) and lines[last].startswith("|"):
            last += 1
        if any(l.startswith("|") for l in lines[last:]):
            err(f"{b}：只能有一张断句表（表格中间不要空行）")
        if first < len(lines):
            parse_table_v3(s, lines[first:last], b, err)
        q = a = cont = None                 # cont：能带续行的项（items 里的最后一项）
        for k, line in enumerate(lines):
            if first <= k < last or line.startswith("|"):
                continue
            top = re.match(r"- \*\*(.+?)\*\*：(.*)$", line)
            if top:
                lab, text, cont = top.group(1), top.group(2).strip(), None
                if lab in [x for x, _ in s["labels"]]:
                    err(f"{b}：「{lab}」只能写一次")
                s["labels"].append((lab, "表前" if k < first else "表后"))
                if lab == "主干":
                    err(f"{b}：第三版不写「主干」，断句表里的粗体就是主干")
                elif lab not in V3_PRE + V3_POST:
                    err(f"{b}：未知的项「{lab}」（表前写{'、'.join(V3_PRE)}，表后写{'、'.join(V3_POST)}）")
                elif lab == "结构":
                    s["tags"] = [t.strip() for t in re.split(r"[、，,]", text) if t.strip()]
                elif lab == "标记":
                    s["mark"] = text
                elif lab == "注":
                    s["notes"], bad = parse_notes(text)
                    for x in bad:
                        err(f"{b}：注要写成「词 释义；词 释义」：「{x[:30]}」")
                elif lab == "试":
                    q = text
                elif lab == "答":
                    a = text
                else:
                    cont = {"label": lab, "text": text, "sub": []}
                    s["items"].append(cont)
            elif cont and re.match(r"  \d+\. ", line):
                cont["sub"].append(re.sub(r"^  \d+\. ", "", line))
            elif cont and line.startswith("  ") and line.strip():
                cont["sub"].append(line.strip())
            elif re.match(r"- \*\*(.+?)\*\*\s*[:：]", line):
                lab = re.match(r"- \*\*(.+?)\*\*", line).group(1)
                err(f"{b}：「{lab}」后面紧跟全角冒号「：」，不用半角「:」、不空格：「{line[:30]}」")
            elif line.strip():
                err(f"{b}：无法识别的行「{line[:30]}」")
        if q is not None or a is not None:
            s["try"] = {"q": q or "", "a": a or ""}
        if not s["table"]:
            err(f"{b}：缺少断句表（表头「| 断句 | 顺读 |」）")
        else:
            for lab, where in s["labels"]:
                if lab in V3_PRE and where == "表后":
                    err(f"{b}：「{lab}」要写在断句表前面")
                elif lab in V3_POST and where == "表前":
                    err(f"{b}：「{lab}」要写在断句表后面")
            for names, where in ((V3_PRE, "表前"), (V3_POST, "表后")):
                got = [names.index(x) for x, w in s["labels"] if x in names and w == where]
                if got != sorted(got):
                    err(f"{b}：断句表{'前面' if where == '表前' else '后面'}的项依次是{'、'.join(names)}")
        labels = [x for x, _ in s["labels"]]
        s["kind"] = (STUCK if stuck else "精讲" if ch["mode"] == "精读" or "卡点" in labels or "译" in labels
                     else "练习")
        out.append(s)
    if [s["i"] for s in out] != list(range(1, len(out) + 1)):
        err(f"{STUCK if stuck else '长难句'}编号不连续，或有句子格式不对")
    return out


def parse_table_v3(s, rows, b, err):
    """断句表：表头「| 断句 | 顺读 |」、分隔行、至少 2 行（S2）。每行两格：断句栏行首的「· 」数出层数，
    粗体片段另记；顺读栏原样。结果填进 s 的 chunks、gloss。"""
    s["table"] = True
    if split_row(rows[0]) != TABLE_HEAD:
        err(f"{b}：断句表的表头要写成「| 断句 | 顺读 |」")
    if len(rows) > 1 and is_sep_row(rows[1]):
        rows = rows[2:]
    else:
        err(f"{b}：断句表第二行要是分隔行「| --- | --- |」")
        rows = rows[1:]
    lead = re.compile(rf"(?:{re.escape(INDENT)})*")
    for k, line in enumerate(rows, 1):
        cells = split_row(line)
        if len(cells) != 2:
            err(f"{b} 断句表第 {k} 行要有两格（断句、顺读），现在 {len(cells)} 格")
            cells = (cells + ["", ""])[:2]
        left, right = cells
        ind = lead.match(left).group(0)
        md = left[len(ind):]
        s["chunks"].append({"depth": len(ind) // len(INDENT), "text": md.replace("**", ""),
                            "bold": re.findall(r"\*\*(.+?)\*\*", md), "md": md})
        s["gloss"].append(right)
    if len(rows) < 2:
        err(f"{b}：断句表至少 2 行，现在 {len(rows)} 行")


def located_lines_v3(ch):
    """第三版：同 located_lines，长难句和卡句的句子块里另有「句 3 断句」「句 3 顺读」「句 3 试」「句 3 注」「卡句 2 卡点」。
    断句表的一行产出两项，「行」是那一格的文字：断句栏一项、顺读栏一项；表头和分隔行的位置是「句 3 断句表」。"""
    kind = base = label = ""
    for loc, line in located_lines({**ch, "format": 2}):
        m = re.match(r"## (.+)$", line)
        if m:
            name = m.group(1).strip()
            kind = "句" if name == "长难句" else STUCK if name == STUCK else ""
            base, label = name, ""
            yield loc, line
            continue
        if not kind:
            yield loc, line
            continue
        m = re.match(r"### (\d+)\.", line)
        if m:
            base, label = f"{kind} {m.group(1)}", ""
            yield f"{base} 标题", line
        elif line.startswith("|"):
            cells = split_row(line)
            if cells == TABLE_HEAD or is_sep_row(line):
                yield f"{base} 断句表", line
            else:
                yield f"{base} 断句", cells[0]
                yield f"{base} 顺读", cells[1] if len(cells) > 1 else ""
        else:
            m = re.match(r"- \*\*(.+?)\*\*：", line)
            if m:
                label = m.group(1)
            yield f"{base} {label}".strip(), line


def length_items_v3(ch):
    """第三版要限长的栏目：同 length_items，句子块另加「试」；卡句的位置写「卡句 N」。"""
    yield from length_items({**ch, "sentences": [], "extra": []})
    for blocks, tag in ((ch["sentences"], "句"), (ch["extra"], STUCK)):
        yield from sentence_items(blocks, tag)
        for s in blocks:
            if s["try"] and s["try"]["q"]:
                yield "试", f"{tag} {s['i']} 试", s["try"]["q"]


def table_quote_text(ch):
    """找「| *引文* |」用的讲义全文。第三版长难句、卡句里的断句表不算（断句栏另按 S3 和原句比）。"""
    if ch.get("format", 2) < 3:
        return ch["raw"]
    out, skip = [], False
    for line in ch["raw"].splitlines():
        m = re.match(r"## (.+)$", line)
        if m:
            skip = m.group(1).strip() in ("长难句", STUCK)
        if not (skip and line.startswith("|")):
            out.append(line)
    return "\n".join(out)


def check_unit_v3(ch, words, rules, text, jing, listed, words_once, hint, tags):
    """第三版一个单元的检查。words：原文词数；text：本单元原文；jing：精读单元号；listed：前面单元读前列过的词；
    words_once()：词级数据（Words）；hint(类别, 说明)：记一条提示；tags：结构标签（结构标签.tsv 的第一列）。"""
    wl = words_once()
    if ch["preread"]:
        check_preread(ch, words, v3_preread_rules(rules), listed)
        check_preread_words(ch, text, words, rules, wl, hint)
    if ch["mode"] == "轻读":
        check_light_v3(ch, words, rules, text)
        check_retell_words(ch, text, wl, hint)
        check_post_length_v3(ch, rules, hint)
    else:
        check_intensive_v3(ch, words, rules, text, jing)
    noted = []                  # 前面的句子注过的词，后面的句子不再提示
    check_blocks_v3(ch, ch["sentences"], text, rules, tags, wl, hint, noted)
    check_blocks_v3(ch, ch["extra"], text, rules, tags, wl, hint, noted)
    check_order(ch, ch["extra"], text, STUCK)
    check_variety_v3(ch, rules, hint)


def check_light_v3(ch, words, rules, text):
    """第三版轻读单元的数量和内容（v3.light.counts）。理解、词条、复述的写法同 check_light；
    长难句分精讲句（有卡点和译）和练习句（都没有）各自数。句子块本身在 check_blocks_v3。"""
    err = ch["errors"].append
    per = light_rules(rules)["per_item"]
    rng = v3_counts(words, rules)
    comp = ch["comprehension"]
    need_count(ch, "理解", len(comp["questions"]), rng["理解"], words, "题")
    lo, hi = per["理解引文"]
    srng = per.get("理解答案句数")
    for k, a in enumerate(comp["answers"], 1):
        got = zh_sentences(a["text"])
        if not a["text"]:
            err(f"理解答案 {k}：先用一两句中文回答，再引原文")
        elif srng and not srng[0] <= got <= srng[1]:
            err(f"理解答案 {k}：写了 {got} 句，答案写 {span(*srng)} 句中文（原文、译文不算）")
        if not lo <= len(a["quotes"]) <= hi:
            err(f"理解答案 {k}：要有 {span(lo, hi)} 处「原文：*…*」，现在 {len(a['quotes'])} 处")
    kinds = [s["kind"] for s in ch["sentences"]]
    need_count(ch, "精讲句", kinds.count("精讲"), rng["精讲句"], words, "句")
    need_count(ch, "练习句", kinds.count("练习"), rng["练习句"], words, "句")
    need_count(ch, "词汇用法", len(ch["usage"]), rng["词条"], words, "条")
    lo, hi = per["词条用法行"]
    for u in ch["usage"]:
        if not u["dict"] or not u["quotes"]:
            err(f"词条 {u['head']}：需要词典和原文引文")
        if not u["level"]:
            err(f"词条 {u['head']}：缺少「掌握：会用」或「掌握：认得」")
        if not lo <= len(u["notes"]) <= hi:
            err(f"词条 {u['head']}：轻读的词条用法写 {span(lo, hi)} 行（{'、'.join(USE_KEYS[-5:])}选一种），"
                f"现在 {len(u['notes'])} 行")
        for q, tag, t in zip(u["quotes"], u["tags"], u["trans"]):
            if not t:
                err(f"词条 {u['head']}：{tag}「{q[:24]}」下一行缺少「译：」")
    r = ch["retell"]
    if r:
        if r["prompts"]:
            need_count(ch, "复述", len(r["prompts"]), rng["复述"], words, "题")
        vocab = {**usage_vocab(ch), **{norm_word(w["head"]): w["head"] for w in (ch["preread"] or {}).get("words", [])}}
        lo, hi = per["提示词"]
        for p in r["prompts"]:
            if not lo <= len(p["hints"]) <= hi:
                err(f"复述的提示词要 {span(lo, hi)} 个，现在 {len(p['hints'])} 个")
            for h in p["hints"]:
                if norm_word(h) not in vocab:
                    err(f"复述的提示词「{h}」不在本{P.unit}的读前词和词条里")
        rs = light_rules(rules).get("retell_sentences", {}).get(P.level)
        if rs:
            for ref in r["refs"]:
                k = len(en_sentences(ref))
                if not rs[0] <= k <= rs[1]:
                    err(f"复述参考写了 {k} 句，{P.level} 读者写 {span(*rs)} 句")
    check_quote_trans(ch, ("长难句", STUCK))
    check_order(ch, ch["sentences"], text, "长难句")


def check_intensive_v3(ch, words, rules, text, jing):
    """第三版精读单元：同 check_intensive（数量照 counts、回头看、写作、赏析、词条），只是不再要求主干；
    句子块（卡点、译、怎么拆的步数）在 check_blocks_v3 里查。"""
    n, name, U = ch["n"], unit_name(ch["n"]), P.unit
    err = ch["errors"].append
    rng = count_ranges(words, rules)
    for key, what, got in (("精讲句", "精讲句", len(ch["sentences"])), ("词条", "词汇用法", len(ch["usage"])),
                           ("自测", "自测", len(ch["quiz"]))):
        lo, hi = rng[key]
        if not lo <= got <= hi:
            unit_word = {"精讲句": "句", "词条": "条", "自测": "题"}[key]
            err(f"{what}需要 {lo}–{hi} {unit_word}（原文 {words} 词），现在 {got} {unit_word}")
    review = [P.review.match(q) for q in ch["quiz"]]
    first = jing[0]
    if n == first and any(review):
        err(f"{name}的自测不要回头看题")
    if n != first and (len(review) < 2 or not all(review[-2:]) or any(review[:-2])):
        err(f"自测最后两题（且只有这两题）要以「回头看（第 N {U}）：」开头")
    for q, m in zip(ch["quiz"], review):
        k = int(m.group(1)) if m else 0
        if m and not (k < n and k in unit_nums()):
            err(f"回头看要指前面的{U}（{U}号小于 {n}）：「{q[:24]}」")
        elif m and k not in jing:
            err(f"回头看要指前面的精读{U}，{unit_name(k)}是轻读：「{q[:24]}」")
        elif not m and "回头看" in q:
            err(f"回头看的写法应为「回头看（第 N {U}）：」：「{q[:24]}」")
    if ch["n_writing"] > 1 or (P.writing and not ch["n_writing"]):
        err("需要恰好一个「## 写作：…」" if P.writing else "「## 写作：…」最多一个")
    elif ch["n_writing"]:
        if not re.search(r"^> .+", ch["writing"], flags=re.M):
            err("写作里至少要引一句原文（> …）")
        if not re.search(r"^### 练习\s*$", ch["writing"], flags=re.M):
            err("写作里缺少「### 练习」")
        if not re.search(r"^参考：.+", ch["writing"], flags=re.M):
            err("写作里缺少「参考：…」（PDF 里排在答案页）")
    check_quote_trans(ch, ("长难句", STUCK))
    label = ch["essay_label"]
    if P.appreciation and not ch["has_essay"]:
        err("缺少「## 赏析」")
    if ch["has_essay"]:
        points = re.split(r"^### ", ch["essay"], flags=re.M)[1:]
        lo, hi = rng["赏析点"]
        if P.appreciation and not lo <= len(points) <= hi:
            err(f"{label}需要 {lo}–{hi} 个有引文的分析点（原文 {words} 词），现在 {len(points)} 个")
        for point in points:
            if not re.search(rf"^> .+|(?:{CITE_RE})：\*.+?\*", point, flags=re.M):
                err(f"{label}存在缺少原文依据的分析点：「{point.splitlines()[0][:24]}」")
    for u in ch["usage"]:
        if not u["dict"] or not u["quotes"] or len(u["notes"]) < 2:
            err(f"词条 {u['head']}：需要词典、原文引文和至少两项用法说明")
        if not u["level"]:
            err(f"词条 {u['head']}：缺少「掌握：会用」或「掌握：认得」")
        for q, tag, t in zip(u["quotes"], u["tags"], u["trans"]):
            if not t:
                err(f"词条 {u['head']}：{tag}「{q[:24]}」下一行缺少「译：」")
    check_order(ch, ch["sentences"], text, "精讲句")


def key_set(wl, heads):
    """几个词或短语里每个词的原形（带连字符的词也拆开算）的集合。"""
    return set().union(*(wl.keys(p) for h in heads for t in EN_WORD.findall(h) for p in [t] + t.split("-") if p))


def note_in_quote(word, toks, wl):
    """注的词在原句里：短语的各词按原形、按先后在原句里都找得到（sb、sth 这类占位词不比）。
    toks：原句各词的原形集合，按原句的顺序。"""
    want = [wl.keys(t) for t in EN_WORD.findall(word) if norm_word(t) not in PLACEHOLDERS]
    i = 0
    for tk in toks:
        if i < len(want) and want[i] & tk:
            i += 1
    return bool(want) and i == len(want)


def chunk_mismatch(chunks, quote):
    """断句栏各行连起来、去掉全部空白后和原句比（S3）。对得上返回 None；对不上返回 (从第几行开始, 这一行从第一个不同的字起的一段,
    原句在那里的一段, 撇号或引号不同时的说明)；各行都对得上、只是连起来比原句短，行号是行数加一，第二项是空的。"""
    target = re.sub(r"\s+", "", quote)
    pos = 0
    for k, c in enumerate(chunks, 1):
        t = re.sub(r"\s+", "", c["text"])
        seg = target[pos:pos + len(t)]
        if seg != t:
            d = next((i for i, (x, y) in enumerate(zip(t, seg)) if x != y), min(len(t), len(seg)))
            return (k, nonspace_from(c["text"], d, 12), nonspace_from(quote, pos + d, 12),
                    quote_kind_diff(t[d:d + 1], seg[d:d + 1]))
        pos += len(t)
    return None if pos == len(target) else (len(chunks) + 1, "", nonspace_from(quote, pos), "")


QUOTE_KINDS = (("'", "’‘", "撇号"), ('"', "“”", "引号"))


def quote_kind_diff(a, b):
    """a（断句栏）和 b（原句）只是直、弯撇号或直、弯引号的不同时，说明是哪种；别的不同返回空串。"""
    for straight, curly, name in QUOTE_KINDS:
        if a == straight and b and b in curly:
            return f"这里是直{name}，原句是弯{name}"
        if b == straight and a and a in curly:
            return f"这里是弯{name}，原句是直{name}"
    return ""


def nonspace_from(s, n, width=24):
    """s 里从第 n 个（从 0 数）不是空白的字符起的一段，长 width 个字符。"""
    seen = 0
    for i, c in enumerate(s):
        if not c.isspace():
            if seen == n:
                return s[i:i + width].rstrip()
            seen += 1
    return ""


def check_chunks_v3(s, b, sr, err, hint):
    """断句表的内容（S3–S7）。b：位置（「句 3」「卡句 2」）；sr：v3.sentence。"""
    chunks, gloss = s["chunks"], s["gloss"]
    bad = chunk_mismatch(chunks, s["quote"])                                        # S3
    if bad and bad[0] <= len(chunks):
        k, mine, theirs, kind = bad
        err(f"{b} 断句第 {k} 行和原句对不上：" + (f"{kind}（「{mine}」）" if kind else
            f"这一行从「{mine}」起和原句不同，原句这里是「{theirs}」" if theirs else
            f"这一行多出了「{mine}」，原句到这里已经完了"))
    elif bad:
        err(f"{b} 断句：各行连起来比原句少了后面的「{bad[2]}」")
    depths, cap = [c["depth"] for c in chunks], sr["chunk_depth"]                   # S4
    for k, d in enumerate(depths, 1):
        if d > cap:
            err(f"{b} 断句第 {k} 行缩进 {d} 层，最多 {cap} 层")
    if 0 not in depths:
        err(f"{b} 断句：至少要有一行顶格（主句的主语、谓语）")
    if depths and depths[0] > 1:
        err(f"{b} 断句第 1 行最多缩进 1 层")
    for k in range(1, len(depths)):
        if depths[k] > depths[k - 1] + 1:
            err(f"{b} 断句第 {k + 1} 行比上一行深了 {depths[k] - depths[k - 1]} 层，一次最多深 1 层")
    for k, c in enumerate(chunks, 1):                                               # S5
        if c["bold"] and c["depth"] > 0:
            err(f"{b} 断句第 {k} 行：粗体只标顶格行（主句的主语中心词和谓语动词）")
        for x in c["bold"]:          # 粗体的写法（句子.md）：主语中心词带前面的冠词、形容词，谓语带助动词、小品词
            if word_count(x) > sr["bold_words"]:
                err(f"{b} 断句第 {k} 行：粗体「{x}」{word_count(x)} 个词，最多 {sr['bold_words']} 个"
                    "（主语只标中心词和前面的冠词、形容词，谓语只标动词，不带宾语、表语）")
            elif re.search(r"[,;:—–]", x):
                err(f"{b} 断句第 {k} 行：粗体「{x}」里有标点，粗体只标主语中心词和谓语动词")
    n_bold = sum(len(c["bold"]) for c in chunks)
    if not n_bold:
        err(f"{b} 断句：没有粗体，主句的主语中心词和谓语动词要标粗")
    elif n_bold == 1:
        hint("断句", f"{b} 断句只有 1 处粗体：主语中心词和谓语动词一般各标一处")
    lo, hi = sr["chunk_words"]                                                      # S6
    many = [str(k) for k, c in enumerate(chunks, 1) if word_count(c["text"]) > hi]
    few = [str(k) for k, c in enumerate(chunks, 1) if word_count(c["text"]) < lo]
    if many:
        hint("断句", f"{b} 断句第 {'、'.join(many)} 行超过 {hi} 词（每行 {span(lo, hi)} 词）")
    if few:
        hint("断句", f"{b} 断句第 {'、'.join(few)} 行不到 {lo} 词（每行 {span(lo, hi)} 词）")
    for k, g in enumerate(gloss, 1):                                                # S7
        if not g.strip():
            err(f"{b} 顺读第 {k} 行是空的")
    cap = sr["gloss_chars"]
    long = [str(k) for k, g in enumerate(gloss, 1) if plain_len(g) > cap]
    if long:
        hint("断句", f"{b} 顺读第 {'、'.join(long)} 行超过 {cap} 字")


def above_words(quote, wl, reader, known, case):
    """原句里高于读者水平（词表定级或估级）、又不在 known（原形）里的词，专名不算（同 check_retell_words：
    句中大写的；句首大写、本单元原文里大写多于小写的）。每个词只列一次，写成「word（B2，估）」。"""
    out, told = [], set()
    for i, t in enumerate(EN_WORD.findall(quote)):
        base = re.sub(r"['’]s$", "", t)
        if base[0].isupper() and (i > 0 or case[base.lower()] > 0):
            continue
        lv = wl.level(base)
        keys = wl.keys(base)
        if not lv or lv[1] <= reader or keys & known or min(keys) in told:
            continue
        told.add(min(keys))
        out.append(f"{base.lower()}（{lv[2]}）")
    return out


def phrase_in(phrase, text):
    """phrase 在 text 里出现，两头落在词边界上（la 不算 lay 的一部分，lied 不算 replied 的一部分）；中间的空白不计多少。
    phrase 头一个字符不是字母时不查前边界（’ll have to go 可以接在 You 后面），末一个不是字母时不查后边界。"""
    body = r"\s+".join(re.escape(p) for p in phrase.split())
    if not body:
        return False
    letter = re.compile(r"[A-Za-zÀ-ɏ]")
    p = phrase.strip()
    pre = r"(?<![A-Za-zÀ-ɏ])" if letter.match(p[0]) else ""       # 头一个字符不是字母（’ll），前边不查边界
    post = r"(?![A-Za-zÀ-ɏ])" if letter.match(p[-1]) else ""
    return re.search(pre + body + post, text) is not None


def check_blocks_v3(ch, blocks, text, rules, tags, wl, hint, noted=None):
    """第三版的句子块（长难句或卡句）的内容：S1、S3–S12、S14、S15、S17
    （S2、S13 的写法在 parse_blocks_v3，S16 在 check_variety_v3）。text：本单元原文；tags：结构标签；wl：Words。
    noted：本单元前面的句子块注过的词，查完一块把这块的注加进去；长难句和卡句传同一个列表。"""
    sr = v3_rules(rules)["sentence"]
    err, U = ch["errors"].append, P.unit
    light = ch["mode"] == "轻读"
    reader = wl.reader()
    noted = [] if noted is None else noted
    pre = (ch["preread"] or {}).get("words", [])
    heads = [w["head"] for w in pre] + [h for u in ch["usage"] for h in (u["head"], dict_head(u["dict"])) if h]
    known = key_set(wl, heads)
    case = Counter()        # 原文里每个词大写（+1）和小写（−1）的次数差，判断句首的词是不是专名
    for t in EN_WORD.findall(text):
        case[re.sub(r"['’]s$", "", t).lower()] += 1 if t[0].isupper() else -1
    for s in blocks:
        stuck = s["kind"] == STUCK
        b = f"{STUCK if stuck else '句'} {s['i']}"
        labels = [x for x, _ in s["labels"]]
        vocab = VOCAB in s["tags"]
        has = {x: x in labels for x in ("卡点", "译")}
        # S1 结构标签
        if "结构" not in labels:
            err(f"{b}：缺少「结构」（{span(*sr['tags'])} 个结构标签，第一个是主标签）")
        else:
            lo, hi = sr["tags"]
            if not lo <= len(s["tags"]) <= hi:
                err(f"{b}：「结构」写 {span(lo, hi)} 个标签，现在 {len(s['tags'])} 个")
            for t in s["tags"]:
                if t not in tags:
                    err(f"{b}：「{t}」不是结构标签（只能用 reference/结构标签.tsv 里的字样）")
            if len(set(s["tags"])) < len(s["tags"]):
                err(f"{b}：「结构」里有重复的标签")
            if vocab and not stuck:
                err(f"{b}：「{VOCAB}」只给卡句用")
            elif vocab and len(s["tags"]) > 1:
                err(f"{b}：「{VOCAB}」要单独用，不和别的标签一起写")
        # S3–S7 断句表
        if s["chunks"]:
            check_chunks_v3(s, b, sr, err, hint)
        # S8 试和答
        if stuck and vocab:
            if s["try"]:
                err(f"{b}：标签是{VOCAB}的卡句不写「试」和「答」")
        else:
            for lab, key in (("试", "q"), ("答", "a")):
                if not (s["try"] or {}).get(key):
                    err(f"{b}：缺少「{lab}」")
        ans = (s["try"] or {}).get("a", "")
        if ans:
            if not phrase_in(ans, text):
                err(f"{b} 答「{ans}」在本{U}原文里找不到（照原文抄，按整词比）")
            if word_count(ans) > sr["answer_words"]:
                err(f"{b} 答 {word_count(ans)} 词，最多 {sr['answer_words']} 词")
        # S9 注；S17 注里的词已是读前词（提示）
        lo, hi = sr["notes"]
        if not lo <= len(s["notes"]) <= hi:
            err(f"{b}：注最多 {hi} 个，现在 {len(s['notes'])} 个" if lo == 0 else
                f"{b}：注写 {span(lo, hi)} 个，现在 {len(s['notes'])} 个")
        toks = [wl.keys(t).union(*(wl.keys(p) for p in t.split("-") if p)) for t in EN_WORD.findall(s["quote"])]
        for w, g in s["notes"]:
            if not note_in_quote(w, toks, wl):
                err(f"{b} 注里的「{w}」不在原句里")
            if plain_len(g) > sr["note_chars"]:
                err(f"{b} 注「{w}」的释义 {plain_len(g)} 字，最多 {sr['note_chars']} 字")
            single = len(EN_WORD.findall(w)) == 1
            if any(norm_word(w) == norm_word(p["head"]) or (single and wl.keys(w) & key_set(wl, [p["head"]]))
                   for p in pre):
                hint("词", f"{b} 注里的「{w}」已经是本{U}的读前词")
        # S10 原句里的生词（提示）
        if reader:
            above = above_words(s["quote"], wl, reader, known | key_set(wl, noted + [w for w, _ in s["notes"]]), case)
            if above:
                hint("词", f"{b} 原句里这些词高于读者水平 {P.level}，读前、词条和注里都没有：{'、'.join(above)}")
        noted += [w for w, _ in s["notes"]]
        # S11 精讲句和练习句；S14 卡句
        if stuck:
            if s["mark"] is None:
                err(f"{b}：卡句要写「标记」（{'、'.join(MARKS)}，三选一）")
            if not has["译"]:
                err(f"{b}：缺少「译」")
            if vocab and has["卡点"]:
                err(f"{b}：标签是{VOCAB}的卡句不写「卡点」")
            elif not vocab and not has["卡点"]:
                err(f"{b}：缺少「卡点」")
            if (vocab or s["mark"] == "有生词") and not s["notes"]:
                err(f"{b}：{'标签是' + VOCAB if vocab else '标记是有生词'}，要写「注」")
        elif light:
            if has["卡点"] != has["译"]:
                err(f"{b}：精讲句要有卡点和译，练习句两样都不写；现在只有「{'卡点' if has['卡点'] else '译'}」")
        else:
            for x in ("卡点", "译"):
                if not has[x]:
                    err(f"{b}：精读的长难句都是精讲句，缺少「{x}」")
        if s["mark"] is not None and s["mark"] not in MARKS:
            err(f"{b}：「标记」只能是{'、'.join(MARKS)}，不是「{s['mark']}」")
        # S12 卡句不写怎么拆、句型、延伸、赏析；轻读只有精讲句可以写怎么拆（steps_light 步）；精读的怎么拆有步数上限
        # （主干在 parse 里报）
        for lab in labels:
            if lab in V3_EXTRAS and (stuck or (light and not (lab == "怎么拆" and has["卡点"]))):
                err(f"{b}：{STUCK if stuck else '轻读的练习句' if lab == '怎么拆' else '轻读的长难句'}不写「{lab}」")
        if not stuck and (not light or has["卡点"]):
            lo, hi = sr["steps_light" if light else "steps_intensive"]
            for it in s["items"]:
                if it["label"] == "怎么拆":
                    k = len(it["sub"]) or int(bool(it["text"].strip()))
                    if not lo <= k <= hi:
                        err(f"{b}：「怎么拆」写 {span(lo, hi)} 步，现在 {k} 步")
        # S15 长难句的词数（提示；卡句是读者自己记的，不查）
        least = sr["min_words"].get(P.level)
        if not stuck and least and word_count(s["quote"]) < least:
            hint("选句", f"{b} 原句 {word_count(s['quote'])} 词，{P.level} 读者的长难句一般选 {least} 词以上的")


def check_variety_v3(ch, rules, hint):
    """S16：一个单元的长难句有 min_sentences 句以上、主标签（结构的第一个）不到 min_tags 种，是提示。卡句不算。"""
    tv = v3_rules(rules)["sentence"]["tag_variety"]
    mains = [s["tags"][0] for s in ch["sentences"] if s["tags"]]
    kinds = list(dict.fromkeys(mains))
    if len(ch["sentences"]) >= tv["min_sentences"] and len(kinds) < tv["min_tags"]:
        hint("选句", f"长难句 {len(ch['sentences'])} 句，主标签只有 {len(kinds)} 种（{'、'.join(kinds) or '无'}），"
                    f"{tv['min_sentences']} 句以上时至少 {tv['min_tags']} 种")


def post_estimate_v3(ch, est):
    """按行数估计第三版轻读的读后排成 A5 大约几页（rules.json 的 v3.light.md_estimate；算法见那里的 _说明）。
    算长难句（标题、整句、断句表、注、卡点）、理解题、词条、复述题和提示词；不算试、答、译、理解答案、复述参考、卡句。
    断句表按 v3.pdf.chunk_layout 算：对排一块一行，左栏超过「表格每行词数」的折行；下置一块一行（超过「下置每行词数」的折行），
    表下的顺读段另算行数（各块连起来，每块另加两个字的编号和 ／，按「顺读每行字数」折行）。"""
    def rows(p):
        z = len(CJK.findall(p)) + est["英文词折合字数"] * len(EN_WORD.findall(p))
        return max(1, math.ceil(z / est["每行字数"]))
    below = v3_pdf()["chunk_layout"] == "下置"
    per_row = est.get("下置每行词数", 13) if below else est["表格每行词数"]
    paras, table = [], 0
    for s in ch["sentences"]:
        paras.append(s["title"])
        table += math.ceil(word_count(s["quote"]) / est.get("整句每行词数", 12))      # 整句：英文按词数折行
        table += sum(max(1, math.ceil(word_count(c["text"]) / per_row)) for c in s["chunks"])
        if below:
            z = sum(len(CJK.findall(g)) + est["英文词折合字数"] * len(EN_WORD.findall(g)) + 2 for g in s["gloss"])
            table += max(1, math.ceil(z / est.get("顺读每行字数", 40)))
        if s["notes"]:
            paras.append("注　" + " · ".join(f"{w} {g}" for w, g in s["notes"]))
        for it in s["items"]:
            if it["label"] in ("卡点", "怎么拆"):
                paras += [x for x in (it["text"], *it["sub"]) if x.strip()]
    paras += [x for q in ch["comprehension"]["questions"] for x in q.split("\n")]
    paras += post_paragraphs({**ch, "comprehension": {"questions": []}, "sentences": [], "extra": []})[0]   # 词条、复述
    lines = sum(rows(p) for p in paras) + est["段间距"] * len(paras) + table
    lines += (est["每个小节标题"] * (len(V3_LIGHT_SECS) - 1) + est["每个句子块"] * len(ch["sentences"])
              + est["每个词条块"] * len(ch["usage"]) + est["回读"])
    return lines / est["每页行数"]


def check_post_length_v3(ch, rules, hint):
    """第三版轻读：估计的读后页数超过 v3.light.pdf.post_pages 是提示（以 PDF 实排为准）。"""
    lr = v3_rules(rules)["light"]
    est = lr.get("md_estimate")
    if not est:
        return
    pages, cap = round(post_estimate_v3(ch, est), 1), int((lr.get("pdf") or {}).get("post_pages", 3))
    near = float(est.get("接近上限", 0.3))
    if pages > cap:
        hint("篇幅", f"估计读后约 {pages} 页，上限 {cap} 页；估计和实排差 0.1 页上下，以 PDF 实排为准")
    elif pages >= cap - near:
        hint("篇幅", f"估计读后约 {pages} 页，接近上限 {cap} 页：断句表整张不跨页，实排可能多出一页，以 PDF 实排为准")


def tag_table(md):
    """前言里「## 句子结构」一节表格的第一列（去掉表头）；「插入、并列」拆成两个。没有这一节或节里没有表格返回 None。"""
    m = re.search(r"^## 句子结构[ \t]*\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S)
    rows = [l.strip() for l in (m.group(1) if m else "").splitlines() if l.strip().startswith("|")]
    rows = [r for r in rows if not is_sep_row(r)]
    if len(rows) < 2:
        return None
    cells = (re.sub(r"[*`]", "", split_row(r)[0]) for r in rows[1:])
    return [t.strip() for c in cells for t in re.split(r"[、，,/／]", c) if t.strip()]


def check_tag_table(chapters, tags):
    """前言.md 的「## 句子结构」表（第三版，做法同语法术语表）：讲义用到的结构标签表里没有，是问题（每个标签报一次，
    写第一次出现的位置）；表里有、讲义一次没用到，是提示。「词汇」不进难句本，表里可以不列。
    没有 前言.md、或有前言没有这张表，各是一条提示。返回 ([(单元名, 说明)…], [说明…])。"""
    pre = P.docs / "前言.md"
    if not pre.exists():
        return [], [f"没有 {P.docs.name}/前言.md：第三版的前言要有「## 句子结构」表（照 reference/前言模板.md 写）"]
    table = tag_table(pre.read_text(encoding="utf-8"))
    if table is None:
        return [], ["前言.md 里没有「## 句子结构」表（列出本书用到的结构标签、定义和一个自造例句）"]
    used = {}
    for ch in chapters:
        for s in ch["sentences"] + ch["extra"]:
            for t in s["tags"]:
                if t in tags and t != VOCAB:
                    used.setdefault(t, (ch["n"], f"{STUCK if s['kind'] == STUCK else '句'} {s['i']}"))
    missing = [(unit_name(n), f"{loc}用了「{t}」，前言的句子结构表里没有") for t, (n, loc) in used.items()
               if t not in table]
    unused = [f"前言的句子结构表里有「{t}」，讲义一次没用到" for t in dict.fromkeys(table) if t not in used]
    return missing, unused


def stuck_words(s):
    """卡句比对用的词串（归一化）：NFKC；去掉零宽字符、软连字符；弯引号换成直的；小写；
    取英文词，带连字符的拆成几段，标点不比。"""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub("[​-‏⁠﻿­]", "", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", s.lower())


def has_run(big, small):
    """small 是 big 里连续的一段（small 不空）。"""
    k = len(small)
    return k > 0 and any(big[i:i + k] == small for i in range(len(big) - k + 1))


def stuck_covered(ch, text, sentence):
    """卡句.txt 的一行（text，定位到的原文句子 sentence）讲了没有：本单元某个句子块（长难句或卡句）的原句包含 text，
    或者原句是 sentence 的一段、sentence 是原句的一段。"""
    tw, sw = stuck_words(text), stuck_words(sentence)
    for s in ch["sentences"] + ch["extra"]:
        qw = stuck_words(s["quote"])
        if has_run(qw, tw) or has_run(sw, qw) or has_run(qw, sw):
            return True
    return False


def stuck_hints(chapters):
    """卡句.txt：定位到本单元、讲义里却没讲的句子，一行一条提示。定位由 notebook.py 的 locate_stuck(build) 做：
    build 是本模块（P 已填好），返回 [{line（卡句.txt 的行号）, text（句子，去掉了标记）, result（命中、多处、近似、
    找不到、太短）, unit（单元号或 None）, sentence（定位到的原文句子）}…]。只看命中的、有讲义的单元。
    返回 [(单元名, 类别, 说明)…]。"""
    if not (P.root / "卡句.txt").exists():
        return []
    if not (HERE / "notebook.py").exists():
        return [("全部单元", "卡句", "有 卡句.txt，但还没有 scripts/notebook.py，卡句讲了没有没查")]
    locate = getattr(sibling("notebook"), "locate_stuck", None)
    if locate is None:
        return [("全部单元", "卡句", "notebook.py 里没有 locate_stuck，卡句讲了没有没查")]
    by_n, out = {ch["n"]: ch for ch in chapters}, []
    for hit in locate(sys.modules[__name__]):
        n = hit.get("unit")
        if hit.get("result") != "命中" or n not in by_n:
            continue
        if not stuck_covered(by_n[n], hit.get("text", ""), hit.get("sentence", "")):
            t = hit.get("text", "")
            out.append((unit_name(n), "卡句", f"卡句.txt 第 {hit.get('line')} 行「{t[:30].rstrip()}{'…' if len(t) > 30 else ''}」"
                                             f"定位到本{P.unit}，讲义里没讲（写进长难句或「## {STUCK}」）"))
    return out


def cmd_check(args):
    if args:
        sys.exit("check 只接项目目录")
    rules = load_rules()
    nums = available()
    if not nums:
        sys.exit(no_units())
    lost = [n for n in nums if not source_path(n).exists()]
    if lost:
        sys.exit("找不到原文：" + "、".join(str(source_path(n)) for n in lost))
    txt = {n: source_text(n) for n in unit_nums() if source_path(n).exists()}
    everything = " ".join(txt.values())
    banned, terms, seen = load_banned(), load_terms(), {}
    U = P.unit
    jing = [n for n in unit_nums() if unit_mode(n) == "精读"]     # 回头看按精读单元算
    listed = {}                                                    # 读前列过的词 → 单元号
    bad = total = 0
    tally = {"格式和引文": 0, "禁用语": 0, "长度": 0, "直引号": 0, "术语": 0, "语法术语": 0}
    if P.format >= 3:
        tally["句子结构"] = 0
        tags = [t["tag"] for t in load_tags()]
    hints, chapters, wl = [], [], []      # hints：(单元名, 类别, 说明)，不计入问题数
    for msg in font_spec(P.fonts)["problems"]:      # fonts 的写法：第三版算问题，第一、二版只提示
        if P.format >= 3:
            bad += 1
            tally["设置"] = tally.get("设置", 0) + 1
            print(f"全部单元 设置：{msg}")
        else:
            hints.append(("全部单元", "设置", msg))

    def words_once():
        """词级数据：有读前或轻读单元时才载入，只载入一次。"""
        if not wl:
            wl.append(Words(P.root))
            if not wl[0].lex:
                hints.append(("全部单元", "词级", f"取不到词级数据（{wl[0].why}）：读前词的次数按简单的后缀规则归并，"
                                                 "读前词的级别、复述参考的超纲词没查"))
            elif wl[0].reader() is None:
                hints.append(("全部单元", "词级", f"设置.json 的 level 不是 {'、'.join(wl[0].lx.LEVELS)} 之一，"
                                                 "读前词和复述参考的级别没查"))
        return wl[0]

    for n in nums:
        ch = parse_chapter(n)
        chapters.append(ch)
        name = unit_name(n)
        words = word_count(txt[n])
        hint = lambda kind, msg, name=name: hints.append((name, kind, msg))
        if P.format >= 3:                  # 第三版另走一套；第一、二版照旧
            check_unit_v3(ch, words, rules, txt[n], jing, listed, words_once, hint, tags)
        else:
            if ch["preread"]:
                check_preread(ch, words, rules, listed)
                check_preread_words(ch, txt[n], words, rules, words_once(), hint)
            if ch["mode"] == "轻读":
                check_light(ch, words, rules, txt[n])
                check_retell_words(ch, txt[n], words_once(), hint)
                check_post_length(ch, rules, hint)
            else:
                check_intensive(ch, words, rules, txt[n], jing)
            check_extra(ch, txt[n], rules)
        check_cite_lines(ch)
        for e in ch["errors"]:
            bad += 1
            tally["格式和引文"] += 1
            print(f"{name} 格式：{e}")
        quotes = [(q, True) for q in re.findall(r"^> (.+)$", ch["raw"], flags=re.M)]
        quotes += [(q, True) for q in re.findall(rf"(?:{CITE_RE})：\*(.+?)\*\s*$", ch["raw"], flags=re.M)]
        quotes += [(q, False) for q in re.findall(rf"\| \*(.+?)\*(?:（第 \d+ {re.escape(U)}）)? \|", table_quote_text(ch))]
        for q, same_unit in quotes:
            total += 1
            q2 = q[1:-1] if q.startswith("(") and q.endswith(")") else q
            if q2 in txt[n] or (not same_unit and q2 in everything):
                continue
            bad += 1
            tally["格式和引文"] += 1
            where = f"在别的{U}" if q2 in everything else "原文里找不到"
            print(f"{name} 引文{where}：{q}")
        for bold in re.findall(r"\*\*(.+?)\*\*", ch["raw"]):
            if "*" in bold:
                bad += 1
                tally["格式和引文"] += 1
                print(f"{name} 格式：粗体里有星号「{bold}」")
        for kind, msg in lint(ch, rules, banned, terms, seen):
            bad += 1
            tally[kind] += 1
            print(f"{name} {kind}：{msg}")
    for msg in term_clashes(seen):
        bad += 1
        tally["术语"] += 1
        print(f"全部单元 术语：{msg}")
    missing, unused = check_grammar_terms(chapters)
    for name, msg in missing:
        bad += 1
        tally["语法术语"] += 1
        print(f"{name} 语法术语：{msg}")
    hints += [("全部单元", "语法术语", msg) for msg in unused]
    if P.format >= 3:
        missing, unused = check_tag_table(chapters, tags)
        for name, msg in missing:
            bad += 1
            tally["句子结构"] += 1
            print(f"{name} 句子结构：{msg}")
        hints += [("全部单元", "句子结构", msg) for msg in unused]
        hints += stuck_hints(chapters)
    for name, kind, msg in hints:
        print(f"提示 {name} {kind}：{msg}")
    print(f"核对引文 {total} 处，问题 {bad} 个")
    if bad:
        print("  其中 " + "，".join(f"{k} {v}" for k, v in tally.items()))
    if hints:
        print(f"提示 {len(hints)} 个（估计出来的，逐条看，有理由不改的在 制作记录/计划与检查.md 记一句）")
    return 1 if bad else 0


CHROME = []     # 找到的排版程序路径，第一次用到时找一次
GUI_WARNING = "用本机浏览器排版，可能会抢前台和键盘输入。"
SHELL = "chrome-headless-shell"


def find_chrome():
    """打印 PDF 用的排版程序（Chromium 内核），按顺序：
    1. 环境变量 ER_CHROME 指定的（可执行文件，或 .app 包）；指错了退出并说明；
    2. renderer.py 装好的 chrome-headless-shell（~/Library/Caches/english-reader/chrome-headless-shell/），没有界面；
    3. 设了 ER_ALLOW_GUI_BROWSER=1 才找本机带界面的浏览器：/Applications、~/Applications 里的 Google Chrome、Chromium、
       Microsoft Edge、Brave，再找 PATH 里的。它们可能抢前台和键盘，用的时候开头先说一声。
    都没有就退出，说明怎么装 chrome-headless-shell，不启动任何浏览器。check、md 不用排版程序。"""
    env = os.environ.get("ER_CHROME", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir() and p.suffix == ".app":         # 指到了 .app 包：取包里 Contents/MacOS 下的可执行文件
            exe = sorted(x for x in (p / "Contents" / "MacOS").glob("*") if x.is_file() and os.access(x, os.X_OK))
            p = exe[0] if exe else p
        if p.is_file() and os.access(p, os.X_OK):
            if sys.platform == "darwin" and app_bundle(p):
                print(GUI_WARNING, flush=True)
            return str(p)
        sys.exit(f"环境变量 ER_CHROME 指的 {env} 不是可执行文件。\n"
                 "它要写排版程序本身，例如 ER_CHROME=\"$HOME/Library/Caches/english-reader/chrome-headless-shell/"
                 "<版本>/chrome-headless-shell-mac-arm64/chrome-headless-shell\"")
    renderer = sibling("renderer")
    shell = renderer.installed()
    if shell:
        print(f"排版程序：chrome-headless-shell {shell[0]}（没有界面，不抢前台）", flush=True)
        return str(shell[1])
    if os.environ.get("ER_ALLOW_GUI_BROWSER", "").strip() != "1":
        sys.exit(renderer.install_hint() + "\n"
                 "不想装的话，可以设环境变量 ER_ALLOW_GUI_BROWSER=1 改用本机带界面的浏览器（Google Chrome、Chromium、"
                 "Microsoft Edge、Brave），但它可能会抢前台和键盘输入；装在别处的排版程序用 ER_CHROME 指定。")
    found = None
    for base in (Path("/Applications"), Path.home() / "Applications"):
        for app in CHROME_APPS:
            if not found and (base / app).is_file():
                found = str(base / app)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
        found = found or shutil.which(name)
    if found:
        print(GUI_WARNING, flush=True)
        return found
    sys.exit("设了 ER_ALLOW_GUI_BROWSER=1，可本机找不到带界面的浏览器（Google Chrome、Chromium、Microsoft Edge、Brave，"
             "放在「应用程序」文件夹里的）。\n" + renderer.install_hint() + "\n"
             "浏览器装在别处的，用环境变量 ER_CHROME 指定，例如：\n"
             "  ER_CHROME=\"$HOME/Apps/Google Chrome.app/Contents/MacOS/Google Chrome\" python3 build.py pdf …")


# 排版程序的专用配置目录：第一次用到时建，之后一直复用，不碰平时用的浏览器配置
CHROME_PROFILE = Path.home() / "Library" / "Caches" / "english-reader" / "chrome-profile"
CHROME_FLAGS = ("--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--no-first-run", "--hide-scrollbars")
# chrome-headless-shell 本来就没有界面，不要 --headless=new；另加两个 Mac 上的参数：用假的钥匙串、cookie 不加密，
# 免得它去读钥匙串里的「Chrome Safe Storage」，弹出钥匙串授权窗口抢前台（不认的参数 Chromium 一律忽略）
SHELL_FLAGS = tuple(f for f in CHROME_FLAGS if not f.startswith("--headless")) + ("--use-mock-keychain", "--disable-cookie-encryption")


def app_bundle(exe):
    """浏览器程序在 .app 包里（…/X.app/Contents/MacOS/X）就返回包的路径，否则 None（如 chrome-headless-shell）。"""
    p = Path(exe).resolve()
    if len(p.parents) > 2 and p.parent.name == "MacOS" and p.parent.parent.name == "Contents" and p.parents[2].suffix == ".app":
        return p.parents[2]
    return None


def chrome(*args):
    """排版程序无界面运行一次（打印 PDF）。配置目录都用 CHROME_PROFILE。
    不在 .app 包里的（chrome-headless-shell，或 ER_CHROME 指的别的命令行程序）直接用 subprocess 运行，看退出码；
    chrome-headless-shell 用 SHELL_FLAGS，别的用 CHROME_FLAGS。
    macOS 上 .app 包里的浏览器（只在 ER_CHROME 指定或 ER_ALLOW_GUI_BROWSER=1 时会用到）经 LaunchServices 后台启动：
    open -g（不带到前台）-j（隐藏）-n（新实例）-W（等它退出）；即使这样也可能抢前台和键盘。open 拿不到浏览器的退出码。
    都先打印到同目录的临时文件，成功了、生成了、不是空的才换成目标文件；否则原来的文件不动，退出并说明。
    卡住 120 秒的按专用配置目录找到关掉。"""
    if not CHROME:
        CHROME.append(find_chrome())
    exe = CHROME[0]
    app = app_bundle(exe) if sys.platform == "darwin" else None
    out = next((Path(a.split("=", 1)[1]).expanduser().resolve() for a in args if a.startswith("--print-to-pdf=")), None)
    part = out.with_name(f".{out.stem}.{os.getpid()}.part.pdf") if out else None
    args = [f"--print-to-pdf={part}" if a.startswith("--print-to-pdf=") else a for a in args]
    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    if part:
        part.unlink(missing_ok=True)
    failed, why, tail = False, "", ""
    with tempfile.TemporaryDirectory() as tmp:
        if app is None:
            who = f"排版程序：{exe}（直接运行，配置目录 {CHROME_PROFILE}）"
            flags = SHELL_FLAGS if Path(exe).name == SHELL else CHROME_FLAGS
            cmd = [exe, f"--user-data-dir={CHROME_PROFILE}", *flags, *args]
        else:
            who = f"浏览器：{app}（经 open 后台启动，配置目录 {CHROME_PROFILE}）"
            log = Path(tmp) / "stderr.txt"
            cmd = ["open", "-g", "-j", "-n", "-W", "--stderr", str(log), "-a", str(app), "--args",
                   f"--user-data-dir={CHROME_PROFILE}", *CHROME_FLAGS, *args]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=120)
            if app is None:
                failed, tail = r.returncode != 0, r.stderr[-600:].strip()
                why = f"退出码 {r.returncode}" if failed else ""
            else:
                why = r.stderr.strip()
                tail = log.read_text(encoding="utf-8", errors="replace")[-600:].strip() if log.exists() else ""
        except subprocess.TimeoutExpired:      # 卡住了：按专用配置目录找到它关掉
            subprocess.run(["pkill", "-f", f"user-data-dir={CHROME_PROFILE}"], capture_output=True)
            failed = app is None
            why = f"等了 120 秒{'浏览器' if app else '排版程序'}还没退出，已关掉"
    if part is None:
        if failed:
            sys.exit(f"排版程序出错\n  {who}\n  {why}" + (f"\n  输出：\n{tail}" if tail else ""))
        return
    if not failed and part.is_file() and part.stat().st_size > 0:
        os.replace(part, out)
        return
    part.unlink(missing_ok=True)
    sys.exit(f"{'浏览器' if app else '排版程序'}没有生成 PDF：{out}\n  {who}"
             + (f"\n  {why}" if why else "") + (f"\n  输出：\n{tail}" if tail else ""))


# ---------- 小册子 PDF ----------

CJK = re.compile(r"[　-〿㐀-鿿豈-﫿＀-￯]")
WORD = re.compile(r"[A-Za-z0-9]+(?:[’'][A-Za-z]+|-[A-Za-z0-9]+)*")
STOP = set("""a an the and or but nor of to in on at by for from with as that which who whom whose when where while
if than then so such it its he she they we you i him her them us his their our was were is are be been being
had has have do did does not no this these those there here what""".split())


def sections(ch):
    """各栏目的页眉右边的字；赏析一节按讲义里写的（「赏析」或「文学赏析」）。
    精读单元有补充句时，补充句排在自测前面。轻读单元的读后各栏连着排，只有一个页眉「读后」。
    读前页和精读的章首页是单元的起首页，不排页眉，不在这里。"""
    if ch["mode"] == "轻读":      # 第三版的卡句另起一页，页眉是「卡句」（不算进读后的页数）
        return [("post", "读后")] + ([("stuck", STUCK)] if ch.get("format") == 3 and ch["extra"] else [])
    return ([("sent", "长难句" if ch.get("format") == 3 else "精讲句"), ("words", "词的用法"), ("gram", "语法"), ("essay", ch["essay_label"]), ("write", "写作")]
            + ([("extra", extra_name())] if ch["extra"] else []) + [("quiz", "自测"), ("ans", "答案")])


SHOWN = {"延伸": "举一反三"}
EN = '"Iowan Old Style","Charter",Georgia'


def esc(s):
    return html.escape(s, quote=False)


def pinline(s):
    """PDF 用的行内 Markdown：`code` 是英文片段，用衬线和墨绿，不用等宽灰底。"""
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r'<span class="c">\1</span>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r'<em class="q">\1</em>', s)
    # 包着中文的弯引号用中文字体排成全角
    s = re.sub(r"“([^“”<]*?[\u3400-\u9fff][^“”<]*?)”", r'<span class="zq">“</span>\1<span class="zq">”</span>', s)
    # 中文省略号用中文字体（居中的六个点）；「（第 N 章）」不拆行；破折号不落在行首
    s = s.replace("……", '<span class="zq">……</span>')
    s = re.sub(rf"（第 \d+ {re.escape(P.unit)}）", r'<span class="nb">\g<0></span>', s)
    s = s.replace(" – ", "\u00a0– ")
    return s


def is_en(s):
    s = s.strip()
    return bool(s) and not CJK.search(s) and bool(re.match(r"[A-Z“‘\"(]", s)) and len(s.split()) >= 2


def split_en_first(s):
    """「English example. 中文说明」→ (例句, 说明)；纯英文 → (s, "")；别的形态 → None。"""
    s = s.strip()
    m = CJK.search(s)
    if not m:
        return (s, "") if is_en(s) else None
    ends = [x.end() for x in re.finditer(r"[.?!][”’)]?(?=\s|（|$)", s[:m.start()])]
    if not ends or not is_en(s[:ends[-1]]):
        return None
    return s[:ends[-1]], s[ends[-1]:].strip()


def split_examples(en):
    parts = [x.strip() for x in en.split(" / ")]
    return parts if len(parts) > 1 and all(is_en(x) for x in parts) else [en.strip()]


def examples_html(en, note=""):
    out = "".join(f'<p class="ex">{pinline(x)}</p>' for x in split_examples(en))
    return out + (f'<p class="exn">{pinline(note)}</p>' if note else "")


def example_block(s):
    """「例：」「参考：」的内容：英文例句排成带圆点的 .ex，中文的照段落排。"""
    r = split_en_first(s)
    return examples_html(*r) if r else f"<p>{pinline(s)}</p>"


def tr_html(t, cls="ctr"):
    """引文下面的译文：楷体小一号，排在引文的同一个块里。"""
    return f'<span class="{cls}">{pinline(t)}</span>' if t else ""


def cite_html(rest, tag="原文", trans=""):
    return f'<p class="cite"><span class="ctag">{tag}</span>{pinline(rest)}{tr_html(trans)}</p>'


def cmp_html(plain, better):
    """「对照：平的写法。 / 改过的写法。」"""
    return (f'<div class="cmp"><p class="pl"><span class="cl">平</span><span>{pinline(plain)}</span></p>'
            f'<p class="gd"><span class="cl">改</span><span>{pinline(better)}</span></p></div>')


def paired(lines):
    """缩进行里，「原文：」（或「书中：」）下一行紧跟的「译：」并进引文。产出 (行, 译文)。"""
    out, i = [], 0
    while i < len(lines):
        if cite_tag(lines[i]) and i + 1 < len(lines) and lines[i + 1].startswith("译："):
            out.append((lines[i], lines[i + 1][2:].strip()))
            i += 2
        else:
            out.append((lines[i], ""))
            i += 1
    return out


def ext_line(line, trans=""):
    """「举一反三」里的一行：说明在上、例句在下。拿不准就原样当段落。"""
    if cite_tag(line):
        return cite_html(line[3:], cite_tag(line), trans)
    if line.startswith("译："):
        return f'<p class="tr">{pinline(line[2:])}</p>'
    if is_en(line):
        return f'<div class="exg">{examples_html(line)}</div>'
    if "：" in line:
        pre, post = line.split("：", 1)
        r = split_en_first(post) if re.match(r"\s*[A-Z“‘\"]", post) else None
        if r and pre.strip():
            return f'<div class="exg"><p class="exd">{pinline(pre)}：</p>{examples_html(*r)}</div>'
    r = split_en_first(line)
    if r and r[1]:
        return f'<div class="exg">{examples_html(*r)}</div>'
    return f'<p class="exp">{pinline(line)}</p>'


def sub_line(line, trans=""):
    if cite_tag(line):
        return cite_html(line[3:], cite_tag(line), trans)
    if line.startswith("译："):      # 没跟在原文后面的译文，单独排成楷体
        return f'<p class="tr">{pinline(line[2:])}</p>'
    return f"<p>{pinline(line)}</p>"


def subs(lines, fn=sub_line):
    return "".join(fn(l, t) for l, t in paired(lines))


# ----- 原句主干高亮 -----

def core_match(quote, core):
    """在原句里找出主干的词。返回 (命中词序号集合或 None, 比例, 说明)。"""
    q = [m.group().lower().replace("’", "'") for m in WORD.finditer(quote)]
    raw = WORD.findall(core)
    if re.search(r"\b[B-D]\b", core) or "A" in raw[1:]:
        return None, 0.0, "主干含 A/B 占位符"
    frags = [[w.lower().replace("’", "'") for w in WORD.findall(f)]
             for f in re.split(r"…|\.\.\.|[,;:–—()?!.“”\"]", core)]
    total = sum(len(f) for f in frags)
    hit, p, got = set(), 0, 0
    for f in frags:
        if not f:
            continue
        blocks = next(([(0, i, len(f))] for i in range(p, len(q) - len(f) + 1) if q[i:i + len(f)] == f), None)
        if blocks is None:
            sm = difflib.SequenceMatcher(None, f, q[p:], autojunk=False)
            blocks = [[a, b + p, n] for a, b, n in sm.get_matching_blocks() if n]
            # 「raced back to | the farm … to wipe」：上一块末尾的虚词其实属于下一块开头，挪过去
            for x, y in zip(blocks, blocks[1:]):
                if (x[2] > 1 and x[0] + x[2] == y[0] and y[1] > 0 and q[y[1] - 1] == f[y[0] - 1] and x[1] + x[2] < y[1]
                        and f[y[0] - 1] in STOP):
                    x[2] -= 1
                    y[0] -= 1
                    y[1] -= 1
                    y[2] += 1
        ok = [x for x in blocks if x[2] >= 2 or (f[x[0]] not in STOP and len(f[x[0]]) > 2)]
        # 单个虚词不成块时，只有紧挨着本片段里已认定的块（原句中相隔不超过 3 个词）才算主干
        near = lambda x: any(x[1] - (y[1] + y[2]) <= 3 and x[1] >= y[1] + y[2] or y[1] - (x[1] + x[2]) <= 3 and y[1] >= x[1] + x[2]
                             for y in ok)
        ok += [x for x in blocks if x not in ok and near(x)]
        for a, b, n in ok:
            hit.update(range(b, b + n))
            got += n
            p = max(p, b + n)
    ratio = got / total if total else 0.0
    if ratio < 0.7:
        return None, ratio, "比例不足"
    return hit, ratio, "高亮"


def quote_html(quote, hits):
    if not hits:
        return esc(quote).replace(" – ", "\u00a0– ")
    toks = list(WORD.finditer(quote))
    out, pos, i = [], 0, 0
    while i < len(toks):
        if i in hits:
            j = i
            while j + 1 < len(toks) and j + 1 in hits:
                j += 1
            out.append(esc(quote[pos:toks[i].start()]))
            out.append(f'<b class="core">{esc(quote[toks[i].start():toks[j].end()])}</b>')
            pos, i = toks[j].end(), j + 1
        else:
            i += 1
    return ("".join(out) + esc(quote[pos:])).replace(" – ", "\u00a0– ")


def sentence_hits(ch, key="sentences"):
    """各句主干在原句里的位置（core_match 的结果）。key = "extra" 时算补充句。"""
    res = []
    for s in ch[key]:
        core = next((it["text"] for it in s["items"] if it["label"] == "主干"), "")
        res.append(core_match(s["quote"], core) if core else (None, 0.0, "没有主干"))
    return res


# ----- 各栏目 -----

def sent_html(n, s, match, tight=False, pid="s"):
    """一个长难句。pid 是锚点前缀：长难句 c{n}-s{i}，补充句 c{n}-x{i}。"""
    hits = match[0]
    h = [f'<article class="sent{" tight" if tight else ""}{" tight2" if tight >= 2 else ""}" id="c{n}-{pid}{s["i"]}">',
         f'<div class="pt"></div><h3 class="st"><span class="sn">{s["i"]}</span> <span>{pinline(s["title"])}</span></h3>',
         f'<p class="orig{" hl" if hits else ""}">{quote_html(s["quote"], hits)}</p>']
    return "\n".join(h + items_html(s["items"])) + "</article>"


def items_html(items):
    """句子块里「- **项**：…」的各项（主干、怎么拆、卡点、译、句型、延伸、赏析），每项一个 div。第一、二版和第三版共用。"""
    h = []
    for it in items:
        lab, text, sub = it["label"], it["text"], it["sub"]
        tag = f'<div class="tag">{SHOWN.get(lab, lab)}</div>'
        lead = f"<p>{pinline(text)}</p>" if text else ""
        if lab == "主干":
            h.append(f'<div class="b corel">{tag}<p class="core">{pinline(text)}</p>{subs(sub)}</div>')
        elif lab == "怎么拆":
            steps = "".join(f"<li>{pinline(x)}</li>" for x in sub)
            h.append(f'<div class="b">{tag}{lead}<ol class="steps">{steps}</ol></div>')
        elif lab == "卡点":
            h.append(f'<div class="b alert">{tag}{lead}{subs(sub)}</div>')
        elif lab == "译":
            h.append(f'<div class="b trans">{tag}<div class="kai">{lead}{subs(sub)}</div></div>')
        elif lab == "句型":
            imit = lambda x, t: (f'<p class="imit"><span class="itag">仿写</span>{pinline(x[3:])}</p>'
                                 if x.startswith("仿写：") else sub_line(x, t))
            h.append(f'<div class="b pattern">{tag}<p class="formula">{pinline(text)}</p>{subs(sub, imit)}</div>')
        elif lab == "延伸":
            h.append(f'<div class="b ext">{tag}<p class="lead">{pinline(text)}</p>{subs(sub, ext_line)}</div>')
        elif lab == "赏析":
            h.append(f'<div class="b appr">{tag}{lead}{subs(sub)}</div>')
        else:
            h.append(f'<div class="b plain">{tag}{lead}{subs(sub)}</div>')
    return h


# ----- 第三版的句子块：标签小框、断句网格、注一行；先印整句；不印试和答，不用 core_match -----

REREAD = "拆完的句子，按正常速度再读两三遍。"      # 回读：「长难句」栏末尾印一行，难句本开头也印
LAYOUTS = ("对排", "下置")                        # 断句表的排法，rules.json 的 v3.pdf.chunk_layout
V3_PDF_DEFAULT = {"chunk_layout": "下置", "keep_rows": 16}      # 同 rules.json（实排后定的）
V3_PDF = []        # 第一次用到时读一次 rules.json 的 v3.pdf
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def v3_pdf():
    """第三版 PDF 的版式开关：rules.json 的 v3.pdf，缺的键用 V3_PDF_DEFAULT。chunk_layout 是对排或下置。"""
    if not V3_PDF:
        got = (load_rules().get("v3") or {}).get("pdf") or {}
        cfg = {**V3_PDF_DEFAULT, **{k: v for k, v in got.items() if not k.startswith("_")}}
        if cfg["chunk_layout"] not in LAYOUTS:
            sys.exit(f"{RULES} 的 v3.pdf.chunk_layout 只能是 {' / '.join(LAYOUTS)}，不是「{cfg['chunk_layout']}」")
        V3_PDF.append(cfg)
    return V3_PDF[0]


def extra_name():
    """单元末尾那一栏的名字：第三版叫卡句，第一、二版叫补充句。"""
    return STUCK if P.format >= 3 else EXTRA


def circled(k):
    return CIRCLED[k - 1] if 1 <= k <= len(CIRCLED) else f"({k})"


def tag_boxes(s):
    """标题行右边的小框：结构标签，卡句（或来自卡句的句子）另加标记。"""
    tags = "".join(f'<span class="tg">{esc(t)}</span>' for t in s.get("tags") or [])
    mark = f'<span class="tg tgm">{esc(s["mark"])}</span>' if s.get("mark") else ""
    return f'<span class="tgs">{tags}{mark}</span>' if tags or mark else ""


def chunk_html(md):
    """断句栏的一格：粗体（主语、谓语）排成 b.core，别的照原样。"""
    s = re.sub(r"\*\*(.+?)\*\*", r'<b class="core">\1</b>', esc(md))
    return s.replace(" – ", " – ")


def grid_html(s, layout=None):
    """断句表。对排：两栏网格，左 58% 断句（英文，缩进一层 1.1em，缩进行左边一条细竖线），右 42% 顺读（楷体）。
    下置：断句占满栏宽，顺读在表下排成一段，各块用 ／ 隔开，两边各标 ①②③。不超过 keep_rows 行的整张不跨页。"""
    cfg = v3_pdf()
    layout = layout or cfg["chunk_layout"]
    keep = " keep" if len(s["chunks"]) <= cfg["keep_rows"] else ""
    if layout == "下置":
        rows = "".join(f'<div class="cr d{c["depth"]}"><span class="cn">{circled(k)}</span>'
                       f'<div class="ce">{chunk_html(c["md"])}</div></div>' for k, c in enumerate(s["chunks"], 1))
        gz = "／".join(f'<span class="gn">{circled(k)}</span>{pinline(g)}' for k, g in enumerate(s["gloss"], 1))
        return f'<div class="cg below{keep}">{rows}<p class="gz">{gz}</p></div>'
    rows = "".join(f'<div class="cr d{c["depth"]}"><div class="ce">{chunk_html(c["md"])}</div>'
                   f'<div class="cz">{pinline(g)}</div></div>' for c, g in zip(s["chunks"], s["gloss"]))
    return f'<div class="cg{keep}">{rows}</div>'


def notes_html(notes):
    """表下面一行小字：注　voluble 话多的 · mastered by 被……左右。"""
    if not notes:
        return ""
    return ('<p class="nts"><span class="ntl">注</span>'
            + " · ".join(f'<span class="c">{esc(w)}</span> {pinline(g)}' for w, g in notes) + "</p>")


def sent_title_v3(s, num, tag="h3", href=None):
    """句子块的标题行：句号、标题，右边是标签小框。小框不放进 h3（PDF 书签取 h3 的文字）。"""
    sn = f'<a class="sn" href="{href}">{num}</a>' if href else f'<span class="sn">{num}</span>'
    return f'<div class="sth"><{tag} class="st">{sn} <span>{pinline(s["title"])}</span></{tag}>{tag_boxes(s)}</div>'


def quote3_html(s):
    """句子块的整句：标题下先把原句整句印一遍（同 md 的「> 原句」），再拆。不加粗，主干留给断句表。"""
    return f'<p class="oq">{esc(s["quote"])}</p>'


def sent3_html(n, s, tight=0, pid="s", trans_out=False):
    """第三版的一个句子块：标题行、原句整句、注、断句表、表后各项（怎么拆、卡点、译、句型、延伸、赏析）。
    顺序照 md：先读全句，再看拆开的。试、答不印（在难句本里）。
    trans_out：译不排在块里（轻读的精讲句，译排到答案区「长难句 · 整句和译」）。pid：长难句 s，卡句 x。"""
    cls = "sent v3" + (" tight" if tight else "") + (" tight2" if tight >= 2 else "")
    items = [it for it in s["items"] if not (trans_out and it["label"] == "译")]
    h = [f'<article class="{cls}" id="c{n}-{pid}{s["i"]}">', '<div class="pt"></div>' + sent_title_v3(s, s["i"]),
         quote3_html(s) + notes_html(s["notes"]) + grid_html(s)]
    return "\n".join(h + items_html(items)) + "</article>"


def overview_html(s):
    """整句一眼看全：断句表各行连起来，粗体（主语、谓语）照 b.core 排，其余灰一档。排在答案区，不剧透「试」。"""
    out, pos, quote = [], 0, s["quote"]
    for k, c in enumerate(s["chunks"]):
        text = c["md"].replace("**", "")
        while k and pos < len(quote) and quote[pos].isspace():      # 行与行之间照原句：原句有空白才空一格（破折号贴字的不空）
            pos += 1
        if k and quote[pos - 1].isspace():
            out.append(" ")
        out.append(chunk_html(c["md"]))
        pos += len(text)
    return '<p class="ov">' + "".join(out) + "</p>"


def trans_v3(s):
    """句子块的「译」：(首行, 续行)；没有就是 None。"""
    return next(((it["text"], it["sub"]) for it in s["items"] if it["label"] == "译"), None)


def light3_pdf_html(ch, sect=()):
    """第三版的轻读单元：读前一页；读后从新页起，长难句（栏末一行回读）、理解、词的用法、复述连着排，
    最后是答案（长难句 · 整句和译、理解答案、复述参考）；卡句有才排，另起一页，页眉是「卡句」，不算读后的页数。"""
    n = ch["n"]
    comp, retell = ch["comprehension"], ch["retell"] or {"prompts": [], "refs": []}
    qs = "".join(f'<li id="c{n}-q{k}"><a class="qn" href="#c{n}-a{k}">{k}</a><div class="qt">{lines_html(q)}</div></li>'
                 for k, q in enumerate(comp["questions"], 1))
    sents = "".join(sent3_html(n, s, trans_out=s["kind"] != STUCK) for s in ch["sentences"])
    body = [f'<h2 class="sk">长难句</h2>{sents}<p class="reread">{REREAD}</p>',
            f'<h2 class="sk">理解</h2><ol class="ql cq">{qs}</ol>',
            '<h2 class="sk">词的用法</h2>' + "".join(usage_html(n, k, u, True) for k, u in enumerate(ch["usage"], 1)),
            f'<h2 class="sk" id="c{n}-retell">复述</h2>{retell_html(ch)}']
    tr = "".join(f'<li id="c{n}-t{s["i"]}"><a class="qn" href="#c{n}-s{s["i"]}">{s["i"]}</a>'
                 f'<div class="qt">{overview_html(s)}<p>{pinline(t[0])}</p>{subs(t[1])}</div></li>'
                 for s in ch["sentences"] for t in [trans_v3(s)] if t)
    ans = "".join(f'<li id="c{n}-a{k}"><a class="qn" href="#c{n}-q{k}">{k}</a><div class="qt"><p>{lines_html(a["text"])}</p>'
                  + "".join(cite_html(f"*{q}*", tag, t) for q, tag, t in zip(a["quotes"], a["tags"], a["trans"]))
                  + "</div></li>" for k, a in enumerate(comp["answers"], 1))
    refs = "".join(f'<p class="rref">{pinline(r)}</p>' for r in retell["refs"])
    body.append(f'<div class="lans" id="c{n}-ans"><p class="wait">{WAIT}</p><h2 class="sk">答案</h2>'
                + (f'<div class="ah">长难句 · 整句和译</div><ol class="ql al lt">{tr}</ol>' if tr else "")
                + (f'<div class="ah">理解</div><ol class="ql al">{ans}</ol>' if ans else "")
                + (f'<div class="ah"><a href="#c{n}-retell">复述 · 参考</a></div>{refs}' if refs else "") + "</div>")
    out = (preread_html(ch, "pre" in sect)
           + f'<section class="post{" tight" if "post" in sect else ""}" style="page:c{n}-post" id="c{n}-post">'
           + '<div class="pt"></div>' + "".join(body) + "</section>")
    if ch["extra"]:
        out += (f'<section class="post stuck{" tight" if "stuck" in sect else ""}" style="page:c{n}-stuck" id="c{n}-extra">'
                f'<div class="pt"></div><h2 class="sk">{STUCK}</h2>'
                + "".join(sent3_html(n, s, pid="x") for s in ch["extra"]) + "</section>")
    return out


def dict_html(d):
    s = esc(d)
    s = re.sub(r"/[^/\s][^/]*/", lambda m: f'<span class="ipa">{m.group(0)}</span>', s)
    s = re.sub(r"(?<![A-Za-z/])(n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.(?=[\s（(]|$)", r'<i class="pos">\1.</i>', s)
    s = re.sub(r"\[[UC](?:, ?[UC])?\]", lambda m: f'<span class="gc">{m.group(0)}</span>', s)
    return s


def level_html(level):
    """词条的掌握程度：会用 = 实心，认得 = 空心。"""
    return f'<span class="lv {"use" if level == "会用" else "rec"}">{level}</span>' if level else ""


def usage_html(n, k, u, inline=False):
    """一个词条。inline：词典行排在词头同一行（轻读的读后用，省一行）。"""
    trans = u.get("trans") or [""] * len(u["quotes"])
    tags = u.get("tags") or [CITE[0]] * len(u["quotes"])
    quotes = "".join(f'<p class="cite"><span class="ctag">{tag}</span><em class="q">{esc(x)}</em>{tr_html(t)}</p>'
                     for x, tag, t in zip(u["quotes"], tags, trans))
    notes = []
    for key, v in u["notes"]:
        if key == "例":
            r = split_en_first(v)
            val = examples_html(*r) if r else f"<p>{pinline(v)}</p>"
        else:
            # 注释里写的音标（如 /æbˈsent/）也用音标字体；只认含 IPA 专用字符的斜线段，避免误伤 A / B
            val = re.sub(r"/[^/<>\s][^/<>]*?[ˈˌːəɪʊʌɒɔɜæʃʒθðŋ][^/<>]*?/",
                         lambda m: f'<span class="ipa">{m.group(0)}</span>', f"<p>{pinline(v)}</p>")
        notes.append(f'<div class="nt"><span class="ntag">{key}</span><div class="nv">{val}</div></div>')
    if inline:
        return (f'<div class="entry" id="c{n}-w{k}"><div class="hwl"><span class="wn">{k:02d}</span>'
                f'<span class="hw">{pinline(u["head"])}</span>'
                + (f'<span class="hd">{dict_html(u["dict"])}</span>' if u["dict"] else "")
                + f'{level_html(u.get("level", ""))}</div>'
                f'<p class="gist">{pinline(u["text"])}</p>{quotes}{"".join(notes)}</div>')
    return (f'<div class="entry" id="c{n}-w{k}"><div class="hwl"><span class="wn">{k:02d}</span>'
            f'<span class="hw">{pinline(u["head"])}</span>{level_html(u.get("level", ""))}</div>'
            + (f'<p class="dict">{dict_html(u["dict"])}</p>' if u["dict"] else "")
            + f'<p class="gist">{pinline(u["text"])}</p>{quotes}{"".join(notes)}</div>')


def latin_share(s):
    letters = len(re.findall(r"[A-Za-z]", s))
    return letters / max(1, letters + len(CJK.findall(s)))


def pblocks(md, kind="gram"):
    """语法、赏析、写作、前言页里的 Markdown 块。kind：gram / essay / write / front。

    段首认这几种写法：「> 原文」（下一段可以是「译：」，并进同一个引文块）、「原文：*…*」或「书中：*…*」（同上）、
    「对照：平的。 / 改过的。」、「例：…」、「参考：…」、「译：…」（没跟在引文后面时单独排）。"""
    essay = kind == "essay"
    out, lines, i, warn = [], md.strip("\n").splitlines(), 0, False

    def take_trans(j):
        """j 起（隔着空行）若是「译：」段，返回 (译文, 它后面的行号)；否则 ("", j)。"""
        k = j
        while k < len(lines) and not lines[k].strip():
            k += 1
        if k < len(lines) and lines[k].startswith("译："):
            return lines[k][2:].strip(), k + 1
        return "", j

    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1
        elif l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = rows[2:]
            en = [all(latin_share(r[c]) > 0.6 for r in body if c < len(r)) for c in range(len(rows[0]))]
            cls = lambda c: ' class="en"' if c < len(en) and en[c] else ""

            def cell(k, c):
                s = pinline(c)
                if kind == "front" and cls(k):     # 前言表格「Mr Jones 琼斯」：英文名在前，中文名排浅一点
                    s = re.sub(r"\s+([㐀-鿿][㐀-鿿·]*)$", r' <span class="zh">\1</span>', s)
                return s
            # 只有最后一栏是英文例句的表（如语法术语表）：首栏窄、例句栏宽一点
            shape = " gloss" if len(en) > 2 and en[-1] and not any(en[:-1]) else ""
            out.append(f'<table class="t{len(rows[0])}{shape}"><thead><tr>' + "".join(f"<th>{pinline(c)}</th>" for c in rows[0])
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td{cls(k)}>{cell(k, c)}</td>" for k, c in enumerate(r)) + "</tr>"
                                 for r in body) + "</tbody></table>")
        elif l.startswith("> "):
            tr, i = take_trans(i + 1)
            if essay:
                out.append(f'<blockquote class="epi">{pinline(l[2:])}{tr_html(tr, "qtr")}</blockquote>')
            else:
                out.append(f'<blockquote class="qb"><span class="ctag">原文</span>{pinline(l[2:])}{tr_html(tr, "qtr")}</blockquote>')
        elif l.startswith("### "):
            warn = "容易错" in l
            out.append(f'<div class="gh"><span class="gi"></span><span>{pinline(l[4:])}</span></div>')
            i += 1
        elif re.match(r"(- |\d+\. )", l):
            tag = "ul" if l.startswith("- ") else "ol"
            items = []
            while i < len(lines) and (re.match(r"(- |\d+\. )", lines[i]) or lines[i].startswith("  ")):
                if lines[i].startswith("  "):
                    items[-1][1].append(lines[i].strip())
                else:
                    items.append([pinline(re.sub(r"^(- |\d+\. )", "", lines[i])), []])
                i += 1
            lst = f"<{tag}>" + "".join(f"<li>{x}{subs(s)}</li>" for x, s in items) + f"</{tag}>"
            out.append(f'<div class="alert warnlist">{lst}</div>' if warn else lst)
        elif cite_tag(l):
            tr, i = take_trans(i + 1)
            out.append(cite_html(l[3:], cite_tag(l), tr))
        elif l.startswith("对照：") and len(l[3:].split(" / ")) == 2:
            out.append(cmp_html(*[x.strip() for x in l[3:].split(" / ")]))
            i += 1
        elif l.startswith("例："):
            out.append(f'<div class="exg">{example_block(l[2:].strip())}</div>')
            i += 1
        elif l.startswith("参考："):
            out.append(f'<div class="refb"><div class="tag">参考</div>{example_block(l[3:].strip())}</div>')
            i += 1
        elif l.startswith("译："):
            out.append(f'<p class="tr">{pinline(l[2:].strip())}</p>')
            i += 1
        else:
            cls = []
            if essay and latin_share(l) < 0.12:
                cls.append("jz")
            if l.rstrip().endswith(("：", ":")):      # 引出下文的一句，不单独留在页底
                cls.append("ld")
            attr = f' class="{" ".join(cls)}"' if cls else ""
            out.append(f"<p{attr}>{pinline(l)}</p>")
            i += 1
    return "\n".join(out)


def essay_points(essay):
    parts = re.split(r"^### ", essay, flags=re.M)
    return parts[0], [(p.split("\n", 1)[0].strip(), p.split("\n", 1)[1] if "\n" in p else "") for p in parts[1:]]


def opener_html(ch, tight=False):
    n, ss, us = ch["n"], ch["sentences"], ch["usage"]
    half = (len(ss) + 1) // 2
    intro, points = essay_points(ch["essay"])

    def li(href, kind, text):
        return (f'<li><span class="box"></span><span class="mk">{kind}</span>'
                f'<a href="#{href}">{text}</a></li>')

    def sents(group):
        return "".join(li(f"c{n}-s{s['i']}", f"句 {s['i']}", pinline(s["title"])) for s in group)

    def words(lo, hi):
        if lo >= len(us):
            return ""
        ws = "".join(f'<a href="#c{n}-w{k}"><span class="box"></span>{pinline(u["head"])}</a>'
                     for k, u in enumerate(us[lo:hi], lo + 1))
        return f'<li class="wl"><span class="mk wk">词 {lo + 1:02d}–{min(hi, len(us)):02d}</span><span class="ws">{ws}</span></li>'

    wh = (len(us) + 1) // 2          # 词条前半、后半（9、10 条都是前 5 条一组）
    s1 = sents(ss[:half]) + words(0, wh)
    s2 = sents(ss[half:]) + words(wh, len(us)) + li(f"c{n}-gram", "语法", pinline(ch["grammar_title"]))
    es = "".join(f'<a href="#c{n}-e{k}"><span class="box"></span>{pinline(t)}</a>' for k, (t, _) in enumerate(points, 1))
    wr = li(f"c{n}-write", "写作", pinline(ch["writing_title"])) if has_writing(ch) else ""
    short = "卡" if P.format >= 3 else "补"
    sk = "长难句" if ch.get("format") == 3 else "精讲句"
    xs = "".join(li(f"c{n}-x{s['i']}", f"{short} {s['i']}", pinline(s["title"])) for s in ch["extra"])     # 补充句（卡句），排在自测前面
    s3 = ((f'<li class="wl el"><span class="mk wk">赏析 {len(points)} 点</span><span class="ws">{es}</span></li>'
           if ch["has_essay"] else "")
          + wr + xs + li(f"c{n}-quiz", "自测", f"{len(ch['quiz'])} 题，答案在后一页"))
    third = " · ".join(([ch["essay_label"]] if ch["has_essay"] else []) + (["写作"] if wr else [])
                       + ([extra_name()] if xs else []) + ["自测"])

    def sess(k, what, body):
        return (f'<div class="sess"><div class="sess-h"><b>第 {k} 次</b><span class="sw">{what}</span>'
                f'<span class="tm">约 25–30 分钟</span></div><ul class="map">{body}</ul></div>')

    note = f'<p class="onote">{pinline(ch["note"])}</p>' if ch["note"] else ""
    num = "" if P.single else f'<div class="onum">{n:02d}</div>'      # 只有一篇时不排大号的 01
    oid = f"c{n}-open" if ch["preread"] else f"ch{n}"                # 有读前时单元从读前页起，目录链到读前页
    # PDF 书签按 h1–h6 生成：有读前时单元名的 h1 在读前页，章首页的单元名改用 div，每个单元只有一个书签（指向读前页）
    tag = "div" if ch["preread"] else "h1"
    return (f'<section class="open{" tight" if tight else ""}" id="{oid}" style="page:c{n}-open">{num}'
            f'<{tag} class="oh">{esc(unit_name(n))}</{tag}><p class="og">{ch["grammar_label"]}：{pinline(ch["grammar_title"])}</p>{note}'
            f'<div class="omap"><div class="mh">{map_title()}<span>分三次学完，做完一项打一个勾</span></div>'
            + sess(1, f"{sk} 1–{half} · 词条前半", s1)
            + sess(2, f"{sk} {half + 1}–{len(ss)} · 词条后半 · 语法", s2)
            + sess(3, third, s3) + "</div></section>")


def map_title():
    """精读单元章首页地图的标题「本章地图」。读回 PDF 时靠它找精读单元的章首页（unit_pages）。"""
    return f"本{P.unit}地图"


# 读前页标题下面固定的一行。读回 PDF 时靠它找有读前的单元的首页（unit_pages），别处不要印这句话
PRE_MARK = "读前 · 先看这一页，再读原文"
WAIT = "做完再看"      # 答案前的一行；轻读的读后靠「做完再看答案」找答案从哪一页起


def preread_html(ch, tight=False):
    """读前页：单元的第一页，单独一页。大号单元号、单元名（设置.json 里有标题就跟在后面）、固定的一行 PRE_MARK，
    然后是背景、人物（有才排）、本章的词（词、音标、词性、本章义，排成表）。轻读单元的一级标题下的说明也排在这一页。"""
    n, pre = ch["n"], ch["preread"] or {"background": [], "people": [], "words": []}
    title = "" if P.single else dict(P.units).get(n, "")
    num = "" if P.single else f'<div class="onum">{n:02d}</div>'
    note = f'<p class="onote">{pinline(ch["note"])}</p>' if ch["note"] and ch["mode"] == "轻读" else ""
    h = [f'<section class="pre{" tight" if tight else ""}" id="ch{n}" style="page:c{n}-pre">{num}'
         f'<h1 class="oh">{esc(unit_name(n))}' + (f' <span class="ut">{esc(title)}</span>' if title else "") + "</h1>"
         f'<p class="og">{esc(PRE_MARK)}</p>{note}']
    if pre["background"]:
        h.append('<div class="pb"><div class="ph">背景</div>'
                 + "".join(f'<p class="pbg">{pinline(p).replace(chr(10), " ")}</p>' for p in pre["background"]) + "</div>")
    if pre["people"]:
        h.append('<div class="pb"><div class="ph">人物</div><ul class="ppl">'
                 + "".join(f'<li><span class="pn">{pinline(x["name"])}</span><span class="pr">{pinline(x["role"])}</span></li>'
                           for x in pre["people"]) + "</ul></div>")
    if pre["words"]:
        rows = "".join(f'<tr><td class="pw">{pinline(w["head"])}</td><td class="pi">'
                       + (f'<span class="ipa">{esc(w["ipa"])}</span>' if w["ipa"] else "")
                       + f'</td><td class="pp"><i class="pos">{esc(w["pos"])}.</i></td><td class="pg">{pinline(w["gloss"])}</td></tr>'
                       for w in pre["words"])
        h.append(f'<div class="pb"><div class="ph">本{P.unit}的词</div><table class="pwt"><tbody>{rows}</tbody></table></div>')
    return "".join(h) + "</section>"


def lines_html(text):
    """几行中文（解析时用换行连起来的续行）：行与行之间换行。"""
    return "<br>".join(pinline(x) for x in text.split("\n"))


def retell_html(ch):
    """复述：题目和提示词；别的行（A2 的引导问题等）照常排。「参考：」挪到答案里。"""
    body = next((b for t, b in ch["secs"].items() if t.strip() == "复述"), "")
    prompts, out, rest = iter((ch["retell"] or {}).get("prompts", [])), [], []

    def flush():
        if rest:
            out.append(f'<div class="rtx">{pblocks(chr(10).join(rest), "retell")}</div>')
            rest.clear()
    for line in body.strip("\n").splitlines():
        s = line.strip()
        if s.startswith("参考："):
            continue
        if "提示词：" in s:
            p = next(prompts, None)
            if p:
                flush()
                chips = "".join(f'<span class="hk">{pinline(x)}</span>' for x in p["hints"])
                out.append(f'<p class="rq">{pinline(p["question"])}</p>'
                           f'<p class="hints"><span class="htag">提示词</span>{chips}</p>')
                continue
        rest.append(line)
    flush()
    return "".join(out)


def light_pdf_html(ch, matches, sect=()):
    """轻读单元：读前一页；读后从新的一页起，理解、长难句、词的用法、复述、补充句（有才排）连着排，
    最后是答案（理解题的答案、复述参考），和精读的答案页同一个样子，整块不拆，放不下就整块挪到下一页。
    第三版的轻读单元见 light3_pdf_html。"""
    if ch.get("format") == 3:
        return light3_pdf_html(ch, sect)
    n = ch["n"]
    comp, retell = ch["comprehension"], ch["retell"] or {"prompts": [], "refs": []}
    qs = "".join(f'<li id="c{n}-q{k}"><a class="qn" href="#c{n}-a{k}">{k}</a><div class="qt">{lines_html(q)}</div></li>'
                 for k, q in enumerate(comp["questions"], 1))
    body = [f'<h2 class="sk">理解</h2><ol class="ql cq">{qs}</ol>',
            '<h2 class="sk">长难句</h2>' + "".join(sent_html(n, s, m) for s, m in zip(ch["sentences"], matches)),
            '<h2 class="sk">词的用法</h2>' + "".join(usage_html(n, k, u, True) for k, u in enumerate(ch["usage"], 1)),
            f'<h2 class="sk" id="c{n}-retell">复述</h2>{retell_html(ch)}']
    if ch["extra"]:
        body.append(f'<h2 class="sk" id="c{n}-extra">{EXTRA}</h2>'
                    + "".join(sent_html(n, s, m, pid="x") for s, m in zip(ch["extra"], sentence_hits(ch, "extra"))))
    ans = "".join(f'<li id="c{n}-a{k}"><a class="qn" href="#c{n}-q{k}">{k}</a><div class="qt"><p>{lines_html(a["text"])}</p>'
                  + "".join(cite_html(f"*{q}*", tag, tr) for q, tag, tr in zip(a["quotes"], a["tags"], a["trans"]))
                  + "</div></li>" for k, a in enumerate(comp["answers"], 1))
    refs = "".join(f'<p class="rref">{pinline(r)}</p>' for r in retell["refs"])
    body.append(f'<div class="lans" id="c{n}-ans"><p class="wait">{WAIT}</p><h2 class="sk">答案</h2>'
                + (f'<div class="ah">理解</div><ol class="ql al">{ans}</ol>' if ans else "")
                + (f'<div class="ah"><a href="#c{n}-retell">复述 · 参考</a></div>{refs}' if refs else "") + "</div>")
    return (preread_html(ch, "pre" in sect)
            + f'<section class="post{" tight" if "post" in sect else ""}" style="page:c{n}-post" id="c{n}-post">'
            + '<div class="pt"></div>' + "".join(body) + "</section>")


def has_writing(ch):
    return ch.get("n_writing", 0) > 0


def quiz_html(x):
    """自测题：开头的「回头看（第 N 章）：」排成小标签。"""
    m = P.review.match(x)
    if m:
        return f'<span class="rv">回头看 · 第 {int(m.group(1))} {P.unit}</span>{pinline(x[m.end():])}'
    return pinline(x)


def chapter_pdf_html(ch, matches, tight={}, sect=(), unkeep=()):
    """一个单元。轻读见 light_pdf_html。精读：读前页（有才排）、章首页、精讲句、词的用法、语法、赏析、写作、
    补充句（有才排）、自测、答案，各从新页开始。"""
    if ch["mode"] == "轻读":
        return light_pdf_html(ch, matches, sect)
    n = ch["n"]
    tk = lambda key: " tight" if key in sect else ""
    pg = lambda key: f'style="page:c{n}-{key}"'
    h = ([preread_html(ch, "pre" in sect)] if ch["preread"] else []) + [opener_html(ch, "open" in sect)]
    v3 = ch.get("format") == 3
    if v3:          # 第三版：句子块换成断句网格，栏末一行回读
        sents = "".join(sent3_html(n, s, tight.get(s["i"], 0)) for s in ch["sentences"]) + f'<p class="reread">{REREAD}</p>'
    else:
        sents = "".join(sent_html(n, s, m, tight.get(s["i"], 0)) for s, m in zip(ch["sentences"], matches))
    h.append(f'<section class="sec-sent" {pg("sent")}><div class="pt"></div><h2 class="sk">{"长难句" if v3 else "精讲句"}</h2>{sents}</section>')
    h.append(f'<section class="words{tk("words")}" {pg("words")}><div class="pt"></div><h2 class="sk">词的用法</h2>'
             + "".join(usage_html(n, k, u) for k, u in enumerate(ch["usage"], 1)) + "</section>")
    h.append(f'<section class="gram{tk("gram")}" {pg("gram")} id="c{n}-gram"><div class="pt"></div><h2 class="sk">语法</h2>'
             f'<h3 class="gt">{pinline(ch["grammar_title"])}</h3>{pblocks(ch["grammar"])}</section>')
    intro, points = essay_points(ch["essay"])
    ess = pblocks(intro, "essay") if intro.strip() else ""
    for k, (title, body) in enumerate(points, 1):
        # 短的赏析点整块不拆；整块挪到下一页会留下大片空白的（UNKEEP 里记的），照常跨页
        keep = " keep" if len(body) < 420 and k not in unkeep else ""
        ess += (f'<div class="point{keep}" id="c{n}-e{k}"><div class="eh"><span class="ei">{k:02d}</span><span>{pinline(title)}</span></div>'
                f'{pblocks(body, "essay")}</div>')
    if ch["has_essay"]:
        h.append(f'<section class="essay{tk("essay")}" {pg("essay")}><div class="pt"></div><h2 class="sk">{ch["essay_label"]}</h2>{ess}</section>')
    body, refs = writing_refs(ch["writing"])
    if has_writing(ch):
        # 「参考：」挪到答案页；写作页只在「练习」标题行右端留一个指引，不另占一行。「### 练习」起的部分可以照常跨页
        parts = re.split(r"^(?=### 练习\s*$)", body, maxsplit=1, flags=re.M)
        nxt = f'<p class="wnext"><a href="#c{n}-wref">参考写法在答案页</a></p>' if refs else ""
        if len(parts) > 1:
            drill = pblocks(parts[1], "write")
            if refs:
                drill = drill.replace("<span>练习</span></div>",
                                      f'<span>练习</span><a class="wnext" href="#c{n}-wref">参考写法在答案页</a></div>', 1)
            wr = pblocks(parts[0], "write") + f'<div class="drill" id="c{n}-drill">{drill}</div>'
        else:
            wr = pblocks(parts[0], "write") + nxt
        h.append(f'<section class="write{tk("write")}" {pg("write")} id="c{n}-write"><div class="pt"></div><h2 class="sk">写作</h2>'
                 f'<h3 class="gt">{pinline(ch["writing_title"])}</h3>{wr}</section>')
    if ch["extra"]:
        # 补充句（第三版叫卡句）：和精讲句同一个排法，句与句接着排（不各占一页）
        xs = ("".join(sent3_html(n, s, pid="x") for s in ch["extra"]) if v3 else
              "".join(sent_html(n, s, m, pid="x") for s, m in zip(ch["extra"], sentence_hits(ch, "extra"))))
        h.append(f'<section class="sec-sent extra" {pg("extra")} id="c{n}-extra"><div class="pt"></div><h2 class="sk">{extra_name()}</h2>'
                 f'{xs}</section>')
    qs ="".join(f'<li id="c{n}-q{k}"><a class="qn" href="#c{n}-a{k}">{k}</a><div class="qt">{quiz_html(x)}</div></li>'
                 for k, x in enumerate(ch["quiz"], 1))
    ans = "".join(f'<li id="c{n}-a{k}"><a class="qn" href="#c{n}-q{k}">{k}</a><div class="qt">{pinline(x)}</div></li>'
                  for k, x in enumerate(ch["answers"], 1))
    # 题多时题间距收一点，保证一页放得下
    gap = 9 if len(ch["quiz"]) <= 8 else 7.4 if len(ch["quiz"]) <= 9 else 6 if len(ch["quiz"]) <= 10 else 5
    h.append(f'<section class="quiz" {pg("quiz")} id="c{n}-quiz"><div class="pt"></div><h2 class="sk">自测</h2>'
             f'<ol class="ql" style="--qg:{gap}mm">{qs}</ol></section>')
    back = f"#c{n}-drill" if re.search(r"^### 练习\s*$", body, flags=re.M) else f"#c{n}-write"
    wref = (f'<div class="wans" id="c{n}-wref"><a class="wh" href="{back}">写作练习 · 参考</a>'
            + "".join(example_block(r) for r in refs) + "</div>") if has_writing(ch) and refs else ""
    h.append(f'<section class="answers{tk("ans")}" {pg("ans")}><p class="wait">做完再看</p><div class="pt"></div><h2 class="sk">答案</h2>'
             f'<ol class="ql al">{ans}</ol>{wref}</section>')
    return "\n".join(h)


def writing_refs(md):
    """把写作里段首的「参考：…」行拿出来（PDF 里排到答案页）。返回 (其余 Markdown, [参考内容…])。"""
    refs = [l[3:].strip() for l in md.splitlines() if l.startswith("参考：")]
    return "\n".join(l for l in md.splitlines() if not l.startswith("参考：")), refs


def css_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def page_css(chapters):
    r = []
    for ch in chapters:
        n = ch["n"]
        if ch["preread"] or ch["mode"] == "轻读":      # 读前页和章首页一样：单元的起首页，没有页眉
            r.append(f"@page c{n}-pre{{margin-top:18mm}}")
        if ch["mode"] == "精读":
            r.append(f"@page c{n}-open{{margin-top:18mm}}")
        for key, label in sections(ch):
            r.append(f'@page c{n}-{key}{{@top-left{{content:{css_str(running_head(n))}}}@top-right{{content:{css_str(label)}}}}}')
    return "\n".join(r)


def pdf_font_css(d):
    """字体目录里有的 BookSong / BookKai 写成 @font-face；没有目录就是空串，CSS 里的字体栈回退到系统宋体、楷体。"""
    return (''.join(
        f'@font-face{{font-family:{fam};src:url("{(d / name).as_uri()}");font-weight:{weight};font-style:normal}}'
        for fam, name, weight in (("StudySong", "BookSong-Regular.otf", 400), ("StudySong", "BookSong-Bold.otf", 600),
                                  ("StudyKai", "BookKai-Regular.ttf", 400))
        if (d / name).exists()) if d else '')


FONT_DIR = []      # 第一次排 PDF 时找一次字体目录，之后共用

PDF_CSS = """
:root{--ink:#1f2a2a;--ink2:#4e5a58;--soft:#6b7775;--mute:#949d9b;--g:#2f4f4f;--gt:#eef2f1;--gl:#c3d0ce;
  --r:#a5532a;--rt:#faf3ee;--rl:#e6cbbb;--rule:#dfdbd2;
  --en:"Iowan Old Style","Charter",Georgia,StudySong,serif;   /* 英文片段里偶尔夹中文（如 名词 + doing），用书宋而不是系统宋体 */
  --body:"Iowan Old Style","Charter",Georgia,StudySong,"Songti SC",serif;
  --kai:"Iowan Old Style","Charter",Georgia,StudyKai,"Kaiti SC","STKaiti",serif;
  --sans:"Helvetica Neue","PingFang SC","Heiti SC",sans-serif;
  --ipa:"STIX Two Text","Times New Roman",serif}
*{box-sizing:border-box;font-variant-ligatures:none !important;font-feature-settings:"liga" 0,"clig" 0 !important}
@page{size:148mm 210mm;margin:18mm 15mm 16mm;
  @top-left{font:7.4pt/1 "PingFang SC";color:#8f9896;vertical-align:bottom;padding-bottom:5mm;letter-spacing:.04em}
  @top-right{font:7.4pt/1 "PingFang SC";color:#8f9896;vertical-align:bottom;padding-bottom:5mm;letter-spacing:.12em}
  @bottom-center{content:counter(page);font:8pt/1 "Iowan Old Style",Georgia,serif;color:#8f9896;vertical-align:top;padding-top:6mm}}
@page cover{@bottom-center{content:none}}
html{font-size:10pt}
body{margin:0;background:#fff;color:var(--ink);font-family:var(--body);line-height:1.66;text-align:left;
  text-wrap:pretty;-webkit-font-smoothing:antialiased;orphans:2;widows:2;hyphens:none}
p{margin:0}
a{color:inherit;text-decoration:none}
strong{font-weight:600}
em.q{font-style:italic}
.c{font-family:var(--en);color:var(--g)}
.zq{font-family:StudySong,"Songti SC",serif}
.nb{white-space:nowrap}
.kai .zq,.ctr .zq,.qtr .zq,p.tr .zq{font-family:StudyKai,"Kaiti SC",serif}
/* 标题、目录、章首地图用黑体，引号跟随标题字体，不换成宋体全角 */
h1 .zq,h2 .zq,h3 .zq,b .zq,.og .zq,.gh .zq,.eh .zq,ul.map .zq{font-family:inherit}
.alert .c{color:var(--r)}
.ipa{font-family:var(--ipa);color:var(--g);font-style:normal}
.pos{font-family:var(--en);font-style:italic;color:var(--soft)}
.gc{font-family:var(--en);color:var(--soft);font-size:.92em}

/* 栏目起首 */
section[style^="page:"],nav.toc,section.howto{break-before:page}
.pt{height:1px}
h2.sk{font:600 7.8pt/1 var(--sans);letter-spacing:.3em;color:var(--g);margin:0 0 7mm;padding-bottom:2.2mm;
  border-bottom:.5pt solid var(--gl)}

/* 封面、前部 */
.cover{page:cover;height:172mm;display:flex;flex-direction:column}
.cover .ck{margin-top:40mm;font:500 7.8pt/1 var(--sans);letter-spacing:.4em;color:var(--soft)}
.cover h1{font:600 36pt/1.1 var(--en);color:var(--g);margin:6mm 0 4mm;letter-spacing:-.01em}
.cover .sub{font:500 12pt/1.4 var(--sans);color:var(--ink);letter-spacing:.12em}
.cover .rule{width:20mm;height:1.2pt;background:var(--r);margin:11mm 0 7mm}
.cover .meta{font-size:9.6pt;line-height:1.95;color:var(--ink2)}
.cover .meta .en{font-family:var(--en)}
.cover .foot{margin-top:auto;padding-top:3mm;border-top:.5pt solid var(--rule);font:8pt/1.8 var(--sans);color:var(--soft)}
.front{page:front}
.howto{break-after:page}
h1.fh{font:600 15pt/1.3 var(--sans);color:var(--g);margin:0 0 4mm}
.fl{font-size:9.2pt;line-height:1.7;color:var(--ink2);margin:0 0 3.6mm}
.lgi{margin:0 0 2.4mm;break-inside:avoid}
.howto .tag{margin-bottom:1mm}
.howto .orig{font-size:9.8pt;line-height:1.6;margin-bottom:0}
.howto .alert p,.howto .exd,.howto .ex{font-size:9.2pt}
.lgm{font-size:8pt;line-height:1.55;color:var(--soft);margin-top:.9mm}
.howto .alert,.howto .ext{padding-top:1.8mm;padding-bottom:1.8mm}
.lgr{display:flex;align-items:baseline;gap:3mm}
.lgw{display:flex;align-items:baseline}
.lgw .lgc{margin-left:auto}
.lgc{flex:none;display:flex;gap:1.4mm;align-items:baseline}
.lgc .lv{margin-left:0;top:0}
.lgc .rv{margin-right:0;top:0}
.lgr .lgm{margin-top:0}
.howto .lgi{margin-bottom:1.7mm}
.howto .fl{margin-bottom:3mm}
.howto .lgm{margin-top:.7mm;line-height:1.45}
.howto .src{line-height:1.55}
.howto .abbr{row-gap:0}
.abt{grid-column:span 2;color:var(--ink2)}
.src{font-size:8.2pt;line-height:1.65;color:var(--ink2);border-top:.5pt solid var(--rule);padding-top:2.2mm;margin-top:2.6mm}
.abbr{display:grid;grid-template-columns:repeat(5,1fr);gap:.4mm 2mm;font-size:8.2pt;margin:1.6mm 0 1.2mm;color:var(--ink2)}
.abbr .pos{color:var(--g);font-style:normal;font-weight:600;margin-right:1mm}
.fsub{font:600 7.4pt/1 var(--sans);letter-spacing:.2em;color:var(--g);margin:0 0 1.4mm}
.toc{break-after:page}
a.trow{display:grid;grid-template-columns:11mm 1fr 9mm;align-items:baseline;padding:2.05mm 0 2.15mm;
  border-bottom:.4pt solid var(--rule);break-inside:avoid}
.tn{font:600 13pt/1 var(--en);color:var(--r)}
.tt b{display:block;font:600 9.8pt/1.45 var(--sans);color:var(--ink)}
.tt b span{color:var(--g);font-weight:500;margin-left:1.5mm}
.tt small{display:block;font:7.6pt/1.5 var(--sans);color:var(--soft);margin-top:.4mm}
.tp{text-align:right;font:9pt/1 var(--en);color:var(--ink2)}

/* 章首页 */
.open{padding-top:4mm}
.onum{font:400 54pt/1 var(--en);color:var(--g);letter-spacing:-.02em}
h1.oh{font:600 15pt/1.3 var(--sans);color:var(--ink);margin:2.5mm 0 1mm}
.og{font:500 9.4pt/1.5 var(--sans);color:var(--r)}
.onote{font-size:8.8pt;color:var(--soft);margin-top:2mm}
.omap{margin-top:8mm}
.mh{font:600 9.8pt/1 var(--sans);color:var(--g);letter-spacing:.2em;display:flex;justify-content:space-between;
  align-items:baseline;margin-bottom:1mm}
.mh span{font-weight:400;letter-spacing:.04em;color:var(--mute);font-size:8pt}
.sess{margin-top:5mm;break-inside:avoid}
.sess-h{display:flex;gap:2.8mm;align-items:baseline;border-bottom:.5pt solid var(--gl);padding-bottom:1.3mm;margin-bottom:2mm}
.sess-h b{font:600 9.6pt/1.2 var(--sans);color:var(--g)}
.sess-h .sw{font:8pt/1.2 var(--sans);color:var(--soft)}
.sess-h .tm{margin-left:auto;font:8pt/1.2 var(--sans);color:var(--r)}
ul.map{list-style:none;margin:0;padding:0;font-size:9.3pt;line-height:1.5}
ul.map li{display:flex;align-items:baseline;gap:2mm;margin:0 0 1.1mm}
.box{flex:none;display:inline-block;width:2.6mm;height:2.6mm;border:.6pt solid var(--g);border-radius:.35mm;
  position:relative;top:.3mm}   /* 空盒子的基线是底边；下移一点，和汉字字身居中 */
.mk{flex:none;width:8.4mm;font:500 7.6pt/1.5 var(--sans);color:var(--mute)}
.mk.wk{width:14.4mm}
li.wl .ws{display:flex;flex-wrap:wrap;gap:.6mm 3.6mm;font-family:var(--en)}
li.wl .ws a{display:inline-flex;align-items:baseline;gap:1.5mm;white-space:nowrap}
li.wl{gap:0 !important}
li.wl>.mk{margin-left:4.6mm}
li.el .ws{font-family:var(--body);gap:.6mm 4mm}
li.wl{margin-bottom:1.5mm !important}
/* 章首页一页放不下时（句子、赏析点多，标题长）整页收紧 */
.open.tight{padding-top:0}
.open.tight .onum{font-size:42pt}
.open.tight h1.oh{margin:1.6mm 0 .6mm}
.open.tight .omap{margin-top:5mm}
.open.tight .sess{margin-top:3.4mm}
.open.tight .sess-h{margin-bottom:1.4mm}
.open.tight ul.map{line-height:1.4}
.open.tight ul.map li{margin-bottom:.6mm}
.open.tight li.wl{margin-bottom:.9mm !important}
.open.tight li.wl .ws{row-gap:.2mm}

/* 精讲句 */
article.sent>.pt{break-before:page}
h2.sk+article.sent>.pt{break-before:auto}
h3.st{display:block;padding-left:7mm;text-indent:-7mm;font:600 12pt/1.45 var(--sans);color:var(--ink);margin:0 0 4.2mm;
  break-after:avoid}
h3.st .sn{font:600 19pt var(--en);color:var(--g);margin-right:1.2mm}  /* 行高须为 normal：字形超出行框时 Chrome 书签会把序号重复一遍 */
.orig{font-family:var(--en);font-size:11.3pt;line-height:1.74;color:var(--ink);margin:0 0 6mm;padding-left:4mm;
  border-left:1.3pt solid var(--r)}
.orig.hl{color:#7c8785}
.orig b.core{font-weight:600;color:#132020}
.b{margin:0 0 4.2mm}
.tag{font:600 8.4pt/1.2 var(--sans);letter-spacing:.16em;color:var(--g);margin:0 0 1.5mm;break-after:avoid}
.corel{break-inside:avoid}
.core{font-family:var(--en);font-size:10.4pt;line-height:1.6;color:var(--g)}
ol.steps{list-style:none;margin:0;padding:0;position:relative;counter-reset:st}
ol.steps::before{content:"";position:absolute;left:2.05mm;top:2.5mm;bottom:3mm;border-left:.6pt solid var(--gl)}
ol.steps li{position:relative;padding-left:7.6mm;margin:0 0 2mm;break-inside:avoid;counter-increment:st}
ol.steps li:last-child{margin-bottom:0}
ol.steps li::before{content:counter(st);position:absolute;left:0;top:.9mm;width:4.1mm;height:4.1mm;border-radius:50%;
  background:#fff;border:.7pt solid var(--g);font:600 6.4pt/3.75mm var(--en);text-align:center;color:var(--g)}
.alert{background:var(--rt);border-left:1.6pt solid var(--r);padding:2.4mm 3.6mm 2.6mm;break-inside:avoid}
.alert .tag{color:var(--r)}
.alert p+p{margin-top:1.2mm}
.trans{break-inside:avoid}
.kai{font-family:var(--kai);font-size:10.3pt;line-height:1.76;color:#2c3535;padding-left:3mm;border-left:.5pt solid var(--rule)}
.pattern{break-inside:avoid}
.formula{font-family:var(--en);background:var(--gt);color:var(--g);padding:1.7mm 3mm;border-radius:.8mm;line-height:1.55}
.formula .c{color:inherit}
.imit{margin-top:1.8mm;padding-left:3mm;font-family:var(--en)}
.itag{font:600 7.8pt/1 var(--sans);color:var(--soft);letter-spacing:.12em;margin-right:2.2mm}
.ext .lead{margin-bottom:.6mm;break-after:avoid}   /* 导语不单独留在页底 */
.exg{margin:1.9mm 0 0;break-inside:avoid}
.exd{color:var(--ink)}
.ex{font-family:var(--en);position:relative;padding-left:6mm;margin-top:.7mm;color:#18262a;line-height:1.6;break-inside:avoid}
.ex::before{content:"";position:absolute;left:2.3mm;top:.66em;width:1.15mm;height:1.15mm;border-radius:50%;background:var(--r)}
.exn{padding-left:6mm;margin-top:.5mm;font-size:8.9pt;line-height:1.6;color:var(--soft)}
.exp{margin-top:1.9mm}
/* 「书中」「原文」悬挂缩进：标签单占一栏，英文折行和译文都对齐到标签后面（标签宽 = 两个 7.4pt 字加字距 ≈ 16.9pt，再加 2mm 间距） */
.cite{margin:2.3mm 0 0;padding:.3mm 0 .3mm calc(3mm + 16.9pt + 2mm);text-indent:calc(-16.9pt - 2mm);
  border-left:.9pt solid var(--r);break-inside:avoid;line-height:1.6}
.cite em.q,.cite{font-family:var(--en)}
.cite em.q{color:#3b3631}
.ctag{font:600 7.4pt/1 var(--sans);color:var(--r);letter-spacing:.14em;margin-right:2mm;font-style:normal;
  position:relative;top:-.3mm}
/* 引文下面的译文：楷体、小一号、浅一点，排在引文的同一个块里（左边同一条赭红线），和引文不分页 */
.ctr,.qtr,p.tr{display:block;font-family:var(--kai);font-style:normal;font-weight:400;color:var(--ink2);text-indent:0}
.ctr{font-size:9.1pt;line-height:1.58;margin-top:.5mm}
.qtr{font-size:9.4pt;line-height:1.62;margin-top:1mm}
p.tr{font-size:9.4pt;line-height:1.62;margin:0 0 2.6mm}
.appr{margin-top:5.6mm;padding-top:3.2mm;border-top:.5pt solid var(--rule)}
.appr .tag{color:var(--r)}
.appr>p{font-size:9.8pt;line-height:1.86;color:#2a3332}

/* 最后一页只剩几行的句子，排紧一点 */
article.tight{line-height:1.56}
.tight h3.st{margin-bottom:3.4mm}
.tight .orig{font-size:10.9pt;line-height:1.62;margin-bottom:4.6mm}
.tight .b{margin-bottom:3.2mm}
.tight ol.steps li{margin-bottom:1.2mm}
.tight .kai{line-height:1.62}
.tight .exg,.tight .exp,.tight .cite{margin-top:1.3mm}
.tight .ex,.tight .core,.tight .cite{line-height:1.5}
.tight .appr{margin-top:4.2mm;padding-top:2.6mm}
.tight .appr>p{line-height:1.7}
article.tight2{font-size:9.5pt}
.tight2 .orig{font-size:10.5pt}
.tight2 .kai{font-size:9.8pt}
.tight2 .core{font-size:9.9pt}
.tight2 .appr>p{font-size:9.4pt}

/* 语法、赏析尾页只剩几行，词条页下部空得多：整个栏目略排紧（字号不变） */
.gram.tight{font-size:9.8pt}
.gram.tight h2.sk,.essay.tight h2.sk{margin-bottom:4.6mm}
.gram.tight p{margin-bottom:1.6mm;line-height:1.52}
.gram.tight h3.gt{margin-bottom:3.6mm}
.gram.tight .gh{margin:4.4mm 0 1.8mm}
.gram.tight blockquote.qb{margin:1.6mm 0 2.2mm;line-height:1.55}
.gram.tight table{margin:2mm 0 3mm;line-height:1.45}
.gram.tight td{padding:1.3mm 3mm 1.3mm 0}
.gram.tight li{margin-bottom:1mm}
.gram.tight .alert{padding-top:1.8mm;padding-bottom:1.8mm}
.write.tight{font-size:9.8pt}
.write.tight h2.sk{margin-bottom:4.6mm}
.write.tight p{margin-bottom:1.6mm;line-height:1.52}
.write.tight h3.gt{margin-bottom:3.6mm}
.write.tight .gh{margin:4.4mm 0 1.8mm}
.write.tight blockquote.qb{margin:1.6mm 0 2.2mm;line-height:1.55}
.write.tight li{margin-bottom:1mm}
.write.tight .cmp{margin:1.6mm 0 2.4mm}
.essay.tight{font-size:9.8pt}
.essay.tight p{line-height:1.7;margin-bottom:1.6mm}
.essay.tight .point{margin-bottom:5mm}
.essay.tight .eh{margin-bottom:2.2mm}
.essay.tight blockquote.epi{margin-bottom:2.4mm;line-height:1.55}
.essay.tight li{margin-bottom:1mm}
.words.tight .entry{padding:3.2mm 0 3.3mm}
.words.tight .dict{margin-top:.6mm}
.words.tight .gist{margin-top:1mm}
.words.tight .entry .cite{margin-top:1.5mm}
.words.tight .nt{margin-top:1mm;line-height:1.55}
.words.tight .ntag{line-height:14.6pt}

/* 词的用法 */
.entry{padding:4.4mm 0 4.6mm;border-top:.5pt solid var(--rule);break-inside:avoid}
h2.sk+.entry{border-top:0;padding-top:0}
.hwl{display:flex;align-items:baseline;gap:2.6mm;break-after:avoid}
/* 掌握程度：会用 = 墨绿实心，认得 = 灰线空心 */
.lv{flex:none;margin-left:auto;font:600 6.6pt/1 var(--sans);letter-spacing:.14em;padding:.8mm .9mm .7mm 1.5mm;
  border-radius:.7mm;border:.5pt solid var(--g);position:relative;top:-1mm;white-space:nowrap;margin-right:.4mm}
.lv.use{background:var(--g);color:#fff}
.lv.rec{color:var(--soft);border-color:#b9c3c1}
.wn{font:600 8pt/1 var(--en);color:var(--r);letter-spacing:.04em;width:5mm;flex:none}
.hw{font:600 14.5pt/1.25 var(--en);color:var(--g)}
.dict,.gist,.entry .cite,.nt{margin-left:7.6mm}
.dict{margin-top:1mm;font-size:9.3pt;line-height:1.6;color:var(--ink2)}
.gist{margin-top:1.4mm}
.nt{display:grid;grid-template-columns:8.5mm 1fr;margin-top:1.5mm;font-size:9.4pt;line-height:1.65}
.ntag{font:600 7.8pt/15.5pt var(--sans);color:var(--g);letter-spacing:.06em}
.nt .ex{padding-left:4mm;margin-top:0}
.nt .ex::before{left:.6mm}
.nt .exn{padding-left:4mm}

/* 语法 */
h3.gt{font:600 16pt/1.35 var(--sans);color:var(--g);margin:0 0 5mm}
.gram{counter-reset:gh}
.gram p{margin:0 0 2.6mm}
.gh{font:600 10.8pt/1.45 var(--sans);color:var(--ink);margin:7mm 0 2.8mm;break-after:avoid;display:flex;gap:2.4mm;
  align-items:baseline;counter-increment:gh}
.gram .gi::before,.write .gi::before{content:counter(gh);font:600 10pt/1 var(--en);color:var(--r)}
blockquote.qb{margin:2.4mm 0 3.2mm;padding:.4mm 0 .4mm calc(3.5mm + 16.9pt + 2mm);text-indent:calc(-16.9pt - 2mm);
  border-left:.9pt solid var(--r);font-family:var(--en);
  font-style:italic;font-size:10.1pt;line-height:1.65;color:#3b3631;break-inside:avoid}
table{width:100%;border-collapse:collapse;margin:3mm 0 4.5mm;font-size:9pt;line-height:1.55;break-inside:avoid}
th{font:600 8.2pt/1.4 var(--sans);letter-spacing:.06em;color:var(--g);text-align:left;padding:0 3mm 1.6mm 0;
  border-bottom:.8pt solid var(--g)}
td{padding:1.9mm 3mm 1.9mm 0;border-bottom:.4pt solid var(--rule);vertical-align:top;overflow-wrap:anywhere}
td.en{font-family:var(--en);color:#18262a}
:is(.gram,.essay,.write) :is(ul,ol){margin:1mm 0 3mm;padding-left:1.25em}
:is(.gram,.essay,.write) li{margin:0 0 1.6mm}
:is(.gram,.essay,.write) li::marker{color:var(--r)}
.warnlist ul,.warnlist ol{margin:0}
.warnlist li:last-child{margin-bottom:0}
:is(.gram,.essay,.write) .cite{line-height:1.6;margin:1.6mm 0 2.6mm}
:is(.gram,.essay,.write) li .cite{margin:1mm 0 .4mm}
:is(.gram,.essay,.write) li:has(.cite){break-inside:avoid}   /* 列表项的说明不和下面的引文分页 */
p.ld{break-after:avoid}
/* 段首「例：」「对照：」「参考：」：自造例句，和精讲句里的 .ex 一个样子 */
:is(.gram,.essay,.write) .exg{margin:1.4mm 0 3mm}
:is(.gram,.essay,.write) .ex{margin:.7mm 0 0;line-height:1.6}
:is(.gram,.essay,.write) .exn{margin:.5mm 0 0;line-height:1.6}
.cmp{margin:2.2mm 0 3.2mm;padding:.3mm 0 .3mm 3mm;border-left:.6pt solid var(--gl);break-inside:avoid}
:is(.gram,.essay,.write) .cmp p,.cmp p{display:grid;grid-template-columns:6mm 1fr;align-items:baseline;margin:0;
  font-family:var(--en);line-height:1.6;text-align:left}
:is(.gram,.essay,.write) .cmp p+p,.cmp p+p{margin-top:.8mm}
.cl{font:600 7.2pt/1 var(--sans);letter-spacing:.06em}
.cmp .pl{color:#87918f}
.cmp .pl .cl{color:var(--mute)}
.cmp .gd{color:#18262a}
.cmp .gd .cl{color:var(--r)}
.refb{margin:3.4mm 0 3mm;padding:2.3mm 3.6mm 2.5mm;background:var(--gt);border-radius:.8mm;break-inside:avoid}
.refb .tag{margin-bottom:.6mm}
:is(.gram,.essay,.write) .refb p{margin:0}
:is(.gram,.essay,.write) .refb .ex{margin-top:.6mm}

/* 写作：和语法同一套 */
.write{counter-reset:gh}
.write p{margin:0 0 2.6mm}
.write p.wnext{font:8pt/1.5 var(--sans);color:var(--soft);letter-spacing:.04em;margin:2.2mm 0 0;break-before:avoid}
.wnext a::after,a.wnext::after{content:" →";color:var(--r)}
.gh a.wnext{margin-left:auto;font:400 8pt/1.5 var(--sans);color:var(--soft);letter-spacing:.04em}

/* 文学赏析 */
.point{margin:0 0 8mm}
.point.keep{break-inside:avoid}
.eh{font:600 10.8pt/1.45 var(--sans);color:var(--ink);margin:0 0 3mm;break-after:avoid;display:flex;gap:2.4mm;align-items:baseline}
.ei{font:600 8pt/1 var(--en);color:var(--r)}
blockquote.epi{margin:0 0 3.4mm;padding:.5mm 0 .5mm 4mm;border-left:1pt solid var(--r);font:italic 10.8pt/1.65 var(--en);
  color:#3b3631;break-inside:avoid}
.essay p{margin:0 0 2.6mm;line-height:1.95}
.essay p.jz{text-align:justify}

/* 自测、答案 */
ol.ql{list-style:none;margin:0;padding:0}
ol.ql li{display:grid;grid-template-columns:8mm 1fr;margin:0 0 var(--qg,9mm);break-inside:avoid}
.qn{font:600 13pt/1.3 var(--en);color:var(--g)}
.rv{display:inline-block;font:500 6.8pt/1 var(--sans);letter-spacing:.08em;color:var(--g);background:var(--gt);
  border:.5pt solid var(--gl);border-radius:.7mm;padding:.75mm 1.4mm .65mm;margin-right:2.2mm;position:relative;top:-.5mm;
  white-space:nowrap}
.wait{font:500 7.4pt/1 var(--sans);letter-spacing:.3em;color:var(--mute);margin:0 0 5mm}
ol.al{font-size:9.2pt;line-height:1.7}
ol.al li{margin-bottom:3.4mm}
ol.al .qn{font-size:10pt;line-height:1.7}
/* 答案页末尾：写作练习的参考写法（从写作页挪过来），小标题点回写作页的练习 */
.wans{margin-top:5mm;padding-top:3mm;border-top:.5pt solid var(--rule);font-size:9.2pt;line-height:1.7;break-inside:avoid}
a.wh{display:block;font:600 8.4pt/1.2 var(--sans);letter-spacing:.16em;color:var(--g);margin:0 0 1.4mm}
.wans .ex{padding-left:8mm;margin-top:.8mm;line-height:1.65}
.wans .ex::before{left:1.4mm}
.wans>p:not(.ex){padding-left:8mm}
/* 答案加上参考一页放不下：只收间距，字号不变 */
.answers.tight .wait{margin-bottom:3.6mm}
.answers.tight h2.sk{margin-bottom:5mm}
.answers.tight ol.al li{margin-bottom:2.2mm}
.answers.tight .wans{margin-top:3.4mm;padding-top:2.4mm}

/* 前言各页（语法术语、人物和历史对应）：表格可以跨页，表头自动重复 */
section.fpage{break-before:page}
.fpage>p{font-size:9.2pt;line-height:1.7;color:var(--ink2);margin:0 0 3.6mm}
.fpage table{break-inside:auto;margin:2.4mm 0 6mm;font-size:8.9pt;line-height:1.5}
.fpage tr{break-inside:avoid}
.fpage td{padding:1.45mm 2.6mm 1.45mm 0}
.fpage td:first-child{font-weight:600;color:var(--g);white-space:nowrap}
.fpage .gloss td:first-child{white-space:normal;width:19mm}
.fpage .gloss td:last-child{width:43%}
.fpage td.en:first-child{font-weight:400}
.fpage td.en strong{color:var(--g)}
.fpage td.en .zh{font-family:var(--body);color:var(--soft);font-size:.92em;margin-left:1.2mm}
a.trow.tf{grid-template-columns:11mm 1fr 9mm;padding:1.9mm 0 2mm}
.tf .tn{font:500 7.4pt/1 var(--sans);color:var(--mute);letter-spacing:.1em}
"""

# 第二版的版式：读前页、轻读单元的读后、补充句。只在有这些内容时才加进页面（第一版的项目排出来的 HTML 和第一版一样）
PDF_CSS_V2 = """
/* 读前页：单元的第一页，单独一页。最多的情形（背景 120 字、人物 5 个、词 8 个）也要一页放下 */
section.pre{padding-top:2mm}
.pre .onum{font-size:46pt}
h1.oh .ut{font:500 12.5pt/1.3 var(--en);color:var(--g);margin-left:1.2mm;letter-spacing:0}
.pb{margin-top:6mm}
.og+.pb,.onote+.pb{margin-top:7.5mm}
.ph{font:600 9.6pt/1 var(--sans);color:var(--g);letter-spacing:.2em;border-bottom:.5pt solid var(--gl);
  padding-bottom:1.5mm;margin-bottom:2.2mm;break-after:avoid}
p.pbg{font-size:9.8pt;line-height:1.78;color:var(--ink)}
ul.ppl{list-style:none;margin:0;padding:0;font-size:9.6pt;line-height:1.55}
ul.ppl li{display:grid;grid-template-columns:30mm 1fr;column-gap:2mm;margin:0 0 .7mm;break-inside:avoid}
.pn{font-family:var(--en);font-weight:600;color:var(--g)}
table.pwt{margin:0;font-size:9.6pt;line-height:1.45;break-inside:auto}
table.pwt tr{break-inside:avoid}
table.pwt td{padding:1.05mm 2.6mm 1.05mm 0;border-bottom:.4pt solid var(--rule);vertical-align:baseline}
table.pwt td.pw{font:600 10.3pt/1.35 var(--en);color:var(--g);width:27mm}
table.pwt td.pi,table.pwt td.pp{white-space:nowrap;width:1%}
table.pwt td.pg{padding-right:0}
section.pre.tight{padding-top:0}
.pre.tight .onum{font-size:36pt}
.pre.tight h1.oh{margin:1.4mm 0 .6mm}
.pre.tight .pb{margin-top:4mm}
.pre.tight .og+.pb{margin-top:5mm}
.pre.tight p.pbg{line-height:1.6}
.pre.tight ul.ppl{line-height:1.45}
.pre.tight table.pwt td{padding-top:.6mm;padding-bottom:.6mm}
/* 有读前的精读单元：章首页的单元名不是 h1（PDF 书签只留读前页那一个），样子和 h1.oh 一样 */
div.oh{font:600 15pt/1.3 var(--sans);color:var(--ink);margin:2.5mm 0 1mm}
.open.tight div.oh{margin:1.6mm 0 .6mm}

/* 轻读的读后：各栏连着排，比精读紧凑。句子沿用精讲句的样子（原句里主干加粗、步骤圈号、赭红的卡点框、楷体译文），
   标签排在左边一栏；词条的词典行排在词头那一行 */
.post{font-size:9.4pt;line-height:1.55}
.post h2.sk{margin:5mm 0 3mm;padding-bottom:1.8mm;break-after:avoid}
.post>.pt+h2.sk{margin-top:0}
.post ol.cq li{grid-template-columns:5.6mm 1fr;margin:0 0 1.4mm}
.post ol.cq .qn{font-size:10.4pt;line-height:1.5}
.post article.sent>.pt{break-before:auto}
.post article.sent+article.sent{border-top:.5pt solid var(--rule);padding-top:2.8mm;margin-top:.6mm}
.post h3.st{font-size:10pt;line-height:1.4;padding-left:5.2mm;text-indent:-5.2mm;margin:0 0 1.8mm}
.post h3.st .sn{font-size:13pt;margin-right:.8mm}
.post .orig{font-size:9.9pt;line-height:1.5;margin:0 0 2.2mm;padding-left:3.2mm}
.post .b{position:relative;padding-left:10.2mm;margin:0 0 1.9mm}
.post .b>.tag{position:absolute;left:0;top:.38em;margin:0;font-size:7.2pt;letter-spacing:.04em}
.post .b.alert{padding:1.3mm 2.6mm 1.4mm calc(2.6mm + 10.2mm)}
.post .b.alert>.tag{left:2.6mm;top:calc(1.3mm + .38em)}
.post .core{font-size:9.5pt;line-height:1.5}
.post ol.steps li{margin-bottom:.7mm;padding-left:6.2mm}
.post ol.steps li::before{top:.5mm;width:3.8mm;height:3.8mm;line-height:3.45mm}
.post ol.steps::before{left:1.9mm}
.post .kai{font-size:9.3pt;line-height:1.58;padding-left:0;border-left:0}
.post .entry{padding:2.2mm 0 2.4mm;break-inside:auto}      /* 词条可以跨页（词头不和下文分开），省得整条挪页留空 */
.post .gist{break-before:avoid}
.post h2.sk+.entry{padding-top:0}
.post .hwl{gap:2.2mm}
.post .hw{font-size:11.6pt;flex:none}
.post .hd{flex:1 1 auto;min-width:0;font-size:8.9pt;line-height:1.45;color:var(--ink2)}
.post .lv{top:-.4mm}
.post .gist{margin-top:.6mm}
.post .entry .cite{margin-top:1mm;line-height:1.5}
.post .ctr{font-size:8.9pt;line-height:1.5;margin-top:.3mm}
.post .nt{margin-top:.8mm;font-size:9pt;line-height:1.55}
.post .nt .ntag{line-height:14pt}
p.rq{margin:0 0 1.4mm;break-after:avoid}
p.hints{display:flex;flex-wrap:wrap;align-items:baseline;gap:1mm 1.4mm}
.htag{font:600 7.2pt/1 var(--sans);color:var(--g);letter-spacing:.04em;margin-right:1mm}
.hk{font-family:var(--en);color:var(--g);border:.5pt solid var(--gl);border-radius:.7mm;padding:0 1.3mm .2mm;white-space:nowrap}
.rtx{margin-top:1.4mm}
.rtx p,.rtx li{margin:0 0 .8mm}
.rtx :is(ul,ol){margin:0 0 1.2mm;padding-left:1.25em}
.lans{margin-top:5.6mm;padding-top:2.8mm;border-top:.5pt solid var(--rule);break-inside:avoid}
.lans .wait{margin-bottom:3.2mm}
.lans h2.sk{margin:0 0 2.8mm}
.ah{font:600 8pt/1.2 var(--sans);letter-spacing:.16em;color:var(--g);margin:2.4mm 0 1.3mm}
.lans h2.sk+.ah{margin-top:0}
.lans ol.al{font-size:9pt;line-height:1.55}
.lans ol.al li{grid-template-columns:5.6mm 1fr;margin-bottom:1.8mm}
.lans ol.al .qn{font-size:9.6pt;line-height:1.55}
.lans .qt .cite{margin-top:.8mm;line-height:1.5}
p.rref{font-family:var(--en);font-size:9.3pt;line-height:1.55;padding-left:5.6mm;color:#18262a}
/* 读后排不下两页时整栏再紧一级 */
.post.tight{font-size:9pt;line-height:1.5}
.post.tight h2.sk{margin:3.8mm 0 2.4mm}
.post.tight .orig{font-size:9.5pt;line-height:1.46;margin-bottom:1.8mm}
.post.tight .b{margin-bottom:1.4mm}
.post.tight h3.st{margin-bottom:1.4mm}
.post.tight .core,.post.tight .kai{font-size:9pt;line-height:1.5}
.post.tight article.sent+article.sent{padding-top:2.2mm}
.post.tight .entry{padding:1.7mm 0 1.9mm}
.post.tight .lans{margin-top:4.2mm}

/* 第二版的「怎么用」页：开头的说明长几行，图例收紧一点，保证一页放下 */
.howto.v2 h1.fh{margin-bottom:3mm}
.howto.v2 .fl{font-size:9pt;line-height:1.6;margin-bottom:2.4mm}
.howto.v2 .lgi{margin-bottom:1.3mm}
.howto.v2 .tag{margin-bottom:.6mm}
.howto.v2 .orig{font-size:9.4pt;line-height:1.5;padding-left:3.4mm}
.howto.v2 .alert{padding-top:1.3mm;padding-bottom:1.3mm}
.howto.v2 .alert p,.howto.v2 .exd,.howto.v2 .ex{font-size:9pt}
.howto.v2 .lgm{font-size:7.8pt;line-height:1.4;margin-top:.5mm}
.howto.v2 .cite{line-height:1.5}
.howto.v2 .src{font-size:8pt;line-height:1.5;margin-top:2mm;padding-top:1.8mm}
.howto.v2 .src p{margin-bottom:1.6mm !important}
.howto.v2 .abbr{margin:1mm 0 0}
.ach{font:600 7.4pt/1 var(--sans);letter-spacing:.14em;color:var(--r);background:var(--rt);border-left:1.6pt solid var(--r);
  padding:1mm 1.8mm 1mm 1.6mm;white-space:nowrap;position:relative;top:-.3mm}

/* 精读单元的补充句：和精讲句一样排，句与句接着排 */
.extra article.sent>.pt{break-before:auto}
.extra article.sent+article.sent{margin-top:6mm;padding-top:5mm;border-top:.5pt solid var(--rule)}
"""


# 第三版的版式：句子块的标签小框、断句网格、注一行、回读一行，答案区的「长难句 · 整句和译」。只有第三版的项目才加
PDF_CSS_V3 = """
/* 标题行：句号、标题，右边是标签小框（8pt，细边框）；标记小框用赭红 */
.sth{display:flex;align-items:baseline;gap:2mm;margin:0 0 3.4mm;break-after:avoid}
.sth .st{flex:1 1 auto;min-width:0;margin:0}
.tgs{flex:none;display:flex;gap:1mm;align-items:baseline;position:relative;top:-.4mm}
.tg{font:500 8pt/1 var(--sans);color:var(--g);border:.5pt solid var(--gl);border-radius:.6mm;padding:.6mm 1.1mm .5mm;
  white-space:nowrap;letter-spacing:.02em}
.tg.tgm{color:var(--r);border-color:var(--rl)}
/* 断句表：两栏网格，左 58% 英文 9.5pt，右 42% 楷体 8.5pt、灰一档；缩进一层 1.1em，缩进行左边一条细竖线 */
.cg{margin:0 0 2.4mm;border-top:.6pt solid var(--gl);border-bottom:.6pt solid var(--gl)}
.cg.keep{break-inside:avoid}
.cr{display:grid;grid-template-columns:58% 42%;break-inside:avoid}
.cr+.cr{border-top:.3pt solid var(--rule)}
.ce{font-family:var(--en);font-size:9.5pt;line-height:1.42;color:var(--ink);padding:.7mm 2.4mm .7mm 0;overflow-wrap:anywhere}
.ce b.core{font-weight:600;color:#132020;font-size:inherit;line-height:inherit;font-family:inherit}     /* 不沿用第二版 .core（主干段）的字号和行距 */
.cz{font-family:var(--kai);font-size:8.5pt;line-height:1.5;color:var(--ink2);padding:.85mm 0 .7mm}
.cr.d1 .ce,.cr.d2 .ce{border-left:.5pt solid var(--gl);padding-left:.75em}
.cr.d1 .ce{margin-left:.35em}
.cr.d2 .ce{margin-left:1.45em;position:relative}
.cr.d2 .ce::before{content:"";position:absolute;left:calc(-1.1em - .5pt);top:0;bottom:0;border-left:.5pt solid var(--gl)}
/* 下置：断句占满栏宽，顺读在表下面排成一段，各块用 ／ 隔开，两边各标 ①②③ */
/* 下置的断句每块一行，行距、上下留白比对排收一点（实排：demo 第 2 章读后从 3.4 页收回 3 页） */
.cg.below .cr{grid-template-columns:4.6mm 1fr}
.cg.below .ce{line-height:1.36;padding-top:.3mm;padding-bottom:.3mm}
.cn,.gn{font:400 7.6pt/1 var(--sans);color:var(--soft)}
.cn{padding-top:1.1mm}
p.gz{font-family:var(--kai);font-size:8.5pt;line-height:1.5;color:var(--ink2);padding:.8mm 0 .6mm;
  border-top:.6pt solid var(--gl)}
.gn{margin:0 .5mm 0 .3mm}
/* 注：表下面一行小字 */
p.nts{font-size:8pt;line-height:1.5;color:var(--soft);margin:0 0 1.6mm;break-after:avoid}      /* 排在整句和断句表之间，不和断句表分到两页 */
/* 整句：标题下先印原句，左边一条细竖线，和 md 的引用块一个样子 */
p.oq{font-family:var(--en);font-size:9.5pt;line-height:1.5;color:var(--ink2);margin:0 0 1.8mm;padding-left:2.6mm;
  border-left:1.2pt solid var(--gl);break-after:avoid;break-inside:avoid}
.post.tight p.oq,article.tight p.oq{line-height:1.4;margin-bottom:1.4mm}
.ntl{font:600 7.4pt/1 var(--sans);color:var(--g);letter-spacing:.06em;margin-right:2mm}
p.nts .c{color:var(--g)}
/* 「长难句」栏末尾的回读 */
p.reread{font:7.8pt/1.5 var(--sans);color:var(--soft);letter-spacing:.04em;margin:2.4mm 0 0;break-before:avoid}
/* 轻读：句子块之间的间距照第二版；答案区的「长难句 · 整句和译」 */
.post .sth{margin-bottom:1.8mm}
ol.lt .qt{font-family:var(--kai);color:#2c3535}
ol.lt .qt p+p{margin-top:.6mm}
ol.lt .qt p.ov{font:9.4pt/1.55 var(--en);color:var(--soft);margin-bottom:1mm}
ol.lt .qt p.ov b.core{font-weight:600;color:#132020}
/* 只有一步：不印圈号和竖线，免得和断句表的 ① 撞号 */
ol.steps:has(li:only-child)::before,ol.steps li:only-child::before{display:none}
ol.steps li:only-child{padding-left:0}
/* 答案区排紧（读后排紧时跟着收一档） */
.post.tight .lans p.ov{font-size:9pt;line-height:1.45}
.post.tight .lans ol.al{line-height:1.48}
.post.tight .lans ol.al li{margin-bottom:1mm}
.post.tight p.rref{font-size:9pt;line-height:1.45}
/* 排紧 */
.post.tight .ce{line-height:1.36;padding-top:.5mm;padding-bottom:.5mm}
.post.tight .cz{line-height:1.42;padding-top:.6mm;padding-bottom:.5mm}
.post.tight .cg.below .ce{line-height:1.3;padding-top:.2mm;padding-bottom:.2mm}
.post.tight .sth{margin-bottom:1.4mm}
article.tight .ce{line-height:1.36}
article.tight .sth{margin-bottom:2.6mm}
/* 前言的「句子结构」一页放下 */
.fpage.tags>p{line-height:1.6;margin-bottom:2.4mm}
.fpage.tags table{font-size:8.4pt;line-height:1.42;margin:1.6mm 0 3mm}
.fpage.tags td{padding:.9mm 2.2mm .9mm 0}
/* 「怎么用」页的断句表图例；目录页末尾的缩写表 */
.howto .lgi .cg.below .ce{line-height:1.3;padding-top:.15mm;padding-bottom:.15mm}
.howto .lgi p.gz{line-height:1.45;padding:.6mm 0 .4mm}
.toc .src.tabbr{margin-top:8mm}
.howto h1.fh{margin-bottom:2.6mm}
.howto .fl{margin-bottom:2.2mm}
.howto .lgi .cg{margin:1mm 0 0}
.howto .lgi .tgs{top:0}
"""


def needs_v2_css(chapters):
    return any(c["mode"] == "轻读" or c["preread"] or c["extra"] for c in chapters)


def preface():
    """前言.md：第一个「## 」之前是出处说明和缩写；之后每个「## 标题」是合订本前部的一页。"""
    p = P.docs / "前言.md"
    parts = re.split(r"^## (.+)$", p.read_text(encoding="utf-8") if p.exists() else "", flags=re.M)
    return parts[0], [(t.strip(), b) for t, b in zip(parts[1::2], parts[2::2])]


def by_mode(chapters):
    """(轻读单元, 精读单元)，各按原顺序。"""
    return [c for c in chapters if c["mode"] == "轻读"], [c for c in chapters if c["mode"] == "精读"]


def scope_line(chapters):
    """封面副标题，按单元里有的栏目写：有读前加「读前」，有轻读单元加「理解」「复述」，有精读单元加「语法」，
    有赏析、写作的精读单元才加「赏析」「写作」。全是没有读前的精读单元时就是第一版的「句子 · 词汇 · 语法 · 赏析 · 写作」。"""
    light, jing = by_mode(chapters)
    parts = ((["读前"] if any(c["preread"] for c in chapters) else []) + (["理解"] if light else []) + ["句子", "词汇"]
             + (["语法"] if jing else []) + (["赏析"] if any(c["has_essay"] for c in jing) else [])
             + (["写作"] if any(has_writing(c) for c in jing) else []) + (["复述"] if light else []))
    return " · ".join(parts)


def cover_foot(chapters):
    """封面底部的数量。语法专题、写作、自测只数精读单元；有轻读单元时句子叫「长难句」，另数理解题。"""
    light, jing = by_mode(chapters)
    total_s = sum(len(c["sentences"]) for c in chapters)
    parts = [f"{'长难句' if light else '精讲句'} {total_s} 句", f"词条 {sum(len(c['usage']) for c in chapters)} 条"]
    if light:
        parts.append(f"理解 {sum(len(c['comprehension']['questions']) for c in light)} 题")
    if jing:
        total_wr = sum(has_writing(c) for c in jing)
        parts += ([f"语法专题 {len(jing)} 个"] + ([f"写作 {total_wr} 节"] if total_wr else [])
                  + [f"自测 {sum(len(c['quiz']) for c in jing)} 题"])
    extra = sum(len(c["extra"]) for c in chapters)
    return " · ".join(parts + ([f"{extra_name()} {extra} 句"] if extra else []))


def toc_small(c, mixed):
    """目录里单元名下面的一行小字。轻读：理解、长难句、词条、复述（第三版长难句在前）；精读：第一版的写法，第三版把精讲写成长难句。
    两种模式混用时前面标模式。"""
    if c["mode"] == "轻读":
        parts = [f"理解 {len(c['comprehension']['questions'])} 题", f"长难句 {len(c['sentences'])} 句",
                 f"词条 {len(c['usage'])} 条", f"复述 {len((c['retell'] or {}).get('prompts', []))} 题"]
        if P.format >= 3:           # 第三版的读后先排长难句
            parts[:2] = parts[1::-1]
        parts += [f"{extra_name()} {len(c['extra'])} 句"] if c["extra"] else []
    else:
        parts = ([f"{'长难句' if P.format >= 3 else '精讲'} {len(c['sentences'])} 句", f"词条 {len(c['usage'])} 条"]
                 + ([f"赏析 {len(essay_points(c['essay'])[1])} 点"] if c["has_essay"] else [])
                 + (["写作 1 节"] if has_writing(c) else []) + ([f"{extra_name()} {len(c['extra'])} 句"] if c["extra"] else [])
                 + [f"自测 {len(c['quiz'])} 题"])
    return (f"{c['mode']} · " if mixed else "") + " · ".join(parts)


def toc_title(c):
    """目录里单元名后面的题目：精读写语法专题，轻读写 设置.json 里的单元标题（没写就空着）。"""
    if c["mode"] == "精读":
        return c["grammar_title"]
    return "" if P.single else dict(P.units).get(c["n"], "")      # 只有一篇时单元名就是篇名，不再重复


def nums_text(chapters):
    """「第 1、3 章」。"""
    return "第 " + "、".join(str(c["n"]) for c in chapters) + f" {P.unit}"


def cover_meta(scope):
    """封面上作者和范围两行；没写作者、只有一篇（没有范围行）时相应省掉。"""
    rows = ([f'<span class="en">{esc(P.author)}</span> 原著'] if P.author else []) + ([scope] if scope else [])
    return f'<div class="meta">{"<br>".join(rows)}</div>' if rows else ""


def cite_sample(chapters):
    """「怎么用」页的引文样例：从词条引的原文里挑，要有译文、至少三个词；优先挑完整的句子（大写开头、句末标点收尾），取最短的。
    返回 (引文, 标签, 译文) 或 None。"""
    cands = [(q, tag, tr) for c in chapters for u in c["usage"] for q, tag, tr in zip(u["quotes"], u["tags"], u["trans"])
             if tr and len(q.split()) >= 3]
    full = [x for x in cands if re.match(r"[A-Z“‘]", x[0]) and re.search(r"[.!?][’”]?$", x[0])]
    return min(full or cands, key=lambda x: len(x[0])) if cands else None


def howto_lead(chapters):
    """「怎么用」页开头的说明。全是没有读前的精读单元时是第一版的原话；否则先说读前 → 原文 → 读后（精读单元是讲解），
    再按模式说读后、讲解各有什么。"""
    U = P.unit
    light, jing = by_mode(chapters)
    order = "、".join(["首页" if P.single else f"{U}首页", "长难句" if P.format >= 3 else "精讲句", "词的用法", "语法"]
                     + ([jing[0]["essay_label"]] if any(c["has_essay"] for c in jing) else [])
                     + (["写作"] if any(has_writing(c) for c in jing) else [])
                     + ([extra_name()] if any(c["extra"] for c in jing) else []))
    pre = [c for c in chapters if c["preread"]]
    if not pre and not light:
        lead = (f"顺序是：{order}、自测和答案。首页把全{U}分成三次学，" if P.single
                else f"每{U}顺序相同：{order}、自测和答案。{U}首页把一{U}分成三次学，")
        return lead + "每次约半小时，学完一项在小方框里打勾。"
    one = P.single or len(chapters) == 1
    mixed = bool(light and jing)
    after = "读后（精读的" + U + "是讲解）" if mixed else "读后" if light else "讲解"
    who = ("" if one else f"每{U}") if len(pre) == len(chapters) else f"{nums_text(pre)}"
    out = [f"{who}先看读前一页，再读原文，读完看{after}。"] if pre else []
    if light and P.format >= 3:      # 第三版：读前 → 原文 → 长难句 → 理解 → 词 → 复述；卡句另起一页
        out.append((f"{nums_text(light)}是轻读，读后" if mixed else "读后")
                   + "依次是长难句、理解、词的用法、复述，答案在最后，精讲句的译也在那里。")
    elif light:
        secs = "、".join(["理解", "长难句", "词的用法", "复述"] + ([EXTRA] if any(c["extra"] for c in light) else []))
        out.append((f"{nums_text(light)}是轻读，读后" if mixed else "读后") + f"依次是{secs}，答案在最后。")
    if jing:
        head = f"{nums_text(jing)}是精读，讲解" if mixed else "讲解"
        out.append(f"{head}依次是{order}、自测和答案；" + ("首页把全" + U if P.single else f"{U}首页把一{U}")
                   + "分成三次学，每次约半小时，学完一项在小方框里打勾。")
    if P.format >= 3:      # 回读的话前言开头的出处说明里有了（写法.md 要求写），这里就不再重复
        out.append(("" if REREAD in preface()[0] else REREAD) + f"读的时候卡住的句子记进 卡句.txt，讲在{U}末的「{STUCK}」里；"
                   f"各{U}的长难句按结构分组，收在难句本里；PDF 不印试，先在难句本里自己拆。")
    return "".join(out)


def front_html(chapters, matches, pages=None):
    """合订本前部：封面、怎么用、目录、前言各页。pages = 目录里各行的页码（前言各页在前，各章在后）。
    全是没有读前、没有补充句的精读单元（第一版的项目）时，排出来和第一版一样；否则按各单元的模式写。"""
    U = P.unit
    light, jing = by_mode(chapters)
    if P.single:
        scope = ""
    elif len(chapters) > 1 and [c["n"] for c in chapters] == unit_nums():
        scope = f"全{cn_num(len(chapters))}{U}"
    else:
        scope = "第 " + "、".join(str(c["n"]) for c in chapters) + f" {U}"
    cover = (f'<section class="cover"><div class="ck">英语学习讲义</div><h1>{esc(P.title)}</h1>'
             f'<div class="sub">{scope_line(chapters)}</div><div class="rule"></div>'
             f'{cover_meta(scope)}'
             f'<div class="foot">{cover_foot(chapters)}</div></section>')
    # 图例：取最短的一句已高亮的原句做样例
    cands = [(len(s["quote"]), c["n"], s, m) for c in chapters for s, m in zip(c["sentences"], matches[c["n"]]) if m[0]]
    sample = ""
    if cands:
        _, cn, s, m = min(cands, key=lambda x: x[0])
        sample = (f'<div class="lgi"><div class="tag">原句</div><p class="orig hl">{quote_html(s["quote"], m[0])}</p>'
                  f'<p class="lgm">深色加粗的词连起来就是主干，浅色是修饰和补充（例句取自{"" if P.single else unit_name(cn)}句 {s["i"]}）。'
                  f'主干与原句对不上时不加粗，全句按普通颜色排。</p></div>')
    if P.format >= 3:
        sample = grid_legend(chapters)
    pre, fsecs = preface()
    src, abbr = [], ""
    for line in [x.strip() for x in pre.splitlines() if x.strip()]:
        if line.startswith("缩写：") and "　" in line:
            pieces = line[3:].split("　")
            tail = ""
            if "。" in pieces[-1]:
                pieces[-1], tail = pieces[-1].split("。", 1)
            cells = []
            for p in pieces:
                k, _, v = p.partition(" ")
                cells.append(f'<span><i class="pos">{esc(k)}</i>{esc(v)}</span>')
            if tail.strip():       # 「音标用英式。」这类尾句排进缩写表的空格里，省一行
                cells.append(f'<span class="abt">{pinline(tail.strip())}</span>')
            src.append(f'<div class="fsub">缩写</div><div class="abbr">{"".join(cells)}</div>')
            abbr = src[-1]
        else:
            src.append(f'<p style="margin-bottom:2.4mm">{pinline(line)}</p>')
    book = U != "篇"            # 整本书分章、分部分；「篇」是单篇文章或短篇
    review = any(P.review.match(q) for c in jing for q in c["quiz"])
    levels = any(u.get("level") for c in chapters for u in c["usage"])
    # 词典行样例：从讲义的词条里取，优先带 [U]/[C] 的，其次任何带音标的；词典行不以词头开头时补上词头
    dicts = [(u["head"], u["dict"]) for c in chapters for u in c["usage"] if "/" in u.get("dict", "")]
    pick = next((d for d in dicts if "[" in d[1]), dicts[0] if dicts else None)
    sample_dict = (pick[1] if not pick[1].lstrip().startswith("/") else f"{pick[0]} {pick[1]}") if pick else ""
    countable = "，[U] [C] 标可数性" if "[" in sample_dict else ""
    word = ((f'<div class="lgi"><div class="lgw"><p class="dict" style="margin:0">{dict_html(sample_dict)}</p>'
            + (f'<span class="lgc">{level_html("会用")}{level_html("认得")}</span>' if levels else "") + '</div>'
            f'<p class="lgm">两条斜线之间是英式音标；斜体是词性{countable}。'
            + ("词条右上角的小标签：会用的要练到自己能造句，认得的读懂就行。" if levels else "") + '</p></div>') if sample_dict else "")
    chips = (f'<div class="lgi lgr"><span class="lgc"><span class="rv">回头看 · 第 {unit_nums()[0]} {U}</span></span>'
             f'<p class="lgm">自测的最后两题回头考前面{"章节" if U == "章" else "几" + U}讲过的内容。</p></div>' if review else "")
    cs = cite_sample(chapters)
    cite = (f'<div class="lgi"><p class="cite" style="margin-top:0"><span class="ctag">{cs[1]}</span><em class="q">{esc(cs[0])}</em>'
            f'{tr_html(cs[2])}</p>'
            f'<p class="lgm">赭红细线加斜体是{esc(P.genre)}原文，' + ("与书里逐字一致" if book else "逐字照录")
            + '；紧跟在下面的楷体小字是译文。</p></div>') if cs else ""
    # 自造例句的图例：有精读单元时用「举一反三」（精讲句里的栏目）举例；全是轻读时用词条里的「例」
    examples = (f'<div class="lgi"><div class="tag">举一反三</div><div class="exg" style="margin-top:0"><p class="exd">上面一行是规则或对比：</p>'
                f'<p class="ex">Indented lines in serif type are examples.</p></div>'
                f'<p class="lgm">缩进、带小圆点的英文是自造例句，不是{"书中" if book else ""}原文。</p></div>' if jing else
                f'<div class="lgi"><div class="nt" style="margin:0"><span class="ntag">例</span><div class="nv">'
                f'<p class="ex">Indented lines in serif type are examples.</p></div></div>'
                f'<p class="lgm">带小圆点的英文是自造例句，不是{"书中" if book else ""}原文。</p></div>')
    v2 = " v2" if light or any(c["preread"] for c in chapters) else ""      # 第二版的说明长几行，图例收紧
    crux = (f'<div class="lgi"><div class="b alert" style="margin:0"><div class="tag">卡点</div><p>每句只写一个最容易错的地方。</p></div>'
            f'<p class="lgm">赭红色的框是提醒，先看它再对照原句。</p></div>' if not v2 else
            f'<div class="lgi lgr"><span class="lgc"><span class="ach">卡点</span></span>'
            f'<p class="lgm">赭红色的框是提醒：每句只写一个最容易错的地方，先看它再对照原句。</p></div>')
    moved = P.format >= 3 and bool(abbr)      # 第三版的图例高几行：缩写表挪到目录页末尾，「怎么用」页一页放下
    howto = (f'<section class="front howto{v2}"><h1 class="fh">怎么用这本讲义</h1>'
             f'<p class="fl">{howto_lead(chapters)}</p>{sample}{crux}'
             f'{examples}{cite}{word}{chips}<div class="src">{"".join(x for x in src if not (moved and x == abbr))}</div></section>')
    pg = lambda i: pages[i] if pages and i < len(pages) else ""
    frows = "".join(f'<a class="trow tf" href="#front{k}"><span class="tn"></span><span class="tt"><b>{pinline(t)}</b></span>'
                    f'<span class="tp">{pg(k - 1)}</span></a>' for k, (t, _) in enumerate(fsecs, 1))
    mixed = bool(light and jing)
    rows = "".join(
        f'<a class="trow" href="#ch{c["n"]}"><span class="tn">{"" if P.single else "%02d" % c["n"]}</span><span class="tt"><b>{esc(unit_name(c["n"]))}'
        f'<span>{pinline(toc_title(c))}</span></b><small>{toc_small(c, mixed)}</small></span>'
        f'<span class="tp">{pg(len(fsecs) + i)}</span></a>'
        for i, c in enumerate(chapters))
    toc = (f'<nav class="front toc"><h1 class="fh">目录</h1>{frows}{rows}'
           + (f'<div class="src tabbr">{abbr}</div>' if moved else "") + '</nav>')
    tags = lambda t: " tags" if P.format >= 3 and t.strip() == "句子结构" else ""      # 第三版：句子结构表排紧，一页放下
    fpages = "".join(f'<section class="front fpage{tags(t)}" id="front{k}"><h1 class="fh">{pinline(t)}</h1>{pblocks(b, "front")}</section>'
                     for k, (t, b) in enumerate(fsecs, 1))
    return cover + howto + toc + fpages


def grid_legend(chapters):
    """第三版「怎么用」页的图例：取行数最少的一个长难句（至少 3 行），排出标签小框和断句表，下面一行说明。"""
    cands = [(len(s["chunks"]), len(s["quote"]), c["n"], s) for c in chapters for s in c["sentences"]
             if len(s["chunks"]) >= 3 and len(s["chunks"]) == len(s["gloss"])]
    if not cands:
        return ""
    _, _, cn, s = min(cands, key=lambda x: x[:2])
    where = ("" if P.single else unit_name(cn)) + f"句 {s['i']}"
    below = v3_pdf()["chunk_layout"] == "下置"
    return (f'<div class="lgi"><div class="lgw">{tag_boxes(s)}</div>{grid_html(s)}'
            f'<p class="lgm">{"上面" if below else "左栏"}是原句按意群断开，缩进的是修饰，细竖线标出挂在哪一层；'
            f'粗体是主语和谓语，连起来是骨架。'
            + ("下面是顺读，编号对应各块。" if below else "右栏顺着英文往下读。")
            + f'小框是结构标签，见前言「句子结构」（例句取自{where}）。</p></div>')


def single_cover(ch):
    return (f'<section class="cover"><div class="ck">英语学习讲义</div><h1>{esc(P.title)}</h1>'
            f'<div class="sub">{esc(unit_name(ch["n"]))}</div><div class="rule"></div>'
            f'{cover_meta(scope_line([ch]))}</section>')


def page_html(chapters, matches, pages=None, tight=None, sect=None, unkeep=None, book=None):
    """book：排成合订本（封面、怎么用、目录、前言各页）；否则是分册，只有一页封面。默认多于一个单元就是合订本。"""
    book = len(chapters) > 1 if book is None else book
    front = front_html(chapters, matches, pages) if book else single_cover(chapters[0])
    body = "".join(chapter_pdf_html(c, matches[c["n"]], (tight or {}).get(c["n"], {}),
                                    (sect or {}).get(c["n"], set()), (unkeep or {}).get(c["n"], set())) for c in chapters)
    if not FONT_DIR:
        FONT_DIR.append(font_dir())
    return (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{esc(P.title)} 讲解</title>'
            f"<style>{pdf_font_css(FONT_DIR[0])}{PDF_CSS}{PDF_CSS_V2 if needs_v2_css(chapters) else ''}"
            f"{PDF_CSS_V3 if any(c.get('format') == 3 for c in chapters) else ''}{font_override_css()}\n{page_css(chapters)}</style>"
            f"<body>{front}{body}</body></html>")


def pdf_words(pdf):
    """读回 PDF 每页的文字：[{head: 页眉文字, text: 正文文字, fill: 正文排到页面多深}]，文字都去掉空白直接连起来。
    有 pdftotext 用 pdftotext -bbox；没有就用系统 swift + PDFKit（swift_words）。都不行返回 None。"""
    tool = shutil.which("pdftotext") or next((t for t in ("/opt/homebrew/bin/pdftotext", "/usr/local/bin/pdftotext")
                                              if Path(t).exists()), None)
    if not tool:
        return swift_words(pdf)
    r = subprocess.run([tool, "-bbox", str(pdf), "-"], capture_output=True, text=True)
    if r.returncode:
        return swift_words(pdf)
    pages = []
    for h, body in re.findall(r'<page width="[\d.]+" height="([\d.]+)">(.*?)</page>', r.stdout, re.S):
        h = float(h)
        ws = [(float(a), float(b), html.unescape(t)) for a, b, t in
              re.findall(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">(.*?)</word>', body)]
        # 坐标是行框；按行中线分页眉（上边距里）、正文、页脚（下边距里）
        head = "".join(t for a, b, t in ws if (a + b) / 2 < 42)
        main = [(a, b, t) for a, b, t in ws if 42 <= (a + b) / 2 <= h - 40]
        fill = (max(b for a, b, t in main) - 45) / (h - 90) if main else 0.0
        pages.append({"head": head, "text": "".join(t for a, b, t in main), "fill": fill})
    return pages


# PDFKit 版的 pdftotext -bbox：按行取文字和外框（PDFPage.characterBounds 和 page.string 的下标会错位，不用），
# 纵坐标从页顶量；阈值和上面一样：行中线 < 42pt 是页眉，> 页高 − 40pt 是页脚。
# 正文按行聚类（纵向重叠过半算一行）、行内从左到右，近似 pdftotext 的阅读顺序。
SWIFT_WORDS = r"""
import Foundation
import PDFKit
guard CommandLine.arguments.count > 1, let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1])) else { exit(1) }
typealias Frag = (top: CGFloat, bottom: CGFloat, x: CGFloat, text: String)
var pages: [[String: Any]] = []
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.bounds(for: .mediaBox)
    var head: [Frag] = [], main: [Frag] = []
    for sel in page.selection(for: box)?.selectionsByLine() ?? [] {
        let t = (sel.string ?? "").components(separatedBy: .whitespacesAndNewlines).joined()
        if t.isEmpty { continue }
        let b = sel.bounds(for: page)
        let f: Frag = (box.maxY - b.maxY, box.maxY - b.minY, b.minX, t)
        let mid = (f.top + f.bottom) / 2
        if mid < 42 { head.append(f) } else if mid <= box.height - 40 { main.append(f) }
    }
    main.sort { $0.top < $1.top }
    var lines: [[Frag]] = []
    for f in main {
        if let last = lines.last {
            let top = last.map { $0.top }.min()!, bottom = last.map { $0.bottom }.max()!
            if min(bottom, f.bottom) - max(top, f.top) > 0.5 * min(bottom - top, f.bottom - f.top) {
                lines[lines.count - 1].append(f)
                continue
            }
        }
        lines.append([f])
    }
    let text = lines.map { $0.sorted { $0.x < $1.x }.map { $0.text }.joined() }.joined()
    let low = main.map { $0.bottom }.max()
    pages.append(["head": head.sorted { $0.x < $1.x }.map { $0.text }.joined(), "text": text,
                  "fill": low.map { Double(($0 - 45) / (box.height - 90)) } ?? 0.0])
}
FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: pages))
"""


def swift_cmd(source, stem):
    """跑一段 swift 的命令（参数另加）：第一次编译成小程序缓存在临时目录，之后直接跑；编译不了就解释执行（慢一些）；
    没有 swift 返回 None。"""
    swiftc, swift = shutil.which("swiftc") or "/usr/bin/swiftc", shutil.which("swift") or "/usr/bin/swift"
    cache = Path(tempfile.gettempdir()) / f"english-reader-{stem}-{hashlib.sha1(source.encode()).hexdigest()[:12]}"
    src, exe = cache / f"{stem}.swift", cache / stem
    if not exe.exists():
        cache.mkdir(parents=True, exist_ok=True)
        src.write_text(source, encoding="utf-8")
        if Path(swiftc).exists():
            tmp = cache / f"{stem}.{os.getpid()}"      # 编好再改名，几个进程同时编也不会读到半个文件
            r = subprocess.run([swiftc, "-O", str(src), "-o", str(tmp)], capture_output=True, text=True)
            if r.returncode == 0:
                tmp.replace(exe)
    if exe.exists():
        return [str(exe)]
    if Path(swift).exists():
        return [swift, str(src)]
    return None


def swift_words(pdf):
    """pdf_words 的后备：swift + PDFKit（Xcode 命令行工具）。第一次编译成小程序缓存在临时目录（约 2 秒），之后每次约 1 秒。"""
    cmd = swift_cmd(SWIFT_WORDS, "pdfwords")
    r = subprocess.run(cmd + [str(pdf)], capture_output=True, text=True) if cmd else None
    if r and r.returncode == 0:
        try:
            return json.loads(r.stdout)
        except ValueError:
            pass
    if not WARNED:
        WARNED.append(True)
        print("  ! 读不出 PDF 的文字（没有 pdftotext，swift 也不可用）：不会自动排紧，目录也没有页码。"
              "装 Xcode 命令行工具（xcode-select --install）就有 swift")
    return None


WARNED = []   # 读不出文字的提示只打印一次


# ---------- 本机字体 ----------
# macOS：swift 调 CoreText 列出字体 family（只用 CoreText，不碰 AppKit，不会变成带界面的程序），
# 顺便看能不能排简体中文（有没有「们这说」的字形）。没有 swift 再用 system_profiler（慢）；Linux 用 fc-list。
# 列表不全（如 Iowan Old Style 不在列表里，却能用），所以查某个名字有没有时，swift 带上名字参数，按 CoreText 的匹配算
# （和 Chrome 一样认本地化名，如「宋体-简」）。
SWIFT_FONTS = r"""
import Foundation
import CoreText
let asked = Array(CommandLine.arguments.dropFirst())
if !asked.isEmpty {
    var have: [String: Bool] = [:]
    for name in asked {
        let desc = CTFontDescriptorCreateWithAttributes([kCTFontFamilyNameAttribute: name] as CFDictionary)
        have[name] = CTFontDescriptorCreateMatchingFontDescriptor(desc, nil) != nil
    }
    let data = try! JSONSerialization.data(withJSONObject: have)
    print(String(data: data, encoding: .utf8)!)
    exit(0)
}
let probe = Array("们这说".utf16)
var out: [[String: Any]] = []
for name in (CTFontManagerCopyAvailableFontFamilyNames() as? [String]) ?? [] {
    if name.hasPrefix(".") { continue }
    let desc = CTFontDescriptorCreateWithAttributes([kCTFontFamilyNameAttribute: name] as CFDictionary)
    let font = CTFontCreateWithFontDescriptor(desc, 12, nil)
    var glyphs = [CGGlyph](repeating: 0, count: probe.count)
    let zh = CTFontGetGlyphsForCharacters(font, probe, &glyphs, probe.count)
    let local = (CTFontCopyLocalizedName(font, kCTFontFamilyNameKey, nil) as String?) ?? name
    out.append(["family": name, "local": local, "zh": zh])
}
let data = try! JSONSerialization.data(withJSONObject: out)
print(String(data: data, encoding: .utf8)!)
"""
SYSTEM_FONTS = {}      # {slow: 结果}，每次运行只取一次


def system_fonts(slow=True):
    """本机装的字体：{"how": 取法, "fams": [(family, 能排简体中文：True/False/None 不知道)], "names": 小写的名字（含本地化名）}。
    取不到是 None。slow=False 时不用 system_profiler（要十几秒；排 PDF 时不值得等）。"""
    if slow not in SYSTEM_FONTS:
        SYSTEM_FONTS[slow] = list_fonts(slow)
    return SYSTEM_FONTS[slow]


def run_quiet(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def list_fonts(slow):
    fams, names = {}, set()

    def done(how):
        return {"how": how, "fams": sorted(fams.items(), key=lambda x: x[0].lower()), "names": names} if fams else None

    if sys.platform == "darwin":
        cmd = swift_cmd(SWIFT_FONTS, "fontlist")
        out = run_quiet(cmd) if cmd else None
        try:
            rows = json.loads(out) if out else None
        except ValueError:
            rows = None
        if rows:
            for r in rows:
                fams[r["family"]] = bool(r.get("zh"))
                names.update({r["family"].lower(), str(r.get("local") or "").lower()} - {""})
            return done("swift + CoreText")
        if slow and shutil.which("system_profiler"):
            print("没有 swift，改用 system_profiler 取字体列表，要十几秒……")
            out = run_quiet(["system_profiler", "SPFontsDataType", "-json"], timeout=180)
            try:
                items = json.loads(out)["SPFontsDataType"] if out else []
            except (ValueError, KeyError, TypeError):
                items = []
            for item in items:
                for face in item.get("typefaces") or []:
                    if face.get("family") and not face["family"].startswith("."):
                        fams[face["family"]] = None
                        names.add(face["family"].lower())
            return done("system_profiler")
    fc = shutil.which("fc-list")
    if fc:
        out, zh = run_quiet([fc, ":", "family"]), run_quiet([fc, ":lang=zh-cn", "family"]) or ""
        zh_names = {n.strip().lower() for line in zh.splitlines() for n in line.split(",")}
        for line in (out or "").splitlines():
            alias = [n.strip() for n in line.split(",") if n.strip()]
            if alias and not alias[0].startswith("."):
                fams[alias[0]] = alias[0].lower() in zh_names
                names.update(a.lower() for a in alias)
        return done("fc-list")
    return None


# 按名字大致分组的关键字（小写）。能判断能不能排简体中文时，中文的三组只收能排的
FONT_GROUPS = (      # 楷体先看：宋刻本秀楷这类名字里也有 song
    ("楷体", ("kai", "楷")),
    ("宋体", ("song", "宋", "ming", "明", "serif cjk", "serif sc", "simsun", "fangsong", "仿宋", "mincho")),
    ("黑体", ("hei", "黑", "sans cjk", "sans sc", "pingfang", "苹方", "yahei", "雅黑", "hiragino sans", "source han sans",
            "思源", "wenquanyi", "文泉驿", "dengxian", "等线")),
)
EN_SANS = ("sans", "helvetica", "arial", "verdana", "tahoma", "segoe", "futura", "avenir", "gill", "optima", "calibri",
           "frutiger", "myriad", "lucida grande", "inter", "roboto", "ubuntu", "cantarell", "trebuchet", "franklin",
           "univers", "seravek", "geneva", "grotesk")
EN_SERIF = ("serif", "times", "georgia", "garamond", "palatino", "baskerville", "iowan", "charter", "caslon", "bodoni",
            "didot", "cambria", "antiqua", "minion", "century", "hoefler", "plantin", "sabon", "bembo", "stix", "libertin",
            "crimson", "charis", "gentium", "constantia", "rockwell", "cochin", "athelas", "superclarendon",
            "new york", "bookman", "schoolbook", "literata", "merriweather", "lora")
FONT_GROUP_NAMES = ("宋体", "楷体", "黑体", "其他中文", "英文衬线", "英文无衬线", "其他")


def font_group(family, zh):
    """按名字大致分组。zh：能不能排简体中文（None 不知道，只看名字）。"""
    low = family.lower()
    if zh is not False:
        for group, keys in FONT_GROUPS:
            if any(k in low for k in keys):
                return group
        if zh:
            return "其他中文"
    if any(k in low for k in EN_SANS):
        return "英文无衬线"
    if any(k in low for k in EN_SERIF):
        return "英文衬线"
    return "其他"


def font_lost(names):
    """这些字体名里本机没有的（字体文件、通用族名、字体目录里的书宋书楷不查）。不知道本机有没有就当作有。
    macOS 有 swift 时按 CoreText 的匹配；否则看 system_fonts() 的名字（排 PDF 时不用慢的 system_profiler）。"""
    ask = sorted({n for n in names if not (n.lower().endswith(FONT_FILES) or n in FONT_OWN or n.lower() in FONT_GENERIC)})
    if not ask:
        return set()
    if sys.platform == "darwin":
        cmd = swift_cmd(SWIFT_FONTS, "fontlist")
        out = run_quiet(cmd + ask) if cmd else None
        try:
            have = json.loads(out) if out else None
        except ValueError:
            have = None
        if isinstance(have, dict):
            return {n for n in ask if have.get(n) is False}
    fams = system_fonts(slow=False)
    return {n for n in ask if n.lower() not in fams["names"]} if fams else set()


def cmd_fonts(args):
    """列出本机字体，按名字大致分组；有项目时再列这个项目四种字体各用什么。"""
    if args:
        sys.exit("fonts 只接项目目录")
    fams = system_fonts()
    if fams:
        print(f"本机字体 {len(fams['fams'])} 个（{fams['how']} 取的，分组按名字猜）：")
        groups = {g: [] for g in FONT_GROUP_NAMES}
        for family, zh in fams["fams"]:
            groups[font_group(family, zh)].append(family)
        for g in FONT_GROUP_NAMES:      # 宋体、楷体、黑体……的顺序
            if groups[g]:
                print(f"{g}（{len(groups[g])}）")
                for k in range(0, len(groups[g]), 6):
                    print("  " + "、".join(groups[g][k:k + 6]))
        if fams["how"] == "swift + CoreText":
            print("列表不全：有的系统字体不列出来也能用（如 Iowan Old Style）。项目一栏的「!」按实际匹配算，以它为准。")
    else:
        print("取不到本机的字体列表（macOS 要 swift，装 Xcode 命令行工具就有；Linux 要 fc-list）。"
              "字体名按系统里显示的 family 名手写进 设置.json 的 fonts。")
    if P.root is None:
        return 0
    spec = font_spec(P.fonts)
    print(f"\n{P.root.name} 的 PDF 字体：")
    now = font_roles_now()
    lost = font_lost([n for _, names, _ in now for n in names])
    for label, names, mine in now:
        print(f"  {label}  {', '.join(('!' if n in lost else '') + n for n in names)}" + ("" if mine else "  （默认）"))
    if spec["dir"]:
        print(f"  目录  {project_path(spec['dir'])}（放 BookSong 书宋、BookKai 书楷；宋体、楷体没写时用）")
    for msg in spec["problems"]:
        print(f"  ! {msg}")
    if lost:
        print("标「!」的本机没有，排出来会换成别的字体。")
    return 0


def page_key(s):
    """读回的页面文字去掉了空白，页上印的字也这样比。"""
    return re.sub(r"\s+", "", s)


def unit_pages(pages, chapters):
    """各单元的首页和章首页的页码（1 起）：{章号: (首页, 章首页)}。
    有读前的单元，首页是读前页，靠页上固定的一行 PRE_MARK 认；没有读前的精读单元，首页就是章首页，靠「本章地图」认
    （和第一版一样）。精读单元的章首页是首页之后第一个印着「本章地图」的页；轻读单元没有章首页，记 None。
    按单元顺序往后找，每个单元从上一个单元之后找起；某个单元找不到，它和后面的单元都不记。"""
    out, k = {}, 0
    if not pages:
        return out
    pre, mp = page_key(PRE_MARK), page_key(map_title())
    for ch in chapters:
        key = pre if ch["preread"] or ch["mode"] == "轻读" else mp
        first = next((i for i in range(k, len(pages)) if key in pages[i]["text"]), None)
        if first is None:
            break
        opener = None if ch["mode"] == "轻读" else first if key == mp else \
            next((i for i in range(first + 1, len(pages)) if mp in pages[i]["text"]), None)
        if ch["mode"] == "精读" and opener is None:
            break
        out[ch["n"]] = (first + 1, None if opener is None else opener + 1)
        k = (first if opener is None else opener) + 1
    return out


def toc_pages(pages, chapters, titles):
    """目录里各行的页码：先是前言各页（页首就是该页标题），再是各单元的首页。对不上返回 None。"""
    found_units = unit_pages(pages, chapters)
    if len(found_units) != len(chapters):
        return None
    opens = [found_units[c["n"]][0] for c in chapters]
    found = []
    for t in titles:
        key = re.sub(r"\s+|[`*]", "", t)
        hit = next((i for i in range(1, opens[0]) if pages[i - 1]["text"].startswith(key)), None)
        if hit is None:
            return None
        found.append(hit)
    return found + opens


def loose_sentences(pages, chapters):
    """找出最后一页只剩几行的精讲句（下一遍排紧一点）。只看精读单元。返回 {章号: {句号…}}。"""
    up = unit_pages(pages, chapters)
    found = {}
    for ch in chapters:
        if ch["mode"] != "精读" or ch["n"] not in up:
            continue
        starts, k = [], up[ch["n"]][1]     # 章首页是 1 起的页码，正好是章首页下一页的下标
        for s in ch["sentences"]:
            t = re.sub(r"\s+|[`*]", "", s["title"])
            while k < len(pages) and t not in pages[k]["text"]:
                k += 1
            starts.append(k)
            k += 1
        end = next((i for i in range(k, len(pages)) if "词的用法" in pages[i]["head"]), None)
        if k > len(pages) or end is None:
            continue
        found[ch["n"]] = {s["i"] for s, a, b in zip(ch["sentences"], starts, starts[1:] + [end])
                          if b - a > 1 and pages[b - 1]["fill"] < 0.34}
    return found


def sec_labels(ch):
    """要检查排紧的栏目和它们的页眉右边的字。轻读单元只有读后一栏。"""
    if ch["mode"] == "轻读":      # 第三版的卡句另起一页（页眉「卡句」），尾页只剩几行也排紧
        return {"post": "读后", **({"stuck": STUCK} if ch.get("format") == 3 and ch["extra"] else {})}
    return {"words": "词的用法", "gram": "语法", "essay": ch["essay_label"], "write": "写作", "ans": "答案"}


def sect_name(ch, key):
    return {"open": f"{P.unit}首页", "pre": PRE, **sec_labels(ch)}[key]


def over_lines(pages, idx):
    """本该一页的栏目多出大约几行：后几页用掉的高度减去前一页底下还空着的高度，按 10pt × 1.66 的行距折算。
    （A5 正文区高 505pt、从 51pt 起；整块挪过去的内容，前一页的空白也算可用。）"""
    if len(idx) < 2:
        return 0
    used = sum(pages[i]["fill"] * 505 - 6 for i in idx[1:])
    free = (1 - pages[idx[-2]]["fill"]) * 505
    return max(1, int(-(-(used - free) // 16.6)))     # 向上取整


def section_pages(pages, n, label):
    """某单元某栏目的各页（下标）：按页眉认，页眉文字去掉空白后是「书名·第N章」+ 栏目名。"""
    head = re.sub(r"\s+", "", running_head(n) + label)
    return [i for i, p in enumerate(pages) if p["head"] == head]


def post_split(pages, idx):
    """轻读的读后（idx：页眉是「读后」的各页下标）：返回 (不含答案的页数, 连答案一共的页数, 答案是否另起一页)。
    答案块从「做完再看」「答案」两行起：从页首起就是另起一页，否则接在读后末尾。"""
    key = page_key(WAIT + "答案")
    a = next((i for i in idx if key in pages[i]["text"]), None)
    if a is None:
        return len(idx), len(idx), False
    own = pages[a]["text"].startswith(key)
    return a - idx[0] + (0 if own else 1), len(idx), own


def unit_layout(pages, chapters):
    """有读前的单元和轻读单元的页数：{章号: {"pre": 读前页数, "post": 读后页数（不含答案）, "total": 读后连答案, "own": 答案另起一页}}。
    精读单元只有 pre。找不到的单元不记。"""
    up, out = unit_pages(pages, chapters), {}
    for ch in chapters:
        n = ch["n"]
        if n not in up or not (ch["preread"] or ch["mode"] == "轻读"):
            continue
        first, opener = up[n]
        if ch["mode"] == "轻读":
            idx = section_pages(pages, n, "读后")
            if not idx:
                continue
            post, total, own = post_split(pages, idx)
            out[n] = {"pre": idx[0] + 1 - first, "post": post, "total": total, "own": own}
        else:
            out[n] = {"pre": opener - first}
    return out


def section_stats(pages, chapters):
    """每章章首页、读前、词条、语法、赏析、写作，轻读的读后的页数和需要排紧的迹象。返回 {(章号, 栏目): (页数, 迹象数)}。"""
    out = {}
    up = unit_pages(pages, chapters)
    for ch in chapters:
        n = ch["n"]
        if ch["mode"] == "精读" and n in up:
            # 章首页没有页眉；下一页也没有页眉，就是地图溢出到了第二页
            o = up[n][1]
            spill = o < len(pages) and not pages[o]["head"]
            out[(n, "open")] = (1 + spill, int(spill))
    lay = unit_layout(pages, chapters)
    for ch in chapters:
        n = ch["n"]
        if n in lay:      # 读前要一页
            out[(n, "pre")] = (lay[n]["pre"], max(0, lay[n]["pre"] - 1))
        for key, label in sec_labels(ch).items():
            idx = section_pages(pages, n, label)
            if not idx:
                continue
            if key == "post":      # 读后（不含答案）要在上限页数内；连答案的最后一页只剩几行的也算
                if n not in lay:
                    continue
                bad = max(0, lay[n]["post"] - post_cap()) + int(len(idx) > 1 and pages[idx[-1]]["fill"] < 0.3)
            elif key == "words":     # 不是最后一页、下面空着三成左右（放不下下一条）
                bad = sum(pages[i]["fill"] < 0.72 for i in idx[:-1])
            elif key in ("write", "ans"):   # 写作、答案要一页：溢出几行就是几（排紧后行数变少也算改善）
                bad = over_lines(pages, idx)
            else:                  # 最后一页只剩几行
                bad = int(len(idx) > 1 and pages[idx[-1]]["fill"] < 0.3)
            out[(n, key)] = (len(idx), bad)
    return out


def essay_gaps(pages, chapters):
    """文学赏析里留白超过约三分之一页、下一页开头是一个整块挪过去的赏析点的地方。返回 {章号: {点号…}}。"""
    found = {}
    for ch in chapters:
        if ch["mode"] != "精读":
            continue
        idx = section_pages(pages, ch["n"], ch["essay_label"])
        points = essay_points(ch["essay"])[1]
        for i, j in zip(idx, idx[1:]):
            if pages[i]["fill"] >= 0.66:
                continue
            for k, (title, _) in enumerate(points, 1):
                if pages[j]["text"].startswith(f"{k:02d}" + re.sub(r"\s+|[`*]", "", title)):
                    found.setdefault(ch["n"], set()).add(k)
    return found


ONE_PAGE = ("写作", "自测", "答案")    # 这几栏要一页放下；放不下就在输出里提示多出几行


def render_pdf(page, target):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "book.html"
        src.write_text(page, encoding="utf-8")
        for attempt in (1, 2):
            try:
                chrome("--no-pdf-header-footer", "--generate-pdf-document-outline", f"--print-to-pdf={target}", src.as_uri())
                return
            except SystemExit:
                # Chrome 偶尔写完 PDF 后退出超时（Teardown watchdog expired）返回非零；重排一次
                if attempt == 2:
                    raise


TIGHT = {}   # 章号 → 需要排紧的句号；各栏目都从新页开始，合订本和分章的排法相同，可以共用
GIVE_UP = set()   # 排紧两级仍收不回去的（章号, 句号），保持正常排法
SECT = {}   # 章号 → 排紧一级的栏目（open/words/gram/essay/write/ans）；改善不了的不留
UNKEEP = {}   # 章号 → 不再整块保留的赏析点号（整块挪页会留下三分之一页以上空白的）
SPILL_WARNED = set()


def build_pdf(chapters, matches, out_dir, whole=False):
    """whole：这一份是全部单元（成品/讲义-全本.pdf），否则是分章（讲义-第NN章.pdf，几个单元一起就是 讲义-第01-02章.pdf）。
    全部单元或多于一个单元时排成合订本。"""
    nums = [c["n"] for c in chapters]
    by_n = {c["n"]: c for c in chapters}
    book = whole or len(chapters) > 1
    if whole:
        target = out_path(out_dir, "讲义.pdf")
    else:
        target = unit_pdf_path(out_dir, nums)
    target.parent.mkdir(parents=True, exist_ok=True)
    html_of = lambda pages=None: page_html(chapters, matches, pages, TIGHT, SECT, UNKEEP, book)
    render_pdf(html_of(), target)
    words = None
    if any(n not in TIGHT for n in nums):
        # 最后一页只剩几行的句子：先排紧一级，还不行再紧一级
        TIGHT.update({n: {} for n in nums})
        for _ in range(3):
            words = pdf_words(target)
            loose = loose_sentences(words, chapters) if words else {}
            # 最多排紧两级；两级还收不回去的，恢复正常排法（宁可多出半页，不要又密又溢出）
            bump = [(n, i) for n, ii in loose.items() for i in ii]
            if not bump:
                break
            for n, i in bump:
                level = TIGHT[n].get(i, 0) + 1
                if level > 2:
                    TIGHT[n].pop(i, None)
                    GIVE_UP.add((n, i))
                elif (n, i) not in GIVE_UP:
                    TIGHT[n][i] = level
            render_pdf(html_of(), target)
            words = None
        if any(c["mode"] == "精读" for c in chapters):       # 轻读单元的句子不各占一页，不排紧
            print("  排紧的句子：" + ("、".join(f"{n}-{i}{'（' + str(v) + '级）' if v > 1 else ''}" for n in nums
                                           for i, v in sorted(TIGHT[n].items())) or "无"))
    if any(n not in SECT for n in nums):
        # 栏目级：语法、赏析尾页只剩几行，或词条页下部空着放不下下一条，就整栏略排紧；没改善就恢复
        SECT.update({n: set() for n in nums})
        words = words or pdf_words(target)
        if words:
            before = section_stats(words, chapters)
            todo = [k for k, (cnt, bad) in before.items() if bad]
            if todo:
                for n, key in todo:
                    SECT[n].add(key)
                render_pdf(html_of(), target)
                words = pdf_words(target)
                after = section_stats(words, chapters)
                undo = [(n, key) for n, key in todo
                        if not (after.get((n, key), before[(n, key)])[0] < before[(n, key)][0]
                                or after.get((n, key), before[(n, key)])[1] < before[(n, key)][1])]
                for n, key in undo:
                    SECT[n].discard(key)
                if undo:
                    render_pdf(html_of(), target)
                    words = None
        print("  排紧的栏目：" + ("、".join(f"{n}-{sect_name(by_n[n], k)}" for n in nums for k in sorted(SECT[n])) or "无"))
    if any(n not in UNKEEP for n in nums):
        # 赏析：短的点整块挪到下一页、留下三分之一页以上空白的，改成照常跨页（标题、引文和译文、列表项仍不拆）
        UNKEEP.update({n: set() for n in nums})
        for _ in range(3):
            words = words or pdf_words(target)
            new = [(n, k) for n, ks in (essay_gaps(words, chapters) if words else {}).items()
                   for k in ks if k not in UNKEEP[n]]
            if not new:
                break
            for n, k in new:
                UNKEEP[n].add(k)
            render_pdf(html_of(), target)
            words = None
        if any(c["mode"] == "精读" for c in chapters):
            print("  跨页排的赏析点：" + ("、".join(f"{n}-{k}" for n in nums for k in sorted(UNKEEP[n])) or "无"))
    words = words or pdf_words(target)
    for n in nums:
        for label in ONE_PAGE:
            idx = section_pages(words or [], n, label)
            if len(idx) > 1 and (n, label) not in SPILL_WARNED:      # 合订本和分章排法相同，只提示一次
                SPILL_WARNED.add((n, label))
                print(f"  ! {unit_name(n)}「{label}」一页放不下，多出约 {over_lines(words, idx)} 行")
    # 读前要一页、轻读的读后（不含答案）不超过 light.pdf.post_pages 页：超了只提示，照常出 PDF
    lay = unit_layout(words or [], chapters)
    for ch in chapters:
        n = ch["n"]
        if n not in lay or (n, PRE) in SPILL_WARNED:
            continue
        SPILL_WARNED.add((n, PRE))
        x = lay[n]
        if ch["mode"] == "轻读":
            print(f"  {unit_name(n)}（轻读）：读前 {x['pre']} 页，读后 {x['post']} 页，"
                  + (f"答案另起，占 {x['total'] - x['post']} 页" if x["own"] else "答案接在读后末尾"))
        if x["pre"] > 1:
            print(f"  ! {unit_name(n)}的读前排了 {x['pre']} 页，应当一页放下：背景写短些，或少列几个人物、词")
        if ch["mode"] == "轻读" and x["post"] > post_cap():
            print(f"  ! {unit_name(n)}的读后排了 {x['post']} 页（不含答案），轻读的读后应不超过 {post_cap()} 页：少选一个词条，或把讲解写短")
    if book:
        words = words or pdf_words(target)
        toc_at = next((i for i, p in enumerate(words or []) if p["text"].startswith("目录")), None)
        if toc_at is not None and toc_at > 2 and "howto" not in SPILL_WARNED:      # 封面、怎么用之后应当就是目录
            SPILL_WARNED.add("howto")
            print("  ! 「怎么用」页一页放不下：前言.md 开头的出处说明写短一些")
        titles = [t for t, _ in preface()[1]]
        pages = toc_pages(words, chapters, titles) if words else None
        if pages:
            render_pdf(html_of(pages), target)
            if toc_pages(pdf_words(target), chapters, titles) != pages:
                print("  ! 目录页码与第二遍排版不一致，请检查")
        elif words:
            print(f"  ! 没能从 PDF 里找到各{P.unit}（或前言各页）的起始页，目录不写页码")
    print(target)


def take_out(args):
    """拿出「--out 目录」，返回 (输出目录, 其余参数)。默认是项目的 成品/（旧项目是项目根目录）。"""
    out_dir = P.out
    if "--out" in args:
        k = args.index("--out")
        if k + 1 >= len(args):
            sys.exit("--out 后面要写目录")
        out_dir = Path(args[k + 1]).expanduser()
        args = args[:k] + args[k + 2:]
    return out_dir, args


def load_units(nums):
    chapters = {n: parse_chapter(n) for n in nums}
    for ch in chapters.values():
        if ch["errors"]:
            sys.exit(f"{unit_name(ch['n'])}格式有问题，先运行 check")
    return chapters


def cmd_pdf(args):
    out_dir, args = take_out(args)
    avail = available()
    if not avail:
        sys.exit(no_units())
    if args == ["all"]:
        jobs = [avail] + ([[n] for n in avail] if len(avail) > 1 else [])     # 只有一个单元时只出 讲义-全本.pdf
    else:
        if not all(a.isdigit() for a in args):
            sys.exit(f"pdf 后面写单元号、all 或 --out 目录，不认识：{' '.join(args)}")
        picked = [int(a) for a in args]
        missing = [n for n in picked if n not in avail]
        if missing:
            sys.exit("没有这些单元的讲义：" + "、".join(str(unit_path(n)) for n in missing))
        jobs = [picked or avail]
    need = sorted({n for job in jobs for n in job})
    chapters = load_units(need)
    if not CHROME:
        CHROME.append(find_chrome())       # 先找好排版程序，找不到就在排版之前说明
    font_warnings()
    matches = {n: sentence_hits(ch) for n, ch in chapters.items()}
    if P.format >= 3:       # 第三版不用 core_match：断句表里的粗体就是主干
        need_hl = []
    else:
        need_hl = need
        print("主干高亮：")
    for n in need_hl:
        for s, (hits, ratio, why) in zip(chapters[n]["sentences"], matches[n]):
            print(f"  {n:>2}-{s['i']}  {ratio:4.0%}  {'高亮' if hits else '跳过：' + why}")
        for s, (hits, ratio, why) in zip(chapters[n]["extra"], sentence_hits(chapters[n], "extra")):
            print(f"  {n:>2}-补{s['i']}  {ratio:4.0%}  {'高亮' if hits else '跳过：' + why}")
    flat_note()
    out_dir.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        build_pdf([chapters[n] for n in job], matches, out_dir, whole=sorted(job) == avail)


# ---------- 合订 Markdown ----------

def toc_line(ch):
    """合订本目录里的一行。精读单元写语法专题的题目（和第一版一样）；轻读单元没有语法专题，写 设置.json 里的单元标题，
    没写标题就只写「第 N 章」。"""
    n = ch["n"]
    if ch["mode"] == "精读":
        return f"- [{unit_name(n)}　{ch['grammar_title']}](#ch{n})"
    title = dict(P.units).get(n, "")
    return f"- [{unit_name(n)}　{title}](#ch{n})" if title else f"- [{unit_name(n)}](#ch{n})"


def cmd_md(args):
    """前言和各单元原样合订成 讲义.md：单元内标题整体降一级，正文一字不改。
    顺序和 PDF 一样：出处和缩写、目录、前言各节（语法术语…）、各单元。只有一个单元时不生成。"""
    out_dir, args = take_out(args)
    if args:
        sys.exit(f"md 只接项目目录和 --out，不认识：{' '.join(args)}")
    if len(P.units) == 1:
        print(f"只有一个单元，{P.docs.name}/{unit_path(P.units[0][0]).name} 就是全文，不生成合订本")
        return 0
    nums = available()
    if not nums:
        sys.exit(no_units())
    units = load_units(nums)
    chapters = [units[n] for n in nums]
    pre, fsecs = preface()
    head = [f"# {P.title} 讲解"] + ([pre.strip("\n")] if pre.strip() else [])
    head.append("## 目录\n\n" + "\n".join([f"- [{t}](#front{k})" for k, (t, _) in enumerate(fsecs, 1)]
                                         + [toc_line(c) for c in chapters]))
    parts = ["\n\n".join(head) + "\n"]
    for k, (t, body) in enumerate(fsecs, 1):
        parts.append(f'<a id="front{k}"></a>\n\n## {t}\n\n' + body.strip("\n") + "\n")
    for ch in chapters:
        lines = []
        for line in ch["raw"].splitlines():
            if line.startswith("# "):          # 一级标题怎么写都行，合订后统一成「## 第 N 章」
                line = f"## {unit_name(ch['n'])}"
            elif re.match(r"#+ ", line):
                line = "#" + line
            lines.append(line)
        parts.append(f'<a id="ch{ch["n"]}"></a>\n\n' + "\n".join(lines).strip("\n") + "\n")
    flat_note()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_path(out_dir, "讲义.md")
    target.write_text("\n---\n\n".join(parts), encoding="utf-8")
    print(target)


def cmd_tidy(args):
    """把旧名字改成新的，只挪不覆盖（目标已有同名的不挪）：
    讲义/ → 源稿/；根目录里平铺的输出 → 成品/；成品/ 里上一种布局（讲义.md、分章/第NN章.pdf、复习/…）→ 讲义-全本.md、
    讲义-第NN章.pdf、难句本.md 这样。挪空了的 分章/、复习/ 删掉。"""
    if args:
        sys.exit(f"tidy 只接项目目录，不认识：{' '.join(args)}")
    root, out = P.root, P.root / OUT_DIR
    moves = []                                      # (原路径, 新路径)
    if P.docs.name == OLD_DOCS_DIR:
        moves.append((P.docs, root / DOCS_DIR))
    P.flat = False
    for name in OUT_PLACE:                          # 平铺的旧项目
        if (root / name).exists():
            moves.append((root / name, out_path(out, name)))
    moves += [(f, out / f"讲义-{f.name}") for f in sorted((root / "分章").glob("*.pdf"))]
    for old, new in OLD_OUT.items():                # 成品/ 的上一种布局
        if (out / old).exists():
            moves.append((out / old, out / new))
    moves += [(f, out / f"讲义-{f.name}") for f in sorted((out / "分章").glob("*.pdf"))]
    if not moves:
        print(f"没有要改的旧名字：源稿在 {DOCS_DIR}/，输出都在 {OUT_DIR}/ 里")
        return 0
    kept = []
    for src, dst in moves:
        if dst.exists():
            kept.append((src, dst))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        print(f"{src.relative_to(root)} → {dst.relative_to(root)}")
    for d in (root / "分章", out / "分章", out / "复习"):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    for src, dst in kept:
        print(f"  ! 已有 {dst.relative_to(root)}，{src.relative_to(root)} 没挪：确认不要了就删掉")
    print("README.md 里指向旧路径的链接（讲义/、成品/讲义.pdf、成品/分章/、成品/复习/）要手动改")
    return 1 if kept else 0


NOTEBOOK = ("sentences", "words", "stuck")      # 难句本、单词本、卡句定位：实现在同目录的 notebook.py


def cmd_notebook(name, args):
    """sentences、words、stuck 转发给 notebook.py 的 run(子命令, 其余参数, build)：build 是本模块，P 已经按项目填好，
    notebook.py 直接用 parse_chapter、source_text 这些。notebook.py 还不在时报“还没实现”。"""
    if not (HERE / "notebook.py").exists():
        sys.exit(f"build.py {name} 还没实现：要同目录的 notebook.py")
    return sibling("notebook").run(name, args, sys.modules[__name__])


def main(argv):
    cmds = {"check": cmd_check, "md": cmd_md, "pdf": cmd_pdf, "fonts": cmd_fonts, "tidy": cmd_tidy}
    cmds.update({c: (lambda args, c=c: cmd_notebook(c, args)) for c in NOTEBOOK})
    if len(argv) < 2 or argv[1] not in cmds:
        sys.exit(__doc__)
    # 项目目录可以写在其他参数前面或后面：pdf demo all、pdf all demo 都行。--out 后面跟的是输出目录，不算项目。
    args, project, rest, skip = argv[2:], None, [], False
    for a in args:
        if skip:
            rest.append(a)
            skip = False
        elif a == "--out":
            rest.append(a)
            skip = True
        elif project is None and a != "all" and not a.isdigit() and not a.startswith("--"):
            project = a
        else:
            rest.append(a)
    args = rest
    if argv[1] != "fonts" or project or Path("设置.json").exists():     # fonts 不在项目里也能用：只列本机字体
        load_project(project or ".")
    return cmds[argv[1]](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
