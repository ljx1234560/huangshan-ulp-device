#include "ui_internal.h"

#include "ui_ai_bridge.h"

#include <stdio.h>
#include <string.h>

#define CHAT_MAX_BUBBLE_W 78 /* LV_PCT */

static lv_obj_t *s_list;
static lv_obj_t *s_mode_label;
static lv_obj_t *s_quick[4];
static lv_obj_t *s_input;
static lv_obj_t *s_send_btn;
static lv_obj_t *s_wait_bubble;
static lv_obj_t *s_wait_label;
static lv_obj_t *s_retry_row;
static lv_timer_t *s_poll_timer;
static uint8_t s_wait_dots;

static ui_ai_kind_t s_last_kind = UI_AI_KIND_GREETING;
static char s_last_text[UI_AI_TEXT_BYTES];
static char s_last_display[96];
static int s_has_last;

static void retry_cb(lv_event_t *e);
static void quick_cb(lv_event_t *e);
static void send_cb(lv_event_t *e);
static void input_focus_cb(lv_event_t *e);
static void keyboard_ready_cb(lv_event_t *e);

static const char *const quick_names[4] = {
    "打招呼", "给我加油", "聊聊任务", "聊聊等级"
};
static const ui_ai_kind_t quick_kinds[4] = {
    UI_AI_KIND_GREETING, UI_AI_KIND_CHEER,
    UI_AI_KIND_TASK, UI_AI_KIND_LEVEL
};
static const char *const offline_lines[UI_AI_KIND_COUNT] = {
    "我在呢～现在联系不上云端，先陪我散散步吧",
    "你今天已经很努力啦！等联网了再让我好好夸夸你",
    "去任务页看看还差多少，完成后记得回来领奖励",
    "快升级啦！联网后我可以帮你规划升级路线",
    "现在联系不上云端，等网络好了再来找我聊天吧"
};

static void set_inputs_enabled(int enabled)
{
    unsigned index;

    for (index = 0U; index < 4U; ++index)
    {
        if (s_quick[index] != NULL)
        {
            if (enabled)
            {
                lv_obj_clear_state(s_quick[index], LV_STATE_DISABLED);
            }
            else
            {
                lv_obj_add_state(s_quick[index], LV_STATE_DISABLED);
            }
        }
    }
    if (s_send_btn != NULL)
    {
        if (enabled)
        {
            lv_obj_clear_state(s_send_btn, LV_STATE_DISABLED);
        }
        else
        {
            lv_obj_add_state(s_send_btn, LV_STATE_DISABLED);
        }
    }
}

static lv_obj_t *add_system_line(const char *text)
{
    lv_obj_t *label = lv_label_create(s_list);

    lv_label_set_text(label, text);
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0x9A93A8), 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_width(label, LV_PCT(100));
    lv_obj_scroll_to_view(label, LV_ANIM_OFF);
    return label;
}

static lv_obj_t *add_bubble(int mine, const char *text)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *row = lv_obj_create(s_list);
    lv_obj_t *bubble = lv_obj_create(row);
    lv_obj_t *label = lv_label_create(bubble);

    lv_obj_remove_style_all(row);
    lv_obj_set_width(row, LV_PCT(100));
    lv_obj_set_height(row, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row, mine ? LV_FLEX_ALIGN_END : LV_FLEX_ALIGN_START,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    lv_obj_set_width(bubble, LV_PCT(CHAT_MAX_BUBBLE_W));
    lv_obj_set_height(bubble, LV_SIZE_CONTENT);
    lv_obj_set_style_radius(bubble, 14, 0);
    lv_obj_set_style_pad_all(bubble, 8, 0);
    if (mine)
    {
        lv_obj_set_style_bg_color(bubble, theme->primary_color, 0);
    }
    else
    {
        lv_obj_set_style_bg_color(bubble, theme->card_color, 0);
        lv_obj_set_style_border_color(bubble, theme->accent_color, 0);
        lv_obj_set_style_border_width(bubble, 1, 0);
    }
    lv_obj_set_style_bg_opa(bubble, LV_OPA_COVER, 0);

    lv_label_set_text(label, (text != NULL) ? text : "");
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_obj_set_style_text_color(label,
                                mine ? lv_color_hex(0xFFFFFF)
                                     : theme->text_color,
                                0);
    lv_obj_set_width(label, LV_PCT(100));
    lv_label_set_long_mode(label, LV_LABEL_LONG_WRAP);

    lv_obj_scroll_to_view(row, LV_ANIM_OFF);
    return row;
}

static void show_waiting(void)
{
    s_wait_bubble = add_bubble(0, "");
    s_wait_label = lv_obj_get_child(s_wait_bubble, 0);
    lv_label_set_text(s_wait_label, "伙伴思考中…");
    s_wait_dots = 0U;
}

