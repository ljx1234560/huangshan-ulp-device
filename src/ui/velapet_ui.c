#include "velapet_ui.h"

#include <stdint.h>
#include <stdio.h>

#include <rtthread.h>
#include <lvgl.h>

#ifdef FINSH_USING_MSH
#include <finsh.h>
#endif

enum velapet_action
{
    VELAPET_ACTION_TASK = 1,
    VELAPET_ACTION_FEED,
    VELAPET_ACTION_CHAT
};

static lv_obj_t *g_exp_bar;
static lv_obj_t *g_exp_label;
static lv_obj_t *g_status_label;
static uint32_t g_tap_count;
static uint32_t g_steps = 1280U;
static uint8_t g_exp = 35U;
static const char *g_last_action = "NONE";

static void set_label_font(lv_obj_t *label, const lv_font_t *font)
{
    lv_obj_set_style_text_font(label, font, LV_PART_MAIN);
}

static lv_obj_t *make_text(lv_obj_t *parent,
                           const char *text,
                           lv_color_t color,
                           const lv_font_t *font,
                           lv_coord_t x,
                           lv_coord_t y)
{
    lv_obj_t *label = lv_label_create(parent);

    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, color, LV_PART_MAIN);
    set_label_font(label, font);
    lv_obj_set_pos(label, x, y);
    return label;
}

static void update_exp_text(void)
{
    char text[32];

    rt_snprintf(text, sizeof(text), "EXP %u / 100", (unsigned int)g_exp);
    lv_label_set_text(g_exp_label, text);
    lv_bar_set_value(g_exp_bar, g_exp, LV_ANIM_ON);
}

static void action_event_cb(lv_event_t *event)
{
    enum velapet_action action;
    char status[64];

    if (lv_event_get_code(event) != LV_EVENT_CLICKED)
    {
        return;
    }

    action = (enum velapet_action)(uintptr_t)lv_event_get_user_data(event);
    g_tap_count++;

    switch (action)
    {
    case VELAPET_ACTION_TASK:
        g_last_action = "TASK";
        g_steps += 25U;
        rt_snprintf(status, sizeof(status), "Task checked: %lu / 3,000 steps",
                    (unsigned long)g_steps);
        break;

    case VELAPET_ACTION_FEED:
        g_last_action = "FEED";
        g_exp = (g_exp <= 95U) ? (uint8_t)(g_exp + 5U) : 100U;
        update_exp_text();
        rt_snprintf(status, sizeof(status), "NOVA is happy!  EXP +5");
        break;

    case VELAPET_ACTION_CHAT:
    default:
        g_last_action = "CHAT";
        rt_snprintf(status, sizeof(status), "NOVA: Touch link is working!");
        break;
    }

    lv_label_set_text(g_status_label, status);
    rt_kprintf("[ui-test] touch=PASS action=%s count=%lu exp=%u steps=%lu\n",
               g_last_action,
               (unsigned long)g_tap_count,
               (unsigned int)g_exp,
               (unsigned long)g_steps);
}

static lv_obj_t *make_button(lv_obj_t *parent,
                             const char *text,
                             lv_color_t color,
                             lv_coord_t x,
                             enum velapet_action action)
{
    lv_obj_t *button = lv_btn_create(parent);
    lv_obj_t *label;

    lv_obj_set_size(button, 110, 72);
    lv_obj_set_pos(button, x, 310);
    lv_obj_set_style_radius(button, 18, LV_PART_MAIN);
    lv_obj_set_style_border_width(button, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(button, 0, LV_PART_MAIN);
    lv_obj_set_style_bg_color(button, color, LV_PART_MAIN | LV_STATE_DEFAULT);
    lv_obj_set_style_bg_color(button, lv_color_lighten(color, LV_OPA_20),
                              LV_PART_MAIN | LV_STATE_PRESSED);
    lv_obj_add_event_cb(button, action_event_cb, LV_EVENT_CLICKED,
                        (void *)(uintptr_t)action);

    label = lv_label_create(button);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, lv_color_white(), LV_PART_MAIN);
    set_label_font(label, &lv_font_montserrat_20);
    lv_obj_center(label);
    return button;
}

