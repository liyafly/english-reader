# scripts/data：词级数据

`lexicon.py` 离线定级用的三份数据。下载日期都是 2026-11-13，sha256 是本目录里文件的值。

| 文件 | 内容 | 版本 | 许可 | 大小 | sha256 |
| --- | --- | --- | --- | --- | --- |
| `cefrj-vocabulary-profile-1.5.csv` | CEFR-J 词表，A1–B2，约 7,800 行 | 1.5 | 注明引用即可免费用于研究和商业，版权属东京外国语大学投野研究室 | 233,214 字节 | `b0dd3c635f1c9a4fdf1490c7e5b7c48e8bbe55b652ad0c9860a95f98e10ae498` |
| `octanove-vocabulary-profile-c1c2-1.0.csv` | Octanove 词表，C1–C2，约 2,100 行 | 1.0 | CC BY-SA 4.0 | 46,462 字节 | `18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380` |
| `ecdict-subset.tsv.gz` | ECDICT 子集：词、COCA 名次、BNC 名次、变形、音标 | 由 ECDICT 生成，见下 | MIT | 658,706 字节（解压后 1,475,439 字节） | `fcd9a0042f3afb91c420ff49e62c97bcc84385628fdf529aef9148c46c81b800` |
| `make_ecdict_subset.py` | 生成上面子集的脚本 | — | 本 skill 自己的代码 | — | — |

三份数据都直接从各自的上游取。没有用 Readest 仓库里的任何代码或数据。

## CEFR-J Vocabulary Profile 1.5

- 仓库：https://github.com/openlanguageprofiles/olp-en-cefrj
- 下载地址：https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv
- 下载时仓库最新提交：`d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`（2020-03-25）
- 文件按原样保存，没有改动。列：`headword,pos,CEFR,CoreInventory 1,CoreInventory 2,Threshold`。`lexicon.py` 只用前三列；headword 里的 `/` 当作并列写法（如 `color/colour`）。

许可原文（仓库 README 的 “Terms of use”，2026-11-13 下载时核对）：

> CEFR-J vocabulary and grammar profile datasets can be used for research and commercial purposes with no charge, provided that you cite the dataset properly. The copyright belongs to Tono Laboratory at TUFS (Tokyo University of Foreign Studies). Neither CEFR-J nor Open Language Profiles is responsible or liable for any inaccuracies in the dataset or any damage resulting from using the dataset.

仓库 README 给的引用文本：

> The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies. Retrieved from http://www.cefr-j.org/download.html on 1/20/2020.

本 skill 用的引用写法：

> The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies. Retrieved from https://github.com/openlanguageprofiles/olp-en-cefrj (Open Language Profiles) on 2026-11-13.

## Octanove Vocabulary Profile C1/C2 1.0

- 仓库：https://github.com/openlanguageprofiles/olp-en-cefrj （作者 Octanove Labs，http://www.octanove.com/）
- 下载地址：https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/octanove-vocabulary-profile-c1c2-1.0.csv
- 下载时仓库最新提交：`d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`（2020-03-25，提交说明 “Add C1/C2 wordlist”）
- 文件按原样保存，没有改动。列：`headword,pos,CEFR,notes`。

许可原文（同一个 README）：

> The Octanove Vocabulary Profile for C1/C2 levels can be used under a [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/).

署名写法：

> Octanove Vocabulary Profile C1/C2, version 1.0, by Octanove Labs (http://www.octanove.com/), distributed by Open Language Profiles (https://github.com/openlanguageprofiles/olp-en-cefrj). Licensed under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).

CC BY-SA 4.0 要求署名并相同方式共享：本目录里的文件没有改动；如果以后改了这个文件再分发，改过的文件也要用 CC BY-SA 4.0，并写明改了什么。`lexicon.py` 只读它，不改它。

## ECDICT 子集（ecdict-subset.tsv.gz）

- 上游：https://github.com/skywind3000/ECDICT
- 下载地址：https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv （上游文件不随 skill 分发）
- 下载时 `ecdict.csv` 的最新提交：`9c46923fb81a2eb6c264a3a1689562ea7bc56b6a`（2026-10-20）
- 上游 `ecdict.csv`：66,009,548 字节，770,611 行，sha256 `d1ecbdf9ee2b920afb6f430ca6b6bb9f559588cf0dff86e04bd255f9390843cc`
- 上游 LICENSE 的 sha256：`f8552dd246f61a4e064569eae6194a01c6b3d63b03bf27c6ca863593c549ed0f`

许可：MIT。上游 LICENSE 原文：

```
MIT License

Copyright (c) 2025 Linwei

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### 生成方法

```sh
curl -A "english-reader/3.0" -o ecdict.csv https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv
python3 scripts/data/make_ecdict_subset.py ecdict.csv      # 默认写到 scripts/data/ecdict-subset.tsv.gz
```

规则（详见脚本开头）：

1. 有效词：`frq`（当代语料库 COCA 的名次）大于 0 的行，共 42,231 个。按 `frq` 从小到大取前 30,000 个，到名次 33,326 为止。保留 `word`、`frq`、`bnc`、`exchange`、`phonetic` 五列。
2. 附加 228 行变形：`exchange` 里写了 `0:原形`、原形在第 1 步里、原形自己的 `exchange` 又没列出它的行（如 were → be）。这些行只有词和 `exchange`。
3. 词一律小写；制表符分隔，带表头；gzip 时间戳写 0，同一份 `ecdict.csv` 生成的文件逐字节相同。

成品 658,706 字节，不到 3 MB，所以随 skill 分发，不用首次使用时下载。

### lexicon.py 怎么用它

- **变形 → 原形**：由 `exchange` 生成，三条清理规则在 `lexicon.build_lemma_map` 里（去掉比原形还常见的假变形；把链压平到最终原形；去掉循环）。
- **估级**：CEFR-J 和 Octanove 都没收的词，按 `frq` 名次估级，门槛见 `lexicon.EST_THRESHOLDS`，结果标“估”。
- **音标**：只作“参考”，不算核对过（ECDICT 的说明是“以英式音标为主”，来源混杂）。

## 联网来源（不在本目录）

`lexicon.py entry` 在系统词典查不到时会请求 dictionaryapi.dev（https://api.dictionaryapi.dev/api/v2/entries/en/WORD ，数据来自 Wiktionary，CC BY-SA 3.0），User-Agent 写 `english-reader/3.0`，两次请求至少间隔 1 秒，结果缓存在项目的 `.cache/lexicon/wiktionary/`，不进 skill。
