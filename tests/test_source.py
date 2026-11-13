"""scripts/source.py 的单元测试：如实的 UA、401/403/429 的提示（本地模拟，不联网）、抽取后的确认信息、
付费墙和残文提示、paste 子命令。

运行：python3 -m unittest tests/test_source.py
"""
import email.message
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import source as S  # noqa: E402

PARA = ("The Mole had been working very hard all the morning, spring-cleaning his little home. "
        "First with brooms, then with dusters; then on ladders and steps and chairs.")


def page(paras, extra=""):
    body = "".join("<p>%s</p>" % p for p in paras)
    return ("<html><head><title>t</title></head><body><nav><p>Home | About</p></nav>"
            "<article><h1>Chapter Two</h1>%s%s</article></body></html>" % (body, extra))


class FakeResponse:
    def __init__(self, data, charset="utf-8"):
        self.data = data
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "text/html; charset=%s" % charset

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run(argv, stdin_bytes=None):
    out, err = io.StringIO(), io.StringIO()
    patches = []
    if stdin_bytes is not None:
        patches.append(mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin_bytes), encoding="utf-8")))
    for p in patches:
        p.start()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            S.main([str(a) for a in argv])
    finally:
        for p in patches:
            p.stop()
    return out.getvalue(), err.getvalue()


class TestHonestFetch(unittest.TestCase):
    def test_no_browser_ua_in_scripts(self):
        text = (SCRIPTS / "source.py").read_text(encoding="utf-8")
        self.assertNotIn("BROWSER_UA", text)
        self.assertNotIn("Mozilla", text)
        self.assertEqual(S.USER_AGENT, "english-reader/3.0")

    def test_sends_honest_ua_once(self):
        seen = []

        def fake(req, timeout=None):
            seen.append(req)
            return FakeResponse(page([PARA]).encode("utf-8"))

        with mock.patch("urllib.request.urlopen", side_effect=fake):
            html = S.fetch_url("https://example.org/a")
        self.assertIn("spring-cleaning", html)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get_header("User-agent"), "english-reader/3.0")

    def test_blocked_codes_ask_user_and_do_not_retry(self):
        for code in (401, 402, 403, 429):
            with self.subTest(code=code):
                err = urllib.error.HTTPError("https://example.org/a", code, "nope", email.message.Message(), None)
                with mock.patch("urllib.request.urlopen", side_effect=err) as m:
                    with self.assertRaises(SystemExit) as cm:
                        S.fetch_url("https://example.org/a")
                self.assertEqual(m.call_count, 1)
                msg = str(cm.exception.code)
                self.assertIn("HTTP %d" % code, msg)
                self.assertIn("贴进对话", msg)
                self.assertIn("另存为 .html", msg)
                self.assertIn("不要换 User-Agent", msg)

    def test_403_through_html_command_writes_nothing(self):
        err = urllib.error.HTTPError("https://example.org/a", 403, "Forbidden", email.message.Message(), None)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "第01篇.txt"
            with mock.patch("urllib.request.urlopen", side_effect=err):
                with self.assertRaises(SystemExit) as cm:
                    run(["html", "https://example.org/a", "--out", out])
            self.assertFalse(out.exists())
        self.assertIn("网站拒绝了脚本访问", str(cm.exception.code))

    def test_local_server_403_and_ok(self):
        """本机起一个 HTTP 服务：/blocked 回 403，/ok 回正文。看实际发出去的 UA 和请求次数。"""
        import http.server
        import threading

        hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append((self.path, self.headers.get("User-Agent")))
                if self.path == "/blocked":
                    self.send_response(403)
                    self.end_headers()
                    return
                body = page([PARA] * 30).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        try:
            srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        except OSError as e:
            self.skipTest("本机不能起 HTTP 服务：%s" % e)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        # macOS 上 urllib 没有代理环境变量时会读系统代理设置；本机地址要直连，否则可能拿到代理的 504
        try:
            with mock.patch.dict(os.environ, {"no_proxy": "*"}), tempfile.TemporaryDirectory() as d:
                dst = Path(d) / "第01篇.txt"
                with self.assertRaises(SystemExit) as cm:
                    run(["html", base + "/blocked", "--out", dst])
                self.assertFalse(dst.exists())
                self.assertIn("HTTP 403", str(cm.exception.code))
                out, _ = run(["html", base + "/ok", "--out", dst])
                self.assertTrue(dst.is_file())
            self.assertIn("请用户确认没有抽残", out)
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(hits, [("/blocked", "english-reader/3.0"), ("/ok", "english-reader/3.0")])

    def test_network_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
            with self.assertRaises(SystemExit) as cm:
                S.fetch_url("https://example.org/a")
        self.assertIn("网络不通", str(cm.exception.code))


