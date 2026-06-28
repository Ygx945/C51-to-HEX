#include <REG52.H>

#define uchar unsigned char
#define uint  unsigned int

/* STC12C5A60S2 的 P4 口和 P4 功能切换寄存器 */
sfr P4 = 0xC0;
sfr P4SW = 0xBB;

#define SEG_COMMON_CATHODE 0

#if SEG_COMMON_CATHODE
/* 共阴极段码：段线高电平点亮 */
uchar code SegCode[10] = {
    0x3F, 0x06, 0x5B, 0x4F, 0x66,
    0x6D, 0x7D, 0x07, 0x7F, 0x6F
};
#define SEG_OFF 0x00
#define DP_MASK 0x80
#else
/* 共阳极段码：段线低电平点亮 */
uchar code SegCode[10] = {
    0xC0, 0xF9, 0xA4, 0xB0, 0x99,
    0x92, 0x82, 0xF8, 0x80, 0x90
};
#define SEG_OFF 0xFF
#define DP_MASK 0x7F
#endif

/* 位选使用 PNP 三极管驱动，低电平有效 */
#define DIGIT_ON  0
#define DIGIT_OFF 1

/* 按键按下为低电平 */
#define KEY_ACTIVE_LEVEL 0

/* 当前时间值，4 位数码管显示 MM:SS */
uchar Hour = 12;
uchar Minute = 12;
uchar Second = 0;

/* 显示缓冲区：分十、分个、秒十、秒个 */
uchar DisplayBuf[4] = {0, 0, 0, 0};

/* 定时器计数变量 */
uint MsCount = 0;
uchar ScanIndex = 0;

/* 按键引脚 */
sbit KEY_MODE = P3^3;   /* KEY1 */
sbit KEY_ADD  = P3^5;   /* KEY2 */
sbit KEY_SUB  = P3^6;   /* KEY3 */
sbit KEY_OK   = P3^7;   /* KEY4 */

/* 位选引脚 */
sbit BIT1 = P4^6;
sbit BIT2 = P4^1;
sbit BIT3 = P4^5;
sbit BIT4 = P4^4;

/* 设置模式：0 正常，1 调分钟，2 调秒 */
uchar SetMode = 0;
uint BlinkCount = 0;
bit BlinkShow = 1;

void UpdateDisplayBuf(void)
{
    DisplayBuf[0] = Minute / 10;
    DisplayBuf[1] = Minute % 10;
    DisplayBuf[2] = Second / 10;
    DisplayBuf[3] = Second % 10;
}

void ClockAddOneSecond(void)
{
    Second++;
    if (Second >= 60) {
        Second = 0;
        Minute++;
        if (Minute >= 60) {
            Minute = 0;
            Hour++;
            if (Hour >= 24) {
                Hour = 0;
            }
        }
    }

    UpdateDisplayBuf();
}

void AllDigitOff(void)
{
    BIT1 = DIGIT_OFF;
    BIT2 = DIGIT_OFF;
    BIT3 = DIGIT_OFF;
    BIT4 = DIGIT_OFF;
}

void SelectDigit(uchar index)
{
    AllDigitOff();

    /* 物理位选顺序与显示顺序相反，这里反向映射 */
    switch (index) {
    case 0:
        BIT4 = DIGIT_ON;
        break;
    case 1:
        BIT3 = DIGIT_ON;
        break;
    case 2:
        BIT2 = DIGIT_ON;
        break;
    case 3:
        BIT1 = DIGIT_ON;
        break;
    default:
        break;
    }
}

uchar MapSegmentToP2(uchar codeValue)
{
    uchar p2Value = 0;

    /* A=P2.7, B=P2.5, C=P2.1, D=P2.3, E=P2.4, F=P2.6, G=P2.0, DP=P2.2 */
    if (codeValue & 0x01) p2Value |= 0x80;
    if (codeValue & 0x02) p2Value |= 0x20;
    if (codeValue & 0x04) p2Value |= 0x02;
    if (codeValue & 0x08) p2Value |= 0x08;
    if (codeValue & 0x10) p2Value |= 0x10;
    if (codeValue & 0x20) p2Value |= 0x40;
    if (codeValue & 0x40) p2Value |= 0x01;
    if (codeValue & 0x80) p2Value |= 0x04;

    return p2Value;
}

