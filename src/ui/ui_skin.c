#include "ui_internal.h"

#include <stdio.h>
#include <string.h>

#define SKIN_CARD_H 56
/* 缩略图 120x96 缩到 70x56 填满卡片左侧（256 为 LVGL zoom 基准） */
#define SKIN_THUMB_ZOOM 149

static lv_obj_t *s_status[5];

static int is_current(const char *skin_id, const velapet_snapshot_t *snap)
{
    return (snap != NULL && strcmp(snap->current_skin, skin_id) == 0);
}

static int is_unlocked(const char *skin_id, const velapet_snapshot_t *snap)
{
    uint8_t index;

    if (snap == NULL)
    {
        return 0;
    }
    for (index = 0U; index < snap->unlocked_skin_count &&
                     index < VELAPET_MAX_UNLOCKED_SKINS; ++index)
    {
        if (strcmp(snap->unlocked_skins[index], skin_id) == 0)
        {
            return 1;
        }
    }
    return 0;
}

static void switch_cb(lv_event_t *e)
{
    uintptr_t index = (uintptr_t)lv_event_get_user_data(e);
    char buf[64];

    if (index >= 5U)
    {
        return;
    }
    ui_note_event("SKIN_SWITCH");
    if (velapet_service_switch_skin(ui_skin_ids[index]) != 0)
    {
        ui_show_toast("还没解锁哦，升级可获得新皮肤");
        return;
    }
    ui_apply_theme_by_skin(ui_skin_ids[index]);
    snprintf(buf, sizeof(buf), "已换上「%s」",
             ui_skin_display_name(ui_skin_ids[index]));
    ui_show_toast(buf);
    /* 「使用」按钮在将被销毁重建的页面里，延迟一拍再重载 */
    ui_nav_defer(ui_router_reload);
}

static void build_status(lv_obj_t *zone, unsigned index,
                         const velapet_snapshot_t *snap)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *label;

    lv_obj_clean(zone);

    if (is_current(ui_skin_ids[index], snap))
    {
        label = lv_label_create(zone);
        lv_label_set_text(label, "使用中");
        lv_obj_set_style_text_color(label, theme->primary_color, 0);
    }
    else if (is_unlocked(ui_skin_ids[index], snap))
    {
        lv_obj_t *btn = ui_create_button(zone, "使用", switch_cb,
                                         (void *)(uintptr_t)index);
        lv_obj_set_size(btn, 64, 34);
        return;
    }
    else
    {
        label = lv_label_create(zone);
        lv_label_set_text(label, "未解锁");
        lv_obj_set_style_text_color(label, lv_color_hex(0x9A93A8), 0);
    }
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_obj_center(label);
}

/* 卡片左侧视觉：图片模式用缩略图（未解锁加暗遮罩），否则回退几何圆色板 */
static void build_swatch(lv_obj_t *card, unsigned index,
                         const velapet_snapshot_t *snap)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    const lv_img_dsc_t *thumb = ui_skin_image_thumb((uint8_t)index);
    lv_obj_t *holder;

    holder = lv_obj_create(card);
    lv_obj_remove_style_all(holder);
    lv_obj_set_size(holder, 70, SKIN_CARD_H);
    lv_obj_clear_flag(holder, LV_OBJ_FLAG_SCROLLABLE);

    if (thumb != NULL)
    {
        lv_obj_t *img = lv_img_create(holder);

        lv_img_set_src(img, thumb);
        lv_img_set_zoom(img, SKIN_THUMB_ZOOM);
        lv_obj_center(img);
        if (!is_unlocked(ui_skin_ids[index], snap))
        {
            lv_obj_t *mask = lv_obj_create(holder);

            lv_obj_remove_style_all(mask);
            lv_obj_set_size(mask, 70, SKIN_CARD_H);
            lv_obj_set_style_radius(mask, 8, 0);
            lv_obj_set_style_bg_color(mask, lv_color_hex(0x000000), 0);
            lv_obj_set_style_bg_opa(mask, LV_OPA_60, 0);
            lv_obj_center(mask);
        }
    }
    else
    {
        lv_obj_t *swatch = lv_obj_create(holder);

        lv_obj_remove_style_all(swatch);
        lv_obj_set_size(swatch, 34, 34);
        lv_obj_set_style_radius(swatch, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(swatch, theme->pet_color, 0);
        lv_obj_set_style_bg_opa(swatch, LV_OPA_COVER, 0);
        lv_obj_center(swatch);
    }
}

void ui_skin_create(void)
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    unsigned index;

    g_ui_root = ui_create_page();
    ui_create_title(g_ui_root, "皮肤", 1);

    for (index = 0U; index < UI_SKIN_COUNT; ++index)
    {
        const VelaPetTheme *theme = ui_get_theme_by_skin(ui_skin_ids[index]);
        lv_obj_t *card = ui_create_card(g_ui_root, LV_PCT(100), SKIN_CARD_H);
        lv_obj_t *name;
        lv_obj_t *current_tag;

        lv_obj_set_flex_flow(card, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(card, LV_FLEX_ALIGN_START,
                              LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(card, 10, 0);

        build_swatch(card, index, snap);

        name = lv_label_create(card);
        lv_label_set_text(name, ui_skin_display_name(ui_skin_ids[index]));
        lv_obj_set_style_text_font(name, ui_font_body(), 0);
        lv_obj_set_style_text_color(name, theme->text_color, 0);
        lv_obj_set_flex_grow(name, 1);

        current_tag = lv_obj_create(card);
        lv_obj_remove_style_all(current_tag);
        lv_obj_set_size(current_tag, 68, SKIN_CARD_H - 16);
        s_status[index] = current_tag;

        build_status(s_status[index], index, snap);
    }

    /* AI 定制皮肤占位（用户上传图片 + 提示词生成；依赖生图服务放开） */
    {
        lv_obj_t *ai_card = ui_create_card(g_ui_root, LV_PCT(100), 48);
        lv_obj_t *ai_label = lv_label_create(ai_card);

        lv_obj_set_style_bg_opa(ai_card, LV_OPA_40, 0);
        lv_label_set_text(ai_label,
                          "AI 定制皮肤 · 上传图片+描述生成（即将开放）");
        lv_obj_set_style_text_font(ai_label, ui_font_body(), 0);
        lv_obj_set_style_text_color(ai_label, lv_color_hex(0x9A93A8), 0);
        lv_obj_center(ai_label);
    }
}

void ui_skin_refresh(void)
{
    const velapet_snapshot_t *snap = velapet_service_snapshot();
    unsigned index;

    if (s_status[0] == NULL)
    {
        return;
    }
    for (index = 0U; index < UI_SKIN_COUNT; ++index)
    {
        build_status(s_status[index], index, snap);
    }
}

void ui_skin_on_destroy(void)
{
    unsigned index;

    for (index = 0U; index < UI_SKIN_COUNT; ++index)
    {
        s_status[index] = NULL;
    }
}
