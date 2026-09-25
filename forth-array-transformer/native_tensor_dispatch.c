/* ============================================================
   NATIVE TCP TENSOR DISPATCH + SWITCHBOARD + DECODER
   NO RUST NO PYTHON NO PYTORCH
   ============================================================ */

#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <errno.h>

#define TENSOR_BLOCK_ELEMS 16
#define MAX_DEPTH 8
#define REG_FILE_SIZE 1024
#define TCP_PORT 9743
#define MAGIC_TENSOR 0x54454E53u /* TENS */
#define MAGIC_RESULT 0x52534C54u /* RSLT */
#define OP_MATMUL 0x01
#define OP_DOT    0x01
#define OP_FMA    0x02
#define OP_REDUCE 0x03
#define OP_TRANSPOSE 0x04
#define OP_LOAD   0x05
#define OP_STORE  0x06
#define OP_BROADCAST 0x07
#define OP_MASK   0x08
#define OP_ATTN   0x00
#define OP_DECODE 0x09
#define OP_VERIFY 0x0A
#define DTYPE_F16  0
#define DTYPE_F32  1
#define DTYPE_I32  2
#define DTYPE_BF16 3
#define LAYOUT_ROW 0
#define LAYOUT_COL 1
#define LAYOUT_BLOCKED 2
#define ROUTE_ATTENTION  0
#define ROUTE_MATRIX     1
#define ROUTE_SIMD       2
#define ROUTE_REDUCE     3
#define ROUTE_GRAPH      4
#define ROUTE_DECODE     5
#define ROUTE_VERIFY     6
#define ROUTE_LOADSTORE  7

typedef struct {
    uint32_t base_address;
    uint8_t  rank;
    uint8_t  dtype;
    uint8_t  layout;
    uint8_t  elem_size;
    uint32_t dim[4];
    uint32_t stride[4];
    uint32_t acc_reg;
    uint32_t weight_reg;
    uint32_t act_reg;
    uint32_t result_reg;
    uint8_t  op;
    uint8_t  depth;
    uint8_t  pad[2];
    float    data[TENSOR_BLOCK_ELEMS];
} TensorBlock;

typedef struct {
    uint32_t    magic;
    uint32_t    seq;
    uint32_t    payload_len;
    uint8_t     op;
    uint8_t     depth;
    uint8_t     dtype;
    uint8_t     flags;
    TensorBlock act;
    TensorBlock weight;
} TensorPacket;

typedef struct {
    uint32_t    magic;
    uint32_t    seq;
    uint32_t    payload_len;
    uint8_t     status;
    uint8_t     depth;
    uint8_t     pad[2];
    TensorBlock result;
} ResultPacket;

static uint32_t reg_file[REG_FILE_SIZE];
static uint32_t global_seq = 1;

/* ── register file ──────────────────────────────────────── */
static inline void reg_write(uint32_t idx, uint32_t val) {
    if (idx < REG_FILE_SIZE) reg_file[idx] = val;
}
static inline uint32_t reg_read(uint32_t idx) {
    if (idx < REG_FILE_SIZE) return reg_file[idx];
    return 0;
}
static inline void reg_clear(void) {
    memset(reg_file, 0, sizeof(reg_file));
}

/* ── bit cast helpers ───────────────────────────────────── */
static inline uint32_t f32_to_bits(float f) {
    uint32_t u; memcpy(&u, &f, 4); return u;
}
static inline float bits_to_f32(uint32_t u) {
    float f; memcpy(&f, &u, 4); return f;
}

/* ── FMA on 16-wide tensor block ────────────────────────── */
static void tensor_fma_block(const TensorBlock *act,
                              const TensorBlock *wgt,
                              TensorBlock       *out) {
    unsigned i;
    *out = *act;
    out->op    = OP_FMA;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++)
        out->data[i] = out->data[i] + act->data[i] * wgt->data[i];
}

