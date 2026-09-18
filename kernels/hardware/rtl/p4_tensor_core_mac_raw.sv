// p4_tensor_core_mac_raw.sv
//
// Pipeline Stage 4 (P4): single node in the Tensor Core systolic array
// computing the incremental state update:  S += K^T * V'
//
// The inline AES obfuscation mask (0xA5A5A5A5) is a placeholder;
// replace with the AES-128 algebraic S-box block in production.

module p4_tensor_core_mac_raw (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] k_in,      // Decrypted K tensor operand (FP16)
    input  wire [15:0] v_in,      // Decrypted V tensor operand (FP16)
    input  wire [31:0] s_accum,   // Prior state fragment (FP32)
    input  wire        valid_in,  // Firmware barrier sync
    output reg  [31:0] s_out,     // Obfuscated state output
    output reg         valid_out
);
    wire [31:0] mult_result;
    wire [31:0] add_result;

    // IEEE-754 FP16 multiplier (gate-level abstraction)
    fp16_multiplier u_fpmac_mul (
        .a (k_in),
        .b (v_in),
        .p (mult_result)
    );

    // IEEE-754 FP32 adder
    fp32_adder u_fpmac_add (
        .a   (mult_result),
        .b   (s_accum),
        .sum (add_result)
    );

    // P4 pipeline register — applies raw obfuscation before SRAM write-back
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_out     <= 32'h0000_0000;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            s_out     <= add_result ^ 32'hA5A5_A5A5; // placeholder mask
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end
endmodule
