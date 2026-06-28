#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keil2Hex V3.0 Build Script
===========================
将 keil2hex_v3.0.pyw + 精简版 SDCC 封装为单个独立 .exe 文件。
用户无需安装 Python、SDCC 或任何依赖，打开即用。

用法:
    python build_v3.py

输出:
    Keil2Hex_v3.0.exe
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ============================================================
# 配置
# ============================================================

PROJECT_DIR = Path(__file__).parent.resolve()
SOURCE_PYW = PROJECT_DIR / "keil2hex.pyw"
BUNDLE_DIR = PROJECT_DIR / "_bundle_sdcc"
OUTPUT_NAME = "Keil2Hex_v3.0"
SDCC_INSTALL = Path(r"C:\Program Files\SDCC")

# SDCC bin 目录中需要的文件（仅 mcs51/8051 相关）
NEEDED_BIN_FILES = [
    "sdcc.exe",
    "sdcpp.exe",
    "sdas8051.exe",
    "sdld.exe",
    "packihx.exe",
    "makebin.exe",
    "libgcc_s_seh-1.dll",
    "libgcc_s_sjlj-1.dll",
    "libstdc++-6.dll",
    "libwinpthread-1.dll",
    "readline5.dll",
]

# SDCC lib 目录中需要的 mcs51 内存模型
NEEDED_LIB_MODELS = [
    "small",
    "medium",
    "large",
    "small-stack-auto",
    "large-stack-auto",
    "huge",
]


# ============================================================
# 函数
# ============================================================