static void tensor_dot_block(const TensorBlock *act,
                              const TensorBlock *wgt,
                              TensorBlock       *out) {
    tensor_fma_block(act, wgt, out);
}

static void tensor_reduce_block(const TensorBlock *src, TensorBlock *out) {
    unsigned i;
    float sum = 0.0f;
    *out       = *src;
    out->rank  = 1;
    out->dim[0] = 1;
    out->op    = OP_REDUCE;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) sum += src->data[i];
    out->data[0] = sum;
    for (i = 1; i < TENSOR_BLOCK_ELEMS; i++) out->data[i] = 0.0f;
}

static void tensor_broadcast_block(const TensorBlock *src, TensorBlock *out) {
    unsigned i;
    *out      = *src;
    out->op   = OP_BROADCAST;
    for (i = 1; i < TENSOR_BLOCK_ELEMS; i++) out->data[i] = src->data[0];
}

static void tensor_mask_block(const TensorBlock *src,
                               const TensorBlock *mask,
                               TensorBlock       *out) {
    unsigned i;
    *out    = *src;
    out->op = OP_MASK;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++)
        if (mask->data[i] == 0.0f) out->data[i] = 0.0f;
}

static void tensor_transpose_2x2(const TensorBlock *src, TensorBlock *out) {
    unsigned i;
    *out      = *src;
    out->op   = OP_TRANSPOSE;
    out->data[0] = src->data[0];
    out->data[1] = src->data[2];
    out->data[2] = src->data[1];
    out->data[3] = src->data[3];
    for (i = 4; i < TENSOR_BLOCK_ELEMS; i++) out->data[i] = src->data[i];
}

/* ── switchboard route ──────────────────────────────────── */
static uint8_t switchboard_route(uint8_t op) {
    switch (op) {
    case OP_ATTN:      return ROUTE_ATTENTION;
    case OP_MATMUL:    return ROUTE_MATRIX;
    case OP_FMA:       return ROUTE_SIMD;
    case OP_REDUCE:    return ROUTE_REDUCE;
    case OP_TRANSPOSE: return ROUTE_GRAPH;
    case OP_LOAD:
    case OP_STORE:     return ROUTE_LOADSTORE;
    case OP_DECODE:    return ROUTE_DECODE;
    case OP_VERIFY:    return ROUTE_VERIFY;
    default:           return ROUTE_SIMD;
    }
}

/* ── engine dispatch ────────────────────────────────────── */
static void engine_attention(const TensorBlock *act,
                              const TensorBlock *wgt,
                              TensorBlock       *out) {
    TensorBlock tmp;
    memset(&tmp, 0, sizeof(tmp));
    tensor_fma_block(act, wgt, &tmp);
    tensor_reduce_block(&tmp, out);
    out->op = OP_ATTN;
}

static void engine_matrix(const TensorBlock *act,
                           const TensorBlock *wgt,
                           TensorBlock       *out) {
    tensor_fma_block(act, wgt, out);
    out->op = OP_MATMUL;
}

static void engine_simd(const TensorBlock *act,
                         const TensorBlock *wgt,
                         TensorBlock       *out) {
    tensor_fma_block(act, wgt, out);
}

static void engine_reduce(const TensorBlock *act,
                           const TensorBlock *wgt,
                           TensorBlock       *out) {
    (void)wgt;
    tensor_reduce_block(act, out);
}

static void engine_graph(const TensorBlock *act,
                          const TensorBlock *wgt,
                          TensorBlock       *out) {
    (void)wgt;
    tensor_transpose_2x2(act, out);
}

static void engine_decode(const TensorBlock *act,
                           const TensorBlock *wgt,
                           TensorBlock       *out) {
    (void)wgt;
    *out     = *act;
    out->op  = OP_DECODE;
}

static void engine_verify(const TensorBlock *act,
                           const TensorBlock *wgt,
                           TensorBlock       *out) {
    unsigned i;
    int ok = 1;
    (void)wgt;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) {
        if (act->data[i] != act->data[i]) { ok = 0; break; } /* NaN */
    }
    *out         = *act;
    out->op      = OP_VERIFY;
    out->data[0] = ok ? 1.0f : 0.0f;
}

