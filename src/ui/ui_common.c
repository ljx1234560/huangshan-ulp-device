#include "ui_internal.h"

#include <stdio.h>
#include <string.h>

#include "fonts/ui_fonts.h"

static VelaPetTheme g_themes[5];
static int g_themes_ready = 0;
static const VelaPetTheme *g_current_theme = NULL;
static lv_obj_t *s_toast = NULL;

static void back_event_cb(lv_event_t *e);
static void toast_close_cb(lv_timer_t *timer);
static void overlay_close_cb(lv_event_t *e);
static void defer_pump_cb(lv_timer_t *timer);

/*
 * 延迟执行队列：在回调里删除事件目标所在的页面/容器会崩溃，
 * 导航与刷新统一延迟一拍（lv_timer）执行。-pedantic 禁止函数指针与
 * void* 互转，故用静态 FIFO 携带函数指针，timer 只作泵。
 */
#define UI_DEFER_QUEUE 4
static void (*s_defer_q[UI_DEFER_QUEUE])(void);
static unsigned s_defer_head;
static unsigned s_defer_count;

void ui_nav_defer(void (*show_fn)(void))
{
    if (s_defer_count >= UI_DEFER_QUEUE)
    {
        return; /* 队列满：丢弃（极端连点场景） */
    }
    s_defer_q[(s_defer_head + s_defer_count) % UI_DEFER_QUEUE] = show_fn;
    s_defer_count++;
    if (s_defer_count == 1U)
    {
        lv_timer_t *timer = lv_timer_create(defer_pump_cb, 1, NULL);

        lv_timer_set_repeat_count(timer, 1);
    }
}

static void defer_pump_cb(lv_timer_t *timer)
{
    lv_timer_del(timer);
    while (s_defer_count > 0U)
    {
        void (*show_fn)(void) = s_defer_q[s_defer_head];

        s_defer_head = (s_defer_head + 1U) % UI_DEFER_QUEUE;
        s_defer_count--;
        if (show_fn != NULL)
        {
            show_fn(); /* 执行中可能再入队，循环会一并处理 */
        }
    }
}

static void init_themes(void)
{
    if (g_themes_ready)
    {
        return;
    }

    /* 颜色只是皮肤的一部分；最终形象由整帧 JPG 场景图承担。 */
    g_themes[0] = (VelaPetTheme){"default",
                                  lv_color_hex(0xF8F1FF), lv_color_hex(0xFFF7FB),
                                  lv_color_hex(0xFFFFFF), lv_color_hex(0xFF8FC7),
                                  lv_color_hex(0x8BD8C7), lv_color_hex(0x344054),
                                  lv_color_hex(0xFFB6D8)};
    g_themes[1] = (VelaPetTheme){"sport_blue",
                                 lv_color_hex(0xEFF8FF), lv_color_hex(0xE0F2FE),
                                 lv_color_hex(0xF8FBFF), lv_color_hex(0x4AA3FF),
                                 lv_color_hex(0x6BD3FF), lv_color_hex(0x243B53),
                                 lv_color_hex(0x8BD3FF)};
    g_themes[2] = (VelaPetTheme){"flame_red",
                                 lv_color_hex(0xFFF3EE), lv_color_hex(0xFFE3D7),
                                 lv_color_hex(0xFFFBF8), lv_color_hex(0xFF8A6B),
                                 lv_color_hex(0xFFC078), lv_color_hex(0x4A2F2A),
                                 lv_color_hex(0xFFAA8F)};
    g_themes[3] = (VelaPetTheme){"star_purple",
                                 lv_color_hex(0xF5F0FF), lv_color_hex(0xEBE1FF),
                                 lv_color_hex(0xFDFBFF), lv_color_hex(0xA98CFF),
                                 lv_color_hex(0xD5B8FF), lv_color_hex(0x352B4B),
                                 lv_color_hex(0xC4A8FF)};
    g_themes[4] = (VelaPetTheme){"rainbow",
                                 lv_color_hex(0xFFFBF0), lv_color_hex(0xF1FFF8),
                                 lv_color_hex(0xFFFFFF), lv_color_hex(0xFF9ECB),
                                 lv_color_hex(0x79D7C8), lv_color_hex(0x344054),
                                 lv_color_hex(0xFFD36E)};

    g_current_theme = &g_themes[0];
    g_themes_ready = 1;
}