static void clear_waiting(void)
{
    if (s_wait_bubble != NULL)
    {
        lv_obj_del(s_wait_bubble);
        s_wait_bubble = NULL;
        s_wait_label = NULL;
    }
}

static void stop_poll_timer(void)
{
    if (s_poll_timer != NULL)
    {
        lv_timer_del(s_poll_timer);
        s_poll_timer = NULL;
    }
}

static void add_retry_line(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *row = lv_obj_create(s_list);
    lv_obj_t *btn;

    lv_obj_remove_style_all(row);
    lv_obj_set_width(row, LV_PCT(100));
    lv_obj_set_height(row, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row, LV_FLEX_ALIGN_END,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    btn = ui_create_button(row, "重试", retry_cb, NULL);
    lv_obj_set_size(btn, 64, 32);
    lv_obj_set_style_bg_color(btn, theme->accent_color, 0);
    lv_obj_scroll_to_view(row, LV_ANIM_OFF);
    s_retry_row = row;
}

static void handle_result(const ui_ai_result_t *res)
{
    char buf[UI_AI_REPLY_BYTES];

    clear_waiting();
    stop_poll_timer();
    set_inputs_enabled(1);

    if (res->source == UI_AI_SOURCE_ERROR)
    {
        add_system_line("连接不上服务器，请稍后再试");
        add_retry_line();
        return;
    }

    snprintf(buf, sizeof(buf), "%s", res->reply);
    ui_text_sanitize(buf, sizeof(buf), ui_font_body());
    add_bubble(0, buf);
    if (res->source == UI_AI_SOURCE_LOCAL_FALLBACK)
    {
        add_system_line("以上为后端离线降级回复");
    }
}

static void poll_cb(lv_timer_t *timer)
{
    ui_ai_result_t res;

    (void)timer;
    while (ui_ai_poll_result(&res))
    {
        if (res.request_id != 0U)
        {
            handle_result(&res);
        }
    }
    if (s_wait_label != NULL)
    {
        static const char *const dots[4] = {
            "伙伴思考中…", "伙伴思考中……", "伙伴思考中………", "伙伴思考中…"
        };
        s_wait_dots = (uint8_t)((s_wait_dots + 1U) % 4U);
        lv_label_set_text(s_wait_label, dots[s_wait_dots]);
    }
}

static void do_send(ui_ai_kind_t kind, const char *text,
                    const char *display_text)
{
    ui_ai_submit_t result = ui_ai_submit(kind, text);

    switch (result)
    {
    case UI_AI_SUBMIT_OK:
        /* 重发成功后移除旧的重试行 */
        if (s_retry_row != NULL)
        {
            lv_obj_del(s_retry_row);
            s_retry_row = NULL;
        }
        add_bubble(1, display_text);
        show_waiting();
        set_inputs_enabled(0);

        s_last_kind = kind;
        snprintf(s_last_text, sizeof(s_last_text), "%s",
                 (text != NULL) ? text : "");
        snprintf(s_last_display, sizeof(s_last_display), "%s", display_text);
        s_has_last = 1;

        stop_poll_timer();
        s_poll_timer = lv_timer_create(poll_cb, 150, NULL);
        break;
    case UI_AI_SUBMIT_BUSY:
        ui_show_toast("伙伴正在思考，请稍等");
        break;
    case UI_AI_SUBMIT_INVALID:
        ui_show_toast("说点什么吧（1~240 字）");
        break;
    case UI_AI_SUBMIT_OFFLINE:
    default:
        add_system_line("AI 服务未接入，当前为本地提示");
        add_bubble(0, offline_lines[(int)kind]);
        break;
    }
}

static void retry_go(void)
{
    if (s_has_last)
    {
        do_send(s_last_kind, s_last_text, s_last_display);
    }
}

static void retry_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("CHAT_RETRY");
    /* 重试行在被删列表里，延迟一拍再重发 */
    ui_nav_defer(retry_go);
}

static void quick_cb(lv_event_t *e)
{
    uintptr_t index = (uintptr_t)lv_event_get_user_data(e);

    if (index >= 4U)
    {
        return;
    }
    ui_note_event("CHAT_QUICK");
    do_send(quick_kinds[index], "", quick_names[index]);
}

static void send_cb(lv_event_t *e)
{
    const char *text;

    (void)e;
    ui_note_event("CHAT_SEND");
    if (s_input == NULL)
    {
        return;
    }
    text = lv_textarea_get_text(s_input);
    if (text == NULL || text[0] == '\0')
    {
        ui_show_toast("说点什么吧");
        return;
    }
    do_send(UI_AI_KIND_CUSTOM, text, text);
    lv_textarea_set_text(s_input, "");
}

