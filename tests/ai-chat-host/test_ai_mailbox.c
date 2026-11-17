#include <assert.h>
#include <string.h>
#include <rtthread.h>
#include "velapet_ai_chat.h"

static int depth;
void rt_enter_critical(void) { ++depth; }
void rt_exit_critical(void) { assert(depth > 0); --depth; }

#ifdef VELAPET_UI_AI_MOCK
static uint32_t tick;
uint32_t lv_tick_get(void) { return tick; }
#else
static velapet_snapshot_t snapshot = {.level = 8};
static int link_up = 1;
static int exchange_status;
static int replace_inflight;
static unsigned calls;
static uint32_t old_id;
static ui_ai_kind_t expected_kind;
const velapet_snapshot_t *velapet_service_snapshot(void) { return &snapshot; }
rt_thread_t rt_thread_create(const char *name, void (*entry)(void *), void *arg,
                             unsigned stack, unsigned priority, unsigned tick)
{
    (void)entry; (void)arg; (void)stack; (void)priority; (void)tick;
    assert(strcmp(name, "vp_chat") == 0);
    return &link_up;
}
int rt_thread_startup(rt_thread_t worker) { assert(worker); return RT_EOK; }
int rt_thread_delete(rt_thread_t worker) { assert(worker); return RT_EOK; }
void rt_thread_mdelay(int delay) { (void)delay; }
static int ready(void) { assert(depth == 0); return link_up; }
static int exchange(const ui_ai_request_t *req, const velapet_snapshot_t *ctx,
                    ui_ai_result_t *res, uint32_t timeout)
{
    assert(depth == 0);
    assert(timeout == VP_NET_CHAT_TIMEOUT_MS);
    assert(ctx->level == 8);
    assert(req->kind == expected_kind && req->max_chars == 50U);
    if (req->kind == UI_AI_KIND_CUSTOM)
        assert(strcmp(req->text, "Custom hello") == 0);
    ++calls;
    old_id = req->request_id;
    if (replace_inflight)
    {
        ui_ai_cancel_pending();
        assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_OK);
    }
    res->request_id = 0xffffffffU; /* An upstream ID must not leak into UI. */
    res->source = req->kind == UI_AI_KIND_CUSTOM ? UI_AI_SOURCE_CLOUD : UI_AI_SOURCE_LOCAL_FALLBACK;
    memcpy(res->reply, "\xe4\xbd\xa0\xe5\xa5\xbd", 7);
    return exchange_status;
}
#endif

int main(void)
{
    ui_ai_result_t reply;
#ifdef VELAPET_UI_AI_MOCK
    assert(ui_ai_mode() == 1);
    for (int kind = UI_AI_KIND_GREETING; kind <= UI_AI_KIND_CUSTOM; ++kind)
    {
        assert(ui_ai_submit((ui_ai_kind_t)kind, "input") == UI_AI_SUBMIT_OK);
        assert(ui_ai_submit(UI_AI_KIND_TASK, NULL) == UI_AI_SUBMIT_BUSY);
        assert(!ui_ai_poll_result(&reply));
        tick += 1200;
        assert(ui_ai_poll_result(&reply) && reply.reply[0]);
    }
    assert(ui_ai_submit(UI_AI_KIND_TASK, NULL) == UI_AI_SUBMIT_OK);
    ui_ai_cancel_pending();
    tick += 1200;
    assert(!ui_ai_poll_result(&reply));
#else
    const vp_net_chat_adapter_t adapter = {ready, exchange};
    assert(ui_ai_submit(UI_AI_KIND_GREETING, NULL) == UI_AI_SUBMIT_OFFLINE);
    assert(velapet_ai_chat_init(&adapter) == 0);
    assert(ui_ai_mode() == 2);
    for (int kind = UI_AI_KIND_GREETING; kind <= UI_AI_KIND_CUSTOM; ++kind)
    {
        expected_kind = (ui_ai_kind_t)kind;
        assert(ui_ai_submit(expected_kind, "Custom hello") == UI_AI_SUBMIT_OK);
        snapshot.level = 9; /* Worker must use the submitted copy. */
        assert(ui_ai_submit(UI_AI_KIND_TASK, NULL) == UI_AI_SUBMIT_BUSY);
        assert(velapet_ai_chat_work_once());
        snapshot.level = 8;
        assert(ui_ai_submit(UI_AI_KIND_TASK, NULL) == UI_AI_SUBMIT_BUSY);
        assert(ui_ai_poll_result(&reply));
        assert(reply.request_id == old_id && reply.reply[0]);
        assert(reply.source == (kind == UI_AI_KIND_CUSTOM ?
              UI_AI_SOURCE_CLOUD : UI_AI_SOURCE_LOCAL_FALLBACK));
    }
    expected_kind = UI_AI_KIND_TASK;
    assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_OK);
    replace_inflight = 1;
    assert(velapet_ai_chat_work_once());
    replace_inflight = 0;
    assert(!ui_ai_poll_result(&reply)); /* Late result was discarded. */
    assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_BUSY);
    exchange_status = VP_NET_CHAT_REPLY_TIMEOUT;
    assert(velapet_ai_chat_work_once());
    assert(ui_ai_poll_result(&reply));
    assert(reply.source == UI_AI_SOURCE_ERROR && reply.error_code == VP_NET_CHAT_REPLY_TIMEOUT);
    exchange_status = 0;
    assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_OK);
    assert(velapet_ai_chat_work_once());
    assert(old_id != reply.request_id);
    ui_ai_cancel_pending(); /* Done is queued, but page was closed. */
    assert(!ui_ai_poll_result(&reply));
    assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_OK);
    link_up = 0;
    assert(velapet_ai_chat_work_once());
    assert(ui_ai_poll_result(&reply));
    assert(reply.source == UI_AI_SOURCE_ERROR && reply.error_code == VP_NET_CHAT_REPLY_OFFLINE);
    assert(ui_ai_submit(expected_kind, NULL) == UI_AI_SUBMIT_OFFLINE);
    assert(calls == 8U);
#endif
    assert(depth == 0);
    return 0;
}
