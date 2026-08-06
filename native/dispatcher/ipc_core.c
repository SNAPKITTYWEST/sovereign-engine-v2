/*
 * ipc_core.c — Sovereign IPC Dispatcher (C core)
 * Part of SOVEREIGN PYTHON LLM ENGINE
 *
 * POSIX shared memory poll loop.  Attaches to the same named shared memory
 * region used by the Python NativeToolRouter.  Polls the dispatch header at
 * offset 0 every 50 microseconds.  When a valid packet arrives (magic ==
 * "DISP", opcode != 0) it logs the dispatch information to stderr, clears
 * the header so the Python worker can continue, and loops.
 *
 * This is the sentinel / relay process that bridges OS-level IPC into the
 * Python asyncio dispatch loop.  On Linux/macOS it uses POSIX shm_open +
 * mmap.  Windows uses named pipe IPC instead (see conditional compile below).
 *
 * Build:
 *   gcc -Wall -O2 -o ipc_core ipc_core.c
 *   (POSIX)   links automatically — no extra flags needed
 *   (macOS)   same; /dev/shm is available via shm_open
 *
 * Usage:
 *   ./ipc_core [shm_name] [size_bytes]
 *   Defaults: shm_name="sovereign_disp", size=65536
 *
 * Wire format (12-byte header, big-endian):
 *   Offset  Len  Field
 *   0       4    magic      — must be 'D','I','S','P'
 *   4       2    opcode     — 16-bit tool opcode (big-endian)
 *   6       2    flags      — dispatch flags (big-endian)
 *   8       4    payload_len — payload length in bytes (big-endian)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <signal.h>

/* ── Platform selection ─────────────────────────────────────────────────── */

#if defined(_WIN32) || defined(_WIN64)
#  define PLATFORM_WINDOWS 1
#else
#  define PLATFORM_POSIX 1
#endif

#ifdef PLATFORM_POSIX
#  include <unistd.h>
#  include <fcntl.h>
#  include <sys/mman.h>
#  include <sys/stat.h>
#  include <errno.h>
#endif

#ifdef PLATFORM_WINDOWS
#  include <windows.h>
#  include <io.h>
#endif

/* ── Constants ──────────────────────────────────────────────────────────── */

#define DISP_MAGIC       "DISP"
#define MAGIC_LEN        4
#define HEADER_SIZE      12

#define DEFAULT_SHM_NAME "sovereign_disp"
#define DEFAULT_SHM_SIZE 65536

/* Poll interval: 50 microseconds */
#define POLL_INTERVAL_US 50

/* ── Dispatch packet header (packed, big-endian in memory) ──────────────── */

typedef struct __attribute__((packed)) {
    char     magic[4];       /* b'DISP' */
    uint16_t opcode;         /* 16-bit tool opcode, big-endian */
    uint16_t flags;          /* dispatch flags, big-endian */
    uint32_t payload_len;    /* payload length in bytes, big-endian */
    char     data[];         /* variable-length payload immediately follows */
} DispatchPacket;

/* ── Byte-order helpers (portable big-endian read) ──────────────────────── */

static inline uint16_t be16(const uint16_t v) {
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)((v >> 8) | (v << 8));
#elif defined(_WIN32)
    return (uint16_t)((v >> 8) | (v << 8));
#else
    return v; /* big-endian host — no swap needed */
#endif
}

static inline uint32_t be32(const uint32_t v) {
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return ((v & 0xFF000000u) >> 24) |
           ((v & 0x00FF0000u) >>  8) |
           ((v & 0x0000FF00u) <<  8) |
           ((v & 0x000000FFu) << 24);
#elif defined(_WIN32)
    return ((v & 0xFF000000u) >> 24) |
           ((v & 0x00FF0000u) >>  8) |
           ((v & 0x0000FF00u) <<  8) |
           ((v & 0x000000FFu) << 24);
#else
    return v;
#endif
}

/* ── Monotonic timestamp in microseconds (diagnostics only) ─────────────── */

static uint64_t now_us(void) {
#ifdef PLATFORM_WINDOWS
    LARGE_INTEGER freq, count;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&count);
    return (uint64_t)(count.QuadPart * 1000000ULL / freq.QuadPart);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)ts.tv_nsec / 1000ULL;
#endif
}

/* ── Signal handling ────────────────────────────────────────────────────── */

