#ifndef SOVEREIGN_EVENTS_H
#define SOVEREIGN_EVENTS_H

#include <stdbool.h>
#include <stdint.h>
#include <windows.h>

typedef enum EventKind {
    EVENT_NONE = 0,
    EVENT_KEY_DOWN,
    EVENT_KEY_UP,
    EVENT_CHAR_INPUT,
    EVENT_MOUSE_MOVE,
    EVENT_MOUSE_DOWN,
    EVENT_MOUSE_UP,
    EVENT_MOUSE_WHEEL,
    EVENT_RESIZE,
    EVENT_FOCUS_GAINED,
    EVENT_FOCUS_LOST,
    EVENT_FILE_CHANGED,
    EVENT_CHAT_MESSAGE,
    EVENT_TOOL_RESULT,
    EVENT_APPROVAL_REQUEST,
    EVENT_BUILD_OUTPUT,
    EVENT_DIAGNOSTIC,
    EVENT_QUIT,
} EventKind;

typedef struct Event {
    EventKind kind;
    uint64_t  timestamp;
    union {
        struct { uint32_t vk; uint32_t scancode; uint32_t mods; }  key;
        struct { uint32_t codepoint; }                              ch;
        struct { int32_t x; int32_t y; uint32_t buttons; }         mouse;
        struct { int32_t delta; }                                   wheel;
        struct { uint32_t width; uint32_t height; }                 resize;
        struct { uint64_t id; }                                     message;
    };
} Event;

typedef void (*EventHandler)(const Event *ev, void *ctx);

void events_init(void);
bool event_post(Event ev);
bool event_poll(Event *out);
void events_drain(EventHandler handler, void *ctx);

#endif /* SOVEREIGN_EVENTS_H */
