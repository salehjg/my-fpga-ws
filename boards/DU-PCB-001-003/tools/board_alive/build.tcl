# Board sanity bitstream for the DU-PCB-001-003 (no MIG, no DDR, LEDs only).
# Run inside this folder:  vivado -mode batch -source build.tcl   ->  alive.bit
#   LED0 (red)    blinks ~1 Hz from the FPGA's internal configuration clock (needs no board clock)
#   LED1 (green)  blinks ~1 Hz from the 50 MHz clock (AA28)
#   LED2 (yellow) blinks ~1 Hz from the 200 MHz clock 1 (AH27/AH28)
#   Holding the user reset button (SW2, R28) lights all three.
# The master XDC keeps pin AC24 high; without it the card clears the FPGA (README section 3, "Keep-alive pin AC24").
read_verilog alive.v
read_xdc alive.xdc
read_xdc ../../constraints/dupcb001003.xdc
synth_design -top alive -part xc7k480tiffg1156-2L
opt_design; place_design; route_design
write_bitstream -force alive.bit
