#!/usr/bin/env python3
"""把原文整理成 原文/第NN章.txt（每个单元一份纯文本，段落之间空一行）。

用法：
  source.py epub BOOK.epub --list
  source.py epub BOOK.epub --items 3,4[,5-9] --out 项目/原文/ [--start 1] [--unit 章] [--force]
  source.py html FILE_OR_URL --out 项目/原文/第01篇.txt [--force]
  source.py txt FILE --out 项目/原文/ [--split REGEX] [--encoding utf-8] [--unit 章] [--force]
  source.py paste [--out 原文/] [--para auto|blank|line] [--unit 篇] [--force]  < 贴的文本

文件名：--out 给目录时，写成 第{NN}{unit}.txt（第01章.txt、第01部分.txt、第01篇.txt）。
  unit 读 --out 目录上一级（项目根）的 设置.json；没有 设置.json 才用 --unit（默认 章）。
  --out 给完整的 .txt 文件名时照用。

清洗规则（三种来源相同）：
  - 一个 <p>、<h1>–<h6>、<li>、<blockquote>（以及 dt/dd/td 等块）里的文字成一段；
    div、section 等容器里直接写的文字也各成一段。
  - 去标签，HTML 实体反转义；删零宽字符（U+200B–U+200D、U+2060、U+FEFF）和软连字符（U+00AD）；
    不换行空格（U+00A0、U+2007、U+202F）换成普通空格；段内空白归一成一个空格。
  - 弯引号、破折号、省略号等原样保留。
  - <br/> 分行（诗行）在段内用换行保留；连续两个 <br/> 视为分段。
  - epub:type 或 role 为 pagebreak / noteref / backlink 的元素（页码、注释号、注释回链）丢掉。

贴的文本（paste）：从标准输入读，UTF-8。文本里有空行时按空行分段（段内硬换行并成一个空格，同 txt）；
  一个空行也没有时每行算一段。--para blank / line 可以强制指定。--out 默认 原文/（相对当前目录），
  文件名同上，只是没有 设置.json、也没给 --unit 时用“篇”：原文/第01篇.txt。

网址（html URL）：User-Agent 如实写 english-reader/3.0，不伪装浏览器。遇到 401、402、403、429，
  或抽出来的词数很少、正文里有付费墙的字样，就提示请用户把文本贴进来或把网页存成文件；不换 UA、不重试。
  抽完打印词数和首尾两句，请用户确认没有抽残。

只用标准库。profile.py 从这里取计词、切句和认标题行的函数。
"""
import argparse
import json
import posixpath
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "english-reader/3.0"  # 如实的 UA；网站不让抓就请用户贴文本或存网页，不伪装浏览器

# ---------------------------------------------------------------- 计词

LETTERS = "A-Za-zÀ-ɏ"
# 一个英文词：字母串，可由撇号或连字符连接（spring-cleaning、didn’t、o’clock 各算一个词）
WORD_RE = re.compile(r"[%s]+(?:['’\-][%s]+)*" % (LETTERS, LETTERS))


def count_words(text):
    return len(WORD_RE.findall(text))


# ---------------------------------------------------------------- 切句、标题行（profile.py 也用）

ABBREV = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "rev", "capt", "col", "gen", "lt",
          "sgt", "mt", "vs", "etc", "no", "co", "messrs", "hon", "esq", "vol", "pp", "fig", "ft"}
SENT_END_RE = re.compile(r"([.!?…]+)([”’\"')\]]*)(\s+)(?=[“‘\"'(\[]*[A-Z])")
HEADING_MAX_WORDS = 12


def is_heading(para):
    """没有句末标点、不超过 12 词的段落当作标题行。"""
    words = WORD_RE.findall(para)
    return 0 < len(words) <= HEADING_MAX_WORDS and not re.search(r"[.!?…:;,—\-”’\"')\]]\s*$", para)