static void engine_loadstore(const TensorBlock *act,
                              const TensorBlock *wgt,
                              TensorBlock       *out) {
    (void)wgt;
    *out = *act;
}

static void dispatch_engine(uint8_t           route,
                             const TensorBlock *act,
                             const TensorBlock *wgt,
                             TensorBlock       *out) {
    switch (route) {
    case ROUTE_ATTENTION:  engine_attention(act, wgt, out);  break;
    case ROUTE_MATRIX:     engine_matrix(act, wgt, out);     break;
    case ROUTE_SIMD:       engine_simd(act, wgt, out);       break;
    case ROUTE_REDUCE:     engine_reduce(act, wgt, out);     break;
    case ROUTE_GRAPH:      engine_graph(act, wgt, out);      break;
    case ROUTE_DECODE:     engine_decode(act, wgt, out);     break;
    case ROUTE_VERIFY:     engine_verify(act, wgt, out);     break;
    case ROUTE_LOADSTORE:  engine_loadstore(act, wgt, out);  break;
    default:               engine_simd(act, wgt, out);       break;
    }
}

/* ── depth machine ──────────────────────────────────────── */
static void depth_machine(TensorBlock *act,
                           TensorBlock *wgt,
                           TensorBlock *out) {
    uint8_t d;
    TensorBlock cur_act = *act;
    TensorBlock cur_wgt = *wgt;
    TensorBlock cur_out;

    for (d = 0; d < MAX_DEPTH; d++) {
        cur_act.depth = d;
        cur_wgt.depth = d;
        uint8_t route = switchboard_route(cur_act.op);
        memset(&cur_out, 0, sizeof(cur_out));
        dispatch_engine(route, &cur_act, &cur_wgt, &cur_out);
        cur_act = cur_out;
        if (cur_out.op == OP_VERIFY && cur_out.data[0] == 0.0f)
            break;
    }
    *out = cur_act;
}

/* ── TCP framing ────────────────────────────────────────── */
static int tcp_send_all(int fd, const void *buf, size_t len) {
    const uint8_t *p = (const uint8_t *)buf;
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = send(fd, p + sent, len - sent, 0);
        if (n <= 0) return -1;
        sent += (size_t)n;
    }
    return 0;
}

static int tcp_recv_all(int fd, void *buf, size_t len) {
    uint8_t *p = (uint8_t *)buf;
    size_t got = 0;
    while (got < len) {
        ssize_t n = recv(fd, p + got, len - got, 0);
        if (n <= 0) return -1;
        got += (size_t)n;
    }
    return 0;
}

/* ── client: dispatch over TCP ──────────────────────────── */
int dispatch_tensor_multiply_tcp(
    const char  *host,
    uint16_t     port,
    const TensorBlock *activations,
    const TensorBlock *weights,
    TensorBlock       *output)
{
    int fd;
    struct sockaddr_in addr;
    TensorPacket req;
    ResultPacket resp;

    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(port);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) { close(fd); return -2; }
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) { close(fd); return -3; }

    memset(&req, 0, sizeof(req));
    req.magic       = MAGIC_TENSOR;
    req.seq         = global_seq++;
    req.payload_len = sizeof(TensorBlock) * 2;
    req.op          = OP_FMA;
    req.dtype       = activations->dtype;
    req.act         = *activations;
    req.weight      = *weights;

    if (tcp_send_all(fd, &req, sizeof(req)) < 0) { close(fd); return -4; }
    if (tcp_recv_all(fd, &resp, sizeof(resp)) < 0) { close(fd); return -5; }
    if (resp.magic != MAGIC_RESULT) { close(fd); return -6; }

    *output = resp.result;
    close(fd);
    return 0;
}

