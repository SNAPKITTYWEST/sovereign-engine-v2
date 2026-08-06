#ifndef SOVEREIGN_PROTOCOL_H
#define SOVEREIGN_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define PROTOCOL_VERSION 1
#define MAX_MESSAGE_SIZE (4 * 1024 * 1024)

typedef enum MsgType {
    MSG_HANDSHAKE           = 0x01,
    MSG_CONVERSATION_CREATE = 0x10,
    MSG_CONVERSATION_MSG    = 0x11,
    MSG_CONVERSATION_CANCEL = 0x12,
    MSG_STREAM_STARTED      = 0x20,
    MSG_STREAM_DELTA        = 0x21,
    MSG_STREAM_COMPLETED    = 0x22,
    MSG_TOOL_STARTED        = 0x30,
    MSG_TOOL_COMPLETED      = 0x31,
    MSG_APPROVAL_REQUESTED  = 0x40,
    MSG_APPROVAL_RESOLVED   = 0x41,
    MSG_AGENT_STATE         = 0x50,
    MSG_ERROR               = 0xFF,
} MsgType;

#pragma pack(push, 1)
typedef struct FrameHeader {
    uint8_t  protocol_version;
    uint8_t  message_type;
    uint32_t request_id;
    uint32_t workspace_id;
    uint32_t conversation_id;
    uint32_t payload_length;
    uint32_t checksum;
} FrameHeader;
#pragma pack(pop)

#define FRAME_HEADER_SIZE sizeof(FrameHeader)

uint32_t protocol_checksum(const uint8_t *data, size_t len);

#endif /* SOVEREIGN_PROTOCOL_H */
