/*
 * Bridge Usage Example
 * Demonstrates how to use the C → Python bridge
 */

#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv) {
    /* Configure HTTP bridge */
    BridgeConfig config = {
        .transport = BRIDGE_TRANSPORT_HTTP,
        .http_host = "127.0.0.1",
        .http_port = 19000,
        .request_timeout = 30000  /* 30 seconds */
    };

    /* Initialize bridge */
    printf("Initializing bridge...\n");
    Bridge* bridge = bridge_init(&config);
    if (!bridge) {
        fprintf(stderr, "Failed to initialize bridge\n");
        return 1;
    }

    /* Health check */
    printf("Health check...\n");
    if (bridge_health_check(bridge)) {
        printf("✓ Bridge is healthy\n\n");
    } else {
        fprintf(stderr, "✗ Bridge health check failed: %s\n",
            bridge_get_error(bridge));
        bridge_shutdown(bridge);
        return 1;
    }

    /* List tools */
    printf("Listing available tools...\n");
    char* tools = bridge_tools_list(bridge);
    if (tools) {
        printf("Tools: %s\n\n", tools);
        free(tools);
    }

    /* Send chat message */
    printf("Sending chat message...\n");
    char* chat_response = bridge_chat_message(bridge, "Hello from C!");
    if (chat_response) {
        printf("Response: %s\n\n", chat_response);
        free(chat_response);
    }

    /* Run agent task */
    printf("Running agent task...\n");
    char* agent_result = bridge_agent_run(
        bridge,
        "List all files in the current directory"
    );

    if (agent_result) {
        printf("Agent result: %s\n\n", agent_result);
        free(agent_result);
    } else {
        fprintf(stderr, "Agent failed: %s\n", bridge_get_error(bridge));
    }

    /* Execute tool */
    printf("Executing tool...\n");
    char* tool_result = bridge_tool_execute(
        bridge,
        "filesystem.read",
        "{\"path\":\"README.md\"}"
    );

    if (tool_result) {
        printf("Tool result: %s\n\n", tool_result);
        free(tool_result);
    }

    /* Cleanup */
    bridge_shutdown(bridge);
    printf("Bridge shutdown complete\n");

    return 0;
}
