"""scripts/renderer.py 的单元测试：装、查、删 chrome-headless-shell。不联网、不下载、不运行它：
清单、下载、zip 都在本地拼出来；urlopen 和 subprocess.run（xattr、sysctl）都换掉了，装的位置换成临时目录。

运行：python3 -m unittest tests/test_renderer.py
"""
import email.message
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))

import renderer as R  # noqa: E402

V = "157.0.8103.78"
OLD = "150.0.7000.1"
BASE = "https://storage.googleapis.com/chrome-for-testing-public/"
PLATS = ("linux64", "mac-arm64", "mac-x64", "win32", "win64")


def url_for(plat, v=V):
    return f"{BASE}{v}/{plat}/chrome-headless-shell-{plat}.zip"


def manifest(v=V, **urls):
    """和官方清单一样的结构；urls 可以换掉某个平台的地址（键里的 - 写成 _）。"""
    shell = [{"platform": p, "url": urls.get(p.replace("-", "_"), url_for(p, v))} for p in PLATS]
    chrome = [{"platform": p, "url": f"{BASE}{v}/{p}/chrome-{p}.zip"} for p in PLATS]
    return {"timestamp": "2026-11-12T00:00:00.000Z", "channels": {
        "Stable": {"channel": "Stable", "version": v, "revision": "1500000",
                   "downloads": {"chrome": chrome, "chrome-headless-shell": shell}},
        "Beta": {"channel": "Beta", "version": "158.0.8200.10", "revision": "1510000",
                 "downloads": {"chrome-headless-shell": [{"platform": "mac-arm64", "url": url_for("mac-arm64", "158.0.8200.10")}]}}}}


def entry(name, mode):
    info = zipfile.ZipInfo(name)
    info.external_attr = mode << 16
    return info


