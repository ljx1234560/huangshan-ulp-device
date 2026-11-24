#ifndef VELAPET_UI_FRAME_SEQ_H
#define VELAPET_UI_FRAME_SEQ_H

/*
 * 帧序列播放器：姿态帧组（sprite sheet 的逐帧版）在 LVGL 上的通用轮播。
 *
 * 原理：姿态帧是"与主图同规格、仅肢体姿态不同"的整帧 JPG（无透明通道约束
 * 下的部位动效方案，见 docs/animation-design.md 4.1）。播放 = lv_timer 按
 * frame_ms 周期对 lv_img 切换源描述符；帧管"肢体在动"，不再依赖整图位移。
 *
 * 与整身动画的关系：
 *   - 播放期间该对象不要再叠加 zoom/angle/translate 动画（会撕裂观感），
 *     ui_anim 的动作接口已在帧组就绪时自动改走本播放器；
 *   - play 记录当前源为基础帧，stop/播完后自动恢复。
 *
 * 资源：每槽一个 lv_timer；对象删除时自动清理（LV_EVENT_DELETE）。
 * 并发：内部固定槽位表（当前 UI 同时最多 2 个舞台），槽满时 play 静默拒绝。
 */

#include "lvgl.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    const lv_img_dsc_t *const *frames; /* 帧指针数组（前 count 个必须有效） */
    uint8_t count;                     /* 帧数 1..255 */
    uint16_t frame_ms;                 /* 每帧时长：8-12 FPS 建议 83~125ms */
    int32_t loops;                     /* 播放轮数；-1 = 无限循环（呼吸） */
    void (*done_cb)(lv_obj_t *img);    /* 有限轮播结束回调（可 NULL） */
} ui_frame_seq_cfg_t;

/* 开始播放。同对象已在播则先停再播；cfg 非法时静默忽略。
 * 立即显示第 0 帧，之后每 frame_ms 前进一帧。 */
void ui_frame_seq_play(lv_obj_t *img, const ui_frame_seq_cfg_t *cfg);

/* 停止并恢复基础帧；未在播放时为无害空操作。 */
void ui_frame_seq_stop(lv_obj_t *img);

/* 1 = 该对象当前正在播帧序列 */
int ui_frame_seq_active(const lv_obj_t *img);

#ifdef __cplusplus
}
#endif

#endif /* VELAPET_UI_FRAME_SEQ_H */
