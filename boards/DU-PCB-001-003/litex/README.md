# LiteX on the DU-PCB-001-003

## Using `setup.litex.du-pcb.py`

```
# 1. Set up (once). Needs python3, git, bash and Vivado.
python3 setup.litex.du-pcb.py --workdir ~/dupcb     # unpacks the project, installs LiteX
cd ~/dupcb

# 2. Build
scripts/build.sh --no-compile-gateware   # quick check, ~1 min
scripts/build.sh                         # full bitstream, ~50 min

# 3. Bring up the card (after every load or power cycle)
scripts/load.sh                          # load the bitstream over JTAG
scripts/pcie_rescan.sh                   # let Linux find the card again
scripts/ddr_init.sh                      # calibrate + test both DDR3 channels

# 4. Use it
scripts/status.sh                        # ident, measured clocks, LEDs
scripts/console.sh                       # BIOS console over PCIe (Ctrl-C quits)

# Changed a project file? Put it back into the script:
python3 setup.litex.du-pcb.py --pack
```

## What the script sets up

**LiteX** is a Python framework for building FPGA systems-on-chip. You describe the SoC in Python
(`boards/dupcb/target.py`). LiteX turns it into Verilog and constraints, and Vivado turns those into a
bitstream. The script pins everything to LiteX release 2026.08 and installs it in `deps/` and `.venv/`.

**CPU and BIOS.** A small VexRiscv RISC-V CPU runs at 125 MHz from on-chip memory. The card has no
UART pins, so the BIOS console runs over PCIe instead (`scripts/console.sh`). At boot the BIOS tries to
calibrate DDR channel 0 by itself and usually prints "Memtest KO". That's expected; the host does the
real calibration. The CPU isn't needed for accelerator work.

**PCIe.** Gen2 x8 (links at x4 in an x4 slot). BAR0 (128 KB) exposes every control register to the host,
and there's one DMA channel. A LitePCIe Linux driver is generated in `build/dupcb/driver/`. The host tools
reach the card through BAR0 directly, so no driver is needed for them.

**DDR3.** Two channels of 2 GB each, 64 bits wide, at DDR3-1000, each with its own LiteDRAM controller
and a built-in self-test (BIST).
- **CH0** is the CPU's main RAM. The CPU sees the first 1 GB at `0x4000_0000`.
- **CH1** is for your accelerator. Take a port with `self.sdram1.crossbar.get_port(clock_domain="accel")`
  in `target.py`.
- **Why the custom PHY:** these FPGA banks can't do DDR3 write leveling, so the project uses
  `wl7ddrphy.py`, a port of openTPU's PHY. `scripts/ddr_init.sh` finds the timing that works for every
  lane on each channel and then runs the self-test. It needs about 12 s and must run after every load.
  Measured on the card: 893 ps of write-timing margin on CH0 and 1429 ps on CH1, with error-free 1 GB
  self-tests at 7.2 GB/s.
- The ninth byte lane (the ECC chip) is not used.

**Clocks.**

| Source | Becomes | Used for |
|---|---|---|
| 200 MHz crystal #0 | `sys` 125 MHz and a 200 MHz IDELAY reference | CPU, buses, DDR controllers, PCIe registers |
| `sys` | one MMCM per DDR channel: CK at 500 MHz (phase moved by the host), DQ/DQS fixed | DDR3 pins |
| 200 MHz crystal #1 | `accel` 200 MHz (PLL) | your accelerator logic |
| 50 MHz crystal | `clk50` | free for your use |

`scripts/status.sh` measures `clk50` and `accel` on the card, so you can check every crystal.

**Board specifics.**
- **Keep-alive:** pin AC24 is driven high and all unused pins have pull-ups. Without this the board's
  watchdog clears the FPGA.
- **LEDs:** the three bracket LEDs run a chaser, which shows the design is alive.
- **Loading:** the bitstream goes in over JTAG and is lost at power-off. Writing it to flash isn't
  supported yet.