static volatile int g_running = 1;

static void handle_signal(int sig) {
    (void)sig;
    g_running = 0;
}

/* ── POSIX shared memory implementation ─────────────────────────────────── */

#ifdef PLATFORM_POSIX

typedef struct {
    int   fd;
    void *addr;
    size_t size;
    char  name[256];
} ShmRegion;

static int shm_open_region(ShmRegion *r, const char *name, size_t size) {
    /* Prepend '/' if not present — POSIX shm_open requires it */
    if (name[0] == '/') {
        snprintf(r->name, sizeof(r->name), "%s", name);
    } else {
        snprintf(r->name, sizeof(r->name), "/%s", name);
    }
    r->size = size;

    r->fd = shm_open(r->name, O_CREAT | O_RDWR, 0600);
    if (r->fd < 0) {
        perror("shm_open");
        return -1;
    }

    if (ftruncate(r->fd, (off_t)size) < 0) {
        perror("ftruncate");
        close(r->fd);
        return -1;
    }

    r->addr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, r->fd, 0);
    if (r->addr == MAP_FAILED) {
        perror("mmap");
        close(r->fd);
        return -1;
    }

    /* The fd can be closed once mmap'd — the mapping keeps the region alive */
    close(r->fd);
    r->fd = -1;

    fprintf(stderr, "[ipc_core] Attached POSIX shm %s (%zu bytes)\n",
            r->name, r->size);
    return 0;
}

static void shm_close_region(ShmRegion *r) {
    if (r->addr && r->addr != MAP_FAILED) {
        munmap(r->addr, r->size);
        r->addr = NULL;
    }
    /* Intentionally do NOT shm_unlink here — Python side owns lifecycle */
}

static int run_dispatch_loop(ShmRegion *r) {
    DispatchPacket *pkt = (DispatchPacket *)r->addr;
    uint64_t dispatch_count = 0;

    fprintf(stderr,
            "[ipc_core] Poll loop running (interval=%d µs, SIGINT to stop)\n",
            POLL_INTERVAL_US);

    while (g_running) {
        /* Check magic without acquiring any lock — single-writer protocol */
        if (memcmp(pkt->magic, DISP_MAGIC, MAGIC_LEN) == 0) {
            uint16_t opcode  = be16(pkt->opcode);
            uint16_t flags   = be16(pkt->flags);
            uint32_t plen    = be32(pkt->payload_len);

            if (opcode != 0) {
                uint64_t ts = now_us();
                dispatch_count++;

                fprintf(stderr,
                        "[ipc_core] dispatch #%llu  ts=%llu µs  "
                        "opcode=0x%04X  flags=0x%04X  plen=%u\n",
                        (unsigned long long)dispatch_count,
                        (unsigned long long)ts,
                        (unsigned)opcode,
                        (unsigned)flags,
                        (unsigned)plen);

                /*
                 * Clear the dispatch header — 12 bytes of zeros signals
                 * to the Python poll loop that the slot is free.
                 * The Python worker will have already read the payload before
                 * we clear, because it processes the packet and writes the
                 * response before the C side comes back around to poll.
                 * In a multi-writer scenario a compare-and-swap would be
                 * needed, but this design is single-writer / single-reader.
                 */
                memset(r->addr, 0, HEADER_SIZE);

                /* msync is optional on Linux — write ordering is sufficient
                 * for same-machine IPC, but aids correctness on macOS */
#ifdef __APPLE__
                msync(r->addr, HEADER_SIZE, MS_SYNC);
#endif
            }
        }

        usleep(POLL_INTERVAL_US);
    }

    fprintf(stderr,
            "[ipc_core] Stopping — %llu dispatches processed\n",
            (unsigned long long)dispatch_count);
    return 0;
}

int main(int argc, char *argv[]) {
    const char *shm_name = DEFAULT_SHM_NAME;
    size_t      shm_size = DEFAULT_SHM_SIZE;

    if (argc >= 2) shm_name = argv[1];
    if (argc >= 3) shm_size = (size_t)atol(argv[2]);

    if (shm_size < (size_t)HEADER_SIZE) {
        fprintf(stderr, "[ipc_core] ERROR: shm_size must be >= %d bytes\n",
                HEADER_SIZE);
        return 1;
    }

    signal(SIGINT,  handle_signal);
    signal(SIGTERM, handle_signal);

    ShmRegion region;
    memset(&region, 0, sizeof(region));

    if (shm_open_region(&region, shm_name, shm_size) < 0) {
        return 1;
    }

    int rc = run_dispatch_loop(&region);

    shm_close_region(&region);
    return rc;
}

