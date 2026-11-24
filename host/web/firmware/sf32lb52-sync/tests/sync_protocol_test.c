#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "velapet_history.h"
#include "velapet_sync_protocol.h"
#include "velapet_sync_session.h"

static void test_frame(void)
{
    const uint8_t body[] = {1U, 2U, 3U, 4U};
    uint8_t frame[64];
    size_t length = 0U;
    vp_frame_header_t input = {VP_SYNC_VERSION, VP_MSG_HISTORY_RECORDS, 3U, 7U, 0U, 1U, 4U, 12U};
    vp_frame_header_t output;
    const uint8_t *decoded = NULL;

    assert(vp_frame_encode(&input, body, frame, sizeof(frame), &length) == 0);
    assert(vp_frame_decode(frame, length, &output, &decoded) == 0);
    assert(output.cursor == 12U);
    assert(memcmp(decoded, body, sizeof(body)) == 0);
    frame[VP_SYNC_HEADER_SIZE] ^= 1U;
    assert(vp_frame_decode(frame, length, &output, &decoded) == -4);
}

static void test_history_ack(void)
{
    vp_history_t history;
    vp_motion_record_t record = {1U, 100U, 20261118U, 480, 20U, 1U, 10000U, VP_RECORD_SOURCE_TEST_INJECTED, 0U};
    vp_motion_record_t output[2];
    uint32_t cursor;
    uint32_t next;

    vp_history_init(&history, 0U);
    assert(vp_history_append(&history, &record, &cursor) == 0 && cursor == 0U);
    record.record_id = 2U;
    assert(vp_history_append(&history, &record, &cursor) == 0 && cursor == 1U);
    assert(vp_history_read(&history, 0U, output, 1U, &next) == 1U && next == 1U);
    /* A BLE disconnect does not mutate the queue. */
    assert(history.count == 2U);
    assert(vp_history_ack(&history, 1U) == 0 && history.count == 1U);
    assert(vp_history_read(&history, 1U, output, 2U, &next) == 1U && output[0].record_id == 2U);
    assert(vp_history_ack(&history, 2U) == 0 && history.count == 0U);
    assert(vp_history_ack(&history, 1U) == -1);
}

static void test_stream_waits_for_exact_ack(void)
{
    vp_history_t history;
    vp_sync_session_t session;
    vp_motion_record_t input = {11U, 100U, 20261119U, 480, 30U, 1U, 10000U, VP_RECORD_SOURCE_TEST_INJECTED, 0U};
    vp_motion_record_t output[1];
    uint32_t cursor;
    uint32_t next;
    size_t count;

    vp_history_init(&history, 100U);
    assert(vp_history_append(&history, &input, &cursor) == 0 && cursor == 100U);
    input.record_id = 12U;
    assert(vp_history_append(&history, &input, &cursor) == 0 && cursor == 101U);
    assert(vp_sync_session_begin(&session, &history, 100U, 1U) == 0);
    assert(vp_sync_session_next(&session, output, 1U, &count, &next) == 0);
    assert(count == 1U && next == 101U && session.state == VP_SYNC_WAIT_ACK);
    assert(vp_sync_session_next(&session, output, 1U, &count, &next) == -3);
    assert(vp_sync_session_ack(&session, 102U) == -2);
    assert(history.count == 2U);
    assert(vp_sync_session_ack(&session, 101U) == 0 && history.count == 1U);
    assert(vp_sync_session_next(&session, output, 1U, &count, &next) == 0 && next == 102U);
    vp_sync_session_disconnect(&session);
    assert(history.count == 1U); /* Disconnect never releases the unacknowledged batch. */
}

int main(void)
{
    test_frame();
    test_history_ack();
    test_stream_waits_for_exact_ack();
    puts("VELAPET_SYNC_PROTOCOL_TEST result=PASS cases=3");
    return 0;
}