def split_sentences(para):
    """. ! ? … 后接空白、再接大写字母或开引号处切开；Mr. 等缩写和单字母缩写不切。"""
    text = re.sub(r"\s+", " ", para).strip()
    out, start = [], 0
    for m in SENT_END_RE.finditer(text):
        if m.group(1) == ".":
            before = re.search(r"([A-Za-z]+)\.$", text[:m.end(1)])
            if before:
                w = before.group(1)
                if w.lower() in ABBREV or (len(w) == 1 and w.isupper()):
                    continue
        cut = m.end(2)
        s = text[start:cut].strip()
        if s:
            out.append(s)
        start = m.end(3)
    s = text[start:].strip()
    if s:
        out.append(s)
    return out


# ---------------------------------------------------------------- 文本清洗

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_NBSP = {ord(" "): " ", ord(" "): " ", ord(" "): " "}
_WS_RE = re.compile(r"\s+")


def clean_line(s):
    """删零宽字符和软连字符，不换行空格变普通空格，空白归一，去首尾空白。"""
    s = s.translate(_ZERO_WIDTH).translate(_NBSP)
    return _WS_RE.sub(" ", s).strip()


# ---------------------------------------------------------------- 迷你 DOM

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}
# 遇到这些开始标签时，自动关闭尚未关闭的 <p>（HTML 的隐式关闭规则，简化版）
P_CLOSERS = {"address", "article", "aside", "blockquote", "div", "dl", "fieldset", "figure",
             "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr",
             "main", "nav", "ol", "p", "pre", "section", "table", "ul", "li", "dt", "dd"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def has_class(self, name):
        return name in self.classes()

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def find_all(self, tag=None, cls=None, pred=None):
        out = []
        for n in self.iter():
            if n is self:
                continue
            if tag is not None and n.tag != tag and not (isinstance(tag, (set, tuple)) and n.tag in tag):
                continue
            if cls is not None and cls not in n.classes():
                continue
            if pred is not None and not pred(n):
                continue
            out.append(n)
        return out

    def find(self, tag=None, cls=None, pred=None):
        for n in self.iter():
            if n is self:
                continue
            if tag is not None and n.tag != tag and not (isinstance(tag, (set, tuple)) and n.tag in tag):
                continue
            if cls is not None and cls not in n.classes():
                continue
            if pred is not None and not pred(n):
                continue
            return n
        return None

    def child_elements(self):
        return [c for c in self.children if isinstance(c, Node)]

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def text(self, skip=None):
        """全部文字（未清洗）。skip(node) 为真的子树跳过。"""
        parts = []

        def walk(n):
            for c in n.children:
                if isinstance(c, Node):
                    if skip is not None and skip(c):
                        continue
                    if c.tag == "br":
                        parts.append(" ")
                    walk(c)
                else:
                    parts.append(c)
        walk(self)
        return "".join(parts)


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def _close_to(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return True
        return False

    def handle_starttag(self, tag, attrs):
        cur = self.stack[-1]
        if tag in P_CLOSERS and cur.tag == "p":
            self.stack.pop()
        if tag == "li":
            self._close_open_item(("li",), ("ul", "ol"))
        elif tag in ("dt", "dd"):
            self._close_open_item(("dt", "dd"), ("dl",))
        elif tag == "tr":
            self._close_open_item(("tr",), ("table", "thead", "tbody", "tfoot"))
        elif tag in ("td", "th"):
            self._close_open_item(("td", "th"), ("tr",))
        parent = self.stack[-1]
        node = Node(tag, [(k, v if v is not None else "") for k, v in attrs], parent)
        parent.children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def _close_open_item(self, items, containers):
        for i in range(len(self.stack) - 1, 0, -1):
            t = self.stack[i].tag
            if t in containers:
                return
            if t in items:
                del self.stack[i:]
                return

    def handle_startendtag(self, tag, attrs):
        parent = self.stack[-1]
        parent.children.append(Node(tag, [(k, v if v is not None else "") for k, v in attrs], parent))

    def handle_endtag(self, tag):
        self._close_to(tag)

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text):
    b = _TreeBuilder()
    b.feed(text)
    b.close()
    return b.root


def decode_bytes(data, declared=None):
    """按声明的编码 → <meta charset> / <?xml encoding?> → UTF-8 解码。"""
    encs = []
    if declared:
        encs.append(declared)
    head = data[:2048].decode("ascii", "replace")
    m = re.search(r"""<\?xml[^>]*encoding=["']([\w.-]+)""", head) or \
        re.search(r"""<meta[^>]+charset=["']?([\w.-]+)""", head, re.I)
    if m:
        encs.append(m.group(1))
    encs += ["utf-8-sig"]
    for e in encs:
        try:
            return data.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", "replace")


# ---------------------------------------------------------------- 段落抽取

PARA_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "dt", "dd",
             "figcaption", "caption", "td", "th", "pre", "address"}
