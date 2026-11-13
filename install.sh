#!/bin/sh
# 把这个目录用软链接装到 Claude Code 的 skill 目录：~/.claude/skills/english-reader
# 用法：./install.sh            安装
#       ./install.sh --remove   卸载（只删软链接，不动这个目录）
# 环境变量 CLAUDE_SKILLS_DIR 可以换目标目录。
set -eu

here=$(cd "$(dirname "$0")" && pwd)
skills="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
dest="$skills/english-reader"

if [ "${1:-}" = "--remove" ]; then
  if [ -L "$dest" ]; then
    rm "$dest"
    echo "已卸载：$dest"
  else
    echo "没有找到软链接：$dest" >&2
    exit 1
  fi
  exit 0
fi

if [ ! -f "$here/SKILL.md" ]; then
  echo "找不到 $here/SKILL.md，请在仓库根目录运行。" >&2
  exit 1
fi

if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$here" ]; then
  echo "已经装好：$dest -> $here"
  exit 0
fi

if [ -e "$dest" ] || [ -L "$dest" ]; then
  echo "$dest 已经存在，没有覆盖。先把它移走再运行。" >&2
  exit 1
fi

mkdir -p "$skills"
ln -s "$here" "$dest"
echo "已安装：$dest -> $here"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  echo "提示：脚本需要 Python 3.9 以上，当前环境没有找到。" >&2
fi
