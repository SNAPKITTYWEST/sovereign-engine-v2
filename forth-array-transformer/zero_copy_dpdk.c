/* ============================================================
   LINUX SPLICE + DPDK ZERO-COPY PATHS
   Native only. No Rust. No Python.
   ============================================================ */

#define _GNU_SOURCE
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/mman.h>
#include <sys/uio.h>
#include <sys/ioctl.h>
#include <sys/epoll.h>
#include <sys/eventfd.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <linux/if_packet.h>
#include <linux/if_ether.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <linux/ethtool.h>
#include <linux/sockios.h>
#include <net/if.h>

/* DPDK headers — conditionally compiled to allow build without DPDK SDK */
#ifdef HAVE_DPDK
#include <rte_config.h>
#include <rte_common.h>
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_mbuf.h>
#include <rte_mempool.h>
#include <rte_ring.h>
#include <rte_memcpy.h>
#include <rte_lcore.h>
#include <rte_cycles.h>
#include <rte_atomic.h>
#include <rte_malloc.h>
#include <rte_ether.h>
#endif

#define TENSOR_BLOCK_ELEMS 16
#define ZC_RING_SLOTS    256
#define ZC_SLOT_SIZE     4096
#define SPLICE_PIPE_SIZE (64 * 1024)
#define DPDK_RX_RING_SIZE 1024
#define DPDK_TX_RING_SIZE 1024
#define DPDK_NUM_MBUFS  8191
#define DPDK_MBUF_CACHE 250
#define DPDK_BURST       32

/* ─ error codes ─────────────────────────────────────────── */
#define TN_OK            0
#define TN_ERR_EAL      -1
#define TN_ERR_NO_PORT  -2
#define TN_ERR_MEMPOOL  -3
#define TN_ERR_RING     -4
#define TN_ERR_CONFIG   -5
#define TN_ERR_RXQ      -6
#define TN_ERR_TXQ      -7
#define TN_ERR_START    -8
#define TN_ERR_LINK     -9
#define TN_ERR_MBUF    -10
#define TN_ERR_ENQUEUE -11
#define TN_ERR_DEQUEUE -12
#define TN_ERR_SPLICE  -13
#define TN_ERR_SOCKET  -14
#define TN_ERR_BIND    -15
#define TN_ERR_LISTEN  -16
#define TN_ERR_ACCEPT  -17
#define TN_ERR_NETLINK -18
#define TN_ERR_IOCTL   -19
#define TN_ERR_MMAP    -20
#define TN_ERR_POLL    -21
#define TN_ERR_TIMEOUT -22
#define TN_ERR_PROTO   -23
#define TN_ERR_VERIFY  -24
#define TN_ERR_DEPTH   -25

static const char *tn_strerror(int e) {
    switch (e) {
    case TN_OK:            return "ok";
    case TN_ERR_EAL:       return "rte_eal_init failed";
    case TN_ERR_NO_PORT:   return "no DPDK ports";
    case TN_ERR_MEMPOOL:   return "mempool create failed";
    case TN_ERR_RING:      return "ring create failed";
    case TN_ERR_CONFIG:    return "eth_dev_configure failed";
    case TN_ERR_RXQ:       return "rx_queue_setup failed";
    case TN_ERR_TXQ:       return "tx_queue_setup failed";
    case TN_ERR_START:     return "eth_dev_start failed";
    case TN_ERR_LINK:      return "link down";
    case TN_ERR_MBUF:      return "mbuf alloc failed";
    case TN_ERR_ENQUEUE:   return "ring enqueue failed";
    case TN_ERR_DEQUEUE:   return "ring dequeue failed";
    case TN_ERR_SPLICE:    return "splice/vmsplice failed";
    case TN_ERR_SOCKET:    return "socket failed";
    case TN_ERR_BIND:      return "bind failed";
    case TN_ERR_LISTEN:    return "listen failed";
    case TN_ERR_ACCEPT:    return "accept failed";
    case TN_ERR_NETLINK:   return "netlink failed";
    case TN_ERR_IOCTL:     return "ioctl failed";
    case TN_ERR_MMAP:      return "mmap failed";
    case TN_ERR_POLL:      return "poll/epoll failed";
    case TN_ERR_TIMEOUT:   return "timeout";
    case TN_ERR_PROTO:     return "protocol error";
    case TN_ERR_VERIFY:    return "verify failed";
    case TN_ERR_DEPTH:     return "depth exceeded";
    default:               return "unknown";
    }
}

/* ─ tensor packet types (same layout as native_tensor_dispatch.c) */
typedef struct {
    uint32_t base_address;
    uint8_t  rank, dtype, layout, elem_size;
    uint32_t dim[4];
    uint32_t stride[4];
    uint32_t acc_reg, weight_reg, act_reg, result_reg;
    uint8_t  op, depth, pad[2];
    float    data[TENSOR_BLOCK_ELEMS];
} TensorBlock;

