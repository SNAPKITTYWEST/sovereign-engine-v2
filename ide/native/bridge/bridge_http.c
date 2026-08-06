/*
 * Bridge HTTP Client Implementation
 * Uses WinHTTP for HTTP communication with Python engine
 */

#include "bridge.h"
#include <windows.h>
#include <winhttp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "winhttp.lib")

/* Bridge internal structure */
struct Bridge {
    BridgeConfig config;
    HINTERNET hSession;
    HINTERNET hConnect;
    char error_msg[512];
    bool ready;
};

/* Helper: validate input length for JSON */
static bool validate_input_length(Bridge* bridge, const char* input, const char* field_name) {
    size_t len = strlen(input);
    if (len > 4000) {  /* Max input: 4KB minus JSON overhead */
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "%s too long: %lu chars (max 4000)", field_name, (unsigned long)len);
        return false;
    }
    return true;
}

/* Helper: escape JSON special characters */
static char* json_escape(const char* str) {
    if (!str) return NULL;

    size_t len = strlen(str);
    /* Worst case: every char needs escaping (doubled length) */
    char* escaped = (char*)malloc(len * 2 + 1);
    if (!escaped) return NULL;

    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        switch (str[i]) {
            case '"':
            case '\\':
                escaped[j++] = '\\';
                escaped[j++] = str[i];
                break;
            case '\n':
                escaped[j++] = '\\';
                escaped[j++] = 'n';
                break;
            case '\r':
                escaped[j++] = '\\';
                escaped[j++] = 'r';
                break;
            case '\t':
                escaped[j++] = '\\';
                escaped[j++] = 't';
                break;
            default:
                escaped[j++] = str[i];
                break;
        }
    }
    escaped[j] = '\0';
    return escaped;
}

/* Helper: HTTP POST request */
static char* http_post(Bridge* bridge, const char* path, const char* body) {
    if (!bridge || !bridge->hConnect) {
        return NULL;
    }

    /* Convert path to wide string */
    wchar_t wide_path[256];
    MultiByteToWideChar(CP_UTF8, 0, path ? path : "/", -1, wide_path, 256);

    /* Open request */
    HINTERNET hRequest = WinHttpOpenRequest(
        bridge->hConnect,
        L"POST",
        wide_path,
        NULL,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        0
    );

    if (!hRequest) {
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Failed to open HTTP request");
        return NULL;
    }

    /* Set headers */
    LPCWSTR headers = L"Content-Type: application/json\r\n";
    WinHttpAddRequestHeaders(hRequest, headers, -1, WINHTTP_ADDREQ_FLAG_ADD);

    /* Send request */
    DWORD body_len = (DWORD)strlen(body);
    BOOL result = WinHttpSendRequest(
        hRequest,
        WINHTTP_NO_ADDITIONAL_HEADERS,
        0,
        (LPVOID)body,
        body_len,
        body_len,
        0
    );

    if (!result) {
        WinHttpCloseHandle(hRequest);
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Failed to send HTTP request");
        return NULL;
    }

    /* Receive response */
    result = WinHttpReceiveResponse(hRequest, NULL);
    if (!result) {
        WinHttpCloseHandle(hRequest);
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Failed to receive HTTP response");
        return NULL;
    }

    /* Read response body */
    DWORD bytes_available = 0;
    DWORD bytes_read = 0;
    char* response = NULL;
    size_t response_len = 0;

    do {
        bytes_available = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &bytes_available)) {
            break;
        }

        if (bytes_available == 0) {
            break;
        }

        /* Allocate buffer */
        char* buffer = (char*)malloc(bytes_available + 1);
        if (!buffer) break;

        /* Read data */
        if (WinHttpReadData(hRequest, buffer, bytes_available, &bytes_read)) {
            /* Append to response */
            char* new_response = (char*)realloc(response, response_len + bytes_read + 1);
            if (new_response) {
                response = new_response;
                memcpy(response + response_len, buffer, bytes_read);
                response_len += bytes_read;
                response[response_len] = '\0';
            } else {
                /* realloc failed - clean up */
                free(response);
                free(buffer);
                WinHttpCloseHandle(hRequest);
                snprintf(bridge->error_msg, sizeof(bridge->error_msg),
                    "Out of memory during HTTP response");
                return NULL;
            }
        }

        free(buffer);
    } while (bytes_available > 0);

    WinHttpCloseHandle(hRequest);
    return response;
}

