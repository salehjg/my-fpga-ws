/*
 * blinky.c - LED blinker + DDR3 (MIG) sanity check for MicroBlaze-V
 *
 * Hardware (design_1):
 *   axi_gpio_0     @ 0x40000000, 1 channel, 3 bits -> LED[2:0]
 *   mig_7series_0  @ 0x80000000, 2 GiB DDR3
 *   LMB BRAM       @ 0x00000000, 16 KiB  <- this program runs from here
 *
 * The program runs entirely from local BRAM (see lscript.ld), so it keeps
 * running (and keeps reporting on the LEDs) even if the DDR is broken.
 * No UART is needed.
 *
 * ---------------------------------------------------------------------------
 * What the LEDs mean
 * ---------------------------------------------------------------------------
 *  1. Lamp test (power-up):  LED0 -> LED1 -> LED2 one at a time, then all on.
 *     If one never lights, check that LED's pin/polarity.
 *
 *  2. DDR test running: LEDs show the test number in binary, lit steady.
 *        001 = test 1  data bus    (walking 1s on every DQ line)
 *        010 = test 2  address bus (power-of-two address lines)
 *        011 = test 3  memory fill (DDR_FILL_BYTES, address pattern + inverse)
 *     Each test normally takes well under a second or two.
 *     If the LEDs STAY FROZEN on a pattern, the CPU hung on a DDR access.
 *     Usually that means the MIG never finished calibration (check the clock,
 *     reset polarity and pinout), because the AXI port stalls until it has.
 *
 *  3a. PASS: a "running light" sweeps forever 0-1-2-1-0-...
 *
 *  3b. FAIL: all LEDs flash together N times, pause, then repeat.
 *      N = the number of the test that failed (1..3).
 * ---------------------------------------------------------------------------
 */

#include "xparameters.h"
#include "xil_types.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xgpio.h"
#include "sleep.h"

/* ------------------------------- settings -------------------------------- */

#define LED_GPIO_BASE    XPAR_AXI_GPIO_0_BASEADDR   /* the LED GPIO, by instance name */
#define LED_CHANNEL      1
#define LED_COUNT        3
#define LED_MASK         ((1u << LED_COUNT) - 1u)
#define LED_ACTIVE_LOW   0      /* set to 1 if a 0 turns your LEDs on */

#define DDR_BASE         XPAR_MIG_0_BASEADDRESS                  /* 0x80000000 */
#define DDR_SIZE         (XPAR_MIG_0_HIGHADDRESS - XPAR_MIG_0_BASEADDRESS + 1u)
/*
 * Build with -DSIM_BUILD for RTL simulation (see build_sim_elf.sh):
 * every "millisecond" becomes 1 microsecond and test 3 uses 4 KiB, so the
 * whole sequence fits in a few hundred microseconds of simulated time.
 */
#ifdef SIM_BUILD
#define DDR_FILL_BYTES   (4u * 1024u)
#define WAIT_MS(ms)      usleep(ms)            /* 1000x faster */
#else
#define DDR_FILL_BYTES   (16u * 1024u * 1024u)   /* region for test 3 */
#define WAIT_MS(ms)      usleep((ms) * 1000u)
#endif

#define CHASE_STEP_MS    150    /* speed of the "pass" running light  */
#define FAIL_FLASH_MS    200    /* speed of the "fail" flash code      */
#define FAIL_PAUSE_MS    1500   /* pause between fail-code repeats     */

/* ------------------------------------------------------------------------- */

static XGpio Gpio;

static void leds(u32 pattern)
{
#if LED_ACTIVE_LOW
    pattern = ~pattern;
#endif
    XGpio_DiscreteWrite(&Gpio, LED_CHANNEL, pattern & LED_MASK);
}

/*
 * The MicroBlaze-V data cache (write-back) covers the whole DDR range.
 * Without flush/invalidate the test would only check the cache, not the DDR.
 * So every write is pushed out to DDR and every read is fetched from DDR.
 */
static void ddr_wr32(UINTPTR a, u32 v)
{
    Xil_Out32(a, v);
    Xil_DCacheFlushRange(a, 4);
}

static u32 ddr_rd32(UINTPTR a)
{
    Xil_DCacheInvalidateRange(a, 4);
    return Xil_In32(a);
}

/* Test 1: walking 1s over a 64-byte block, so the bit hits every DQ line
 * in every beat of a DDR3 burst (bus is 64 data bits wide). */