const VelaPetTheme *ui_get_theme_by_skin(const char *skin_name)
{
    unsigned index;

    init_themes();
    if (skin_name != NULL)
    {
        for (index = 0U; index < 5U; ++index)
        {
            if (g_themes[index].skin_name != NULL &&
                strcmp(skin_name, g_themes[index].skin_name) == 0)
            {
                return &g_themes[index];
            }
        }
    }
    return &g_themes[0];
}

const VelaPetTheme *ui_get_current_theme(void)
{
    init_themes();
    return (g_current_theme != NULL) ? g_current_theme : &g_themes[0];
}

void ui_apply_theme_by_skin(const char *skin_name)
{
    g_current_theme = ui_get_theme_by_skin(skin_name);
}

void ui_apply_theme_to_page(lv_obj_t *page)
{
    const VelaPetTheme *theme;

    if (page == NULL)
    {
        return;
    }
    theme = ui_get_current_theme();
    lv_obj_set_style_bg_color(page, theme->bg_color, 0);
    lv_obj_set_style_bg_grad_color(page, theme->bg_grad_color, 0);
    lv_obj_set_style_bg_grad_dir(page, LV_GRAD_DIR_VER, 0);
}

const lv_font_t *ui_font_title(void)
{
    /* 中文子集 20px（GB2312 一级常用字）。数字与拉丁同样覆盖。 */
    return &ui_font_cn_20;
}

const lv_font_t *ui_font_body(void)
{
    return &ui_font_cn_16;
}

static const char *const g_skin_ids[5] = {
    "default", "sport_blue", "flame_red", "star_purple", "rainbow"
};

const char *ui_skin_display_name(const char *skin_id)
{
    static const char *const names[5] = {
        "初始", "运动蓝", "烈焰红", "星河紫", "彩虹"
    };
    unsigned index;

    if (skin_id != NULL && skin_id[0] != '\0')
    {
        for (index = 0U; index < 5U; ++index)
        {
            if (strcmp(skin_id, g_skin_ids[index]) == 0)
            {
                return names[index];
            }
        }
    }
    return names[0];
}

const char *ui_title_display_name(const char *title_id)
{
    if (title_id != NULL)
    {
        if (strcmp(title_id, "egg_baby") == 0) return "小小萌新";
        if (strcmp(title_id, "young_pet") == 0) return "元气少年";
        if (strcmp(title_id, "sport_star") == 0) return "运动之星";
        if (strcmp(title_id, "vela_legend") == 0) return "腕上传说";
    }
    return "见习伙伴";
}

void ui_check_levelup(void)
{
    static lv_obj_t *s_overlay = NULL;
    uint16_t level;
    lv_obj_t *card;
    lv_obj_t *label;
    char buf[48];

    if (s_overlay != NULL)
    {
        return; /* 上一场庆祝还没关 */
    }
    level = velapet_service_last_levelup();
    if (level == 0U)
    {
        return;
    }
    velapet_service_ack_levelup();

    s_overlay = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(s_overlay);
    lv_obj_set_size(s_overlay, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(s_overlay, lv_color_hex(0x1B1526), 0);
    lv_obj_set_style_bg_opa(s_overlay, LV_OPA_80, 0);
    lv_obj_clear_flag(s_overlay, LV_OBJ_FLAG_SCROLLABLE);

    card = ui_create_card(s_overlay, 250, 150);
    lv_obj_center(card);

    label = lv_label_create(card);
    snprintf(buf, sizeof(buf), "升级啦！Lv.%u", (unsigned)level);
    lv_label_set_text(label, buf);
    lv_obj_set_style_text_font(label, ui_font_title(), 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFC94D), 0);
    lv_obj_align(label, LV_ALIGN_TOP_MID, 0, 22);

    label = lv_label_create(card);
    lv_label_set_text(label, "新奖励可能已经解锁，\n去任务页和皮肤页看看吧！");
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(label, LV_ALIGN_CENTER, 0, 6);

    {
        lv_obj_t *btn = ui_create_button(card, "太棒了", overlay_close_cb, NULL);
        lv_obj_align(btn, LV_ALIGN_BOTTOM_MID, 0, -12);
    }
}

