"""第三版 demo 的冻结副本：fixtures/demo_snapshot_v3/（从 demo/ 复制；不放 PDF）。
在临时目录里重跑 check、md、sentences、words，输出要和副本里的逐字节相同；check 0 个问题。
另有第三版读后估页的校准（v3.light.md_estimate）：实排页数是用 chrome-headless-shell 排出、读回的。
demo/ 改了以后，整份重新复制到这里。"""
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "fixtures" / "demo_snapshot_v3"
BUILD = HERE.parent / "scripts" / "build.py"
OUTPUTS = ("成品/讲义.md", "成品/复习/难句本.md", "成品/导入/难句本.tsv", "成品/复习/单词本.md", "成品/导入/单词本.tsv")


def load_build():
    spec = importlib.util.spec_from_file_location("er_build_snap3", BUILD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestSnapshotV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "demo"
        shutil.copytree(SNAP, cls.root, ignore=shutil.ignore_patterns("成品"))
        cls.out = {}
        for cmd in ("check", "md", "sentences", "words"):
            r = subprocess.run([sys.executable, str(BUILD), cmd, str(cls.root)], capture_output=True, text=True)
            cls.out[cmd] = (r.returncode, r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_check(self):
        code, out = self.out["check"]
        self.assertEqual(code, 0, out)
        self.assertIn("问题 0 个", out)
        self.assertIn("提示 2 个", out)

    def test_outputs_identical(self):
        for cmd in ("md", "sentences", "words"):
            self.assertEqual(self.out[cmd][0], 0, self.out[cmd][1])
        for name in OUTPUTS:
            with self.subTest(name):
                self.assertEqual((self.root / name).read_bytes(), (SNAP / name).read_bytes())


class TestPostEstimateV3(unittest.TestCase):
    """第 2 章（轻读）和从它改出来的三个变体，估页和实排相差不超过 0.15 页。
    实排：下置排法，读后从第一页起，到「做完再看」前最后一行，按页面正文区折算成页数（校准时一共排了 6 个变体，最多差 0.10 页）。"""
    ACTUAL = {"原样": 2.87, "去掉句 4": 2.40, "只留精讲句 1、3": 2.12, "加一句 8 行的长难句": 3.47}

    def setUp(self):
        self.b = load_build()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo"
        shutil.copytree(SNAP, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def variants(self):
        md = (SNAP / "讲义" / "第02章.md").read_text(encoding="utf-8")
        sec = re.search(r"(?ms)^## 长难句\n.*?(?=^## )", md).group(0)
        head, *sents = re.split(r"(?m)^(?=### \d+\. )", sec)
        stuck = re.split(r"(?m)^(?=### \d+\. )", re.search(r"(?ms)^## 卡句\n.*", md).group(0))[1:]
        extra = re.sub(r"(?m)^- \*\*标记\*\*：.*\n", "", stuck[2])

        def keep(lst):
            return md.replace(sec, head + "".join(re.sub(r"^### \d+\. ", f"### {k}. ", s, count=1)
                                                  for k, s in enumerate(lst, 1)))
        return {"原样": md, "去掉句 4": keep(sents[:3]), "只留精讲句 1、3": keep([sents[0], sents[2]]),
                "加一句 8 行的长难句": keep(sents + [extra])}

    def test_calibration(self):
        self.b.V3_PDF[:] = [{"chunk_layout": "下置", "keep_rows": 12}]
        est = self.b.load_rules()["v3"]["light"]["md_estimate"]
        for name, md in self.variants().items():
            with self.subTest(name):
                (self.root / "讲义" / "第02章.md").write_text(md, encoding="utf-8")
                self.b.load_project(self.root)
                ch = self.b.parse_chapter(2)
                self.assertEqual(ch["errors"], [])
                self.assertAlmostEqual(self.b.post_estimate_v3(ch, est), self.ACTUAL[name], delta=0.15)


if __name__ == "__main__":
    unittest.main()
