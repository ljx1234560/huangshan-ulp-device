#ifndef VELAPET_UI_FONTS_H
#define VELAPET_UI_FONTS_H

/*
 * 内置中文字体子集（等线/DengXian，GB2312 一级常用字 3779 字 + ASCII）。
 * 生成命令见仓库 scripts/gen-cn-font.sh。--no-compress 无需 LV_USE_FONT_COMPRESSED。
 * 版权提示：等线为 Windows 附带字体，仅限课程开发演示；
 * 公开演示/发布前替换为 OFL 开源字体（思源黑体/Alibaba PuHuiTi）重新生成。
 */

#include "lvgl.h"

#ifdef __cplusplus
extern "C" {
#endif

/* 16px：正文/气泡/按钮 */
extern const lv_font_t ui_font_cn_16;
/* 20px：页面标题/宠物名 */
extern const lv_font_t ui_font_cn_20;

#ifdef __cplusplus
}
#endif

#endif
