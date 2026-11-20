#ifndef VELAPET_HISTORY_H
#define VELAPET_HISTORY_H

#include <stddef.h>
#include <stdint.h>

#define VP_HISTORY_CAPACITY 128U
#define VP_RECORD_FLAG_TIME_TRUSTED 0x01U

typedef enum
{
    VP_RECORD_SOURCE_HARDWARE = 1,
    VP_RECORD_SOURCE_TEST_INJECTED = 2
} vp_record_source_t;

typedef struct
{
    uint64_t record_id;
    uint32_t occurred_at_epoch_s;
    uint32_t local_date_yyyymmdd;
    int16_t timezone_offset_minutes;
    uint32_t steps;
    uint16_t active_minutes;
    uint16_t goal;
    uint8_t source;
    uint8_t flags;
} vp_motion_record_t;

typedef struct
{
    vp_motion_record_t records[VP_HISTORY_CAPACITY];
    uint32_t cursors[VP_HISTORY_CAPACITY];
    uint16_t head;
    uint16_t count;
    uint32_t next_cursor;
    uint32_t acknowledged_cursor;
} vp_history_t;

void vp_history_init(vp_history_t *history, uint32_t restored_ack_cursor);
int vp_history_append(vp_history_t *history, const vp_motion_record_t *record, uint32_t *cursor);
size_t vp_history_read(const vp_history_t *history,
                       uint32_t cursor,
                       vp_motion_record_t *output,
                       size_t capacity,
                       uint32_t *next_cursor);
int vp_history_ack(vp_history_t *history, uint32_t next_cursor);

#endif
