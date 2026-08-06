/*
 * Sovereign IDE — Event System
 * Lock-free SPSC ring buffer for inter-module communication.
 * C native modules post events; consumers drain per frame.
 */

#include "events.h"
#include <string.h>
#include <assert.h>

#define EVENT_QUEUE_CAPACITY 4096

static struct {
    Event    ring[EVENT_QUEUE_CAPACITY];
    volatile LONG write_pos;
    volatile LONG read_pos;
} g_events;

void events_init(void) {
    memset(&g_events, 0, sizeof(g_events));
}

bool event_post(Event ev) {
    LONG w = g_events.write_pos;
    LONG next = (w + 1) % EVENT_QUEUE_CAPACITY;
    if (next == g_events.read_pos) {
        return false; /* queue full */
    }
    g_events.ring[w] = ev;
    MemoryBarrier();
    InterlockedExchange(&g_events.write_pos, next);
    return true;
}

bool event_poll(Event *out) {
    LONG r = g_events.read_pos;
    if (r == g_events.write_pos) {
        return false; /* empty */
    }
    *out = g_events.ring[r];
    MemoryBarrier();
    InterlockedExchange(&g_events.read_pos, (r + 1) % EVENT_QUEUE_CAPACITY);
    return true;
}

void events_drain(EventHandler handler, void *ctx) {
    Event ev;
    while (event_poll(&ev)) {
        handler(&ev, ctx);
    }
}