static int test_data_bus(void)
{
    const UINTPTR base = DDR_BASE;
    const u32 words = 64 / 4;

    for (u32 bit = 0; bit < 32; bit++) {
        for (u32 inv = 0; inv < 2; inv++) {
            u32 pat = 1u << bit;
            if (inv)
                pat = ~pat;              /* walking 0 */
            for (u32 w = 0; w < words; w++)
                Xil_Out32(base + 4 * w, (w & 1) ? ~pat : pat);
            Xil_DCacheFlushRange(base, 64);
            Xil_DCacheInvalidateRange(base, 64);
            for (u32 w = 0; w < words; w++)
                if (Xil_In32(base + 4 * w) != ((w & 1) ? ~pat : pat))
                    return -1;
        }
    }
    return 0;
}

/* Test 2: address lines. Each power-of-two offset gets its own value, then
 * we check that writing one address doesn't alias onto another. */
static int test_address_bus(void)
{
    const u32 pat  = 0xAAAAAAAAu;
    const u32 anti = 0x55555555u;
    UINTPTR off, test;

    for (off = 4; off < DDR_SIZE; off <<= 1)
        ddr_wr32(DDR_BASE + off, pat);
    ddr_wr32(DDR_BASE, anti);

    /* stuck-high address bits */
    for (off = 4; off < DDR_SIZE; off <<= 1)
        if (ddr_rd32(DDR_BASE + off) != pat)
            return -1;

    ddr_wr32(DDR_BASE, pat);

    /* stuck-low / shorted address bits */
    for (test = 4; test < DDR_SIZE; test <<= 1) {
        ddr_wr32(DDR_BASE + test, anti);
        if (ddr_rd32(DDR_BASE) != pat)
            return -1;
        for (off = 4; off < DDR_SIZE; off <<= 1)
            if (off != test && ddr_rd32(DDR_BASE + off) != pat)
                return -1;
        ddr_wr32(DDR_BASE + test, pat);
    }
    return 0;
}

/* Test 3: fill a block with an address-derived pattern, read it back from
 * DDR, then repeat with the inverse so every bit is checked as 0 and 1. */
static int test_fill(void)
{
    const UINTPTR base = DDR_BASE;
    const u32 n = DDR_FILL_BYTES / 4;

    for (u32 pass = 0; pass < 2; pass++) {
        u32 x = pass ? 0xFFFFFFFFu : 0;

        for (u32 i = 0; i < n; i++)
            Xil_Out32(base + 4 * i, (base + 4 * i) ^ x);
        Xil_DCacheFlushRange(base, DDR_FILL_BYTES);
        Xil_DCacheInvalidateRange(base, DDR_FILL_BYTES);

        for (u32 i = 0; i < n; i++)
            if (Xil_In32(base + 4 * i) != ((base + 4 * i) ^ x))
                return -1;
    }
    return 0;
}

static void lamp_test(void)
{
    for (u32 i = 0; i < LED_COUNT; i++) {
        leds(1u << i);
        WAIT_MS(300);
    }
    leds(LED_MASK);
    WAIT_MS(500);
    leds(0);
    WAIT_MS(300);
}

static void fail_forever(u32 test_no)
{
    for (;;) {
        for (u32 i = 0; i < test_no; i++) {
            leds(LED_MASK);
            WAIT_MS(FAIL_FLASH_MS);
            leds(0);
            WAIT_MS(FAIL_FLASH_MS);
        }
        WAIT_MS(FAIL_PAUSE_MS);
    }
}

static void chase_forever(void)
{
    int pos = 0, dir = 1;

    for (;;) {
        leds(1u << pos);
        WAIT_MS(CHASE_STEP_MS);
        if (pos + dir < 0 || pos + dir >= LED_COUNT)
            dir = -dir;
        pos += dir;
    }
}

int main(void)
{
    static int (*const tests[])(void) = {
        test_data_bus,
        test_address_bus,
        test_fill,
    };

    XGpio_Initialize(&Gpio, LED_GPIO_BASE);
    XGpio_SetDataDirection(&Gpio, LED_CHANNEL, 0);   /* all outputs */

    lamp_test();

    for (u32 t = 0; t < sizeof(tests) / sizeof(tests[0]); t++) {
        leds(t + 1);                 /* show which test is running */
        if (tests[t]() != 0)
            fail_forever(t + 1);
    }

    chase_forever();
    return 0;
}
