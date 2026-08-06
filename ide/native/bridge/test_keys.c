/*
 * API Key Management Test
 * Demonstrates setting keys via bridge
 */

#include "bridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void print_status(Bridge* bridge) {
    printf("\n=== API Key Status ===\n");
    char* status = bridge_get_key_status(bridge);
    if (status) {
        printf("%s\n", status);
        free(status);
    } else {
        printf("Failed to get status\n");
    }
}

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
    printf("OK: Bridge healthy\n");

    /* Get initial status */
    print_status(bridge);

    /* Simulate UI - set OpenRouter key */
    printf("\n--- Setting OpenRouter Key ---\n");
    printf("(In real UI, user would paste their key here)\n");

    const char* demo_key = "sk-or-v1-demo-key-12345";  /* Demo key */
    char* set_result = bridge_set_key(bridge, "openrouter", demo_key);
    if (set_result) {
        printf("Result: %s\n", set_result);
        free(set_result);
    }

    /* Get updated status */
    print_status(bridge);

    /* Test chat with key set */
    printf("\n--- Testing Chat (should use OpenRouter) ---\n");
    char* chat_reply = bridge_chat_message(bridge, "Hello! Test message.");
    if (chat_reply) {
        printf("Reply: %s\n", chat_reply);
        free(chat_reply);
    } else {
        printf("Chat failed (expected - demo key not real)\n");
    }

    /* Delete key */
    printf("\n--- Deleting OpenRouter Key ---\n");
    char* delete_result = bridge_delete_key(bridge, "openrouter");
    if (delete_result) {
        printf("Result: %s\n", delete_result);
        free(delete_result);
    }

    /* Final status */
    print_status(bridge);

    /* Cleanup */
    bridge_shutdown(bridge);
    printf("\nDone\n");

    return 0;
}
