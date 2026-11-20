#include "velapet_sync_session.h"

int vp_sync_session_begin(vp_sync_session_t *session,
                          vp_history_t *history,
                          uint32_t absolute_cursor,
                          uint16_t max_records)
{
    if (session == NULL || history == NULL || max_records == 0U)
    {
        return -1;
    }
    if (absolute_cursor < history->acknowledged_cursor || absolute_cursor > history->next_cursor)
    {
        return -2;
    }
    session->history = history;
    session->state = VP_SYNC_STREAMING;
    session->cursor = absolute_cursor;
    session->pending_ack_cursor = absolute_cursor;
    session->max_records = max_records;
    return 0;
}

int vp_sync_session_next(vp_sync_session_t *session,
                         vp_motion_record_t *output,
                         size_t capacity,
                         size_t *record_count,
                         uint32_t *next_cursor)
{
    size_t limit;
    size_t count;

    if (session == NULL || output == NULL || record_count == NULL || next_cursor == NULL ||
        session->history == NULL)
    {
        return -1;
    }
    if (session->state == VP_SYNC_WAIT_ACK)
    {
        return -3; /* The next batch is forbidden until the exact ACK arrives. */
    }
    if (session->state != VP_SYNC_STREAMING)
    {
        return -2;
    }
    limit = capacity < session->max_records ? capacity : session->max_records;
    count = vp_history_read(session->history, session->cursor, output, limit, next_cursor);
    *record_count = count;
    if (count == 0U)
    {
        session->state = VP_SYNC_COMPLETE;
        return 0;
    }
    session->pending_ack_cursor = *next_cursor;
    session->state = VP_SYNC_WAIT_ACK;
    return 0;
}

int vp_sync_session_ack(vp_sync_session_t *session, uint32_t absolute_next_cursor)
{
    if (session == NULL || session->history == NULL || session->state != VP_SYNC_WAIT_ACK)
    {
        return -1;
    }
    if (absolute_next_cursor != session->pending_ack_cursor)
    {
        return -2;
    }
    if (vp_history_ack(session->history, absolute_next_cursor) != 0)
    {
        session->state = VP_SYNC_ERROR;
        return -3;
    }
    session->cursor = absolute_next_cursor;
    session->state = VP_SYNC_STREAMING;
    return 0;
}

void vp_sync_session_disconnect(vp_sync_session_t *session)
{
    if (session == NULL)
    {
        return;
    }
    /* The history queue is deliberately untouched. */
    session->history = NULL;
    session->state = VP_SYNC_IDLE;
}