/* ── server: accept and execute ─────────────────────────── */
static void handle_client(int cfd) {
    TensorPacket req;
    ResultPacket resp;
    TensorBlock  out;

    if (tcp_recv_all(cfd, &req, sizeof(req)) < 0) { close(cfd); return; }
    if (req.magic != MAGIC_TENSOR)                 { close(cfd); return; }

    memset(&out, 0, sizeof(out));
    depth_machine(&req.act, &req.weight, &out);

    memset(&resp, 0, sizeof(resp));
    resp.magic       = MAGIC_RESULT;
    resp.seq         = req.seq;
    resp.payload_len = sizeof(TensorBlock);
    resp.status      = 0;
    resp.depth       = out.depth;
    resp.result      = out;

    tcp_send_all(cfd, &resp, sizeof(resp));
    close(cfd);
}

int tensor_tcp_server(uint16_t port) {
    int sfd, cfd;
    struct sockaddr_in addr;
    int opt = 1;

    sfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sfd < 0) return -1;
    setsockopt(sfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(port);

    if (bind(sfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) { close(sfd); return -2; }
    if (listen(sfd, 64) < 0)                                   { close(sfd); return -3; }

    for (;;) {
        cfd = accept(sfd, NULL, NULL);
        if (cfd < 0) continue;
        handle_client(cfd);
    }
    return 0;
}

/* ── canonicalizer / encoder / decoder / verifier ──────── */
typedef struct {
    uint32_t node_id;
    uint8_t  node_type;
    uint8_t  depth;
    uint16_t in_degree;
    uint16_t out_degree;
    float    features[8];
    uint32_t structural_hash;
} NativeNode;

typedef struct {
    uint32_t src;
    uint32_t dst;
    uint8_t  edge_type;
    uint8_t  pad[3];
    float    meta[4];
} NativeEdge;

typedef struct {
    NativeNode nodes[64];
    NativeEdge edges[128];
    uint32_t   n_nodes;
    uint32_t   n_edges;
    uint32_t   structural_hash;
    uint8_t    topo[64];
    uint8_t    depth_map[64];
} CanonicalGraph;

static uint32_t simple_hash(const void *p, size_t n) {
    const uint8_t *b = (const uint8_t *)p;
    uint32_t h = 2166136261u;
    size_t i;
    for (i = 0; i < n; i++) { h ^= b[i]; h *= 16777619u; }
    return h;
}

static void canonicalize(CanonicalGraph *g) {
    uint32_t i;
    for (i = 0; i < g->n_nodes; i++) {
        g->depth_map[i] = g->nodes[i].depth;
        g->topo[i]      = (uint8_t)i;
    }
    g->structural_hash  = simple_hash(g->nodes, g->n_nodes * sizeof(NativeNode));
    g->structural_hash ^= simple_hash(g->edges, g->n_edges * sizeof(NativeEdge));
}

static void encode_graph(const CanonicalGraph *g, TensorBlock *out) {
    unsigned i;
    memset(out, 0, sizeof(*out));
    out->rank   = 2;
    out->dtype  = DTYPE_F32;
    out->layout = LAYOUT_ROW;
    out->elem_size = 4;
    out->dim[0] = g->n_nodes;
    out->dim[1] = 8;
    out->op     = OP_LOAD;
    for (i = 0; i < TENSOR_BLOCK_ELEMS && i < g->n_nodes; i++)
        out->data[i] = g->nodes[i].features[0];
}

static void decode_graph(const TensorBlock *in, CanonicalGraph *g) {
    unsigned i;
    memset(g, 0, sizeof(*g));
    g->n_nodes = in->dim[0] ? in->dim[0] : 1;
    for (i = 0; i < g->n_nodes && i < 64; i++) {
        g->nodes[i].node_id    = i;
        g->nodes[i].features[0] = (i < TENSOR_BLOCK_ELEMS) ? in->data[i] : 0.0f;
        g->nodes[i].depth      = in->depth;
    }
    canonicalize(g);
}

static int verify_roundtrip(const CanonicalGraph *orig,
                             const CanonicalGraph *recon) {
    if (orig->n_nodes         != recon->n_nodes)         return 0;
    if (orig->n_edges         != recon->n_edges)         return 0;
    if (orig->structural_hash != recon->structural_hash) return 0;
    return 1;
}

/* ── level scheduler ────────────────────────────────────── */
static void recompute_depths(CanonicalGraph *g) {
    uint32_t i, changed;
    for (i = 0; i < g->n_nodes; i++) g->depth_map[i] = 0;
    do {
        changed = 0;
        for (i = 0; i < g->n_edges; i++) {
            uint32_t s = g->edges[i].src;
            uint32_t d = g->edges[i].dst;
            if (s < g->n_nodes && d < g->n_nodes) {
                uint8_t nd = (uint8_t)(g->depth_map[s] + 1);
                if (nd > g->depth_map[d]) {
                    g->depth_map[d]    = nd;
                    g->nodes[d].depth  = nd;
                    changed = 1;
                }
            }
        }
    } while (changed);
}

static void schedule_levels(CanonicalGraph *g,
                             TensorBlock    *activations,
                             TensorBlock    *weights,
                             TensorBlock    *output) {
    uint8_t  max_depth = 0;
    uint32_t i;
    for (i = 0; i < g->n_nodes; i++)
        if (g->depth_map[i] > max_depth) max_depth = g->depth_map[i];
    if (max_depth > MAX_DEPTH) max_depth = MAX_DEPTH;

    for (i = 0; i <= max_depth; i++) {
        activations->depth = (uint8_t)i;
        weights->depth     = (uint8_t)i;
        depth_machine(activations, weights, output);
        *activations = *output;
    }
}

/* ── full pipeline ──────────────────────────────────────── */
int native_pipeline(CanonicalGraph *g,
                    TensorBlock    *act,
                    TensorBlock    *wgt,
                    TensorBlock    *out) {
    CanonicalGraph recon;
    canonicalize(g);
    encode_graph(g, act);
    schedule_levels(g, act, wgt, out);
    decode_graph(out, &recon);
    if (!verify_roundtrip(g, &recon)) return -1;
    return 0;
}

/* ── in-process dispatch ────────────────────────────────── */
int dispatch_tensor_multiply(const TensorBlock *activations,
                              const TensorBlock *weights,
                              TensorBlock       *output) {
    depth_machine((TensorBlock *)activations, (TensorBlock *)weights, output);
    return 0;
}

int dispatch_tensor_multiply_remote(const char        *host,
                                     const TensorBlock *activations,
                                     const TensorBlock *weights,
                                     TensorBlock       *output) {
    return dispatch_tensor_multiply_tcp(host, TCP_PORT, activations, weights, output);
}

/* ── register file init / dump ──────────────────────────── */
void native_reg_init(void)                  { reg_clear(); }
void native_reg_set(uint32_t idx, uint32_t val) { reg_write(idx, val); }
uint32_t native_reg_get(uint32_t idx)       { return reg_read(idx); }

/* ── FASM-style call site boundary ──────────────────────── */
extern void execute_layer_fasm(const float *act, const float *wgt, float *out);
void call_fasm_layer(const TensorBlock *act, const TensorBlock *wgt, TensorBlock *out) {
    execute_layer_fasm(act->data, wgt->data, out->data);
}

/* ── attention mask build ───────────────────────────────── */
static void build_attention_mask(const CanonicalGraph *g, TensorBlock *mask) {
    unsigned i, j;
    memset(mask, 0, sizeof(*mask));
    mask->rank    = 2;
    mask->dtype   = DTYPE_F32;
    mask->dim[0]  = g->n_nodes;
    mask->dim[1]  = g->n_nodes;
    mask->op      = OP_MASK;
    for (i = 0; i < g->n_nodes && i < 4; i++)
        for (j = 0; j < g->n_nodes && j < 4; j++)
            if (j <= i) mask->data[i * 4 + j] = 1.0f;
}

/* ── provenance log ─────────────────────────────────────── */
typedef struct {
    uint32_t source_graph_hash;
    uint32_t node_range_begin;
    uint32_t node_range_end;
    uint32_t edge_range_begin;
    uint32_t edge_range_end;
    uint32_t transformation_id;
    uint32_t parent_id;
    uint8_t  execution_stage;
    uint8_t  pad[3];
} ProvenanceRecord;

static ProvenanceRecord prov_log[256];
static uint32_t prov_len = 0;

static void prov_append(uint32_t hash, uint8_t stage) {
    if (prov_len >= 256) return;
    ProvenanceRecord *r = &prov_log[prov_len++];
    memset(r, 0, sizeof(*r));
    r->source_graph_hash = hash;
    r->transformation_id = prov_len;
    r->execution_stage   = stage;
}

/* ── server entry ───────────────────────────────────────── */
int native_main_server(void) {
    native_reg_init();
    return tensor_tcp_server(TCP_PORT);
}

/* ── block helpers ──────────────────────────────────────── */
static void fill_pattern(TensorBlock *t, float seed) {
    unsigned i;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++)
        t->data[i] = seed + (float)i * 0.1f;
}

