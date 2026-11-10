#ifndef VELAPET_UI_SKIN_IMAGE_H
#define VELAPET_UI_SKIN_IMAGE_H

/*
 * 皮肤整帧图片接入层：把 assets/skins 的 JPG 场景图暴露给各页面。
 *
 * 硬件约束（handoff 第 6 节）：解码仅支持 JPG/SJPG，无透明通道，所以
 * 宠物形象 = 整帧场景图（背景烘焙在图里），主题只控制界面配色。
 *
 * 真机启用条件（三处同时满足，缺一自动退回几何替身）：
 *   1. 构建系统定义 VELAPET_UI_SKIN_IMAGES=1（rtconfig 的 CPPDEFINES）；
 *   2. lv_conf.h 打开 LV_USE_TJPGD 1 —— LVGL v8 内置 RAW JPEG 软解码器，
 *      直接解码 lv_img_dsc_t 里的 JPG 原始字节，不依赖任何 SDK 解码组件；
 *   3. lv_conf.h 设 LV_IMG_CACHE_DEF_SIZE >= 1（解码帧缓存，220x176 RGB565
 *      约 77 KB/帧，T113 内存充裕）。
 *
 * 演示与单测（PC，无 lv_conf 定制）：保持开关关闭，页面画几何替身。
 */

#include "lvgl.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* 皮肤总数，与 assets/skins、velapet_service 的预置皮肤一一对应 */
#define UI_SKIN_COUNT 5U

/* 权威皮肤 ID 顺序：索引即 ui_skin_img_full/thumb 数组下标。
 * 各页面一律用此表，不再自建拷贝。 */
extern const char *const ui_skin_ids[UI_SKIN_COUNT];

/* 皮肤 ID -> 数组下标；未知 ID 返回 -1 */
int ui_skin_image_index_of(const char *skin_id);

/* 整帧场景图 220x176（主页/形象页舞台）。
 * 开关未启用或下标越界返回 NULL，调用方回退几何替身。 */
const lv_img_dsc_t *ui_skin_image_full(uint8_t index);

/* 列表缩略图 120x96（皮肤页卡片） */
const lv_img_dsc_t *ui_skin_image_thumb(uint8_t index);

/* 1 = 图片数据已编译进固件；0 = 几何替身模式 */
int ui_skin_images_ready(void);

#ifdef __cplusplus
}
#endif

#endif /* VELAPET_UI_SKIN_IMAGE_H */
