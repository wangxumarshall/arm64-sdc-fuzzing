#!/bin/bash
# Copyright (C) 2024 Intel Corporation.
# SPDX-License-Identifier: Apache-2.0
#
# Package opendcdiag + ALL its dynamic library dependencies into a single,
# self-contained, relocatable distribution directory:
#
#   opendcdiag-dist/
#   ├── opendcdiag          (binary, RPATH=$ORIGIN/lib already baked in)
#   ├── lib/                (every NEEDED .so, with soname symlinks preserved)
#   ├── run.sh              (wrapper: sets LD_LIBRARY_PATH + forwards args)
#   └── README.md           (usage / how it works / glibc caveats)
#
# The binary's RPATH is $ORIGIN/lib, so when run from inside this directory it
# finds the bundled .so files without any LD_LIBRARY_PATH and without polluting
# the target system's ldconfig. run.sh additionally sets LD_LIBRARY_PATH as a
# belt-and-suspenders fallback (e.g. for libarm_compute's own NEEDED chain).
#
# IMPORTANT — glibc/libstdc++ symbol-versioning caveat (NOT solved by this):
# RPATH only lets the loader *locate* a .so; it cannot downgrade the symbol
# versions the .so was compiled against. If the binary or any bundled .so was
# built on a newer OS (e.g. openEuler 24.03 SP3, glibc 2.38) it will STILL
# fail on an older target (e.g. openEuler 22.03 SP4, glibc 2.34) with
# "version 'GLIBC_2.38' not found". Bundling libc.so.6 itself does NOT help —
# the loader refuses to use a libc that doesn't match the running kernel/ABI.
# To run on an older baseline, rebuild the binary AND all deps there. See
# PLAN.md §0/§1.
#
# Usage:
#   ./scripts/package-dist.sh [builddir] [outname]
#
#   builddir   meson build dir containing opendcdiag  (default: builddir)
#   outname    output dir name                         (default: opendcdiag-dist)
#
# Example:
#   ./scripts/package-dist.sh builddir
#   ./scripts/package-dist.sh builddir myrelease
set -euo pipefail

BUILDDIR="${1:-builddir}"
OUTNAME="${2:-opendcdiag-dist}"
BIN="$BUILDDIR/opendcdiag"

if [ ! -x "$BIN" ]; then
    echo "error: $BIN not found or not executable" >&2
    exit 1
fi

# Sanity: binary must carry $ORIGIN/lib RPATH, else run.sh falls back to
# LD_LIBRARY_PATH only (still works, but less clean).
if readelf -d "$BIN" 2>/dev/null | grep -qE 'RPATH|RUNPATH'; then
    RPATH_OK=1
else
    RPATH_OK=0
    echo "WARN: binary has no RPATH/RUNPATH — run.sh will rely on LD_LIBRARY_PATH" >&2
fi

DIST="$OUTNAME"
rm -rf "$DIST"
mkdir -p "$DIST/lib"

# --- 1. copy binary ---------------------------------------------------------
cp "$BIN" "$DIST/opendcdiag"
chmod 0755 "$DIST/opendcdiag"

# --- 2. collect NEEDED libs (exclude the interpreter ld-linux-*) -----------
# readelf prints NEEDED sonames; ldd resolves each to a real file path.
mapfile -t NEEDED < <(readelf -d "$BIN" 2>/dev/null \
    | sed -n 's/.*NEEDED.*\[\([^]]*\)\].*/\1/p' \
    | grep -v '^ld-linux')

declare -A SEEN=()
copied=0
for soname in "${NEEDED[@]}"; do
    # ldd prints "<soname> => /path (addr)" — grab column 3.
    src=$(ldd "$BIN" 2>/dev/null | awk -v s="$soname" '$1==s && $2=="=>" {print $3}')
    if [ -z "$src" ] || [ ! -e "$src" ]; then
        echo "WARN: $soname not resolved by ldd (skipping)" >&2
        continue
    fi
    real=$(readlink -f "$src")
    if [ -n "${SEEN[$real]:-}" ]; then continue; fi
    SEEN[$real]=1
    # Copy the real file under its real basename, then recreate the soname
    # symlink so the loader's SONAME lookup resolves to it.
    base=$(basename "$real")
    cp -L "$real" "$DIST/lib/$base"
    if [ "$base" != "$soname" ]; then
        ln -sf "$base" "$DIST/lib/$soname"
    fi
    copied=$((copied+1))
    echo "  + $soname  <-  $real"
done
echo "copied $copied library file(s) into $DIST/lib/"

