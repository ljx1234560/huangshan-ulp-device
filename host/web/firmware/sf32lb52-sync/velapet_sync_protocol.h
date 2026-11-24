#ifndef VELAPET_SYNC_PROTOCOL_H
#define VELAPET_SYNC_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define VP_SYNC_MAGIC 0x5056U
#define VP_SYNC_VERSION 1U
#define VP_SYNC_HEADER_SIZE 16U
#define VP_SYNC_CRC_SIZE 2U
#define VP_SYNC_MIN_FRAME_SIZE (VP_SYNC_HEADER_SIZE + VP_SYNC_CRC_SIZE)

typedef enum
{
    VP_MSG_GET_PROTOCOL = 0x01,
    VP_MSG_GET_DEVICE_INFO = 0x02,
    VP_MSG_GET_MOTION_STATUS = 0x03,
    VP_MSG_SYNC_START = 0x10,
    VP_MSG_ACK = 0x11,
    VP_MSG_NACK = 0x12,
    VP_MSG_GET_PET_SNAPSHOT = 0x20,
    VP_MSG_PING = 0x7e,
    VP_MSG_CANCEL = 0x7f,
    VP_MSG_PROTOCOL_INFO = 0x81,
    VP_MSG_DEVICE_INFO = 0x82,
    VP_MSG_MOTION_STATUS = 0x83,
    VP_MSG_HISTORY_RECORDS = 0x90,
    VP_MSG_SYNC_COMPLETE = 0x91,
    VP_MSG_PET_SNAPSHOT = 0xa0,
    VP_MSG_ERROR = 0xe0
} vp_message_type_t;

typedef struct
{
    uint8_t version;
    uint8_t message_type;
    uint16_t session_id;
    uint16_t sequence;
    uint8_t fragment_index;
    uint8_t fragment_count;
    uint16_t payload_length;
    uint32_t cursor;
} vp_frame_header_t;

uint16_t vp_crc16_ccitt(const uint8_t *data, size_t length);

int vp_frame_encode(const vp_frame_header_t *header,
                    const uint8_t *payload,
                    uint8_t *output,
                    size_t capacity,
                    size_t *written);

int vp_frame_decode(const uint8_t *frame,
                    size_t frame_length,
                    vp_frame_header_t *header,
                    const uint8_t **payload);

#endif
