#!/usr/bin/env python3
"""PDF 的排版程序 chrome-headless-shell：装、查、删。只用 Python 标准库，只支持 macOS。

chrome-headless-shell 是 Google 官方 Chrome for Testing 里没有界面的那一版：一个普通的命令行程序，不是 App，
不进程序坞，也不抢前台和键盘。build.py pdf 默认只用它排版。

  python3 renderer.py install   下载 Stable 版，装到 ~/Library/Caches/english-reader/chrome-headless-shell/<版本>/
                                下载前打印版本、大小、来源网址和目标目录；已经装了同一版本就不再下载；旧版本删掉，只留一个
  python3 renderer.py status    装没装、版本、路径
  python3 renderer.py remove    删掉整个 ~/Library/Caches/english-reader/chrome-headless-shell/
  python3 renderer.py path      只打印程序的路径；没装时不打印路径，退出码 1

来源：官方清单 last-known-good-versions-with-downloads.json 里 Stable 一栏的 chrome-headless-shell，
  按本机芯片选 mac-arm64 或 mac-x64。只从 https://storage.googleapis.com/chrome-for-testing-public/ 下载，
  User-Agent 如实写 english-reader/3.0。
下载先写到临时文件，解压到临时目录，检查无误才改成正式目录：网络断了、清单格式变了、按了 Ctrl-C，都不留半截文件。
解压时拒绝绝对路径、..、指到外面的软链接。
"""
import http.client
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from pathlib import Path

MANIFEST_URL = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
DOWNLOAD_PREFIX = "https://storage.googleapis.com/chrome-for-testing-public/"
USER_AGENT = "english-reader/3.0"
CACHE = Path.home() / "Library" / "Caches" / "english-reader"
ROOT = CACHE / "chrome-headless-shell"          # 每个版本一个子目录，只留一个
EXE = "chrome-headless-shell"
PLATFORMS = {"arm64": "mac-arm64", "x86_64": "mac-x64"}     # platform.machine() → 清单里的 platform
APPROX_MB = 100        # 提示里说的大约下载大小；装的时候按服务器给的实际大小打印
VERSION_RE = re.compile(r"\d+(?:\.\d+){3}")
CHUNK = 1 << 16
MACOS_ONLY = "PDF 只支持 macOS：chrome-headless-shell 的安装和 build.py pdf 都只在 Mac 上用。check、md 不受影响。"


def command():
    """给人照抄的安装命令（完整路径）。"""
    return f"python3 {shlex.quote(str(Path(__file__).resolve()))} install"


def install_hint():
    """build.py 找不到排版程序时的说明。"""
    if sys.platform != "darwin":
        return MACOS_ONLY
    return (f"PDF 要用没有界面的排版程序 chrome-headless-shell，先运行一次：{command()}"
            f"（约 {APPROX_MB} MB，装在 ~/Library/Caches/english-reader/）。check、md 不受影响。")


# ---------- 装在哪、装没装 ----------

def version_key(v):
    return tuple(int(x) for x in v.split("."))


def find_exe(d):
    """版本目录 d 里的可执行文件：d/chrome-headless-shell-<平台>/chrome-headless-shell。没有返回 None。"""
    for p in sorted(Path(d).glob(f"{EXE}-*/{EXE}")):
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def installed():
    """装好的 (版本, 程序路径)；没装返回 None。有几个版本时取最新的（正常只有一个）。"""
    found = []
    if ROOT.is_dir():
        for d in ROOT.iterdir():
            if VERSION_RE.fullmatch(d.name) and d.is_dir():
                exe = find_exe(d)
                if exe:
                    found.append((version_key(d.name), d.name, exe))
    if not found:
        return None
    _, version, exe = max(found)
    return version, exe


def drop_others(keep):
    """ROOT 里除了 keep 这个版本目录，别的（旧版本、上次中断留下的临时文件）都删掉。"""
    old = []
    if not ROOT.is_dir():
        return old
    for p in ROOT.iterdir():
        if p.name == keep:
            continue
        if VERSION_RE.fullmatch(p.name):
            old.append(p.name)
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
    if old:
        print("删掉旧版本：" + "、".join(sorted(old, key=version_key)))
    return old


def clean_partial():
    """上次被强行中止（kill -9、断电）留下的下载临时文件和解压临时目录。"""
    if ROOT.is_dir():
        for p in ROOT.glob(".download-*"):
            p.unlink(missing_ok=True)
        for p in ROOT.glob(".staging-*"):
            shutil.rmtree(p, ignore_errors=True)


# ---------- 清单 ----------

def machine():
    """本机芯片。Apple 芯片上经 Rosetta 转译运行的 Python 也报 x86_64：问一下系统，是转译的按 arm64 算。"""
    m = platform.machine()
    if m == "x86_64":
        try:
            r = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True)
            if r.stdout.strip() == "1":
                return "arm64"
        except OSError:
            pass
    return m


def platform_name():
    m = machine()
    if m not in PLATFORMS:
        raise SystemExit(f"不认识这台 Mac 的芯片（{m}）：chrome-headless-shell 只有 Apple 芯片（arm64）和 Intel（x86_64）两种。")
    return PLATFORMS[m]