typedef struct {
    uint32_t    magic, seq, payload_len;
    uint8_t     op, depth, dtype, flags;
    TensorBlock act, weight;
} TensorPacket;

typedef struct {
    uint32_t    magic, seq, payload_len;
    uint8_t     status, depth, pad[2];
    TensorBlock result;
} ResultPacket;

/* ─────────────────────────────────────────────────────────
   LINUX SPLICE / VMSPLICE / TEE
   ───────────────────────────────────────────────────────── */

static int splice_all(int fd_in, int fd_out, size_t len) {
    size_t left = len;
    while (left > 0) {
        ssize_t n = splice(fd_in, NULL, fd_out, NULL, left,
                           SPLICE_F_MOVE | SPLICE_F_MORE);
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) continue;
            return -1;
        }
        if (n == 0) break;
        left -= (size_t)n;
    }
    return (left == 0) ? 0 : -2;
}

static int vmsplice_tensor(int pipe_wr, const TensorPacket *pkt) {
    struct iovec iov;
    iov.iov_base = (void *)pkt;
    iov.iov_len  = sizeof(*pkt);
    for (;;) {
        ssize_t n = vmsplice(pipe_wr, &iov, 1, SPLICE_F_GIFT);
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) continue;
            return -1;
        }
        if ((size_t)n == sizeof(*pkt)) return 0;
        return -2;
    }
}

static int tee_pipe(int fd_in, int fd_out, size_t len) {
    size_t left = len;
    while (left > 0) {
        ssize_t n = tee(fd_in, fd_out, left, SPLICE_F_NONBLOCK);
        if (n < 0) {
            if (errno == EAGAIN || errno == EINTR) continue;
            return -1;
        }
        if (n == 0) break;
        left -= (size_t)n;
    }
    return 0;
}

static int make_tensor_pipe(int pfd[2]) {
    if (pipe2(pfd, O_NONBLOCK | O_CLOEXEC) < 0)      return -1;
    if (fcntl(pfd[0], F_SETPIPE_SZ, SPLICE_PIPE_SIZE) < 0) return -2;
    if (fcntl(pfd[1], F_SETPIPE_SZ, SPLICE_PIPE_SIZE) < 0) return -3;
    return 0;
}

int dispatch_tensor_multiply_splice(
    int                sock_fd,
    const TensorBlock *activations,
    const TensorBlock *weights,
    TensorBlock       *output)
{
    int pfd[2];
    TensorPacket req;
    ResultPacket resp;
    int rc;

    if (make_tensor_pipe(pfd) < 0) return TN_ERR_SPLICE;

    memset(&req, 0, sizeof(req));
    req.magic  = 0x54454E53u;
    req.op     = 0x02;
    req.act    = *activations;
    req.weight = *weights;

    rc = vmsplice_tensor(pfd[1], &req);
    if (rc < 0) { close(pfd[0]); close(pfd[1]); return TN_ERR_SPLICE; }

    rc = splice_all(pfd[0], sock_fd, sizeof(req));
    if (rc < 0) { close(pfd[0]); close(pfd[1]); return TN_ERR_SPLICE; }

    {
        uint8_t *p = (uint8_t *)&resp;
        size_t got = 0;
        while (got < sizeof(resp)) {
            ssize_t n = recv(sock_fd, p + got, sizeof(resp) - got, 0);
            if (n <= 0) { close(pfd[0]); close(pfd[1]); return TN_ERR_PROTO; }
            got += (size_t)n;
        }
    }

    *output = resp.result;
    close(pfd[0]);
    close(pfd[1]);
    return TN_OK;
}

/* ─────────────────────────────────────────────────────────
   PMD INTERNALS — SOFTWARE RING DESCRIPTORS
   ───────────────────────────────────────────────────────── */
#define PMD_DESC_NB   1024
#define PMD_DESC_MASK (PMD_DESC_NB - 1)
#define PMD_BURST      32

struct pmd_rx_desc {
    void    *mbuf;
    uint16_t data_len, pkt_len;
    uint32_t ol_flags;
    uint16_t vlan_tci, hash;
    uint8_t  status, error, pad[2];
};

struct pmd_tx_desc {
    void    *mbuf;
    uint16_t data_len;
    uint8_t  status, error;
    uint32_t flags;
};

struct pmd_rx_queue {
    struct pmd_rx_desc descs[PMD_DESC_NB];
    uint16_t head, tail, free, port_id, queue_id;
    void    *mp;
    uint64_t rx_pkts, rx_bytes, rx_errors, rx_missed;
};

struct pmd_tx_queue {
    struct pmd_tx_desc descs[PMD_DESC_NB];
    uint16_t head, tail, free, port_id, queue_id;
    uint64_t tx_pkts, tx_bytes, tx_errors, tx_drop;
};