static void input_focus_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);
    lv_obj_t *kb = ui_keyboard();

    (void)e;
    if (code == LV_EVENT_FOCUSED)
    {
        lv_obj_clear_flag(kb, LV_OBJ_FLAG_HIDDEN);
    }
    else if (code == LV_EVENT_DEFOCUSED)
    {
        lv_obj_add_flag(kb, LV_OBJ_FLAG_HIDDEN);
    }
}

static void keyboard_ready_cb(lv_event_t *e)
{
    lv_event_code_t code = lv_event_get_code(e);

    if (code == LV_EVENT_READY || code == LV_EVENT_CANCEL)
    {
        lv_obj_add_flag(ui_keyboard(), LV_OBJ_FLAG_HIDDEN);
        if (s_input != NULL)
        {
            lv_obj_clear_state(s_input, LV_STATE_FOCUSED);
        }
        if (code == LV_EVENT_READY)
        {
            send_cb(e);
        }
    }
}

void ui_chat_create(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    unsigned index;
    int mode = ui_ai_mode();

    g_ui_root = ui_create_page();
    ui_create_title(g_ui_root, "AI 伙伴", 1);

    s_mode_label = lv_label_create(g_ui_root);
    if (mode == 1)
    {
        lv_label_set_text(s_mode_label, "演示模式：回复为本地模拟");
    }
    else if (mode == 2)
    {
        lv_label_set_text(s_mode_label, "已接入 AI 服务");
    }
    else
    {
        lv_label_set_text(s_mode_label, "AI 服务未接入（提交后为本地提示）");
    }
    lv_obj_set_style_text_font(s_mode_label, ui_font_body(), 0);
    lv_obj_set_style_text_color(s_mode_label, lv_color_hex(0x9A93A8), 0);

    s_list = lv_obj_create(g_ui_root);
    lv_obj_remove_style_all(s_list);
    lv_obj_set_size(s_list, LV_PCT(100), 268);
    lv_obj_set_flex_flow(s_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(s_list, LV_FLEX_ALIGN_START,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_row(s_list, 8, 0);
    lv_obj_add_flag(s_list, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_scroll_dir(s_list, LV_DIR_VER);

    {
        lv_obj_t *row = lv_obj_create(g_ui_root);
        lv_obj_remove_style_all(row);
        lv_obj_set_size(row, LV_PCT(100), 38);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_style_pad_column(row, 6, 0);
        for (index = 0U; index < 4U; ++index)
        {
            s_quick[index] = ui_create_button(row, quick_names[index],
                                              quick_cb, (void *)(uintptr_t)index);
            lv_obj_set_size(s_quick[index], 84, 34);
            lv_obj_set_style_text_font(lv_obj_get_child(s_quick[index], 0),
                                       ui_font_body(), 0);
        }
    }

    {
        lv_obj_t *row = lv_obj_create(g_ui_root);
        lv_obj_remove_style_all(row);
        lv_obj_set_size(row, LV_PCT(100), 40);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_style_pad_column(row, 6, 0);

        s_input = lv_textarea_create(row);
        lv_obj_set_flex_grow(s_input, 1);
        lv_obj_set_height(s_input, 40);
        lv_textarea_set_one_line(s_input, 1);
        lv_textarea_set_max_length(s_input, 240);
        lv_textarea_set_placeholder_text(s_input, "想聊点什么…");
        lv_obj_set_style_text_font(s_input, ui_font_body(), 0);
        lv_obj_set_style_border_color(s_input, theme->accent_color, 0);
        lv_obj_set_style_radius(s_input, 12, 0);
        lv_obj_add_event_cb(s_input, input_focus_cb, LV_EVENT_ALL, NULL);

        s_send_btn = ui_create_button(row, "发送", send_cb, NULL);
        lv_obj_set_size(s_send_btn, 64, 40);
        lv_obj_set_style_text_font(lv_obj_get_child(s_send_btn, 0),
                                   ui_font_body(), 0);
    }

    /* 虚拟键盘：共享实例在顶层，绑定本页输入框 */
    {
        lv_obj_t *kb = ui_keyboard();
        lv_keyboard_set_textarea(kb, s_input);
        lv_obj_add_event_cb(kb, keyboard_ready_cb, LV_EVENT_READY, NULL);
        lv_obj_add_event_cb(kb, keyboard_ready_cb, LV_EVENT_CANCEL, NULL);
    }

    add_system_line("点下面的快捷消息，或输入文字聊天");
}

void ui_chat_on_destroy(void)
{
    stop_poll_timer();
    lv_obj_add_flag(ui_keyboard(), LV_OBJ_FLAG_HIDDEN);
    s_wait_bubble = NULL;
    s_wait_label = NULL;
    s_retry_row = NULL;
    s_list = NULL;
    s_mode_label = NULL;
    s_input = NULL;
    s_send_btn = NULL;
    {
        unsigned index;
        for (index = 0U; index < 4U; ++index)
        {
            s_quick[index] = NULL;
        }
    }
    ui_ai_cancel_pending();
}
