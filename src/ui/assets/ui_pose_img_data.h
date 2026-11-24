#ifndef VELAPET_UI_POSE_IMG_DATA_H
#define VELAPET_UI_POSE_IMG_DATA_H

/*
 * 姿态帧数据表（由 scripts/gen-pose-frames.js 生成，勿手改）。
 * 共 4 帧；表顺序 = ui_skin_ids x ui_pose_action_t 顺序。
 */

#include "lvgl.h"

#include <stdint.h>

#if VELAPET_UI_POSE_FRAMES

#define UI_POSE_IMG_SKIN_COUNT 5U
#define UI_POSE_IMG_ACTION_COUNT 4U
#define UI_POSE_IMG_MAX_FRAMES 6U

extern const lv_img_dsc_t *const ui_pose_frame_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT][UI_POSE_IMG_MAX_FRAMES];
extern const uint8_t ui_pose_count_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT];

#endif /* VELAPET_UI_POSE_FRAMES */

#endif /* VELAPET_UI_POSE_IMG_DATA_H */
