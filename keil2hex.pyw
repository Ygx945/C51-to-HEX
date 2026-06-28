#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keil C51 → HEX Converter  v3.0
================================
v1.0: 选择 .c 文件 → 转换 → 编译 → 生成 .hex
v2.0: 新增"代码模式"，可直接粘贴 C51 代码，无需保存文件
v3.0: 封装为独立 EXE，内置 SDCC 编译器，无需安装任何依赖，打开即用！

依赖: 无！（Python + tkinter + SDCC 全部内置在 EXE 中）
双击 .exe 即可运行。
"""

import os
import sys
import re
import shutil
import tempfile
import subprocess
import threading
import queue
import time
from pathlib import Path
from tkinter import Tk, Toplevel, StringVar, BooleanVar, IntVar
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import font as tkfont

# ============================================================
# 常量配置
# ============================================================

APP_TITLE = "Keil C51 → HEX 转换器"
APP_VERSION = "3.0"

# 标准 8051/8052 SFR 基地址表（用于 sbit 位地址计算）
SFR_BASE_MAP = {
    'P0': 0x80, 'SP': 0x81, 'DPL': 0x82, 'DPH': 0x83,
    'PCON': 0x87,
    'TCON': 0x88, 'TMOD': 0x89, 'TL0': 0x8A, 'TL1': 0x8B,
    'TH0': 0x8C, 'TH1': 0x8D, 'AUXR': 0x8E,
    'P1': 0x90,
    'SCON': 0x98, 'SBUF': 0x99,
    'P2': 0xA0,
    'IE': 0xA8, 'IP': 0xB8,
    'P3': 0xB0,
    'T2CON': 0xC8, 'RCAP2L': 0xCA, 'RCAP2H': 0xCB, 'TL2': 0xCC, 'TH2': 0xCD,
    'PSW': 0xD0,
    'ACC': 0xE0, 'A': 0xE0,
    'B': 0xF0,
    'P4': 0xC0, 'P5': 0xC8,
    'P4SW': 0xBB,
    'AUXR1': 0xA2,
    'WAKE_CLKO': 0x8F,
    'CLK_DIV': 0x97,
}

MCU_MODELS = [
    "STC12C5A60S2", "STC89C52RC", "STC89C51RC",
    "STC15F2K60S2", "STC15W4K56S4", "STC8A8K64S4A12",
    "AT89C52", "AT89C51", "AT89S52", "AT89S51",
    "Generic 8052", "Generic 8051",
]

MEMORY_MODELS = ["small", "medium", "large"]

# 正则表达式模式（预编译）
RE_INCLUDE_REG = re.compile(
    r'#include\s*[<"]\s*(REG5[12]|REGX5[12]|STC12C5A60S2)\.H\s*[>"]',
    re.IGNORECASE
)
RE_SFR = re.compile(r'\bsfr\s+(\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\s*;')
RE_SBIT = re.compile(r'\bsbit\s+(\w+)\s*=\s*(\w+)\s*\^\s*(\d+)\s*;')
RE_CODE_TYPE = re.compile(
    r'\b((?:const\s+)?(?:(?:unsigned\s+)?(?:char|int|long|short|float|double)|'
    r'u?int(?:8|16|32|64)_t|'
    r'\w+)\s+)code\b'
)
RE_INTERRUPT = re.compile(r'\)\s*interrupt\s+(\d+)')
RE_INTERRUPT_USING = re.compile(r'\)\s*interrupt\s+(\d+)\s+using\s+(\d+)')
RE_BIT_TYPE = re.compile(r'(?<![_s])\bbit\b(?=\s+\w)')
RE_XDATA = re.compile(r'\bxdata\b')
RE_IDATA = re.compile(r'\bidata\b')
RE_PDATA = re.compile(r'\bpdata\b')
RE_DATA_QUAL = re.compile(r'\bdata\b(?=\s+\w+\s*[=;,\[])')
RE_AT_KEYWORD = re.compile(r'\b_at_\b')
RE_USING = re.compile(r'\)\s+using\s+(\d+)')


# ============================================================
# SDCC 路径工具（v3.0：支持封装内置 SDCC）
# ============================================================

def _get_bundled_sdcc_home():
    """
    检测是否在 PyInstaller 封装环境中运行。
    如果是，返回内置 SDCC 的根目录；否则返回 None。
    """
    # PyInstaller 在运行时设置 sys.frozen = True
    # sys._MEIPASS 是临时解压目录
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None)
        if base:
            # SDCC 被打包为 sdcc/ 子目录
            sdcc_home = os.path.join(base, 'sdcc')
            sdcc_exe = os.path.join(sdcc_home, 'bin', 'sdcc.exe')
            if os.path.isfile(sdcc_exe):
                return sdcc_home
    return None


def find_sdcc():
    """
    查找 SDCC 可执行文件。
    优先级：内置 SDCC > 系统安装的 SDCC > PATH 中的 sdcc
    """
    # 1. 检查内置 SDCC（PyInstaller 封装）
    bundled_home = _get_bundled_sdcc_home()
    if bundled_home:
        exe = os.path.join(bundled_home, 'bin', 'sdcc.exe')
        if os.path.isfile(exe):
            return exe

    # 2. 搜索常见安装路径
    search_paths = [
        r"C:\Program Files\SDCC\bin\sdcc.exe",
        r"C:\Program Files (x86)\SDCC\bin\sdcc.exe",
    ]
    for p in search_paths:
        if os.path.isfile(p):
            return p

    # 3. 在 PATH 中查找
    try:
        result = subprocess.run(
            ['where', 'sdcc'] if sys.platform == 'win32' else ['which', 'sdcc'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            found = result.stdout.strip().split('\n')[0]
            if os.path.isfile(found):
                return found
    except Exception:
        pass

    return 'sdcc'


def get_sdcc_home(sdcc_exe):
    """
    根据 sdcc.exe 的路径推断 SDCC 根目录。
    如果 sdcc.exe 在 bin/ 下，则根目录是 bin/../；
    否则假定 sdcc.exe 所在目录就是根目录。
    """
    exe_dir = os.path.dirname(os.path.abspath(sdcc_exe))
    # 如果 exe 在 bin/ 子目录下
    if os.path.basename(exe_dir).lower() == 'bin':
        return os.path.dirname(exe_dir)
    return exe_dir


def get_packihx_path(sdcc_exe):
    """获取 packihx 路径（与 sdcc 同目录）。"""
    sdcc_dir = os.path.dirname(sdcc_exe)
    if sys.platform == 'win32':
        return os.path.join(sdcc_dir, 'packihx.exe')
    return os.path.join(sdcc_dir, 'packihx')


# ============================================================
# 转换引擎
# ============================================================

class KeilToSDCCConverter:
    """将 Keil C51 语法转换为 SDCC 兼容语法。"""

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.sfr_map = dict(SFR_BASE_MAP)

    def _warn(self, msg):
        self.warnings.append(msg)

    def _err(self, msg):
        self.errors.append(msg)

    @staticmethod
    def detect_encoding(filepath):
        """检测文件编码：UTF-8 → GBK → GB2312 → latin-1 回退"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
        raw = Path(filepath).read_bytes()
        for enc in encodings:
            try:
                text = raw.decode(enc)
                return enc, text
            except (UnicodeDecodeError, UnicodeError):
                continue
        return 'latin-1', raw.decode('latin-1', errors='replace')

    def collect_sfr(self, code):
        for m in RE_SFR.finditer(code):
            name = m.group(1)
            addr_str = m.group(2)
            addr = int(addr_str, 0)
            if name in self.sfr_map and self.sfr_map[name] != addr:
                self._warn(
                    f"SFR '{name}' 重复定义 (0x{self.sfr_map[name]:02X} vs 0x{addr:02X})，"
                    f"使用新值 0x{addr:02X}"
                )
            self.sfr_map[name] = addr

    def convert_includes(self, code):
        def _replace(m):
            original = m.group(0)
            header = m.group(1).upper()
            if header in ('REG51',):
                return '#include <8051.h>'
            elif header in ('REG52', 'REGX52', 'STC12C5A60S2'):
                return '#include <8052.h>'
            return original
        return RE_INCLUDE_REG.sub(_replace, code)

    def convert_sfr(self, code):
        def _replace(m):
            name = m.group(1)
            addr = m.group(2)
            return f'__sfr __at ({addr}) {name};'
        return RE_SFR.sub(_replace, code)

    def convert_sbit(self, code):
        def _replace(m):
            name = m.group(1)
            sfr_name = m.group(2)
            bit_pos = int(m.group(3))
            if sfr_name in self.sfr_map:
                sfr_addr = self.sfr_map[sfr_name]
                if (sfr_addr & 0x07) != 0:
                    self._warn(
                        f"SFR '{sfr_name}' (0x{sfr_addr:02X}) 不是标准的位寻址 SFR，"
                        f"sbit '{name}' 可能无效"
                    )
                bit_addr = sfr_addr + bit_pos
                return f'__sbit __at (0x{bit_addr:02X}) {name};'
            else:
                self._warn(
                    f"SFR '{sfr_name}' 地址未知，无法计算 sbit '{name}' 的位地址。"
                    f"请在源文件中添加 sfr {sfr_name} = <地址>; 定义"
                )
                return m.group(0)
        return RE_SBIT.sub(_replace, code)

    def convert_code_memory(self, code):
        def _replace(m):
            prefix = m.group(1)
            return f'__code {prefix}'
        return RE_CODE_TYPE.sub(_replace, code)

    def convert_interrupt(self, code):
        def _replace(m):
            n = m.group(1)
            return f') __interrupt ({n})'
        return RE_INTERRUPT.sub(_replace, code)

    def convert_interrupt_using(self, code):
        def _replace(m):
            n, m_num = m.group(1), m.group(2)
            return f') __interrupt ({n}) __using ({m_num})'
        return RE_INTERRUPT_USING.sub(_replace, code)

    def convert_bit_type(self, code):
        return RE_BIT_TYPE.sub('__bit', code)

    def convert_memory_qualifiers(self, code):
        code = RE_XDATA.sub('__xdata', code)
        code = RE_IDATA.sub('__idata', code)
        code = RE_PDATA.sub('__pdata', code)
        code = RE_DATA_QUAL.sub('__data', code)
        return code

    def convert_at_keyword(self, code):
        return RE_AT_KEYWORD.sub('__at', code)

    def convert_using(self, code):
        def _replace(m):
            n = m.group(1)
            return f') __using ({n})'
        return RE_USING.sub(_replace, code)

    def convert_all(self, code):
        self.warnings = []
        self.errors = []
        self.sfr_map = dict(SFR_BASE_MAP)

        self.collect_sfr(code)

        pipeline = [
            ('替换头文件', self.convert_includes),
            ('转换 sfr', self.convert_sfr),
            ('转换 sbit', self.convert_sbit),
            ('转换 code 限定符', self.convert_code_memory),
            ('转换 interrupt+using', self.convert_interrupt_using),
            ('转换 interrupt', self.convert_interrupt),
            ('转换 using', self.convert_using),
            ('转换 bit 类型', self.convert_bit_type),
            ('转换内存限定符', self.convert_memory_qualifiers),
            ('转换 _at_', self.convert_at_keyword),
        ]

        for step_name, converter in pipeline:
            try:
                code = converter(code)
            except Exception as e:
                self._err(f"步骤 '{step_name}' 出错: {e}")

        return code, self.warnings, self.errors


