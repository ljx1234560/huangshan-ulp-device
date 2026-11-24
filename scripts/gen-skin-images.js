#!/usr/bin/env node
/*
 * 皮肤素材 C 数组生成器（bin2c）。
 *
 * 用途：把 assets/skins/ 下的整帧场景图（skin_*.jpg，220x176）与列表缩略图
 * （thumb_*.jpg，120x96）转换为 LVGL lv_img_dsc_t RAW 描述符源码，
 * 输出到 src/ui/assets/ui_skin_img_data.h / .c。
 *
 * 设计要点：
 * - JPG 原始字节直接进固件，显示时由 LVGL v8 内置 TJpgDec 软解码（lv_conf 开
 *   LV_USE_TJPGD），不依赖任何 SDK 解码组件。
 * - 产物整体包在 #if VELAPET_UI_SKIN_IMAGES 内：开关未定义时编译为空，
 *   UI 自动退回几何替身。
 * - 数组顺序 = 权威皮肤顺序（见 src/ui/ui_skin_image.h 的 ui_skin_ids）。
 *
 * 运行：node scripts/gen-skin-images.js（仓库根目录下执行）
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SKIN_DIR = path.join(ROOT, 'assets', 'skins');
const OUT_DIR = path.join(ROOT, 'src', 'ui', 'assets');

/* 与 ui_skin_image.c / ui_skin.c 的展示顺序保持一致 */
const SKIN_ORDER = [
  'default',
  'sport_blue',
  'flame_red',
  'star_purple',
  'rainbow',
];

const FULL_W = 220;
const FULL_H = 176;
const THUMB_W = 120;
const THUMB_H = 96;

/* 解析 JPEG SOF0/SOF1/SOF2 段取宽高，防止素材被换错尺寸 */
function jpegSize(buf) {
  for (let i = 2; i < buf.length - 9;) {
    if (buf[i] !== 0xff) { i += 1; continue; }
    const marker = buf[i + 1];
    if (marker >= 0xc0 && marker <= 0xc2) {
      const h = (buf[i + 5] << 8) | buf[i + 6];
      const w = (buf[i + 7] << 8) | buf[i + 8];
      return { w, h };
    }
    const len = (buf[i + 2] << 8) | buf[i + 3];
    i += 2 + len;
  }
  return null;
}

function toCBytes(buf) {
  const lines = [];
  for (let i = 0; i < buf.length; i += 16) {
    const chunk = [];
    for (let j = i; j < Math.min(i + 16, buf.length); j += 1) {
      chunk.push('0x' + buf[j].toString(16).padStart(2, '0'));
    }
    lines.push('    ' + chunk.join(', ') + ',');
  }
  return lines.join('\n');
}

function loadSkins() {
  return SKIN_ORDER.map((id) => {
    const full = fs.readFileSync(path.join(SKIN_DIR, `skin_${id}.jpg`));
    const thumb = fs.readFileSync(path.join(SKIN_DIR, `thumb_${id}.jpg`));

    const fullSize = jpegSize(full);
    const thumbSize = jpegSize(thumb);
    if (!fullSize || fullSize.w !== FULL_W || fullSize.h !== FULL_H) {
      throw new Error(`skin_${id}.jpg 尺寸异常: ` + JSON.stringify(fullSize) +
                      `，期望 ${FULL_W}x${FULL_H}`);
    }
    if (!thumbSize || thumbSize.w !== THUMB_W || thumbSize.h !== THUMB_H) {
      throw new Error(`thumb_${id}.jpg 尺寸异常: ` + JSON.stringify(thumbSize) +
                      `，期望 ${THUMB_W}x${THUMB_H}`);
    }
    return { id, full, thumb };
  });
}

function buildHeader(skins) {
  const ids = skins.map((s) => `    "${s.id}",`).join('\n');
  return `/*
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

#define UI_SKIN_IMG_COUNT ${skins.length}
#define UI_SKIN_FULL_W ${FULL_W}
#define UI_SKIN_FULL_H ${FULL_H}
#define UI_SKIN_THUMB_W ${THUMB_W}
#define UI_SKIN_THUMB_H ${THUMB_H}

/* 权威皮肤 ID 顺序（与 ui_skin_image.c 的 ui_skin_ids 一致）
${ids}
 */
extern const lv_img_dsc_t ui_skin_img_full[UI_SKIN_IMG_COUNT];
extern const lv_img_dsc_t ui_skin_img_thumb[UI_SKIN_IMG_COUNT];

#endif /* VELAPET_UI_SKIN_IMAGES */

#endif /* VELAPET_UI_SKIN_IMG_DATA_H */
`;
}

function buildSource(skins) {
  const parts = [];
  parts.push(`/*
 * 由 scripts/gen-skin-images.js 自动生成，勿手改。
 * 数据体量：${skins.length} 整帧 + ${skins.length} 缩略图，JPG 原始字节。
 */
#include "ui_skin_img_data.h"

#if VELAPET_UI_SKIN_IMAGES
`);

  for (const s of skins) {
    parts.push(`/* skin_${s.id}: 整帧 ${s.full.length} B；缩略图 ${s.thumb.length} B */
static const uint8_t skin_full_${s.id}_jpg[] = {
${toCBytes(s.full)}
};

static const uint8_t skin_thumb_${s.id}_jpg[] = {
${toCBytes(s.thumb)}
};
`);
  }

  parts.push('const lv_img_dsc_t ui_skin_img_full[UI_SKIN_IMG_COUNT] = {\n');
  for (const s of skins) {
    parts.push(`    { .header = { .cf = LV_IMG_CF_RAW, .always_zero = 0, .reserved = 0,
                   .w = UI_SKIN_FULL_W, .h = UI_SKIN_FULL_H },
      .data = skin_full_${s.id}_jpg,
      .data_size = sizeof(skin_full_${s.id}_jpg) },
`);
  }
  parts.push('};\n\nconst lv_img_dsc_t ui_skin_img_thumb[UI_SKIN_IMG_COUNT] = {\n');
  for (const s of skins) {
    parts.push(`    { .header = { .cf = LV_IMG_CF_RAW, .always_zero = 0, .reserved = 0,
                   .w = UI_SKIN_THUMB_W, .h = UI_SKIN_THUMB_H },
      .data = skin_thumb_${s.id}_jpg,
      .data_size = sizeof(skin_thumb_${s.id}_jpg) },
`);
  }
  parts.push('};\n\n#endif /* VELAPET_UI_SKIN_IMAGES */\n');
  return parts.join('');
}

function main() {
  const skins = loadSkins();
  for (const s of skins) {
    if (s.full[0] !== 0xff || s.full[1] !== 0xd8 ||
        s.thumb[0] !== 0xff || s.thumb[1] !== 0xd8)
    {
      throw new Error(`skin_${s.id} 不是 JPEG 数据（缺 SOI 魔数）`);
    }
  }
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, 'ui_skin_img_data.h'), buildHeader(skins));
  fs.writeFileSync(path.join(OUT_DIR, 'ui_skin_img_data.c'), buildSource(skins));

  const total = skins.reduce((n, s) => n + s.full.length + s.thumb.length, 0);
  console.log(`生成完成: ${skins.length} 皮肤, JPG 总字节 ${total}`);
  skins.forEach((s) => console.log(
    `  ${s.id.padEnd(12)} full=${String(s.full.length).padStart(6)} B  thumb=${String(s.thumb.length).padStart(6)} B`));
}

main();