static void zero_block(TensorBlock *t)                    { memset(t, 0, sizeof(*t)); }
static void copy_block(TensorBlock *dst, const TensorBlock *src) { *dst = *src; }

static float block_sum(const TensorBlock *t) {
    unsigned i; float s = 0.0f;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) s += t->data[i];
    return s;
}

static float block_max(const TensorBlock *t) {
    unsigned i; float m = t->data[0];
    for (i = 1; i < TENSOR_BLOCK_ELEMS; i++) if (t->data[i] > m) m = t->data[i];
    return m;
}

static void block_scale(TensorBlock *t, float s) {
    unsigned i;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) t->data[i] *= s;
}

static void block_add(TensorBlock *a, const TensorBlock *b) {
    unsigned i;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) a->data[i] += b->data[i];
}

static void block_sub(TensorBlock *a, const TensorBlock *b) {
    unsigned i;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) a->data[i] -= b->data[i];
}

static void block_mul(TensorBlock *a, const TensorBlock *b) {
    unsigned i;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) a->data[i] *= b->data[i];
}

/* ── softmax / layernorm stubs ──────────────────────────── */
static void engine_softmax_stub(TensorBlock *t) {
    float m = block_max(t);
    unsigned i; float s = 0.0f;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) {
        t->data[i] = 1.0f + (t->data[i] - m) + 0.5f * (t->data[i] - m) * (t->data[i] - m);
        s += t->data[i];
    }
    if (s != 0.0f) block_scale(t, 1.0f / s);
}