def check_prerequisites():
    """检查构建环境。"""
    errors = []

    if not SOURCE_PYW.is_file():
        errors.append(f"找不到源文件: {SOURCE_PYW}")

    if not SDCC_INSTALL.is_dir():
        errors.append(f"找不到 SDCC 安装目录: {SDCC_INSTALL}")
    else:
        sdcc_exe = SDCC_INSTALL / "bin" / "sdcc.exe"
        if not sdcc_exe.is_file():
            errors.append(f"找不到 sdcc.exe: {sdcc_exe}")

    try:
        result = subprocess.run(
            ["pyinstaller", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            errors.append("PyInstaller 未正确安装，请运行: pip install pyinstaller")
    except FileNotFoundError:
        errors.append("找不到 PyInstaller，请运行: pip install pyinstaller")

    if errors:
        print("[FAIL] 构建环境检查失败:")
        for e in errors:
            print(f"   - {e}")
        return False

    print("[OK] 构建环境检查通过")
    print(f"  源文件: {SOURCE_PYW}")
    print(f"  SDCC: {SDCC_INSTALL}")
    print(f"  PyInstaller: {result.stdout.strip()}")
    return True


def create_sdcc_bundle():
    """创建精简版 SDCC 目录（仅 mcs51 所需文件）。"""
    print("\n[Step 2] 创建精简版 SDCC 捆绑包...")

    if BUNDLE_DIR.is_dir():
        print(f"  清理旧捆绑包: {BUNDLE_DIR}")
        shutil.rmtree(BUNDLE_DIR)

    bin_src = SDCC_INSTALL / "bin"
    inc_src = SDCC_INSTALL / "include"
    lib_src = SDCC_INSTALL / "lib"

    # --- bin/ ---
    bin_dst = BUNDLE_DIR / "bin"
    bin_dst.mkdir(parents=True)
    copied_bin = 0
    for fname in NEEDED_BIN_FILES:
        src = bin_src / fname
        if src.is_file():
            shutil.copy2(src, bin_dst / fname)
            copied_bin += 1
        else:
            print(f"  [WARN] bin 文件不存在，跳过: {fname}")
    print(f"  bin/: {copied_bin} 个文件")

    # --- include/ ---
    inc_dst = BUNDLE_DIR / "include"
    shutil.copytree(inc_src, inc_dst)
    for subdir in list(inc_dst.iterdir()):
        if subdir.is_dir() and subdir.name not in ("mcs51",):
            shutil.rmtree(subdir, ignore_errors=True)
    inc_count = sum(1 for _ in inc_dst.rglob("*") if _.is_file())
    print(f"  include/: {inc_count} 个文件")

    # --- lib/ ---
    lib_dst = BUNDLE_DIR / "lib"
    lib_dst.mkdir(parents=True)
    lib_total = 0
    for model in NEEDED_LIB_MODELS:
        src_dir = lib_src / model
        if src_dir.is_dir():
            dst_dir = lib_dst / model
            shutil.copytree(src_dir, dst_dir)
            count = sum(1 for _ in dst_dir.glob("*") if _.is_file())
            lib_total += count
        else:
            print(f"  [WARN] lib 模型目录不存在，跳过: {model}")
    print(f"  lib/: {lib_total} 个文件（{len(NEEDED_LIB_MODELS)} 个内存模型）")

    total_size = 0
    for f in BUNDLE_DIR.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size

    print(f"  捆绑包总大小: {total_size / (1024*1024):.1f} MB")
    return True


def run_pyinstaller():
    """运行 PyInstaller 打包。"""
    print("\n[Step 3] PyInstaller 打包中...")
    print("  （此过程可能需要 2-5 分钟，请耐心等待）")

    for d in ["build", "__pycache__"]:
        p = PROJECT_DIR / d
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    spec_file = PROJECT_DIR / f"{OUTPUT_NAME}.spec"
    if spec_file.is_file():
        spec_file.unlink()

    cmd = [
        "pyinstaller",
        "--windowed",
        "--onefile",
        "--clean",
        f"--name={OUTPUT_NAME}",
        f"--add-data={BUNDLE_DIR};sdcc",
        "--log-level=WARN",
        str(SOURCE_PYW),
    ]

    print(f"  命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            timeout=600,
            cwd=str(PROJECT_DIR),
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] 打包超时（10分钟）")
        return False

    if result.returncode != 0:
        print(f"[FAIL] PyInstaller 返回码: {result.returncode}")
        return False

    exe_path = PROJECT_DIR / "dist" / f"{OUTPUT_NAME}.exe"
    if exe_path.is_file():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] 打包成功!")
        print(f"  输出文件: {exe_path}")
        print(f"  文件大小: {size_mb:.1f} MB")
        return True
    else:
        print(f"[FAIL] 未找到输出文件: {exe_path}")
        return False


def cleanup():
    """清理构建中间文件。"""
    print("\n[Cleanup] 清理构建中间文件...")

    if BUNDLE_DIR.is_dir():
        shutil.rmtree(BUNDLE_DIR)
        print(f"  已删除: {BUNDLE_DIR}")

    build_dir = PROJECT_DIR / "build"
    if build_dir.is_dir():
        shutil.rmtree(build_dir)
        print(f"  已删除: {build_dir}")

    spec_file = PROJECT_DIR / f"{OUTPUT_NAME}.spec"
    if spec_file.is_file():
        spec_file.unlink()
        print(f"  已删除: {spec_file}")


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 60)
    print("  Keil2Hex V3.0 - 独立 EXE 构建工具")
    print("=" * 60)

    if not check_prerequisites():
        sys.exit(1)

    if not create_sdcc_bundle():
        sys.exit(1)

    if not run_pyinstaller():
        sys.exit(1)

    cleanup()

    exe_path = PROJECT_DIR / "dist" / f"{OUTPUT_NAME}.exe"
    print(f"\n{'='*60}")
    print(f"  构建完成！")
    print(f"  独立可执行文件: {exe_path}")
    print(f"  将此 .exe 文件分享给任何人即可使用！")
    print(f"  对方无需安装 Python、SDCC 或任何依赖。")
    print(f"{'='*60}")

    try:
        ans = input("\n是否打开输出文件夹？[Y/n]: ").strip().lower()
        if ans != 'n':
            os.startfile(str(exe_path.parent))
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
