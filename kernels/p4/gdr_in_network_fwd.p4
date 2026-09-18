/*
 * gdr_in_network_fwd.p4
 * Target: Tofino Native Architecture (TNA) / Sovereign Bare-Metal Fabric
 *
 * Transforms a network switch into a distributed systolic array.
 * Packets carry Q, K, V fragments as custom headers; stateful SRAM
 * registers maintain the recurrent hidden state:
 *   S_i = g * S_{i-1} + K^T V
 * across chunk boundaries — bypassing host PCIe entirely.
 */

#include <core.p4>
#include <tna.p4>

typedef bit<32>     scalar_t;
typedef bit<16>     token_idx_t;

header gdr_payload_t {
    token_idx_t chunk_id;
    token_idx_t seq_idx;
    scalar_t    k_val;
    scalar_t    v_val;
    scalar_t    g_val;
}

struct parsed_headers_t {
    ethernet_t     ethernet;
    ipv4_t         ipv4;
    gdr_payload_t  gdr;
}

parser SovereignParser(packet_in packet, out parsed_headers_t hdr) {
    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;
            default: accept;
        }
    }
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            0xFD: parse_gdr;   // Custom Protocol 253 for Sovereign GDR
            default: accept;
        }
    }
    state parse_gdr {
        packet.extract(hdr.gdr);
        transition accept;
    }
}

control GdrIngress(inout parsed_headers_t hdr,
                   inout ingress_intrinsic_metadata_t ig_md) {

    // Stateful SRAM: hidden state h (DV × DK dimensions)
    Register<scalar_t, token_idx_t> h_state_reg =
        Register<scalar_t, token_idx_t>(65536);

    // Atomic RMW: h = (h * g) + (k * v)
    RegisterAction<scalar_t, token_idx_t, scalar_t> update_h_state =
        RegisterAction<scalar_t, token_idx_t, scalar_t>(h_state_reg) {
        void apply(inout scalar_t h_val, out scalar_t result) {
            scalar_t k_v_prod = hdr.gdr.k_val * hdr.gdr.v_val;
            h_val  = (h_val * hdr.gdr.g_val) + k_v_prod;
            result = h_val;
        }
    };

    action process_gdr_chunk() {
        scalar_t updated_h;
        updated_h      = update_h_state.execute(hdr.gdr.seq_idx);
        hdr.gdr.v_val  = updated_h;
        ig_md.ucast_egress_port = 9;   // route to aggregator
    }

    table exact_match_gdr {
        key     = { hdr.ipv4.protocol : exact; }
        actions = { process_gdr_chunk; NoAction; }
        default_action = NoAction;
    }

    apply {
        if (hdr.gdr.isValid()) {
            exact_match_gdr.apply();
        }
    }
}
