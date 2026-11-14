"""项目目录的结构：输出进 成品/（讲义在顶层，复习/、导入/ 分开）；旧项目（根目录已有输出、没有 成品/）照旧平铺；
tidy 把旧项目的输出挪进 成品/，不覆盖已有的。用 fixtures/demo_snapshot_v3/ 的副本，不排 PDF。"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "fixtures" / "demo_snapshot_v3"
BUILD = HERE.parent / "scripts" / "build.py"
NEW = ("成品/讲义.md", "成品/复习/难句本.md", "成品/导入/难句本.tsv", "成品/复习/单词本.md", "成品/导入/单词本.tsv")
FLAT = ("讲义.md", "难句本.md", "难句本.tsv", "单词本.md", "单词本.tsv")


def run(*args):
    r = subprocess.run([sys.executable, str(BUILD), *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class TestLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo"
        shutil.copytree(SNAP, self.root, ignore=shutil.ignore_patterns("成品"))

    def tearDown(self):
        self.tmp.cleanup()

    def build_all(self, *extra):
        for cmd in ("md", "sentences", "words"):
            code, out = run(cmd, self.root, *(a for a in extra if cmd != "md" or a != "--anki"))
            self.assertEqual(code, 0, out)

    def test_new_project_writes_into_outputs(self):
        self.build_all("--anki")
        for name in NEW + ("成品/导入/难句本-anki.tsv", "成品/导入/单词本-anki.tsv"):
            self.assertTrue((self.root / name).exists(), name)
        for name in FLAT:
            self.assertFalse((self.root / name).exists(), name)

    def test_out_dir_keeps_subfolders(self):
        out = Path(self.tmp.name) / "别处"
        self.build_all("--out", out)
        for name in NEW:
            self.assertTrue((out / name.removeprefix("成品/")).exists(), name)
        self.assertFalse((self.root / "成品").exists())

    def test_old_flat_project_stays_flat(self):
        (self.root / "讲义.md").write_text("旧的\n", encoding="utf-8")
        code, out = run("words", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("build.py tidy", out)
        self.assertTrue((self.root / "单词本.md").exists())
        self.assertFalse((self.root / "成品").exists())

    def test_tidy_moves_old_outputs(self):
        (self.root / "讲义.md").write_text("旧的\n", encoding="utf-8")
        self.build_all()
        (self.root / "分章").mkdir()
        (self.root / "分章" / "第01章.pdf").write_bytes(b"%PDF")
        code, out = run("tidy", self.root)
        self.assertEqual(code, 0, out)
        for name in NEW + ("成品/分章/第01章.pdf",):
            self.assertTrue((self.root / name).exists(), name)
        for name in FLAT + ("分章",):
            self.assertFalse((self.root / name).exists(), name)
        code, out = run("words", self.root)          # 挪完以后按新结构输出
        self.assertNotIn("build.py tidy", out)
        self.assertFalse((self.root / "单词本.md").exists())

    def test_tidy_does_not_overwrite(self):
        (self.root / "成品").mkdir()
        (self.root / "成品" / "讲义.md").write_text("新的\n", encoding="utf-8")
        (self.root / "讲义.md").write_text("旧的\n", encoding="utf-8")
        code, out = run("tidy", self.root)
        self.assertEqual(code, 1, out)
        self.assertEqual((self.root / "成品" / "讲义.md").read_text(encoding="utf-8"), "新的\n")
        self.assertTrue((self.root / "讲义.md").exists())

    def test_tidy_nothing_to_move(self):
        code, out = run("tidy", self.root)
        self.assertEqual(code, 0, out)
        self.assertIn("没有要挪的输出", out)


if __name__ == "__main__":
    unittest.main()
