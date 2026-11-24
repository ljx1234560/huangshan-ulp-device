#!/usr/bin/env node
/*
 * 姿态帧裁切脚本（示范帧一次性入库用，量产帧走 Seedream 管线时复用逻辑）。
 *
 * 输入：assets/poses_raw/ 下的 1024x1024 PNG（AI 生图产物，底部带水印区）
 * 处理：中心裁 5:4（同 process-skin-assets.js，裁掉底部水印）→ 缩放 220x176 → JPG q90
 * 输出：assets/poses/<skin>/<action>_<n>.jpg
 * 另：把主图 skin_<skin>.jpg 字节复制为各动作的 _1 帧（帧 1 = 静态基准帧），
 *     gen-pose-frames.js 检测到与主图字节一致时直接引用 ui_skin_img_full，
 *     不产生重复数据。
 *
 * 用法：node scripts/process-pose-frames.js <raw.png> <skin> <action> <n>
 */
const fs = require('fs');
const path = require('path');

let Jimp;
try
{
    Jimp = require('jimp');
}
catch (e)
{
    console.error('缺少依赖：npm install jimp@0.22.12 --prefix .tooling 后运行');
    process.exit(1);
}

const REPO = path.resolve(__dirname, '..');
const SRC_SIZE = 1024;
const OUT_W = 220;
const OUT_H = 176;
const JPEG_QUALITY = 90;

async function main()
{
    const [rawPath, skin, action, n] = process.argv.slice(2);
    if (!rawPath || !skin || !action || !n)
    {
        console.error('用法: node scripts/process-pose-frames.js <raw.png> <skin> <action> <n>');
        process.exit(1);
    }
    const img = await Jimp.read(rawPath);
    /* 中心裁 5:4 */
    const cropW = Math.min(img.bitmap.width, SRC_SIZE);
    const cropH = Math.round(cropW * 4 / 5);
    const cropX = Math.round((img.bitmap.width - cropW) / 2);
    const cropY = Math.round((img.bitmap.height - cropH) / 2);
    img.crop(cropX, cropY, cropW, cropH);
    img.resize(OUT_W, OUT_H);
    img.quality(JPEG_QUALITY);

    const outDir = path.join(REPO, 'assets', 'poses', skin);
    fs.mkdirSync(outDir, { recursive: true });
    const outPath = path.join(outDir, `${action}_${n}.jpg`);
    await img.writeAsync(outPath);
    console.log('OK:', outPath);

    /* 帧 1 = 主图字节复制 */
    if (parseInt(n, 10) === 1)
    {
        const mainImg = path.join(REPO, 'assets', 'skins', `skin_${skin}.jpg`);
        if (fs.existsSync(mainImg))
        {
            fs.copyFileSync(mainImg, outPath);
            console.log('OK(帧1=主图复制):', outPath);
        }
    }
}

main().catch((e) => { console.error(e); process.exit(1); });