void velapet_ui_create(void)
{
    lv_obj_t *screen = lv_scr_act();
    lv_obj_t *card;
    lv_obj_t *avatar;
    lv_obj_t *face;
    lv_obj_t *online_dot;
    lv_obj_t *title;
    lv_obj_t *subtitle;

    lv_obj_clean(screen);
    lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_scrollbar_mode(screen, LV_SCROLLBAR_MODE_OFF);
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x0B1020), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_pad_all(screen, 0, LV_PART_MAIN);

    title = make_text(screen, "VelaPet", lv_color_white(),
                      &lv_font_montserrat_28, 20, 14);
    lv_obj_set_style_text_letter_space(title, 1, LV_PART_MAIN);

    online_dot = lv_obj_create(screen);
    lv_obj_set_size(online_dot, 12, 12);
    lv_obj_set_pos(online_dot, 276, 25);
    lv_obj_set_style_radius(online_dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(online_dot, lv_color_hex(0x52E3A4), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(online_dot, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(online_dot, 0, LV_PART_MAIN);
    lv_obj_clear_flag(online_dot, LV_OBJ_FLAG_SCROLLABLE);

    subtitle = make_text(screen, "DEVICE READY", lv_color_hex(0xA9B6D3),
                         &lv_font_montserrat_12, 294, 24);
    lv_obj_align_to(subtitle, online_dot, LV_ALIGN_OUT_RIGHT_MID, 6, 0);

    card = lv_obj_create(screen);
    lv_obj_set_size(card, 350, 190);
    lv_obj_set_pos(card, 20, 58);
    lv_obj_set_style_radius(card, 24, LV_PART_MAIN);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x172141), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card, 0, LV_PART_MAIN);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);

    avatar = lv_obj_create(card);
    lv_obj_set_size(avatar, 112, 112);
    lv_obj_set_pos(avatar, 20, 23);
    lv_obj_set_style_radius(avatar, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(avatar, lv_color_hex(0x8A6CFF), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(avatar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_border_width(avatar, 4, LV_PART_MAIN);
    lv_obj_set_style_border_color(avatar, lv_color_hex(0xB7A8FF), LV_PART_MAIN);
    lv_obj_clear_flag(avatar, LV_OBJ_FLAG_SCROLLABLE);

    face = lv_label_create(avatar);
    lv_label_set_text(face, "^_^");
    lv_obj_set_style_text_color(face, lv_color_white(), LV_PART_MAIN);
    set_label_font(face, &lv_font_montserrat_24);
    lv_obj_center(face);

    make_text(card, "NOVA", lv_color_white(), &lv_font_montserrat_24, 154, 24);
    make_text(card, "LV. 1", lv_color_hex(0x52E3A4), &lv_font_montserrat_20, 154, 56);

    g_exp_label = make_text(card, "EXP 35 / 100", lv_color_hex(0xA9B6D3),
                            &lv_font_montserrat_12, 154, 91);
    g_exp_bar = lv_bar_create(card);
    lv_obj_set_size(g_exp_bar, 170, 12);
    lv_obj_set_pos(g_exp_bar, 154, 112);
    lv_bar_set_range(g_exp_bar, 0, 100);
    lv_bar_set_value(g_exp_bar, g_exp, LV_ANIM_OFF);
    lv_obj_set_style_radius(g_exp_bar, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(g_exp_bar, lv_color_hex(0x2A355A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g_exp_bar, lv_color_hex(0xFFB65C), LV_PART_INDICATOR);

    make_text(card, "STEPS", lv_color_hex(0x7E8DB3),
              &lv_font_montserrat_12, 20, 154);
    make_text(card, "1,280 / 3,000", lv_color_white(),
              &lv_font_montserrat_20, 82, 147);

    g_status_label = lv_label_create(screen);
    lv_obj_set_width(g_status_label, 350);
    lv_label_set_long_mode(g_status_label, LV_LABEL_LONG_DOT);
    lv_label_set_text(g_status_label, "Tap a button to test touch");
    lv_obj_set_style_text_color(g_status_label, lv_color_hex(0xA9B6D3), LV_PART_MAIN);
    lv_obj_set_style_text_align(g_status_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
    set_label_font(g_status_label, &lv_font_montserrat_20);
    lv_obj_set_pos(g_status_label, 20, 268);

    make_button(screen, "TASK", lv_color_hex(0x3E6EEB), 15, VELAPET_ACTION_TASK);
    make_button(screen, "FEED", lv_color_hex(0xE8863A), 140, VELAPET_ACTION_FEED);
    make_button(screen, "CHAT", lv_color_hex(0x7B58D6), 265, VELAPET_ACTION_CHAT);

    subtitle = make_text(screen, "UI BRING-UP  |  COM8 LOG ENABLED",
                         lv_color_hex(0x66759B), &lv_font_montserrat_12, 0, 411);
    lv_obj_align(subtitle, LV_ALIGN_TOP_MID, 0, 411);
}

#ifdef FINSH_USING_MSH
static int ui_status(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    rt_kprintf("[ui-test] status=%s taps=%lu last=%s exp=%u steps=%lu\n",
               (g_tap_count > 0U) ? "PASS" : "WAITING",
               (unsigned long)g_tap_count,
               g_last_action,
               (unsigned int)g_exp,
               (unsigned long)g_steps);
    return 0;
}
MSH_CMD_EXPORT(ui_status, show VelaPet UI touch status);
#endif
