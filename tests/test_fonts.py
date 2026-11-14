"""PDF 的字体：设置.json 的 fonts 写成对象、build.py fonts、排 PDF 前的提示、check 的校验。
只生成 HTML，不排 PDF；取本机字体列表的地方都换成假的，不运行 swift、fc-list。"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
BUILD = HERE.parent / "scripts" / "build.py"
OUTPUTS = ("讲义.md", "难句本.md", "难句本.tsv", "单词本.md", "单词本.tsv")
FAKE = {"how": "测试", "fams": [("Songti SC", True), ("STKaiti", True), ("PingFang SC", True), ("Palatino", False),
                               ("Helvetica Neue", False), ("Apple Symbols", False)],
        "names": {"songti sc", "stkaiti", "pingfang sc", "palatino", "helvetica neue", "apple symbols"}}


def load_build():
    spec = importlib.util.spec_from_file_location("er_build_fonts", BUILD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Base(unittest.TestCase):
    SNAP = FIX / "demo_snapshot_v3"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / "demo"
        shutil.copytree(self.SNAP, self.root, ignore=shutil.ignore_patterns(*OUTPUTS))
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("ENGLISH_READER_FONTS", None)
        self.b = load_build()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def set_fonts(self, fonts):
        conf = self.root / "设置.json"
        cfg = json.loads(conf.read_text(encoding="utf-8"))
        cfg["fonts"] = fonts
        conf.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        self.b.load_project(self.root)

    def book_html(self):
        b = self.b
        b.FONT_DIR[:] = []
        nums = b.available()
        chs = b.load_units(nums)
        matches = {n: b.sentence_hits(c) for n, c in chs.items()}
        return b.page_html([chs[n] for n in nums], matches, None, {}, {}, {}, True)

    def sentence_html(self):
        self.b.FONT_DIR[:] = []
        nb = self.b.sibling("notebook")
        return nb.book_html(nb.sentence_book(self.b), self.b)


class TestSpec(Base):
    def test_chinese_and_english_keys(self):
        zh = self.b.font_spec({"宋体": "A", "楷体": "B", "黑体": "C", "英文": "D"})
        en = self.b.font_spec({"song": "A", "kai": "B", "hei": "C", "en": "D"})
        self.assertEqual(zh, en)
        self.assertEqual(zh["roles"]["song"], [("name", "A")])
        self.assertEqual(zh["problems"], [])

    def test_old_forms(self):
        self.assertEqual(self.b.font_spec(None), {"dir": None, "roles": {}, "problems": []})
        self.assertEqual(self.b.font_spec("字体")["dir"], "字体")
        self.assertEqual(self.b.font_spec({})["roles"], {})

    def test_list_and_file(self):
        self.b.load_project(self.root)
        (self.root / "fonts").mkdir()
        (self.root / "fonts" / "My Kai.ttf").write_bytes(b"x")
        spec = self.b.font_spec({"kai": ["fonts/My Kai.ttf", "Kaiti SC"], "目录": "fonts"})
        self.assertEqual(spec["roles"]["kai"], [("file", self.root / "fonts" / "My Kai.ttf"), ("name", "Kaiti SC")])
        self.assertEqual(spec["dir"], "fonts")
        self.assertEqual(spec["problems"], [])

    def test_problems(self):
        self.b.load_project(self.root)
        probs = self.b.font_spec({"宋": "A", "楷体": 3, "黑体": [], "英文": "没有.otf", "song": "A", "宋体": "B",
                                  "dir": "没有的目录", "kai": None, "en": "x/y"})["problems"]
        text = "\n".join(probs)
        for want in ("不认识「宋」", "「楷体」要写字体名", "「黑体」要写字体名", "没有.otf 不存在",
                     "「song」和「宋体」是同一项", "没有的目录 不存在"):
            self.assertIn(want, text)
        self.assertIn("「英文」和「en」是同一项", text)
        self.assertIn("fonts 要写", "\n".join(self.b.font_spec(3)["problems"]))


class TestHtml(Base):
    def test_default_unchanged(self):
        self.set_fonts(None)
        default = self.book_html()
        self.assertNotIn("设置.json 的 fonts", default)
        self.set_fonts({})
        self.assertEqual(self.book_html(), default)
        self.set_fonts({"目录": "."})          # 只写目录：和原来的目录写法一样，不加覆盖
        self.assertEqual(self.b.font_override_css(), "")

    def test_names(self):
        self.set_fonts({"宋体": "STSong", "楷体": ["STKaiti", "Kaiti SC"], "黑体": "Hiragino Sans GB", "英文": "Palatino"})
        page = self.book_html()
        css = page[page.index("/* 设置.json 的 fonts */"):]
        self.assertIn('--body:"Palatino","STSong",serif', css)
        self.assertIn('--en:"Palatino","STSong",serif', css)
        self.assertIn('--kai:"Palatino","STKaiti","Kaiti SC",serif', css)
        self.assertIn('--sans:"Helvetica Neue","Hiragino Sans GB",sans-serif', css)
        self.assertIn('@top-left{font-family:"Hiragino Sans GB",sans-serif}', css)
        self.assertIn('@bottom-center{font-family:"Palatino",serif}', css)
        self.assertIn('.zq{font-family:"STSong",serif}', css)
        self.assertIn('p.tr .zq{font-family:"STKaiti","Kaiti SC",serif}', css)
        self.assertLess(page.index("/* 设置.json 的 fonts */"), page.index("@page c1-"))   # 在默认 CSS 之后

    def test_partial_keeps_defaults(self):
        self.set_fonts({"hei": "Microsoft YaHei"})
        css = self.b.font_override_css()
        self.assertIn('--body:"Iowan Old Style","Charter","Georgia","StudySong","Songti SC",serif', css)
        self.assertIn('--sans:"Helvetica Neue","Microsoft YaHei",sans-serif', css)

    def test_generic_and_escape(self):
        self.set_fonts({"英文": ['My "Font"', "serif"]})
        css = self.b.font_override_css()
        self.assertIn('@bottom-center{font-family:"My \\"Font\\"",serif}', css)
        self.assertNotIn('"serif"', css)

    def test_file_font_face(self):
        f = self.root / "书 宋.otf"
        f.write_bytes(b"x")
        self.set_fonts({"宋体": ["书 宋.otf", "Songti SC"]})
        css = self.b.font_override_css()
        self.assertIn(f'@font-face{{font-family:"er-song-1";src:url("{f.as_uri()}")', css)
        self.assertIn("%20", f.as_uri())
        self.assertIn('.zq{font-family:"er-song-1","Songti SC",serif}', css)

    def test_sentence_book(self):
        self.set_fonts(None)
        default = self.sentence_html()
        self.assertNotIn("设置.json 的 fonts", default)
        self.set_fonts({"song": "STSong"})
        page = self.sentence_html()
        self.assertIn('.zq{font-family:"STSong",serif}', page)
        self.assertEqual(page.replace(self.b.font_override_css(), ""), default)


class TestSystemFonts(Base):
    def test_no_list(self):
        """拿不到字体列表：fonts 说明手写名字；排 PDF 前不提示本机有没有。"""
        self.set_fonts({"宋体": "SimSun"})
        with mock.patch.object(self.b, "swift_cmd", return_value=None), \
                mock.patch.object(self.b.shutil, "which", return_value=None):
            out = StringIO()
            with redirect_stdout(out):
                self.b.cmd_fonts([])
                self.b.font_warnings()
        text = out.getvalue()
        self.assertIn("取不到本机的字体列表", text)
        self.assertIn("宋体  SimSun", text)
        self.assertNotIn("!", text)

    def test_listing_and_missing(self):
        self.set_fonts({"宋体": "SimSun", "英文": "Palatino"})
        out = StringIO()
        with mock.patch.object(self.b, "system_fonts", return_value=FAKE), \
                mock.patch.object(self.b, "swift_cmd", return_value=None), redirect_stdout(out):
            self.b.cmd_fonts([])
            self.b.font_warnings()
        text = out.getvalue()
        self.assertIn("宋体（1）\n  Songti SC", text)
        self.assertIn("英文衬线（1）\n  Palatino", text)
        self.assertIn("英文无衬线（1）\n  Helvetica Neue", text)
        self.assertIn("其他（1）\n  Apple Symbols", text)
        self.assertIn("宋体  !SimSun\n", text)
        self.assertIn("英文  Palatino\n", text)
        self.assertIn("楷体  StudyKai, !Kaiti SC, STKaiti  （默认）", text)
        self.assertIn("宋体「SimSun」本机没有", text)
        self.assertNotIn("Palatino」本机没有", text)

    def test_swift_match(self):
        """macOS 有 swift 时按 CoreText 的匹配判断有没有。"""
        self.set_fonts({"黑体": ["PingFang SC", "Nope"]})
        with mock.patch.object(self.b.sys, "platform", "darwin"), \
                mock.patch.object(self.b, "swift_cmd", return_value=["fontlist"]), \
                mock.patch.object(self.b, "run_quiet", return_value='{"Nope": false, "PingFang SC": true}') as run:
            self.assertEqual(self.b.font_lost(["PingFang SC", "Nope", "serif", "a.ttf", "StudySong"]), {"Nope"})
        run.assert_called_once_with(["fontlist", "Nope", "PingFang SC"])

    def test_fc_list(self):
        fc = {":": "Noto Serif CJK SC,Noto Serif CJK SC SemiBold\nDejaVu Serif\n.Hidden\n",
              ":lang=zh-cn": "Noto Serif CJK SC,Noto Serif CJK SC SemiBold\n"}
        with mock.patch.object(self.b.sys, "platform", "linux"), \
                mock.patch.object(self.b.shutil, "which", return_value="/usr/bin/fc-list"), \
                mock.patch.object(self.b, "run_quiet", side_effect=lambda cmd, timeout=60: fc[cmd[1]]):
            got = self.b.list_fonts(slow=True)
        self.assertEqual(got["fams"], [("DejaVu Serif", False), ("Noto Serif CJK SC", True)])
        self.assertIn("noto serif cjk sc semibold", got["names"])

    def test_groups(self):
        g = self.b.font_group
        self.assertEqual(g("FZSongKeBenXiuKaiS", True), "楷体")
        self.assertEqual(g("Noto Sans CJK SC", None), "黑体")
        self.assertEqual(g("SimSun", None), "宋体")
        self.assertEqual(g("Hiragino Sans", False), "英文无衬线")
        self.assertEqual(g("Weibei SC", True), "其他中文")
        self.assertEqual(g("Georgia", False), "英文衬线")

    def test_fonts_command_without_project(self):
        r = subprocess.run([sys.executable, "-B", str(BUILD), "fonts"], capture_output=True, text=True,
                           cwd=self.tmp.name, env={**os.environ, "PATH": "/nonexistent"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("的 PDF 字体", r.stdout)


class TestCheck(Base):
    def run_check(self):
        r = subprocess.run([sys.executable, "-B", str(BUILD), "check", str(self.root)], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_v3_problem(self):
        self.set_fonts({"宋体": "Songti SC", "粗体": "X", "英文": "没有.ttf"})
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("全部单元 设置：fonts 里不认识「粗体」", out)
        self.assertIn("问题 2 个", out)
        self.assertIn("设置 2", out)

    def test_v3_ok(self):
        self.set_fonts({"宋体": "Songti SC", "kai": ["Kaiti SC"]})
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("设置", out)


class TestCheckV2(TestCheck):
    SNAP = FIX / "demo_snapshot"

    def test_v3_problem(self):
        pass

    def test_v2_hint_only(self):
        self.set_fonts(None)
        base = self.run_check()
        self.set_fonts({"粗体": "X"})
        code, out = self.run_check()
        self.assertEqual(code, base[0])
        self.assertIn("提示 全部单元 设置：fonts 里不认识「粗体」", out)
        self.assertNotIn("全部单元 设置：fonts", out.replace("提示 全部单元 设置：fonts", ""))


if __name__ == "__main__":
    unittest.main()