class TestExtractionReport(unittest.TestCase):
    def html_cmd(self, html_text):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.html"
            src.write_text(html_text, encoding="utf-8")
            dst = Path(d) / "out" / "第01篇.txt"
            out, _ = run(["html", src, "--out", dst])
            return out, dst.read_text(encoding="utf-8")

    def test_first_last_sentence_and_confirm(self):
        paras = [PARA] * 3 + ["It was the last paragraph. So he went home at last."]
        out, txt = self.html_cmd(page(paras * 10))
        self.assertIn("正文取自 <article>", out)
        self.assertIn("开头一句：The Mole had been working very hard all the morning, spring-cleaning his little home.",
                      out)
        self.assertIn("结尾一句：So he went home at last.", out)
        self.assertIn("请用户确认没有抽残", out)
        self.assertIn("（其中标题行 1 个）", out)
        self.assertNotIn("注意：", out)
        self.assertNotIn("Home | About", txt)

    def test_low_word_count_warns(self):
        out, _ = self.html_cmd(page([PARA]))
        self.assertIn("只抽到", out)
        self.assertIn("抽残", out)
        self.assertIn("贴进对话", out)

    def test_paywall_phrase_warns(self):
        out, _ = self.html_cmd(page([PARA] * 20 + ["Subscribe to continue reading this article."]))
        self.assertIn("付费墙", out)
        self.assertIn("Subscribe to continue", out)

    def test_paywall_words_inside_prose_do_not_warn(self):
        prose = PARA + " She was far too tired to continue reading, and subscribers only got the old news. " + PARA
        out, _ = self.html_cmd(page([prose] * 20))
        self.assertNotIn("注意：", out)

    def test_paywall_mark_with_few_words(self):
        out, _ = self.html_cmd(page([PARA], extra='<div class="article-paywall">x</div>'))
        self.assertIn("paywall 标记", out)

    def test_clip_long_sentence(self):
        s = "word " * 100
        c = S.clip(s, 60)
        self.assertLessEqual(len(c), 60)
        self.assertIn(" … ", c)


class TestPaste(unittest.TestCase):
    def test_blank_line_mode_merges_wrapped_lines(self):
        text = "First paragraph line one\ncontinues here.\n\nSecond paragraph.\n"
        self.assertEqual(S.paste_paragraphs(text), ["First paragraph line one continues here.", "Second paragraph."])

    def test_line_mode_when_no_blank_lines(self):
        text = "\n\nFirst paragraph.\nSecond paragraph.\nThird.\n\n"
        self.assertEqual(S.paste_paragraphs(text), ["First paragraph.", "Second paragraph.", "Third."])
        self.assertEqual(S.paste_paragraphs("a b\nc d\n\ne f", "line"), ["a b", "c d", "e f"])

    def test_writes_one_para_per_line_with_blank_between(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "原文"
            out, _ = run(["paste", "--out", out_dir], "“Hello,” he said.\r\nIt was late.\n".encode("utf-8"))
            f = out_dir / "第01篇.txt"
            self.assertEqual(f.read_text(encoding="utf-8"), "“Hello,” he said.\n\nIt was late.\n")
        self.assertIn("第01篇.txt", out)
        self.assertIn("词", out)

    def test_default_out_and_unit_from_settings(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            try:
                os.chdir(d)
                run(["paste"], b"One.\nTwo.\n")
                self.assertTrue((Path(d) / "原文" / "第01篇.txt").is_file())
                (Path(d) / "设置.json").write_text('{"unit": "章"}', encoding="utf-8")
                run(["paste", "--start", "2"], b"Three.\n")
                self.assertTrue((Path(d) / "原文" / "第02章.txt").is_file())
                with self.assertRaises(SystemExit):  # 不加 --force 不覆盖
                    run(["paste", "--start", "2"], b"Again.\n")
                run(["paste", "--start", "2", "--force"], b"Again.\n")
                self.assertEqual((Path(d) / "原文" / "第02章.txt").read_text(encoding="utf-8"), "Again.\n")
            finally:
                os.chdir(cwd)

    def test_empty_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as cm:
                run(["paste", "--out", Path(d) / "x.txt"], b"\n  \n")
        self.assertIn("没有文字", str(cm.exception.code))


class TestSentences(unittest.TestCase):
    def test_split_sentences(self):
        self.assertEqual(S.split_sentences("Mr. Toad came. “Hullo!” said Rat. He left"),
                         ["Mr. Toad came.", "“Hullo!” said Rat.", "He left"])
        self.assertTrue(S.is_heading("The Open Road"))
        self.assertFalse(S.is_heading("He left."))


if __name__ == "__main__":
    unittest.main()
