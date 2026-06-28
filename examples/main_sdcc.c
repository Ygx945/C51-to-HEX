#include <8052.h>

#define uchar unsigned char
#define uint  unsigned int

/* STC12C5A60S2: P4 port and P4 switch register */
__sfr __at (0xC0) P4;
__sfr __at (0xBB) P4SW;

#define SEG_COMMON_CATHODE 0

#if SEG_COMMON_CATHODE
/* Common cathode segment code: segment high active */
__code uchar SegCode[10] = {
    0x3F, 0x06, 0x5B, 0x4F, 0x66,
    0x6D, 0x7D, 0x07, 0x7F, 0x6F
};
#define SEG_OFF 0x00
#define DP_MASK 0x80
#else
/* Common anode segment code: segment low active */
__code uchar SegCode[10] = {
    0xC0, 0xF9, 0xA4, 0xB0, 0x99,
    0x92, 0x82, 0xF8, 0x80, 0x90
};
#define SEG_OFF 0xFF
#define DP_MASK 0x7F
#endif

/* Digit selection uses PNP transistor, low level active */
#define DIGIT_ON  0
#define DIGIT_OFF 1

/* Key active low */
#define KEY_ACTIVE_LEVEL 0

/* Current time: 4-digit display MM:SS */
uchar Hour = 12;
uchar Minute = 12;
uchar Second = 0;

/* Display buffer: tens of min, ones of min, tens of sec, ones of sec */
uchar DisplayBuf[4] = {0, 0, 0, 0};

/* Timing variables */
uint MsCount = 0;
uchar ScanIndex = 0;

/* Keys (bit addresses for P3):
   P3 bit addresses: P3.0=0xB0, P3.1=0xB1, ..., P3.7=0xB7 */
__sbit __at (0xB3) KEY_MODE;   /* KEY1 = P3^3 */
__sbit __at (0xB5) KEY_ADD;    /* KEY2 = P3^5 */
__sbit __at (0xB6) KEY_SUB;    /* KEY3 = P3^6 */
__sbit __at (0xB7) KEY_OK;     /* KEY4 = P3^7 */

/* Digit select (P4 bit addresses: P4.0=0xC0, P4.1=0xC1, ..., P4.7=0xC7) */
__sbit __at (0xC6) BIT1;       /* P4^6 */
__sbit __at (0xC1) BIT2;       /* P4^1 */
__sbit __at (0xC5) BIT3;       /* P4^5 */
__sbit __at (0xC4) BIT4;       /* P4^4 */

/* Settings mode: 0=run, 1=set minute, 2=set second */
uchar SetMode = 0;
uint BlinkCount = 0;
__bit BlinkShow = 1;

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

    /* Mapping is reversed relative to display order */
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

__bit IsBlinkDigit(uchar index)
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

void Timer0Interrupt(void) __interrupt (1)
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
    P4SW |= 0x70;   /* Release P4.4/P4.5/P4.6 as normal GPIO */

    WriteSegment(SEG_OFF);
    AllDigitOff();

    P3 |= 0xE8;     /* P3.3/P3.5/P3.6/P3.7 set high for key reading */

    UpdateDisplayBuf();
    Timer0Init();

    while (1) {
        KeyProcess();
    }
}
