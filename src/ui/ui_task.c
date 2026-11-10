#include "ui_internal.h"

#include <stdio.h>
#include <string.h>

#define TASK_CARD_H 60
#define TASK_GLYPH 34

static lv_obj_t *s_checkin_label;
static lv_obj_t *s_checkin_btn;
static lv_obj_t *s_card[VELAPET_TASK_COUNT];
static lv_obj_t *s_title[VELAPET_TASK_COUNT];
static lv_obj_t *s_progress_text[VELAPET_TASK_COUNT];
static lv_obj_t *s_bar[VELAPET_TASK_COUNT];
static lv_obj_t *s_status[VELAPET_TASK_COUNT];

static void glyph_label(lv_obj_t *parent, velapet_task_type_t type)
{
    static const char *glyphs[VELAPET_TASK_COUNT] = {
        "步", "走", "签", "友"
    };
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *circle = lv_obj_create(parent);
    lv_obj_t *label;
    unsigned index = (unsigned)type;

    lv_obj_remove_style_all(circle);
    lv_obj_set_size(circle, TASK_GLYPH, TASK_GLYPH);
    lv_obj_set_style_radius(circle, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(circle, theme->accent_color, 0);
    lv_obj_set_style_bg_opa(circle, LV_OPA_60, 0);

    label = lv_label_create(circle);
    lv_label_set_text(label,
                      (index < VELAPET_TASK_COUNT) ? glyphs[index] : "?");
    lv_obj_set_style_text_color(label, theme->text_color, 0);
    lv_obj_set_style_text_font(label, ui_font_title(), 0);
    lv_obj_center(label);
}

static void refresh_after_action(void)
{
    ui_check_levelup();
    ui_task_refresh();
}

static void claim_cb(lv_event_t *e)
{
    uintptr_t index = (uintptr_t)lv_event_get_user_data(e);
    int gained;

    if (index >= VELAPET_TASK_COUNT)
    {
        return;
    }
    ui_note_event("TASK_CLAIM");
    gained = velapet_service_claim((velapet_task_type_t)index);
    if (gained > 0)
    {
        char buf[48];
        snprintf(buf, sizeof(buf), "领取成功，+%d 经验", gained);
        ui_show_toast(buf);
    }
    else if (gained == 0)
    {
        ui_show_toast("任务还没完成，还不能领取");
    }
    else
    {
        ui_show_toast("领取失败，稍后再试");
    }
    /* 领取按钮在被重建的状态区内，延迟一拍再刷新 */
    ui_nav_defer(refresh_after_action);
}

static void checkin_cb(lv_event_t *e)
{
    int days;

    (void)e;
    ui_note_event("TASK_CHECKIN");
    days = velapet_service_checkin();
    if (days > 0)
    {
        char buf[48];
        snprintf(buf, sizeof(buf), "签到成功，已连签 %d 天", days);
        ui_show_toast(buf);
    }
    else if (days == 0)
    {
        ui_show_toast("今天已经签过啦");
    }
    else
    {
        ui_show_toast("签到失败，稍后再试");
    }
    ui_nav_defer(refresh_after_action);
}

static void build_status(lv_obj_t *zone, const velapet_task_view_t *task)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *label;

    lv_obj_clean(zone);

    switch (task->status)
    {
    case VELAPET_TASK_COMPLETED:
    {
        uintptr_t index = (uintptr_t)task->type;
        lv_obj_t *btn = ui_create_button(zone, "领取", claim_cb, (void *)index);
        lv_obj_set_size(btn, 64, 34);
        lv_obj_center(btn);
        return;
    }
    case VELAPET_TASK_REWARD_CLAIMED:
        label = lv_label_create(zone);
        lv_label_set_text(label, "已领取");
        lv_obj_set_style_text_color(label, lv_color_hex(0x3BA272), 0);
        break;
    case VELAPET_TASK_IN_PROGRESS:
        label = lv_label_create(zone);
        lv_label_set_text(label, "进行中");
        lv_obj_set_style_text_color(label, theme->primary_color, 0);
        break;
    default:
        label = lv_label_create(zone);
        lv_label_set_text(label, "未开始");
        lv_obj_set_style_text_color(label,
                                    lv_color_hex(0x9A93A8), 0);
        break;
    }
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_obj_center(label);
}