def get(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def fetch_manifest():
    try:
        with get(MANIFEST_URL) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"取不到官方下载清单（HTTP {e.code}）：{MANIFEST_URL}\n"
                         "过一会儿再运行一次。什么都没装，也没留下文件。")
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        raise SystemExit(f"连不上官方下载清单（{getattr(e, 'reason', e)}）：{MANIFEST_URL}\n"
                         "网络通了再运行一次。什么都没装，也没留下文件。")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise SystemExit(f"官方下载清单不是 JSON，格式可能变了：{MANIFEST_URL}\n"
                         "什么都没装。请把这句话发给维护 english-reader 的人。")


def check_url(url):
    """只接受 Chrome for Testing 官方存储的 https 地址；不是就退出（什么都不下载）。"""
    ok = isinstance(url, str) and url.startswith(DOWNLOAD_PREFIX) and url.isprintable() and " " not in url
    if ok:
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.unquote(parts.path)
        ok = (parts.scheme == "https" and parts.netloc == "storage.googleapis.com"
              and path.startswith("/chrome-for-testing-public/") and ".." not in path.split("/")
              and "\\" not in path and not parts.query and not parts.fragment)
    if not ok:
        raise SystemExit(f"下载地址不是 Chrome for Testing 官方存储（只认 {DOWNLOAD_PREFIX} 开头的）：{url!r}\n"
                         "没有下载，什么都没装。")
    return url


def pick(manifest, plat):
    """清单里 Stable 版、本机平台的 chrome-headless-shell：(版本, 网址)。格式不对、网址不在白名单里就退出。"""
    try:
        stable = manifest["channels"]["Stable"]
        version = stable["version"]
        url = next(x["url"] for x in stable["downloads"][EXE] if x.get("platform") == plat)
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise SystemExit(f"官方下载清单的格式变了，找不到 Stable 版 {plat} 的 chrome-headless-shell：{MANIFEST_URL}\n"
                         "什么都没装。请把这句话发给维护 english-reader 的人。")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise SystemExit(f"官方下载清单里的版本号看不懂（{version!r}），格式可能变了。什么都没装。")
    return version, check_url(url)


# ---------- 下载、解压 ----------

def mb(n):
    return f"{n / 1e6:.1f} MB"


def download(url, dest):
    """下载到 dest。收到的字节数和服务器说的对不上、网络断了，都退出；dest 由调用的人删。"""
    tty = sys.stdout.isatty()
    try:
        with get(url, timeout=60) as r:
            check_url(r.geturl())                    # 跟了跳转，也还得是官方存储
            size = r.headers.get("Content-Length", "")
            total = int(size) if size.strip().isdigit() else None
            print(f"大小：{mb(total) if total else '服务器没说，边下边算'}", flush=True)
            got, shown = 0, -1
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    pct = got * 100 // total if total else got >> 20
                    if tty and pct != shown:
                        shown = pct
                        print(f"\r下载中 {pct}%" if total else f"\r下载中 {mb(got)}", end="", flush=True)
            if tty:
                print()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"下载失败（HTTP {e.code}）：{url}\n过一会儿再运行一次。什么都没装，也没留下文件。")
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        if tty:
            print()
        raise SystemExit(f"下载中断（{getattr(e, 'reason', e)}）：{url}\n"
                         "网络稳定了再运行一次。什么都没装，也没留下下载了一半的文件。")
    if not got or (total and got != total):
        raise SystemExit(f"下载中断：只收到 {mb(got)}" + (f"，应该是 {mb(total)}" if total else "") + f"：{url}\n"
                         "网络稳定了再运行一次。什么都没装，也没留下下载了一半的文件。")
    return got


def inside(base, path):
    return os.path.commonpath([base, path]) == base


def unsafe(name, why):
    raise SystemExit(f"压缩包里有不安全的路径（{why}）：{name!r}\n已经停下，什么都没装。")


