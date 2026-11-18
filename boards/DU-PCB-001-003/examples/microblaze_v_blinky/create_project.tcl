# create_project.tcl - recreate the MicroBlaze-V blinker project for the DU-PCB-001-003
# (board README section 4, "Example: MicroBlaze-V blinker"). Vivado 2026.1.
#
# Usage (from any directory):
#   vivado -mode batch -source create_project.tcl                         project only
#   vivado -mode batch -source create_project.tcl -tclargs -build          + bitstream and .xsa
#   vivado -mode batch -source create_project.tcl -tclargs -dir <path> [-build]
#   (or in the GUI Tcl console: set argv {-build}; source create_project.tcl)
#
# Default project location: ./blinky_project/blinky.xpr, relative to the current directory.
# With -build it also writes <dir>/design_1_wrapper.xsa (bitstream included) for Vitis.
#
# What it builds:
#   - board part johndoe:dupcb001003:part0:1.0, taken from this repo's board files (no install
#     needed);
#   - block design design_1 (design_1_bd.tcl): MicroBlaze-V at 100 MHz, 16 KB local BRAM,
#     MIG DDR3 channel 0 (2 GB at 0x8000_0000), axi_gpio_0 on the 3 LEDs, MDM;
#   - axi_gpio_keepalive on board interface fpga_keepalive. It holds pin AC24 high, without
#     which the card clears the FPGA (README section 3, "Keep-alive pin AC24"). Never write 0 to it;
#   - constraints/dupcb001003.xdc (UNUSEDPIN Pullup, CFGBVS/1.8 V, BPI flash settings), added
#     by reference.

set here  [file normalize [file dirname [info script]]]
set board_root [file normalize [file join $here .. ..]]   ;# folder that holds dupcb001003/1.0
set xdc   [file join $board_root constraints dupcb001003.xdc]

set proj_dir [file normalize blinky_project]
set build 0
for {set i 0} {$i < [llength $argv]} {incr i} {
  switch -- [lindex $argv $i] {
    -dir   { incr i; set proj_dir [file normalize [lindex $argv $i]] }
    -build { set build 1 }
    default { error "unknown argument [lindex $argv $i] (use -dir <path> and/or -build)" }
  }
}

# ---- project with the repo's board files ----------------------------------------------
set_param board.repoPaths [concat [list $board_root] [get_param board.repoPaths]]
create_project blinky $proj_dir -part xc7k480tiffg1156-2L -force
set bp [lindex [get_board_parts -quiet johndoe:dupcb001003:part0:*] end]
if {$bp eq ""} { error "board part johndoe:dupcb001003 not found under $board_root" }
set_property board_part $bp [current_project]
set_property target_language Verilog [current_project]

# ---- block design ----------------------------------------------------------------------
source [file join $here design_1_bd.tcl]
cr_bd_design_1 ""
open_bd_design [get_files design_1.bd]

# keep-alive: 1-bit axi_gpio with default output 1 on AC24 (board interface fpga_keepalive)
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_keepalive
apply_bd_automation -rule xilinx.com:bd_rule:board -config {Board_Interface "fpga_keepalive"} \
    [get_bd_intf_pins axi_gpio_keepalive/GPIO]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {/clk_wiz_0/clk_out1 (100 MHz)} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/microblaze_riscv_0 (Periph)} Slave {/axi_gpio_keepalive/S_AXI} \
    ddr_seg {Auto} intc_ip {/axi_smc} master_apm {0}} \
    [get_bd_intf_pins axi_gpio_keepalive/S_AXI]
set seg [get_bd_addr_segs -of [get_bd_addr_spaces microblaze_riscv_0/Data] -filter {NAME =~ *axi_gpio_keepalive*}]
set_property offset 0x40010000 $seg
set_property range 64K $seg
foreach p {C_GPIO_WIDTH C_ALL_OUTPUTS C_DOUT_DEFAULT GPIO_BOARD_INTERFACE} {
  puts "KEEPALIVE $p = [get_property CONFIG.$p [get_bd_cells axi_gpio_keepalive]]"
}
validate_bd_design
save_bd_design

set wrapper [make_wrapper -files [get_files design_1.bd] -top]
add_files -norecurse $wrapper
set_property top design_1_wrapper [current_fileset]

# ---- constraints (by reference, so fixes in the repo apply) -----------------------------
add_files -fileset constrs_1 -norecurse $xdc
update_compile_order -fileset sources_1

puts "PROJECT_CREATED [get_property DIRECTORY [current_project]]/blinky.xpr"

# ---- optional: bitstream + hardware export ------------------------------------------------
if {$build} {
  launch_runs impl_1 -to_step write_bitstream -jobs 8
  wait_on_run impl_1
  if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "implementation failed" }
  open_run impl_1
  set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
  puts "TIMING_WNS $wns ns"
  set xsa [file join $proj_dir design_1_wrapper.xsa]
  write_hw_platform -fixed -include_bit -force -file $xsa
  puts "XSA_WRITTEN $xsa"
}
