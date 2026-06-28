/**
 * pasted_project.c
 * 从 pasted_project.hex 反编译的 8051 C 代码
 * 功能: 4 位数码管显示的秒表/时钟, 4 按键控制
 * 编译: Keil C51, 12MHz 晶振
 */

#include <reg51.h>

/* ---- 引脚定义 ---- */
sbit SEG_A = P2 ^ 0;   /* 段码 a */
sbit SEG_B = P2 ^ 1;   /* 段码 b */
sbit SEG_C = P2 ^ 2;   /* 段码 c */
sbit SEG_D = P2 ^ 3;   /* 段码 d */
sbit SEG_E = P2 ^ 4;   /* 段码 e */
sbit SEG_F = P2 ^ 5;   /* 段码 f */
sbit SEG_G = P2 ^ 6;   /* 段码 g */
sbit SEG_DP = P2 ^ 7;  /* 小数点 */

sbit DIG_1 = P0 ^ 1;   /* 位选1 (P0.1) */
sbit DIG_2 = P0 ^ 2;   /* 位选2 (P0.2) */
sbit DIG_3 = P0 ^ 3;   /* 位选3 (P0.3) */

sbit KEY_MODE = P3 ^ 3;  /* 模式键 */
sbit KEY_UP   = P3 ^ 5;  /* 上调键 */
sbit KEY_DOWN = P3 ^ 6;  /* 下调键 */
sbit KEY_SET  = P3 ^ 7;  /* 设置键 */

/* ---- 全局变量 (对应 0x08~0x1F) ---- */
unsigned char data disp[4];   /* 显示缓冲区 (待显示的4个数字) */
unsigned char data mode;      /* 模式: 0=待机, 1=秒表, 2=时钟, 3=设置 */
unsigned char data sub_mode;  /* 扫描位 0~3 */
unsigned char data sec_h;     /* 秒表十位 (0~9) */
unsigned char data sec_l;     /* 秒表个位 (0~9) */
unsigned char data ds;        /* 十分之一秒 (0~9) */
unsigned char data clk_h;     /* 时钟时 (0~23) */
unsigned char data clk_m;     /* 时钟分 (0~59) */
unsigned char data cnt100_l;  /* 100ms 计数低字节 */
unsigned char data cnt100_h;  /* 100ms 计数高字节 */
unsigned char data cnt1s_l;   /* 1s 计数低字节 */
unsigned char data cnt1s_h;   /* 1s 计数高字节 */
unsigned char data cnt500_l;  /* 0.5s 闪烁计数低 */
unsigned char data cnt500_h;  /* 0.5s 闪烁计数高 */
unsigned char data scan_idx;  /* 当前扫描位索引 */
unsigned char data blink;     /* 闪烁标志 */
unsigned char data last_key;  /* 上次按键值 */

/* ---- 7 段码表 (0x03C0) ---- */
unsigned char code seg_tab[] = {
    0xFA,  /* 0 */
    0x22,  /* 1 */
    0xB9,  /* 2 */
    0xAB,  /* 3 */
    0x63,  /* 4 */
    0xCB,  /* 5 */
    0xDB,  /* 6 */
    0xA2,  /* 7 */
    0xFB,  /* 8 */
    0xEB,  /* 9 */
    0xFF   /* 空 (0x0A) */
};

/* ---- 数字转段码 ---- */
unsigned char get_seg(unsigned char n)
{
    if (n > 9) return 0xFF;   /* 越界返回全灭 */
    return seg_tab[n];
}

/* ---- 初始化定时器0 ---- */
void init_timer0(void)
{
    TMOD &= 0xF0;   /* 保留 T1 */
    TMOD |= 0x01;   /* T0 模式1: 16位 */
    TH0   = 0xFC;   /* 1ms @ 12MHz */
    TL0   = 0x18;
    ET0   = 1;      /* 开 T0 中断 */
    EA    = 1;      /* 开总中断 */
    TR0   = 1;      /* 启动 T0 */
}

/* ---- 十进制进位 ---- */
void time_tick(void)
{
    ds++;                      /* 0.1 秒 +1 */
    if (ds >= 10) {
        ds = 0;
        sec_l++;               /* 秒个位 +1 */
        if (sec_l >= 10) {
            sec_l = 0;
            sec_h++;           /* 秒十位 +1 */
            if (sec_h >= 10) {
                sec_h = 0;
            }
        }
    }
}

/* ---- 时钟进位 ---- */
void clock_tick(void)
{
    clk_m++;                   /* 分 +1 */
    if (clk_m >= 60) {
        clk_m = 0;
        clk_h++;               /* 时 +1 */
        if (clk_h >= 24) {
            clk_h = 0;
        }
    }
}

/* ---- 准备秒表显示 ---- */
void prep_stopwatch(void)
{
    disp[0] = sec_h;
    disp[1] = sec_l;
    disp[2] = ds;
    disp[3] = 0xFF;   /* 空 */
}