def extract(zip_path, dest):
    """把 zip 解压到空目录 dest，返回解压后的总字节数。绝对路径、..、指到 dest 外面的软链接，一律拒绝。
    zipfile 不还原权限和软链接：这里按压缩包里记的权限（只取 rwx 位）设，软链接检查过才建。"""
    base = os.path.realpath(dest)
    total = 0
    try:
        z = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise SystemExit("下载的文件不是完整的 zip（可能下载中断了，或者服务器给的不是压缩包）。什么都没装。")
    with z:
        for info in z.infolist():
            name = info.filename
            parts = name.replace("\\", "/").split("/")
            if name.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", name) or "\x00" in name:
                unsafe(name, "绝对路径")
            if ".." in parts:
                unsafe(name, "..")
            target = os.path.normpath(os.path.join(base, *[p for p in parts if p not in ("", ".")]))
            if target == base:
                continue
            if not inside(base, target) or not inside(base, os.path.realpath(os.path.dirname(target))):
                unsafe(name, "指到解压目录外面")
            if os.path.islink(target):
                unsafe(name, "和压缩包里的软链接重名")
            mode = info.external_attr >> 16
            try:
                if info.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if stat.S_ISLNK(mode):
                    link = z.read(info).decode("utf-8")
                    if not link or link.startswith(("/", "\\")) or "\x00" in link:
                        unsafe(name, f"软链接指到绝对路径 {link}")
                    if not inside(base, os.path.normpath(os.path.join(os.path.dirname(target), link))):
                        unsafe(name, f"软链接指到解压目录外面 {link}")
                    os.symlink(link, target)
                    continue
                with z.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, CHUNK)
            except (zipfile.BadZipFile, zlib.error, EOFError, UnicodeDecodeError):
                raise SystemExit(f"压缩包坏了，解不开 {name}（可能下载中断了）。什么都没装，网络稳定了再运行一次。")
            except OSError as e:
                raise SystemExit(f"解压 {name} 时出错（{e}）。什么都没装。")
            os.chmod(target, ((mode & 0o777) or 0o644) | 0o600)
            total += info.file_size
    for top, dirs, files in os.walk(base):               # 软链接一个接一个，最后也不许指到外面
        for n in dirs + files:
            p = os.path.join(top, n)
            if os.path.islink(p) and not inside(base, os.path.realpath(p)):
                unsafe(os.path.relpath(p, base), "软链接指到解压目录外面")
    return total


def unquarantine(path):
    """有 com.apple.quarantine（隔离属性）就用 xattr -d 去掉，免得第一次运行时弹窗。返回去没去。
    Python 下载的文件一般没有这个属性；从浏览器下载的压缩包解出来的才会带。"""
    try:
        r = subprocess.run(["xattr", "-r", str(path)], capture_output=True, text=True)
    except OSError:
        return False
    if "com.apple.quarantine" not in r.stdout:
        return False
    subprocess.run(["xattr", "-r", "-d", "com.apple.quarantine", str(path)], capture_output=True, text=True)
    print("已去掉隔离属性 com.apple.quarantine")
    return True


# ---------- 子命令 ----------

def install():
    plat = platform_name()
    clean_partial()
    version, url = pick(fetch_manifest(), plat)
    final = ROOT / version
    have = find_exe(final) if final.is_dir() else None
    if have:
        print(f"已经装好 chrome-headless-shell {version}（当前的 Stable 版），不用再下载：{have}")
        drop_others(version)
        return 0
    print(f"chrome-headless-shell {version}（Stable，{plat}）")
    print(f"来源：{url}")
    print(f"装到：{final}/", flush=True)
    made_root = not ROOT.exists()
    tmp_zip = staging = None
    done = False
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        fd, tmp_zip = tempfile.mkstemp(prefix=".download-", suffix=".zip", dir=ROOT)
        os.close(fd)
        staging = tempfile.mkdtemp(prefix=".staging-", dir=ROOT)
        download(url, tmp_zip)
        size = extract(tmp_zip, staging)
        exe = Path(staging) / f"{EXE}-{plat}" / EXE
        if not exe.is_file() or exe.is_symlink():
            raise SystemExit(f"压缩包里没有 {EXE}-{plat}/{EXE}，格式可能变了。什么都没装。请把这句话发给维护 english-reader 的人。")
        os.chmod(exe, exe.stat().st_mode | 0o755)
        unquarantine(staging)
        if final.is_symlink() or final.is_file():     # 同一版本装坏了（没有可执行文件）：换掉
            final.unlink()
        elif final.exists():
            shutil.rmtree(final)
        os.rename(staging, final)
        done = True
    finally:
        if tmp_zip:
            Path(tmp_zip).unlink(missing_ok=True)
        if not done:
            if staging:
                shutil.rmtree(staging, ignore_errors=True)
            if made_root:
                shutil.rmtree(ROOT, ignore_errors=True)
    drop_others(version)
    print(f"解压后 {mb(size)}")
    print(f"装好了：{final / f'{EXE}-{plat}' / EXE}")
    return 0


def status():
    got = installed()
    if not got:
        print(f"没有装 chrome-headless-shell。build.py pdf 要用它，先运行一次：{command()}（约 {APPROX_MB} MB）")
        return 0
    version, exe = got
    print(f"已装好：chrome-headless-shell {version}")
    print(f"路径：{exe}")
    return 0


def remove():
    if ROOT.is_symlink():
        ROOT.unlink()
    elif ROOT.exists():
        shutil.rmtree(ROOT)
    else:
        print(f"没有装，不用删：{ROOT}")
        return 0
    print(f"已删除：{ROOT}")
    return 0


def path():
    got = installed()
    if not got:
        print(f"没有装 chrome-headless-shell。装：{command()}", file=sys.stderr)     # 标准输出留空
        return 1
    print(got[1])
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmds = {"install": install, "status": status, "remove": remove, "path": path}
    if argv in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if len(argv) != 1 or argv[0] not in cmds:
        print(__doc__, file=sys.stderr)
        return 2
    if sys.platform != "darwin":
        print(MACOS_ONLY, file=sys.stderr)
        return 1
    try:
        return cmds[argv[0]]()
    except KeyboardInterrupt:
        print("\n已取消。" + ("什么都没装，也没留下下载了一半的文件。" if argv[0] == "install" else ""), file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
