# 《柳林风声》第 1–2 章 · B1

english-reader 做完的一个项目，也是写讲义时照着学的样板：第 1 章精读，第 2 章轻读，第三版格式（`设置.json` 写 `"format": 3`）。

## 从这里开始

- 讲义：[成品/讲义-全本.pdf](成品/讲义-全本.pdf)（合订的小册子），或 [成品/讲义-全本.md](成品/讲义-全本.md)；每章一份：[讲义-第01章.pdf](成品/讲义-第01章.pdf)、[讲义-第02章.pdf](成品/讲义-第02章.pdf)
- 难句本：[成品/难句本.pdf](成品/难句本.pdf)、[成品/难句本.md](成品/难句本.md)：先自己拆，再看对照
- 单词本：[成品/单词本.md](成品/单词本.md)
- 导入 Anki：[成品/导入/](成品/导入/) 里的 难句本-anki.tsv、单词本-anki.tsv（笔记类型选问答题）；别的工具用 难句本.tsv、单词本.tsv
- 读的时候卡住的句子记进 [卡句.txt](卡句.txt)

## 目录

| 位置 | 是什么 |
| --- | --- |
| `设置.json` | 格式（3）、卡片 id 前缀（willows）、书名、作者、单元和模式（第 1 章精读，其余默认轻读）、读者水平 B1、文体小说 |
| `卡句.txt` | 读的时候卡住的句子，3 行（示例） |
| `原文/` | 两章的纯文本，各约 4,300 词，引文核对的底本 |
| `源稿/` | 讲义的源稿，写、改都在这里：`前言.md`（出处、缩写、语法术语、句子结构、人名和译名）；`第01章.md` 精读（6 个长难句、10 个词条、一个语法点、7 个赏析点、写作、10 道自测）；`第02章.md` 轻读（4 个长难句、2 道理解题、2 个词条、复述、3 个卡句） |
| `成品/` | 脚本生成的，不要手改，文件名自带类别：讲义-全本、讲义-第NN章、难句本、单词本，`导入/` 是 TSV |
| `制作记录/计划与检查.md` | 摸底、计划、标签台账、检查和审稿记录 |

重新生成（输出都进 `成品/`）：

```
python3 ../scripts/build.py check .     # 检查
python3 ../scripts/build.py stuck .     # 卡句.txt 每句在原文哪里、讲了没有
python3 ../scripts/build.py sentences . # 难句本.md、难句本.tsv（加 --pdf 另出 难句本.pdf）
python3 ../scripts/build.py words .     # 单词本.md、单词本.tsv
python3 ../scripts/build.py md .        # 讲义-全本.md
python3 ../scripts/build.py pdf all .   # 讲义-全本.pdf 和 讲义-第NN章.pdf，需要 macOS 和 chrome-headless-shell（../scripts/renderer.py install）
```

`讲义-全本.pdf` 在 macOS 上用系统字体排出（正文 Iowan Old Style，中文宋体、楷体，标签 Helvetica Neue），字体按各自的嵌入许可以子集嵌入。换一台机器重排，字体可能不同，版式相同。

## 原文的来源和版权

- 作品：Kenneth Grahame, *The Wind in the Willows*，1908 年在英国出版。
- 底本：Standard Ebooks 版（<https://standardebooks.org/ebooks/kenneth-grahame/the-wind-in-the-willows>），它依据 Project Gutenberg 的转录和 HathiTrust 的扫描本校订。
- 版权：1931 年以前出版的作品在美国已进入公有领域。Grahame 1932 年去世，在按作者终身加 70 年计算的国家（英国、欧盟等）也已进入公有领域。Standard Ebooks 对自己的校订、排版和元数据按 CC0 放弃了全部权利。这不是法律意见。
- 处理：第 1 章从电子书抽出正文，第 2 章用 `source.py html` 从 Standard Ebooks 网站的章节页抽出。都是每段一行，段落之间空一行；去掉了零宽字符（Standard Ebooks 在破折号前后加的 word joiner）。没有改动任何词和标点。开头两行是章号和章名。第 2 章里的《鸭子小调》每行诗单独一行。

讲义、译文、例句、复述参考和自测题是自写的，AI 协助。

