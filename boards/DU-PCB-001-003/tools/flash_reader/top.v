// Flash reader for the DU-PCB-001-003: JTAG-to-AXI -> axi_emc -> BPI flash (read only use).
module top (
  input  wire        clk50, resetn,
  output wire [25:1] flash_a,
  inout  wire [15:0] flash_dq,
  output wire        flash_adv_n, flash_ce_n, flash_oe_n, flash_we_n,
  output wire        fpga_keepalive        // AC24: must stay high on this card
);
  assign fpga_keepalive = 1'b1;
  wire [31:0] a;
  fr_wrapper u (
    .clk50(clk50), .resetn(resetn),
    .EMC_INTF_0_addr(a), .EMC_INTF_0_dq_io(flash_dq),
    .EMC_INTF_0_adv_ldn(flash_adv_n), .EMC_INTF_0_ce_n(flash_ce_n),
    .EMC_INTF_0_oen(flash_oe_n), .EMC_INTF_0_wen(flash_we_n),
    .EMC_INTF_0_wait(1'b0),
    .EMC_INTF_0_ben(), .EMC_INTF_0_ce(), .EMC_INTF_0_clken(), .EMC_INTF_0_cre(),
    .EMC_INTF_0_lbon(), .EMC_INTF_0_qwen(), .EMC_INTF_0_rnw(), .EMC_INTF_0_rpn()
  );
  assign flash_a = a[25:1];
endmodule