BOUNDARY_TAGS = PARA_TAGS | {"div", "section", "article", "aside", "header", "footer", "hgroup",
                             "main", "nav", "figure", "table", "thead", "tbody", "tfoot", "tr",
                             "ul", "ol", "dl", "body", "html", "hr", "form", "fieldset",
                             "details", "summary", "#document"}
SKIP_TAGS = {"head", "title", "script", "style", "template", "noscript", "svg", "math",
             "iframe", "object", "video", "audio", "canvas", "button", "select", "input",
             "textarea"}
DROP_TYPES = {"pagebreak", "noteref", "backlink"}
DROP_ROLES = {"doc-pagebreak", "doc-noteref", "doc-backlink"}
DROP_CLASSES = {"pagenum", "pageno", "page-number"}
HTML_EXTRA_SKIP = {"nav", "aside", "form", "footer", "figure"}
# 网页里常见的“不打印/隐藏/编辑链接”类（MediaWiki 的 noprint、mw-editsection 等）
HTML_SKIP_CLASSES = {"noprint", "mw-editsection", "navbox", "catlinks", "printfooter", "mw-jump-link",
                     "visually-hidden", "sr-only", "screen-reader-text", "ws-noexport", "reference",
                     "mw-cite-backlink"}

_BR = "\u0000"


def is_dropped(node, html_mode=False):
    if node.tag in SKIP_TAGS:
        return True
    types = set((node.attrs.get("epub:type") or "").split())
    if types & DROP_TYPES:
        return True
    if (node.attrs.get("role") or "") in DROP_ROLES:
        return True
    if set(node.classes()) & DROP_CLASSES:
        return True
    if html_mode:
        if node.tag in HTML_EXTRA_SKIP:
            return True
        if node.attrs.get("role") in ("navigation", "complementary", "banner", "contentinfo"):
            return True
        if (node.attrs.get("aria-hidden") or "").lower() == "true":
            return True
        if set(node.classes()) & HTML_SKIP_CLASSES or node.attrs.get("hidden") is not None:
            return True
        if re.search(r"display\s*:\s*none", node.attrs.get("style") or ""):
            return True
    return False


def extract_paragraphs(root, html_mode=False, only_tags=None):
    """从节点里按块抽段落。only_tags 给出时，只取这些标签（如 {'p'}）里的文字。"""
    paras = []
    buf = []

    def flush():
        if not buf:
            return
        raw = "".join(buf)
        buf.clear()
        # 连续两个 <br/>（中间只有空白）当作分段
        chunks = re.split(_BR + r"\s*" + _BR, raw)
        for chunk in chunks:
            lines = [clean_line(x) for x in chunk.split(_BR)]
            lines = [x for x in lines if x]
            if lines:
                paras.append("\n".join(lines))

    def walk(node, inside):
        for c in node.children:
            if isinstance(c, str):
                if inside:
                    buf.append(c.replace(_BR, ""))
                continue
            if is_dropped(c, html_mode):
                continue
            if c.tag == "br":
                if inside:
                    buf.append(_BR)
                continue
            now_inside = inside or (only_tags is not None and c.tag in only_tags)
            if c.tag in BOUNDARY_TAGS:
                flush()
                walk(c, now_inside)
                flush()
            else:
                walk(c, now_inside)

    walk(root, only_tags is None)
    flush()
    return paras


