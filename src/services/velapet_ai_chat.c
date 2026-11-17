#include "velapet_ai_chat.h"

#include <rtthread.h>
#include <string.h>

#ifndef VELAPET_UI_AI_MOCK
static const vp_net_chat_adapter_t *s_adapter;
static uint32_t s_snapshot_id;
static velapet_snapshot_t s_snapshot;

RT_WEAK const vp_net_chat_adapter_t *vp_net_chat_platform(void)
{
    return RT_NULL;
}

int velapet_ai_chat_ready(void)
{
    return s_adapter != RT_NULL && s_adapter->ready();
}

void velapet_ai_chat_capture(uint32_t request_id, const velapet_snapshot_t *context)
{
    s_snapshot = *context;
    s_snapshot_id = request_id;
}

int velapet_ai_chat_work_once(void)
{
    ui_ai_request_t req;
    ui_ai_result_t reply = {0};
    velapet_snapshot_t snapshot;
    uint32_t snapshot_id;
    int status = VP_NET_CHAT_REPLY_OFFLINE;

    if (!ui_ai_bridge_take_request(&req))
        return 0;

    rt_enter_critical();
    snapshot_id = s_snapshot_id;
    snapshot = s_snapshot;
    rt_exit_critical();
    if (snapshot_id != req.request_id)
        return 1; /* Superseded by a newer UI submission. */

    if (velapet_ai_chat_ready())
        status = s_adapter->exchange(&req, &snapshot, &reply, VP_NET_CHAT_TIMEOUT_MS);

    if (status == 0 &&
        ((reply.source != UI_AI_SOURCE_CLOUD && reply.source != UI_AI_SOURCE_LOCAL_FALLBACK) ||
         reply.reply[0] == '\0' || memchr(reply.reply, '\0', sizeof(reply.reply)) == NULL))
        status = VP_NET_CHAT_REPLY_INVALID;

    if (status != 0)
    {
        memset(&reply, 0, sizeof(reply));
        reply.source = UI_AI_SOURCE_ERROR;
        reply.error_code = status;
    }
    /* Only the UI request ID controls delivery. The REST ID is a separate string. */
    reply.request_id = req.request_id;
    (void)ui_ai_bridge_push_result(&reply);
    return 1;
}

static void chat_worker(void *unused)
{
    (void)unused;
    while (1)
    {
        (void)velapet_ai_chat_work_once();
        rt_thread_mdelay(25);
    }
}

int velapet_ai_chat_init(const vp_net_chat_adapter_t *adapter)
{
    rt_thread_t worker;
    if (!adapter || !adapter->ready || !adapter->exchange)
        return 0; /* No link configured; keep the offline UI usable. */
    if (s_adapter)
        return 0;
    worker = rt_thread_create("vp_chat", chat_worker, RT_NULL, 4096, 24, 10);
    if (worker == RT_NULL)
        return -1;
    s_adapter = adapter;
    if (rt_thread_startup(worker) != RT_EOK)
    {
        s_adapter = RT_NULL;
        rt_thread_delete(worker);
        return -1;
    }
    return 0;
}
#else
const vp_net_chat_adapter_t *vp_net_chat_platform(void) { return RT_NULL; }
int velapet_ai_chat_ready(void) { return 0; }
int velapet_ai_chat_init(const vp_net_chat_adapter_t *adapter) { (void)adapter; return 0; }
#endif
