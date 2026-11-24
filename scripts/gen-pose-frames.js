#!/usr/bin/env node
/*
 * 姿态帧 C 数组生成器（bin2c，配 docs/animation-design.md 4.1 帧序列机制）。
 *
 * 输入：assets/poses/<skin_id>/<action>_<n>.jpg（220x176，n 从 1 起）
 *       例：assets/poses/default/happy_1.jpg ... happy_2.jpg
 * 输出：src/ui/assets/ui_pose_img_data.h / .c（LVGL lv_img_dsc_t RAW 描述符）
 *
 * 与 gen-skin-images.js 同构：JPG 原始字节进固件，显示时 TJpgDec 软解码。
 * 帧顺序 = 文件名 n 升序；某动作一帧都没有时该槽 count=0（UI 自动回退整图动画）。
 * 产物整体包在 #if VELAPET_UI_POSE_FRAMES 内：开关未定义时编译为空。
 *
 * 运行：node scripts/gen-pose-frames.js
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const POSE_DIR = path.join(ROOT, 'assets', 'poses');
const SKIN_DIR = path.join(ROOT, 'assets', 'skins');
const OUT_DIR = path.join(ROOT, 'src', 'ui', 'assets');

/* 与 ui_skin_image.c 的 ui_skin_ids / ui_pose_frame.h 的动作枚举顺序一致 */
const SKIN_ORDER = [
  'default',
  'sport_blue',
  'flame_red',
  'star_purple',
  'rainbow',
];
const ACTION_ORDER = ['breathe', 'happy', 'dance', 'cheer'];

const FULL_W = 220;
const FULL_H = 176;

/* 解析 JPEG SOF0/SOF1/SOF2 段取宽高，防止素材被换错尺寸（复用皮肤管线断言） */
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
  throw new Error('非 JPEG 或无法解析 SOF 段');
}

function cIdentifier(skin, action, n) {
  return `ui_pose_${skin}_${action}_${n}`;
}

const sha1 = (buf) => crypto.createHash('sha1').update(buf).digest('hex');

/* 主图指纹表：帧文件与主图字节一致时直接引用 ui_skin_img_full，不重复嵌入 */
function mainImageDigests() {
  const digests = {};
  for (const skin of SKIN_ORDER) {
    const p = path.join(SKIN_DIR, `skin_${skin}.jpg`);
    if (fs.existsSync(p)) digests[skin] = sha1(fs.readFileSync(p));
  }
  return digests;
}

function cBytes(buf) {
  const lines = [];
  for (let i = 0; i < buf.length; i += 16) {
    const chunk = [];
    for (let j = i; j < Math.min(i + 16, buf.length); j++) {
      chunk.push('0x' + buf[j].toString(16).padStart(2, '0'));
    }
    lines.push('    ' + chunk.join(', ') + ',');
  }
  return lines.join('\n');
}

