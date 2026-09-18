// pcie_doorbell_latch.v — PCIe Doorbell Latch
// Triggers on VALUE CHANGE of pcie_doorbell_in (not level).
// trigger_event pulses for 1 clock → drives Kalman Filter / QNN update.

module pcie_doorbell_latch (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] pcie_doorbell_in,  // From PCIe BAR
    input  wire        pcie_write_en,     // Write strobe from PCIe
    output reg  [31:0] pcie_latch_out,    // Status register
    output reg         trigger_event      // Pulse to Kalman Filter/QNN
);
    reg [31:0] prev_doorbell;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pcie_latch_out <= 32'h0;
            trigger_event  <= 1'b0;
            prev_doorbell  <= 32'h0;
        end else begin
            trigger_event <= 1'b0;  // default pulse low

            if (pcie_write_en) begin
                if (pcie_doorbell_in != prev_doorbell) begin
                    pcie_latch_out <= pcie_doorbell_in;
                    trigger_event  <= 1'b1;  // KICK!
                end
                prev_doorbell <= pcie_doorbell_in;
            end
        end
    end
endmodule