/* ---- 准备时钟显示 ---- */
void prep_clock(void)
{
    disp[0] = clk_h / 10;
    disp[1] = clk_h % 10;
    disp[2] = clk_m / 10;
    disp[3] = clk_m % 10;
}

/* ---- 显示刷新 (在中断里调用) ---- */
void display_scan(void)
{
    unsigned char seg;

    /* 先关闭所有位选 */
    DIG_1 = 1;
    DIG_2 = 1;
    DIG_3 = 1;

    /* 跳过空白位 */
    if (disp[scan_idx] == 0xFF) {
        /* 这一位不显示 */
    } else {
        seg = get_seg(disp[scan_idx]);

        /* 第2和第3位之间的小数点: 秒表模式亮 */
        if (mode == 1 && scan_idx == 2) {
            seg &= ~0x80;   /* 点亮 DP (假设低有效) */
        }
        /* 第1和第2位之间的冒号: 时钟模式且闪烁 */
        if (mode == 2 && scan_idx == 1 && blink) {
            /* 冒号位特殊处理 */
        }

        P2 = seg;   /* 输出段码 */

        /* 位选 */
        if (scan_idx == 0)      DIG_1 = 0;
        else if (scan_idx == 1) DIG_2 = 0;
        else if (scan_idx == 2) DIG_3 = 0;
    }

    /* 下一位 */
    scan_idx++;
    if (scan_idx >= 4) scan_idx = 0;
}

/* ---- 按键扫描 ---- */
unsigned char read_keys(void)
{
    if (!KEY_MODE) return 1;
    if (!KEY_UP)   return 2;
    if (!KEY_DOWN) return 3;
    if (!KEY_SET)  return 4;
    return 0xFF;   /* 无按键 */
}

/* ---- 按键处理 ---- */
void handle_keys(void)
{
    unsigned char key;

    key = read_keys();

    if (key == 0xFF) {
        /* 无按键 */
        if (last_key == 0xFF) {
            /* 连续无按键, 短暂延时消抖 */
            unsigned int i;
            for (i = 0; i < 100; i++);
        }
        return;
    }

    /* 等待按键释放才执行动作 (简单消抖) */
    if (key == last_key) return;

    /* 按键分发 */
    if (key == 1) {
        /* 模式键: 循环切换子模式 */
        mode = 0;
        sub_mode++;
        if (sub_mode >= 3) sub_mode = 0;
    }
    else if (key == 2) {
        /* 上调键: 秒表模式 */
        mode = 1;
    }
    else if (key == 3) {
        /* 下调键: 时钟模式 */
        mode = 2;
    }
    else if (key == 4) {
        /* 设置键 */
        mode = 3;
    }

    /* 等待全部释放 */
    while (read_keys() != 0xFF);
    last_key = 0xFF;
}

/* ---- 定时器0 中断 (每1ms) ---- */
void timer0_isr(void) __interrupt(1)
{
    /* 重载 */
    TH0 = 0xFC;
    TL0 = 0x18;

    /* ---- 100ms 计时 ---- */
    cnt100_l++;
    if (cnt100_l == 0) cnt100_h++;
    if (cnt100_h >= 100 || (cnt100_h == 0 && cnt100_l >= 100)) {
        cnt100_l = 0;
        cnt100_h = 0;
        time_tick();   /* 秒表走时 */
    }

    /* ---- 1秒计时 ---- */
    cnt1s_l++;
    if (cnt1s_l == 0) cnt1s_h++;
    if (cnt1s_h >= 3 && cnt1s_l >= 0xE8) {   /* >= 1000 */
        cnt1s_l = 0;
        cnt1s_h = 0;
        clock_tick();   /* 时钟走时 */
    }

    /* ---- 0.5秒闪烁 ---- */
    cnt500_l++;
    if (cnt500_l == 0) cnt500_h++;
    if (cnt500_h >= 1 && cnt500_l >= 0xF4) {  /* >= 500 */
        cnt500_l = 0;
        cnt500_h = 0;
        blink = !blink;   /* 闪烁翻转 */
    }

    /* ---- 准备显示 ---- */
    if (mode == 1) {
        prep_stopwatch();
    } else if (mode == 2) {
        prep_clock();
    } else {
        /* 待机/设置: 全零 */
        disp[0] = 0;
        disp[1] = 0;
        disp[2] = 0;
        disp[3] = 0;
    }

    /* ---- 刷新当前位 ---- */
    display_scan();
}

/* ---- 主程序 ---- */
void main(void)
{
    /* 变量初始化 */
    {
        unsigned char i;
        unsigned char data *p = (unsigned char data *)0x08;
        for (i = 0; i < 24; i++) *p++ = 0;
    }
    last_key = 0xFF;
    mode     = 0;
    sub_mode = 0;

    /* 硬件初始化 */
    P0 = 0xFF;   /* LED 全灭 */
    P2 = 0xFF;   /* 段码全灭 */
    init_timer0();

    /* 主循环: 只处理按键, 显示在中断中刷新 */
    while (1) {
        handle_keys();
    }
}
