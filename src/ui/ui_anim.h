#ifndef VELAPET_UI_ANIM_H
#define VELAPET_UI_ANIM_H

#include "lvgl.h"

/*
 * 前端动效模块（规格见 docs/animation-design.md）。
 * 动画只使用样式变换（zoom/angle/translate/opa），不改动布局；
 * 动作动画结束后自动重启待机呼吸；transform 样式需要 LVGL v8.2+，
 * 低版本编译时自动降级为位移 + 淡入（呼吸退化为透明度呼吸）。
 */

/* A4 待机呼吸：zoom 256->264 循环（低版本为透明度呼吸）。 */
void ui_anim_breathe(lv_obj_t *obj);

/* A1 单击开心跳两下（约 600ms），结束自动重启呼吸。 */
void ui_anim_happy(lv_obj_t *obj);

/* A2 双击跳舞：摇摆 +-15 度 + 弹跳，约 2 秒，结束自动重启呼吸。 */
void ui_anim_dance(lv_obj_t *obj);

/* A5 弹跳欢呼两连跳（约 600ms），可用于任意卡片。 */
void ui_anim_cheer(lv_obj_t *obj);

/* A8/A9 淡入（220ms）；from_x 非 0 时叠加自右向左的横滑进入。 */
void ui_anim_fade_in(lv_obj_t *obj, lv_coord_t from_x);

/* 清空对象上的全部动画并复位样式（切页/销毁时调用）。 */
void ui_anim_stop(lv_obj_t *obj);

/* 单击/双击判别绑定：250ms 时间窗（规格第 3 节）。
 * single_cb / double_cb 允许为 NULL；obj 销毁时自动清理内部上下文。
 * 若 obj 的子对象需要参与命中，请先对子树加 LV_OBJ_FLAG_EVENT_BUBBLE。 */
void ui_anim_bind_tap(lv_obj_t *obj,
                      void (*single_cb)(lv_obj_t *obj),
                      void (*double_cb)(lv_obj_t *obj));

#endif
