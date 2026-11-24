#include "velapet_sync_protocol.h"

static void write16(uint8_t *dst, uint16_t value)
{
    dst[0] = (uint8_t)(value & 0xffU);
    dst[1] = (uint8_t)(value >> 8U);
}

static void write32(uint8_t *dst, uint32_t value)
{
    write16(dst, (uint16_t)(value & 0xffffU));
    write16(dst + 2, (uint16_t)(value >> 16U));
}

static uint16_t read16(const uint8_t *src)
{
    return (uint16_t)((uint16_t)src[0] | ((uint16_t)src[1] << 8U));
}

static uint32_t read32(const uint8_t *src)
{
    return (uint32_t)read16(src) | ((uint32_t)read16(src + 2) << 16U);
}

uint16_t vp_crc16_ccitt(const uint8_t *data, size_t length)
{
    uint16_t crc = 0xffffU;
    size_t index;
    uint8_t bit;

    if (data == NULL && length != 0U)
    {
        return 0U;
    }
    for (index = 0U; index < length; ++index)
    {
        crc ^= (uint16_t)data[index] << 8U;
        for (bit = 0U; bit < 8U; ++bit)
        {
            crc = (crc & 0x8000U) != 0U
                      ? (uint16_t)((crc << 1U) ^ 0x1021U)
                      : (uint16_t)(crc << 1U);
        }
    }
    return crc;
}

int vp_frame_encode(const vp_frame_header_t *header,
                    const uint8_t *payload,
                    uint8_t *output,
                    size_t capacity,
                    size_t *written)
{
    size_t frame_size;
    uint16_t crc;
    size_t index;

    if (header == NULL || output == NULL || written == NULL ||
        (payload == NULL && header->payload_length != 0U) ||
        header->version != VP_SYNC_VERSION || header->fragment_count == 0U ||
        header->fragment_index >= header->fragment_count)
    {
        return -1;
    }
    frame_size = VP_SYNC_MIN_FRAME_SIZE + header->payload_length;
    if (capacity < frame_size)
    {
        return -2;
    }
    write16(output, VP_SYNC_MAGIC);
    output[2] = header->version;
    output[3] = header->message_type;
    write16(output + 4, header->session_id);
    write16(output + 6, header->sequence);
    output[8] = header->fragment_index;
    output[9] = header->fragment_count;
    write16(output + 10, header->payload_length);
    write32(output + 12, header->cursor);
    for (index = 0U; index < header->payload_length; ++index)
    {
        output[VP_SYNC_HEADER_SIZE + index] = payload[index];
    }
    crc = vp_crc16_ccitt(output, VP_SYNC_HEADER_SIZE + header->payload_length);
    write16(output + VP_SYNC_HEADER_SIZE + header->payload_length, crc);
    *written = frame_size;
    return 0;
}

int vp_frame_decode(const uint8_t *frame,
                    size_t frame_length,
                    vp_frame_header_t *header,
                    const uint8_t **payload)
{
    uint16_t expected;
    uint16_t actual;

    if (frame == NULL || header == NULL || payload == NULL || frame_length < VP_SYNC_MIN_FRAME_SIZE)
    {
        return -1;
    }
    if (read16(frame) != VP_SYNC_MAGIC || frame[2] != VP_SYNC_VERSION)
    {
        return -2;
    }
    header->version = frame[2];
    header->message_type = frame[3];
    header->session_id = read16(frame + 4);
    header->sequence = read16(frame + 6);
    header->fragment_index = frame[8];
    header->fragment_count = frame[9];
    header->payload_length = read16(frame + 10);
    header->cursor = read32(frame + 12);
    if (header->fragment_count == 0U || header->fragment_index >= header->fragment_count ||
        frame_length != VP_SYNC_MIN_FRAME_SIZE + header->payload_length)
    {
        return -3;
    }
    expected = read16(frame + VP_SYNC_HEADER_SIZE + header->payload_length);
    actual = vp_crc16_ccitt(frame, VP_SYNC_HEADER_SIZE + header->payload_length);
    if (expected != actual)
    {
        return -4;
    }
    *payload = frame + VP_SYNC_HEADER_SIZE;
    return 0;
}