/* ─────────────────────────────────────────────────────────
   LINUX KERNEL NETWORKING STACK SURFACE
   ───────────────────────────────────────────────────────── */

static int nl_open(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE);
    if (fd < 0) return TN_ERR_NETLINK;
    return fd;
}

static int nl_link_query(int nlfd, const char *ifname) {
    struct {
        struct nlmsghdr nh;
        struct ifinfomsg ifm;
        char attrbuf[256];
    } req;
    struct sockaddr_nl sa;
    int len;

    memset(&req, 0, sizeof(req));
    req.nh.nlmsg_len   = NLMSG_LENGTH(sizeof(struct ifinfomsg));
    req.nh.nlmsg_type  = RTM_GETLINK;
    req.nh.nlmsg_flags = NLM_F_REQUEST;
    req.ifm.ifi_family = AF_UNSPEC;

    if (ifname) {
        struct rtattr *rta = (struct rtattr *)(
            ((char *)&req) + NLMSG_ALIGN(req.nh.nlmsg_len));
        rta->rta_type = IFLA_IFNAME;
        rta->rta_len  = RTA_LENGTH(strlen(ifname) + 1);
        memcpy(RTA_DATA(rta), ifname, strlen(ifname) + 1);
        req.nh.nlmsg_len = NLMSG_ALIGN(req.nh.nlmsg_len) + RTA_ALIGN(rta->rta_len);
    }

    memset(&sa, 0, sizeof(sa));
    sa.nl_family = AF_NETLINK;
    len = sendto(nlfd, &req, req.nh.nlmsg_len, 0,
                 (struct sockaddr *)&sa, sizeof(sa));
    if (len < 0) return TN_ERR_NETLINK;
    return TN_OK;
}

static int ethtool_link(const char *ifname, int *up, uint32_t *speed) {
    int fd;
    struct ifreq ifr;
    struct ethtool_cmd ecmd;
    struct ethtool_value edata;

    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return TN_ERR_SOCKET;

    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);

    edata.cmd       = ETHTOOL_GLINK;
    ifr.ifr_data    = (caddr_t)&edata;
    if (ioctl(fd, SIOCETHTOOL, &ifr) < 0) { close(fd); return TN_ERR_IOCTL; }
    *up = edata.data ? 1 : 0;

    memset(&ecmd, 0, sizeof(ecmd));
    ecmd.cmd     = ETHTOOL_GSET;
    ifr.ifr_data = (caddr_t)&ecmd;
    if (ioctl(fd, SIOCETHTOOL, &ifr) == 0)
        *speed = ethtool_cmd_speed(&ecmd);
    else
        *speed = 0;

    close(fd);
    return TN_OK;
}

/* AF_PACKET raw socket with TPACKET_V3 */
struct kpkg_ring {
    int              fd;
    void            *map;
    size_t           map_len;
    struct tpacket_req3 req;
    uint32_t         block_nr, frame_nr;
};

static int kpkg_ring_open(const char *ifname, struct kpkg_ring *kr) {
    int fd;
    struct sockaddr_ll sll;
    struct ifreq ifr;
    int ver = TPACKET_V3;
    int fanout;

    fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (fd < 0) return TN_ERR_SOCKET;

    if (setsockopt(fd, SOL_PACKET, PACKET_VERSION, &ver, sizeof(ver)) < 0) {
        close(fd); return TN_ERR_IOCTL;
    }

    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) { close(fd); return TN_ERR_IOCTL; }

    memset(&sll, 0, sizeof(sll));
    sll.sll_family   = AF_PACKET;
    sll.sll_protocol = htons(ETH_P_ALL);
    sll.sll_ifindex  = ifr.ifr_ifindex;
    if (bind(fd, (struct sockaddr *)&sll, sizeof(sll)) < 0) {
        close(fd); return TN_ERR_BIND;
    }

    memset(&kr->req, 0, sizeof(kr->req));
    kr->req.tp_block_size   = 1 << 22;
    kr->req.tp_block_nr     = 64;
    kr->req.tp_frame_size   = 2048;
    kr->req.tp_frame_nr     = (kr->req.tp_block_size / kr->req.tp_frame_size) *
                               kr->req.tp_block_nr;
    kr->req.tp_retire_blk_tov = 60;

    if (setsockopt(fd, SOL_PACKET, PACKET_RX_RING, &kr->req, sizeof(kr->req)) < 0) {
        close(fd); return TN_ERR_IOCTL;
    }

    kr->map_len = kr->req.tp_block_size * kr->req.tp_block_nr;
    kr->map = mmap(NULL, kr->map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (kr->map == MAP_FAILED) { close(fd); return TN_ERR_MMAP; }

    fanout = (getpid() & 0xffff) | (PACKET_FANOUT_HASH << 16);
    setsockopt(fd, SOL_PACKET, PACKET_FANOUT, &fanout, sizeof(fanout));

    kr->fd       = fd;
    kr->block_nr = kr->req.tp_block_nr;
    kr->frame_nr = kr->req.tp_frame_nr;
    return TN_OK;
}