# ============================================================
# SDCC 编译后端（v3.0：自动适配内置/系统 SDCC）
# ============================================================

class SDCCCompiler:
    """封装 SDCC 调用和 .hex 生成。支持内置和系统 SDCC。"""

    def __init__(self, sdcc_path=None, log_callback=None):
        self.sdcc_path = sdcc_path or find_sdcc()
        self.sdcc_home = get_sdcc_home(self.sdcc_path)
        self.log = log_callback or (lambda msg: None)
        self.temp_dir = None

    def compile(self, source_file, memory_model='small'):
        """
        编译转换后的 SDCC 源文件。
        返回 (success, hex_file_path, log_output)。
        """
        self.temp_dir = tempfile.mkdtemp(prefix='keil2hex_')
        self.log(f"[信息] 临时目录: {self.temp_dir}")

        src_name = os.path.basename(source_file)
        tmp_src = os.path.join(self.temp_dir, src_name)
        shutil.copy2(source_file, tmp_src)

        # 构建 SDCC 命令
        cmd = [
            self.sdcc_path,
            '-mmcs51',
            f'--model-{memory_model}',
            '--opt-code-size',
        ]

        # 内置 SDCC：明确指定 include 和 lib 路径（确保可靠）
        if self.sdcc_home:
            inc_dir = os.path.join(self.sdcc_home, 'include')
            inc_mcs51 = os.path.join(self.sdcc_home, 'include', 'mcs51')
            if os.path.isdir(inc_dir):
                cmd.extend(['-I', inc_dir])
            if os.path.isdir(inc_mcs51):
                cmd.extend(['-I', inc_mcs51])

        cmd.append(tmp_src)

        self.log(f"[命令] {' '.join(cmd)}")

        # 设置环境变量，确保 SDCC 找到其组件
        env = os.environ.copy()
        if self.sdcc_home:
            env['SDCC_HOME'] = self.sdcc_home
            # 将 SDCC bin 加入 PATH，以便 sdcc 找到 sdcpp, sdas8051 等
            sdcc_bin = os.path.join(self.sdcc_home, 'bin')
            if os.path.isdir(sdcc_bin):
                env['PATH'] = sdcc_bin + os.pathsep + env.get('PATH', '')

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.temp_dir,
                env=env,
            )
        except subprocess.TimeoutExpired:
            self.log("[错误] SDCC 编译超时（60秒）")
            return False, None, "SDCC 编译超时（60秒）"
        except FileNotFoundError:
            self.log(f"[错误] 找不到 SDCC: {self.sdcc_path}")
            return False, None, f"找不到 SDCC 编译器: {self.sdcc_path}"

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        full_output = stdout + ('\n' + stderr if stderr else '')

        if full_output:
            for line in full_output.split('\n'):
                self.log(f"[SDCC] {line}")

        if result.returncode != 0:
            self.log(f"[错误] SDCC 返回码: {result.returncode}")
            return False, None, full_output

        base_name = os.path.splitext(src_name)[0]
        ihx_file = os.path.join(self.temp_dir, f'{base_name}.ihx')

        if not os.path.isfile(ihx_file):
            self.log(f"[错误] 未找到 .ihx 文件: {ihx_file}")
            for f in os.listdir(self.temp_dir):
                self.log(f"[调试] 临时文件: {f}")
            return False, None, f"编译完成但未生成 .ihx 文件"

        self.log(f"[信息] 已生成 .ihx: {ihx_file}")

        hex_file = os.path.join(self.temp_dir, f'{base_name}.hex')
        packihx = get_packihx_path(self.sdcc_path)

        try:
            with open(hex_file, 'w') as f_out:
                subprocess.run(
                    [packihx, ihx_file],
                    stdout=f_out,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15,
                )
        except Exception as e:
            self.log(f"[警告] packihx 失败: {e}，直接复制 .ihx 为 .hex")
            shutil.copy2(ihx_file, hex_file)

        if os.path.isfile(hex_file):
            size = os.path.getsize(hex_file)
            self.log(f"[成功] 生成 .hex 文件: {hex_file} ({size} bytes)")
            return True, hex_file, full_output
        else:
            return False, None, "packihx 未能生成 .hex 文件"

    @staticmethod
    def copy_hex(hex_path, output_path):
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        shutil.copy2(hex_path, output_path)
        return output_path

    def cleanup(self):
        if self.temp_dir and os.path.isdir(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = None


# ============================================================
# GUI 应用
# ============================================================

class ConverterApp:
    """tkinter GUI 主应用 — 支持文件模式和代码模式，支持内置 SDCC。"""

    MODE_FILE = 0
    MODE_CODE = 1

    def __init__(self):
        self.root = Tk()

        # 标题标注封装状态
        if _get_bundled_sdcc_home():
            self.root.title(f"{APP_TITLE} v{APP_VERSION} (独立封装版)")
        else:
            self.root.title(f"{APP_TITLE} v{APP_VERSION}")

        self.root.geometry("860x700")
        self.root.minsize(700, 520)

        self._setup_style()

        self.source_path = StringVar()
        self.output_path = StringVar()
        self.output_dir = StringVar()
        self.selected_mcu = StringVar(value=MCU_MODELS[0])
        self.selected_model = StringVar(value=MEMORY_MODELS[0])
        self.running = BooleanVar(value=False)
        self.current_mode = IntVar(value=self.MODE_FILE)

        self.log_queue = queue.Queue()
        self.converted_code = None

        self.converter = KeilToSDCCConverter()
        self.compiler = None

        self._build_ui()
        self._setup_drag_drop()
        self._poll_log_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- 样式 ----

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use('vista')
        except Exception:
            try:
                style.theme_use('clam')
            except Exception:
                pass

        self.mono_font = tkfont.Font(family='Consolas', size=10)
        if 'Consolas' not in tkfont.families():
            self.mono_font = tkfont.Font(family='Courier New', size=10)

        self.code_font = tkfont.Font(family='Consolas', size=11)
        if 'Consolas' not in tkfont.families():
            self.code_font = tkfont.Font(family='Courier New', size=11)

    # ---- UI 构建 ----

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill='both', expand=True)

        # 第0行：模式切换
        self._build_mode_selector(main_frame)

        # 第1行：文件模式输入
        self.file_mode_frame = ttk.Frame(main_frame)
        self._build_file_mode_input()

        # 第1行替代：代码模式输入
        self.code_mode_frame = ttk.Frame(main_frame)
        self._build_code_mode_input()

        # 第2行：输出路径
        row2 = ttk.Frame(main_frame)
        row2.pack(fill='x', pady=(0, 6))
        ttk.Label(row2, text='输出目录:', width=10).pack(side='left')
        self.entry_output = ttk.Entry(row2, textvariable=self.output_dir)
        self.entry_output.pack(side='left', fill='x', expand=True, padx=(0, 6))
        ttk.Label(row2, text='文件名:').pack(side='left')
        self.entry_name = ttk.Entry(row2, textvariable=self.output_path, width=22)
        self.entry_name.pack(side='left', padx=(0, 6))
        ttk.Button(row2, text='浏览...', command=self._browse_output, width=8).pack(side='right')

        # 第3行：选项
        row3 = ttk.Frame(main_frame)
        row3.pack(fill='x', pady=(0, 6))
        ttk.Label(row3, text='MCU 型号:', width=10).pack(side='left')
        self.cmb_mcu = ttk.Combobox(
            row3, textvariable=self.selected_mcu,
            values=MCU_MODELS, state='readonly', width=22
        )
        self.cmb_mcu.pack(side='left', padx=(0, 16))
        ttk.Label(row3, text='存储模式:').pack(side='left')
        self.cmb_model = ttk.Combobox(
            row3, textvariable=self.selected_model,
            values=MEMORY_MODELS, state='readonly', width=8
        )
        self.cmb_model.pack(side='left')

        # 第4行：Notebook（预览 + 日志）
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True, pady=(6, 6))

        preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(preview_frame, text='转换预览')
        self.preview_text = scrolledtext.ScrolledText(
            preview_frame, wrap='none', font=self.mono_font,
            bg='#f8f8f8', fg='#333333'
        )
        self.preview_text.pack(fill='both', expand=True)
        self.preview_text.bind('<Key>', lambda e: 'break')

        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text='编译日志')
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap='none', font=self.mono_font,
            bg='#1e1e1e', fg='#d4d4d4'
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.tag_config('error', foreground='#f44747')
        self.log_text.tag_config('warning', foreground='#e5c07b')
        self.log_text.tag_config('success', foreground='#6a9955')
        self.log_text.tag_config('info', foreground='#569cd6')
        self.log_text.tag_config('cmd', foreground='#ce9178')

        # 第5行：按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(0, 4))

        self.btn_convert = ttk.Button(
            btn_frame, text='▶ 转换并编译', command=self._start_conversion,
            width=16
        )
        self.btn_convert.pack(side='left', padx=(0, 6))

        self.btn_save_c = ttk.Button(
            btn_frame, text='💾 保存转换后的 .c', command=self._save_converted_c,
            width=20
        )
        self.btn_save_c.pack(side='left', padx=(0, 6))

        self.btn_open_output = ttk.Button(
            btn_frame, text='📂 打开输出目录', command=self._open_output_dir,
            width=16
        )
        self.btn_open_output.pack(side='left', padx=(0, 6))

        ttk.Button(
            btn_frame, text='清除日志', command=self._clear_log, width=10
        ).pack(side='right')

        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill='x')
        self.status_var = StringVar(value='就绪 — 选择文件或粘贴代码，然后点击"转换并编译"')
        ttk.Label(status_frame, textvariable=self.status_var, relief='sunken',
                  anchor='w', padding=(6, 2)).pack(fill='x')

        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')

        self._switch_mode_ui()

    # ---- 模式选择器 ----

    def _build_mode_selector(self, parent):
        mode_frame = ttk.Frame(parent)
        mode_frame.pack(fill='x', pady=(0, 8))

        ttk.Label(mode_frame, text='工作模式:', width=10).pack(side='left')

        self.btn_file_mode = ttk.Button(
            mode_frame, text='📁 文件模式',
            command=lambda: self._set_mode(self.MODE_FILE),
            width=18
        )
        self.btn_file_mode.pack(side='left', padx=(0, 4))

        self.btn_code_mode = ttk.Button(
            mode_frame, text='✏️ 代码模式（直接粘贴）',
            command=lambda: self._set_mode(self.MODE_CODE),
            width=24
        )
        self.btn_code_mode.pack(side='left')

        self.mode_hint = ttk.Label(mode_frame, text='', foreground='gray')
        self.mode_hint.pack(side='left', padx=(12, 0))

    def _set_mode(self, mode):
        if self.running.get():
            messagebox.showwarning('正在编译', '编译进行中，请等待完成后再切换模式。')
            return
        self.current_mode.set(mode)
        self._switch_mode_ui()

    def _switch_mode_ui(self):
        mode = self.current_mode.get()
        if mode == self.MODE_FILE:
            self.code_mode_frame.pack_forget()
            self.file_mode_frame.pack(fill='x', pady=(0, 6))
            self.btn_file_mode.state(['disabled'])
            self.btn_code_mode.state(['!disabled'])
            self.mode_hint.config(text='选择本地 .c 文件进行转换')
            self._set_status('文件模式 — 请选择或拖放 Keil C51 源文件 (.c)')
        else:
            self.file_mode_frame.pack_forget()
            self.code_mode_frame.pack(fill='both', expand=False, pady=(0, 6))
            self.btn_code_mode.state(['disabled'])
            self.btn_file_mode.state(['!disabled'])
            self.mode_hint.config(text='直接粘贴 C51 代码，无需保存文件')
            self._set_status('代码模式 — 在编辑器中粘贴 Keil C51 代码，然后点击"转换并编译"')

    # ---- 文件模式输入 ----

    def _build_file_mode_input(self):
        ttk.Label(self.file_mode_frame, text='源文件 (.c):', width=10).pack(side='left')
        self.entry_source = ttk.Entry(self.file_mode_frame, textvariable=self.source_path)
        self.entry_source.pack(side='left', fill='x', expand=True, padx=(0, 6))
        self.entry_source.insert(0, '(拖放 .c 文件到此处，或点击浏览)')
        self.entry_source.bind('<FocusIn>', self._on_source_focus)
        self.entry_source.bind('<FocusOut>', self._on_source_blur)
        ttk.Button(self.file_mode_frame, text='浏览...', command=self._browse_source, width=8).pack(side='right')

    # ---- 代码模式输入 ----

    def _build_code_mode_input(self):
        lbl_frame = ttk.Frame(self.code_mode_frame)
        lbl_frame.pack(fill='x')
        ttk.Label(lbl_frame, text='C51 代码:', width=10).pack(side='left')
        ttk.Label(lbl_frame, text='（直接粘贴 Keil C51 代码到下方编辑区）',
                  foreground='#888888').pack(side='left')

        editor_frame = ttk.Frame(self.code_mode_frame)
        editor_frame.pack(fill='both', expand=True, pady=(2, 0))

        self.code_editor = scrolledtext.ScrolledText(
            editor_frame, wrap='none', font=self.code_font,
            bg='#ffffff', fg='#1e1e1e', insertbackground='#000000',
            undo=True, maxundo=50,
        )
        self.code_editor.pack(fill='both', expand=True)
        self.code_editor.config(height=12)

        self._code_placeholder = (
            '/* 在此粘贴 Keil C51 代码 */\n'
            '/* 例如: */\n'
            '#include <REG52.H>\n'
            '\n'
            'void delay(unsigned int t) {\n'
            '    while (t--) { }\n'
            '}\n'
            '\n'
            'void main() {\n'
            '    while (1) {\n'
            '        P1 = 0x55;\n'
            '        delay(50000);\n'
            '        P1 = 0xAA;\n'
            '        delay(50000);\n'
            '    }\n'
            '}\n'
        )
        self.code_editor.insert('1.0', self._code_placeholder)
        self.code_editor.config(fg='#aaaaaa')
        self.code_editor.bind('<FocusIn>', self._on_code_editor_focus)
        self.code_editor.bind('<FocusOut>', self._on_code_editor_blur)
        self._code_editor_has_placeholder = True

    # ---- 代码编辑器事件 ----

    def _on_code_editor_focus(self, event):
        if self._code_editor_has_placeholder:
            self.code_editor.delete('1.0', 'end')
            self.code_editor.config(fg='#1e1e1e')
            self._code_editor_has_placeholder = False

    def _on_code_editor_blur(self, event):
        content = self.code_editor.get('1.0', 'end-1c').strip()
        if not content and not self._code_editor_has_placeholder:
            self.code_editor.insert('1.0', self._code_placeholder)
            self.code_editor.config(fg='#aaaaaa')
            self._code_editor_has_placeholder = True

    def _get_code_editor_content(self):
        if self._code_editor_has_placeholder:
            return ''
        return self.code_editor.get('1.0', 'end-1c')

    # ---- 拖放支持 ----

    def _setup_drag_drop(self):
        if sys.platform != 'win32':
            self._log('info', '[信息] 拖放功能仅支持 Windows')
            return
        try:
            import ctypes
            self._ctypes = ctypes
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
            GWL_WNDPROC = -4
            self._old_wndproc = ctypes.windll.user32.SetWindowLongPtrW(
                hwnd, GWL_WNDPROC,
                ctypes.cast(self._wnd_proc, ctypes.c_void_p).value
            )
            self._wnd_proc_ref = self._wnd_proc
        except Exception as e:
            self._log('warning', f'[警告] 拖放初始化失败: {e}，请使用"浏览"按钮选择文件')

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        WM_DROPFILES = 0x0233
        if msg == WM_DROPFILES:
            try:
                import ctypes
                MAX_PATH = 260
                buf = ctypes.create_unicode_buffer(MAX_PATH)
                ctypes.windll.shell32.DragQueryFileW(wparam, 0, buf, MAX_PATH)
                filepath = buf.value
                ctypes.windll.shell32.DragFinish(wparam)
                self._set_mode(self.MODE_FILE)
                if filepath.lower().endswith(('.c', '.h', '.txt')):
                    self.source_path.set(filepath)
                    self._auto_set_output(filepath)
                    self._log('info', f'[拖放] 已加载: {filepath}')
                else:
                    messagebox.showwarning(
                        '文件类型',
                        f'不支持的文件类型。请拖放 .c 或 .h 文件。\n当前文件: {filepath}'
                    )
                return 0
            except Exception as e:
                self._log('error', f'[错误] 处理拖放文件时出错: {e}')
        return self._ctypes.windll.user32.CallWindowProcW(
            self._old_wndproc, hwnd, msg, wparam, lparam
        )

    # ---- 事件处理 ----

    def _on_source_focus(self, event):
        if self.source_path.get() == '(拖放 .c 文件到此处，或点击浏览)':
            self.source_path.set('')

    def _on_source_blur(self, event):
        if not self.source_path.get():
            self.source_path.set('(拖放 .c 文件到此处，或点击浏览)')

    def _browse_source(self):
        path = filedialog.askopenfilename(
            title='选择 C51 源文件',
            filetypes=[
                ('C 源文件', '*.c'), ('头文件', '*.h'),
                ('文本文件', '*.txt'), ('所有文件', '*.*'),
            ]
        )
        if path:
            self.source_path.set(path)
            self._auto_set_output(path)

    def _browse_output(self):
        directory = filedialog.askdirectory(title='选择输出目录')
        if directory:
            self.output_dir.set(directory)
            self._update_full_output_path()

    def _auto_set_output(self, source_path):
        src = Path(source_path)
        self.output_dir.set(str(src.parent))
        self.output_path.set(src.stem + '.hex')

    def _update_full_output_path(self):
        name = self.entry_name.get()
        if name:
            self.output_path.set(name)

    # ---- 日志 ----

    def _log(self, tag, message):
        self.log_queue.put((tag, message))

    def _poll_log_queue(self):
        try:
            while True:
                tag, message = self.log_queue.get_nowait()
                self._log_text_insert(tag, message)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _log_text_insert(self, tag, message):
        self.log_text.insert('end', message + '\n', tag)
        self.log_text.see('end')
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 2000:
            self.log_text.delete('1.0', '500.0')

    def _clear_log(self):
        self.log_text.delete('1.0', 'end')
        self.preview_text.delete('1.0', 'end')
        self.converted_code = None

    # ---- 状态 ----

    def _set_status(self, message):
        self.root.after(0, lambda: self.status_var.set(message))

    def _set_running(self, running):
        self.running.set(running)
        self.root.after(0, self._update_ui_state)

    def _update_ui_state(self):
        if self.running.get():
            self.btn_convert.config(text='⏳ 编译中...', state='disabled')
            self.progress.pack(side='right', padx=(8, 4))
            self.progress.start(10)
            self.btn_file_mode.state(['disabled'])
            self.btn_code_mode.state(['disabled'])
        else:
            self.btn_convert.config(text='▶ 转换并编译', state='normal')
            self.progress.stop()
            self.progress.pack_forget()
            mode = self.current_mode.get()
            if mode == self.MODE_FILE:
                self.btn_file_mode.state(['disabled'])
                self.btn_code_mode.state(['!disabled'])
            else:
                self.btn_code_mode.state(['disabled'])
                self.btn_file_mode.state(['!disabled'])

    # ---- 预览 ----

    def _show_preview(self, code):
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', code)
        self.converted_code = code

    # ---- 核心转换流程 ----

    def _start_conversion(self):
        if self.running.get():
            return

        mode = self.current_mode.get()

        if mode == self.MODE_FILE:
            source = self.source_path.get()
            placeholder = '(拖放 .c 文件到此处，或点击浏览)'
            if not source or source == placeholder:
                messagebox.showwarning('缺少源文件', '请先选择或拖放一个 .c 源文件。')
                return
            if not os.path.isfile(source):
                messagebox.showerror('文件不存在', f'找不到文件:\n{source}')
                return
        else:
            code = self._get_code_editor_content()
            if not code.strip():
                messagebox.showwarning('缺少代码', '请在代码编辑器中粘贴 Keil C51 代码。')
                return
            source = None

        out_dir = self.output_dir.get()
        out_name = self.output_path.get()
        if not out_dir or not out_name:
            messagebox.showwarning('缺少输出路径', '请指定输出目录和文件名。')
            return

        if mode == self.MODE_CODE and not out_name.strip():
            self.output_path.set('output.hex')
            out_name = 'output.hex'

        sdcc_path = find_sdcc()
        if not sdcc_path or sdcc_path == 'sdcc':
            try:
                subprocess.run(['sdcc', '--version'], capture_output=True, timeout=5, check=True)
            except Exception:
                messagebox.showerror(
                    '找不到 SDCC',
                    '未找到 SDCC 编译器。\n\n'
                    '如果您运行的是独立封装版（.exe），请重新下载完整版本。\n'
                    '如果您运行的是 .pyw 脚本，请安装 SDCC。'
                )
                return

        self._clear_log()
        self._log('info', f'{"="*50}')
        self._log('info', f'Keil C51 → HEX 转换器 v{APP_VERSION}')
        if _get_bundled_sdcc_home():
            self._log('info', f'运行模式: 独立封装版（内置 SDCC）')
        else:
            self._log('info', f'运行模式: 脚本版（系统 SDCC）')
        if mode == self.MODE_FILE:
            self._log('info', f'工作模式: 文件模式')
            self._log('info', f'源文件: {source}')
        else:
            self._log('info', f'工作模式: 代码模式（直接粘贴）')
            code_preview = self._get_code_editor_content().strip()[:80].replace('\n', ' ')
            self._log('info', f'代码片段: {code_preview}...')
        self._log('info', f'输出路径: {os.path.join(out_dir, out_name)}')
        self._log('info', f'MCU: {self.selected_mcu.get()}')
        self._log('info', f'存储模式: {self.selected_model.get()}')
        self._log('info', f'SDCC: {sdcc_path}')
        self._log('info', f'{"="*50}')

        self._set_running(True)
        self._set_status('正在转换和编译...')

        thread = threading.Thread(
            target=self._conversion_thread,
            args=(mode, source, out_dir, out_name, sdcc_path),
            daemon=True
        )
        thread.start()

    def _conversion_thread(self, mode, source, out_dir, out_name, sdcc_path):
        output_hex = None
        compiler = None

        try:
            # 步骤1: 获取源代码
            self._log('info', '\n[步骤 1/6] 读取源代码...')
            if mode == self.MODE_FILE:
                enc, code = KeilToSDCCConverter.detect_encoding(source)
                self._log('info', f'  检测到编码: {enc}')
                self._log('info', f'  文件大小: {len(code)} 字符')
                src_stem = Path(source).stem
            else:
                code = self._get_code_editor_content()
                enc = 'utf-8'
                self._log('info', f'  代码长度: {len(code)} 字符（从编辑器直接读取）')
                src_stem = 'pasted_code'

            if not code.strip():
                self._log('error', '[错误] 源代码为空！')
                self._set_status('错误：源代码为空')
                return

            # 步骤2: 转换
            self._log('info', '\n[步骤 2/6] 转换 Keil C51 → SDCC 语法...')
            converted, warnings, errors = self.converter.convert_all(code)
            for w in warnings:
                self._log('warning', f'  ⚠ 警告: {w}')
            for e in errors:
                self._log('error', f'  ✗ 错误: {e}')
            if errors:
                self._log('error', '\n[失败] 转换阶段出现错误，已中止。')
                self._set_status('转换失败 — 请查看日志')
                return
            self._log('info', f'  转换完成 ({len(warnings)} 个警告, {len(errors)} 个错误)')
            self.root.after(0, lambda: self._show_preview(converted))

            # 步骤3: 写临时文件
            self._log('info', '\n[步骤 3/6] 写入转换后的源文件...')
            temp_dir = tempfile.mkdtemp(prefix='keil2hex_')
            tmp_c = os.path.join(temp_dir, src_stem + '_sdcc.c')
            with open(tmp_c, 'w', encoding='utf-8') as f:
                if mode == self.MODE_FILE:
                    f.write('// Auto-converted by Keil2Hex v3.0 from: ' + os.path.basename(source) + '\n')
                    f.write('// Original encoding: ' + enc + '\n')
                else:
                    f.write('// Auto-converted by Keil2Hex v3.0 from pasted code\n')
                f.write('// Conversion date: ' + time.strftime('%Y-%m-%d %H:%M:%S') + '\n')
                f.write('// Target MCU: ' + self.selected_mcu.get() + '\n')
                f.write('\n')
                f.write(converted)
            self._log('info', f'  写入: {tmp_c}')

            # 步骤4: 编译
            self._log('info', '\n[步骤 4/6] SDCC 编译中...')
            compiler = SDCCCompiler(sdcc_path=sdcc_path, log_callback=lambda m: self._log('info', m))
            success, hex_path, log_output = compiler.compile(
                tmp_c, memory_model=self.selected_model.get()
            )

            if not success:
                self._log('error', '\n[失败] SDCC 编译失败。请检查上方日志。')
                self._log('info', '\n[提示] 常见问题:')
                self._log('info', '  1. 源文件中使用了 SDCC 不支持的特性')
                self._log('info', '  2. SFR 地址在 sbit 转换时无法确定')
                self._log('info', '  3. 请查看"转换预览"标签页检查转换结果')
                self._set_status('编译失败 — 请查看日志')
                return

            # 步骤5: 保存 hex
            self._log('info', '\n[步骤 5/6] 保存 .hex 文件...')
            final_hex = os.path.join(out_dir, out_name)
            SDCCCompiler.copy_hex(hex_path, final_hex)
            hex_size = os.path.getsize(final_hex)
            self._log('success', f'  ✓ HEX 文件已保存: {final_hex} ({hex_size} bytes)')
            output_hex = final_hex

            # 步骤6: 内存信息
            self._log('info', '\n[步骤 6/6] 生成完成!')
            mem_file = os.path.join(compiler.temp_dir, src_stem + '_sdcc.mem')
            if os.path.isfile(mem_file):
                with open(mem_file, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if 'ROM/EPROM/FLASH' in line or 'Stack starts' in line:
                            self._log('info', f'  {line.strip()}')

            self.root.after(0, lambda: self.notebook.select(1))
            self.root.after(100, lambda: self._ask_open_output(final_hex))
            self._set_status(f'✓ 转换成功 — {os.path.basename(final_hex)} ({hex_size} bytes)')

        except Exception as e:
            self._log('error', f'\n[异常] {type(e).__name__}: {e}')
            import traceback
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self._log('error', f'  {line}')
            self._set_status(f'错误: {e}')

        finally:
            if compiler:
                compiler.cleanup()
            self._set_running(False)

    # ---- 辅助操作 ----

    def _save_converted_c(self):
        if not self.converted_code:
            messagebox.showinfo('无转换结果', '请先执行一次转换。')
            return
        mode = self.current_mode.get()
        if mode == self.MODE_FILE:
            src = Path(self.source_path.get())
            default_name = src.stem + '_sdcc.c'
        else:
            default_name = 'converted_sdcc.c'
        path = filedialog.asksaveasfilename(
            title='保存转换后的 C 文件',
            defaultextension='.c',
            initialfile=default_name,
            filetypes=[('C 源文件', '*.c'), ('所有文件', '*.*')]
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.converted_code)
            self._log('success', f'转换后的代码已保存: {path}')
            self._set_status(f'已保存转换后的代码: {os.path.basename(path)}')

    def _open_output_dir(self):
        out_dir = self.output_dir.get()
        if out_dir and os.path.isdir(out_dir):
            os.startfile(out_dir)
        else:
            messagebox.showinfo('路径不存在', '输出目录不存在，请先完成一次成功的转换。')

    def _ask_open_output(self, hex_path):
        if messagebox.askyesno('转换完成', f'HEX 文件已生成:\n{hex_path}\n\n是否打开所在文件夹？'):
            os.startfile(os.path.dirname(hex_path))

    def _on_close(self):
        if self.running.get():
            if not messagebox.askyesno('确认退出', '编译正在进行中，确定要退出吗？'):
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================
# 命令行入口
# ============================================================

def cli_convert(source_file, output_file=None):
    if not output_file:
        output_file = os.path.splitext(source_file)[0] + '.hex'

    print(f"Keil C51 → HEX Converter v{APP_VERSION} (CLI mode)")
    print(f"Source: {source_file}")
    print(f"Output: {output_file}")
    print()

    converter = KeilToSDCCConverter()
    enc, code = KeilToSDCCConverter.detect_encoding(source_file)
    print(f"Encoding: {enc}")

    converted, warnings, errors = converter.convert_all(code)
    for w in warnings:
        print(f"Warning: {w}")
    for e in errors:
        print(f"Error: {e}")
    if errors:
        return False

    temp_dir = tempfile.mkdtemp(prefix='keil2hex_cli_')
    src_name = os.path.basename(source_file)
    tmp_c = os.path.join(temp_dir, os.path.splitext(src_name)[0] + '_sdcc.c')
    with open(tmp_c, 'w', encoding='utf-8') as f:
        f.write(converted)

    compiler = SDCCCompiler()
    success, hex_path, log = compiler.compile(tmp_c)

    if success:
        SDCCCompiler.copy_hex(hex_path, output_file)
        print(f"Success! HEX saved to: {output_file}")
        print(f"Size: {os.path.getsize(output_file)} bytes")
    else:
        print(f"Compilation failed:")
        print(log)

    compiler.cleanup()
    shutil.rmtree(temp_dir, ignore_errors=True)
    return success


# ============================================================
# 主入口
# ============================================================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        src = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else None
        success = cli_convert(src, out)
        sys.exit(0 if success else 1)
    else:
        app = ConverterApp()
        app.run()