function main() {
  if (!fs.existsSync(POSE_DIR)) {
    console.log('SKIP: assets/poses/ 不存在，无姿态帧素材');
    process.exit(0);
  }

  /* 收集：poses[skin][action] = [ {n, file, buf, size} 按帧号升序 ] */
  const poses = {};
  let frameTotal = 0;
  for (const skin of SKIN_ORDER) {
    const skinDir = path.join(POSE_DIR, skin);
    if (!fs.existsSync(skinDir)) continue;
    poses[skin] = {};
    for (const action of ACTION_ORDER) {
      const re = new RegExp(`^${action}_(\\d+)\\.jpg$`, 'i');
      const frames = fs.readdirSync(skinDir)
        .map((f) => {
          const m = f.match(re);
          if (!m) return null;
          const buf = fs.readFileSync(path.join(skinDir, f));
          const size = jpegSize(buf);
          if (size.w !== FULL_W || size.h !== FULL_H) {
            throw new Error(`${f}: 尺寸 ${size.w}x${size.h} != ${FULL_W}x${FULL_H}（必须与主图同规格）`);
          }
          return { n: parseInt(m[1], 10), file: f, buf, sha: sha1(buf) };
        })
        .filter(Boolean)
        .sort((a, b) => a.n - b.n);
      if (frames.length > 0) {
        poses[skin][action] = frames;
        frameTotal += frames.length;
        console.log(`  ${skin}/${action}: ${frames.length} 帧`);
      }
    }
  }

  if (frameTotal === 0) {
    console.log('SKIP: assets/poses/ 下无有效帧素材');
    process.exit(0);
  }

  /* 生成 .h */
  const hBuf = `#ifndef VELAPET_UI_POSE_IMG_DATA_H
#define VELAPET_UI_POSE_IMG_DATA_H

/*
 * 姿态帧数据表（由 scripts/gen-pose-frames.js 生成，勿手改）。
 * 共 ${frameTotal} 帧；表顺序 = ui_skin_ids x ui_pose_action_t 顺序。
 */

#include "lvgl.h"

#include <stdint.h>

#if VELAPET_UI_POSE_FRAMES

#define UI_POSE_IMG_SKIN_COUNT ${SKIN_ORDER.length}U
#define UI_POSE_IMG_ACTION_COUNT ${ACTION_ORDER.length}U
#define UI_POSE_IMG_MAX_FRAMES 6U

extern const lv_img_dsc_t *const ui_pose_frame_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT][UI_POSE_IMG_MAX_FRAMES];
extern const uint8_t ui_pose_count_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT];

#endif /* VELAPET_UI_POSE_FRAMES */

#endif /* VELAPET_UI_POSE_IMG_DATA_H */
`;

  /* 生成 .c */
  const dscs = [];
  const skinBlocks = [];
  const countRows = [];
  const digests = mainImageDigests();

  for (let s = 0; s < SKIN_ORDER.length; s++) {
    const skin = SKIN_ORDER[s];
    const actionRows = [];
    for (let a = 0; a < ACTION_ORDER.length; a++) {
      const action = ACTION_ORDER[a];
      const frames = (poses[skin] && poses[skin][action]) || [];
      /* 帧表行：MAX_FRAMES 定长，不足补 NULL；与主图字节一致的帧引用主图 dsc */
      const ptrs = [];
      for (let f = 0; f < 6; f++) {
        if (f >= frames.length) { ptrs.push('NULL'); continue; }
        const fr = frames[f];
        if (digests[skin] && fr.sha === digests[skin]) {
          ptrs.push(`&ui_skin_img_full[${s}] /* 主图复用 */`);
        } else {
          ptrs.push(`&${cIdentifier(skin, action, fr.n)}`);
        }
      }
      actionRows.push(`        { ${ptrs.join(', ')} }, /* ${action} */`);
      countRows.push(`    ${frames.length}U, /* ${skin}/${action} */`);
      for (const fr of frames) {
        if (digests[skin] && fr.sha === digests[skin]) continue; /* 主图已有，跳过 */
        const id = cIdentifier(skin, action, fr.n);
        dscs.push(`/* ${skin}/${action} 帧 ${fr.n}：${fr.file} ${fr.buf.length} 字节 */
static const uint8_t ${id}_data[] = {
${cBytes(fr.buf)}
};

const lv_img_dsc_t ${id} = {
    .header.always_zero = 0,
    .header.w = ${FULL_W},
    .header.h = ${FULL_H},
    .header.cf = LV_IMG_CF_RAW,
    .data_size = sizeof(${id}_data),
    .data = ${id}_data,
};
`);
      }
    }
    /* 三维表：每个皮肤块外层包一层花括号，内含 ACTION_COUNT 个动作行 */
    skinBlocks.push(`    { /* ${skin} */
${actionRows.join('\n')}
    }`);
  }

  const cBuf = `/* 姿态帧数据（由 scripts/gen-pose-frames.js 生成，勿手改） */
#include "ui_pose_img_data.h"
#include "ui_pose_frame.h"
#include "ui_skin_img_data.h"

#if VELAPET_UI_POSE_FRAMES
#if !VELAPET_UI_SKIN_IMAGES
#error "VELAPET_UI_POSE_FRAMES 依赖 VELAPET_UI_SKIN_IMAGES（帧表引用主图 dsc）"
#endif

${dscs.join('\n')}

const lv_img_dsc_t *const ui_pose_frame_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT][UI_POSE_IMG_MAX_FRAMES] = {
${skinBlocks.join(',\n')}
};

const uint8_t ui_pose_count_table[UI_POSE_IMG_SKIN_COUNT][UI_POSE_IMG_ACTION_COUNT] = {
${countRows.join('\n')}
};

#endif /* VELAPET_UI_POSE_FRAMES */
`;

  fs.writeFileSync(path.join(OUT_DIR, 'ui_pose_img_data.h'), hBuf);
  fs.writeFileSync(path.join(OUT_DIR, 'ui_pose_img_data.c'), cBuf);
  console.log(`OK: ${frameTotal} 帧 -> src/ui/assets/ui_pose_img_data.h/.c`);
}

main();
