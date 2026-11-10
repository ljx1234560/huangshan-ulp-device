#include "ui_ai_bridge.h"

#include <string.h>

#ifdef __RTTHREAD__
#include <rtthread.h>
#define UI_AI_LOCK() rt_enter_critical()
#define UI_AI_UNLOCK() rt_exit_critical()
#else
#define UI_AI_LOCK()
#define UI_AI_UNLOCK()
#endif

#ifdef VELAPET_UI_AI_MOCK
#include "lvgl.h"
#endif

#define UI_AI_DONE_DEPTH 4U

static ui_ai_request_t s_pending;
static int s_has_pending;
static uint32_t s_inflight_id;
static ui_ai_result_t s_done[UI_AI_DONE_DEPTH];
static uint32_t s_done_head;
static uint32_t s_done_count;
static uint32_t s_next_request_id = 1U;
static int s_service_seen; /* 服务取走过请求 = 已挂接 */

#ifdef VELAPET_UI_AI_MOCK
static uint32_t s_mock_submit_tick;
static ui_ai_kind_t s_mock_kind;
static const char *const s_mock_reply[UI_AI_KIND_COUNT] = {
    "嗨～我是 VelaPet！今天想先做点什么呢？",
    "已经做得很棒啦，休息一下再出发也可以哦！",
    "今天的步数任务快达标啦，饭后散步一圈就够了！",
    "再攒一点经验就能升级，升级会解锁新皮肤哦！",
    "收到啦！等我接入云端大脑之后，回答会更聪明～"
};

static uint32_t mock_elapsed(void)
{
    return (uint32_t)(lv_tick_get() - s_mock_submit_tick);
}
#endif

int ui_ai_mode(void)
{
#ifdef VELAPET_UI_AI_MOCK
    return 1;
#else
    return s_service_seen ? 2 : 0;
#endif
}

ui_ai_submit_t ui_ai_submit(ui_ai_kind_t kind, const char *utf8_text)
{
    ui_ai_submit_t result = UI_AI_SUBMIT_OK;
    size_t bytes;

    if ((int)kind < 0 || kind >= UI_AI_KIND_COUNT)
    {
        return UI_AI_SUBMIT_INVALID;
    }
    if (kind == UI_AI_KIND_CUSTOM &&
        (utf8_text == NULL || utf8_text[0] == '\0'))
    {
        return UI_AI_SUBMIT_INVALID;
    }

    bytes = 0U;
    if (utf8_text != NULL)
    {
        bytes = strlen(utf8_text);
    }
    if (bytes >= UI_AI_TEXT_BYTES)
    {
        return UI_AI_SUBMIT_INVALID; /* 超 240 字（720 字节上限） */
    }

    UI_AI_LOCK();
#ifdef VELAPET_UI_AI_MOCK
    if (s_inflight_id != 0U)
    {
        result = UI_AI_SUBMIT_BUSY;
    }
    else
    {
        s_inflight_id = s_next_request_id++;
        s_mock_kind = kind;
        s_mock_submit_tick = (uint32_t)lv_tick_get();
    }
#else
    if (s_inflight_id != 0U)
    {
        result = UI_AI_SUBMIT_BUSY;
    }
    else
    {
        memset(&s_pending, 0, sizeof(s_pending));
        s_pending.request_id = s_next_request_id;
        s_pending.kind = kind;
        s_pending.max_chars = 50U;
        if (bytes > 0U)
        {
            memcpy(s_pending.text, utf8_text, bytes);
        }
        s_has_pending = 1;
        s_inflight_id = s_next_request_id;
        s_next_request_id++;
    }
#endif
    UI_AI_UNLOCK();
    return result;
}

int ui_ai_poll_result(ui_ai_result_t *out)
{
    int found = 0;

    if (out == NULL)
    {
        return 0;
    }

    UI_AI_LOCK();
    if (s_done_count > 0U)
    {
        *out = s_done[s_done_head];
        s_done_head = (s_done_head + 1U) % UI_AI_DONE_DEPTH;
        s_done_count--;
        found = 1;
    }
    UI_AI_UNLOCK();

#ifdef VELAPET_UI_AI_MOCK
    /* mock：无真实结果时检查演示延时（1.2s）是否到达 */
    if (!found && s_inflight_id != 0U && mock_elapsed() >= 1200U)
    {
        static const char *const s_intent_names[UI_AI_KIND_COUNT] = {
            "greeting", "cheer", "task", "level", "custom"
        };
        memset(out, 0, sizeof(*out));
        out->request_id = s_inflight_id;
        out->source = UI_AI_SOURCE_CLOUD;
        out->error_code = 0;
        strncpy(out->reply, s_mock_reply[s_mock_kind], sizeof(out->reply) - 1U);
        strncpy(out->intent, s_intent_names[s_mock_kind],
                sizeof(out->intent) - 1U);
        found = 1;
    }
    if (found)
    {
        UI_AI_LOCK();
        s_inflight_id = 0U;
        UI_AI_UNLOCK();
    }
#endif
    return found;
}

void ui_ai_cancel_pending(void)
{
    UI_AI_LOCK();
    s_has_pending = 0;
    s_inflight_id = 0U;
    UI_AI_UNLOCK();
}

int ui_ai_bridge_take_request(ui_ai_request_t *out)
{
    int found = 0;

    if (out == NULL)
    {
        return 0;
    }

    UI_AI_LOCK();
    if (s_has_pending)
    {
        *out = s_pending;
        s_has_pending = 0;
        found = 1;
        s_service_seen = 1;
    }
    UI_AI_UNLOCK();
    return found;
}

int ui_ai_bridge_push_result(const ui_ai_result_t *in)
{
    int accepted = 0;

    if (in == NULL)
    {
        return 0;
    }

    UI_AI_LOCK();
    if (s_inflight_id != 0U && in->request_id == s_inflight_id &&
        s_done_count < UI_AI_DONE_DEPTH)
    {
        s_done[(s_done_head + s_done_count) % UI_AI_DONE_DEPTH] = *in;
        s_done_count++;
        s_inflight_id = 0U;
        accepted = 1;
    }
    UI_AI_UNLOCK();
    return accepted;
}
