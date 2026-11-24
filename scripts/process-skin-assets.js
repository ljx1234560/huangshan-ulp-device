/*
 * 皮肤素材批处理管线（可复现脚本，配 docs/animation-design.md 第 4 节）。
 *
 * 用途：把 assets/source/ 下的 1024x1024 宠物源图，中心裁剪 5:4
 *（顺带裁掉底部水印区），缩放导出固件规格 JPG：
 *   assets/skins/skin_<id>.jpg   220x176 主页舞台场景图
 *   assets/skins/thumb_<id>.jpg  120x96  皮肤页缩略图
 *
 * 依赖：Node.js 16+，jimp@0.22（npm install jimp@0.22.12）
 * 用法：
 *   node scripts/process-skin-assets.js            # 处理下方 SKINS 全部 5 套
 *   node scripts/process-skin-assets.js rainbow    # 只处理指定皮肤
 *
 * 新增/更新素材流程：
 *   1) 生成或取得 1024x1024 源图（AI 定制皮肤同规格）
 *   2) 命名为 assets/source/pet_source_<skin_id>.png
 *   3) 在 SKINS 表登记皮肤 ID（与 velapet_core.h 的 VELAPET_SKIN_* 对应）
 *   4) 运行本脚本，提交 assets/skins/ 产物
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
    console.error('缺少依赖：先执行 npm install jimp@0.22.12（任意目录均可）');
    process.exit(1);
}

const REPO = path.resolve(__dirname, '..');
const SRC = path.join(REPO, 'assets', 'source');
const SKIN_DIR = path.join(REPO, 'assets', 'skins');

/* 皮肤 ID 清单（与内核 VELAPET_SKIN_* 枚举对应） */
const SKINS = ['default', 'sport_blue', 'flame_red', 'star_purple', 'rainbow'];

/* 源图统一 1024x1024；裁剪目标比例 5:4 */
const SRC_SIZE = 1024;
const OUT_SPECS = [
    { prefix: 'skin_',  w: 220, h: 176 },
    { prefix: 'thumb_', w: 120, h: 96  },
];
const JPEG_QUALITY = 90;

async function process_one(id)
{
    const srcPath = path.join(SRC, 'pet_source_' + id + '.png');
    if (!fs.existsSync(srcPath))
    {
        console.log('SKIP', id, '(缺少', srcPath, ')');
        return;
    }
    const img = await Jimp.read(srcPath);

    /* 中心裁 5:4 */
    const cropW = Math.min(img.bitmap.width, SRC_SIZE);
    const cropH = Math.floor(cropW * 4 / 5);
    const y0 = Math.floor((img.bitmap.height - cropH) / 2);
    const scene = img.clone().crop(0, y0, cropW, cropH);

    fs.mkdirSync(SKIN_DIR, { recursive: true });
    for (const spec of OUT_SPECS)
    {
        await scene.clone()
            .resize(spec.w, spec.h)
            .quality(JPEG_QUALITY)
            .writeAsync(path.join(SKIN_DIR, spec.prefix + id + '.jpg'));
    }
    console.log('OK', id);
}

(async () =>
{
    const only = process.argv.slice(2);
    const list = (only.length > 0) ? only : SKINS;
    for (const id of list)
    {
        if (!SKINS.includes(id))
        {
            console.log('未知皮肤 ID:', id, '(可选:', SKINS.join(', '), ')');
            process.exitCode = 1;
            return;
        }
        await process_one(id);
    }
    console.log('DONE');
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