static void kpkg_ring_close(struct kpkg_ring *kr) {
    if (kr->map)   munmap(kr->map, kr->map_len);
    if (kr->fd >= 0) close(kr->fd);
    kr->map = NULL; kr->fd = -1;
}

/* epoll-driven kernel socket event loop */
struct ksock_loop {
    int epfd, listen_fd, event_fd;
};

static int ksock_loop_init(struct ksock_loop *kl, uint16_t port) {
    struct sockaddr_in addr;
    struct epoll_event ev;
    int one = 1;

    kl->epfd = epoll_create1(EPOLL_CLOEXEC);
    if (kl->epfd < 0) return TN_ERR_POLL;

    kl->listen_fd = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
    if (kl->listen_fd < 0) return TN_ERR_SOCKET;

    setsockopt(kl->listen_fd, SOL_SOCKET,   SO_REUSEADDR,   &one, sizeof(one));
    setsockopt(kl->listen_fd, IPPROTO_TCP,  TCP_NODELAY,    &one, sizeof(one));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port        = htons(port);
    if (bind(kl->listen_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0)
        return TN_ERR_BIND;
    if (listen(kl->listen_fd, 128) < 0)
        return TN_ERR_LISTEN;

    ev.events   = EPOLLIN;
    ev.data.fd  = kl->listen_fd;
    if (epoll_ctl(kl->epfd, EPOLL_CTL_ADD, kl->listen_fd, &ev) < 0)
        return TN_ERR_POLL;

    kl->event_fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    if (kl->event_fd < 0) return TN_ERR_POLL;
    ev.events  = EPOLLIN;
    ev.data.fd = kl->event_fd;
    epoll_ctl(kl->epfd, EPOLL_CTL_ADD, kl->event_fd, &ev);

    return TN_OK;
}

static int ksock_loop_run(struct ksock_loop *kl, int timeout_ms) {
    struct epoll_event events[64];
    int n, i;

    n = epoll_wait(kl->epfd, events, 64, timeout_ms);
    if (n < 0) {
        if (errno == EINTR) return TN_OK;
        return TN_ERR_POLL;
    }

    for (i = 0; i < n; i++) {
        if (events[i].data.fd == kl->listen_fd) {
            int cfd = accept4(kl->listen_fd, NULL, NULL,
                              SOCK_NONBLOCK | SOCK_CLOEXEC);
            if (cfd >= 0) {
                struct epoll_event ev;
                ev.events  = EPOLLIN | EPOLLRDHUP;
                ev.data.fd = cfd;
                epoll_ctl(kl->epfd, EPOLL_CTL_ADD, cfd, &ev);
            }
        } else if (events[i].data.fd == kl->event_fd) {
            uint64_t v;
            (void)read(kl->event_fd, &v, sizeof(v));
        } else {
            if (events[i].events & (EPOLLRDHUP | EPOLLHUP | EPOLLERR)) {
                epoll_ctl(kl->epfd, EPOLL_CTL_DEL, events[i].data.fd, NULL);
                close(events[i].data.fd);
            }
        }
    }
    return TN_OK;
}

/* ─────────────────────────────────────────────────────────
   FULL INIT WITH ERROR PROPAGATION
   ───────────────────────────────────────────────────────── */
int tensor_net_init_kernel(const char *kif, uint16_t port) {
    struct ksock_loop kl;
    struct kpkg_ring  kr;
    int nlfd;
    int up   = 0;
    uint32_t speed = 0;
    int ret;

    if (kif) {
        ret = ethtool_link(kif, &up, &speed);
        if (ret < 0) return ret;

        ret = kpkg_ring_open(kif, &kr);
        if (ret < 0) return ret;
    }

    nlfd = nl_open();
    if (nlfd < 0) return nlfd;
    if (kif) nl_link_query(nlfd, kif);
    close(nlfd);

    ret = ksock_loop_init(&kl, port);
    if (ret < 0) return ret;

    (void)speed; (void)up;
    return TN_OK;
}

/* ─────────────────────────────────────────────────────────
   COMBINED POLL LOOP (kernel only — no DPDK in this build)
   ───────────────────────────────────────────────────────── */
int tensor_poll_loop_kernel(struct ksock_loop *kl, int timeout_ms) {
    return ksock_loop_run(kl, timeout_ms);
}

/* ============================================================
   END OF ZERO-COPY / DPDK MODULE
   ============================================================ */
