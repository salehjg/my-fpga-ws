create_project -force frd ./frd -part xc7k480tiffg1156-2L
create_bd_design fr
create_bd_port -dir I -type clk -freq_hz 50000000 clk50
create_bd_port -dir I -type rst resetn
set_property CONFIG.POLARITY ACTIVE_LOW [get_bd_ports resetn]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset rst
create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi jtag
set_property -dict [list CONFIG.PROTOCOL {0} CONFIG.M_AXI_DATA_WIDTH {32}] [get_bd_cells jtag]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_emc emc
set_property -dict [list CONFIG.C_MAX_MEM_WIDTH {16} CONFIG.C_MEM0_TYPE {2} CONFIG.C_MEM0_WIDTH {16} \
  CONFIG.C_TAVDV_PS_MEM_0 {130000} CONFIG.C_TCEDV_PS_MEM_0 {130000} CONFIG.C_THZCE_PS_MEM_0 {20000} \
  CONFIG.C_THZOE_PS_MEM_0 {20000} CONFIG.C_TWPH_PS_MEM_0 {20000} CONFIG.C_TLZWE_PS_MEM_0 {20000} \
  CONFIG.C_TWC_PS_MEM_0 {40000} CONFIG.C_TWP_PS_MEM_0 {40000} CONFIG.C_WR_REC_TIME_MEM_0 {200000} \
  CONFIG.C_S_AXI_MEM_DATA_WIDTH {32}] [get_bd_cells emc]
connect_bd_net [get_bd_ports clk50] [get_bd_pins rst/slowest_sync_clk] [get_bd_pins jtag/aclk] [get_bd_pins emc/s_axi_aclk] [get_bd_pins emc/rdclk]
connect_bd_net [get_bd_ports resetn] [get_bd_pins rst/ext_reset_in]
connect_bd_net [get_bd_pins rst/peripheral_aresetn] [get_bd_pins jtag/aresetn] [get_bd_pins emc/s_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins jtag/M_AXI] [get_bd_intf_pins emc/S_AXI_MEM]
make_bd_intf_pins_external [get_bd_intf_pins emc/EMC_INTF]
assign_bd_address
set_property range 64M [get_bd_addr_segs -of [get_bd_addr_spaces jtag/Data]]
set_property offset 0x60000000 [get_bd_addr_segs -of [get_bd_addr_spaces jtag/Data]]
puts "ADDR [get_property OFFSET [get_bd_addr_segs -of [get_bd_addr_spaces jtag/Data]]] RANGE [get_property RANGE [get_bd_addr_segs -of [get_bd_addr_spaces jtag/Data]]]"
validate_bd_design
save_bd_design
add_files -norecurse [make_wrapper -files [get_files fr.bd] -top]