def heading_text(node):
    return clean_line(node.text(skip=lambda n: is_dropped(n)))


def doc_title(root):
    """文档标题：hgroup（各行用 ': ' 连接）> 第一个 h1–h3 > <title>。"""
    body = root.find("body") or root
    hg = body.find("hgroup")
    if hg is not None:
        parts = [heading_text(c) for c in hg.child_elements()
                 if c.tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p")]
        parts = [p for p in parts if p]
        if parts:
            return ": ".join(parts)
    h = body.find(("h1", "h2", "h3"))
    if h is not None and heading_text(h):
        return heading_text(h)
    t = root.find("title")
    if t is not None:
        return clean_line(t.text())
    return ""


# ---------------------------------------------------------------- 输出

def write_unit(path, paras, force):
    path = Path(path)
    if path.exists() and not force:
        raise SystemExit("错误：%s 已存在。确认要覆盖请加 --force。" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n\n".join(paras) + "\n")


def report_unit(path, paras, note=""):
    words = sum(count_words(p) for p in paras)
    print("%-10s 段 %4d   词 %7s%s" % (Path(path).name, len(paras), format(words, ","),
                                        ("   ← " + note) if note else ""))
    return words


UNITS = ("章", "部分", "篇")


def unit_name(n, total, unit):
    width = max(2, len(str(total)))
    return "第%0*d%s.txt" % (width, n, unit)


def resolve_unit(out_dir, cli_unit, default="章"):
    """单元名：项目根（--out 目录的上一级）的 设置.json 里的 unit 优先，其次 --unit，再次 default。"""
    cfg = Path(out_dir).resolve().parent / "设置.json"
    if cfg.is_file():
        try:
            with open(cfg, encoding="utf-8") as f:
                unit = (json.load(f).get("unit") or "").strip()
        except (OSError, ValueError) as e:
            raise SystemExit("错误：读不了 %s（%s）" % (cfg, e))
        if unit:
            if cli_unit and cli_unit != unit:
                print("注意：%s 里 unit 是“%s”，以它为准（忽略 --unit %s）。" % (cfg, unit, cli_unit),
                      file=sys.stderr)
            return unit
    return cli_unit or default


# ---------------------------------------------------------------- EPUB

class Epub:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.zf = zipfile.ZipFile(str(self.path))
        except (OSError, zipfile.BadZipFile) as e:
            raise SystemExit("错误：打不开 EPUB %s（%s）" % (path, e))
        container = parse_html(self._read_text("META-INF/container.xml"))
        rf = container.find("rootfile")
        if rf is None or not rf.attrs.get("full-path"):
            raise SystemExit("错误：META-INF/container.xml 里没有 rootfile")
        self.opf_path = rf.attrs["full-path"]
        self.opf_dir = posixpath.dirname(self.opf_path)
        opf = parse_html(self._read_text(self.opf_path))
        manifest = {}
        for it in opf.find_all("item"):
            href = urllib.parse.unquote(it.attrs.get("href", ""))
            full = posixpath.normpath(posixpath.join(self.opf_dir, href)) if self.opf_dir else href
            manifest[it.attrs.get("id")] = (full, it.attrs.get("media-type", ""))
        self.spine = []  # (zip 内路径, media-type, linear)
        for ref in opf.find_all("itemref"):
            idref = ref.attrs.get("idref")
            if idref not in manifest:
                continue
            full, mt = manifest[idref]
            self.spine.append((full, mt, (ref.attrs.get("linear") or "yes") != "no"))

    def _read_text(self, name):
        try:
            data = self.zf.read(name)
        except KeyError:
            raise SystemExit("错误：EPUB 里缺少 %s" % name)
        return decode_bytes(data)

    def document(self, index):
        full, mt, linear = self.spine[index]
        root = parse_html(self._read_text(full))
        return root


def cmd_epub(args):
    book = Epub(args.file)
    if args.list or not args.items:
        if not args.list:
            print("（没给 --items，先列出目录；选好后用 --items 3,4 --out 项目/原文/）\n")
        print("%4s  %-36s %8s  %s" % ("序号", "文件", "词数", "标题"))
        for i, (full, mt, linear) in enumerate(book.spine, 1):
            if "html" not in mt and not full.lower().endswith((".xhtml", ".html", ".htm")):
                print("%4d  %-36s %8s  （%s，跳过）" % (i, posixpath.basename(full), "-", mt))
                continue
            root = book.document(i - 1)
            body = root.find("body") or root
            words = sum(count_words(p) for p in extract_paragraphs(body))
            flag = "" if linear else "  [linear=no]"
            print("%4d  %-36s %8s  %s%s" % (i, posixpath.basename(full), format(words, ","),
                                            doc_title(root), flag))
        return
    if not args.out:
        raise SystemExit("错误：抽取时要给 --out 项目/原文/")
    items = parse_items(args.items, len(book.spine))
    out_dir = Path(args.out)
    unit = resolve_unit(out_dir, args.unit)
    total_words = 0
    last = args.start + len(items) - 1
    for k, idx in enumerate(items):
        root = book.document(idx - 1)
        body = root.find("body") or root
        paras = extract_paragraphs(body)
        if not paras:
            print("警告：第 %d 项（%s）没有抽到文字。" % (idx, posixpath.basename(book.spine[idx - 1][0])),
                  file=sys.stderr)
        path = out_dir / unit_name(args.start + k, last, unit)
        write_unit(path, paras, args.force)
        total_words += report_unit(path, paras, "%d %s（%s）" % (
            idx, posixpath.basename(book.spine[idx - 1][0]), doc_title(root)))
    print("共 %d 个单元，%s 词。" % (len(items), format(total_words, ",")))


def parse_items(spec, n):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        nums = range(int(m.group(1)), int(m.group(2)) + 1) if m else [int(part)] if part.isdigit() else None
        if nums is None:
            raise SystemExit("错误：--items 写法不对：%r（例：3,4 或 3-14）" % part)
        for x in nums:
            if not 1 <= x <= n:
                raise SystemExit("错误：序号 %d 超出范围（1–%d），先用 --list 看目录" % (x, n))
            out.append(x)
    if not out:
        raise SystemExit("错误：--items 是空的")
    return out


# ---------------------------------------------------------------- HTML

# 网站明确拒绝时的提示。这些都不重试、不换 UA。
BLOCKED_HTTP = {
    401: "要登录才能看",
    402: "要付费才能看",
    403: "网站拒绝了脚本访问",
    429: "网站嫌请求太频繁，暂时不让取",
}
ASK_USER = ("请用户把文章文本直接贴进对话（用 source.py paste 存成原文），"
            "或在浏览器里把网页另存为 .html 文件，再用 source.py html 那个文件 抽取。"
            "不要换 User-Agent，也不要重试绕过。")
LOW_WORDS = 300  # 抽出来不到这么多词，多半是付费墙、登录墙或页面靠脚本加载正文
PAYWALL_MAX_WORDS = 40  # 付费墙提示是短的独立段落；长段落里的同样字样多半是正文
PAYWALL_RE = re.compile(
    r"subscribe (?:now )?to (?:continue|keep reading|read|unlock)|already (?:a subscriber|have an account)"
    r"|subscribers?[- ]only|(?:subscribe|sign up|log in|sign in) (?:now )?to continue"
    r"|(?:sign|log) in to (?:continue|read|keep reading)|create a free account to"
    r"|this (?:article|story|content) is (?:only )?(?:for|available to|reserved for) (?:paid |paying )?"
    r"(?:subscribers|members)"
    r"|you(?:'|’)ve (?:reached|used) (?:your|all of your|all your) (?:free )?(?:article|story|monthly)",
    re.I)
PAYWALL_MARK_RE = re.compile(r"""(?:class|id)=["'][^"']*pay-?wall""", re.I)


def fetch_url(url, timeout=30):
    """如实的 UA 取一次。401/402/403/429 给出请用户贴文本或存网页的提示后退出，不重试。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            charset = r.headers.get_content_charset()
    except urllib.error.HTTPError as e:
        if e.code in BLOCKED_HTTP:
            raise SystemExit("错误：取不到 %s：HTTP %d，%s。\n%s" % (url, e.code, BLOCKED_HTTP[e.code], ASK_USER))
        raise SystemExit("错误：取不到 %s（HTTP %d %s）。网址对的话，%s" % (url, e.code, e.reason, ASK_USER))
    except (urllib.error.URLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", None) or e
        raise SystemExit("错误：取不到 %s（%s）。网络不通或网址有误；%s" % (url, reason, ASK_USER))
    return decode_bytes(data, charset)


def clip(s, width=160):
    """太长的句子只留头尾。"""
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= width:
        return s
    half = (width - 3) // 2
    return s[:half].rstrip() + " … " + s[-half:].lstrip()


def extraction_report(paras, raw_html="", path=None, where=""):
    """抽完以后给用户确认用：词数、首尾两句；词数很少或有付费墙字样时提示。返回提示列表。"""
    words = sum(count_words(p) for p in paras)
    body = [p for p in paras if not is_heading(p)] or paras
    first = split_sentences(body[0])[0]
    last = split_sentences(body[-1])[-1]
    heads = len(paras) - len(body) if body is not paras else 0
    print("%s%s%d 段，%s 词%s。" % ("正文取自 %s；" % where if where else "",
                                 "已写入 %s：" % path if path else "抽到 ", len(paras), format(words, ","),
                                 "（其中标题行 %d 个）" % heads if heads else ""))
    print("开头一句：%s" % clip(first))
    print("结尾一句：%s" % clip(last))
    print("请用户确认没有抽残：开头、结尾和原网页对得上，中间没有丢段。")
    warns = []
    hit = next((m for m in (PAYWALL_RE.search(x) for x in paras if count_words(x) <= PAYWALL_MAX_WORDS) if m), None)
    if hit:
        warns.append("正文里有“%s”这样的字样，可能是付费墙或登录墙，抽到的不是全文。" % hit.group(0))
    if words < LOW_WORDS:
        why = "，网页里还有 paywall 标记" if PAYWALL_MARK_RE.search(raw_html or "") else ""
        warns.append("只抽到 %d 词%s，可能是付费墙、登录墙，或者正文靠脚本加载，抽残了。" % (words, why))
    for w in warns:
        print("注意：" + w)
    if warns:
        print("注意：" + ASK_USER)
    return warns


def html_main_paragraphs(root):
    articles = root.find_all("article")
    if articles:
        best = max(articles, key=lambda a: len(clean_line(a.text())))
        return extract_paragraphs(best, html_mode=True), "<article>"
    body_text = root.find(pred=lambda n: n.attrs.get("itemprop") == "articleBody")
    if body_text is not None:
        return extract_paragraphs(body_text, html_mode=True), 'itemprop="articleBody"'
    mw = root.find(cls="mw-parser-output")  # MediaWiki（Wikipedia、Wikisource）的正文
    if mw is not None:
        return extract_paragraphs(mw, html_mode=True), "MediaWiki 正文（.mw-parser-output）"
    main = root.find("main")
    if main is not None:
        return extract_paragraphs(main, html_mode=True), "<main>"
    body = root.find("body") or root
    return extract_paragraphs(body, html_mode=True, only_tags={"p"}), "<body> 里的 <p>"


def cmd_html(args):
    src = args.source
    if re.match(r"https?://", src, re.I):
        text = fetch_url(src)
    else:
        p = Path(src)
        if not p.is_file():
            raise SystemExit("错误：找不到文件 %s" % src)
        text = decode_bytes(p.read_bytes())
    root = parse_html(text)
    paras, where = html_main_paragraphs(root)
    if not paras:
        raise SystemExit("错误：页面里没有抽到正文段落（找过 article、main、body 里的 p）")
    out = Path(args.out)
    if out.suffix.lower() != ".txt":
        out = out / unit_name(args.start, args.start, resolve_unit(out, args.unit))
    write_unit(out, paras, args.force)
    extraction_report(paras, text, path=out, where=where)


# ---------------------------------------------------------------- TXT

def txt_paragraphs(lines):
    """空行分段；段内硬换行合并成一个空格（行尾是连字符或破折号时直接接上）。"""
    paras, cur = [], []

    def flush():
        if cur:
            s = ""
            for ln in cur:
                if not s:
                    s = ln
                elif re.search(r"[%s][-—]$" % LETTERS, s):
                    s += ln
                else:
                    s += " " + ln
            s = clean_line(s)
            if s:
                paras.append(s)
            cur.clear()

    for ln in lines:
        ln2 = clean_line(ln)
        if not ln2:
            flush()
        else:
            cur.append(ln2)
    flush()
    return paras


def cmd_txt(args):
    p = Path(args.file)
    if not p.is_file():
        raise SystemExit("错误：找不到文件 %s" % args.file)
    try:
        text = p.read_bytes().decode(args.encoding)
    except (UnicodeDecodeError, LookupError) as e:
        raise SystemExit("错误：按 %s 解码失败（%s）。用 --encoding 指定编码。" % (args.encoding, e))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    units = []  # 每个单元一组行
    if args.split:
        try:
            rx = re.compile(args.split)
        except re.error as e:
            raise SystemExit("错误：--split 正则写错了：%s" % e)
        pre, cur = [], None
        for ln in lines:
            if rx.search(ln):
                if cur is not None:
                    units.append(cur)
                cur = [ln, ""]  # 标题行单独成段
            elif cur is None:
                pre.append(ln)
            else:
                cur.append(ln)
        if cur is not None:
            units.append(cur)
        if not units:
            raise SystemExit("错误：--split 正则一行也没匹配上")
        pre_words = count_words("\n".join(pre))
        if pre_words:
            print("注意：第一个标题之前有 %d 词，已略过（如需保留请调整 --split）。" % pre_words)
    else:
        units = [lines]
    out_dir = Path(args.out)
    if out_dir.suffix.lower() == ".txt":
        if len(units) != 1:
            raise SystemExit("错误：切出了 %d 个单元，--out 要给目录" % len(units))
        targets = [out_dir]
    else:
        last = args.start + len(units) - 1
        unit = resolve_unit(out_dir, args.unit)
        targets = [out_dir / unit_name(args.start + k, last, unit) for k in range(len(units))]
    total = 0
    for path, ls in zip(targets, units):
        paras = txt_paragraphs(ls)
        write_unit(path, paras, args.force)
        total += report_unit(path, paras, paras[0][:40] if args.split and paras else "")
    if len(units) > 1:
        print("共 %d 个单元，%s 词。" % (len(units), format(total, ",")))


# ---------------------------------------------------------------- 贴的文本

def paste_paragraphs(text, mode="auto"):
    """贴进来的文本 → 段落。auto：有空行就按空行分段（段内换行并成空格），一个空行都没有就每行一段。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if mode == "auto":
        inner = [clean_line(x) for x in lines]
        while inner and not inner[0]:
            inner.pop(0)
        while inner and not inner[-1]:
            inner.pop()
        mode = "blank" if any(not x for x in inner) else "line"
    if mode == "blank":
        return txt_paragraphs(lines)
    return [x for x in (clean_line(ln) for ln in lines) if x]


def read_stdin_text():
    if sys.stdin is None:
        raise SystemExit("错误：没有标准输入。")
    if sys.stdin.isatty():
        print("把文本贴进来，贴完另起一行按 Ctrl-D（Windows 按 Ctrl-Z 再回车）。", file=sys.stderr)
    buf = getattr(sys.stdin, "buffer", None)
    data = buf.read() if buf is not None else sys.stdin.read().encode("utf-8")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise SystemExit("错误：标准输入不是 UTF-8（%s）。先存成文件，再用 source.py txt 文件 --encoding …。" % e)


def cmd_paste(args):
    paras = paste_paragraphs(read_stdin_text(), args.para)
    if not paras:
        raise SystemExit("错误：标准输入里没有文字。用法：source.py paste --out 项目/原文/ <<'EOF' … EOF")
    out = Path(args.out)
    if out.suffix.lower() != ".txt":
        out = out / unit_name(args.start, args.start, resolve_unit(out, args.unit, default="篇"))
    write_unit(out, paras, args.force)
    report_unit(out, paras)


# ---------------------------------------------------------------- main

def setup_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="把原文整理成 原文/第NN章.txt")
    unit_help = "单元名 章/部分/篇（只在项目根没有 设置.json 时用；默认 章）"
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    e = sub.add_parser("epub", help="从 EPUB 抽取")
    e.add_argument("file")
    e.add_argument("--list", action="store_true", help="按 spine 顺序列出文档")
    e.add_argument("--items", help="要抽的序号，按给的顺序编号：3,4 或 3-14")
    e.add_argument("--out", help="输出目录（项目/原文/）")
    e.add_argument("--start", type=int, default=1, help="第一个文件的编号（默认 1 → 第01章.txt）")
    e.add_argument("--unit", choices=UNITS, help=unit_help)
    e.add_argument("--force", action="store_true", help="覆盖已有文件")
    e.set_defaults(func=cmd_epub)

    h = sub.add_parser("html", help="从网页文件或 URL 抽取")
    h.add_argument("source", help="本地 .html 文件或 http(s) URL")
    h.add_argument("--out", required=True, help="输出文件（项目/原文/第01篇.txt）或目录（项目/原文/）")
    h.add_argument("--start", type=int, default=1, help="--out 是目录时用的编号")
    h.add_argument("--unit", choices=UNITS, help=unit_help)
    h.add_argument("--force", action="store_true")
    h.set_defaults(func=cmd_html)

    t = sub.add_parser("txt", help="整理纯文本，可按正则切成多个单元")
    t.add_argument("file")
    t.add_argument("--out", required=True, help="输出目录（项目/原文/），或单个 .txt 文件名")
    t.add_argument("--split", help="匹配单元标题行的正则，如 '^CHAPTER [IVXLC]+'")
    t.add_argument("--encoding", default="utf-8-sig")
    t.add_argument("--start", type=int, default=1)
    t.add_argument("--unit", choices=UNITS, help=unit_help)
    t.add_argument("--force", action="store_true")
    t.set_defaults(func=cmd_txt)

    pa = sub.add_parser("paste", help="把贴的文本（标准输入）存成原文")
    pa.add_argument("--out", default="原文", help="输出目录（默认 原文/）或单个 .txt 文件名")
    pa.add_argument("--para", choices=("auto", "blank", "line"), default="auto",
                    help="分段：auto 有空行按空行分、没有就每行一段（默认）；blank 按空行；line 每行一段")
    pa.add_argument("--start", type=int, default=1, help="--out 是目录时用的编号")
    pa.add_argument("--unit", choices=UNITS, help="单元名（只在项目根没有 设置.json 时用；默认 篇）")
    pa.add_argument("--force", action="store_true", help="覆盖已有文件")
    pa.set_defaults(func=cmd_paste)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
