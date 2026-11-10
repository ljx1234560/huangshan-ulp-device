#include "ui_internal.h"

#include <rtthread.h>

#ifdef FINSH_USING_MSH
#include <finsh.h>
#endif

lv_obj_t *g_ui_root = NULL;
UiPage g_ui_page = UI_PAGE_HOME;

static uint32_t g_tap_count;
static const char *g_last_action = "NONE";

void ui_note_event(const char *action)
{
    g_tap_count++;
    g_last_action = action;
    rt_kprintf("[ui] tap=%lu action=%s\n",
               (unsigned long)g_tap_count,
               (action != NULL) ? action : "?");
}

int velapet_ui_init(void)
{
    const velapet_snapshot_t *snap;

    /* TODO: 接 RTC 后 day_id 改为真实日期序号；当前演示恒为同一天。 */
    if (velapet_service_init(0U) != 0)
    {
        rt_kprintf("[ui] init=FAIL service\n");
        return -1;
    }

    snap = velapet_service_snapshot();
    ui_apply_theme_by_skin((snap != NULL) ? snap->current_skin : NULL);
    ui_router_show_home();

    rt_kprintf("[ui] init=PASS skin=%s level=%u\n",
               (snap != NULL) ? snap->current_skin : "default",
               (snap != NULL) ? (unsigned)snap->level : 1U);
    return 0;
}

void velapet_ui_show_home(void) { ui_router_show_home(); }

void velapet_ui_show_task(void)
{
    ui_note_event("NAV->TASK");
    ui_router_show_task();
}

void velapet_ui_show_chat(void)
{
    ui_note_event("NAV->CHAT");
    ui_router_show_chat();
}

void velapet_ui_show_pet_image(void)
{
    ui_note_event("NAV->PET");
    ui_router_show_pet_image();
}

void velapet_ui_show_skin(void)
{
    ui_note_event("NAV->SKIN");
    ui_router_show_skin();
}

void velapet_ui_refresh_all(void)
{
    switch (g_ui_page)
    {
    case UI_PAGE_TASK: ui_task_refresh(); break;
    case UI_PAGE_PET_IMAGE: ui_avatar_refresh(); break;
    case UI_PAGE_SKIN: ui_skin_refresh(); break;
    case UI_PAGE_CHAT: break; /* 聊天页数据走 AI 桥接信箱 */
    case UI_PAGE_HOME:
    default: ui_home_refresh(); break;
    }
}

#ifdef FINSH_USING_MSH
static int ui_status(int argc, char **argv)
{
    (void)argc;
    (void)argv;

    rt_kprintf("[ui] status=%s taps=%lu last=%s\n",
               (g_tap_count > 0U) ? "PASS" : "WAITING",
               (unsigned long)g_tap_count,
               g_last_action);
    return 0;
}
MSH_CMD_EXPORT(ui_status, show VelaPet UI touch status);
#endif
