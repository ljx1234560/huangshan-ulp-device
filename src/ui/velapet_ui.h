#ifndef VELAPET_UI_H
#define VELAPET_UI_H

/*
 * 前端对外入口。main 在 LVGL/触摸初始化后调用 velapet_ui_init()。
 * 数据一律来自 velapet_service 快照；外部数据变化后调用 velapet_ui_refresh_all()。
 */

#ifdef __cplusplus
extern "C" {
#endif

/* 成功返回 0；业务服务初始化失败返回 -1。 */
int velapet_ui_init(void);

void velapet_ui_show_home(void);
void velapet_ui_show_task(void);
void velapet_ui_show_chat(void);
void velapet_ui_show_pet_image(void);
void velapet_ui_show_skin(void);

/* 数据变化后刷新当前页。 */
void velapet_ui_refresh_all(void);

/*
 * AI 回复回填：统一走 src/ui/ui_ai_bridge.h 的信箱接口
 * （ui_ai_bridge_push_result 由端侧 AI 服务线程调用），
 * 聊天页在自己的定时器里取结果并渲染，不再提供直接 setter。
 */

#ifdef __cplusplus
}
#endif

#endif
