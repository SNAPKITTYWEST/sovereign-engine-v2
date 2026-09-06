// gdr_dual_core_top.sv
//
// GDR Dual-Core Top — wires two gdr_core instances with a shared memory bus
// and a combinatorial hardware barrier (sync0 && sync1).
//
// Instantiates:
//   - gdr_tensor_core_gemm  (inline AES-128 algebraic S-box for state decryption)
//   - gdr_core              (PC + accumulator with 1024-cycle sync signal)

// ── GDR Tensor Core GEMM (inline S-Box decrypt + 16x8x16 MAC array) ──────────
module gdr_tensor_core_gemm #(
    parameter DATA_WIDTH = 32,
    parameter CHUNK_SIZE = 64
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [DATA_WIDTH-1:0] q_in,
    input  wire [DATA_WIDTH-1:0] k_in,
    input  wire [DATA_WIDTH-1:0] state_enc_in,
    output wire [DATA_WIDTH-1:0] o_out
);
    wire [DATA_WIDTH-1:0] state_dec;
    wire [DATA_WIDTH-1:0] mac_result;

    // Inline algebraic S-Box decryption of the state vector
    aes_sbox_algebraic_decrypt u_dec (
        .clk          (clk),
        .cipher_state (state_enc_in),
        .plain_state  (state_dec)
    );

    genvar i;
    generate
        for (i = 0; i < CHUNK_SIZE; i++) begin : gen_mac_array
            mul_add_tree inst_mac (
                .a   (q_in),
                .b   (k_in),
                .c   (state_dec),
                .out (mac_result)
            );
        end
    endgenerate

    assign o_out = mac_result;
endmodule

// ── gdr_core ─────────────────────────────────────────────────────────────────
module gdr_core (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         start,
    input  logic [127:0] dataIn,
    output logic [127:0] dataOut,
    output logic         sync
);
    logic [9:0]   pc;
    logic [127:0] acc;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc  <= 10'b0;
            acc <= 128'b0;
        end else if (start) begin
            pc  <= pc + 1'b1;
            acc <= acc + dataIn;
        end
    end

    assign sync    = (pc == 10'd1024);
    assign dataOut = acc;
endmodule

// ── Top-level ────────────────────────────────────────────────────────────────
module gdr_dual_core_top (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         global_start,
    input  logic [127:0] mem_bus,
    output logic [255:0] result_bus
);
    logic         sync0, sync1;
    logic [127:0] out0,  out1;
    logic         barrier;

    gdr_core core0 (
        .clk    (clk),
        .rst_n  (rst_n),
        .start  (global_start),
        .dataIn (mem_bus),
        .dataOut(out0),
        .sync   (sync0)
    );

    gdr_core core1 (
        .clk    (clk),
        .rst_n  (rst_n),
        .start  (global_start),
        .dataIn (mem_bus),
        .dataOut(out1),
        .sync   (sync1)
    );

    assign barrier    = sync0 && sync1;
    assign result_bus = {out0, out1};
endmodule
