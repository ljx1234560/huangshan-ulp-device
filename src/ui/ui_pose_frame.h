#ifndef VELAPET_UI_POSE_FRAME_H
#define VELAPET_UI_POSE_FRAME_H

/*
 * 姿态帧组查询层：把管线生成的动作帧组暴露给动效模块。
 *
 * 帧组规格（docs/animation-design.md 4.1/第 4 节）：
 *   呼吸 2 帧 / 开心跳 2 帧 / 欢呼 3 帧 / 跳舞 6 帧，
 *   每帧 220x176 JPG，与主图同源同构图、仅肢体姿态不同。
 *
 * 数据由 scripts/gen-pose-frames.js 从 assets/poses/<skin_id>/ 生成到
 * src/ui/assets/ui_pose_img_data.c/.h；VELAPET_UI_POSE_FRAMES=1 时编译进固件。
 *
 * 解码条件与整帧皮肤图一致（TJpgDec + 图片缓存），真机三条件见
 * ui_skin_image.h 头注；任一不满足请勿打开本开关。
 */

#include "lvgl.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 动作枚举：顺序即帧表第二维下标，勿插入只可追加 */
typedef enum
{
    UI_POSE_BREATHE = 0, /* 呼吸（无限循环） */
    UI_POSE_HAPPY,       /* 单击开心跳 */
    UI_POSE_DANCE,       /* 双击跳舞 */
    UI_POSE_CHEER,       /* 签到/达标欢呼 */
    UI_POSE_ACTION_COUNT
} ui_pose_action_t;

/* 帧表最大帧数 = 跳舞 6 帧 */
#define UI_POSE_MAX_FRAMES 6U

/* 取某皮肤某动作的帧指针数组；*count 回写帧数。
 * 开关未开 / 素材越界 / 该组合无帧组时返回 NULL（调用方回退整图动画）。 */
const lv_img_dsc_t *const *ui_pose_frames(uint8_t skin_index,
                                          ui_pose_action_t action,
                                          uint8_t *count);

/* 1 = 姿态帧数据已编译进固件；0 = 无帧模式 */
int ui_pose_frames_ready(void);

#ifdef __cplusplus
}
#endif

#endif /* VELAPET_UI_POSE_FRAME_H */