void ui_text_sanitize(char *buf, uint32_t buf_size, const lv_font_t *font)
{
    uint32_t read = 0U;
    uint32_t write = 0U;

    if (buf == NULL || font == NULL)
    {
        return;
    }

    while (buf[read] != '\0' && write + 4U < buf_size)
    {
        unsigned char c = (unsigned char)buf[read];
        uint32_t codepoint = 0U;
        uint32_t len = 1U;

        if (c < 0x80U)
        {
            codepoint = c;
        }
        else if ((c & 0xE0U) == 0xC0U)
        {
            len = 2U;
            codepoint = (uint32_t)(c & 0x1FU);
        }
        else if ((c & 0xF0U) == 0xE0U)
        {
            len = 3U;
            codepoint = (uint32_t)(c & 0x0FU);
        }
        else
        {
            len = 1U; /* 非法字节，按单字节处理 */
            codepoint = c;
        }

        if (len == 1U)
        {
            lv_font_glyph_dsc_t dsc;

            if (codepoint == '\n' || codepoint == '\r' ||
                lv_font_get_glyph_dsc(font, &dsc, codepoint, 0U))
            {
                buf[write++] = buf[read++];
            }
            else
            {
                buf[write++] = '?';
                read++;
            }
        }
        else
        {
            uint32_t cont;
            int valid = 1;

            for (cont = 1U; cont < len; ++cont)
            {
                unsigned char cc = (unsigned char)buf[read + cont];
                if ((cc & 0xC0U) != 0x80U)
                {
                    valid = 0;
                }
            }
            if (valid)
            {
                lv_font_glyph_dsc_t dsc;

                for (cont = 1U; cont < len; ++cont)
                {
                    codepoint = (codepoint << 6) |
                                (uint32_t)(buf[read + cont] & 0x3F);
                }
                if (lv_font_get_glyph_dsc(font, &dsc, codepoint, 0U))
                {
                    uint32_t k;

                    for (k = 0U; k < len; ++k)
                    {
                        buf[write++] = buf[read++];
                    }
                }
                else
                {
                    buf[write++] = '?';
                    read += len;
                }
            }
            else
            {
                buf[write++] = '?';
                read++;
            }
        }
    }
    buf[write] = '\0';
}