def make_zip(entries):
    """entries：[(名字, 内容, 权限)]，权限带文件类型位（0o100644 普通文件、0o120777 软链接、0o040755 目录）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data, mode in entries:
            z.writestr(entry(name, mode), data)
    return buf.getvalue()


def shell_zip(plat="mac-arm64", extra=(), exe=True):
    """像官方压缩包：chrome-headless-shell-<平台>/ 下面是程序和几个库。程序存成 0644，装的时候要加执行权限。"""
    top = f"chrome-headless-shell-{plat}/"
    entries = [(top, b"", 0o040755)]
    if exe:
        entries.append((top + "chrome-headless-shell", b"\xcf\xfa\xed\xfe fake mach-o", 0o100644))
    entries += [(top + "libEGL.dylib", b"lib", 0o100644), (top + "headless_lib_data.pak", b"pak", 0o100644)]
    return make_zip(entries + list(extra))


class FakeResponse:
    """urlopen 的返回值。cut：只给这么多字节就像断线一样返回空；fail：读到 fail_at 字节时抛这个异常。"""

    def __init__(self, data, url, length=True, cut=None, fail=None, fail_at=0):
        self.data, self.url, self.pos = data, url, 0
        self.cut, self.fail, self.fail_at = cut, fail, fail_at
        self.headers = email.message.Message()
        if length:
            self.headers["Content-Length"] = str(len(data))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def geturl(self):
        return self.url

    def read(self, n=-1):
        if self.fail is not None and self.pos >= self.fail_at:
            raise self.fail
        end = len(self.data) if self.cut is None else self.cut
        if n is None or n < 0:
            n = end - self.pos
        if self.fail is not None:
            n = min(n, max(self.fail_at - self.pos, 1))
        chunk = self.data[self.pos:min(self.pos + n, end)]
        self.pos += len(chunk)
        return chunk


class Net:
    """代替 urlopen：网址 → 返回响应的函数（或要抛的异常）。记下每次的 Request。"""

    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        route = self.routes.get(req.full_url)
        if route is None:
            raise AssertionError(f"测试没准备这个网址：{req.full_url}")
        if isinstance(route, BaseException):
            raise route
        return route()

    @property
    def urls(self):
        return [r.full_url for r in self.requests]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "Library" / "Caches" / "english-reader" / "chrome-headless-shell"
        self.root.parent.mkdir(parents=True)          # ~/Library/Caches/english-reader 本来就可能有（排版的配置目录也在这里）
        self.translated, self.xattrs, self.sys_calls = "0\n", "", []
        for p in (mock.patch.object(R, "ROOT", self.root),
                  mock.patch.object(R.sys, "platform", "darwin"),
                  mock.patch.object(R.platform, "machine", return_value="arm64"),
                  mock.patch.object(R.urllib.request, "urlopen", side_effect=AssertionError("测试里不许联网")),
                  mock.patch.object(R.subprocess, "run", self.fake_run)):
            p.start()
            self.addCleanup(p.stop)

    def fake_run(self, cmd, **kw):
        """代替 subprocess.run：只认 sysctl 和 xattr，别的命令一律不许运行。"""
        self.sys_calls.append(cmd)
        if cmd[:2] == ["sysctl", "-n"]:
            return subprocess.CompletedProcess(cmd, 0, self.translated, "")
        if cmd[:2] == ["xattr", "-r"] and len(cmd) == 3:
            return subprocess.CompletedProcess(cmd, 0, self.xattrs, "")
        if cmd[:4] == ["xattr", "-r", "-d", "com.apple.quarantine"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise AssertionError(f"测试里不许运行：{cmd}")

    def net(self, routes):
        n = Net(routes)
        p = mock.patch.object(R.urllib.request, "urlopen", n)
        p.start()
        self.addCleanup(p.stop)
        return n

    def online(self, data=None, plat="mac-arm64", m=None, **kw):
        """清单和下载都准备好：data 是下载到的字节（默认一个正常的压缩包），kw 交给 FakeResponse。"""
        m = manifest() if m is None else m
        data = shell_zip(plat) if data is None else data
        url = url_for(plat)
        final = kw.pop("final_url", url)
        return self.net({R.MANIFEST_URL: lambda: FakeResponse(json.dumps(m).encode(), R.MANIFEST_URL),
                         url: lambda: FakeResponse(data, final, **kw)})

    def run_main(self, *args):
        """(退出码, 标准输出, 标准错误)。SystemExit 带的说明算进标准错误、退出码算 1。"""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = R.main(list(args))
            except SystemExit as e:
                code = e.code
                if isinstance(code, str):
                    err.write(code)
                    code = 1
        return code, out.getvalue(), err.getvalue()

    def put_version(self, v, plat="mac-arm64", exe=True):
        """摆一个“已经装好”的版本（假的程序，不运行）。"""
        d = self.root / v / f"chrome-headless-shell-{plat}"
        d.mkdir(parents=True)
        f = d / "chrome-headless-shell"
        if exe:
            f.write_text("#!/bin/sh\nexit 1\n")
            f.chmod(0o755)
        return f

    def files(self):
        """假的家目录里多出来的所有东西（不算事先建好的 Library/Caches/english-reader 这几层）。"""
        chain = {str(p.relative_to(self.home)) for p in (self.root.parent, *self.root.parent.parents) if p != self.home
                 and self.home in p.parents}
        return sorted(x for x in (str(p.relative_to(self.home)) for p in self.home.rglob("*")) if x not in chain)

    def versions(self):
        return sorted(p.name for p in self.root.iterdir()) if self.root.exists() else []


# ---------- 平台 ----------

class TestPlatform(Base):
    def test_arm64(self):
        self.assertEqual(R.platform_name(), "mac-arm64")

    def test_intel(self):
        with mock.patch.object(R.platform, "machine", return_value="x86_64"):
            self.assertEqual(R.platform_name(), "mac-x64")

    def test_rosetta_python_gets_arm64(self):
        self.translated = "1\n"
        with mock.patch.object(R.platform, "machine", return_value="x86_64"):
            self.assertEqual(R.platform_name(), "mac-arm64")

    def test_unknown_chip(self):
        with mock.patch.object(R.platform, "machine", return_value="ppc"):
            with self.assertRaises(SystemExit) as cm:
                R.platform_name()
        self.assertIn("ppc", str(cm.exception.code))

    def test_pick_stable_for_platform(self):
        self.assertEqual(R.pick(manifest(), "mac-arm64"), (V, url_for("mac-arm64")))
        self.assertEqual(R.pick(manifest(), "mac-x64"), (V, url_for("mac-x64")))

    def test_intel_install_downloads_x64(self):
        net = self.online(plat="mac-x64")
        with mock.patch.object(R.platform, "machine", return_value="x86_64"):
            code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        self.assertEqual(net.urls, [R.MANIFEST_URL, url_for("mac-x64")])
        self.assertTrue(os.access(self.root / V / "chrome-headless-shell-mac-x64" / "chrome-headless-shell", os.X_OK))


# ---------- 清单 ----------

class TestManifest(Base):
    def test_format_changed(self):
        stable = lambda **d: {"channels": {"Stable": {"version": V, **d}}}     # noqa: E731
        bad = [{}, [], "x", {"channels": {}}, {"channels": {"Stable": None}}, stable(),
               stable(downloads={"chrome": []}), stable(downloads={"chrome-headless-shell": "x"}),
               stable(downloads={"chrome-headless-shell": [{"platform": "linux64", "url": url_for("linux64")}]}),
               stable(downloads={"chrome-headless-shell": [{"platform": "mac-arm64"}]}),
               stable(downloads={"chrome-headless-shell": ["mac-arm64"]})]
        for m in bad:
            with self.assertRaises(SystemExit, msg=m) as cm:
                R.pick(m, "mac-arm64")
            self.assertIn("格式变了", str(cm.exception.code))

    def test_bad_version(self):
        for v in ("../../evil", "157", "157.0.8103.78/../x", 157, None):
            m = manifest()
            m["channels"]["Stable"]["version"] = v
            with self.assertRaises(SystemExit, msg=v):
                R.pick(m, "mac-arm64")

    def test_not_json(self):
        self.net({R.MANIFEST_URL: lambda: FakeResponse(b"<html>moved</html>", R.MANIFEST_URL)})
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("不是 JSON", err)
        self.assertEqual(self.files(), [])

    def test_network_down(self):
        net = self.net({R.MANIFEST_URL: urllib.error.URLError("nodename nor servname provided")})
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("连不上官方下载清单", err)
        self.assertIn("网络通了再运行一次", err)
        self.assertEqual(net.urls, [R.MANIFEST_URL])
        self.assertEqual(self.files(), [])                       # 连目录都没建

    def test_http_error(self):
        self.net({R.MANIFEST_URL: urllib.error.HTTPError(R.MANIFEST_URL, 503, "Unavailable", {}, None)})
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("HTTP 503", err)
        self.assertEqual(self.files(), [])

    def test_user_agent(self):
        net = self.online()
        self.assertEqual(self.run_main("install")[0], 0)
        self.assertEqual(len(net.requests), 2)
        for req in net.requests:
            self.assertEqual(req.get_header("User-agent"), "english-reader/3.0")


# ---------- 下载地址白名单 ----------

class TestWhitelist(Base):
    def test_official_urls(self):
        for p in PLATS:
            self.assertEqual(R.check_url(url_for(p)), url_for(p))

    def test_rejects(self):
        for url in ("http://storage.googleapis.com/chrome-for-testing-public/x.zip",
                    "https://storage.googleapis.com/other-bucket/x.zip",
                    "https://storage.googleapis.com.evil.example/chrome-for-testing-public/x.zip",
                    "https://evil.example/chrome-for-testing-public/x.zip",
                    "https://storage.googleapis.com@evil.example/chrome-for-testing-public/x.zip",
                    "https://storage.googleapis.com:8443/chrome-for-testing-public/x.zip",
                    "https://storage.googleapis.com/chrome-for-testing-public/../other-bucket/x.zip",
                    "https://storage.googleapis.com/chrome-for-testing-public/%2e%2e/other-bucket/x.zip",
                    "https://storage.googleapis.com/chrome-for-testing-public/x.zip?alt=media",
                    "https://storage.googleapis.com/chrome-for-testing-public/x.zip#frag",
                    "https://storage.googleapis.com/chrome-for-testing-public/x .zip",
                    "https://storage.googleapis.com/chrome-for-testing-public/x\n.zip",
                    "", None, 123):
            with self.assertRaises(SystemExit, msg=url) as cm:
                R.check_url(url)
            self.assertIn("chrome-for-testing-public", str(cm.exception.code))

    def test_install_refuses_bad_url(self):
        net = self.online(m=manifest(mac_arm64="https://evil.example/chrome-headless-shell-mac-arm64.zip"))
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("不是 Chrome for Testing 官方存储", err)
        self.assertEqual(net.urls, [R.MANIFEST_URL])             # 一个字节都没下载
        self.assertEqual(self.files(), [])

    def test_redirect_elsewhere(self):
        self.online(final_url="https://evil.example/x.zip")
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("evil.example", err)
        self.assertEqual(self.files(), [])


# ---------- 解压：防路径穿越 ----------

class TestZipSafety(Base):
    TOP = "chrome-headless-shell-mac-arm64/"

    def extract(self, entries):
        case = self.home / "case"
        dest = case / "dest"
        dest.mkdir(parents=True)
        z = case / "x.zip"
        z.write_bytes(make_zip(entries))
        try:
            R.extract(z, dest)
        finally:
            z.unlink()
        return case, dest

    def test_rejects_traversal(self):
        cases = {
            "..": [("../evil.txt", b"x", 0o100644)],
            "藏在中间的 ..": [(self.TOP + "../../evil.txt", b"x", 0o100644)],
            "绝对路径": [("/tmp/evil.txt", b"x", 0o100644)],
            "反斜杠绝对路径": [("\\evil.txt", b"x", 0o100644)],
            "盘符": [("C:/evil.txt", b"x", 0o100644)],
            "软链接指到绝对路径": [(self.TOP + "l", b"/etc", 0o120777)],
            "软链接指到外面": [(self.TOP + "l", b"../../outside", 0o120777)],
            "软链接接力指到外面": [("x", b".", 0o120777), ("x/y/l", b"../..", 0o120777)],
            "先软链接再从它写出去": [(self.TOP + "l", b"../..", 0o120777), (self.TOP + "l/evil.txt", b"x", 0o100644)],
        }
        for why, entries in cases.items():
            with self.subTest(why):
                with self.assertRaises(SystemExit) as cm:
                    self.extract(entries)
                self.assertIn("不安全的路径", str(cm.exception.code))
                self.assertEqual(sorted(p.name for p in (self.home / "case").iterdir()), ["dest"])    # 外面什么都没多
                self.assertFalse((self.home / "evil.txt").exists())
                shutil.rmtree(self.home / "case")

    def test_clash_is_reported_not_traceback(self):
        # 同名的文件和目录、文件后面又来同名软链接：说明解不开，不抛 Python 的错
        for entries in ([(self.TOP + "a", b"x", 0o100644), (self.TOP + "a/b", b"y", 0o100644)],
                        [(self.TOP + "a", b"x", 0o100644), (self.TOP + "a", b"b", 0o120777)]):
            with self.subTest(entries=entries):
                with self.assertRaises(SystemExit) as cm:
                    self.extract(entries)
                self.assertIn("什么都没装", str(cm.exception.code))
                shutil.rmtree(self.home / "case")

    def test_inner_symlink_and_permissions(self):
        case, dest = self.extract([(self.TOP, b"", 0o040755), (self.TOP + "A/f", b"data", 0o100644),
                                   (self.TOP + "Current", b"A", 0o120777), (self.TOP + "tool", b"#!", 0o104755),
                                   (self.TOP + "readonly", b"x", 0o100444)])
        top = dest / self.TOP
        self.assertEqual(os.readlink(top / "Current"), "A")     # 包里的软链接照建（只指里面）
        self.assertEqual((top / "Current" / "f").read_bytes(), b"data")
        mode = (top / "tool").stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)
        self.assertFalse(mode & stat.S_ISUID)                   # 只取 rwx 位，setuid 不带过来
        self.assertEqual(stat.S_IMODE((top / "readonly").stat().st_mode), 0o644)     # 自己总能读写（删得掉）

    def test_install_with_evil_zip_leaves_nothing(self):
        self.online(data=shell_zip(extra=[("../../../../evil.txt", b"x", 0o100644)]))
        code, out, err = self.run_main("install")
        self.assertEqual(code, 1)
        self.assertIn("不安全的路径", err)
        self.assertEqual(self.files(), [])


# ---------- install ----------

class TestInstall(Base):
    def test_fresh_install(self):
        net = self.online()
        code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        exe = self.root / V / "chrome-headless-shell-mac-arm64" / "chrome-headless-shell"
        for s in (f"chrome-headless-shell {V}（Stable，mac-arm64）", f"来源：{url_for('mac-arm64')}",
                  f"装到：{self.root / V}/", "大小：0.0 MB", f"装好了：{exe}"):
            self.assertIn(s, out)
        self.assertLess(out.index("来源："), out.index("大小："))     # 先说清楚再下载
        self.assertEqual(net.urls, [R.MANIFEST_URL, url_for("mac-arm64")])
        self.assertTrue(os.access(exe, os.X_OK))                   # 加了执行权限
        self.assertEqual(R.installed(), (V, exe))
        self.assertEqual(self.versions(), [V])                     # 临时文件、临时目录都不留
        xattr = [c for c in self.sys_calls if c[0] == "xattr"]
        self.assertEqual(len(xattr), 1)                            # 查过隔离属性；没有就不去
        self.assertNotIn("-d", xattr[0])

    def test_quarantine_removed(self):
        self.xattrs = "chrome-headless-shell-mac-arm64/chrome-headless-shell: com.apple.quarantine\n"
        self.online()
        code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        removes = [c for c in self.sys_calls if c[:4] == ["xattr", "-r", "-d", "com.apple.quarantine"]]
        self.assertEqual(len(removes), 1)
        self.assertIn("已去掉隔离属性", out)

    def test_same_version_already_installed(self):
        exe = self.put_version(V)
        self.put_version(OLD)
        net = self.online()
        code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        self.assertIn(f"已经装好 chrome-headless-shell {V}", out)
        self.assertIn(str(exe), out)
        self.assertEqual(net.urls, [R.MANIFEST_URL])              # 只看了清单，没下载
        self.assertEqual(self.versions(), [V])                     # 旧版本删了
        self.assertIn(f"删掉旧版本：{OLD}", out)

    def test_old_version_replaced(self):
        self.put_version(OLD)
        (self.root / ".download-abc.zip").write_bytes(b"half")    # 上次被强行中止留下的
        (self.root / ".staging-abc").mkdir()
        self.online()
        code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.versions(), [V])
        self.assertIn(f"删掉旧版本：{OLD}", out)
        self.assertEqual(R.installed()[0], V)

    def test_broken_same_version_reinstalled(self):
        self.put_version(V, exe=False)                             # 目录在，程序不在
        net = self.online()
        code, out, err = self.run_main("install")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(net.urls), 2)
        self.assertEqual(R.installed()[0], V)

    def check_nothing_left(self, code, err, keep_old):
        self.assertEqual(code, 1)
        self.assertIn("什么都没装", err)
        if keep_old:
            self.assertEqual(self.versions(), [OLD])               # 原来装的不动，临时文件不留
            self.assertEqual(R.installed()[0], OLD)
        else:
            self.assertEqual(self.files(), [])                     # 连 chrome-headless-shell 目录都不留

    def test_download_cut_short(self):
        data = shell_zip()
        for keep_old in (False, True):
            with self.subTest(keep_old=keep_old):
                if keep_old:
                    self.put_version(OLD)
                self.online(data=data, cut=len(data) // 2)        # 服务器说了大小，只给了一半就断了
                code, out, err = self.run_main("install")
                self.assertIn("下载中断", err)
                self.check_nothing_left(code, err, keep_old)

    def test_download_connection_reset(self):
        data = shell_zip()
        self.put_version(OLD)
        self.online(data=data, fail=ConnectionResetError("Connection reset by peer"), fail_at=len(data) // 3)
        code, out, err = self.run_main("install")
        self.assertIn("下载中断", err)
        self.assertIn("Connection reset by peer", err)
        self.check_nothing_left(code, err, True)

    def test_download_no_length_cut(self):
        self.online(data=shell_zip(), length=False, cut=100)      # 服务器没说大小：解压时发现不完整
        code, out, err = self.run_main("install")
        self.assertIn("不是完整的 zip", err)
        self.check_nothing_left(code, err, False)

    def test_ctrl_c(self):
        data = shell_zip()
        self.online(data=data, fail=KeyboardInterrupt(), fail_at=len(data) // 2)
        code, out, err = self.run_main("install")
        self.assertEqual(code, 130)
        self.assertIn("已取消", err)
        self.assertEqual(self.files(), [])

    def test_corrupt_zip(self):
        self.online(data=b"PK not really a zip file")
        code, out, err = self.run_main("install")
        self.assertIn("不是完整的 zip", err)
        self.check_nothing_left(code, err, False)

    def test_zip_without_program(self):
        self.online(data=shell_zip(exe=False))
        code, out, err = self.run_main("install")
        self.assertIn("没有 chrome-headless-shell-mac-arm64/chrome-headless-shell", err)
        self.check_nothing_left(code, err, False)


# ---------- status、path、remove，非 macOS ----------

class TestOtherCommands(Base):
    def test_path(self):
        code, out, err = self.run_main("path")
        self.assertEqual((code, out), (1, ""))                     # 没装：标准输出留空，退出码 1
        self.assertIn("install", err)
        exe = self.put_version(V)
        code, out, err = self.run_main("path")
        self.assertEqual((code, out), (0, f"{exe}\n"))

    def test_status(self):
        code, out, err = self.run_main("status")
        self.assertEqual(code, 0)
        self.assertIn("没有装", out)
        self.assertIn(R.command(), out)
        exe = self.put_version(V)
        code, out, err = self.run_main("status")
        self.assertIn(f"已装好：chrome-headless-shell {V}", out)
        self.assertIn(f"路径：{exe}", out)

    def test_remove(self):
        self.put_version(V)
        code, out, err = self.run_main("remove")
        self.assertEqual(code, 0)
        self.assertIn(f"已删除：{self.root}", out)
        self.assertFalse(self.root.exists())
        self.assertTrue(self.root.parent.exists())                 # 只删 chrome-headless-shell 这一层
        code, out, err = self.run_main("remove")
        self.assertEqual(code, 0)
        self.assertIn("没有装", out)

    def test_not_macos(self):
        self.put_version(V)
        with mock.patch.object(R.sys, "platform", "linux"):
            for cmd in ("install", "status", "path", "remove"):
                code, out, err = self.run_main(cmd)
                self.assertEqual((code, out), (1, ""), cmd)
                self.assertIn("PDF 只支持 macOS", err)
            self.assertEqual(R.install_hint(), R.MACOS_ONLY)
        self.assertEqual(self.versions(), [V])

    def test_install_hint(self):
        hint = R.install_hint()
        self.assertIn("PDF 要用没有界面的排版程序 chrome-headless-shell，先运行一次：python3 ", hint)
        self.assertIn(str(SKILL / "scripts" / "renderer.py"), hint)
        self.assertIn(f"（约 {R.APPROX_MB} MB，装在 ~/Library/Caches/english-reader/）。check、md 不受影响。", hint)

    def test_usage(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("download")[0], 2)
        self.assertEqual(self.run_main("--help")[0], 0)


if __name__ == "__main__":
    unittest.main()