void WriteSegment(uchar codeValue)
{
    P2 = MapSegmentToP2(codeValue);
}

bit IsBlinkDigit(uchar index)
{
    if ((SetMode == 1) && (index < 2)) {
        return 1;
    }
    if ((SetMode == 2) && (index >= 2) && (index < 4)) {
        return 1;
    }
    return 0;
}

void DisplayScan(void)
{
    uchar codeValue;

    AllDigitOff();
    WriteSegment(SEG_OFF);

    codeValue = SegCode[DisplayBuf[ScanIndex]];

#if SEG_COMMON_CATHODE
    if (ScanIndex == 1) {
        codeValue |= DP_MASK;
    }
#else
    if (ScanIndex == 1) {
        codeValue &= DP_MASK;
    }
#endif

    if ((SetMode != 0) && (BlinkShow == 0) && IsBlinkDigit(ScanIndex)) {
        codeValue = SEG_OFF;
    }

    WriteSegment(codeValue);
    SelectDigit(ScanIndex);

    ScanIndex++;
    if (ScanIndex >= 4) {
        ScanIndex = 0;
    }
}

void Timer0Init(void)
{
    TMOD &= 0xF0;
    TMOD |= 0x01;

    TH0 = 0xFC;
    TL0 = 0x18;

    ET0 = 1;
    EA = 1;
    TR0 = 1;
}

void Timer0Interrupt(void) interrupt 1
{
    TH0 = 0xFC;
    TL0 = 0x18;

    DisplayScan();

    BlinkCount++;
    if (BlinkCount >= 250) {
        BlinkCount = 0;
        BlinkShow = !BlinkShow;
    }

    MsCount++;
    if (MsCount >= 1000) {
        MsCount = 0;
        ClockAddOneSecond();
    }
}

uchar LastMode = 1;
uchar LastAdd  = 1;
uchar LastSub  = 1;
uchar LastOk   = 1;

void KeyProcess(void)
{
    uchar nowMode = KEY_MODE;
    uchar nowAdd  = KEY_ADD;
    uchar nowSub  = KEY_SUB;
    uchar nowOk   = KEY_OK;

    if((nowMode == KEY_ACTIVE_LEVEL) && (LastMode != KEY_ACTIVE_LEVEL))
    {
        SetMode++;
        if(SetMode > 2) SetMode = 0;
        BlinkCount = 0;
        BlinkShow = 1;
    }

    if((nowAdd == KEY_ACTIVE_LEVEL) && (LastAdd != KEY_ACTIVE_LEVEL))
    {
        if(SetMode == 1) {
            Minute++;
            if(Minute >= 60) Minute = 0;
        } else if(SetMode == 2) {
            Second++;
            if(Second >= 60) Second = 0;
        }

        UpdateDisplayBuf();
    }

    if((nowSub == KEY_ACTIVE_LEVEL) && (LastSub != KEY_ACTIVE_LEVEL))
    {
        if(SetMode == 1) {
            if(Minute == 0) Minute = 59;
            else Minute--;
        } else if(SetMode == 2) {
            if(Second == 0) Second = 59;
            else Second--;
        }

        UpdateDisplayBuf();
    }

    if((nowOk == KEY_ACTIVE_LEVEL) && (LastOk != KEY_ACTIVE_LEVEL))
    {
        Second = 0;
        SetMode = 0;
        BlinkCount = 0;
        BlinkShow = 1;
        UpdateDisplayBuf();
    }

    LastMode = nowMode;
    LastAdd  = nowAdd;
    LastSub  = nowSub;
    LastOk   = nowOk;
}

void main(void)
{
    P4SW |= 0x70;   /* 释放 P4.4/P4.5/P4.6 为普通 GPIO */

    WriteSegment(SEG_OFF);
    AllDigitOff();

    P3 |= 0xE8;     /* P3.3/P3.5/P3.6/P3.7 写 1，准备读取按键 */

    UpdateDisplayBuf();
    Timer0Init();

    while (1) {
        KeyProcess();
    }
}