lv_obj_t *ui_create_page(void)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *page = lv_obj_create(lv_scr_act());

    lv_obj_remove_style_all(page);
    lv_obj_set_size(page, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(page, theme->bg_color, 0);
    lv_obj_set_style_bg_grad_color(page, theme->bg_grad_color, 0);
    lv_obj_set_style_bg_grad_dir(page, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_opa(page, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_all(page, 9, 0);
    lv_obj_set_style_pad_row(page, 6, 0);
    lv_obj_set_flex_flow(page, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(page, LV_FLEX_ALIGN_START,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    return page;
}

lv_obj_t *ui_create_title(lv_obj_t *parent, const char *title, int with_back)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *row = lv_obj_create(parent);
    lv_obj_t *label;

    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, LV_PCT(100), 30);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row, LV_FLEX_ALIGN_SPACE_BETWEEN,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    if (with_back)
    {
        ui_create_button(row, "＜", back_event_cb, NULL);
    }

    label = lv_label_create(row);
    lv_label_set_text(label, title);
    lv_obj_set_style_text_color(label, theme->text_color, 0);
    lv_obj_set_style_text_font(label, ui_font_title(), 0);

    if (with_back)
    {
        lv_obj_t *space = lv_obj_create(row);
        lv_obj_remove_style_all(space);
        lv_obj_set_size(space, 40, 30);
    }
    return label;
}

static void back_event_cb(lv_event_t *e)
{
    (void)e;
    ui_note_event("BACK->HOME");
    ui_nav_defer(ui_router_show_home);
}

lv_obj_t *ui_create_button(lv_obj_t *parent, const char *text,
                           lv_event_cb_t cb, void *user_data)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *btn = lv_btn_create(parent);
    lv_obj_t *label = lv_label_create(btn);

    lv_obj_set_size(btn, 78, 36);
    lv_obj_set_style_radius(btn, 18, 0);
    lv_obj_set_style_bg_color(btn, theme->primary_color, 0);
    lv_obj_set_style_bg_color(btn, theme->accent_color, LV_STATE_PRESSED);
    lv_obj_set_style_shadow_width(btn, 8, 0);
    lv_obj_set_style_shadow_opa(btn, LV_OPA_30, 0);
    lv_obj_set_style_pad_hor(btn, 8, 0);

    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(label, ui_font_title(), 0);
    lv_obj_center(label);

    if (cb != NULL)
    {
        lv_obj_add_event_cb(btn, cb, LV_EVENT_CLICKED, user_data);
    }
    return btn;
}

lv_obj_t *ui_create_card(lv_obj_t *parent, lv_coord_t width, lv_coord_t height)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *card = lv_obj_create(parent);

    lv_obj_set_size(card, width, height);
    lv_obj_set_style_radius(card, 22, 0);
    lv_obj_set_style_bg_color(card, theme->card_color, 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_80, 0);
    lv_obj_set_style_border_width(card, 1, 0);
    lv_obj_set_style_border_color(card, theme->accent_color, 0);
    lv_obj_set_style_shadow_width(card, 10, 0);
    lv_obj_set_style_shadow_opa(card, LV_OPA_30, 0);
    lv_obj_set_style_pad_all(card, 12, 0);
    return card;
}

