#include "ui_internal.h"

#include <stdio.h>
#include <string.h>

static lv_obj_t *s_name;
static lv_obj_t *s_level;
static lv_obj_t *s_exp_text;
static lv_obj_t *s_exp_bar;
static lv_obj_t *s_today_chip;
static lv_obj_t *s_steps_chip;
static lv_obj_t *s_checkin_chip;
static lv_obj_t *s_pet_avatar;

static void task_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("HOME->任务");
    ui_nav_defer(velapet_ui_show_task);
}

static void chat_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("HOME->AI");
    ui_nav_defer(velapet_ui_show_chat);
}

static void image_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("HOME->形象");
    ui_nav_defer(velapet_ui_show_pet_image);
}

static void skin_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("HOME->皮肤");
    ui_nav_defer(velapet_ui_show_skin);
}

/* 宠物子树点击事件冒泡到舞台，统一由 tap 判别器处理（规格 A1/A2）。 */
static void enable_event_bubble(lv_obj_t *obj)
{
    int32_t i;

    lv_obj_add_flag(obj, LV_OBJ_FLAG_EVENT_BUBBLE);
    for (i = 0; i < lv_obj_get_child_cnt(obj); i++)
    {
        enable_event_bubble(lv_obj_get_child(obj, i));
    }
}

static void pet_single_cb(lv_obj_t *obj)
{
    ui_note_event("PET_TAP1");
    ui_anim_happy(obj);
}

static void pet_double_cb(lv_obj_t *obj)
{
    ui_note_event("PET_TAP2");
    ui_anim_dance(obj);
}

static const char *skin_display_name(const char *skin)
{
    return ui_skin_display_name(skin);
}

void ui_home_create(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();

    g_ui_root = ui_create_page();
    ui_create_title(g_ui_root, "VelaPet", 0);

    /* 宠物舞台：优先整帧 JPG 场景图（VELAPET_UI_SKIN_IMAGES=1），否则几何替身 */
    lv_obj_t *hero = lv_obj_create(g_ui_root);
    lv_obj_remove_style_all(hero);
    lv_obj_set_size(hero, LV_PCT(100), 186);
    lv_obj_t *stage = lv_obj_create(hero);
    lv_obj_remove_style_all(stage);
    lv_obj_set_size(stage, 220, 176);
    lv_obj_clear_flag(stage, LV_OBJ_FLAG_SCROLLABLE);
    {
        const velapet_snapshot_t *snap = velapet_service_snapshot();
        int skin_index = (snap != NULL)
                             ? ui_skin_image_index_of(snap->current_skin) : -1;
        const lv_img_dsc_t *full =
            (skin_index >= 0) ? ui_skin_image_full((uint8_t)skin_index) : NULL;

        if (full != NULL)
        {
            s_pet_avatar = lv_img_create(stage);
            lv_img_set_src(s_pet_avatar, full);
        }
        else
        {
            s_pet_avatar = ui_create_pet_avatar(stage, 220, 176);
        }
    }
    lv_obj_center(s_pet_avatar);
    lv_obj_center(stage);
    /* A1/A2：单击开心跳、双击跳舞；A4：待机呼吸。 */
    enable_event_bubble(stage);
    ui_anim_bind_tap(stage, pet_single_cb, pet_double_cb);
    ui_anim_breathe(s_pet_avatar);

    lv_obj_t *info = lv_obj_create(g_ui_root);
    lv_obj_remove_style_all(info);
    lv_obj_set_size(info, LV_PCT(100), 76);
    lv_obj_set_flex_flow(info, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(info, LV_FLEX_ALIGN_CENTER,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    s_name = lv_label_create(info);
    ui_style_label(s_name, theme->text_color);
    lv_obj_set_style_text_font(s_name, ui_font_title(), 0);

    s_level = lv_label_create(info);
    ui_style_label(s_level, theme->text_color);

    s_exp_text = lv_label_create(info);
    ui_style_label(s_exp_text, theme->text_color);

    s_exp_bar = ui_create_exp_bar(info, 0);

    lv_obj_t *stats = lv_obj_create(g_ui_root);
    lv_obj_remove_style_all(stats);
    lv_obj_set_size(stats, LV_PCT(98), 56);
    lv_obj_set_flex_flow(stats, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(stats, LV_FLEX_ALIGN_SPACE_EVENLY,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    s_today_chip = ui_create_chip(stats, "今日", "0%");
    s_steps_chip = ui_create_chip(stats, "步数", "0");
    s_checkin_chip = ui_create_chip(stats, "连签", "0 天");

    lv_obj_t *grid = lv_obj_create(g_ui_root);
    lv_obj_remove_style_all(grid);
    lv_obj_set_size(grid, LV_PCT(98), 46);
    lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_SPACE_EVENLY,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    ui_create_button(grid, "任务", task_cb, NULL);
    ui_create_button(grid, "AI", chat_cb, NULL);
    ui_create_button(grid, "形象", image_cb, NULL);
    ui_create_button(grid, "皮肤", skin_cb, NULL);

    ui_home_refresh();
}

void ui_home_refresh(void)
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    char buf[96];

    if (s_name == NULL || s_level == NULL || s_exp_text == NULL ||
        s_exp_bar == NULL)
    {
        return;
    }

    if (snap == NULL)
    {
        lv_label_set_text(s_name, "VelaPet");
        lv_label_set_text(s_level, "等级 1");
        lv_label_set_text(s_exp_text, "经验 0 / 100");
        lv_bar_set_value(s_exp_bar, 0, LV_ANIM_OFF);
        return;
    }

    lv_label_set_text(s_name, (snap->name[0] != '\0') ? snap->name : "VelaPet");

    snprintf(buf, sizeof(buf), "等级 %u · %s",
             (unsigned)snap->level, skin_display_name(snap->current_skin));
    lv_label_set_text(s_level, buf);

    snprintf(buf, sizeof(buf), "经验 %lu / %lu",
             (unsigned long)snap->exp, (unsigned long)snap->exp_to_next);
    lv_label_set_text(s_exp_text, buf);
    lv_bar_set_value(s_exp_bar, snap->exp_percent, LV_ANIM_ON);

    snprintf(buf, sizeof(buf), "今日\n%u%%",
             (unsigned)snap->daily_percent);
    lv_label_set_text(lv_obj_get_child(s_today_chip, 0), buf);

    snprintf(buf, sizeof(buf), "步数\n%llu",
             (unsigned long long)snap->total_steps);
    lv_label_set_text(lv_obj_get_child(s_steps_chip, 0), buf);

    snprintf(buf, sizeof(buf), "连签\n%lu 天",
             (unsigned long)snap->consecutive_days);
    lv_label_set_text(lv_obj_get_child(s_checkin_chip, 0), buf);
}

void ui_home_on_destroy(void)
{
    ui_anim_stop(s_pet_avatar);
    s_name = NULL;
    s_level = NULL;
    s_exp_text = NULL;
    s_exp_bar = NULL;
    s_today_chip = NULL;
    s_steps_chip = NULL;
    s_checkin_chip = NULL;
    s_pet_avatar = NULL;
}