# --- 3. run.sh wrapper -------------------------------------------------------
cat > "$DIST/run.sh" <<'RUN_EOF'
#!/bin/bash
# opendcdiag wrapper — locates the bundled libraries next to this script.
# The binary already has RPATH=$ORIGIN/lib, so this is mostly a convenience
# wrapper with sane defaults; LD_LIBRARY_PATH is set as a fallback so the
# bundled .so files win over any system-installed copies.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$HERE/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/opendcdiag" "$@"
RUN_EOF
chmod 0755 "$DIST/run.sh"

# --- 4. README.md usage -----------------------------------------------------
cat > "$DIST/README.md" <<'README_EOF'
# opendcdiag (ARM64) — 自包含分发包

本目录是一个可重定位的交付包: `opendcdiag` 二进制 + 全部动态依赖库 + 运行脚本.
拷到任何同架构 (aarch64, glibc >= 构建基线) 的机器上即可运行, 无需安装任何软件包.

## 目录结构

```
opendcdiag-dist/
├── opendcdiag      主二进制 (RPATH=$ORIGIN/lib, 已静态链入 mathlib/stringlib/isal/compiler-rt)
├── lib/            全部动态依赖库 (保留 soname 符号链接)
├── run.sh          运行脚本 (设 LD_LIBRARY_PATH + 转发参数)
└── README.md       本文件
```

## 快速开始

```bash
cd opendcdiag-dist
./run.sh --version
```

## 常用运行方式 (从 CLAUDE.md)

```bash
# 冒烟测试 (1 分钟, 全核)
./run.sh -T 1m -n $(nproc) --ignore-os-error --ignore-timeout -o run.log -q

# 全核满载持续运行 (本机 128 核, 不要用 -n 0)
./run.sh -T forever -n 128 --ignore-os-error --ignore-timeout -o run.log -q

# 定时运行
./run.sh -T 24h -n 128 --ignore-os-error --ignore-timeout -o run.log -q

# 定向 ARM64 测试 (--list 不打印 arm64 测试, 但 -e 可运行)
./run.sh -e arm64_sdc -e neon_add -e arm_crypto

# 自检 (框架故意失败以验证检测机制, 统计 result: pass 的正向用例)
./run.sh --selftests --max-test-loop-count 1

# 列出所有测试
./run.sh --list
```

## 它怎么工作

- 二进制内嵌 `RPATH=$ORIGIN/lib`: 动态链接器在二进制所在目录的 `lib/`
  子目录里查找依赖库, 不依赖目标机的 `ldconfig`, 也不需要 `LD_LIBRARY_PATH`.
- `run.sh` 额外设置 `LD_LIBRARY_PATH=<dir>/lib` 作为兜底 (例如 libarm_compute
  自身的 NEEDED 传递依赖), 并转发所有参数给二进制.
- mathlib / stringlib / isa-l / compiler-rt builtins 已**静态**链入二进制,
  不在 `lib/` 里 (见构建日志).

## glibc / libstdc++ 版本兼容性 (重要)

`lib/` 里附带的核心库 (libc/libm/libgcc_s/libstdc++ 等) 是在**构建机**
(openEuler 24.03 SP3, glibc 2.38) 上编译的. 这意味着:

- RPATH 只解决"找不到库文件", **不能**降级 .so 内部烙印的符号版本需求
  (`GLIBC_2.38` / `GLIBCXX_3.4.30` 等).
- 在更旧的系统 (如 openEuler 22.03 SP4, glibc 2.34) 上运行, 若二进制或任一
  随包 .so 引用了 2.34 之后的符号, 仍会报 `version 'GLIBC_2.38' not found`.
- 附带 libc.so.6 本身也无济于事: 加载器拒绝使用与运行内核/ABI 不匹配的 libc.
- 若需在更旧基线上运行, 唯一可靠做法是在该基线上**重新构建** opendcdiag 及
  全部依赖 (含 libarm_compute). 见仓库 `PLAN.md`.

## 验证包是否自包含

```bash
cd opendcdiag-dist
LD_LIBRARY_PATH="$PWD/lib" ldd ./opendcdiag   # 期望: 无 "not found"
./run.sh --version                              # 期望: 打印版本号
```
README_EOF

# --- 5. report --------------------------------------------------------------
echo ""
echo "=== $DIST contents ==="
ls -lR "$DIST"
echo ""
echo "=== binary RPATH (expect \$ORIGIN/lib) ==="
readelf -d "$DIST/opendcdiag" 2>/dev/null | grep -E 'RPATH|RUNPATH' || true
echo ""
echo "=== ldd against bundled lib/ (expect no 'not found') ==="
LD_LIBRARY_PATH="$DIST/lib" ldd "$DIST/opendcdiag" 2>/dev/null || true
echo ""
echo "=== making tarball ==="
tar czf "$DIST.tar.gz" "$DIST"
echo "-> $DIST.tar.gz"
