#include "ui_internal.h"

#include <stdio.h>
#include <string.h>

/*
 * 形象页：当前用几何占位形象；默认三款（星云猫/奶油犬/薄荷兔）为云端资源
 * （handoff 第 6 节），资源事件接口（外观资源事件）评审接入后替换为图片。
 */

static lv_obj_t *s_name_label;
static lv_obj_t *s_title_label;
static lv_obj_t *s_stat_label;
static lv_obj_t *s_pet_choice[3];
static int s_pet_selected;

static const char *const pet_names[3] = {
    "星云猫（默认）", "奶油犬", "薄荷兔"
};

static void pet_choice_cb(lv_event_t *e)
{
    uintptr_t index = (uintptr_t)lv_event_get_user_data(e);
    unsigned i;

    if (index >= 3U)
    {
        return;
    }
    ui_note_event("PET_SELECT");
    s_pet_selected = (int)index;
    for (i = 0U; i < 3U; ++i)
    {
        if (s_pet_choice[i] == NULL)
        {
            continue;
        }
        if ((int)i == s_pet_selected)
        {
            lv_obj_set_style_border_width(s_pet_choice[i], 2, 0);
        }
        else
        {
            lv_obj_set_style_border_width(s_pet_choice[i], 1, 0);
        }
    }
    ui_show_toast("形象选择待端侧保存接入，暂不持久化");
}

void ui_avatar_create(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    unsigned index;

    g_ui_root = ui_create_page();
    ui_create_title(g_ui_root, "形象", 1);

    /* 舞台 */
    lv_obj_t *stage_card = ui_create_card(g_ui_root, LV_PCT(100), 196);
    lv_obj_t *stage = lv_obj_create(stage_card);
    lv_obj_remove_style_all(stage);
    lv_obj_set_size(stage, 170, 130);
    lv_obj_clear_flag(stage, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *avatar = ui_create_pet_avatar(stage, 170, 130);
    lv_obj_center(avatar);
    lv_obj_align(stage, LV_ALIGN_TOP_MID, 0, 0);

    s_name_label = lv_label_create(stage_card);
    lv_obj_set_style_text_font(s_name_label, ui_font_title(), 0);
    lv_obj_set_style_text_color(s_name_label, theme->text_color, 0);
    lv_obj_align(s_name_label, LV_ALIGN_BOTTOM_LEFT, 0, -14);

    s_title_label = lv_label_create(stage_card);
    lv_obj_set_style_text_font(s_title_label, ui_font_body(), 0);
    lv_obj_set_style_text_color(s_title_label, theme->primary_color, 0);
    lv_obj_align(s_title_label, LV_ALIGN_BOTTOM_RIGHT, 0, -14);

    /* 资料小字 */
    s_stat_label = lv_label_create(g_ui_root);
    lv_obj_set_style_text_font(s_stat_label, ui_font_body(), 0);
    lv_obj_set_style_text_color(s_stat_label,
                                lv_color_hex(0x8A8398), 0);

    /* 默认款选择（云端外观接口；端侧保存待接入） */
    lv_obj_t *card = ui_create_card(g_ui_root, LV_PCT(100), 118);
    lv_obj_t *caption = lv_label_create(card);
    lv_label_set_text(caption, "默认形象（云端选择）");
    lv_obj_set_style_text_font(caption, ui_font_body(), 0);
    lv_obj_set_style_text_color(caption, theme->text_color, 0);
    lv_obj_align(caption, LV_ALIGN_TOP_LEFT, 0, 0);

    lv_obj_t *row = lv_obj_create(card);
    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, LV_PCT(100), 42);
    lv_obj_align(row, LV_ALIGN_BOTTOM_MID, 0, -2);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(row, 6, 0);
    for (index = 0U; index < 3U; ++index)
    {
        lv_obj_t *btn = ui_create_button(row, pet_names[index],
                                         pet_choice_cb, (void *)(uintptr_t)index);
        lv_obj_set_size(btn, 108, 38);
        lv_obj_set_style_text_font(lv_obj_get_child(btn, 0), ui_font_body(), 0);
        lv_obj_set_style_bg_color(btn, theme->card_color, 0);
        lv_obj_set_style_bg_opa(btn, LV_OPA_90, 0);
        lv_obj_set_style_text_color(lv_obj_get_child(btn, 0),
                                    theme->text_color, 0);
        s_pet_choice[index] = btn;
    }

    /* AI 生成形象占位（Seedream 当前禁用，handoff 第 6 节） */
    lv_obj_t *ai_card = ui_create_card(g_ui_root, LV_PCT(100), 52);
    lv_obj_set_style_bg_opa(ai_card, LV_OPA_40, 0);
    lv_obj_t *ai_label = lv_label_create(ai_card);
    lv_label_set_text(ai_label, "AI 生成专属形象 · 即将开放");
    lv_obj_set_style_text_font(ai_label, ui_font_body(), 0);
    lv_obj_set_style_text_color(ai_label, lv_color_hex(0x9A93A8), 0);
    lv_obj_center(ai_label);

    /* 初始态 */
    s_pet_selected = 0;
    for (index = 0U; index < 3U; ++index)
    {
        lv_obj_set_style_border_width(s_pet_choice[index],
                                      (index == 0U) ? 2 : 1, 0);
        lv_obj_set_style_border_color(s_pet_choice[index],
                                      theme->primary_color, 0);
    }

    if (snap != NULL)
    {
        lv_label_set_text(s_name_label,
                          (snap->name[0] != '\0') ? snap->name : "VelaPet");
    }
    ui_avatar_refresh();
}

void ui_avatar_refresh(void)
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    char buf[96];

    if (s_name_label == NULL || s_title_label == NULL ||
        s_stat_label == NULL)
    {
        return;
    }
    if (snap == NULL)
    {
        lv_label_set_text(s_name_label, "VelaPet");
        lv_label_set_text(s_title_label, "");
        lv_label_set_text(s_stat_label, "");
        return;
    }

    lv_label_set_text(s_name_label,
                      (snap->name[0] != '\0') ? snap->name : "VelaPet");
    lv_label_set_text(s_title_label, ui_title_display_name(snap->title));

    snprintf(buf, sizeof(buf), "等级 %u · 皮肤：%s",
             (unsigned)snap->level,
             ui_skin_display_name(snap->current_skin));
    lv_label_set_text(s_stat_label, buf);
}

void ui_avatar_on_destroy(void)
{
    unsigned index;

    s_name_label = NULL;
    s_title_label = NULL;
    s_stat_label = NULL;
    for (index = 0U; index < 3U; ++index)
    {
        s_pet_choice[index] = NULL;
    }
}