static void engine_layernorm_stub(TensorBlock *t) {
    float mean = block_sum(t) / (float)TENSOR_BLOCK_ELEMS;
    unsigned i; float var = 0.0f;
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) { float d = t->data[i] - mean; var += d * d; }
    var /= (float)TENSOR_BLOCK_ELEMS;
    float inv = 1.0f / (1.0f + var);
    for (i = 0; i < TENSOR_BLOCK_ELEMS; i++) t->data[i] = (t->data[i] - mean) * inv;
}

/* ── graph edge walk ────────────────────────────────────── */
static void walk_edges(const CanonicalGraph *g,
                        void (*fn)(uint32_t, uint32_t, void *),
                        void *ctx) {
    uint32_t i;
    for (i = 0; i < g->n_edges; i++) fn(g->edges[i].src, g->edges[i].dst, ctx);
}

static void edge_count_cb(uint32_t s, uint32_t d, void *ctx) {
    uint32_t *c = (uint32_t *)ctx; (void)s; (void)d; (*c)++;
}

/* ── packet builders ────────────────────────────────────── */
static void build_request(TensorPacket *pkt,
                           const TensorBlock *a,
                           const TensorBlock *w,
                           uint8_t op) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->magic       = MAGIC_TENSOR;
    pkt->seq         = global_seq++;
    pkt->payload_len = sizeof(TensorBlock) * 2;
    pkt->op          = op;
    pkt->dtype       = a->dtype;
    pkt->act         = *a;
    pkt->weight      = *w;
}

