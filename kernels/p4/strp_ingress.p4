/*
 * strp_ingress.p4
 * Sovereign Tensor Routing Protocol (STRP) — Phase IV data plane.
 * Target: v1model (BMv2 / Tofino with model adapter)
 *
 * Bypasses AMD Ryzen 7700X CPU entirely: strips Ethernet/IP headers and
 * routes fused-chunk tensor payloads (Q, K, V) directly via DMA into
 * the silicon SRAM queues or RTX 3080 VRAM, governed by the Ortho AI
 * Gateway control plane.
 *
 * Chunk Protocol Layout:
 *   Session ID   (32-bit): execution context
 *   Chunk Offset (16-bit): position within num_tokens sequence
 *   Tensor Type  (8-bit):  0x01=Q  0x02=K  0x03=V  0x04=State H
 *   Head Index   (16-bit): routes to specific systolic array grid
 */

#include <core.p4>
#include <v1model.p4>

/* --- Headers --- */
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header strp_tensor_chunk_t {
    bit<32> session_id;
    bit<16> sequence_num;
    bit<16> chunk_offset;   // block_S = 64
    bit<16> head_index;     // bhg or bh index
    bit<8>  tensor_type;    // Q / K / V
    bit<8>  is_varlen;
}

struct metadata_t {
    bit<32> target_queue_address;
}

struct headers {
    ethernet_t          ethernet;
    strp_tensor_chunk_t strp;
}

/* --- Parser --- */
parser MyParser(packet_in              packet,
                out headers            hdr,
                inout metadata_t       meta,
                inout standard_metadata_t standard_metadata) {
    state start           { transition parse_ethernet; }
    state parse_ethernet  {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x88B5: parse_strp;   // custom EtherType for Tensor Protocol
            default: accept;
        }
    }
    state parse_strp {
        packet.extract(hdr.strp);
        transition accept;
    }
}

/* --- Ingress (Ortho AI Gateway) --- */
control MyIngress(inout headers            hdr,
                  inout metadata_t         meta,
                  inout standard_metadata_t standard_metadata) {

    table direct_memory_route {
        key = {
            hdr.strp.session_id  : exact;
            hdr.strp.tensor_type : exact;
            hdr.strp.head_index  : exact;
        }
        actions = { set_dma_queue; drop; }
        size    = 1024;
    }

    action set_dma_queue(bit<9> egress_port, bit<32> memory_offset) {
        // offset = base + (chunk_offset * 64 * 128 * sizeof(bfloat16)) = base + chunk*16384
        meta.target_queue_address =
            memory_offset + ((bit<32>)hdr.strp.chunk_offset * 16384);
        standard_metadata.egress_spec = egress_port;
    }

    apply {
        if (hdr.strp.isValid()) {
            direct_memory_route.apply();
        }
    }
}

/* --- Deparser --- */
control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.strp);
        // Tensor payload follows directly into PCIe/SRAM bridge
    }
}
