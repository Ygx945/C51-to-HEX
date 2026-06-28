# Keil C51 → HEX 转换器

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**一款绿色免安装的 Windows 桌面工具**，将 Keil C51 语法的 `.c` 源文件自动转换为 SDCC 兼容语法，并编译生成标准 Intel HEX 文件。

> 🎯 无需安装 Python、SDCC 或任何依赖 —— 下载 EXE 直接运行！

## ✨ 功能特性

- 🔄 **自动语法转换** — Keil C51 → SDCC 全自动，无需手动修改代码
- 📦 **独立封装版** — 内置 SDCC 编译器，一个 EXE 搞定一切
- 📁 **文件模式** — 拖放 `.c` 文件到窗口，一键转换编译
- ✏️ **代码模式** — 直接粘贴 C51 代码片段，无需保存文件
- 👁️ **转换预览** — 实时查看转换后的 SDCC 代码
- 📋 **编译日志** — 详细的编译过程输出，方便调试
- 🖥️ **命令行支持** — 也支持 CLI 模式，方便脚本集成
- 🔧 **8051 反汇编器** — 附带 HEX → 汇编反编译工具

## 🚀 快速开始

### 方式一：独立 EXE（推荐）

从 [Releases](https://github.com/Ygx945/KeilC51-to-HEX/releases) 下载 `Keil2Hex_v3.0.exe`，双击运行。

### 方式二：Python 脚本

```bash
# 1. 安装 SDCC 编译器（仅脚本模式需要）
#    下载地址: https://sdcc.sourceforge.net/

# 2. 安装 Python 依赖
pip install tkinter  # 通常 Python 自带

# 3. 运行
python keil2hex.pyw
```

### 命令行使用

```bash
# GUI 模式
python keil2hex.pyw

# CLI 模式
python keil2hex.pyw input.c output.hex
```

## 📸 界面预览

```
┌─────────────────────────────────────────────────────┐
│  Keil C51 → HEX 转换器 v3.0 (独立封装版)            │
├─────────────────────────────────────────────────────┤
│  工作模式: [📁 文件模式]  [✏️ 代码模式（直接粘贴）]  │
│  源文件:  [C:\project\main.c           ] [浏览...]  │
│  输出目录: [C:\project\   ] 文件名: [main.hex]      │
│  MCU 型号: [STC12C5A60S2 ▼]  存储模式: [small ▼]   │
├─────────────────────────────────────────────────────┤
│  [转换预览]  [编译日志]                              │
│  ┌─────────────────────────────────────────────┐    │
│  │ // Auto-converted by Keil2Hex v3.0          │    │
│  │ #include <8052.h>                           │    │
│  │ __sfr __at (0x80) P0;                       │    │
│  │ ...                                         │    │
│  └─────────────────────────────────────────────┘    │
│  [▶ 转换并编译] [💾 保存转换后的 .c] [📂 打开目录]  │
│  就绪 — 选择文件或粘贴代码，然后点击"转换并编译"    │
└─────────────────────────────────────────────────────┘
```

## 🔧 支持的语法转换

| Keil C51 | SDCC |
|----------|------|
| `#include <REG52.H>` | `#include <8052.h>` |
| `sfr P0 = 0x80;` | `__sfr __at (0x80) P0;` |
| `sbit LED = P1^0;` | `__sbit __at (0x90) LED;` |
| `unsigned char code tab[]` | `__code unsigned char tab[]` |
| `void isr() interrupt 1` | `void isr() __interrupt (1)` |
| `void isr() interrupt 1 using 1` | `void isr() __interrupt (1) __using (1)` |
| `bit flag;` | `__bit flag;` |
| `xdata / idata / pdata / data` | `__xdata / __idata / __pdata / __data` |
| `_at_` | `__at` |

## 📦 支持的 MCU 型号

STC12C5A60S2, STC89C52RC, STC89C51RC, STC15F2K60S2, STC15W4K56S4, STC8A8K64S4A12, AT89C52, AT89C51, AT89S52, AT89S51, Generic 8052, Generic 8051

## 🛠️ 自行构建 EXE

```bash
# 1. 安装依赖
pip install pyinstaller

# 2. 安装 SDCC（默认路径 C:\Program Files\SDCC）

# 3. 运行构建脚本
python build.py
```

构建脚本会自动：
1. 从系统 SDCC 目录提取 mcs51 所需文件
2. 打包为单个 `Keil2Hex_v3.0.exe`

## 📂 项目结构

```
KeilC51-to-HEX/
├── keil2hex.pyw          # 主程序（GUI + CLI）
├── build.py              # PyInstaller 构建脚本
├── disasm_8051.py        # 8051 HEX 反汇编器
├── examples/             # 示例文件
│   ├── main.c            # 示例 Keil C51 源文件
│   ├── main.hex          # 示例转换输出
│   ├── main_sdcc.c       # 示例转换后的 SDCC 代码
│   ├── pasted_project.c  # 秒表/时钟项目示例
│   └── pasted_project.hex
├── README.md
└── LICENSE
```

## 📄 许可证

MIT License © 2025 — 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [SDCC (Small Device C Compiler)](https://sdcc.sourceforge.net/) — 开源的 8051 C 编译器
- 本项目基于 SDCC 构建，将 Keil C51 语法自动转换为 SDCC 兼容格式
