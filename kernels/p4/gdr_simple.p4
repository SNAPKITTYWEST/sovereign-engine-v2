/*
 * gdr_simple.p4
 * Minimal V1Switch GDR pipeline — register-based fused recurrent state update.
 * Target: v1model (BMv2)
 *
 * State update: S_t = g * S_{t-1} + K^T @ V'
 * Approximated as: current_state += (k_vector XOR v_vector)
 * (full FP32 MAC requires an extern or P4_16 fixed-point extension)
 */

#include <core.p4>
#include <v1model.p4>

header gdr_t {
    bit<16>  chunk_id;
    bit<32>  gamma;
    bit<32>  beta;
    bit<128> q_vector;
    bit<128> k_vector;
    bit<128> v_vector;
}

struct metadata { bit<32> scaled_g; }

struct headers   { gdr_t gdr; }

parser MyParser(packet_in              packet,
                out headers            hdr,
                inout metadata         meta,
                inout standard_metadata_t std_meta) {
    state start {
        packet.extract(hdr.gdr);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) { apply {} }
control MyComputeChecksum(inout headers hdr, inout metadata meta) { apply {} }

control MyIngress(inout headers            hdr,
                  inout metadata           meta,
                  inout standard_metadata_t std_meta) {

    register<bit<128>>(65536) h_state_register;
    bit<128> current_state;

    apply {
        h_state_register.read(current_state, (bit<32>)hdr.gdr.chunk_id);
        current_state = current_state + (hdr.gdr.k_vector ^ hdr.gdr.v_vector);
        h_state_register.write((bit<32>)hdr.gdr.chunk_id, current_state);
    }
}

control MyEgress(inout headers hdr, inout metadata meta,
                 inout standard_metadata_t std_meta) { apply {} }

control MyDeparser(packet_out packet, in headers hdr) {
    apply { packet.emit(hdr.gdr); }
}

V1Switch(
    MyParser(),
    MyVerifyChecksum(),
    MyIngress(),
    MyEgress(),
    MyComputeChecksum(),
    MyDeparser()
) main;
