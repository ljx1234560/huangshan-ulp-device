/*
 * 由 scripts/gen-skin-images.js 自动生成，勿手改。
 * 产物：整帧场景图与缩略图的 JPG 原始字节（RAW），显示端经 LVGL TJpgDec 解码。
 * 数组顺序 = ui_skin_ids 权威顺序。
 */
#ifndef VELAPET_UI_SKIN_IMG_DATA_H
#define VELAPET_UI_SKIN_IMG_DATA_H

#include "lvgl.h"

#ifndef VELAPET_UI_SKIN_IMAGES
#define VELAPET_UI_SKIN_IMAGES 0
#endif

#if VELAPET_UI_SKIN_IMAGES

#define UI_SKIN_IMG_COUNT 5
#define UI_SKIN_FULL_W 220
#define UI_SKIN_FULL_H 176
#define UI_SKIN_THUMB_W 120
#define UI_SKIN_THUMB_H 96

/* 权威皮肤 ID 顺序（与 ui_skin_image.c 的 ui_skin_ids 一致）
    "default",
    "sport_blue",
    "flame_red",
    "star_purple",
    "rainbow",
 */
extern const lv_img_dsc_t ui_skin_img_full[UI_SKIN_IMG_COUNT];
extern const lv_img_dsc_t ui_skin_img_thumb[UI_SKIN_IMG_COUNT];

#endif /* VELAPET_UI_SKIN_IMAGES */

#endif /* VELAPET_UI_SKIN_IMG_DATA_H */