/* Helper: HTTP GET request */
static char* http_get(Bridge* bridge, const char* path) {
    if (!bridge || !bridge->hConnect) {
        return NULL;
    }

    /* Convert path to wide string */
    wchar_t wide_path[256];
    MultiByteToWideChar(CP_UTF8, 0, path ? path : "/", -1, wide_path, 256);

    /* Open request */
    HINTERNET hRequest = WinHttpOpenRequest(
        bridge->hConnect,
        L"GET",
        wide_path,
        NULL,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        0
    );

    if (!hRequest) {
        return NULL;
    }

    /* Send request */
    BOOL result = WinHttpSendRequest(
        hRequest,
        WINHTTP_NO_ADDITIONAL_HEADERS,
        0,
        WINHTTP_NO_REQUEST_DATA,
        0,
        0,
        0
    );

    if (!result) {
        WinHttpCloseHandle(hRequest);
        return NULL;
    }

    /* Receive response */
    result = WinHttpReceiveResponse(hRequest, NULL);
    if (!result) {
        WinHttpCloseHandle(hRequest);
        return NULL;
    }

    /* Read response (same as POST) */
    DWORD bytes_available = 0;
    DWORD bytes_read = 0;
    char* response = NULL;
    size_t response_len = 0;

    do {
        bytes_available = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &bytes_available)) {
            break;
        }

        if (bytes_available == 0) {
            break;
        }

        char* buffer = (char*)malloc(bytes_available + 1);
        if (!buffer) {
            free(response);
            break;
        }

        if (WinHttpReadData(hRequest, buffer, bytes_available, &bytes_read)) {
            char* new_response = (char*)realloc(response, response_len + bytes_read + 1);
            if (new_response) {
                response = new_response;
                memcpy(response + response_len, buffer, bytes_read);
                response_len += bytes_read;
                response[response_len] = '\0';
            } else {
                /* realloc failed - clean up */
                free(response);
                free(buffer);
                WinHttpCloseHandle(hRequest);
                return NULL;
            }
        }

        free(buffer);
    } while (bytes_available > 0);

    WinHttpCloseHandle(hRequest);
    return response;
}

/* Public API */

Bridge* bridge_init(const BridgeConfig* config) {
    if (!config) return NULL;

    Bridge* bridge = (Bridge*)calloc(1, sizeof(Bridge));
    if (!bridge) return NULL;

    /* Copy config */
    memcpy(&bridge->config, config, sizeof(BridgeConfig));

    if (config->transport == BRIDGE_TRANSPORT_HTTP) {
        /* Initialize WinHTTP session */
        bridge->hSession = WinHttpOpen(
            L"SovereignIDE/1.0",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS,
            0
        );

        if (!bridge->hSession) {
            snprintf(bridge->error_msg, sizeof(bridge->error_msg),
                "Failed to initialize WinHTTP");
            free(bridge);
            return NULL;
        }

        /* Set timeout */
        DWORD timeout = config->request_timeout ? config->request_timeout : 30000;
        WinHttpSetTimeouts(bridge->hSession, timeout, timeout, timeout, timeout);

        /* Connect to host */
        wchar_t host[256];
        MultiByteToWideChar(CP_UTF8, 0, config->http_host, -1, host, 256);

        bridge->hConnect = WinHttpConnect(
            bridge->hSession,
            host,
            config->http_port,
            0
        );

        if (!bridge->hConnect) {
            snprintf(bridge->error_msg, sizeof(bridge->error_msg),
                "Failed to connect to %s:%d", config->http_host, config->http_port);
            WinHttpCloseHandle(bridge->hSession);
            free(bridge);
            return NULL;
        }

        bridge->ready = true;
    }

    return bridge;
}

void bridge_shutdown(Bridge* bridge) {
    if (!bridge) return;

    if (bridge->hConnect) {
        WinHttpCloseHandle(bridge->hConnect);
    }

    if (bridge->hSession) {
        WinHttpCloseHandle(bridge->hSession);
    }

    free(bridge);
}