static void build_response(ResultPacket *pkt,
                            uint32_t seq,
                            const TensorBlock *r) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->magic       = MAGIC_RESULT;
    pkt->seq         = seq;
    pkt->payload_len = sizeof(TensorBlock);
    pkt->status      = 0;
    pkt->depth       = r->depth;
    pkt->result      = *r;
}

/* ── inductive list / FFI ────────────────────────────────── */
#include <stdlib.h>

typedef struct Node_ { float val; struct Node_ *next; } Node;
typedef struct TensorRow_ { float data[16]; struct TensorRow_ *next; } TensorRow;

static Node *cons(float v, Node *tail) {
    Node *n = (Node *)malloc(sizeof(Node));
    if (!n) return NULL;
    n->val  = v; n->next = tail; return n;
}
static void list_free(Node *xs) { while (xs) { Node *n = xs->next; free(xs); xs = n; } }
static float list_sum(const Node *xs) { return xs ? xs->val + list_sum(xs->next) : 0.0f; }
static size_t list_length(const Node *xs) { return xs ? 1 + list_length(xs->next) : 0; }
static void list_scale(Node *xs, float s) { if (xs) { xs->val *= s; list_scale(xs->next, s); } }
static Node *list_rev_acc(Node *xs, Node *acc) {
    if (!xs) return acc;
    Node *rest = xs->next; xs->next = acc; return list_rev_acc(rest, xs);
}
static Node *list_reverse(Node *xs) { return list_rev_acc(xs, NULL); }
static TensorRow *row_cons(const float *src, TensorRow *tail) {
    TensorRow *r = (TensorRow *)malloc(sizeof(TensorRow));
    if (!r) return NULL;
    memcpy(r->data, src, sizeof(r->data)); r->next = tail; return r;
}
static void row_free(TensorRow *xs) { while (xs) { TensorRow *n = xs->next; free(xs); xs = n; } }
static void row_fma(TensorRow *acc, const TensorRow *a, const TensorRow *w) {
    if (!acc || !a || !w) return;
    unsigned i;
    for (i = 0; i < 16; i++) acc->data[i] += a->data[i] * w->data[i];
    row_fma(acc->next, a->next, w->next);
}
static void row_depth(TensorRow *xs, unsigned depth, unsigned max_depth) {
    if (!xs || depth >= max_depth) return;
    unsigned i;
    for (i = 0; i < 16; i++) xs->data[i] += 1.0f;
    row_depth(xs->next, depth + 1, max_depth);
}

float    ffi_list_sum(const Node *xs)             { return list_sum(xs); }
size_t   ffi_list_length(const Node *xs)          { return list_length(xs); }
void     ffi_list_scale(Node *xs, float s)        { list_scale(xs, s); }
Node    *ffi_list_reverse(Node *xs)               { return list_reverse(xs); }
void     ffi_row_fma(TensorRow *acc, const TensorRow *a, const TensorRow *w) { row_fma(acc, a, w); }
void     ffi_row_depth(TensorRow *xs, unsigned d, unsigned m) { row_depth(xs, d, m); }

/* ── warp lane walk ─────────────────────────────────────── */
typedef struct Lane_ { uint32_t id; float reg[8]; struct Lane_ *next; } Lane;
static void warp_fma(Lane *lanes, unsigned max_depth) {
    unsigned d;
    for (d = 0; d < max_depth; d++) {
        Lane *L = lanes;
        while (L) { unsigned i; for (i = 0; i < 8; i++) L->reg[i] += L->reg[i]; L = L->next; }
    }
}

/* ============================================================
   END OF NATIVE TCP TENSOR MACHINE
   ============================================================ */
