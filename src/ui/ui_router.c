#include "ui_internal.h"

/*
 * 五页路由：主页 / 任务 / 聊天 / 形象 / 皮肤。
 * 切页 = 销毁回调 + 删除页面根对象 + 创建新页；
 * 同页重复触发不重建（防连点），换肤等需要重载的场景走 ui_router_reload()。
 */

static void destroy_current(void)
{
    switch (g_ui_page)
    {
    case UI_PAGE_TASK: ui_task_on_destroy(); break;
    case UI_PAGE_CHAT: ui_chat_on_destroy(); break;
    case UI_PAGE_PET_IMAGE: ui_avatar_on_destroy(); break;
    case UI_PAGE_SKIN: ui_skin_on_destroy(); break;
    case UI_PAGE_HOME:
    default: ui_home_on_destroy(); break;
    }

    if (g_ui_root != NULL)
    {
        lv_obj_del(g_ui_root);
        g_ui_root = NULL;
    }
}

static void show_page(UiPage page, void (*create)(void))
{
    if (g_ui_page == page && g_ui_root != NULL)
    {
        return;
    }
    destroy_current();
    g_ui_page = page;
    create();
    /* A9 切页淡入 + 横滑进入。 */
    ui_anim_fade_in(g_ui_root, 24);
}

void ui_router_show_home(void)
{
    show_page(UI_PAGE_HOME, ui_home_create);
}

void ui_router_show_task(void)
{
    show_page(UI_PAGE_TASK, ui_task_create);
}

void ui_router_show_chat(void)
{
    show_page(UI_PAGE_CHAT, ui_chat_create);
}

void ui_router_show_pet_image(void)
{
    show_page(UI_PAGE_PET_IMAGE, ui_avatar_create);
}

void ui_router_show_skin(void)
{
    show_page(UI_PAGE_SKIN, ui_skin_create);
}

void ui_router_reload(void)
{
    destroy_current();
    switch (g_ui_page)
    {
    case UI_PAGE_TASK: ui_task_create(); break;
    case UI_PAGE_CHAT: ui_chat_create(); break;
    case UI_PAGE_PET_IMAGE: ui_avatar_create(); break;
    case UI_PAGE_SKIN: ui_skin_create(); break;
    case UI_PAGE_HOME:
    default: ui_home_create(); break;
    }
    /* A8 换肤重载后的整页淡入。 */
    ui_anim_fade_in(g_ui_root, 0);
}
