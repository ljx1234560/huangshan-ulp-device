#ifndef VELAPET_SYNC_SESSION_H
#define VELAPET_SYNC_SESSION_H

#include <stddef.h>
#include <stdint.h>

#include "velapet_history.h"

typedef enum
{
    VP_SYNC_IDLE = 0,
    VP_SYNC_STREAMING,
    VP_SYNC_WAIT_ACK,
    VP_SYNC_COMPLETE,
    VP_SYNC_ERROR
} vp_sync_state_t;

typedef struct
{
    vp_history_t *history;
    vp_sync_state_t state;
    uint32_t cursor;
    uint32_t pending_ack_cursor;
    uint16_t max_records;
} vp_sync_session_t;

int vp_sync_session_begin(vp_sync_session_t *session,
                          vp_history_t *history,
                          uint32_t absolute_cursor,
                          uint16_t max_records);

int vp_sync_session_next(vp_sync_session_t *session,
                         vp_motion_record_t *output,
                         size_t capacity,
                         size_t *record_count,
                         uint32_t *next_cursor);

int vp_sync_session_ack(vp_sync_session_t *session, uint32_t absolute_next_cursor);
void vp_sync_session_disconnect(vp_sync_session_t *session);

#endif
