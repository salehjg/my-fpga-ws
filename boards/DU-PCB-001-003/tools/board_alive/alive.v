// Board "is it alive" test: no MIG, no DDR, only the 3 LEDs are outputs.
//   LED0 blinks ~1 Hz from the FPGA's internal config clock (needs no board clock)
//   LED1 blinks ~1 Hz from the 50 MHz clock pin (AA28)
//   LED2 blinks ~1 Hz from the 200 MHz differential clock (AH27/AH28)
//   Holding the reset button (resetn low) turns all LEDs on.
module alive (
  input  wire       default_50mhz_clk0,
  input  wire       sys_diff_clock_clk_p,
  input  wire       sys_diff_clock_clk_n,
  input  wire       resetn,
  output wire [2:0] led
);
  wire cfgmclk;
  STARTUPE2 #(.PROG_USR("FALSE")) u_startup (
    .CFGCLK(), .CFGMCLK(cfgmclk), .EOS(), .PREQ(),
    .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b1), .PACK(1'b0),
    .USRCCLKO(1'b0), .USRCCLKTS(1'b1), .USRDONEO(1'b1), .USRDONETS(1'b1)
  );
  wire clk_int;  BUFG u_bg0 (.I(cfgmclk), .O(clk_int));
  wire clk50;    BUFG u_bg1 (.I(default_50mhz_clk0), .O(clk50));
  wire clk200_i, clk200;
  IBUFDS u_ibufds (.I(sys_diff_clock_clk_p), .IB(sys_diff_clock_clk_n), .O(clk200_i));
  BUFG u_bg2 (.I(clk200_i), .O(clk200));

  reg [25:0] c_int = 0;  always @(posedge clk_int) c_int <= c_int + 1'b1;  // ~65 MHz
  reg [25:0] c50   = 0;  always @(posedge clk50)   c50   <= c50   + 1'b1;  // 50 MHz
  reg [27:0] c200  = 0;  always @(posedge clk200)  c200  <= c200  + 1'b1;  // 200 MHz

  assign led = resetn ? {c200[27], c50[25], c_int[25]} : 3'b111;
endmodule
