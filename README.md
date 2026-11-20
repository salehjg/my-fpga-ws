# My FPGA Workspace

## Boards
### YPCB-00338-1P1 (Inspur) Kintex-7 480t
- [**Archive**](boards.archives/inspur-kintex7-480t/archive.zip)
- **FPGA:** Xilinx Kintex-7 `XC7K480T`
- **DDR:** Two groups, each group (72-bit ECC) with 9 chips in each (`MT41K256M8DA-125:K`)
- **OSC:** Two 200MHz differential active crystal oscillators.
- **Platform Flash:** 512Mb NOR - Micron `MT28GU512AAA1EGC-0SIT`

### DU-PCB-001-003 / SCH-001-003 (Celestica) Kintex-7 480t
- [**Docs**](boards/DU-PCB-001-003/README.md): hardware reference, board files, examples, flash backup
- **FPGA:** Xilinx Kintex-7 `XC7K480T-L2FFG1156I` (Vivado part `xc7k480tiffg1156-2L`)
- **DDR:** Two groups, each group (72-bit ECC) with 9 chips in each (SK hynix `H5TC2G83FFR-PBA` DDR3L), 4 GB usable
- **OSC:** Two 200MHz differential oscillators and one 50MHz single-ended oscillator.
- **Platform Flash:** 512Mb NOR - Micron `MT28GU512AAA1EGC-0SIT` (BPI x16)
- **Host:** PCIe Gen2 x8
- **Note:** FPGA pin `AC24` must stay high, or the card clears the FPGA ~250 ms after configuration.
- **Vivado:** corrected board files, master XDC and a MicroBlaze-V example with DDR check (Vivado/Vitis 2026.1).
- **LiteX:** [`litex/setup.litex.du-pcb.py`](boards/DU-PCB-001-003/litex/README.md) sets up a LiteX 2026.08 SoC with PCIe and both DDR3 channels.


## Programmers
### FTDI FT4232HL
- **Drivers:** `cd /workspace/01_software/xilinx/2026.1/Vivado/data/xicom/cable_drivers/lin64/install_script/install_drivers/ && sudo bash install_drivers`

