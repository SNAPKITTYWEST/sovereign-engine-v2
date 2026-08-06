/*
 * Tool Execution Test
 * Tests filesystem and code tools
 */

#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv) {
    /* Configure bridge */
    BridgeConfig config = {
        .transport = BRIDGE_TRANSPORT_HTTP,
        .http_host = "127.0.0.1",
        .http_port = 19000,
        .request_timeout = 30000
    };

    /* Initialize */
    printf("Initializing bridge...\n");
    Bridge* bridge = bridge_init(&config);
    if (!bridge) {
        fprintf(stderr, "Failed to initialize bridge\n");
        return 1;
    }

    /* Health check */
    if (!bridge_health_check(bridge)) {
        fprintf(stderr, "Bridge not healthy\n");
        bridge_shutdown(bridge);
        return 1;
    }
    printf("OK: Bridge healthy\n\n");

    /* List available tools */
    printf("=== Available Tools ===\n");
    char* tools = bridge_tools_list(bridge);
    if (tools) {
        printf("%s\n\n", tools);
        free(tools);
    }

    /* Test filesystem.read */
    printf("=== Test: filesystem.read ===\n");
    char* read_result = bridge_tool_execute(
        bridge,
        "filesystem.read",
        "{\"path\":\"README.md\"}"
    );
    if (read_result) {
        printf("Result: %s\n\n", read_result);
        free(read_result);
    }

    /* Test filesystem.write */
    printf("=== Test: filesystem.write ===\n");
    char* write_result = bridge_tool_execute(
        bridge,
        "filesystem.write",
        "{\"path\":\"test_output.txt\",\"content\":\"Hello from C!\\nBridge is working.\"}"
    );
    if (write_result) {
        printf("Result: %s\n\n", write_result);
        free(write_result);
    }

    /* Test filesystem.list */
    printf("=== Test: filesystem.list ===\n");
    char* list_result = bridge_tool_execute(
        bridge,
        "filesystem.list",
        "{\"path\":\".\"}"
    );
    if (list_result) {
        printf("Result: %s\n\n", list_result);
        free(list_result);
    }

    /* Cleanup */
    bridge_shutdown(bridge);
    printf("Done\n");

    return 0;
}
