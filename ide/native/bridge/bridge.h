/*
 * Bridge Client — C → Python Engine
 * Sovereign IDE Bridge Layer
 *
 * Communicates with Python sovereign-engine via stdio or HTTP.
 */

#ifndef BRIDGE_H
#define BRIDGE_H

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Bridge transport types */
typedef enum {
    BRIDGE_TRANSPORT_STDIO,
    BRIDGE_TRANSPORT_HTTP
} BridgeTransport;

/* Bridge result codes */
typedef enum {
    BRIDGE_OK = 0,
    BRIDGE_ERROR_INIT = -1,
    BRIDGE_ERROR_SEND = -2,
    BRIDGE_ERROR_RECV = -3,
    BRIDGE_ERROR_PARSE = -4,
    BRIDGE_ERROR_TIMEOUT = -5
} BridgeResult;

/* Bridge handle (opaque) */
typedef struct Bridge Bridge;

/* Bridge configuration */
typedef struct {
    BridgeTransport transport;

    /* HTTP config */
    const char* http_host;
    unsigned short http_port;

    /* Stdio config */
    const char* python_executable;
    const char* bridge_script;

    /* Timeouts (milliseconds) */
    unsigned int request_timeout;
} BridgeConfig;

/* Response callback */
typedef void (*BridgeCallback)(const char* response_json, void* user_data);

/*
 * Initialize bridge
 * Returns bridge handle on success, NULL on failure
 */
Bridge* bridge_init(const BridgeConfig* config);

/*
 * Shutdown bridge
 */
void bridge_shutdown(Bridge* bridge);

/*
 * Check if bridge is ready
 */
bool bridge_is_ready(Bridge* bridge);

/*
 * Run agent task (blocking)
 * Returns JSON response string (caller must free)
 */
char* bridge_agent_run(Bridge* bridge, const char* task);

/*
 * Run agent task (async)
 */
BridgeResult bridge_agent_run_async(
    Bridge* bridge,
    const char* task,
    BridgeCallback callback,
    void* user_data
);

/*
 * Execute tool (blocking)
 */
char* bridge_tool_execute(
    Bridge* bridge,
    const char* tool_name,
    const char* args_json
);

/*
 * List available tools (blocking)
 */
char* bridge_tools_list(Bridge* bridge);

/*
 * Send chat message (blocking)
 */
char* bridge_chat_message(Bridge* bridge, const char* message);

/*
 * Health check (blocking)
 */
bool bridge_health_check(Bridge* bridge);

/*
 * Get last error message
 */
const char* bridge_get_error(Bridge* bridge);

/*
 * Set API key for provider
 * provider: "openrouter" or "ollama"
 * Returns JSON response (caller must free)
 */
char* bridge_set_key(Bridge* bridge, const char* provider, const char* api_key);

/*
 * Get API key status
 * Returns JSON with all provider statuses (caller must free)
 */
char* bridge_get_key_status(Bridge* bridge);

/*
 * Delete API key for provider
 * Returns JSON response (caller must free)
 */
char* bridge_delete_key(Bridge* bridge, const char* provider);

#ifdef __cplusplus
}
#endif

#endif /* BRIDGE_H */
