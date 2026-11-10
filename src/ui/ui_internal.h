#ifndef VELAPET_UI_INTERNAL_H
#define VELAPET_UI_INTERNAL_H

#include "lvgl.h"
#include "velapet_ui.h"
#include "velapet_service.h"
#include "ui_anim.h"
#include "ui_skin_image.h"

typedef enum
{
    UI_PAGE_HOME = 0,
    UI_PAGE_TASK,
    UI_PAGE_CHAT,
    UI_PAGE_PET_IMAGE,
    UI_PAGE_SKIN
} UiPage;

/* 皮肤主题：颜色只是皮肤的一部分，最终形象由整帧 JPG 场景图承担（无透明通道）。 */
typedef struct
{
    const char *skin_name;
    lv_color_t bg_color;
    lv_color_t bg_grad_color;
    lv_color_t card_color;
    lv_color_t primary_color;
    lv_color_t accent_color;
    lv_color_t text_color;
    lv_color_t pet_color;
} VelaPetTheme;

const VelaPetTheme *ui_get_current_theme(void);
const VelaPetTheme *ui_get_theme_by_skin(const char *skin_name);
void ui_apply_theme_by_skin(const char *skin_name);
void ui_apply_theme_to_page(lv_obj_t *page);

/* 字体集中在此：内置中文字体子集就绪后，只改这里三个函数即可全量切换。 */
const lv_font_t *ui_font_title(void);
const lv_font_t *ui_font_body(void);

lv_obj_t *ui_create_page(void);
lv_obj_t *ui_create_title(lv_obj_t *parent, const char *title, int with_back);
lv_obj_t *ui_create_button(lv_obj_t *parent, const char *text,
                           lv_event_cb_t cb, void *user_data);
lv_obj_t *ui_create_card(lv_obj_t *parent, lv_coord_t width, lv_coord_t height);
lv_obj_t *ui_create_chip(lv_obj_t *parent, const char *label, const char *value);
lv_obj_t *ui_create_pet_avatar(lv_obj_t *parent, lv_coord_t width,
                               lv_coord_t height);
lv_obj_t *ui_create_exp_bar(lv_obj_t *parent, uint8_t percent);
void ui_style_label(lv_obj_t *label, lv_color_t color);
void ui_show_toast(const char *msg);
int ui_percent(uint32_t value, uint32_t total);

/* 皮肤 ID -> 中文名。未知 ID 回退「初始」。 */
const char *ui_skin_display_name(const char *skin_id);
/* 内核称号 ID -> 中文称号。 */
const char *ui_title_display_name(const char *title_id);
/* 若服务有待处理升级事件，弹全屏庆祝并 ack。在动作回调后调用。 */
void ui_check_levelup(void);
/* 将 buf 中当前字体没有字形的字符替换为 '?'（AI 任意回复的缺字兜底）。 */
void ui_text_sanitize(char *buf, uint32_t buf_size, const lv_font_t *font);
/* 共享虚拟键盘（顶层，默认隐藏）；聊天页绑定 textarea 后按需显示。 */
lv_obj_t *ui_keyboard(void);
/* 延迟一拍再执行导航/刷新：回调内删除事件目标所在容器会崩溃。 */
void ui_nav_defer(void (*show_fn)(void));

/* 触摸诊断：所有可点控件回调里调用，供串口 ui_status 命令观察。 */
void ui_note_event(const char *action);

void ui_router_show_home(void);
void ui_router_show_task(void);
void ui_router_show_chat(void);
void ui_router_show_pet_image(void);
void ui_router_show_skin(void);
/* 销毁并重建当前页（换肤后应用新主题）。 */
void ui_router_reload(void);

void ui_home_create(void);
void ui_home_refresh(void);
void ui_home_on_destroy(void);

void ui_task_create(void);
void ui_task_refresh(void);
void ui_task_on_destroy(void);

void ui_chat_create(void);
void ui_chat_on_destroy(void);

void ui_avatar_create(void);
void ui_avatar_refresh(void);
void ui_avatar_on_destroy(void);

void ui_skin_create(void);
void ui_skin_refresh(void);
void ui_skin_on_destroy(void);

extern lv_obj_t *g_ui_root;
extern UiPage g_ui_page;

#endif
