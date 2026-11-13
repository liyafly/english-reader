#!/usr/bin/env python3
"""从 ECDICT 的 ecdict.csv 生成 lexicon.py 用的子集 ecdict-subset.tsv.gz。

用法：
  python3 make_ecdict_subset.py 路径/ecdict.csv [-o ecdict-subset.tsv.gz] [--top 30000]

ecdict.csv 从上游取（不随 skill 分发）：
  https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv

生成规则：
  1. 有效词：frq（COCA 名次）> 0 的行。按 frq 从小到大排，取前 --top 个（默认 30,000）。
     这些行保留 5 列：word、frq、bnc、exchange、phonetic。
  2. 附加的变形行：frq 为 0 或排在 --top 以外、exchange 里有 “0:原形” 且原形在第 1 步里、
     而原形自己的 exchange 没有列出这个变形的行（例如 were → be：be 的 exchange 只列了 was）。
     这些行只留 word 和 exchange（frq、bnc 写 0，phonetic 留空），供 lexicon.py 建“变形 → 原形”表。
  3. 词一律小写；同一个小写词出现多次时留 frq 最小的一行。
  4. 输出 UTF-8、制表符分隔、带表头，按 frq 排序（附加行排在最后，按词排序）；
     gzip 的时间戳写 0，同一份输入生成的文件逐字节相同。

只用 Python 标准库。
"""
import argparse
import csv
import gzip
import hashlib
import io
import re
import sys
from pathlib import Path

COLUMNS = ["word", "frq", "bnc", "exchange", "phonetic"]
FORM_KEYS = set("pdi3rts")  # exchange 里的变形类型；0 是原形，1 是变形类型说明


def to_int(s):
    try:
        return int(s or 0)
    except ValueError:
        return 0


def clean(s):
    return re.sub(r"[\t\r\n]+", " ", s or "").strip()


def exchange_items(ex):
    for item in (ex or "").split("/"):
        k, sep, v = item.partition(":")
        if sep and v:
            yield k.strip(), v.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成 ECDICT 子集")
    ap.add_argument("csv", help="上游的 ecdict.csv")
    ap.add_argument("-o", "--out", default=str(Path(__file__).resolve().parent / "ecdict-subset.tsv.gz"))
    ap.add_argument("--top", type=int, default=30000, help="按 frq 取前多少个有效词（默认 30000）")
    args = ap.parse_args(argv)

    csv.field_size_limit(sys.maxsize)
    ranked, forms = {}, {}
    with open(args.csv, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            w = clean(row.get("word")).lower()
            if not w:
                continue
            frq = to_int(row.get("frq"))
            rec = (frq, to_int(row.get("bnc")), clean(row.get("exchange")), clean(row.get("phonetic")))
            if frq > 0:
                old = ranked.get(w)
                if old is None or frq < old[0]:
                    ranked[w] = rec
            elif rec[2]:
                forms.setdefault(w, rec)

    top = sorted(ranked.items(), key=lambda kv: (kv[1][0], kv[0]))[: args.top]
    kept = dict(top)
    listed = set()  # (变形, 原形)：原形的 exchange 里已经列出的
    for w, rec in top:
        for k, v in exchange_items(rec[2]):
            if k in FORM_KEYS:
                listed.add((v.lower(), w))
    extra = []
    for w, rec in list(forms.items()) + [kv for kv in ranked.items() if kv[0] not in kept]:
        if w in kept:
            continue
        lemmas = [v.lower() for k, v in exchange_items(rec[2]) if k == "0"]
        if any(l in kept and (w, l) not in listed for l in lemmas):
            extra.append((w, (0, 0, rec[2], "")))
    extra.sort()

    buf = io.StringIO()
    wr = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    wr.writerow(COLUMNS)
    for w, (frq, bnc, ex, ph) in top + extra:
        wr.writerow([w, frq, bnc, ex, ph])
    data = buf.getvalue().encode("utf-8")
    out = Path(args.out)
    with open(out, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(data)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("有效词 %d 行（frq ≤ %d），附加变形行 %d 行，共 %d 行" % (
        len(top), top[-1][1][0] if top else 0, len(extra), len(top) + len(extra)))
    print("写入 %s：%s 字节（解压后 %s 字节）" % (out, format(out.stat().st_size, ","), format(len(data), ",")))
    print("sha256 %s" % digest)


if __name__ == "__main__":
    main()