bool bridge_is_ready(Bridge* bridge) {
    return bridge && bridge->ready;
}

char* bridge_agent_run(Bridge* bridge, const char* task) {
    if (!bridge || !task) return NULL;

    /* Validate input length */
    if (!validate_input_length(bridge, task, "Task")) {
        return NULL;
    }

    /* Escape JSON special characters */
    char* escaped_task = json_escape(task);
    if (!escaped_task) {
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Out of memory during JSON escaping");
        return NULL;
    }

    /* Build request JSON */
    char request_body[4096];
    snprintf(request_body, sizeof(request_body),
        "{\"task\":\"%s\"}", escaped_task);

    free(escaped_task);

    /* POST to /agent/run */
    return http_post(bridge, "/agent/run", request_body);
}

char* bridge_tool_execute(Bridge* bridge, const char* tool_name, const char* args_json) {
    if (!bridge || !tool_name) return NULL;

    /* Build request */
    char request_body[4096];
    snprintf(request_body, sizeof(request_body),
        "{\"tool\":\"%s\",\"args\":%s}",
        tool_name, args_json ? args_json : "{}");

    return http_post(bridge, "/tool/execute", request_body);
}

char* bridge_tools_list(Bridge* bridge) {
    if (!bridge) return NULL;
    return http_get(bridge, "/tools");
}

char* bridge_chat_message(Bridge* bridge, const char* message) {
    if (!bridge || !message) return NULL;

    /* Validate input length */
    if (!validate_input_length(bridge, message, "Message")) {
        return NULL;
    }

    /* Escape JSON special characters */
    char* escaped_message = json_escape(message);
    if (!escaped_message) {
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Out of memory during JSON escaping");
        return NULL;
    }

    char request_body[4096];
    snprintf(request_body, sizeof(request_body),
        "{\"message\":\"%s\"}", escaped_message);

    free(escaped_message);

    return http_post(bridge, "/chat", request_body);
}

bool bridge_health_check(Bridge* bridge) {
    if (!bridge) return false;

    char* response = http_get(bridge, "/health");
    if (!response) return false;

    /* Check for "ok" in response */
    bool ok = strstr(response, "ok") != NULL;
    free(response);

    return ok;
}

const char* bridge_get_error(Bridge* bridge) {
    return bridge ? bridge->error_msg : "Bridge is NULL";
}

char* bridge_set_key(Bridge* bridge, const char* provider, const char* api_key) {
    if (!bridge || !provider || !api_key) return NULL;

    /* Validate input lengths */
    if (!validate_input_length(bridge, provider, "Provider")) {
        return NULL;
    }
    if (!validate_input_length(bridge, api_key, "API key")) {
        return NULL;
    }

    /* Escape JSON special characters */
    char* escaped_provider = json_escape(provider);
    char* escaped_key = json_escape(api_key);

    if (!escaped_provider || !escaped_key) {
        free(escaped_provider);
        free(escaped_key);
        snprintf(bridge->error_msg, sizeof(bridge->error_msg),
            "Out of memory during JSON escaping");
        return NULL;
    }

    /* Build request JSON */
    char request_body[4096];
    snprintf(request_body, sizeof(request_body),
        "{\"provider\":\"%s\",\"key\":\"%s\"}",
        escaped_provider, escaped_key);

    free(escaped_provider);
    free(escaped_key);

    return http_post(bridge, "/keys/set", request_body);
}

char* bridge_get_key_status(Bridge* bridge) {
    if (!bridge) return NULL;
    return http_get(bridge, "/keys/status");
}

char* bridge_delete_key(Bridge* bridge, const char* provider) {
    if (!bridge || !provider) return NULL;

    /* Build path */
    char path[256];
    snprintf(path, sizeof(path), "/keys/%s", provider);

    /* Need to implement DELETE - for now use POST with _method */
    char request_body[256];
    snprintf(request_body, sizeof(request_body), "{\"_method\":\"DELETE\"}");

    return http_post(bridge, path, request_body);
}
