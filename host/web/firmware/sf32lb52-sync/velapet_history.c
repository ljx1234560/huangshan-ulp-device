#include "velapet_history.h"

#include <string.h>

void vp_history_init(vp_history_t *history, uint32_t restored_ack_cursor)
{
    if (history == NULL)
    {
        return;
    }
    memset(history, 0, sizeof(*history));
    history->next_cursor = restored_ack_cursor;
    history->acknowledged_cursor = restored_ack_cursor;
}

int vp_history_append(vp_history_t *history, const vp_motion_record_t *record, uint32_t *cursor)
{
    uint16_t index;

    if (history == NULL || record == NULL || cursor == NULL)
    {
        return -1;
    }
    if (history->count >= VP_HISTORY_CAPACITY)
    {
        return -2; /* Never overwrite an unacknowledged record. */
    }
    index = (uint16_t)((history->head + history->count) % VP_HISTORY_CAPACITY);
    history->records[index] = *record;
    history->cursors[index] = history->next_cursor;
    *cursor = history->next_cursor;
    ++history->next_cursor;
    ++history->count;
    return 0;
}

size_t vp_history_read(const vp_history_t *history,
                       uint32_t cursor,
                       vp_motion_record_t *output,
                       size_t capacity,
                       uint32_t *next_cursor)
{
    size_t copied = 0U;
    uint16_t offset;

    if (history == NULL || output == NULL || next_cursor == NULL)
    {
        return 0U;
    }
    *next_cursor = cursor;
    for (offset = 0U; offset < history->count && copied < capacity; ++offset)
    {
        uint16_t index = (uint16_t)((history->head + offset) % VP_HISTORY_CAPACITY);
        if (history->cursors[index] < cursor)
        {
            continue;
        }
        output[copied++] = history->records[index];
        *next_cursor = history->cursors[index] + 1U;
    }
    return copied;
}

int vp_history_ack(vp_history_t *history, uint32_t next_cursor)
{
    if (history == NULL || next_cursor < history->acknowledged_cursor || next_cursor > history->next_cursor)
    {
        return -1;
    }
    while (history->count > 0U && history->cursors[history->head] < next_cursor)
    {
        history->head = (uint16_t)((history->head + 1U) % VP_HISTORY_CAPACITY);
        --history->count;
    }
    history->acknowledged_cursor = next_cursor;
    return 0;
}