lv_obj_t *ui_create_chip(lv_obj_t *parent, const char *label, const char *value)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *chip = lv_obj_create(parent);
    lv_obj_t *txt;

    lv_obj_set_size(chip, 108, 52);
    lv_obj_set_style_radius(chip, 18, 0);
    lv_obj_set_style_bg_color(chip, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_bg_opa(chip, LV_OPA_70, 0);
    lv_obj_set_style_border_width(chip, 1, 0);
    lv_obj_set_style_border_color(chip, theme->accent_color, 0);
    lv_obj_set_style_pad_all(chip, 5, 0);
    lv_obj_clear_flag(chip, LV_OBJ_FLAG_SCROLLABLE);

    txt = lv_label_create(chip);
    lv_label_set_text_fmt(txt, "%s\n%s", (label != NULL) ? label : "",
                          (value != NULL) ? value : "");
    lv_obj_set_width(txt, LV_PCT(100));
    lv_obj_set_style_text_align(txt, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_font(txt, ui_font_body(), 0);
    lv_obj_set_style_text_color(txt, theme->text_color, 0);
    lv_obj_center(txt);
    return chip;
}

static lv_obj_t *pet_part(lv_obj_t *parent, lv_coord_t x, lv_coord_t y,
                          lv_coord_t w, lv_coord_t h, lv_color_t color)
{
    lv_obj_t *part = lv_obj_create(parent);

    lv_obj_remove_style_all(part);
    lv_obj_set_pos(part, x, y);
    lv_obj_set_size(part, w, h);
    lv_obj_set_style_radius(part, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(part, color, 0);
    lv_obj_set_style_bg_opa(part, LV_OPA_COVER, 0);
    return part;
}

/* 临时占位形象：等整帧 JPG 场景图接入后整体删除。 */
lv_obj_t *ui_create_pet_avatar(lv_obj_t *parent, lv_coord_t width,
                               lv_coord_t height)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *box = lv_obj_create(parent);
    lv_coord_t cx = width / 2;
    lv_coord_t head = (height * 44) / 100;
    lv_coord_t head_x;
    lv_coord_t head_y = (height * 16) / 100;

    if (head < 56)
    {
        head = 56;
    }
    head_x = cx - head / 2;

    lv_obj_remove_style_all(box);
    lv_obj_set_size(box, width, height);
    lv_obj_clear_flag(box, LV_OBJ_FLAG_SCROLLABLE);

    pet_part(box, head_x, head_y, head, head, theme->pet_color);
    pet_part(box, cx - (width * 24) / 100, head_y + head - 4,
             (width * 48) / 100, (height * 28) / 100, theme->pet_color);
    pet_part(box, cx - 18, head_y + head / 2 - 4, 8, 8, theme->text_color);
    pet_part(box, cx + 10, head_y + head / 2 - 4, 8, 8, theme->text_color);

    lv_obj_t *mouth = lv_label_create(box);
    lv_label_set_text(mouth, "^");
    lv_obj_set_style_text_color(mouth, theme->text_color, 0);
    lv_obj_set_style_text_font(mouth, ui_font_body(), 0);
    lv_obj_align(mouth, LV_ALIGN_CENTER, 0, -2);
    return box;
}

lv_obj_t *ui_create_exp_bar(lv_obj_t *parent, uint8_t percent)
{
    const VelaPetTheme *theme = ui_get_current_theme();
    lv_obj_t *bar = lv_bar_create(parent);

    lv_obj_set_size(bar, LV_PCT(88), 12);
    lv_bar_set_range(bar, 0, 100);
    lv_bar_set_value(bar, percent, LV_ANIM_ON);
    lv_obj_set_style_radius(bar, 12, 0);
    lv_obj_set_style_radius(bar, 12, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(bar, theme->bg_grad_color, 0);
    lv_obj_set_style_bg_color(bar, theme->accent_color, LV_PART_INDICATOR);
    return bar;
}

void ui_style_label(lv_obj_t *label, lv_color_t color)
{
    lv_obj_set_style_text_color(label, color, 0);
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
}

void ui_show_toast(const char *msg)
{
    if (s_toast != NULL)
    {
        lv_obj_del(s_toast);
        s_toast = NULL;
    }

    s_toast = lv_obj_create(lv_layer_top());
    lv_obj_set_size(s_toast, LV_PCT(82), 44);
    lv_obj_align(s_toast, LV_ALIGN_BOTTOM_MID, 0, -18);
    lv_obj_set_style_radius(s_toast, 20, 0);
    lv_obj_set_style_bg_color(s_toast, lv_color_hex(0x5A5066), 0);
    lv_obj_set_style_bg_opa(s_toast, LV_OPA_90, 0);
    lv_obj_set_style_border_width(s_toast, 0, 0);

    lv_obj_t *label = lv_label_create(s_toast);
    lv_label_set_text(label, (msg != NULL) ? msg : "");
    lv_obj_set_style_text_color(label, lv_color_hex(0xFFFFFF), 0);
    lv_obj_set_style_text_font(label, ui_font_body(), 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_width(label, LV_PCT(90));
    lv_obj_center(label);

    lv_timer_t *timer = lv_timer_create(toast_close_cb, 1400, s_toast);
    lv_timer_set_repeat_count(timer, 1);
}

static void toast_close_cb(lv_timer_t *timer)
{
    if (timer->user_data == s_toast)
    {
        lv_obj_del_async(s_toast);
        s_toast = NULL;
    }
    lv_timer_del(timer);
}

static void overlay_close_cb(lv_event_t *e)
{
    lv_obj_t *overlay = lv_obj_get_parent(lv_obj_get_parent(lv_event_get_target(e)));

    (void)e;
    ui_note_event("LEVELUP_ACK");
    lv_obj_del_async(overlay);
}

lv_obj_t *ui_keyboard(void)
{
    static lv_obj_t *s_keyboard = NULL;

    if (s_keyboard == NULL)
    {
        s_keyboard = lv_keyboard_create(lv_layer_top());
        lv_obj_set_size(s_keyboard, LV_PCT(100), 190);
        lv_obj_align(s_keyboard, LV_ALIGN_BOTTOM_MID, 0, 0);
        lv_obj_add_flag(s_keyboard, LV_OBJ_FLAG_HIDDEN);
    }
    return s_keyboard;
}

int ui_percent(uint32_t value, uint32_t total)
{
    uint64_t pct;

    if (total == 0U)
    {
        return 0;
    }
    pct = ((uint64_t)value * 100U) / (uint64_t)total;
    return (pct > 100U) ? 100 : (int)pct;
}