#endif /* PLATFORM_POSIX */

/* ── Windows named pipe implementation ─────────────────────────────────── */

#ifdef PLATFORM_WINDOWS

/*
 * On Windows, shm_open does not exist.  We implement equivalent IPC using a
 * named pipe so the C core can still relay dispatch events to the Python
 * worker.  The Python NativeToolRouter uses mmap with tagname= (a Windows
 * Named Section), which is the correct SHM primitive on Windows — the C
 * core here communicates via a named pipe as a diagnostic/relay channel.
 *
 * Named pipe path: \\.\pipe\sovereign_disp  (or argv[1])
 *
 * Protocol: same 12-byte DispatchPacket header.
 */

static int run_dispatch_loop_win(HANDLE pipe) {
    uint8_t  buf[HEADER_SIZE];
    DWORD    bytes_read;
    uint64_t dispatch_count = 0;

    fprintf(stderr,
            "[ipc_core] Windows named pipe poll loop running (CTRL-C to stop)\n");

    while (g_running) {
        BOOL ok = ReadFile(pipe, buf, HEADER_SIZE, &bytes_read, NULL);

        if (!ok || bytes_read < HEADER_SIZE) {
            if (!ok) {
                DWORD err = GetLastError();
                if (err == ERROR_BROKEN_PIPE) {
                    fprintf(stderr, "[ipc_core] Pipe broken — client disconnected\n");
                } else {
                    fprintf(stderr, "[ipc_core] ReadFile error: %lu\n", err);
                }
            }
            Sleep(POLL_INTERVAL_US / 1000 + 1);
            continue;
        }

        if (memcmp(buf, DISP_MAGIC, MAGIC_LEN) != 0) {
            continue;
        }

        uint16_t opcode = be16(*(uint16_t *)(buf + 4));
        uint16_t flags  = be16(*(uint16_t *)(buf + 6));
        uint32_t plen   = be32(*(uint32_t *)(buf + 8));

        if (opcode != 0) {
            dispatch_count++;
            fprintf(stderr,
                    "[ipc_core] dispatch #%llu  opcode=0x%04X  "
                    "flags=0x%04X  plen=%u\n",
                    (unsigned long long)dispatch_count,
                    (unsigned)opcode,
                    (unsigned)flags,
                    (unsigned)plen);
        }
    }

    fprintf(stderr,
            "[ipc_core] Stopping — %llu dispatches processed\n",
            (unsigned long long)dispatch_count);
    return 0;
}

int main(int argc, char *argv[]) {
    const char *pipe_name_base = (argc >= 2) ? argv[1] : DEFAULT_SHM_NAME;
    char        pipe_path[512];

    /* Build \\.\pipe\<name> */
    snprintf(pipe_path, sizeof(pipe_path), "\\\\.\\pipe\\%s", pipe_name_base);

    signal(SIGINT,  handle_signal);

    fprintf(stderr, "[ipc_core] Creating named pipe: %s\n", pipe_path);

    HANDLE pipe = CreateNamedPipeA(
        pipe_path,
        PIPE_ACCESS_INBOUND,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1,        /* max instances */
        0,        /* out buffer size */
        4096,     /* in buffer size */
        0,        /* default timeout */
        NULL      /* default security */
    );

    if (pipe == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "[ipc_core] CreateNamedPipe failed: %lu\n",
                GetLastError());
        return 1;
    }

    fprintf(stderr, "[ipc_core] Waiting for client connection...\n");

    if (!ConnectNamedPipe(pipe, NULL)) {
        DWORD err = GetLastError();
        if (err != ERROR_PIPE_CONNECTED) {
            fprintf(stderr, "[ipc_core] ConnectNamedPipe failed: %lu\n", err);
            CloseHandle(pipe);
            return 1;
        }
    }

    fprintf(stderr, "[ipc_core] Client connected\n");

    int rc = run_dispatch_loop_win(pipe);

    CloseHandle(pipe);
    return rc;
}

#endif /* PLATFORM_WINDOWS */