void ui_task_create(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    unsigned index;

    g_ui_root = ui_create_page();
    ui_create_title(g_ui_root, "今日任务", 1);

    /* 连续签到卡 */
    lv_obj_t *checkin = ui_create_card(g_ui_root, LV_PCT(100), TASK_CARD_H);
    lv_obj_set_flex_flow(checkin, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(checkin, LV_FLEX_ALIGN_SPACE_BETWEEN,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    s_checkin_label = lv_label_create(checkin);
    lv_obj_set_style_text_font(s_checkin_label, ui_font_title(), 0);
    lv_obj_set_style_text_color(s_checkin_label, theme->text_color, 0);
    s_checkin_btn = ui_create_button(checkin, "签到", checkin_cb, NULL);
    lv_obj_set_size(s_checkin_btn, 84, 36);

    /* 任务卡 ×4 */
    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        lv_obj_t *card = ui_create_card(g_ui_root, LV_PCT(100), TASK_CARD_H);
        lv_obj_t *col;
        lv_obj_t *row;

        lv_obj_set_flex_flow(card, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(card, LV_FLEX_ALIGN_START,
                              LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(card, 8, 0);

        s_card[index] = card;
        glyph_label(card, (velapet_task_type_t)index);

        col = lv_obj_create(card);
        lv_obj_remove_style_all(col);
        lv_obj_set_flex_grow(col, 1);
        lv_obj_set_height(col, LV_SIZE_CONTENT);
        lv_obj_set_flex_flow(col, LV_FLEX_FLOW_COLUMN);
        lv_obj_set_style_pad_row(col, 4, 0);

        s_title[index] = lv_label_create(col);
        lv_obj_set_style_text_font(s_title[index], ui_font_body(), 0);
        lv_obj_set_style_text_color(s_title[index], theme->text_color, 0);

        row = lv_obj_create(col);
        lv_obj_remove_style_all(row);
        lv_obj_set_width(row, LV_PCT(100));
        lv_obj_set_height(row, 10);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(row, LV_FLEX_ALIGN_START,
                              LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

        s_bar[index] = lv_bar_create(row);
        lv_obj_set_flex_grow(s_bar[index], 1);
        lv_bar_set_range(s_bar[index], 0, 100);
        lv_obj_set_height(s_bar[index], 8);
        lv_obj_set_style_radius(s_bar[index], 6, 0);
        lv_obj_set_style_radius(s_bar[index], 6, LV_PART_INDICATOR);
        lv_obj_set_style_bg_color(s_bar[index], theme->bg_grad_color, 0);
        lv_obj_set_style_bg_color(s_bar[index], theme->accent_color,
                                  LV_PART_INDICATOR);

        s_progress_text[index] = lv_label_create(col);
        lv_obj_set_style_text_font(s_progress_text[index], ui_font_body(), 0);
        lv_obj_set_style_text_color(s_progress_text[index],
                                    lv_color_hex(0x8A8398), 0);

        s_status[index] = lv_obj_create(card);
        lv_obj_remove_style_all(s_status[index]);
        lv_obj_set_size(s_status[index], 68, TASK_CARD_H - 16);
    }

    ui_task_refresh();
}

void ui_task_refresh(void)
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    unsigned index;
    char buf[80];

    if (s_checkin_label == NULL)
    {
        return;
    }

    if (snap == NULL)
    {
        return;
    }

    if (snap->can_checkin != 0U)
    {
        snprintf(buf, sizeof(buf), "连续签到 %lu 天",
                 (unsigned long)snap->consecutive_days);
        lv_label_set_text(s_checkin_label, buf);
        lv_obj_clear_state(s_checkin_btn, LV_STATE_DISABLED);
    }
    else
    {
        snprintf(buf, sizeof(buf), "今日已签到 · 连签 %lu 天",
                 (unsigned long)snap->consecutive_days);
        lv_label_set_text(s_checkin_label, buf);
        lv_obj_add_state(s_checkin_btn, LV_STATE_DISABLED);
    }

    for (index = 0U; index < VELAPET_TASK_COUNT &&
                     index < (unsigned)snap->task_count; ++index)
    {
        const velapet_task_view_t *task = &snap->tasks[index];
        int pct = ui_percent(task->progress, task->target);

        snprintf(buf, sizeof(buf), "%s（+%lu 经验）",
                 task->title, (unsigned long)task->exp_reward);
        lv_label_set_text(s_title[index], buf);

        snprintf(buf, sizeof(buf), "%lu / %lu %s",
                 (unsigned long)task->progress,
                 (unsigned long)task->target, task->unit);
        lv_label_set_text(s_progress_text[index], buf);

        lv_bar_set_value(s_bar[index], pct, LV_ANIM_ON);
        build_status(s_status[index], task);
    }
}

void ui_task_on_destroy(void)
{
    unsigned index;

    s_checkin_label = NULL;
    s_checkin_btn = NULL;
    for (index = 0U; index < VELAPET_TASK_COUNT; ++index)
    {
        s_card[index] = NULL;
        s_title[index] = NULL;
        s_progress_text[index] = NULL;
        s_bar[index] = NULL;
        s_status[index] = NULL;
    }
}
